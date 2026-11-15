#!/usr/bin/env python3
"""Coverage ranges for all 24 investigations, and profiles for those the dashboard lacks.

Coverage comes from data/runs.json (PSI experimental tables): oxygen in the
surrounding gas (vol%), pressure (kPa and psi), row count and Moon-condition rows.
Profiles come from the PSI records, tier "catalogued".

Writes data/dashboard_profiles.json. Run after psi_observations.py.
"""
import json, re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
AREAS = {"PSI-25": ["prevention", "suppression"], "PSI-26": ["prevention", "suppression"], "PSI-98": ["prevention"],
         "PSI-99": ["prevention"], "PSI-100": ["prevention"], "PSI-20": ["prevention"], "PSI-62": ["prevention"],
         "PSI-159": ["prevention"], "PSI-102": ["detection"], "PSI-101": ["detection"], "PSI-47": ["detection"],
         "PSI-115": ["detection"], "PSI-107": ["detection"], "PSI-69": ["suppression"], "PSI-68": ["suppression"],
         "PSI-39": ["suppression"], "PSI-117": ["suppression"], "PSI-142": ["suppression"], "PSI-23": ["suppression"]}


def sentences(text, n=2):
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text or "").strip())
    return " ".join(parts[:n])


def main():
    runs = json.loads((DATA / "runs.json").read_text())
    invs = json.loads((DATA / "investigations.json").read_text())
    issues = json.loads((DATA / "issues.json").read_text())
    obs_cols = {}
    cov = {}
    for r in runs:
        c = cov.setdefault(r["psi"], {"rows": 0, "o2": [], "kpa": [], "moon": 0})
        c["rows"] += 1
        c["moon"] += r["moon"]
        o = r["conditions"].get("o2_ambient") or {}
        vals = [o["value"]] if "value" in o else o.get("values", [])
        if not vals and "o2" in (r["conditions"].get("atmosphere") or {}):
            vals = [r["conditions"]["atmosphere"]["o2"]]
        c["o2"] += [v * 100 for v in vals if v > 0]
        p = r["conditions"].get("pressure") or {}
        c["kpa"] += [v for v in ([p["value"]] if "value" in p else p.get("values", [])) if v > 0]
        for k in r["outcomes"]:
            obs_cols.setdefault(r["psi"], set()).add(k)
    coverage = {}
    for psi, c in cov.items():
        page = f"https://psi.nasa.gov/physci/repo/data/investigations/{psi}"
        e = {"rows": c["rows"], "moon": c["moon"], "source": [f"NASA {psi} experimental table", page]}
        if c["o2"]:
            e["oxygen"] = {"min": round(min(c["o2"]), 1), "max": round(max(c["o2"]), 1)}
        if c["kpa"]:
            e["pressure"] = {"minKpa": round(min(c["kpa"]), 1), "maxKpa": round(max(c["kpa"]), 1),
                             "minPsi": round(min(c["kpa"]) / 6.894757, 2), "maxPsi": round(max(c["kpa"]) / 6.894757, 2)}
        coverage[psi] = e
    labels = json.loads((DATA / "atlas.json").read_text())["quantity_labels"]
    profiles = []
    for inv in invs:
        raw = json.loads((DATA / "raw" / inv["psi"] / "record.json").read_text())
        cv = coverage.get(inv["psi"], {})
        cond = []
        if "oxygen" in cv:
            cond.append(f"Oxygen {cv['oxygen']['min']:g} to {cv['oxygen']['max']:g}% in the PSI table")
        if "pressure" in cv:
            cond.append(f"pressure {cv['pressure']['minPsi']:g} to {cv['pressure']['maxPsi']:g} psi")
        meas = ", ".join(labels.get(k, k.replace("_", " ")) for k in sorted(obs_cols.get(inv["psi"], [])))
        profiles.append({
            "id": inv["psi"], "checked": "", "atlas": "", "name": inv["acronym"] or inv["title"], "title": inv["title"],
            "version": str(inv["version"]), "areas": AREAS.get(inv["psi"], []), "runs": [],
            "platform": inv["platform"] or "Not stated on the PSI record", "hardware": inv["hardware"] or "Not stated on the PSI record",
            "objective": sentences(raw.get("objective") or raw.get("description")) or "Not stated on the PSI record.",
            "fuels": ", ".join(inv["fuels_in_tables"][:8]) or "Not listed in a PSI table.",
            "conditions": ("; ".join(cond) + "." if cond else "No oxygen or pressure column in the PSI table."),
            "variables": "", "measurements": meas or "No outcome column in the PSI table.",
            "notes": issues.get(inv["psi"], {}).get("record", []), "generated": True,
        })
    # Search text per investigation: PSI title, keywords, platform and hardware, plus the table summary written below.
    search = {}
    for inv in invs:
        raw = json.loads((DATA / "raw" / inv["psi"] / "record.json").read_text())
        search[inv["psi"]] = " ".join(x for x in [inv["title"], inv["acronym"], " ".join(inv["keywords"]), inv["platform"] or "", inv["hardware"] or "",
                                                  raw.get("subResearchArea") or "", " ".join(inv["fuels_in_tables"])] if x)
    summaries = table_chunk_texts(invs, runs, coverage, obs_cols, labels, issues)
    for psi, text in summaries.items():
        search[psi] = search.get(psi, "") + " " + text
    (DATA / "dashboard_profiles.json").write_text(json.dumps({"coverage": coverage, "profiles": profiles, "search": search}, ensure_ascii=False,
                                                             separators=(",", ":")))
    print(len(coverage), "coverage entries,", len(profiles), "profiles")
    write_table_chunks(invs, runs, coverage, obs_cols, labels, issues)


