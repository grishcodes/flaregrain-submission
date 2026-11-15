#!/usr/bin/env python3
"""Rebuild Flaregrain's NASA data from NASA's own servers, with one command.

  python3 -I flaregrain/intake/rebuild.py              fetch PSI, then build every data file
  python3 -I flaregrain/intake/rebuild.py --reports    also download the 9 NASA report PDFs and cut them into passages
  python3 -I flaregrain/intake/rebuild.py --offline    rebuild from the copy already fetched into data/raw
  python3 -I flaregrain/intake/rebuild.py --strict     fail if the counts differ from the ones recorded below

Everything is written to flaregrain/intake/data/, which is not committed: NASA's tables and reports stay at NASA and are
linked from every record. Python 3.9 or later, standard library only. The --reports step also needs poppler's
pdftotext and pdfinfo.

Steps: PSI intake → normalized observations → catalog → profiles → issues summary → trend models → (report passages).
"""
import json, os, subprocess, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
# Counts from the team's build of November 13, 2026. NASA can update PSI, so a fresh fetch may differ; --strict makes that fail.
EXPECTED = {"investigations": 24, "table rows": 2009, "normalized values": 24573, "report PDFs": 9, "report passages": 1595}
STEPS = ["psi_observations.py", "build_dashboard_catalog.py", "build_dashboard_profiles.py", "build_issues_summary.py", "build_models.py"]


def run(script, *args):
    print("→", script, *args, flush=True)
    result = subprocess.run([sys.executable, "-I", str(HERE / script), *args], cwd=HERE, text=True, capture_output=True)
    for line in (result.stdout + result.stderr).strip().splitlines()[-3:]:
        print("   ", line[:200])
    if result.returncode:
        sys.exit(f"failed: {script}")


def fetch_reports():
    """Download the NASA report PDFs listed in build_corpus.py into data/reports/pdfs (skipping ones already there)."""
    sys.path.insert(0, str(HERE))
    from build_corpus import DOCS  # the list of NASA URLs, kept in one place
    pdfs = DATA / "reports" / "pdfs"
    pdfs.mkdir(parents=True, exist_ok=True)
    for stem, _id, url, *_ in DOCS:
        target = pdfs / (stem + ".pdf")
        if target.exists() and target.stat().st_size:
            continue
        print("→ download", url, flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Flaregrain intake (NASA Space Apps 2026)"})
        with urllib.request.urlopen(request, timeout=120) as response:
            target.write_bytes(response.read())


def counts(reports):
    manifest = json.loads((DATA / "manifest.json").read_text())
    catalog = json.loads((DATA / "dashboard_catalog.json").read_text())["summary"]
    found = {"investigations": manifest["count"], "table rows": catalog["runCount"],
             "normalized values": len(json.loads((DATA / "observations.json").read_text()))}
    if reports:
        passages = json.loads((DATA / "report_passages.json").read_text())
        found["report PDFs"], found["report passages"] = len(passages["docs"]), len(passages["passages"])
    return found


def main():
    reports = "--reports" in sys.argv
    DATA.mkdir(exist_ok=True)
    run("psi_intake.py", *(["--offline"] if "--offline" in sys.argv else []))
    for script in STEPS:
        run(script)
    if reports:
        if "--offline" not in sys.argv:
            fetch_reports()
        run("build_corpus.py", "build")
        run("build_report_passages.py")
    found = counts(reports)
    differ = {k: (v, EXPECTED[k]) for k, v in found.items() if v != EXPECTED[k]}
    for key, value in found.items():
        mark = "" if key not in differ else f"   (recorded {EXPECTED[key]:,})"
        print(f"  {key:<18} {value:>7,}{mark}")
    if differ and "--strict" in sys.argv:
        sys.exit("counts differ from the recorded build")
    print("done · data in", os.path.relpath(DATA))


if __name__ == "__main__":
    main()
