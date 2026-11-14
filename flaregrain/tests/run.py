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

# The real page, once its source is in this tree: the checks and journeys depend on these hooks.
if (ROOT / "app" / "shell.html").is_file():
    real = build.render(ROOT)
    for hook in ("data-view", 'id="rehearsal-data"', 'id="psi-catalog-data"'):
        expect(f"real page keeps {hook}", hook in real)

status = subprocess.run([sys.executable, "-I", str(ROOT / "build.py"), "--check"], capture_output=True, text=True)
expect("build.py --check runs from the command line", status.returncode == 0)

print(f"{len(failures)} failed" if failures else "all build checks passed")
sys.exit(1 if failures else 0)