def table_chunk_texts(invs, runs, coverage, obs_cols, labels, issues):
    return {c["psi"]: c["text"] for c in table_chunks(invs, runs, coverage, obs_cols, labels, issues)}


def write_table_chunks(invs, runs, coverage, obs_cols, labels, issues):
    out = table_chunks(invs, runs, coverage, obs_cols, labels, issues)
    with open(DATA / "chunks_table_summaries.jsonl", "w") as fh:
        for c in out:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    # Title cards (Mac Mini prototype B): one short passage per investigation with acronym, title and PSI keywords,
    # added beside the existing chunks rather than prefixed to them, which hurt topic questions.
    cards = [{"id": f"{i['psi']}:title-card:0", "psi": i["psi"], "acronym": i["acronym"], "field": "title card",
              "text": f"{i['acronym']}: {i['title']}. PSI keywords: {', '.join(i['keywords'])}.", "source": i["psi_page"], "doi": i["doi"], "tier": "catalogued"}
             for i in invs]
    base = (DATA / "chunks.jsonl").read_text()
    extra = out + cards
    (DATA / "chunks_all.jsonl").write_text(base + "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in extra))
    print(len(out), "table-summary chunks,", len(cards), "title cards;", base.count("\n") + len(extra), "chunks in chunks_all.jsonl")


def table_chunks(invs, runs, coverage, obs_cols, labels, issues):
    """One passage per investigation, written from its PSI table, so text retrieval
    can find conditions that the PSI descriptions never state (for example CFI-G's
    Moon-base oxygen). Marked tier "generated from table": Flaregrain's wording, NASA's numbers."""
    flows = {}
    for r in runs:
        f = r["conditions"].get("flow_speed") or {}
        flows.setdefault(r["psi"], []).extend([f["value"]] if "value" in f else f.get("values", []))
    out = []
    for inv in invs:
        psi, cv = inv["psi"], coverage.get(inv["psi"])
        name = inv["acronym"] or inv["title"]
        label = name if psi in name else f"{name} ({psi})"
        page = f"https://psi.nasa.gov/physci/repo/data/investigations/{psi}"
        if not cv:
            text = (f"{label} has no experimental table in PSI, so Flaregrain holds no per-run oxygen, pressure "
                    f"or outcome values for it. Its PSI record describes the work; see the investigation page.")
        else:
            parts = [f"{label} PSI experimental table, summarized by Flaregrain from {cv['rows']} rows."]
            if inv["fuels_in_tables"]:
                parts.append("Fuels and materials listed: " + ", ".join(inv["fuels_in_tables"][:8]) + ".")
            if "oxygen" in cv:
                parts.append(f"Oxygen in the surrounding gas ranges from {cv['oxygen']['min']:g}% to {cv['oxygen']['max']:g}%.")
            if "pressure" in cv:
                p = cv["pressure"]
                parts.append(f"Pressure ranges from {p['minPsi']:g} to {p['maxPsi']:g} psi ({p['minKpa']:g} to {p['maxKpa']:g} kPa).")
            if flows.get(psi):
                parts.append(f"Flow speed ranges from {min(flows[psi]):g} to {max(flows[psi]):g} cm/s.")
            meas = [labels.get(k, k.replace("_", " ")).lower() for k in sorted(obs_cols.get(psi, []))]
            parts.append(("Outcomes recorded per row: " + ", ".join(meas) + ".") if meas else "The table records conditions only, with no outcome column.")
            if cv["moon"]:
                parts.append(f"{cv['moon']} rows meet the Moon base habitat conditions in NASA's challenge: oxygen at 30% or more "
                             f"and pressure at 10.2 psi or less.")
            n_flags = len(issues.get(psi, {}).get("values", []))
            if n_flags:
                parts.append(f"{n_flags} values carry data-issue flags; the printed value is kept beside the reading used.")
            text = " ".join(parts)
        out.append({"id": f"{psi}:table-summary:0", "psi": psi, "acronym": name, "field": "table summary", "text": text,
                    "source": page, "doi": inv["doi"], "tier": "generated from table"})
    return out


if __name__ == "__main__":
    main()
