"""Zip attachments: the largest PDF inside is used; archives without a PDF yield nothing."""
from __future__ import annotations

import io
import zipfile

from api.ingest.documents import pdf_from_zip

PDF_SMALL = b"%PDF-1.4\n% small cover letter\n"
PDF_BIG = b"%PDF-1.7\n" + b"% annexure with the profile " * 50


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_largest_pdf_wins():
    data = _zip({"cover.pdf": PDF_SMALL, "sub/annexure.PDF": PDF_BIG, "readme.txt": b"hello"})
    assert pdf_from_zip(data) == PDF_BIG


def test_no_pdf_or_fake_pdf_or_not_a_zip():
    assert pdf_from_zip(_zip({"notes.txt": b"x"})) is None
    assert pdf_from_zip(_zip({"fake.pdf": b"not really a pdf"})) is None
    assert pdf_from_zip(b"%PDF-1.4 plain pdf, not a zip") is None


def test_path_traversal_names_are_only_read_in_memory():
    data = _zip({"../../evil.pdf": PDF_BIG})
    assert pdf_from_zip(data) == PDF_BIG  # read by name into memory; nothing is written outside PDF_DIR
