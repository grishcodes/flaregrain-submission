"""Flaregrain report-PDF lane, built on the Mac Mini on November 13, 2026.

Builds corpus.sqlite (documents, pages, FTS5 over page text) and chunks_reports.jsonl from the NASA PDFs
in data/reports/pdfs, using only the Python standard library and poppler's pdftotext/pdfinfo. The PDFs come
from the NASA URLs below; rebuild.py --reports downloads them, and `verify` re-hashes them.

    python3 -I build_corpus.py build     # (re)build corpus.sqlite and chunks_reports.jsonl
    python3 -I build_corpus.py verify    # re-hash every PDF against the documents table
    python3 -I build_corpus.py search "question" [k]   # BM25 over pages (FTS5)
"""
import hashlib, json, os, re, sqlite3, subprocess, sys

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reports")
PDFS = os.path.join(HERE, "pdfs")
DB = os.path.join(HERE, "corpus.sqlite")
CHUNKS = os.path.join(HERE, "chunks_reports.jsonl")

# file stem -> (NTRS id, URL, PSI, acronym, related PSI, mapping note)
DOCS = [
    ("TM-20210011385", "20210011385", "https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf",
     "PSI-25", "BASS-II", [], "BASS-II summary report"),
    ("20170008805", "20170008805", "https://ntrs.nasa.gov/api/citations/20170008805/downloads/20170008805.pdf",
     "PSI-98", "SAFFIRE-I", ["PSI-99"], "Saffire I and II results slides; mapped to Saffire-I, also covers Saffire-II"),
    ("20150023456", "20150023456", "https://ntrs.nasa.gov/api/citations/20150023456/downloads/20150023456.pdf",
     "PSI-69", "FLEX", [], "FLEX detailed results, NASA/TP-2015-216046"),
    ("20080012612", "20080012612", "https://ntrs.nasa.gov/api/citations/20080012612/downloads/20080012612.pdf",
     "PSI-102", "SAME", [], "SAME AIAA paper"),
    ("20150008962", "20150008962", "https://ntrs.nasa.gov/api/citations/20150008962/downloads/20150008962.pdf",
     "PSI-25", "BASS-II", [], "Zhao et al. 2015, concurrent flame over composite fabric in purely forced flow; listed among BASS-II's PSI publications"),
    ("20210011521", "20210011521", "https://ntrs.nasa.gov/api/citations/20210011521/downloads/ICES%202021-266%200503-2021%20final.pdf",
     "PSI-100", "SAFFIRE-III", ["PSI-98", "PSI-99"], "ICES-2021-266, Saffire IV and V, compared with Saffire I-III; Saffire IV-V are not PSI investigations, so mapped to the nearest, Saffire-III"),
    ("20180005168", "20180005168", "https://ntrs.nasa.gov/api/citations/20180005168/downloads/20180005168.pdf",
     "PSI-98", "SAFFIRE-I", ["PSI-99", "PSI-100"], "Urban et al. Saffire overview slides, Saffire I-III"),
    ("20130000422", "20130000422", "https://ntrs.nasa.gov/api/citations/20130000422/downloads/20130000422.pdf",
     "PSI-101", "SAME-R", [], "SAME-2 particle morphology, ICES 2012; SAME-R's PSI keywords include same-2"),
    ("np-2015-10-034-guide", "NP-2015-10-034-JSC",
     "https://www.nasa.gov/wp-content/uploads/2016/05/np-2015-10-034-jsc_combustion_in_reduced_gravity-iss-mini-book-011116-508.pdf",
     None, "Researcher's Guide: Combustion Science", [], "2015 ISS Researcher's Guide; covers many investigations, no single PSI"),
]


# Titles read from each PDF's first page (several files carry placeholder metadata titles).
TITLES = {
    "TM-20210011385": "Burning and Suppression of Solids–II (BASS–II) Summary Report, NASA/TM-20210011385",
    "20170008805": "Results of Large-Scale Spacecraft Flammability Tests (Ferkul et al., slides)",
    "20150023456": "Detailed Results From the Flame Extinguishment Experiment (FLEX) March 2009 to December 2011, NASA/TP-2015-216046",
    "20080012612": "Spacecraft Fire Detection: Smoke Properties and Transport in Low-Gravity (Urban, Ruff, Brooker)",
    "20150008962": "Concurrent flame growth, spread and extinction over composite fabric samples in low speed purely forced flow in microgravity (Zhao, T'ien, Ferkul, Olson, 2015)",
    "20210011521": "Fire Safety Implications of Preliminary Results from Saffire IV and V Experiments on Large Scale Spacecraft Fires, ICES-2021-266",
    "20180005168": "Saffire: A Novel Approach to Study of Spacecraft Fire Safety Using Un-manned Spacecraft (Urban et al., slides)",
    "20130000422": "Particle Morphology and Size Results from the Smoke Aerosol Measurement Experiment-2, ICES 2012",
    "np-2015-10-034-guide": "A Researcher's Guide to: Combustion Science (NASA ISS, NP-2015-10-034-JSC)",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pdfinfo(path):
    out = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
    info = dict(line.split(":", 1) for line in out.splitlines() if ":" in line)
    return int(info.get("Pages", "0").strip()), info.get("Title", "").strip()


def page_text(path, n, layout=False):
    return subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), "-enc", "UTF-8"] + (["-layout"] if layout else []) +
                          [path, "-"], capture_output=True, text=True).stdout


