"""Page images + located highlight rectangles for cited passages in PDFs."""

import pytest


def _pdf(lines):
    """A minimal valid one-page PDF with Helvetica text lines (no extra libraries)."""
    stream = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode("latin-1")


@pytest.mark.asyncio
async def test_page_image_and_locate(client, auth_headers):
    pdf = _pdf(["ANNEX C PRICE ADJUSTMENT",
                "C.3 Where the Index has moved by more than five per cent the price is adjusted.",
                "C.4 Adjustments shall not be capped."])
    r = await client.post("/ingest", headers=auth_headers, files={"file": ("annex.pdf", pdf, "application/pdf")})
    assert r.status_code == 202, r.text
    from src.ingestion.worker import wait_for_inline_jobs
    await wait_for_inline_jobs()
    doc = r.json()["document_id"]

    img = await client.get(f"/documents/{doc}/pages/1.png", headers=auth_headers)
    assert img.status_code == 200 and img.content[:8] == b"\x89PNG\r\n\x1a\n"

    loc = (await client.post(f"/documents/{doc}/pages/1/locate", headers=auth_headers,
                             json={"text": "C.4 Adjustments shall not be capped. Some text that is not on the page at all."})).json()
    assert loc["found"] and len(loc["rects"]) >= 1
    x0, y0, x1, y1 = loc["rects"][0]
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1 and y0 > 0.05      # below the heading, top-left origin

    assert (await client.get(f"/documents/{doc}/pages/9.png", headers=auth_headers)).status_code == 404
    r = await client.post("/auth/register", json={"username": "pagepeek", "email": "pagepeek@example.com", "password": "secret12"})
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}
    await client.put(f"/documents/{doc}/sharing", headers=auth_headers, json={"visibility": "private"})
    assert (await client.get(f"/documents/{doc}/pages/1.png", headers=other)).status_code in (403, 404)
