"""
Claim-by-claim check of a finished answer, with no extra model call.

Each sentence is a claim. For the passages it cites we check:
- every number in the sentence appears in a cited passage (numbers are where answers go wrong), and
- enough of its content words appear there.

Statuses:
  supported    numbers match and most content words are found
  partial      numbers match but the wording is loosely backed (paraphrase or inference)
  unsupported  a number in the sentence is not in any cited passage, or almost nothing matches
  uncited      a sentence with a figure in it and no citation

Sentences with no citation and no figure (framing, hedges) are not listed.
"""

from __future__ import annotations

import re
from typing import Dict, List

from src.contracts import Evidence

_CITE = re.compile(r"\[(\d{1,3})\]")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[a-z][a-z'-]{2,}")
_STOP = set("""the and for are but not with that this from was were has have had its it's into than then
they them their there these those which while what when where who whom will would shall should could can
may might must also only just very more most such any all each other some about over under upon your our
does did done been being per via out off yet nor both either neither""".split())


def _context_by_number(context: str) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for part in context.split("\n\n---\n\n"):
        m = re.match(r"\s*\[(\d{1,3})\]", part)
        if m:
            out[int(m.group(1))] = part
    return out


def _sentences(text: str) -> List[str]:
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.M)        # list bullets
    text = re.sub(r"[*_#`]", "", text)                           # markdown emphasis
    text = re.sub(r"([.!?])((?:\s*\[\d{1,3}\])+)", r"\2\1", text)   # "...5%. [6]" -> "...5% [6]." (marker after the stop)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 12]


def _numbers(s: str) -> List[str]:
    return [n.replace(",", "") for n in _NUM.findall(s)]


def check_claims(text: str, evidence: List[Evidence], context: str = "") -> List[dict]:
    full = _context_by_number(context)
    sources = {i + 1: (full.get(i + 1) or ev.snippet).lower() for i, ev in enumerate(evidence)}
    claims: List[dict] = []
    for sent in _sentences(text):
        markers = sorted({int(n) for n in _CITE.findall(sent) if int(n) in sources})
        body = re.sub(r"\s+([.,;:!?])", r"\1", _CITE.sub("", sent)).strip()
        body = re.sub(r"^[A-Z][\w ]{0,30}:\s+", "", body)          # "Trigger: ..." list labels are not claims
        nums = [n for n in _numbers(body) if len(n) > 0]
        if not markers:
            if nums:
                claims.append({"text": body, "markers": [], "status": "uncited", "missing": []})
            continue
        cited = " ".join(sources[m] for m in markers)
        cited_nums = set(_numbers(cited))
        missing = [n for n in nums if n not in cited_nums]
        words = {w for w in _WORD.findall(body.lower()) if w not in _STOP}
        found = sum(1 for w in words if w in cited or (len(w) >= 5 and w[:4] in cited))
        overlap = found / len(words) if words else 1.0
        if missing or overlap < 0.25:
            status = "unsupported"
        elif overlap >= 0.55:
            status = "supported"
        else:
            status = "partial"
        claims.append({"text": body, "markers": markers, "status": status, "missing": missing,
                       "overlap": round(overlap, 2)})
    return claims[:60]
