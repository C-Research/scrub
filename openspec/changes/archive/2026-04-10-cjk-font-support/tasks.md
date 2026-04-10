## 1. fontconfig substitution file

- [x] 1.1 Create `docker/99-cjk-subst.conf` with fontconfig `<alias>` entries mapping SimSun, NSimSun → Noto Serif CJK SC
- [x] 1.2 Add aliases for SimHei, Microsoft YaHei → Noto Sans CJK SC
- [x] 1.3 Add aliases for KaiTi, KaiTi_GB2312 → AR PL UKai CN
- [x] 1.4 Add aliases for FangSong, FangSong_GB2312 → AR PL UMing CN
- [x] 1.5 Add aliases for MingLiU, PMingLiU → Noto Serif CJK TC
- [x] 1.6 Add aliases for Microsoft JhengHei → Noto Sans CJK TC
- [x] 1.7 Add aliases for DFKai-SB → AR PL UKai TW
- [x] 1.8 Add aliases for MS Gothic, MS PGothic, Meiryo → Noto Sans CJK JP
- [x] 1.9 Add aliases for MS Mincho, MS PMincho → Noto Serif CJK JP
- [x] 1.10 Add aliases for Gulim, Dotum, Malgun Gothic → Noto Sans CJK KR
- [x] 1.11 Add alias for Batang → Noto Serif CJK KR

## 2. Dockerfile

- [x] 2.1 Add `fonts-noto-cjk` to the `apt-get install` block
- [x] 2.2 Add `fonts-wqy-microhei` to the `apt-get install` block
- [x] 2.3 Add `fonts-wqy-zenhei` to the `apt-get install` block
- [x] 2.4 Add `fonts-arphic-ukai` to the `apt-get install` block
- [x] 2.5 Add `fonts-arphic-uming` to the `apt-get install` block
- [x] 2.6 Add `COPY docker/99-cjk-subst.conf /etc/fonts/conf.d/99-cjk-subst.conf` after the apt-get block
- [x] 2.7 Add `RUN fc-cache -f` after the COPY line

## 3. Verification

- [ ] 3.1 Run `docker compose build` and confirm build succeeds
- [ ] 3.2 Place a Chinese DOCX in `data/source/` and run `docker compose up`; confirm output PNG contains legible CJK characters
- [ ] 3.3 Verify no box characters (□) appear in the output for CJK content
