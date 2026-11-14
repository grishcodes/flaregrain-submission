# Flaregrain

Flaregrain is an evidence dashboard for the NASA Space Apps 2026 challenge "Flame in Freefall". The first app build compares two checked microgravity fire experiments and links each observation to its NASA source.

## Browse the evidence

[Open the evidence browser source](evidence/browser/index.html). To use the page, clone or download this repository and open `flaregrain/evidence/browser/index.html` in your browser. Filter the three published examples by reported measurement, missing value, or disputed value. Each entry links to the original NASA sources.

## Run Compare

From the repository root, run `python3 -I flaregrain/build.py` and open `flaregrain/dist/index.html`. Choose **Airflow cutoff** to compare BASS-II B1 with Saffire I-1. The two source records and their citations are included in the build. The page opens without an account or backend service.

The [airflow shutoff evidence](evidence/airflow-shutoff-source-trace.md) and [Saffire thickness note](evidence/saffire-disputed-thickness.md) explain the scientific limits and link to the original NASA sources. Nora Forghani authored the Compare page and record drawer. This package adapts them for a static build from the two checked records.

## Checks

Python 3.9 or later, standard library only. Run from the repository root:

    python3 -I flaregrain/tests/run.py
    python3 -I flaregrain/build.py --check

`dist/` holds the generated output. It is not committed, and publishing it is a separate deploy step.

The build embeds JavaScript and CSS inline. If source text needs to contain a literal HTML end tag, use the language's string escapes so the HTML parser cannot read it as markup.

## Evidence rules

Every NASA value links to its source, and where two sources disagree both values are shown. Flaregrain's own readings and models are labelled as ours and are never styled as NASA evidence.
