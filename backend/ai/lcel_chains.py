from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from backend.ai.llm_manager import OllamaClient


_DEFAULT_PROMPTS: dict[str, str] = {
    "intent_system": (
        "Classify the user query intent and return strict JSON only with keys: "
        "intent_type, entities, time_sensitivity. intent_type must be one of factual, "
        "research, news, comparison. time_sensitivity must be one of recent, historical, "
        "timeless. entities must be an array of strings."
    ),
    "query_system": (
        "Generate exactly 3 diverse web search queries. Return strict JSON only: "
        '{"queries": ["...", "...", "..."]}. '
        "Avoid long prose and keep each query concise."
    ),
    "refine_system": (
        "You are an extractive refinement assistant. Refine only by reorganizing and "
        "clarifying provided scraped excerpts. Do not add new facts, claims, numbers, "
        "dates, entities, or sources. Do not invent or alter URLs."
    ),
    "ack_system": (
        "Write a single-line acknowledgement for a scrape-grounded answer. "
        "Use only provided snippets. No invented facts. 8 to 18 words."
    ),
    "synthesis_system": (
        "You are CortX, an expert research assistant. Produce a clear, well-structured "
        "answer to the user's question using ONLY the provided scraped web content. "
        "Use markdown formatting. Include inline citation markers like [1], [2]. "
        "Do not invent facts. Keep the answer concise but comprehensive (150-400 words). "
        "Write in a natural, conversational tone. Do NOT include raw URLs in the body."
    ),
    "followup_system": (
        "Resolve conversational follow-up queries for web research. "
        "Given recent conversation context and the latest user query, return strict JSON only with keys: "
        "standalone_query (string), requires_context (boolean), update_intent (boolean), context_focus (string), "
        "action_type (string: ask|reply|follow|update). "
        "If the user asks for new/latest updates about prior topic, set update_intent=true and ensure standalone_query "
        "explicitly includes fresh/update wording."
    ),
    "spell_system": (
        "You are a strict query refiner and spell-checker. "
        "Fix any grammatical or spelling mistakes in the user query while keeping its original meaning intact. "
        "Return ONLY the corrected string and nothing else. No quotes, no preamble."
    ),
    "title_system": (
        "You are a summarization assistant. Generate a snappy 2 to 4 word title for this chat based on the user query. "
        "Return ONLY the title string and nothing else. No quotes, no preamble."
    ),
}


def _load_prompts(path: str | Path = "config/prompts.yaml") -> dict[str, str]:
    config_path = Path(path)
    if not config_path.exists():
        return dict(_DEFAULT_PROMPTS)

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    return {
        "intent_system": str(data.get("intent_lcel_system", _DEFAULT_PROMPTS["intent_system"])),
        "query_system": str(data.get("query_lcel_system", _DEFAULT_PROMPTS["query_system"])),
        "refine_system": str(data.get("refine_lcel_system", _DEFAULT_PROMPTS["refine_system"])),
        "ack_system": str(data.get("ack_lcel_system", _DEFAULT_PROMPTS["ack_system"])),
        "synthesis_system": str(data.get("synthesis_lcel_system", _DEFAULT_PROMPTS["synthesis_system"])),
        "followup_system": str(data.get("followup_lcel_system", _DEFAULT_PROMPTS["followup_system"])),
        "spell_system": str(data.get("spell_lcel_system", _DEFAULT_PROMPTS["spell_system"])),
        "title_system": str(data.get("title_lcel_system", _DEFAULT_PROMPTS["title_system"])),
    }


