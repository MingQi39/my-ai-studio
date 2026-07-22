#!/usr/bin/env python3
"""Import interview stems from bcefghj/ai-agent-interview-guide (MIT)."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db.database import async_session_factory
from app.interview.embedding_service import OllamaEmbeddingService
from app.interview.github_guide_ingest import extract_from_guide_repo
from app.interview.question_bank_sync import sync_question_bank

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_REPO = "https://github.com/bcefghj/ai-agent-interview-guide.git"
DEFAULT_SOURCE_URL = "https://github.com/bcefghj/ai-agent-interview-guide"


def sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clone_or_use(repo_dir: Path | None, repo_url: str) -> Path:
    if repo_dir is not None:
        path = Path(repo_dir)
        if not path.exists():
            raise FileNotFoundError(path)
        return path
    tmp = Path(tempfile.mkdtemp(prefix="ai-agent-interview-guide-"))
    logger.info("Cloning %s → %s", repo_url, tmp)
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(tmp)],
        check=True,
        capture_output=True,
        text=True,
    )
    return tmp


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", default=None, help="Local clone path (skip git clone)")
    parser.add_argument("--repo-url", default=DEFAULT_REPO)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--title", default="ai-agent-interview-guide")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-embedding", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = clone_or_use(Path(args.repo_dir) if args.repo_dir else None, args.repo_url)
    items = extract_from_guide_repo(root)
    # Hash from sorted stems so re-order doesn't force re-embed noise
    payload = "\n".join(sorted(i.normalized_question for i in items))
    content_hash = sha256_short(payload)
    logger.info("Extracted %d unique stems (hash=%s)", len(items), content_hash[:12])

    topics: dict[str, int] = {}
    for q in items:
        topics[q.topic] = topics.get(q.topic, 0) + 1
    logger.info("topic_counts=%s", dict(sorted(topics.items(), key=lambda x: -x[1])))

    if args.dry_run:
        for q in items[:15]:
            logger.info("[dry-run] %s | %s", q.topic, q.normalized_question[:100])
        return 0

    embedder = None if args.skip_embedding else OllamaEmbeddingService()
    async with async_session_factory() as db:
        result = await sync_question_bank(
            db,
            source_url=args.source_url,
            title=args.title,
            document_hash=content_hash,
            items=items,
            embedder=embedder,
            force=bool(args.force),
            skip_embedding=bool(args.skip_embedding),
        )
        await db.commit()

    if result.skipped:
        logger.info("Import skipped (unchanged). Use --force to re-sync.")
    else:
        logger.info(
            "Import finished. added=%s reactivated=%s deactivated=%s unchanged=%s embedded=%s",
            result.added,
            result.reactivated,
            result.deactivated,
            result.unchanged,
            result.embedded,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
