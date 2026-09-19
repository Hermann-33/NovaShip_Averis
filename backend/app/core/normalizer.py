"""
Safe normalization - reduces FORMATTING-ONLY false mismatches.

Rules (see spec section 6):
  * trim + collapse whitespace, case-fold names/ports for comparison
  * normalise punctuation conservatively
  * "22,000 KG" / "22000 kg" / "22 000 kilograms" / 22000 -> 22000 (int kg)
  * "3 x 40'HC" / "3X20'GP" / "3" -> 3 (int)
  * never rewrites company identity; never invents values
Both original and normalized values are always preserved.
"""
from __future__ import annotations

import re
from typing import Any, Optional

BLANK_TOKENS = {"", "???", "_______", "____", "tba", "tbc", "n/a", "na", "-", "--", "____mt", "nil", "none", "null"}

_WS = re.compile(r"\s+")
_PUNCT_EDGE = re.compile(r"^[\s\.,;:\-_]+|[\s\.,;:\-_]+$")
_MULTI_PUNCT = re.compile(r"[\.,;:]{2,}")


def is_blank(value: Optional[str]) -> bool:
    if value is None:
        return True
    v = value.strip().lower()
    if v in BLANK_TOKENS:
        return True
    # tokens made only of underscores / question marks / dashes
    if re.fullmatch(r"[_\?\-\s]+(mt|kg|kgs)?", v):
        return True
    return False


def normalize_text(value: Optional[str]) -> Optional[str]:
    """Case-fold + whitespace + conservative punctuation normalisation."""
    if value is None or is_blank(value):
        return None
    v = value.strip()
    v = _MULTI_PUNCT.sub(lambda m: m.group(0)[0], v)
    v = _WS.sub(" ", v)
    v = _PUNCT_EDGE.sub("", v)
    v = v.casefold()
    # unify common typographic variants
    v = v.replace("’", "'").replace("“", '"').replace("”", '"')
    v = v.replace(" ,", ",").replace(" .", ".")
    return v or None


def normalize_party(value: Optional[str]) -> Optional[str]:
    """Company / party names: casefold + whitespace only. NO legal-name rewriting."""
    v = normalize_text(value)
    if v is None:
        return None
    # Strip a trailing address block if the value was captured as "NAME | ADDRESS"
    v = v.split(" | ")[0].strip()
    # Tolerate "CO., LTD" vs "CO.,LTD" spacing only
    v = re.sub(r"\s*,\s*", ", ", v)
    v = re.sub(r"\.\s+,", ".,", v)
    return v


_PORT_CODE = re.compile(r"\(\s*[A-Z]{5}\s*\)\s*$")


def normalize_port(value: Optional[str]) -> Optional[str]:
    """Ports: casefold, drop a trailing UN/LOCODE in parentheses, unify separators.
    'PORT KLANG (WESTPORT), MALAYSIA (MYPKG)' -> 'port klang (westport), malaysia'
    """
    if value is None or is_blank(value):
        return None
    v = value.strip()
    v = _PORT_CODE.sub("", v).strip()
    v = normalize_text(v)
    if v is None:
        return None
    v = re.sub(r"\s*,\s*", ", ", v)
    v = re.sub(r"\s*/\s*", "/", v)
    return v


_INT = re.compile(r"\d+")


def normalize_container_count(value: Optional[str | int]) -> Optional[int]:
    """'3 x 40'HC' -> 3 ; '15X20'GP' -> 15 ; 3 -> 3 ; unclear -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if is_blank(s):
        return None
    # take the first integer that precedes an 'x' or stands alone
    m = re.match(r"^\s*(\d{1,4})\s*(?:x|X|×)\s*\S", s)
    if m:
        return int(m.group(1))
    if re.fullmatch(r"\d{1,4}", s):
        return int(s)
    # "3 containers" / "3 x" style
    m = re.match(r"^\s*(\d{1,4})\s*(x|X|×|containers?|ctrs?|units?)?\s*$", s)
    if m:
        return int(m.group(1))
    return None


_WEIGHT_UNIT = re.compile(r"(kgs?|kilograms?|kilo|mt|mts|tons?|tonnes?|lbs?)\b", re.I)


def normalize_weight_kg(value: Optional[str | int | float]) -> Optional[int]:
    """Numeric kilograms. Accepts '22,000 KG', '22000 kg', '22 000 kilograms',
    22000, 22000.0. Converts MT->kg ONLY when the unit is explicit. Returns
    None when uncertain (never silently guesses)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    s = str(value).strip()
    if is_blank(s):
        return None
    unit_m = _WEIGHT_UNIT.search(s)
    unit = unit_m.group(1).lower() if unit_m else "kg"
    num_part = _WEIGHT_UNIT.sub("", s).strip()
    # refuse values that mix letters with digits (e.g. a container number 'GLBV3136502')
    if not re.fullmatch(r"[\d\.\s,]+", num_part):
        return None
    # '22 000' or '22,000' -> '22000'
    num_part = num_part.replace(" ", "").replace(",", "")
    if not num_part or not re.fullmatch(r"\d+(\.\d+)?", num_part):
        return None
    val = float(num_part)
    if unit in ("mt", "mts", "ton", "tons", "tonne", "tonnes"):
        val *= 1000.0
    elif unit in ("lb", "lbs"):
        return None  # refuse silent imperial conversion
    return int(round(val))


def normalize_field(field: str, value: Any) -> Any:
    if field in ("shipper", "consignee", "notify_party"):
        return normalize_party(value if value is None else str(value))
    if field in ("port_of_loading", "port_of_discharge"):
        return normalize_port(value if value is None else str(value))
    if field == "container_count":
        return normalize_container_count(value)
    if field == "gross_weight_kg":
        return normalize_weight_kg(value)
    return normalize_text(value if value is None else str(value))
