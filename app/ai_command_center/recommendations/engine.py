from __future__ import annotations

from typing import Any, Dict, List, Optional


def rank_recommendations(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
