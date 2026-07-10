import re
from dataclasses import dataclass


@dataclass
class GoldRate:
    store_name: str
    store_slug: str
    gold_22k: float | None = None
    gold_24k: float | None = None
    gold_18k: float | None = None
    source_url: str = ""
    logo: str = ""
    history: list | None = None  # optional [{date, gold_22k, gold_24k, gold_18k}]


def parse_price(text) -> float | None:
    if text is None or text == "":
        return None
    if isinstance(text, (int, float)):
        val = float(text)
        return round(val, 2) if val >= 100 else None
    cleaned = re.sub(r"[^\d.]", "", str(text).replace(",", ""))
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        if val < 100:
            return None
        # Values above ~40k must be a per-10g quote (per-gram tops out near 22k
        # even for 24K); halving-to-per-gram must not clip a real per-gram rate.
        if val > 40000:
            val = val / 10
        return round(val, 2)
    except ValueError:
        return None
