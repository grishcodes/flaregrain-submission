#!/usr/bin/env python3
"""PSI combustion intake for Flaregrain.

Fetches every investigation PSI lists under Research Area "combustion science",
saves each raw record and experimental-table CSV with its SHA-256, and writes:

  data/manifest.json        what was fetched, from where, when, with hashes
  data/investigations.json  one normalized record per investigation
  data/tables/PSI-##.json   parsed experimental-table rows, raw cell text kept
  data/chunks.jsonl         text chunks for retrieval, each with its source locator
  data/graph.json           investigations as nodes, weighted explainable edges

Stdlib only. Rerun:  python3 -I psi_intake.py            (fetch + build)
                     python3 -I psi_intake.py --offline  (rebuild from data/raw)
"""
import csv, hashlib, io, json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://psi.nasa.gov/geode-py/ws"
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RAW = DATA / "raw"
UA = {"User-Agent": "flaregrain-intake/0.1 (research prototype)"}

# Links the challenge text states between investigations (Details tab, read Nov 13).
HARDWARE_GROUPS = {
    "ACME in the Combustion Integrated Rack": ["PSI-10", "PSI-20", "PSI-21", "PSI-22", "PSI-23", "PSI-159"],
    "MDCA droplet hardware": ["PSI-68", "PSI-69", "PSI-39"],
    "MSG with the SPICE flow duct": ["PSI-25", "PSI-26", "PSI-107", "PSI-106"],
    "Saffire on Cygnus": ["PSI-98", "PSI-99", "PSI-100"],
    "SAME P-Trak smoke instrument": ["PSI-102", "PSI-101", "PSI-47"],
}
# This project's reading of NASA's three fire-safety areas, plus fundamentals.
FIRE_SAFETY = {
    "PSI-25": ["prevention", "suppression"], "PSI-26": ["prevention", "suppression"],
    "PSI-98": ["prevention"], "PSI-99": ["prevention"], "PSI-100": ["prevention"],
    "PSI-20": ["prevention"], "PSI-62": ["prevention"], "PSI-159": ["prevention"],
    "PSI-102": ["detection"], "PSI-101": ["detection"], "PSI-47": ["detection"],
    "PSI-115": ["detection"], "PSI-107": ["detection", "prevention"],
    "PSI-69": ["suppression"], "PSI-68": ["suppression"], "PSI-39": ["suppression"],
    "PSI-117": ["suppression"], "PSI-142": ["suppression"], "PSI-23": ["suppression"],
}
WEIGHTS = {"psi_related": 1.0, "shared_hardware": 0.6, "shared_publication": 0.5,
           "shared_fuel": 0.5, "shared_keywords": 0.4, "shared_fire_safety_area": 0.3}


def get(url, binary=False, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                b = r.read()
                return b if binary else b.decode("utf-8", "replace")
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    q = urllib.parse.urlencode({"ffield": "Research Area", "fvalue": "combustion science", "size": 200})
    search = json.loads(get(f"{BASE}/repo/search?{q}"))
    (RAW / "search.json").write_text(json.dumps(search, indent=1))
    hits = search["hits"]["hits"]
    ids = sorted({h["_source"].get("Accession") or h["_id"] for h in hits}, key=lambda s: int(s.split("-")[1]))
    manifest = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "search_url": f"{BASE}/repo/search?{q}", "count": len(ids), "files": []}
    for pid in ids:
        d = RAW / pid
        d.mkdir(exist_ok=True)
        rb = get(f"{BASE}/repo/investigations/{pid}", binary=True)
        (d / "record.json").write_bytes(rb)
        rec = json.loads(rb)
        manifest["files"].append({"psi": pid, "kind": "record", "path": f"raw/{pid}/record.json",
                                  "url": f"{BASE}/repo/investigations/{pid}", "version": rec.get("version"),
                                  "sha256": sha(rb), "bytes": len(rb)})
        for t in rec.get("experimentalTable") or []:
            name = t["file_name"]
            if not name.lower().endswith(".csv"):
                continue
            q2 = urllib.parse.urlencode({"file": name, "version": rec.get("version"), "redirect": "false"})
            signed = get(f"{BASE}/studies/{pid}/download?{q2}").strip()
            try:
                signed = json.loads(signed)
                if isinstance(signed, dict):
                    signed = signed.get("url") or next(iter(signed.values()))
            except ValueError:
                pass
            b = get(signed.strip('"'), binary=True)
            (d / name).write_bytes(b)
            manifest["files"].append({"psi": pid, "kind": "experimental_table", "path": f"raw/{pid}/{name}",
                                      "psi_page": f"https://psi.nasa.gov/physci/repo/data/investigations/{pid}",
                                      "file_name": name, "version": rec.get("version"),
                                      "sha256": sha(b), "bytes": len(b)})
        print(pid, rec.get("investigationAcronym"), len(rec.get("experimentalTable") or []), "table(s)")
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


NUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
HDR_UNIT = re.compile(r"\(([^)]*)\)\s*$")


def parse_cell(s):
    """Keep the raw text; add numbers only when the cell is unambiguous."""
    s = (s or "").strip()
    out = {"raw": s}
    if not s:
        return out
    nums = NUM.findall(s.replace(",", ""))
    rest = NUM.sub("", s.replace(",", "")).strip(" ~;/-")
    if len(nums) == 1:
        out["value"] = float(nums[0])
        if rest and len(rest) <= 12:
            out["unit_in_cell"] = rest
        if "~" in s:
            out["approx"] = True
    elif len(nums) > 1:
        out["values"] = [float(n) for n in nums]
        if re.search(r"\d\s*-\s*\d", s) and len(nums) == 2:
            out["range"] = [float(nums[0]), float(nums[1])]
    return out


def parse_table(path):
    text = path.read_bytes().decode("utf-8-sig", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return {"columns": [], "rows": []}
    header = [h.strip() for h in rows[0]]
    cols = []
    for i, h in enumerate(header):
        m = HDR_UNIT.search(h)
        cols.append({"index": i, "name": h or f"column {i+1}", "unit_in_header": m.group(1) if m else None})
    body = []
    for n, r in enumerate(rows[1:], start=2):
        cells = {cols[i]["name"]: parse_cell(r[i] if i < len(r) else "") for i in range(len(cols))}
        body.append({"csv_line": n, "cells": cells})
    return {"columns": cols, "rows": body}


FUEL_COL = re.compile(r"fuel|material|sample \(fuel", re.I)
# Canonical fuel names for linking. Raw strings stay in investigations.json.
FUEL_ALIASES = [
    ("pmma", r"pmma|acrylic|black rod"), ("sibal cotton-fiberglass", r"sibal|cotton"),
    ("silicone", r"silicone"), ("kapton", r"kapton"), ("teflon", r"teflon"), ("nomex", r"nomex"),
    ("methane", r"\bch4\b|methane"), ("ethane", r"\bc2h6\b|\bethane"), ("ethylene", r"\bc2h4\b|ethylene"),
    ("propane", r"\bc3h8\b|propane"), ("propylene", r"propylene"), ("butane", r"butane"),
    ("methanol", r"methanol"), ("ethanol", r"(?<![a-z])ethanol"), ("heptane", r"heptane"), ("isooctane", r"isooctane"), ("octane", r"(?<![a-z])octane"),
    ("decane", r"(?<![a-z])decane"), ("dodecane", r"c12h26|dodecane"), ("dibutyl phthalate", r"dibutyl"),
    ("lampwick", r"lampwick"), ("dust", r"\bdust\b"),
]


def canon_fuels(raw):
    out = set()
    for v in raw:
        for name, pat in FUEL_ALIASES:
            if re.search(pat, v):
                out.add(name)
    return out


def fuels_of(table):
    out = set()
    for c in table["columns"]:
        if FUEL_COL.search(c["name"]) and not re.search(r"rate|bottle|mfc|conc|#|number", c["name"], re.I):
            for r in table["rows"]:
                v = r["cells"][c["name"]]["raw"].strip().lower()
                if v and not NUM.fullmatch(v):
                    out.add(re.sub(r"\s+", " ", v))
    return out


def text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join(text(x) for x in v if x)
    if isinstance(v, dict):
        return text(v.get("annotationValue") or v.get("name") or "")
    return str(v).strip()


def build():
    manifest = json.loads((DATA / "manifest.json").read_text())
    search = json.loads((RAW / "search.json").read_text())
    kw = {}
    for h in search["hits"]["hits"]:
        s = h["_source"]
        k = s.get("Keywords") or []
        kw[s.get("Accession") or h["_id"]] = [x.strip().lower() for x in (k if isinstance(k, list) else str(k).split(",")) if x.strip()]
    (DATA / "tables").mkdir(exist_ok=True)
    invs, chunks, fuels, pubs = [], [], {}, {}
    for f in [f for f in manifest["files"] if f["kind"] == "record"]:
        pid = f["psi"]
        rec = json.loads((DATA / f["path"]).read_text())
        page = f"https://psi.nasa.gov/physci/repo/data/investigations/{pid}"
        related = [x.strip() for x in re.split(r"[,; ]+", text(rec.get("related_glds"))) if x.strip().startswith("PSI-")]
        tables, fz = [], set()
        for tf in [t for t in manifest["files"] if t["psi"] == pid and t["kind"] == "experimental_table"]:
            t = parse_table(DATA / tf["path"])
            t.update({"file_name": tf["file_name"], "sha256": tf["sha256"], "psi_page": page, "version": tf["version"]})
            tables.append(t)
            fz |= fuels_of(t)
        (DATA / "tables" / f"{pid}.json").write_text(json.dumps(tables, indent=1))
        fuels[pid] = canon_fuels(fz)
        pubs[pid] = {p.get("doi").lower() for p in rec.get("publications") or [] if p.get("doi")}
        inv = {
            "psi": pid, "acronym": rec.get("investigationAcronym") or short_title(rec.get("title"), pid), "acronym_from_title": not rec.get("investigationAcronym"), "title": rec.get("title"),
            "doi": rec.get("doi"), "license": rec.get("licenseIdentifier") or None, "version": rec.get("version"),
            "modified": rec.get("modifiedDate"), "platform": rec.get("flightProgram"),
            "hardware": rec.get("experimentHardware"), "sub_area": rec.get("subResearchArea"),
            "project_type": rec.get("projectType"),
            "dates": [rec.get("investigationStartDate") or None, rec.get("investigationEndDate") or None],
            "psi_related": related, "fire_safety_areas": FIRE_SAFETY.get(pid, ["fundamentals"]),
            "keywords": kw.get(pid, []), "fuels_in_tables": sorted(fz), "fuels": sorted(fuels[pid]),
            "tables": [{"file_name": t["file_name"], "rows": len(t["rows"]), "columns": [c["name"] for c in t["columns"]]} for t in tables],
            "publications": [{"title": p.get("title"), "authors": p.get("authorList"), "doi": p.get("doi") or None}
                             for p in rec.get("publications") or []],
            "total_file_bytes": rec.get("totalFileSize"), "psi_page": page,
            "tier": "catalogued", "tier_note": "From the PSI record and table as published; not independently checked.",
        }
        invs.append(inv)
        for field in ["objective", "hypothesis", "approach", "researchImpacts", "description"]:
            body = text(rec.get(field))
            for i, part in enumerate(split_chunks(body)):
                chunks.append({"id": f"{pid}:{field}:{i}", "psi": pid, "acronym": inv["acronym"], "field": field,
                               "text": part, "source": page, "doi": rec.get("doi"), "tier": "catalogued"})
        for j, p in enumerate(inv["publications"]):
            chunks.append({"id": f"{pid}:publication:{j}", "psi": pid, "acronym": inv["acronym"], "field": "publication",
                           "text": f"{p['title']} — {p['authors']}", "source": f"https://doi.org/{p['doi']}" if p["doi"] else page,
                           "doi": p["doi"], "tier": "catalogued"})
    (DATA / "investigations.json").write_text(json.dumps(invs, indent=1))
    with open(DATA / "chunks.jsonl", "w") as fh:
        for c in chunks:
            fh.write(json.dumps(c) + "\n")
    graph = build_graph(invs, fuels, pubs)
    (DATA / "graph.json").write_text(json.dumps(graph, indent=1))
    rows = sum(t["rows"] for i in invs for t in i["tables"])
    print(f"{len(invs)} investigations, {rows} table rows, {len(chunks)} chunks, {len(graph['edges'])} edges")


def short_title(title, pid):
    """PSI analysis records have no acronym; use the first words of the title, marked as derived."""
    words = re.sub(r"[^\w\s-]", "", title or "").split()
    return (" ".join(words[:5]) or pid) + f" ({pid})"


def split_chunks(s, size=900):
    s = re.sub(r"\s+", " ", s or "").strip()
    if not s:
        return []
    sents, out, cur = re.split(r"(?<=[.!?])\s+", s), [], ""
    for x in sents:
        if cur and len(cur) + len(x) > size:
            out.append(cur)
            cur = x
        else:
            cur = f"{cur} {x}".strip()
    return out + ([cur] if cur else [])


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def build_graph(invs, fuels, pubs):
    ids = [i["psi"] for i in invs]
    by = {i["psi"]: i for i in invs}
    edges = []
    for a_i, a in enumerate(ids):
        for b in ids[a_i + 1:]:
            parts = []
            if b in by[a]["psi_related"] or a in by[b]["psi_related"]:
                parts.append({"kind": "psi_related", "weight": WEIGHTS["psi_related"], "why": "PSI lists them as related"})
            for g, members in HARDWARE_GROUPS.items():
                if a in members and b in members:
                    parts.append({"kind": "shared_hardware", "weight": WEIGHTS["shared_hardware"], "why": g})
            sp = pubs[a] & pubs[b]
            if sp:
                parts.append({"kind": "shared_publication", "weight": WEIGHTS["shared_publication"], "why": sorted(sp)[:3]})
            j = jaccard(fuels[a], fuels[b])
            if j:
                parts.append({"kind": "shared_fuel", "weight": round(WEIGHTS["shared_fuel"] * j, 3),
                              "why": sorted(fuels[a] & fuels[b])[:5]})
            j = jaccard(set(by[a]["keywords"]), set(by[b]["keywords"]))
            if j:
                parts.append({"kind": "shared_keywords", "weight": round(WEIGHTS["shared_keywords"] * j, 3),
                              "why": sorted(set(by[a]["keywords"]) & set(by[b]["keywords"]))[:5]})
            fs = set(by[a]["fire_safety_areas"]) & set(by[b]["fire_safety_areas"]) - {"fundamentals"}
            if fs:
                parts.append({"kind": "shared_fire_safety_area", "weight": WEIGHTS["shared_fire_safety_area"], "why": sorted(fs)})
            if parts:
                edges.append({"a": a, "b": b, "weight": round(sum(p["weight"] for p in parts), 3), "parts": parts})
    edges.sort(key=lambda e: -e["weight"])
    nodes = [{"psi": i["psi"], "acronym": i["acronym"], "fire_safety_areas": i["fire_safety_areas"], "hardware": i["hardware"]} for i in invs]
    return {"weights": WEIGHTS, "note": "Each edge weight is the sum of its parts; every part says why.", "nodes": nodes, "edges": edges}


if __name__ == "__main__":
    if "--offline" not in sys.argv:
        fetch()
    build()
