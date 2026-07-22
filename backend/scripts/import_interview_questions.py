#!/usr/bin/env python3
"""
Import / sync interview question stems from a Feishu wiki doc into the local RAG bank.

Re-running is a real sync:
- unchanged document hash → skip (unless --force)
- new stems → insert + embed
- removed stems → soft-delete (is_active=False)
- previously soft-deleted stems that reappear → reactivate
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import subprocess
import sys
from pathlib import Path

# Ensure backend/ is on path when invoked as scripts/import_*.py
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db.database import async_session_factory
from app.interview.embedding_service import OllamaEmbeddingService
from app.interview.handbook_filter import extract_handbook_stems_from_markdown
from app.interview.question_bank_ingest import extract_questions_from_markdown
from app.interview.question_bank_sync import sync_question_bank

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_feishu_doc_markdown(doc_url: str) -> str:
    """
    Fetch a Feishu wiki doc via lark-cli.

    Requirements:
    - lark-cli installed
    - user logged in with view permission for the document
    """
    cmd = [
        "lark-cli",
        "docs",
        "+fetch",
        "--doc",
        doc_url,
        "--as",
        "user",
        "--doc-format",
        "markdown",
        "--format",
        "pretty",
    ]
    logger.info("Fetching Feishu doc via: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "lark-cli fetch failed")
    return proc.stdout


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc-url", required=True, help="Feishu wiki doc url")
    parser.add_argument("--title", default=None, help="Optional doc title")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-sync even when document content hash is unchanged",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Import items but do not compute embeddings",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + extract only; do not write DB",
    )
    parser.add_argument(
        "--handbook",
        action="store_true",
        help="Filter tutorial/handbook noise; keep interview-like stems only",
    )
    parser.add_argument(
        "--default-topic",
        default=None,
        help="When --handbook, map General stems to this topic (e.g. RAG)",
    )
    parser.add_argument(
        "--from-file",
        default=None,
        help="Read markdown from a local file instead of lark-cli (password-share docs)",
    )
    args = parser.parse_args()

    if args.from_file:
        markdown = Path(args.from_file).read_text(encoding="utf-8")
        logger.info("Loaded markdown from file: %s (%d chars)", args.from_file, len(markdown))
    else:
        markdown = fetch_feishu_doc_markdown(args.doc_url)
    content_hash = sha256_short(markdown)
    if args.handbook:
        items = extract_handbook_stems_from_markdown(
            markdown,
            default_topic=args.default_topic,
        )
        logger.info(
            "Handbook extract: %d stems (default_topic=%s, doc_hash=%s)",
            len(items),
            args.default_topic,
            content_hash[:12],
        )
    else:
        items = extract_questions_from_markdown(markdown)
        logger.info("Extracted %d raw stems (doc_hash=%s)", len(items), content_hash[:12])

    if args.dry_run:
        topics: dict[str, int] = {}
        for q in items:
            topics[q.topic] = topics.get(q.topic, 0) + 1
        logger.info("[dry-run] topic_counts=%s", topics)
        for q in items[:12]:
            logger.info("[dry-run] %s | %s", q.topic, q.normalized_question[:100])
        return 0

    embedder = None if args.skip_embedding else OllamaEmbeddingService()
    if embedder is not None:
        logger.info("Using Ollama embedding model=%s", embedder.model)

    async with async_session_factory() as db:
        result = await sync_question_bank(
            db,
            source_url=args.doc_url,
            title=args.title,
            document_hash=content_hash,
            items=items,
            embedder=embedder,
            force=bool(args.force),
            skip_embedding=bool(args.skip_embedding),
        )
        await db.commit()

    if result.skipped:
        logger.info("Import skipped (document unchanged). Use --force to re-sync.")
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
