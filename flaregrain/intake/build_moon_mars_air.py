#!/usr/bin/env python3
"""Build the Moon & Mars air snapshot: for seven habitat atmospheres, what NASA's PSI tables tested near each one.

The full-data demo's habitat view answers this live from all 2,009 PSI table rows. This public site carries only the
13 hand-checked records, so it shows a snapshot of those answers instead. The snapshot keeps counts, ranges and record
ids only: no table rows. It never interpolates; a preset with no tested row nearby says so.

The rules are the demo's own (its habitat view at the commit recorded in the snapshot):
  near          a PSI row with both oxygen and a usable pressure, within 3 points of oxygen and 1.5 psi
  oxygen only   a row within 3 points of oxygen whose table gives no usable pressure, counted apart and never placed
  distance      hypot(Δoxygen / 10, Δpsi / 4), used only to rank the nearest checked records
PSI-10 (ACME/Flame Design) is left out: its PSI record has a blank licence field (NOTICE.md).

  python3 -I flaregrain/intake/build_moon_mars_air.py --catalog PATH          write the snapshot
  python3 -I flaregrain/intake/build_moon_mars_air.py --catalog PATH --check  compare with the committed snapshot

PATH is dashboard_catalog.json, as build_dashboard_catalog.py writes it. The snapshot records the SHA-256 of the
catalog it was built from.
"""
import argparse, hashlib, json, math, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUTS = [ROOT / "data" / "moon-mars-air.json", ROOT / "redesign" / "moon-mars-air.json"]
COMPARE = ROOT / "data" / "compare-data.json"
SOURCE_COMMIT = "c219442"
KPA_PER_PSI = 6.894757
EARTH_PP = 0.21 * 14.7
EXCLUDED = {"PSI-10": "Its PSI record has a blank licence field, so this site leaves its rows out of every count."}
NEAR_O2, NEAR_PSI = 3, 1.5
PRINTED = re.compile(r"^Printed\s+\S+\s*(?:mmHg|kPa|psi|atm|torr)\b", re.I)

# The demo's presets, verbatim.
PRESETS = [
    {"id": "iss", "label": "ISS cabin", "o2": 21, "psi": 14.7, "gravity": "micro", "note": "Station air near sea-level composition."},
    {"id": "moon", "label": "Moon base or rover", "o2": 30, "psi": 10.2, "gravity": "moon", "note": "NASA’s challenge: 30% oxygen or more at 10.2 psi or less, to shorten spacesuit pre-breathing."},
    {"id": "bre-265", "label": "BRE 26.5% at 10.2 psi", "o2": 26.5, "psi": 10.2, "gravity": "moon", "note": "An exploration atmosphere named in the BRE record (PSI-20 record text, not a table value)."},
    {"id": "bre", "label": "BRE 34% at 8.2 psi", "o2": 34, "psi": 8.2, "gravity": "moon", "note": "An exploration atmosphere named in the BRE record (PSI-20 record text, not a table value)."},
    {"id": "suit", "label": "Spacesuit", "o2": 100, "psi": 4.3, "gravity": "micro", "note": "NASA’s challenge: suits hold 100% oxygen at 4.3 psi."},
    {"id": "earth", "label": "Earth, sea level", "o2": 21, "psi": 14.7, "gravity": "earth", "note": "The atmosphere Earth flammability tests use."},
    {"id": "mars", "label": "Mars habitat (assumed)", "o2": 30, "psi": 10.2, "gravity": "mars", "note": "Assumed, no NASA source: NASA’s challenge gives no Mars habitat atmosphere, so this preset reuses the Moon base numbers. Only the gravity differs."},
]
GRAVITY = {"micro": "Microgravity", "moon": "Moon, 0.16 g", "mars": "Mars, 0.38 g", "earth": "Earth, 1 g"}


