# Flaregrain data files

## `compare-data.json`

The 13 hand-checked NASA records and the prepared comparisons that the Ask, Compare, Browse and Evidence pages read:

- **Fields:** every value keeps its NASA source link and page, its provenance tier, and its flag or dispute state.
- **Comparisons:** cover the 110 ordered pairs among the 11 runs.
- **Explanations:** 39 pairs carry a saved explanation. Its facts fingerprint matches these records exactly, and every sentence was kept by the sentence checker. It's labelled as Flaregrain's reading, not NASA evidence.

## `moon-mars-air.json`

The Moon & Mars air page's snapshot. For seven habitat atmospheres (ISS cabin, Moon base or rover, two BRE atmospheres, spacesuit, Earth at sea level and an assumed Mars habitat), it gives how many NASA PSI table rows were tested nearby, from which investigations, in which gravity, and what is untested, plus which of the 13 checked records sit nearest.

- **Source:** the full-data demo's PSI catalog (2,009 rows, 24 investigations) and its habitat rules at commit `c219442`. The catalog's SHA-256 is recorded in the file.
- **Near:** a row with both oxygen and a usable pressure within 3 points of oxygen and 1.5 psi, the demo's own rule. Rows with oxygen but no usable pressure are counted apart.
- **Left out:** PSI-10 (ACME/Flame Design), whose PSI record has a blank licence field.
- **Holds:** counts, ranges and record ids only, no table rows. It never interpolates.
- **Rebuild:** `python3 -I flaregrain/intake/build_moon_mars_air.py --catalog dashboard_catalog.json`. `tests/run.py` recounts the checked records from `compare-data.json` and, with `FLAREGRAIN_CATALOG` set to the demo's catalog, recounts the whole snapshot.
- **Copy:** the page reads the identical `redesign/moon-mars-air.json`, because the preview package ships `redesign/` whole and only `compare-data.json` from this folder. The tests check that both copies match.

## `report-passages.json`

Passages from the 9 NASA reports Flaregrain cites, cut into pieces of about 600 characters. The full-data demo searches these passages to answer from the reports, in its "From NASA reports" section. This public site doesn't use the file yet; it's published so the retrieval layer's input can be inspected.

`intake/build_report_passages.py` builds it from `intake/build_corpus.py`, which reads the PDFs from NASA's servers (`intake/rebuild.py --reports`). `docs` lists each report with its title, NASA address and PSI investigation.

**Text is copied only from the five NASA-series documents** (`docs[*].text` is `true`), 1,321 passages:

- BASS-II Summary Report, NASA/TM-20210011385
- FLEX detailed results, NASA/TP-2015-216046
- *A Researcher's Guide to: Combustion Science*, NP-2015-10-034-JSC
- the NASA Saffire slides 20170008805 and 20180005168

**The four conference and journal papers are listed by page only**, with a link to each page at NASA and no copied text (`pages`, 43 entries):

- the SAME paper, 20080012612
- Zhao et al. 2015, 20150008962
- ICES-2021-266, 20210011521
- ICES 2012 SAME-2, 20130000422

| Key | Row |
|---|---|
| `passages` | `[document id, PDF page, text, position on the page]` |
| `pages` | `[document id, PDF page, link to that page]` |
