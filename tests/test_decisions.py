"""The record of judgements already made.

A queue that repeats itself is a queue nobody reads. "Sampanie Moet & Chandon"
carries no colour, grape or sweetness, so it reaches the review queue on every
run and is wine on every run; without somewhere to put that answer, it is asked
forever.
"""

import pytest

from winescraper import decisions as dec
from winescraper.validate import Finding


def log(path, *entries):
    for entry in entries:
        dec.record(path, entry)
    return dec.load(path)


def test_a_decision_settles_its_finding(tmp_path):
    path = tmp_path / "decisions.jsonl"
    saved = log(path, dec.Decision(finding="review", verdict="wine",
                                   retailer="auchan", external_id="454898"))
    findings = [Finding("review", "auchan", "Sampanie Moet & Chandon", "1 signal",
                        retailer_key="auchan", external_id="454898")]
    open_findings, settled = dec.apply(findings, saved)
    assert (open_findings, settled) == ([], 1)


def test_a_decision_does_not_settle_a_different_finding(tmp_path):
    """Deciding a listing is wine says nothing about its price."""
    path = tmp_path / "decisions.jsonl"
    saved = log(path, dec.Decision(finding="review", verdict="wine",
                                   retailer="auchan", external_id="454898"))
    findings = [Finding("price too high", "auchan", "x", "9999 RON/L",
                        retailer_key="auchan", external_id="454898")]
    assert dec.apply(findings, saved) == (findings, 0)


def test_a_wine_finding_is_settled_by_its_key(tmp_path):
    path = tmp_path / "decisions.jsonl"
    saved = log(path, dec.Decision(
        finding="wine spread", verdict="noted", wine_key="tohani-abc",
        note="two unrelated Tohani wines under identical titles"))
    findings = [Finding("wine spread", "metro/freshful", "tohani-abc", "10.8x",
                        wine_key="tohani-abc")]
    assert dec.apply(findings, saved)[1] == 1


def test_exclude_drops_the_listing_from_the_data(tmp_path):
    path = tmp_path / "decisions.jsonl"
    saved = log(path, dec.Decision(finding="not wine", verdict="exclude",
                                   retailer="carrefour", external_id="99",
                                   note="fizzy juice"))
    rows = [{"retailer": "carrefour", "external_id": "99"},
            {"retailer": "carrefour", "external_id": "100"}]
    kept, dropped = dec.filter_rows(rows, saved)
    assert [r["external_id"] for r in kept] == ["100"]
    assert dropped == 1


def test_a_wine_verdict_never_drops_a_listing(tmp_path):
    """Only "exclude" changes the data; the others only quieten the report."""
    path = tmp_path / "decisions.jsonl"
    saved = log(path, dec.Decision(finding="review", verdict="wine",
                                   retailer="auchan", external_id="1"),
                dec.Decision(finding="outlier", verdict="noted",
                             retailer="auchan", external_id="2"))
    rows = [{"retailer": "auchan", "external_id": "1"},
            {"retailer": "auchan", "external_id": "2"}]
    assert dec.filter_rows(rows, saved) == (rows, 0)


def test_a_later_decision_supersedes_an_earlier_one(tmp_path):
    """The file is append-only, so revising a judgement means adding a line."""
    path = tmp_path / "decisions.jsonl"
    saved = log(path,
                dec.Decision(finding="review", verdict="wine", retailer="a",
                             external_id="1"),
                dec.Decision(finding="review", verdict="exclude", retailer="a",
                             external_id="1", note="looked again"))
    assert saved.settled("review", "a", "1").verdict == "exclude"
    assert len(saved.decisions) == 2


def test_an_unknown_verdict_is_refused(tmp_path):
    with pytest.raises(ValueError, match="verdict"):
        dec.record(tmp_path / "d.jsonl",
                   dec.Decision(finding="review", verdict="probably",
                                retailer="a", external_id="1"))


def test_a_decision_needs_something_to_point_at(tmp_path):
    with pytest.raises(ValueError, match="wine_key or retailer"):
        dec.record(tmp_path / "d.jsonl",
                   dec.Decision(finding="review", verdict="wine"))


def test_a_wine_level_finding_refuses_a_listing_target(tmp_path):
    """A spread is a property of the grouping, not of one listing in it."""
    with pytest.raises(ValueError, match="wine_key"):
        dec.record(tmp_path / "d.jsonl",
                   dec.Decision(finding="wine spread", verdict="noted",
                                retailer="metro", external_id="1"))


def test_a_malformed_line_names_itself(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text('{"finding": "review", "verdict": "wine", "retailer": "a",'
                    ' "external_id": "1"}\nnot json at all\n', encoding="utf-8")
    with pytest.raises(ValueError, match="decisions.jsonl:2"):
        dec.load(path)


def test_comments_and_blank_lines_are_allowed(tmp_path):
    """The file is meant to be read and edited by hand."""
    path = tmp_path / "decisions.jsonl"
    path.write_text('# reviewed 2026-08-11\n\n'
                    '{"finding": "review", "verdict": "wine", "retailer": "a",'
                    ' "external_id": "1"}\n', encoding="utf-8")
    assert len(dec.load(path).decisions) == 1


def test_a_missing_file_is_simply_no_decisions(tmp_path):
    assert dec.load(tmp_path / "nothing.jsonl").decisions == []