def gravity_note(g):
    """The demo's gravity notes, verbatim."""
    if g == "micro":
        return "All 24 PSI combustion investigations are microgravity flight tests or analyses of them."
    if g == "earth":
        return "PSI holds microgravity data. Some investigations list normal-gravity results beside them (for example Saffire-II’s 1-g burn length and spread rate)."
    return ("PSI holds no " + GRAVITY[g] + " combustion data. NASA notes microgravity and normal-gravity results could bound intermediate gravity: "
            "use the microgravity rows here as one bound and normal-gravity results (for example Saffire-II’s 1-g columns) as the other. "
            "E-FIELD Flames (PSI-22) mimicked partial gravity with an electric field; LUCI and FM2 are future sources not yet in PSI.")


# Oxygen and pressure of the 13 checked records, read from the named field of data/compare-data.json. tests/run.py checks
# that each quoted text is still in that field. Pressure stays empty where the record gives none (B1, B10, B11: "Not in
# Table A.1"), so those records are never placed by pressure.
CHECKED = [
    ("B1", 22.2, "Oxygen", "22.2 → 22.2 vol%", None, "Pressure", "Not in Table A.1"),
    ("B10", 21.0, "Specimen and oxygen", "21.0 → 20.8 vol%", None, "Pressure", "Not in Table A.1"),
    ("B11", 21.0, "Specimen and oxygen", "21.0 → 20.7 vol%", None, "Pressure", "Not in Table A.1"),
    ("S1", 21.7, "Starting oxygen", "21.7%", (100, "kPa"), "Pressure and flame size", "100 kPa"),
    ("S25", 22.1, "Starting oxygen", "22.1%", (100, "kPa"), "Pressure and flame size", "100 kPa"),
    ("S12", 21.5, "Oxygen", "About 21.5%", None, None, None),
    ("S26", 22.1, "Oxygen", "About 22.1%", (100, "kPa"), "Pressure and flame size", "100 kPa"),
    ("M7", 18.9, "Oxygen", "18.9 → 18.4 vol%", None, None, None),
    ("FLEX-002", 21.0, "Conditions", "O₂ mole fraction 0.21", (762, "mmHg"), "Conditions", "762 mmHg"),
    ("S31", 21.2, "Oxygen", "21.2 to 21.0%", (100, "kPa"), "Flame size and pressure", "100 kPa"),
    ("BASS-T7", 21.0, "Oxygen", "21% by volume", (1, "atm"), "Duct and pressure", "1 atm"),
    ("SAME-KAPTON", None, None, None, None, None, None),
    ("SAMER-KAPTON", None, None, None, None, None, None),
]
TO_PSI = {"kPa": 1 / KPA_PER_PSI, "mmHg": 14.6959 / 760, "atm": 14.6959}


def r2(x):
    return round(x + 0.0, 2)


def checked_points():
    out = []
    for rid, o2, o2_field, o2_text, pressure, p_field, p_text in CHECKED:
        out.append({"id": rid, "o2": o2, "psi": r2(pressure[0] * TO_PSI[pressure[1]]) if pressure else None,
                    "read": {"o2": [o2_field, o2_text] if o2_field else None, "pressure": [p_field, p_text] if p_field else None}})
    return out


def rows_from(catalog):
    studies = {s[0]: s for s in catalog["studies"]}
    rows = []
    for run in catalog["runs"]:
        o2 = run[6][0]
        if not isinstance(o2, (int, float)):
            continue
        study = studies[run[1]]
        if study[7] in EXCLUDED:
            continue
        kpa = run[13] if isinstance(run[13], (int, float)) else None
        # The demo's test for a printed pressure that cannot be used, such as FLEX test 114's 0 mmHg.
        printed = next((t for t in ((run[9][2] if len(run[9]) > 2 else None) or []) if PRINTED.match(str(t))), "")
        hot = next((f[1] for f in (run[11] or []) if f[0] == "Hot flame ignited"), "")
        rows.append({"psiId": study[7], "name": study[1], "env": study[3], "area": study[2], "o2": o2,
                     "psi": kpa / KPA_PER_PSI if kpa is not None else None, "unverified": bool(printed), "hot": hot, "fuel": run[2]})
    return rows


