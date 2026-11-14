# Flaregrain

Flaregrain is an evidence dashboard for the NASA Space Apps 2026 challenge "Flame in Freefall". When the dashboard source arrives, a researcher can ask a combustion question or browse NASA microgravity fire studies, compare two runs, and open the exact NASA report page behind each value.

## Current phase: build tool and fixture checks

This batch holds only the build tool and its tests. **There is no dashboard here yet.** The checks below run against a small synthetic fixture in `tests/fixture/`, and they show that the build tool works, not that the app works. Without `app/shell.html`, `build.py --check` builds that fixture, and `build.py` on its own stops with "no app/shell.html yet".

## Checks

Python 3.9 or later, standard library only, with nothing to install. Run from the repository root:

    python3 -I flaregrain/tests/run.py          # seventeen build checks on the fixture
    python3 -I flaregrain/build.py --check      # builds into a temporary folder; no tracked file changes

## What the real dashboard build will need

Later batches add these under `flaregrain/`, and `build.py` then builds them instead of the fixture:

- `app/shell.html`: the page markup, with `{{STYLES}}`, `{{APP}}` and `{{DATA:<id>}}` placeholders. The real page must keep the `data-view`, `rehearsal-data` and `psi-catalog-data` hooks that `tests/run.py` checks.
- `app/styles.css` and `app/js/NN-*.js`: the styles and the application script. The script files are joined in file-name order into one scope.
- `data/<id>.json`: one JSON file per data block. It holds the team's checked NASA records and the tables generated from NASA's Physical Sciences Informatics combustion investigations, each value with its source.
- `static/`: files copied as they are next to the page. This includes the third-party browser libraries and fonts in `static/Vendor/`, each with its own licence file.

`dist/` holds the generated output. It is not committed, and publishing it is a separate deploy step.

The build embeds JavaScript and CSS inline. If source text needs to contain a literal HTML end tag, use the language's string escapes so the HTML parser cannot read it as markup.

## Evidence rules

Every NASA value links to its source, and where two sources disagree both values are shown. Flaregrain's own readings and models are labelled as ours and are never styled as NASA evidence.
