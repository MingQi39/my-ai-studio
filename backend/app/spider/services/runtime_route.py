"""Choose Pipeline vs DeepAgent runtime for spider /agent/run."""

from __future__ import annotations

from typing import Literal

from app.spider.services.target_url import try_resolve_spider_target_url

SpiderRuntime = Literal["pipeline", "deepagent"]


def choose_spider_runtime(message: str, target_url: str | None) -> SpiderRuntime:
    if try_resolve_spider_target_url(message, target_url):
        return "pipeline"
    return "deepagent"