def flags(p, with_p, near):
    """The demo's limit flags for a chosen atmosphere, without row labels."""
    out = []
    if not near:
        band = [r for r in with_p if abs(r["psi"] - p["psi"]) <= NEAR_PSI]
        below = max((r for r in band if r["o2"] < p["o2"]), key=lambda r: r["o2"], default=None)
        above = min((r for r in band if r["o2"] > p["o2"]), key=lambda r: r["o2"], default=None)
        if below and above:
            out.append({"kind": "interpolation", "text": f"Between tested rows. Within 1.5 psi of this pressure, the nearest PSI rows were tested at "
                        f"{below['o2']:g}% oxygen ({below['name']}) and {above['o2']:g}% ({above['name']}). A value here would need interpolation; Flaregrain does not interpolate."})
        else:
            out.append({"kind": "outside", "text": "Outside tested conditions. No PSI row lies within 3 points of oxygen and 1.5 psi, and none brackets this oxygen at this pressure. Any number here would be extrapolation."})
    if (abs(p["o2"] - 30) <= 2 and p["psi"] <= 12) or (abs(p["psi"] - 10.2) <= 1 and p["o2"] >= 28):
        out.append({"kind": "boundary", "text": "On the Moon base boundary (30% oxygen, 10.2 psi). Rows on either side of it fall under different NASA conditions; check which side each row is on."})
    pp = p["o2"] / 100 * p["psi"]
    max_pp = max(r["o2"] / 100 * r["psi"] for r in with_p)
    min_psi = min(r["psi"] for r in with_p)
    if pp > max_pp:
        out.append({"kind": "regime", "text": f"Oxygen partial pressure {pp:.2f} psi is above every PSI row with a pressure (highest {max_pp:.2f} psi)."})
    if p["psi"] < min_psi:
        out.append({"kind": "regime", "text": f"Total pressure {p['psi']:g} psi is below every PSI row with a pressure (lowest {min_psi:.2f} psi)."})
    if p["gravity"] != "micro":
        out.append({"kind": "gravity", "text": "Gravity regime differs from the data. PSI rows are microgravity flight tests; none of the rows counted here was tested at this gravity."})
    return out


def by_investigation(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["psiId"], []).append(r)
    out = []
    for psi_id, group in sorted(groups.items(), key=lambda kv: (-len(kv[1]), int(kv[0].split("-")[1]))):
        item = {"psi": psi_id, "name": group[0]["name"], "rows": len(group), "gravity": sorted({r["env"] for r in group}),
                "o2": [r2(min(r["o2"] for r in group)), r2(max(r["o2"] for r in group))]}
        pressures = [r["psi"] for r in group if r["psi"] is not None]
        if pressures:
            item["pressurePsi"] = [r2(min(pressures)), r2(max(pressures))]
        out.append(item)
    return out


