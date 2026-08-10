from __future__ import annotations

from typing import Iterable, List


def assess_data_quality(rows: Iterable[dict]) -> dict:
    """Basic data-quality validation used before running analytics."""
    row_list = list(rows)
    if not row_list:
        return {"quality_score": 0, "warnings": ["INSUFFICIENT_DATA"]}

    warnings: List[str] = []
    missing_values = 0
    invalid_prices = 0
    negative_quantities = 0
    duplicate_count = 0

    seen = set()
    for row in row_list:
        if not row:
            continue
        if row.get("id") is not None:
            marker = str(row.get("id"))
            if marker in seen:
                duplicate_count += 1
            else:
                seen.add(marker)

        for key in ("timestamp", "created_at", "order_time"):
            if key in row and (row.get(key) is None or row.get(key) == ""):
                missing_values += 1

        price = row.get("price")
        if price is not None and float(price) < 0:
            invalid_prices += 1

        qty = row.get("quantity")
        if qty is not None and float(qty) < 0:
            negative_quantities += 1

    if missing_values:
        warnings.append(f"{missing_values} records are missing timestamps or critical identifiers.")
    if invalid_prices:
        warnings.append(f"{invalid_prices} records contain invalid prices.")
    if negative_quantities:
        warnings.append(f"{negative_quantities} records contain negative quantities.")
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate records detected.")

    quality_score = 100
    quality_score -= min(40, missing_values * 2)
    quality_score -= min(25, invalid_prices * 5)
    quality_score -= min(25, negative_quantities * 5)
    quality_score -= min(10, duplicate_count * 2)
    quality_score = max(0, quality_score)
    return {"quality_score": quality_score, "warnings": warnings or ["No critical data-quality issues detected."]}
