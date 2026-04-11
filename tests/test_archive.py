"""Tests for scrub.archive — archive pre-processing pass."""

import gzip
import io
import stat
import zipfile
from pathlib import Path

from scrub.archive import expand_archives

_LIMITS = dict(
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


def _dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Return (source_dir, extracts_dir) under tmp_path, both created."""
    src = tmp_path / "source"
    ext = tmp_path / "extracts"
    src.mkdir()
    ext.mkdir()
    return src, ext


# ---------------------------------------------------------------------------
# 5.1 ZIP extraction: member lands in extracts/<archive-stem>/, not source
# ---------------------------------------------------------------------------


class TestZipExtraction:
    async def test_member_extracted_into_extracts(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(_make_zip({"report.docx": b"fake docx"}))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 1
        assert (ext / "archive/report.docx").read_bytes() == b"fake docx"
        assert not (src / "report.docx").exists()

    async def test_multiple_members_extracted(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(_make_zip({"a.pdf": b"pdf", "b.png": b"png"}))

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "archive/a.pdf").exists()
        assert (ext / "archive/b.png").exists()

    async def test_nested_member_path_preserved(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(_make_zip({"subdir/report.docx": b"content"}))

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "archive/subdir/report.docx").read_bytes() == b"content"

    async def test_returns_count_of_archives_processed(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "a.zip").write_bytes(_make_zip({"x.txt": b"x"}))
        (src / "b.zip").write_bytes(_make_zip({"y.txt": b"y"}))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 2


# ---------------------------------------------------------------------------
# 5.2 Mirrored structure: archive in subdirectory → matching subdir in extracts
# ---------------------------------------------------------------------------


class TestMirroredStructure:
    async def test_subdir_archive_extracts_to_matching_subdir(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "docs").mkdir()
        (src / "docs/archive.zip").write_bytes(_make_zip({"report.pdf": b"pdf"}))

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "docs/archive/report.pdf").read_bytes() == b"pdf"

    async def test_deeply_nested_archive(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "a/b").mkdir(parents=True)
        (src / "a/b/data.zip").write_bytes(_make_zip({"file.txt": b"hello"}))

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "a/b/data/file.txt").read_bytes() == b"hello"


# ---------------------------------------------------------------------------
# 5.3 .gz single-file extraction: output at extracts/<stem>, no extra subdir
# ---------------------------------------------------------------------------


class TestGzExtraction:
    async def test_gz_extracted_without_archive_stem_subdir(self, tmp_path):
        src, ext = _dirs(tmp_path)
        compressed = gzip.compress(b"pdf content")
        (src / "report.pdf.gz").write_bytes(compressed)

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 1
        assert (ext / "report.pdf").read_bytes() == b"pdf content"
        assert not (ext / "report.pdf.gz").exists()

    async def test_gz_in_subdir_mirrors_structure(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "docs").mkdir()
        compressed = gzip.compress(b"content")
        (src / "docs/file.txt.gz").write_bytes(compressed)

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "docs/file.txt").read_bytes() == b"content"


# ---------------------------------------------------------------------------
# 5.4 Sentinel skip: first member exists in source → archive skipped entirely
# ---------------------------------------------------------------------------


class TestSentinelSkip:
    async def test_archive_skipped_when_first_member_in_source(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "report.docx").write_bytes(b"already here")
        (src / "archive.zip").write_bytes(
            _make_zip({"report.docx": b"from zip", "other.pdf": b"also in zip"})
        )

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 0
        assert not (ext / "archive/report.docx").exists()
        assert not (ext / "archive/other.pdf").exists()

    async def test_gz_skipped_when_stem_exists_in_source(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "report.pdf").write_bytes(b"already here")
        (src / "report.pdf.gz").write_bytes(gzip.compress(b"compressed"))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 0
        assert not (ext / "report.pdf").exists()


# ---------------------------------------------------------------------------
# 5.5 Sentinel pass: first member absent from source → extraction proceeds
# ---------------------------------------------------------------------------


class TestSentinelPass:
    async def test_archive_extracted_when_first_member_absent(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(_make_zip({"report.docx": b"content"}))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 1
        assert (ext / "archive/report.docx").read_bytes() == b"content"

    async def test_unrelated_source_file_does_not_trigger_sentinel(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "other.pdf").write_bytes(b"unrelated")
        (src / "archive.zip").write_bytes(_make_zip({"report.docx": b"content"}))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 1
        assert (ext / "archive/report.docx").exists()


# ---------------------------------------------------------------------------
# 5.6 Extracts dedup: member already in extracts → skipped on re-run
# ---------------------------------------------------------------------------


class TestExtractsDedup:
    async def test_existing_extracts_file_not_overwritten(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(
            _make_zip({"report.docx": b"new content from zip"})
        )
        (ext / "archive").mkdir(parents=True)
        (ext / "archive/report.docx").write_bytes(b"original in extracts")

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "archive/report.docx").read_bytes() == b"original in extracts"

    async def test_other_members_still_extracted_when_one_in_extracts(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(
            _make_zip({"existing.txt": b"new", "new.txt": b"new file"})
        )
        (ext / "archive").mkdir(parents=True)
        (ext / "archive/existing.txt").write_bytes(b"original")

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "archive/existing.txt").read_bytes() == b"original"
        assert (ext / "archive/new.txt").read_bytes() == b"new file"


# ---------------------------------------------------------------------------
# Path traversal rejection
# ---------------------------------------------------------------------------


class TestPathTraversal:
    async def test_dotdot_member_not_extracted(self, tmp_path):
        src, ext = _dirs(tmp_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("../../escape.txt")
            zf.writestr(info, b"escaped")
        (src / "archive.zip").write_bytes(buf.getvalue())

        await expand_archives(src, ext, **_LIMITS)

        assert not list(ext.rglob("escape.txt"))

    async def test_safe_members_extracted_despite_unsafe_sibling(self, tmp_path):
        src, ext = _dirs(tmp_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("../../escape.txt")
            zf.writestr(info, b"bad")
            zf.writestr("safe.txt", b"good")
        (src / "archive.zip").write_bytes(buf.getvalue())

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "archive/safe.txt").read_bytes() == b"good"


# ---------------------------------------------------------------------------
# Symlink skipped
# ---------------------------------------------------------------------------


class TestSymlink:
    async def test_symlink_member_not_extracted(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(_make_zip_with_symlink("link.txt"))

        await expand_archives(src, ext, **_LIMITS)

        assert not (ext / "archive/link.txt").exists()

    async def test_non_symlink_extracted_alongside_symlink(self, tmp_path):
        src, ext = _dirs(tmp_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            link_info = zipfile.ZipInfo("link.txt")
            link_info.external_attr = (stat.S_IFLNK | 0o644) << 16
            zf.writestr(link_info, "target")
            zf.writestr("real.txt", b"real content")
        (src / "archive.zip").write_bytes(buf.getvalue())

        await expand_archives(src, ext, **_LIMITS)

        assert not (ext / "archive/link.txt").exists()
        assert (ext / "archive/real.txt").read_bytes() == b"real content"


# ---------------------------------------------------------------------------
# Per-member size limit
# ---------------------------------------------------------------------------


class TestMemberSizeLimit:
    async def test_oversized_member_not_extracted(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(_make_zip({"big.bin": b"x" * 200}))

        await expand_archives(src, ext, max_file_bytes=100, max_members=1000, max_total_bytes=500 * 1024 * 1024)

        assert not (ext / "archive/big.bin").exists()

    async def test_small_member_extracted_when_other_is_oversized(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "archive.zip").write_bytes(
            _make_zip({"big.bin": b"x" * 200, "small.txt": b"ok"})
        )

        await expand_archives(src, ext, max_file_bytes=100, max_members=1000, max_total_bytes=500 * 1024 * 1024)

        assert not (ext / "archive/big.bin").exists()
        assert (ext / "archive/small.txt").read_bytes() == b"ok"


# ---------------------------------------------------------------------------
# Member count limit
# ---------------------------------------------------------------------------


class TestMemberCountLimit:
    async def test_extraction_aborts_at_max_members(self, tmp_path):
        src, ext = _dirs(tmp_path)
        members = {f"file_{i:04d}.txt": f"content {i}".encode() for i in range(10)}
        (src / "archive.zip").write_bytes(_make_zip(members))

        await expand_archives(src, ext, max_file_bytes=100 * 1024 * 1024, max_members=5, max_total_bytes=500 * 1024 * 1024)

        extracted = list((ext / "archive").glob("file_*.txt"))
        assert len(extracted) == 5


# ---------------------------------------------------------------------------
# Total bytes limit
# ---------------------------------------------------------------------------


class TestTotalBytesLimit:
    async def test_extraction_aborts_when_total_exceeded(self, tmp_path):
        src, ext = _dirs(tmp_path)
        # Each file is 50 bytes; limit is 120 bytes → 2 files extracted, 3rd aborts
        members = {f"file_{i}.txt": b"x" * 50 for i in range(5)}
        (src / "archive.zip").write_bytes(_make_zip(members))

        await expand_archives(src, ext, max_file_bytes=100 * 1024 * 1024, max_members=1000, max_total_bytes=120)

        extracted = list((ext / "archive").glob("file_*.txt"))
        assert len(extracted) == 2


# ---------------------------------------------------------------------------
# Office ZIP skipped (not treated as archive)
# ---------------------------------------------------------------------------


class TestOfficeZipSkipped:
    async def test_docx_not_expanded(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "report.docx").write_bytes(_make_zip({"word/document.xml": b"<xml/>"}))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 0
        assert not (ext / "report").exists()

    async def test_xlsx_not_expanded(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "budget.xlsx").write_bytes(_make_zip({"xl/workbook.xml": b"<xml/>"}))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 0

    async def test_pptx_not_expanded(self, tmp_path):
        src, ext = _dirs(tmp_path)
        (src / "deck.pptx").write_bytes(_make_zip({"ppt/presentation.xml": b"<xml/>"}))

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 0


# ---------------------------------------------------------------------------
# One-level only: inner zip extracted but not expanded
# ---------------------------------------------------------------------------


class TestOneLevelOnly:
    async def test_inner_zip_extracted_but_not_expanded(self, tmp_path):
        src, ext = _dirs(tmp_path)
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, "w") as iz:
            iz.writestr("secret.docx", b"inner content")

        outer_buf = io.BytesIO()
        with zipfile.ZipFile(outer_buf, "w") as oz:
            oz.writestr("inner.zip", inner_buf.getvalue())

        (src / "outer.zip").write_bytes(outer_buf.getvalue())

        await expand_archives(src, ext, **_LIMITS)

        assert (ext / "outer/inner.zip").exists()
        assert not list(ext.rglob("secret.docx"))

    async def test_count_reflects_only_outer_archive(self, tmp_path):
        src, ext = _dirs(tmp_path)
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, "w") as iz:
            iz.writestr("file.txt", b"inner")

        (src / "outer.zip").write_bytes(
            _make_zip({"inner.zip": inner_buf.getvalue()})
        )

        count = await expand_archives(src, ext, **_LIMITS)

        assert count == 1
