"""Claim-by-claim check: numbers must appear in the cited passage; wording must mostly match."""

from src.contracts import Evidence
from src.orchestrator.claims import check_claims

CTX = ("[1] annex.pdf p.1\nC.3 Where the Index has moved by more than five per cent (5%), the Contract Price shall be "
       "adjusted by the full movement. The Q3 adjustment equals +18.0%.\n\n---\n\n"
       "[2] report.pdf p.1\nManagement expects margins to recover within two quarters.")
EV = [Evidence(id="ev_1", source_name="annex.pdf", snippet="C.3 Where"), Evidence(id="ev_2", source_name="report.pdf", snippet="")]


def by_status(text):
    return [c["status"] for c in check_claims(text, EV, CTX)]


def test_supported_uses_full_context_not_snippet():
    assert by_status("The Contract Price is adjusted by the full movement when the Index moves more than 5% [1].") == ["supported"]


def test_wrong_number_is_unsupported():
    claims = check_claims("The Q3 adjustment equals 12.5% [1].", EV, CTX)
    assert claims[0]["status"] == "unsupported" and claims[0]["missing"] == ["12.5"]


def test_number_cited_to_wrong_source_is_unsupported():
    assert by_status("The Q3 adjustment equals 18.0% [2].") == ["unsupported"]


def test_uncited_figure_flagged_and_plain_framing_skipped():
    assert by_status("Here is what the documents say.\nPrices rose 18.0% this year.") == ["uncited"]


def test_bullets_and_markdown_are_split_into_claims():
    text = "- **Trigger:** the Index moves by more than 5% [1].\n- **Outlook:** margins recover within two quarters [2]."
    assert by_status(text) == ["supported", "supported"]


def test_marker_after_full_stop_belongs_to_that_sentence():
    text = "The Contract Price is adjusted by the full movement. [1] Margins recover within two quarters. [2]"
    claims = check_claims(text, EV, CTX)
    assert [c["markers"] for c in claims] == [[1], [2]] and all(c["status"] == "supported" for c in claims)