def first_title(path):
    lines = [l.strip() for l in page_text(path, 1).splitlines() if len(l.strip()) > 12]
    return " ".join(lines[:2])[:200]


def quality(text):
    """'ok'; 'empty' (almost no text: image-only slide, blank or figure-only page); 'table' (number-heavy page,
    re-extracted with -layout so rows stay aligned); or 'garbled' (encoding failures, or mostly neither words nor numbers)."""
    t = text.strip()
    if len(re.sub(r"\s", "", t)) < 40:
        return "empty"
    if "�" in t or re.search(r"\(cid:\d+\)", t):
        return "garbled"
    tokens = re.findall(r"\S+", t)
    if len(tokens) < 20:
        return "ok"
    wordlike = sum(1 for w in tokens if re.fullmatch(r"[A-Za-z][A-Za-z'’\-]*[.,;:)]?", w)) / len(tokens)
    numeric = sum(1 for w in tokens if re.fullmatch(r"[-–+]?[\d.,/:%]+[a-zA-Z]{0,4}", w)) / len(tokens)
    if wordlike < 0.35:
        return "table" if numeric + wordlike >= 0.6 else "garbled"
    return "ok"


def clean(text):
    text = text.replace("\f", " ")
    text = re.sub(r"-\n(?=[a-z])", "", text)          # join words hyphenated across lines
    return re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", text)).strip()


def build():
    if os.path.exists(DB):
        os.remove(DB)
    db = sqlite3.connect(DB)
    db.executescript("""
        create table documents (doc text primary key, ntrs_id text, title text, url text, sha256 text,
                                bytes integer, pages integer, psi text, acronym text, psi_related text, note text);
        create table pages (doc text references documents(doc), page integer, text text, quality text, chars integer,
                            primary key (doc, page));
        create virtual table pages_fts using fts5(text, content='pages', content_rowid='rowid',
                                                  tokenize='porter unicode61');
    """)
    with open(CHUNKS, "w") as out:
        for stem, ntrs, url, psi, acronym, related, note in DOCS:
            path = os.path.join(PDFS, stem + ".pdf")
            n, meta_title = pdfinfo(path)
            title = TITLES.get(stem) or (meta_title if meta_title and not re.search(r"Microsoft Word|PowerPoint|\.pdf$|^GRC_", meta_title) else first_title(path))
            db.execute("insert into documents values (?,?,?,?,?,?,?,?,?,?,?)",
                       (stem, ntrs, title, url, sha256(path), os.path.getsize(path), n, psi, acronym,
                        json.dumps(related), note))
            for p in range(1, n + 1):
                text = clean(page_text(path, p))
                q = quality(text)
                if q == "table":  # keep columns aligned; collapse only runs of 3+ spaces so cells stay apart
                    text = re.sub(r" {3,}", "   ", page_text(path, p, layout=True).replace("\f", " ")).strip()
                db.execute("insert into pages values (?,?,?,?,?)", (stem, p, text, q, len(text)))
                if q == "empty":
                    continue
                out.write(json.dumps({
                    "id": f"{ntrs}:page:{p}", "psi": psi, "acronym": acronym, "field": "report page",
                    "text": text, "source": f"{url}#page={p}", "doi": None, "tier": "NASA report",
                    "quality": q, "psi_related": related}, ensure_ascii=False) + "\n")
    db.execute("insert into pages_fts(pages_fts) values('rebuild')")
    db.commit()
    for row in db.execute("select doc, pages, (select count(*) from pages p where p.doc=d.doc and quality='empty'),"
                          "(select count(*) from pages p where p.doc=d.doc and quality='garbled') from documents d"):
        print(*row)
    db.close()


def verify():
    db = sqlite3.connect(DB)
    bad = 0
    for doc, digest in db.execute("select doc, sha256 from documents"):
        path = os.path.join(PDFS, doc + ".pdf")
        ok = os.path.exists(path) and sha256(path) == digest
        bad += not ok
        print("ok  " if ok else "FAIL", doc)
    print("all PDFs match" if not bad else f"{bad} PDF(s) missing or changed")
    return bad == 0


STOP = set("a an and are as at be by did do does during for from had has have how in is it of on or that the this "
           "to was were what when where which who why with".split())


# Spelling and wording variants seen in these reports ("airflow" vs "air flow" vs "flow"; "cut off" vs "shut off").
# Kept small and general on purpose; findings.md compares results with and without it.
EXPAND = {"airflow": ["air flow", "flow"], "airspeed": ["air speed", "flow velocity"], "cut": ["shut", "stopped"],
          "cloth": ["fabric", "textile"], "soot": ["smoke"], "smoke": ["soot", "particles"]}


def query(question, expand=True):
    terms = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in STOP and len(w) > 2]
    phrases = list(dict.fromkeys(terms + [x for w in terms for x in (EXPAND.get(w, []) if expand else [])]))
    return " OR ".join(f'"{w}"' for w in phrases)


def search(question, k=3, expand=True):
    match = query(question, expand)
    db = sqlite3.connect(DB)
    return db.execute("""select p.doc, p.page, round(bm25(pages_fts),2), d.acronym, substr(replace(p.text, char(10), ' '), 1, 160)
                         from pages_fts join pages p on p.rowid = pages_fts.rowid join documents d on d.doc = p.doc
                         where pages_fts match ? order by bm25(pages_fts) limit ?""", (match, k)).fetchall()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build(); verify()
    elif cmd == "verify":
        sys.exit(0 if verify() else 1)
    elif cmd == "search":
        for row in search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3):
            print(row)
