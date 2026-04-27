"""Subprocess entry point for fitz (MuPDF) operations.

Run as: python -m scrub._fitz_worker <cmd> <pdf_path> <out_path>

Isolates MuPDF C-library crashes (SIGSEGV/exit 139) from the main process.
Results are pickled to <out_path>: ("ok", result) or ("err", error_type, detail).
"""
import pickle
import sys
from pathlib import Path


def main() -> None:
    cmd, pdf_path_str, out_path_str = sys.argv[1], sys.argv[2], sys.argv[3]
    pdf_path = Path(pdf_path_str)
    out_path = Path(out_path_str)

    from scrub import sanitize
    from scrub.converter import ConversionError, extract_text_from_pdf, rasterize_pdf

    try:
        if cmd == "rasterize":
            pixel_pages = rasterize_pdf(pdf_path)
            result = [sanitize.reencode_png(rgb, w, h) for rgb, w, h in pixel_pages]
        else:
            result = extract_text_from_pdf(pdf_path)
        out_path.write_bytes(pickle.dumps(("ok", result)))
    except ConversionError as e:
        out_path.write_bytes(pickle.dumps(("err", e.error_type, e.detail)))
        sys.exit(1)
    except Exception as e:
        out_path.write_bytes(pickle.dumps(("err", "PyMuPDFError", str(e))))
        sys.exit(1)


if __name__ == "__main__":
    main()
