from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional in bare environments
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


@dataclass
class AppSettings:
    name: str
    log_level: str
    max_urls: int
    min_words_per_page: int


@dataclass
class NetworkSettings:
    search_timeout_seconds: int
    httpx_timeout_seconds: int


@dataclass
class ModelSettings:
    local_model: str
    enable_ollama_chains: bool
    enable_llm_synthesis: bool
    enable_llm_result_refinement: bool
    ollama_timeout_seconds: int
    ollama_keep_alive: str
    warmup_ollama_on_start: bool
    unload_ollama_on_exit: bool


@dataclass
class LimitSettings:
    max_pages_for_synthesis: int
    max_words_per_page: int
    max_context_tokens: int


@dataclass
class CacheSettings:
    ttl_seconds: int


@dataclass
class ScraperSettings:
    user_agent: str
    random_delay_min_seconds: int
    random_delay_max_seconds: int


@dataclass
class Settings:
    app: AppSettings
    network: NetworkSettings
    models: ModelSettings
    limits: LimitSettings
    cache: CacheSettings
    scraper: ScraperSettings
    ollama_url: str


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_settings(config_path: str | Path = "config/settings.yaml") -> Settings:
    load_dotenv()
    path = Path(config_path)
    raw = _read_yaml(path)

    app = raw.get("app", {})
    network = raw.get("network", {})
    models = raw.get("models", {})
    limits = raw.get("limits", {})
    cache = raw.get("cache", {})
    scraper = raw.get("scraper", {})

    max_urls = int(os.getenv("MAX_URLS", app.get("max_urls", 3)))
    log_level = os.getenv("LOG_LEVEL", app.get("log_level", "INFO"))

    model_local = os.getenv("LOCAL_MODEL", models.get("local_model", "llama3.1:8b-instruct-q5_K_M"))
    enable_ollama_chains = str(
        os.getenv("ENABLE_OLLAMA_CHAINS", models.get("enable_ollama_chains", "true"))
    ).strip().lower() in {"1", "true", "yes", "on"}
    enable_llm_synthesis = str(
        os.getenv("ENABLE_LLM_SYNTHESIS", models.get("enable_llm_synthesis", "false"))
    ).strip().lower() in {"1", "true", "yes", "on"}
    enable_llm_result_refinement = str(
        os.getenv("ENABLE_LLM_RESULT_REFINEMENT", models.get("enable_llm_result_refinement", "true"))
    ).strip().lower() in {"1", "true", "yes", "on"}
    ollama_timeout_seconds = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", models.get("ollama_timeout_seconds", 20)))
    ollama_keep_alive = str(os.getenv("OLLAMA_KEEP_ALIVE", models.get("ollama_keep_alive", "30m"))).strip()
    warmup_ollama_on_start = str(
        os.getenv("WARMUP_OLLAMA_ON_START", models.get("warmup_ollama_on_start", "true"))
    ).strip().lower() in {"1", "true", "yes", "on"}
    unload_ollama_on_exit = str(
        os.getenv("UNLOAD_OLLAMA_ON_EXIT", models.get("unload_ollama_on_exit", "true"))
    ).strip().lower() in {"1", "true", "yes", "on"}

    return Settings(
        app=AppSettings(
            name=app.get("name", "Cortx"),
            log_level=log_level,
            max_urls=max_urls,
            min_words_per_page=int(app.get("min_words_per_page", 120)),
        ),
        network=NetworkSettings(
            search_timeout_seconds=int(network.get("search_timeout_seconds", 8)),
            httpx_timeout_seconds=int(network.get("httpx_timeout_seconds", 10)),
        ),
        models=ModelSettings(
            local_model=model_local,
            enable_ollama_chains=enable_ollama_chains,
            enable_llm_synthesis=enable_llm_synthesis,
            enable_llm_result_refinement=enable_llm_result_refinement,
            ollama_timeout_seconds=ollama_timeout_seconds,
            ollama_keep_alive=ollama_keep_alive,
            warmup_ollama_on_start=warmup_ollama_on_start,
            unload_ollama_on_exit=unload_ollama_on_exit,
        ),
        limits=LimitSettings(
            max_pages_for_synthesis=int(limits.get("max_pages_for_synthesis", 3)),
            max_words_per_page=int(limits.get("max_words_per_page", 600)),
            max_context_tokens=int(limits.get("max_context_tokens", 4096)),
        ),
        cache=CacheSettings(
            ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", cache.get("ttl_seconds", 86400))),
        ),
        scraper=ScraperSettings(
            user_agent=scraper.get("user_agent", "Mozilla/5.0"),
            random_delay_min_seconds=int(scraper.get("random_delay_min_seconds", 1)),
            random_delay_max_seconds=int(scraper.get("random_delay_max_seconds", 2)),
        ),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
    )
