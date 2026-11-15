#!/usr/bin/env python3
"""Checks for the Flaregrain build. Run from anywhere: python3 -I tests/run.py"""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixture"
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

failures = []


def expect(name, ok):
    print(("passed " if ok else "FAILED ") + name)
    if not ok:
        failures.append(name)


def refuses(root):
    try:
        build.render(root)
    except SystemExit:
        return True
    return False


page = build.render(FIXTURE)
expect("styles, script and data are filled in", "body{margin:0}" in page and "window.fixtureReady" in page and '"records"' in page)
expect("script files keep file-name order", page.index("first script") < page.index("second script"))
block = re.search(r'<script id="rehearsal-data" type="application/json">(.*?)</script>', page, re.S)
expect("a JSON string cannot close the script element", "\\u003c/script>alert(1)" in page and "</script>alert" not in page)
expect("the embedded JSON has no literal less-than sign", bool(block) and "<" not in block.group(1))
expect("<!--<script> in a JSON value is escaped and the JSON round-trips",
       bool(block) and "<!--" not in block.group(1) and "\\u003c!--\\u003cscript>" in block.group(1)
       and json.loads(block.group(1)) == json.loads((FIXTURE / "data" / "rehearsal-data.json").read_text(encoding="utf-8")))
expect("no placeholder is left", not build.PLACEHOLDER.search(page))

with tempfile.TemporaryDirectory() as tmp:
    broken = Path(tmp) / "broken"
    shutil.copytree(FIXTURE, broken)
    (broken / "data" / "rehearsal-data.json").unlink()
    expect("missing data file stops the build", refuses(broken))
    (broken / "data" / "rehearsal-data.json").write_text("{not json", encoding="utf-8")
    expect("broken JSON stops the build", refuses(broken))
    invalid_values = []
    for constant in ("NaN", "Infinity", "-Infinity"):
        (broken / "data" / "rehearsal-data.json").write_text('{"value": ' + constant + '}', encoding="utf-8")
        invalid_values.append(refuses(broken))
    expect("non-JSON numeric constants stop the build", all(invalid_values))

with tempfile.TemporaryDirectory() as tmp:
    template = Path(tmp) / "template"
    shutil.copytree(FIXTURE, template)
    shell = template / "app" / "shell.html"
    original = shell.read_text(encoding="utf-8")
    shell.write_text(original.replace("{{APP}}", ""), encoding="utf-8")
    expect("missing application placeholder stops the build", refuses(template))
    shell.write_text(original, encoding="utf-8")
    data = template / "data" / "rehearsal-data.json"
    data.write_text(json.dumps({"note": "{{DATA:literal}}"}), encoding="utf-8")
    expect("placeholder text inside JSON stays literal", '"{{DATA:literal}}"' in build.render(template))
    script = template / "app" / "js" / "01-first.js"
    script.write_text('window.example = "</ScRiPt >";', encoding="utf-8")
    expect("unsafe markup in application JavaScript stops the build", refuses(template))
    script.write_text('window.example = "<\\/script>";', encoding="utf-8")
    css = template / "app" / "styles.css"
    css.write_text('main::after {content: "</style>";}', encoding="utf-8")
    expect("unsafe markup in CSS stops the build", refuses(template))

with tempfile.TemporaryDirectory() as tmp:
    build.build(FIXTURE, tmp)
    expect("build writes index.html to the chosen folder", (Path(tmp) / "index.html").is_file())
    expect("static files keep the paths the page uses", (Path(tmp) / "Vendor" / "fixture.txt").is_file())

with tempfile.TemporaryDirectory() as tmp:
    collision = Path(tmp) / "collision"
    shutil.copytree(FIXTURE, collision)
    (collision / "static" / "index.html").write_text("replacement page", encoding="utf-8")
    try:
        build.check(collision)
    except SystemExit as error:
        expect("static files cannot replace the generated page", "static/index.html" in str(error))
    else:
        expect("static files cannot replace the generated page", False)

# Verify the published Compare data survives the real application build.
if (ROOT / "app" / "shell.html").is_file():
    real = build.render(ROOT)
    embedded = re.search(r'<script id="compare-data" type="application/json">(.*?)</script>', real, re.S)
    expect("Compare mounts with its data", 'data-view="compare"' in real and embedded is not None)
    if embedded:
        data = json.loads(embedded.group(1))
        forward = data["pairs"]["B1,S1"]
        reverse = data["pairs"]["S1,B1"]
        expect("both pair orders preserve the selected records",
               [r["id"] for r in forward["records"]] == ["B1", "S1"]
               and [r["id"] for r in reverse["records"]] == ["S1", "B1"])
        expect("NASA sources point to their exact report pages",
               [s["url"].split("#")[-1] for s in forward["supportingSources"]] == ["page=111", "page=16", "page=29"])
        thickness = next(c for c in forward["conditions"][1] if c["label"] == "Sample thickness")
        expect("Saffire thickness preserves two separately sourced readings",
               thickness["tier"] == "dispute" and [r["value"] for r in thickness["readings"]]
               == ["0.37 mm", "0.37 under Sample Thickness (cm)"]
               and len({r["url"] for r in thickness["readings"]}) == 2)
        for pair in (forward, reverse):
            position = pair["ids"].index("S1")
            dimensions = next(c for c in pair["conditions"][position] if c["label"] == "Sample width and length")
            row_index = next(i for i, row in enumerate(pair["rows"]) if row[0] == "Specimen and conditions")
            expect("Saffire dimensions are disputed in the comparison and retain both sources",
                   dimensions["tier"] == "dispute"
                   and [r["value"] for r in dimensions["readings"]]
                   == ["40.6 cm wide × 94 cm long", "94 cm wide × 40.6 cm long"]
                   and len({r["url"] for r in dimensions["readings"]}) == 2
                   and pair["rowFlags"][row_index][position] == "dispute"
                   and "Dimensions disputed" in pair["rows"][row_index][position + 1])

status = subprocess.run([sys.executable, "-I", str(ROOT / "build.py"), "--check"], capture_output=True, text=True)
expect("build.py --check runs from the command line", status.returncode == 0)

# Live Explain in redesign/server.mjs, against a stand-in model proxy on this computer (tests/live_explain.mjs).
node = shutil.which("node") or next((p for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node") if Path(p).is_file()), None)
if node is None:
    expect("live Explain checks run (needs Node.js 22 or later)", False)
else:
    try:
        live = subprocess.run([node, str(ROOT / "tests" / "live_explain.mjs")], capture_output=True, text=True, timeout=120)
        lines = [line for line in live.stdout.splitlines() if line.startswith(("passed ", "FAILED "))]
        for line in lines:
            expect(line.split(" ", 1)[1], line.startswith("passed "))
        expect("live Explain checks complete", live.returncode == 0 and bool(lines))
    except subprocess.TimeoutExpired:
        expect("live Explain checks complete", False)

print(f"{len(failures)} failed" if failures else "all build checks passed")
sys.exit(1 if failures else 0)