@dataclass
class LocalLCELChains:
    llm_client: OllamaClient
    prompt_path: str = "config/prompts.yaml"

    def __post_init__(self) -> None:
        prompts = _load_prompts(self.prompt_path)

        self._intent_chain = self._build_chain(
            system_prompt=prompts["intent_system"],
            human_template="Query: {query}",
            temperature=0.0,
        )
        self._query_chain = self._build_chain(
            system_prompt=prompts["query_system"],
            human_template=(
                "Original query: {original_query}\n"
                "Intent type: {intent_type}\n"
                "Time sensitivity: {time_sensitivity}\n"
                "Entities: {entities}"
            ),
            temperature=0.2,
        )
        self._refine_chain = self._build_chain(
            system_prompt=prompts["refine_system"],
            human_template=(
                "Return refined findings text only (no headings, no sections).\n"
                "Rules:\n"
                "1) Use only information from the snippets below.\n"
                "2) Keep findings grounded in those snippets.\n"
                "3) Do not include URLs, citation lists, or metadata labels.\n"
                "4) Keep concise and factual.\n\n"
                "User Query:\n{query}\n\n"
                "Refined Search Queries:\n{refined_queries}\n\n"
                "Snippets:\n{snippets}\n\n"
                "Allowed Sources:\n{allowed_sources}"
            ),
            temperature=0.0,
        )
        self._ack_chain = self._build_chain(
            system_prompt=prompts["ack_system"],
            human_template=(
                "User query: {query}\n\n"
                "Scraped snippet highlights:\n{snippet_highlights}\n\n"
                "Return one plain sentence only."
            ),
            temperature=0.0,
        )
        self._synthesis_chain = self._build_chain(
            system_prompt=prompts["synthesis_system"],
            human_template=(
                "User Question:\n{query}\n\n"
                "Scraped Web Content (use ONLY this for your answer):\n{snippets}\n\n"
                "Source URLs to cite (reference these inline as [1], [2], etc.):\n{sources}\n\n"
                "Produce a well-structured markdown answer with inline citations.\n"
                "CRITICAL: Do NOT include a 'Sources' or 'References' list at the very end of your answer. Just cite inline. The UI handles links automatically."
            ),
            temperature=0.3,
            num_predict=1024,
        )
        self._followup_chain = self._build_chain(
            system_prompt=prompts["followup_system"],
            human_template=(
                "Conversation context (latest first):\n{conversation_context}\n\n"
                "Latest user query:\n{query}\n\n"
                "Return JSON only."
            ),
            temperature=0.0,
        )
        self._spell_chain = self._build_chain(
            system_prompt=prompts["spell_system"],
            human_template="User query to correct: {query}",
            temperature=0.0,
            num_predict=128,
        )
        self._title_chain = self._build_chain(
            system_prompt=prompts["title_system"],
            human_template="User query: {query}",
            temperature=0.3,
            num_predict=32,
        )

    def _build_chain(self, system_prompt: str, human_template: str, temperature: float, num_predict: int = 512):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", human_template),
            ]
        )

        def _invoke(prompt_value: Any) -> str:
            messages = prompt_value.to_messages()
            system_parts: list[str] = []
            user_parts: list[str] = []
            for message in messages:
                role = getattr(message, "type", "")
                content = str(getattr(message, "content", "")).strip()
                if not content:
                    continue
                if role == "system":
                    system_parts.append(content)
                else:
                    user_parts.append(content)

            system = "\n\n".join(system_parts) if system_parts else None
            user_prompt = "\n\n".join(user_parts)
            return self.llm_client.generate(prompt=user_prompt, system=system, temperature=temperature, num_predict=num_predict)

        return prompt | RunnableLambda(_invoke)

    def run_intent(self, query: str) -> str:
        return str(self._intent_chain.invoke({"query": query}))

    def run_spell_check(self, query: str) -> str:
        return str(self._spell_chain.invoke({"query": query})).strip()

    def run_title_generation(self, query: str) -> str:
        return str(self._title_chain.invoke({"query": query})).strip()

    def run_queries(
        self,
        original_query: str,
        intent_type: str,
        time_sensitivity: str,
        entities: str,
    ) -> str:
        return str(
            self._query_chain.invoke(
                {
                    "original_query": original_query,
                    "intent_type": intent_type,
                    "time_sensitivity": time_sensitivity,
                    "entities": entities,
                }
            )
        )

    def run_refinement(
        self,
        query: str,
        refined_queries: str,
        snippets: str,
        allowed_sources: str,
    ) -> str:
        return str(
            self._refine_chain.invoke(
                {
                    "query": query,
                    "refined_queries": refined_queries,
                    "snippets": snippets,
                    "allowed_sources": allowed_sources,
                }
            )
        )

    def run_ack(self, query: str, snippet_highlights: str) -> str:
        return str(self._ack_chain.invoke({"query": query, "snippet_highlights": snippet_highlights}))

    def run_synthesis(self, query: str, snippets: str, sources: str) -> str:
        return str(
            self._synthesis_chain.invoke(
                {
                    "query": query,
                    "snippets": snippets,
                    "sources": sources,
                }
            )
        )

    def run_followup_resolution(self, query: str, conversation_context: str) -> str:
        return str(
            self._followup_chain.invoke(
                {
                    "query": query,
                    "conversation_context": conversation_context,
                }
            )
        )


_CHAIN_CACHE: dict[int, LocalLCELChains] = {}


def get_lcel_chains(llm_client: OllamaClient) -> LocalLCELChains:
    key = id(llm_client)
    chains = _CHAIN_CACHE.get(key)
    if chains is None:
        chains = LocalLCELChains(llm_client=llm_client)
        _CHAIN_CACHE[key] = chains
    return chains
