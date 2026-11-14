#!/usr/bin/env python3
"""Build the Flaregrain page from source.

Layout, relative to this file:
  app/shell.html     markup with {{STYLES}}, {{APP}} and {{DATA:<id>}} placeholders
  app/styles.css     page styles
  app/js/NN-*.js     application script, joined in file-name order into one scope
  data/<id>.json     one JSON file per {{DATA:<id>}} block
  static/            copied as is next to index.html (for example static/Vendor/ becomes Vendor/)

  python3 -I build.py                 write dist/index.html
  python3 -I build.py --out DIR       write DIR/index.html
  python3 -I build.py --check         build into a temporary folder and check the result
"""
import argparse, hashlib, json, re, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = re.compile(r"DATA:([a-z0-9-]+)")
PLACEHOLDER = re.compile(r"\{\{(STYLES|APP|DATA:[^}]*)\}\}")
SCRIPT_MARKUP = re.compile(r"</script(?=[\t\n\f\r />])|<!--", re.IGNORECASE)
STYLE_MARKUP = re.compile(r"</style(?=[\t\n\f\r />])", re.IGNORECASE)


def reject_non_json_constant(value):
    raise ValueError(f"{value} is not valid JSON")


def data_block(root, sid):
    path = root / "data" / f"{sid}.json"
    if not path.is_file():
        raise SystemExit(f"missing data for {sid}: data/{sid}.json")
    text = path.read_text(encoding="utf-8")
    try:
        json.loads(text, parse_constant=reject_non_json_constant)
    except ValueError as error:
        raise SystemExit(f"broken JSON in data/{sid}.json: {error}")
    # Every "<" becomes \u003c. JSON allows "<" only inside strings, where \u003c reads back as the same text, and no
    # string can then close the script element (</script>) or switch the HTML parser into its "double escaped" script
    # state (<!--<script>), which stops the page's own scripts from running.
    return text.replace("<", "\\u003c")


def render(root):
    app = root / "app"
    shell = (app / "shell.html").read_text(encoding="utf-8")
    for required in ("{{STYLES}}", "{{APP}}"):
        if shell.count(required) != 1:
            raise SystemExit(f"app/shell.html must contain exactly one {required} placeholder")
    script = "\n".join(p.read_text(encoding="utf-8") for p in sorted((app / "js").glob("*.js")))
    if not script.strip():
        raise SystemExit("no application script in app/js")
    if SCRIPT_MARKUP.search(script):
        raise SystemExit("application JavaScript contains markup unsafe in an inline script")
    styles = (app / "styles.css").read_text(encoding="utf-8")
    if STYLE_MARKUP.search(styles):
        raise SystemExit("application CSS contains markup unsafe in an inline style")
    content = {"STYLES": styles, "APP": script}

    def fill(match):
        name = match.group(1)
        if name in content:
            return content[name]
        data = DATA.fullmatch(name)
        if not data:
            raise SystemExit(f"invalid data placeholder in app/shell.html: {name}")
        return data_block(root, data.group(1))

    return PLACEHOLDER.sub(fill, shell)


def build(root=HERE, out=None):
    out = Path(out) if out else root / "dist"
    page = render(root)
    static = root / "static"
    if (static / "index.html").exists():
        raise SystemExit("static/index.html conflicts with the generated page")
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    if static.is_dir():
        shutil.copytree(static, out, dirs_exist_ok=True)
    return page


def check(root=HERE):
    with tempfile.TemporaryDirectory() as tmp:
        build(root, tmp)
        page = (Path(tmp) / "index.html").read_text(encoding="utf-8")
        if "<script" not in page or "</html>" not in page.lower():
            raise SystemExit("built page is incomplete")
        return page


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (HERE / "app" / "shell.html").is_file():
        # The app source arrives in a later batch; until then the build checks its own fixture.
        page = check(HERE / "tests" / "fixture") if args.check else sys.exit("no app/shell.html yet")
    else:
        page = check() if args.check else build(HERE, args.out)
    print("built index.html SHA-256", hashlib.sha256(page.encode()).hexdigest()[:16], f"{len(page)/1e6:.2f} MB")
