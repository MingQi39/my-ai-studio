"""Local food calorie database for Fitness Agent.

This v1 uses a small JSON library (local_foods.json) and does best-effort
normalization + alias matching.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


_BRAND_ALIASES = (
    (("芒果班戟", "山姆"), "山姆芒果班戟"),
    (("芒果班戟", "sam"), "山姆芒果班戟"),
)

@dataclass(frozen=True)
class LocalFoodEntry:
    name: str
    unit: str
    kcal: float
    qty: float
    grams: float | None = None
    aliases: list[str] | None = None


@lru_cache(maxsize=1)
def load_local_foods() -> list[dict[str, Any]]:
    local_path = Path(__file__).resolve().parents[1] / "data" / "local_foods.json"
    with open(local_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("local_foods.json must be a JSON array")
    return data


@lru_cache(maxsize=1)
def build_local_index() -> dict[str, LocalFoodEntry]:
    index: dict[str, LocalFoodEntry] = {}
    for row in load_local_foods():
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        entry = LocalFoodEntry(
            name=name,
            unit=str(row.get("unit") or ""),
            kcal=float(row.get("kcal") or 0),
            qty=float(row.get("qty") or 1),
            grams=float(row["grams"]) if row.get("grams") is not None else None,
            aliases=[str(a) for a in (row.get("aliases") or []) if str(a).strip()],
        )
        # exact name
        index[_normalize_key(name)] = entry
        # aliases
        for a in entry.aliases or []:
            index[_normalize_key(a)] = entry
    return index


def _normalize_key(s: str) -> str:
    return "".join(s.strip().lower().split())


def normalize_food_name(name: str) -> str:
    """Clean common speech-to-text / heuristic parsing artifacts."""
    text = (name or "").strip()
    if not text:
        return text

    text = re.sub(r"[的]+$", "", text)

    compact = _normalize_key(text)
    for tokens, canonical in _BRAND_ALIASES:
        if all(_normalize_key(token) in compact for token in tokens):
            return canonical

    if "山姆" in text and "芒果班戟" in text:
        return "山姆芒果班戟"

    return text


def resolve_local_food(name: str) -> LocalFoodEntry | None:
    index = build_local_index()
    normalized = normalize_food_name(name)
    for candidate in (normalized, name):
        hit = index.get(_normalize_key(candidate))
        if hit is not None:
            return hit

    compact = _normalize_key(normalized)
    for key, entry in index.items():
        if len(key) >= 4 and key in compact:
            return entry
    return None


def is_exact_local_match(name: str) -> bool:
    index = build_local_index()
    normalized = normalize_food_name(name)
    for candidate in (normalized, name):
        if _normalize_key(candidate) in index:
            return True
    return False

