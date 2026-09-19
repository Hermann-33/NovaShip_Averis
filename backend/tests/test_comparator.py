"""Unit tests for the deterministic seven-field comparator + normalization (spec section 27)."""
import pytest

from app.contracts.schemas import (
    NO_MISMATCH_MESSAGE,
    SEVEN_FIELDS,
    ComparisonStatus,
    Evidence,
    ExtractedField,
    FieldResult,
    SevenFieldExtraction,
)
from app.core.comparator import compare_seven_fields
from app.core.normalizer import normalize_container_count, normalize_party, normalize_port, normalize_weight_kg

BASE = {
    "shipper": "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE",
    "consignee": "AL GURG STATIONERY LLC",
    "notify_party": "AL GURG STATIONERY LLC",
    "port_of_loading": "PORT KLANG (WESTPORT), MALAYSIA (MYPKG)",
    "port_of_discharge": "JEBEL ALI, UAE (AEJEA)",
    "container_count": "3 x 40'HC",
    "gross_weight_kg": "22,000 KG",
}


def make(values: dict, conf: float = 0.97) -> SevenFieldExtraction:
    x = SevenFieldExtraction()
    for f in SEVEN_FIELDS:
        v = values.get(f)
        setattr(x, f, ExtractedField(original=v, normalized=None, confidence=(conf if v is not None else 0.0), needs_review=v is None, evidence=Evidence(document_id="doc", snippet=f"{f}: {v}")))
    return x


def test_all_seven_match_gives_exact_message():
    res = compare_seven_fields(make(BASE), make(BASE))
    assert res.mismatch_count == 0
    assert res.comparison_status == ComparisonStatus.PASSED
    assert res.message == NO_MISMATCH_MESSAGE == "No mismatch detected."
    assert all(f.result == FieldResult.MATCH for f in res.fields)
    assert len(res.fields) == 7


def test_required_acceptance_container_3_vs_4_weight_equal():
    bl = dict(BASE, container_count="4 x 40'HC", gross_weight_kg="22000 kg")
    res = compare_seven_fields(make(BASE), make(bl))
    assert res.mismatch_count == 1
    by = {f.field: f for f in res.fields}
    assert by["container_count"].result == FieldResult.MISMATCH
    assert by["container_count"].si_normalized == 3 and by["container_count"].bl_normalized == 4
    assert by["gross_weight_kg"].result == FieldResult.MATCH
    assert by["gross_weight_kg"].si_normalized == 22000 == by["gross_weight_kg"].bl_normalized
    assert res.mismatch_fields == ["container_count"]
    assert "Container Count" in res.message
    assert by["container_count"].attention == "Verify and correct the Draft BL container count."


@pytest.mark.parametrize("field,bad", [
    ("shipper", "ASIA PACIFIC PAPERBOARD TRADING PTE LTD"),
    ("consignee", "UAB NOVAKOPA"),
    ("notify_party", "MOORIM SP CO., LTD"),
    ("port_of_loading", "SINGAPORE (SGSIN)"),
    ("port_of_discharge", "MOMBASA, KENYA (KEMBA)"),
    ("container_count", "2 x 40'HC"),
    ("gross_weight_kg", "23,000 KG"),
])
def test_each_field_mismatches_independently(field, bad):
    bl = dict(BASE, **{field: bad})
    res = compare_seven_fields(make(BASE), make(bl))
    assert res.mismatch_fields == [field]
    assert res.mismatch_count == 1
    for f in res.fields:
        assert (f.result == FieldResult.MISMATCH) == (f.field == field), f"{f.field} wrongly flagged"


def test_two_mismatches_only_those_two():
    bl = dict(BASE, consignee="UAB NOVAKOPA", notify_party="UAB NOVAKOPA")
    res = compare_seven_fields(make(BASE), make(bl))
    assert sorted(res.mismatch_fields) == ["consignee", "notify_party"]
    assert res.mismatch_count == 2


def test_formatting_only_differences_are_not_mismatches():
    bl = dict(BASE, port_of_loading="Port Klang (Westport), Malaysia", gross_weight_kg="22 000 kilograms", container_count="3X40'HC", shipper="April  Fine Paper Trading (Middle East) FZE")
    res = compare_seven_fields(make(BASE), make(bl))
    assert res.message == NO_MISMATCH_MESSAGE


def test_missing_in_si_is_review_not_mismatch():
    si = make(dict(BASE, consignee=None))
    res = compare_seven_fields(si, make(BASE))
    by = {f.field: f for f in res.fields}
    assert by["consignee"].result == FieldResult.MISSING_IN_SI
    assert res.mismatch_count == 0
    assert res.comparison_status == ComparisonStatus.HUMAN_REVIEW
    assert res.review_reason.value == "missing_value"


def test_missing_in_bl_is_review_not_mismatch():
    res = compare_seven_fields(make(BASE), make(dict(BASE, gross_weight_kg="???")))
    by = {f.field: f for f in res.fields}
    assert by["gross_weight_kg"].result == FieldResult.MISSING_IN_BL
    assert res.mismatch_count == 0


def test_low_confidence_routes_to_review():
    si = make(BASE)
    si.shipper.confidence = 0.5
    res = compare_seven_fields(si, make(BASE), confidence_threshold=0.85)
    by = {f.field: f for f in res.fields}
    assert by["shipper"].result == FieldResult.LOW_CONFIDENCE_REVIEW
    assert by["consignee"].result == FieldResult.MATCH


def test_originals_preserved_as_evidence():
    res = compare_seven_fields(make(BASE), make(dict(BASE, container_count="4 x 40'HC")))
    f = next(x for x in res.fields if x.field == "container_count")
    assert f.si_original == "3 x 40'HC" and f.bl_original == "4 x 40'HC"
    assert f.si_evidence.snippet.startswith("container_count")


# ---------------------------------------------------------------- normalization
@pytest.mark.parametrize("raw,expected", [("22,000 KG", 22000), ("22000 kg", 22000), ("22 000 kilograms", 22000), (22000, 22000), ("131,058 KG", 131058), ("22 MT", 22000), ("243588", 243588), ("GLBV3136502", None), ("???", None), ("", None), ("12 lbs", None)])
def test_weight_normalization(raw, expected):
    assert normalize_weight_kg(raw) == expected


@pytest.mark.parametrize("raw,expected", [("3 x 40'HC", 3), ("15X20'GP", 15), ("6 x 40'HC", 6), ("3", 3), (3, 3), ("TBA", None), ("_______", None)])
def test_container_normalization(raw, expected):
    assert normalize_container_count(raw) == expected


def test_port_normalization_case_insensitive_and_code_stripped():
    assert normalize_port("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)") == normalize_port("Port Klang (Westport), Malaysia")
    assert normalize_port("PORT KLANG") == "port klang"


def test_party_normalization_does_not_rewrite_identity():
    assert normalize_party("MOORIM SP CO., LTD") != normalize_party("MOORIM SP CO LTD")  # legally different -> not merged
    assert normalize_party("  AL GURG   STATIONERY LLC ") == normalize_party("al gurg stationery llc")
