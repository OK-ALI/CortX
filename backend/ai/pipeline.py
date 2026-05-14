from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
import time
from typing import Callable

from backend.ai.followup_intent import FollowupIntentResolver
from backend.ai.intent_chain import IntentResult, extract_intent
from backend.ai.llm_manager import create_ollama_client, get_llm_availability
from backend.ai.query_chain import generate_search_queries
from backend.ai.synth_chain import SynthesisResult, synthesize_answer
from backend.processor.ranker import rank_pages
from backend.processor.text_cleaner import clean_text
from backend.processor.truncator import truncate_words
from backend.scraper.scraper_engine import ScraperEngine, ScrapedPage
from backend.search.web_search import SearchResult, discover_urls
from backend.utils.config import Settings
from database.lance_store import LanceStore


@dataclass
class PipelineResult:
    query: str
    intent: IntentResult
    queries: list[str]
    urls: list[str]
    pages: list[ScrapedPage]
    answer: str
    sources: list[str] = field(default_factory=list)


# Type alias for optional status callbacks
StatusCallback = Callable[[str], None] | None


class CortxPipeline:
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        status_callback: StatusCallback = None,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.status_callback = status_callback
        self.store = LanceStore()
        self.llm_client = None
        self.followup_resolver = FollowupIntentResolver()

        llm_availability = get_llm_availability(
            ollama_url=settings.ollama_url,
            ollama_model=settings.models.local_model,
        )

        if settings.models.enable_ollama_chains and llm_availability.ollama_enabled:
            self.llm_client = create_ollama_client(
                base_url=settings.ollama_url,
                model=settings.models.local_model,
                timeout_seconds=settings.models.ollama_timeout_seconds,
                keep_alive=settings.models.ollama_keep_alive,
            )
            self.logger.info(
                "Ollama enabled with model %s",
                settings.models.local_model,
            )
            if settings.models.warmup_ollama_on_start:
                warmed = self.llm_client.warm_model()
                if warmed:
                    self.logger.info(
                        "Ollama model warmed and kept alive for %s",
                        settings.models.ollama_keep_alive,
                    )
                else:
                    self.logger.warning("Ollama warmup failed; runtime fallback remains enabled")
        elif settings.models.enable_ollama_chains:
            self.logger.warning("Ollama requested but model/service unavailable; using heuristic flow")

        self.scraper = ScraperEngine(
            timeout_seconds=settings.network.httpx_timeout_seconds,
            user_agent=settings.scraper.user_agent,
            min_words_per_page=settings.app.min_words_per_page,
            cache_db=self.store,
            cache_ttl_seconds=settings.cache.ttl_seconds,
            delay_min_seconds=settings.scraper.random_delay_min_seconds,
            delay_max_seconds=settings.scraper.random_delay_max_seconds,
        )

    def _emit_status(self, message: str) -> None:
        if self.status_callback:
            try:
                self.status_callback(message)
            except Exception:
                pass

    @staticmethod
    def _extract_url_from_source(source: str) -> str:
        match = re.search(r"https?://[^\s\]\)]+", source)
        if not match:
            return ""
        return match.group(0).rstrip("/ ")

    def _prioritize_new_sources(
        self,
        search_results: list[SearchResult],
        conversation_messages: list[dict] | None,
        update_intent: bool,
    ) -> list[SearchResult]:
        if not update_intent or not conversation_messages:
            return search_results

        seen_urls: set[str] = set()
        for item in conversation_messages:
            if str(item.get("role", "")).strip().lower() != "assistant":
                continue
            for source in item.get("sources", []) or []:
                normalized = self._extract_url_from_source(str(source))
                if normalized:
                    seen_urls.add(normalized)

        if not seen_urls:
            return search_results

        unseen: list[SearchResult] = []
        seen: list[SearchResult] = []
        for result in search_results:
            normalized = result.url.rstrip("/ ")
            if normalized in seen_urls:
                seen.append(result)
            else:
                unseen.append(result)
        return unseen + seen

    def shutdown(self) -> None:
        """Release runtime resources, including optional Ollama unload."""
        if self.llm_client is None:
            return

        if not self.settings.models.unload_ollama_on_exit:
            self.logger.info("Skipping Ollama unload on exit by configuration")
            return

        unloaded = self.llm_client.unload_model()
        if unloaded:
            self.logger.info("Ollama model unload requested successfully")
        else:
            self.logger.warning("Ollama model unload request failed")

    async def run(
        self,
        query: str,
        conversation_messages: list[dict] | None = None,
        explicit_context: dict | None = None,
    ) -> PipelineResult:
        pipeline_start = time.perf_counter()
        resolution = self.followup_resolver.resolve(
            query=query,
            conversation_messages=conversation_messages,
            llm_client=self.llm_client,
            explicit_context=explicit_context,
        )
        resolved_query = resolution.standalone_query
        used_memory = resolution.requires_context
        update_intent = resolution.update_intent
        self.logger.info("=" * 60)
        self.logger.info("PIPELINE START | query=%s", query[:80])
        if used_memory:
            self.logger.info("Follow-up memory enabled for query resolution")
        if update_intent:
            self.logger.info("Detected update intent; prioritizing fresh results")
        self.logger.info("=" * 60)

        removed = self.store.cache_invalidate_stale(self.settings.cache.ttl_seconds)
        if removed > 0:
            self.logger.info("Cache cleanup: removed %s stale entries", removed)

        # ------------------------------------------------------------------
        # Step 1: Intent & query generation
        # ------------------------------------------------------------------
        self._emit_status("Analyzing your question...")
        t0 = time.perf_counter()
        intent = extract_intent(resolved_query, llm_client=self.llm_client)
        t_intent = time.perf_counter() - t0
        self.logger.info("[Step 1/6] Intent extracted: %s (%.1fs)", intent.intent_type, t_intent)

        t0 = time.perf_counter()
        queries = generate_search_queries(resolved_query, intent, llm_client=self.llm_client)
        t_queries = time.perf_counter() - t0
        self.logger.info("[Step 2/6] Search queries generated (%.1fs):", t_queries)
        for i, q in enumerate(queries, 1):
            self.logger.info("  Q%d: %s", i, q)

        # ------------------------------------------------------------------
        # Step 3: Search
        # ------------------------------------------------------------------
        self._emit_status("Searching the web...")
        t0 = time.perf_counter()
        search_results: list[SearchResult] = discover_urls(
            queries,
            max_urls=self.settings.app.max_urls,
            return_results=True,
            time_sensitivity="recent" if update_intent else intent.time_sensitivity,
        )
        search_results = self._prioritize_new_sources(search_results, conversation_messages, update_intent)
        t_search = time.perf_counter() - t0
        urls = [r.url for r in search_results]
        search_snippets = [r.snippet for r in search_results if r.snippet]
        self.logger.info("[Step 3/6] Web search complete: %d URLs found (%.1fs)", len(urls), t_search)

        # ------------------------------------------------------------------
        # Step 4: Scrape
        # ------------------------------------------------------------------
        page_count = len(urls)
        self._emit_status(f"Reading {page_count} web pages...")
        t0 = time.perf_counter()
        pages = await self.scraper.scrape(urls)
        t_scrape = time.perf_counter() - t0

        stats = self.scraper.last_stats
        self.logger.info("[Step 4/6] Scraping complete (%.1fs)", t_scrape)
        self.logger.info("  ├─ Requested:      %d URLs", stats.total_requested)
        self.logger.info("  ├─ Cache hits:      %d", stats.cache_hits)
        self.logger.info("  ├─ Robots blocked:  %d", stats.robots_blocked)
        self.logger.info("  ├─ Bot challenges:  %d", stats.bot_challenges)
        self.logger.info("  ├─ Tier 1 (httpx):  %d succeeded", stats.tier1_success)
        self.logger.info("  ├─ Tier 2 (Playwright): %d attempted → %d succeeded", stats.tier2_attempted, stats.tier2_success)
        self.logger.info("  └─ Failed:          %d", stats.failed_urls)

        # Log per-page tier info
        for page in pages:
            word_count = len(page.text.split())
            self.logger.info("  ✓ [%s] %s (%d words)", page.tier.upper(), page.url[:80], word_count)

        # ------------------------------------------------------------------
        # Step 5: Clean, truncate, rank
        # ------------------------------------------------------------------
        self._emit_status("Processing content...")
        t0 = time.perf_counter()
        processed_pages: list[ScrapedPage] = []
        for page in pages:
            text = clean_text(page.text)
            text = truncate_words(text, self.settings.limits.max_words_per_page, query=query)
            processed_pages.append(ScrapedPage(url=page.url, text=text, tier=page.tier))

        ranked = rank_pages(resolved_query, processed_pages)
        t_rank = time.perf_counter() - t0
        self.logger.info("[Step 5/6] Ranked %d pages (%.1fs)", len(ranked), t_rank)
        for i, rp in enumerate(ranked[:5], 1):
            self.logger.info("  #%d [score=%.3f] %s", i, rp.score, rp.url[:80])

        # ------------------------------------------------------------------
        # Step 6: Synthesize
        # ------------------------------------------------------------------
        self._emit_status("Generating answer...")
        t0 = time.perf_counter()
        synthesis_result: SynthesisResult = synthesize_answer(
            query=resolved_query,
            ranked_pages=ranked,
            max_pages=self.settings.limits.max_pages_for_synthesis,
            refined_queries=queries,
            llm_client=self.llm_client,
            enable_llm_synthesis=self.settings.models.enable_llm_synthesis,
            enable_llm_result_refinement=self.settings.models.enable_llm_result_refinement,
            search_snippets=search_snippets,
        )
        t_synth = time.perf_counter() - t0
        answer_words = len(synthesis_result.answer.split())
        self.logger.info("[Step 6/6] Synthesis complete: %d words, %d sources (%.1fs)", answer_words, len(synthesis_result.sources), t_synth)

        total_time = time.perf_counter() - pipeline_start
        self.logger.info("=" * 60)
        self.logger.info("PIPELINE COMPLETE | total=%.1fs", total_time)
        self.logger.info("  Intent: %.1fs | Queries: %.1fs | Search: %.1fs", t_intent, t_queries, t_search)
        self.logger.info("  Scrape: %.1fs | Rank: %.1fs | Synthesis: %.1fs", t_scrape, t_rank, t_synth)
        self.logger.info("=" * 60)

        return PipelineResult(
            query=query,
            intent=intent,
            queries=queries,
            urls=urls,
            pages=processed_pages,
            answer=synthesis_result.answer,
            sources=synthesis_result.sources,
        )
