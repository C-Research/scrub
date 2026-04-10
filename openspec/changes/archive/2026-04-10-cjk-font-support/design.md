## Context

The scrub Docker image converts office documents to PNGs via LibreOffice → PDF → PyMuPDF → Pillow. The image currently includes only Latin font packages (`fonts-liberation`, `fonts-dejavu-core`, `fonts-noto-core`). When LibreOffice opens a CJK document and references a font it cannot find (e.g. SimSun, MS Gothic), it falls back to the closest available font, which lacks CJK glyphs, producing box characters in the output PDF. The fix is entirely at the OS/font layer — the Python pipeline and LibreOffice invocation are correct.

## Goals / Non-Goals

**Goals:**
- CJK characters in source documents render correctly as glyphs in output PNGs
- Windows font names commonly found in Chinese/Japanese/Korean documents resolve to installed equivalents
- Works for both modern formats (DOCX/XLSX/PPTX — always Unicode) and legacy formats (DOC/XLS/PPT — code page in file header, handled by LibreOffice automatically)
- Covers Simplified Chinese, Traditional Chinese, Japanese, and Korean

**Non-Goals:**
- Matching exact visual style of original Windows fonts (acceptable rendering, not pixel-identical reproduction)
- Supporting rare or vendor-specific CJK fonts beyond the common Windows set
- Changes to the Python pipeline, LibreOffice invocation, or rasterization

## Decisions

### fontconfig substitution over LibreOffice XCU registry

**Chosen:** a fontconfig alias file at `/etc/fonts/conf.d/99-cjk-subst.conf`.

**Alternatives considered:**
- *LibreOffice `registrymodifications.xcu`*: `converter.py` already writes this file for macro security. However, the font substitution XCU schema is complex and poorly documented for headless use; getting property names wrong fails silently. fontconfig is OS-standard, well-documented, and works for any process in the container.
- *`FONTCONFIG_FILE` env var pointing to a custom config*: unnecessarily complex when we can drop a file into `conf.d/`.

### Font packages

| Package | Role |
|---|---|
| `fonts-noto-cjk` | Primary: complete SC/TC/JP/KR glyph coverage, all weights |
| `fonts-wqy-microhei` | Simplified/Traditional fallback; excellent at small sizes |
| `fonts-wqy-zenhei` | Secondary WenQuanYi variant for stylistic coverage |
| `fonts-arphic-ukai` | KaiTi brush style — substitutes KaiTi, KaiTi_GB2312, DFKai-SB |
| `fonts-arphic-uming` | Ming/Song style — substitutes FangSong, MingLiU, PMingLiU |

**Rationale for breadth:** Chinese Windows documents reference a wide variety of font names depending on author locale (Simplified vs Traditional), Office version, and document age. Noto CJK covers glyph rendering; Arphic covers stylistic variants that Noto doesn't map cleanly. WenQuanYi provides additional fallback depth.

### fontconfig alias targets

Aliases resolve to Noto CJK or Arphic based on style class:

| Style class | Target |
|---|---|
| Sans-serif (SC) | Noto Sans CJK SC |
| Serif/Song (SC) | Noto Serif CJK SC |
| Sans-serif (TC) | Noto Sans CJK TC |
| Serif/Ming (TC) | Noto Serif CJK TC |
| KaiTi/brush | AR PL UKai CN / AR PL UKai TW |
| Sans-serif (JP) | Noto Sans CJK JP |
| Serif (JP) | Noto Serif CJK JP |
| Sans-serif (KR) | Noto Sans CJK KR |
| Serif (KR) | Noto Serif CJK KR |

## Risks / Trade-offs

- **Image size +~450 MB** → Accepted. User confirmed size is not a concern. `fonts-noto-cjk` is large but is the most complete CJK font available in Debian packages.
- **Font name mismatches** → fontconfig family names must match exactly what LibreOffice queries. Names are taken from standard Windows font family names; if an unusual document uses a non-standard name string it may not be covered. Mitigation: `fonts-noto-cjk` provides broad Unicode coverage as a catch-all fallback even without an explicit alias.
- **`fc-cache` adds build time** → Minor (~5–10 s). No mitigation needed.

## Migration Plan

1. Add font packages to `apt-get install` in Dockerfile
2. Add `COPY docker/99-cjk-subst.conf /etc/fonts/conf.d/99-cjk-subst.conf` 
3. Add `RUN fc-cache -f`
4. `docker compose build` — image rebuild required; no data migration, no rollback complexity
