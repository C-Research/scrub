"""Tests for scrub.archive — archive pre-processing pass."""

import io
import stat
import zipfile
from pathlib import Path

from scrub.archive import expand_archives

_DEFAULTS = dict(
    max_file_bytes=100 * 1024 * 1024,
    max_members=1000,
    max_total_bytes=500 * 1024 * 1024,
)


def _make_zip(members: dict[str, bytes]) -> bytes:
    """Return bytes of a ZIP archive containing the given name→content pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _make_zip_with_symlink(symlink_name: str) -> bytes:
    """Return bytes of a ZIP containing a symlink entry."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo(symlink_name)
        info.external_attr = (stat.S_IFLNK | 0o644) << 16
        zf.writestr(info, "target")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 6.1 ZIP extraction: members land in source dir alongside archive
# ---------------------------------------------------------------------------


class TestZipExtraction:
    async def test_member_extracted_next_to_archive(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/archive.zip").write_bytes(
            _make_zip({"report.docx": b"fake docx"})
        )

        count = await expand_archives(tmp_path, **_DEFAULTS)

        assert count == 1
        assert (tmp_path / "docs/report.docx").read_bytes() == b"fake docx"

    async def test_multiple_members_extracted(self, tmp_path):
        (tmp_path / "archive.zip").write_bytes(
            _make_zip({"a.pdf": b"pdf", "b.png": b"png"})
        )

        await expand_archives(tmp_path, **_DEFAULTS)

        assert (tmp_path / "a.pdf").exists()
        assert (tmp_path / "b.png").exists()

    async def test_nested_member_path_preserved(self, tmp_path):
        (tmp_path / "archive.zip").write_bytes(
            _make_zip({"subdir/report.docx": b"content"})
        )

        await expand_archives(tmp_path, **_DEFAULTS)

        assert (tmp_path / "subdir/report.docx").read_bytes() == b"content"

    async def test_returns_count_of_archives_processed(self, tmp_path):
        (tmp_path / "a.zip").write_bytes(_make_zip({"x.txt": b"x"}))
        (tmp_path / "b.zip").write_bytes(_make_zip({"y.txt": b"y"}))

        count = await expand_archives(tmp_path, **_DEFAULTS)

        assert count == 2


# ---------------------------------------------------------------------------
# 6.2 Dedup: member skipped when destination already exists
# ---------------------------------------------------------------------------


class TestDedup:
    async def test_existing_file_not_overwritten(self, tmp_path):
        original = b"original content"
        (tmp_path / "report.docx").write_bytes(original)
        (tmp_path / "archive.zip").write_bytes(
            _make_zip({"report.docx": b"new content from zip"})
        )

        await expand_archives(tmp_path, **_DEFAULTS)

        assert (tmp_path / "report.docx").read_bytes() == original

    async def test_other_members_still_extracted_when_one_skipped(self, tmp_path):
        (tmp_path / "existing.txt").write_bytes(b"existing")
        (tmp_path / "archive.zip").write_bytes(
            _make_zip({"existing.txt": b"new", "new.txt": b"new file"})
        )

        await expand_archives(tmp_path, **_DEFAULTS)

        assert (tmp_path / "existing.txt").read_bytes() == b"existing"
        assert (tmp_path / "new.txt").read_bytes() == b"new file"


# ---------------------------------------------------------------------------
# 6.3 Path traversal rejection
# ---------------------------------------------------------------------------


