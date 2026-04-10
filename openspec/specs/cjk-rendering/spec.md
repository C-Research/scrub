### Requirement: CJK glyphs render correctly in converted output
The system SHALL produce output PNGs with correct CJK glyphs when processing documents containing Simplified Chinese, Traditional Chinese, Japanese, or Korean characters. Box characters (□) in place of CJK text SHALL NOT appear in output when the source document contains valid CJK content.

#### Scenario: Simplified Chinese document produces readable output
- **WHEN** a DOCX or DOC file containing Simplified Chinese text referencing SimSun or Microsoft YaHei is processed
- **THEN** the output PNG SHALL contain legible Chinese characters, not box characters

#### Scenario: Traditional Chinese document produces readable output
- **WHEN** a DOCX or DOC file containing Traditional Chinese text referencing MingLiU or Microsoft JhengHei is processed
- **THEN** the output PNG SHALL contain legible Traditional Chinese characters, not box characters

#### Scenario: Japanese document produces readable output
- **WHEN** a document containing Japanese text referencing MS Gothic, MS Mincho, or Meiryo is processed
- **THEN** the output PNG SHALL contain legible Japanese characters, not box characters

#### Scenario: Korean document produces readable output
- **WHEN** a document containing Korean text referencing Gulim, Dotum, or Batang is processed
- **THEN** the output PNG SHALL contain legible Korean characters, not box characters

#### Scenario: ASCII and numeric content is unaffected
- **WHEN** a CJK document also contains ASCII text, numerals, or Latin characters
- **THEN** those characters SHALL render correctly alongside CJK content

### Requirement: Windows CJK font names resolve via fontconfig substitution
The system SHALL configure fontconfig aliases so that the following Windows font family names resolve to installed fonts without requiring LibreOffice-specific configuration:

Simplified Chinese: SimSun, NSimSun, SimHei, Microsoft YaHei, KaiTi, KaiTi_GB2312, FangSong, FangSong_GB2312  
Traditional Chinese: MingLiU, PMingLiU, Microsoft JhengHei, DFKai-SB  
Japanese: MS Gothic, MS PGothic, MS Mincho, MS PMincho, Meiryo  
Korean: Gulim, Dotum, Batang, Malgun Gothic

#### Scenario: Document referencing unavailable Windows font still renders
- **WHEN** a document specifies a Windows CJK font name not installed in the image
- **THEN** fontconfig SHALL substitute an installed equivalent and LibreOffice SHALL render the document without falling back to box characters

#### Scenario: fontconfig substitution is transparent to the pipeline
- **WHEN** LibreOffice converts a CJK document to PDF
- **THEN** the substitution SHALL occur silently with no changes to converter.py, pipeline.py, or any other Python module
