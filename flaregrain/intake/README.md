# Flaregrain intake

How Flaregrain turns NASA's public combustion data into the values the app shows. One command fetches everything from NASA and rebuilds it:

    python3 -I flaregrain/intake/rebuild.py --reports

Run it from the repository root with Python 3.9 or later; it uses only the standard library. The `--reports` step also needs poppler's `pdftotext` and `pdfinfo`. Leave out `--reports` to build only the PSI data. Add `--offline` to rebuild from the copy already fetched, and `--strict` to fail if the counts differ from the recorded build.

Everything is written to `flaregrain/intake/data/`, which is not committed. NASA's tables and report PDFs stay at NASA, and every record links back to its source page.

## Expected result

These are the counts from the team's build of November 13, 2026. A rebuild on November 15 reproduced every data file byte for byte. NASA can update PSI, so a later fetch may differ, and `rebuild.py` shows any difference.

| What | Count |
|---|---|
| PSI combustion investigations | 24 |
| Experimental-table rows | 2,009 |
| Normalized values | 24,573 |
| Table values flagged, each with the reading the build takes | 575 |
| NASA report PDFs | 9 |
| Report passages | 1,595 |

## Steps

| Script | Reads | Writes |
|---|---|---|
| `psi_intake.py` | NASA PSI: the investigations listed under Research Area "combustion science", their records and experimental-table CSVs, each saved with its SHA-256 | `data/manifest.json`, `investigations.json`, `tables/`, `chunks.jsonl`, `graph.json` |
| `psi_observations.py` | the tables | `observations.json` (one normalized value per cell, with its unit and source cell), `runs.json`, `issues.json` (flagged cells and the reading taken), `atlas.json` |
| `build_dashboard_catalog.py` | runs, issues, observations | `dashboard_catalog.json` (the catalog the app searches) |
| `build_dashboard_profiles.py` | runs, investigations, raw records | `dashboard_profiles.json`, table-summary chunks |
| `build_issues_summary.py` | issues | `issues_summary.json` (flags grouped by kind and investigation) |
| `build_models.py` | runs | `models.json` (simple trend fits, labelled as Flaregrain's models, not NASA evidence) |
| `build_corpus.py` | the 9 report PDFs, downloaded by `rebuild.py --reports` | `data/reports/corpus.sqlite`, `chunks_reports.jsonl`. `build_corpus.py verify` re-hashes the PDFs |
| `build_report_passages.py` | the report chunks | `report_passages.json` (passages the app cites, with page numbers) |

Second readings of questioned values are kept in the team's working repository. Without that file, every flagged value uses the intake's own reading.

The hand-checked records and their comparisons in `../data/compare-data.json` were checked against these NASA sources by hand. The rebuild doesn't regenerate them.