class TestPathTraversal:
    async def test_dotdot_member_not_extracted(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("../../escape.txt")
            zf.writestr(info, b"escaped")
        (tmp_path / "archive.zip").write_bytes(buf.getvalue())

        await expand_archives(tmp_path, **_DEFAULTS)

        assert not (tmp_path / "escape.txt").exists()
        assert not list(tmp_path.rglob("escape.txt"))

    async def test_safe_members_extracted_despite_unsafe_sibling(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("../../escape.txt")
            zf.writestr(info, b"bad")
            zf.writestr("safe.txt", b"good")
        (tmp_path / "archive.zip").write_bytes(buf.getvalue())

        await expand_archives(tmp_path, **_DEFAULTS)

        assert (tmp_path / "safe.txt").read_bytes() == b"good"


# ---------------------------------------------------------------------------
# 6.4 Symlink skipped
# ---------------------------------------------------------------------------


class TestSymlink:
    async def test_symlink_member_not_extracted(self, tmp_path):
        (tmp_path / "archive.zip").write_bytes(_make_zip_with_symlink("link.txt"))

        await expand_archives(tmp_path, **_DEFAULTS)

        assert not (tmp_path / "link.txt").exists()

    async def test_non_symlink_extracted_alongside_symlink(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            link_info = zipfile.ZipInfo("link.txt")
            link_info.external_attr = (stat.S_IFLNK | 0o644) << 16
            zf.writestr(link_info, "target")
            zf.writestr("real.txt", b"real content")
        (tmp_path / "archive.zip").write_bytes(buf.getvalue())

        await expand_archives(tmp_path, **_DEFAULTS)

        assert not (tmp_path / "link.txt").exists()
        assert (tmp_path / "real.txt").read_bytes() == b"real content"


# ---------------------------------------------------------------------------
# 6.5 Per-member size limit
# ---------------------------------------------------------------------------


class TestMemberSizeLimit:
    async def test_oversized_member_not_extracted(self, tmp_path):
        (tmp_path / "archive.zip").write_bytes(
            _make_zip({"big.bin": b"x" * 200})
        )

        await expand_archives(tmp_path, max_file_bytes=100, max_members=1000, max_total_bytes=500 * 1024 * 1024)

        assert not (tmp_path / "big.bin").exists()

    async def test_small_member_extracted_when_other_is_oversized(self, tmp_path):
        (tmp_path / "archive.zip").write_bytes(
            _make_zip({"big.bin": b"x" * 200, "small.txt": b"ok"})
        )

        await expand_archives(tmp_path, max_file_bytes=100, max_members=1000, max_total_bytes=500 * 1024 * 1024)

        assert not (tmp_path / "big.bin").exists()
        assert (tmp_path / "small.txt").read_bytes() == b"ok"


# ---------------------------------------------------------------------------
# 6.6 Member count limit
# ---------------------------------------------------------------------------


class TestMemberCountLimit:
    async def test_extraction_aborts_at_max_members(self, tmp_path):
        members = {f"file_{i:04d}.txt": f"content {i}".encode() for i in range(10)}
        (tmp_path / "archive.zip").write_bytes(_make_zip(members))

        await expand_archives(tmp_path, max_file_bytes=100 * 1024 * 1024, max_members=5, max_total_bytes=500 * 1024 * 1024)

        extracted = list(tmp_path.glob("file_*.txt"))
        assert len(extracted) == 5


# ---------------------------------------------------------------------------
# 6.7 Total bytes limit
# ---------------------------------------------------------------------------


class TestTotalBytesLimit:
    async def test_extraction_aborts_when_total_exceeded(self, tmp_path):
        # Each file is 50 bytes; limit is 120 bytes → 2 files extracted, 3rd aborts
        members = {f"file_{i}.txt": b"x" * 50 for i in range(5)}
        (tmp_path / "archive.zip").write_bytes(_make_zip(members))

        await expand_archives(tmp_path, max_file_bytes=100 * 1024 * 1024, max_members=1000, max_total_bytes=120)

        extracted = list(tmp_path.glob("file_*.txt"))
        assert len(extracted) == 2


# ---------------------------------------------------------------------------
# 6.8 Office ZIP skipped (not treated as archive)
# ---------------------------------------------------------------------------


class TestOfficeZipSkipped:
    async def test_docx_not_expanded(self, tmp_path):
        (tmp_path / "report.docx").write_bytes(_make_zip({"word/document.xml": b"<xml/>"}))

        count = await expand_archives(tmp_path, **_DEFAULTS)

        assert count == 0
        assert not (tmp_path / "word").exists()

    async def test_xlsx_not_expanded(self, tmp_path):
        (tmp_path / "budget.xlsx").write_bytes(_make_zip({"xl/workbook.xml": b"<xml/>"}))

        count = await expand_archives(tmp_path, **_DEFAULTS)

        assert count == 0

    async def test_pptx_not_expanded(self, tmp_path):
        (tmp_path / "deck.pptx").write_bytes(_make_zip({"ppt/presentation.xml": b"<xml/>"}))

        count = await expand_archives(tmp_path, **_DEFAULTS)

        assert count == 0


# ---------------------------------------------------------------------------
# 6.9 One-level only: inner zip extracted but not expanded
# ---------------------------------------------------------------------------


class TestOneLevelOnly:
    async def test_inner_zip_extracted_but_not_expanded(self, tmp_path):
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, "w") as iz:
            iz.writestr("secret.docx", b"inner content")

        outer_buf = io.BytesIO()
        with zipfile.ZipFile(outer_buf, "w") as oz:
            oz.writestr("inner.zip", inner_buf.getvalue())

        (tmp_path / "outer.zip").write_bytes(outer_buf.getvalue())

        await expand_archives(tmp_path, **_DEFAULTS)

        assert (tmp_path / "inner.zip").exists()
        assert not (tmp_path / "secret.docx").exists()

    async def test_count_reflects_only_outer_archive(self, tmp_path):
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, "w") as iz:
            iz.writestr("file.txt", b"inner")

        (tmp_path / "outer.zip").write_bytes(
            _make_zip({"inner.zip": inner_buf.getvalue()})
        )

        count = await expand_archives(tmp_path, **_DEFAULTS)

        assert count == 1
