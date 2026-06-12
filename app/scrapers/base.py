import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
        if val > 20000:
            val = val / 10
        return round(val, 2)
    except ValueError:
        return None


def find_prices_in_text(text: str) -> list[float]:
    patterns = [
        r"₹\s*([\d,]+(?:\.\d+)?)",
        r"Rs\.?\s*([\d,]+(?:\.\d+)?)",
        r"INR\s*([\d,]+(?:\.\d+)?)",
        r"([\d,]{4,}(?:\.\d+)?)\s*(?:per\s*gram|/g)",
    ]
    prices = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            p = parse_price(m)
            if p and 3000 < p < 15000:
                prices.append(p)
    return sorted(set(prices))