def snapshot(catalog, catalog_sha):
    rows = rows_from(catalog)
    with_p = [r for r in rows if r["psi"] is not None]
    points = checked_points()
    presets = []
    for p in PRESETS:
        near = [r for r in with_p if abs(r["o2"] - p["o2"]) <= NEAR_O2 and abs(r["psi"] - p["psi"]) <= NEAR_PSI]
        oxygen_only = [r for r in rows if r["psi"] is None and abs(r["o2"] - p["o2"]) <= NEAR_O2]
        known = [r for r in near if r["hot"].lower() in ("yes", "no")]
        solid = [r for r in near if r["area"] == "flammability"]
        untested = []
        if not solid:
            untested.append("Whether a cabin material ignites or spreads here: no solid-material flammability test in PSI records both oxygen and pressure near this atmosphere.")
        b1s1 = [c for c in points if c["id"] in ("B1", "S1")]
        shut_near = [c["id"] for c in b1s1 if c["psi"] is not None and abs(c["o2"] - p["o2"]) <= NEAR_O2 and abs(c["psi"] - p["psi"]) <= NEAR_PSI]
        if shut_near:
            untested.append("How many seconds a flame takes to go out after the fan stops. Saffire I-1, tested close to this atmosphere, went out immediately when airflow stopped; the cited passages give no elapsed time in seconds.")
        else:
            gap = min(abs(c["o2"] - p["o2"]) for c in b1s1)
            untested.append(f"Whether a flame goes out when the fan stops here. The two checked airflow-shutoff tests (BASS-II B1, Saffire I-1) were in station air, "
                            f"{gap:.1f} points of oxygen away" + (" and at about 14.5 psi or a pressure the table does not give" if p["psi"] < 12 else "") + ".")
        both = [c for c in points if c["o2"] is not None and c["psi"] is not None]
        ranked = sorted(both, key=lambda c: (math.hypot((c["o2"] - p["o2"]) / 10, (c["psi"] - p["psi"]) / 4), c["id"]))
        presets.append({
            **p, "gravityLabel": GRAVITY[p["gravity"]],
            "partialPressurePsi": r2(p["o2"] / 100 * p["psi"]), "earthAirShare": round(p["o2"] / 100 * p["psi"] / EARTH_PP * 100),
            "near": {"rows": len(near), "investigations": by_investigation(near),
                     "gravity": sorted({r["env"] for r in near}),
                     "hotIgnition": {"known": len(known), "ignited": sum(1 for r in known if r["hot"].lower() == "yes")}},
            "oxygenOnly": {"rows": len(oxygen_only), "unverifiedPressure": sum(1 for r in oxygen_only if r["unverified"]),
                           "investigations": by_investigation(oxygen_only)},
            "gravityNote": gravity_note(p["gravity"]),
            "flags": flags(p, with_p, near),
            "untested": untested,
            "checked": {
                "near": [c["id"] for c in both if abs(c["o2"] - p["o2"]) <= NEAR_O2 and abs(c["psi"] - p["psi"]) <= NEAR_PSI],
                "oxygenOnly": [c["id"] for c in points if c["o2"] is not None and c["psi"] is None and abs(c["o2"] - p["o2"]) <= NEAR_O2],
                "nearest": [{"id": c["id"], "o2Points": r2(abs(c["o2"] - p["o2"])), "psiApart": r2(abs(c["psi"] - p["psi"]))} for c in ranked[:3]],
            },
        })
    return {
        "note": "Moon & Mars air snapshot: for seven habitat atmospheres, how many NASA PSI table rows were tested nearby, from which investigations, "
                "and what is untested. Counts, ranges and record ids only; no table rows. Built by intake/build_moon_mars_air.py.",
        "source": {"commit": SOURCE_COMMIT, "what": "the full-data demo's PSI catalog (dashboard_catalog.json) and its habitat rules at that commit",
                   "catalogSha256": catalog_sha, "investigations": catalog["summary"]["studyCount"], "rows": catalog["summary"]["runCount"]},
        "method": {
            "near": "A PSI table row is near when it records both oxygen and a usable pressure within 3 points of oxygen and 1.5 psi of the preset.",
            "oxygenOnly": "Rows within 3 points of oxygen whose table gives no usable pressure are counted apart and never placed by pressure.",
            "excluded": [{"psi": k, "reason": v} for k, v in EXCLUDED.items()],
            "checked": "Checked records use the oxygen and pressure printed in their own fields. Records with no pressure are listed by oxygen only. "
                       "Nearest ranks records with both values by hypot(Δoxygen / 10, Δpsi / 4), the demo's own distance.",
            "interpolation": "Never. A preset with no tested row nearby says so; no value is estimated between rows.",
        },
        "checkedRecords": points,
        "presets": presets,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = args.catalog.read_bytes()
    text = json.dumps(snapshot(json.loads(raw), hashlib.sha256(raw).hexdigest()), ensure_ascii=False, indent=1) + "\n"
    if args.check:
        stale = [str(p.relative_to(ROOT)) for p in OUTPUTS if not p.is_file() or p.read_text(encoding="utf-8") != text]
        print("snapshot matches a rebuild from the catalog" if not stale else "differs from a rebuild: " + ", ".join(stale))
        sys.exit(1 if stale else 0)
    for p in OUTPUTS:
        p.write_text(text, encoding="utf-8")
    print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in OUTPUTS), f"({len(text.encode())} bytes)")


if __name__ == "__main__":
    main()
