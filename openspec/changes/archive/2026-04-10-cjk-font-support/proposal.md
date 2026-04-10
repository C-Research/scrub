## Why

LibreOffice produces box characters (□) when converting Chinese, Japanese, or Korean documents because the Docker image contains no CJK fonts. Documents sourced from Windows environments reference fonts like SimSun, Microsoft YaHei, and MS Gothic that are unavailable on Linux, causing silent glyph fallback to empty boxes on all non-ASCII characters.

## What Changes

- Install five CJK font packages in the Docker image (`fonts-noto-cjk`, `fonts-wqy-microhei`, `fonts-wqy-zenhei`, `fonts-arphic-ukai`, `fonts-arphic-uming`)
- Add a fontconfig substitution file (`docker/99-cjk-subst.conf`) mapping ~15 common Windows CJK font names to the installed equivalents for Simplified Chinese, Traditional Chinese, Japanese, and Korean
- Copy the fontconfig file into `/etc/fonts/conf.d/` in the Dockerfile and rebuild the font cache

## Capabilities

### New Capabilities

- `cjk-rendering`: LibreOffice can render CJK documents to PDF with correct glyphs; fontconfig substitution maps Windows font references to installed Noto/Arphic/WenQuanYi fonts transparently

### Modified Capabilities

- `document-conversion`: No requirement changes — the conversion pipeline is unchanged. Font support is an infrastructure concern resolved below the LibreOffice invocation layer.

## Impact

- **Dockerfile**: new apt packages and two new `RUN` lines (COPY + fc-cache)
- **docker/**: new file `99-cjk-subst.conf`
- **Image size**: `fonts-noto-cjk` is ~400 MB installed; total image growth ~450 MB
- **No Python changes**: `converter.py`, `pipeline.py`, and all other modules are unaffected
- **No runtime changes**: fontconfig substitution is transparent to LibreOffice and to the scrub pipeline
