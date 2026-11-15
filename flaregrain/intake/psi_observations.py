#!/usr/bin/env python3
"""Observation layer for Flaregrain, built from psi_intake.py output.

One record per table cell that carries a value. Each record keeps the value as
PSI printed it, its normalized value and unit, the quantity it measures, the
exact locator (file, version, SHA-256, CSV line, column) and any data-issue
flags. A corrected reading never replaces the printed value; both are kept.

Writes:
  data/observations.json   every value, with provenance and flags
  data/runs.json           one entry per table row (run, sample, test day)
  data/issues.json         every flag, by investigation, plus record-level issues
  data/atlas.json          the 4-area, 11-topic taxonomy with counts

Run after psi_intake.py:  python3 -I psi_observations.py
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
NUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")

# ---------- column map: (psi, file contains, column) -> quantity, role, printed unit
# role: condition | outcome | identifier | context
COLS = {}
def col(psi, file_key, column, quantity, role, unit=None):
    COLS[(psi, file_key, column)] = (quantity, role, unit)

for fk in ("Normal Flame",):
    col("PSI-10", fk, "Fuel", "fuel", "condition"); col("PSI-10", fk, "Test", "test_id", "identifier")
    col("PSI-10", fk, "XO2 (init)", "o2_ambient", "condition", "mole fraction")
    col("PSI-10", fk, "XO2 (final)", "o2_ambient_final", "condition", "mole fraction")
    col("PSI-10", fk, "pmean (atm)", "pressure", "condition", "atm")
    col("PSI-10", fk, "pinit (atm)", "pressure_initial", "condition", "atm")
    col("PSI-10", fk, "Xfuel", "fuel_fraction", "condition", "mole fraction")
    col("PSI-10", fk, "Tad (K)", "adiabatic_flame_temp", "outcome", "K")
col("PSI-10", "Inverse Flame", "Test", "test_id", "identifier")
col("PSI-10", "Inverse Flame", "XO2", "o2_burner", "condition", "mole fraction")
col("PSI-10", "Inverse Flame", "pmean (atm)", "pressure", "condition", "atm")
col("PSI-10", "Inverse Flame", "XC2H4 initial", "fuel_fraction_ambient", "condition", "mole fraction")
col("PSI-20", "BRE", "Oxygen Conc (percent)", "o2_ambient", "condition", "%")
col("PSI-20", "BRE", "Fuel Bottle", "fuel", "condition"); col("PSI-20", "BRE", "Burner Size (mm)", "burner_size", "condition", "mm")
col("PSI-20", "BRE", "Flames Ignited", "flames_ignited", "outcome", "count")
col("PSI-21", "CLD", "Fuel Bottle", "fuel", "condition"); col("PSI-21", "CLD", "Flames ignited", "flames_ignited", "outcome", "count")
col("PSI-21", "CLD", "Test Day", "test_id", "identifier")
col("PSI-22", "E-FIELD", "Fuel Bottle", "fuel", "condition"); col("PSI-22", "E-FIELD", "Mesh Polarity", "field_polarity", "condition")
col("PSI-22", "E-FIELD", "Flames Ignited", "flames_ignited", "outcome", "count"); col("PSI-22", "E-FIELD", "Test Day", "test_id", "identifier")
col("PSI-23", "s-Flame", "Atmosphere*", "atmosphere", "condition"); col("PSI-23", "s-Flame", "Fuel Bottle", "fuel", "condition")
col("PSI-23", "s-Flame", "Flames Ignited*", "flames_ignited", "outcome", "count"); col("PSI-23", "s-Flame", "Test Day*", "test_id", "identifier")
col("PSI-25", "BASS-II", "Test #", "test_id", "identifier"); col("PSI-25", "BASS-II", "Fuel Sample Material", "fuel", "condition")
col("PSI-25", "BASS-II", "Calibrated  initial O2 % by vol", "o2_ambient", "condition", "%")
col("PSI-25", "BASS-II", "Calibrated final O2 % by vol", "o2_ambient_final", "condition", "%")
col("PSI-25", "BASS-II", "Initial CO2 % by vol", "co2_ambient", "condition", "%")
col("PSI-25", "BASS-II", "Final CO (ppm)", "co_final", "outcome", "ppm")
col("PSI-26", "BASS", "Test #", "test_id", "identifier"); col("PSI-26", "BASS", "Fuel Sample Material", "fuel", "condition")
col("PSI-39", "CFI", "Flex Number", "test_id", "identifier"); col("PSI-39", "CFI", "Pressure", "pressure", "condition", None)
col("PSI-39", "CFI", "Oxygen", "o2_ambient", "condition", "mole fraction"); col("PSI-39", "CFI", "Helium", "he_ambient", "condition", "mole fraction")
col("PSI-39", "CFI", "Fuel", "fuel", "condition")
col("PSI-47", "DAFT", "Session Name", "test_id", "identifier"); col("PSI-47", "DAFT", "Sample Material", "fuel", "condition")
col("PSI-68", "Flex2", "Sample (Fuel Type)", "fuel", "condition")
col("PSI-68", "Flex2", "Oxygen Mole Fraction", "o2_ambient", "condition", "mole fraction")
col("PSI-68", "Flex2", "Ambient Pressure (atm)", "pressure", "condition", "atm")
col("PSI-68", "Flex2", "Initial Droplet Diameter (mm)", "droplet_d0", "condition", "mm")
col("PSI-68", "Flex2", "Flow Velocity (cm/s)", "flow_speed", "condition", "cm/s")
col("PSI-69", "FLEX", "FLEX Identifier", "test_id", "identifier"); col("PSI-69", "FLEX", "Fuel", "fuel", "condition")
col("PSI-69", "FLEX", "Ambient pressure; mmHg", "pressure", "condition", "mmHg")
col("PSI-69", "FLEX", "O initial ambient composition; mole fraction", "o2_ambient", "condition", "mole fraction")
col("PSI-69", "FLEX", "CO initial ambient composition; mole fraction", "co2_ambient", "condition", "mole fraction")
col("PSI-69", "FLEX", "He initial ambient composition; mole fraction", "he_ambient", "condition", "mole fraction")
col("PSI-69", "FLEX", "Droplet initial diameter; mm", "droplet_d0", "condition", "mm")
col("PSI-69", "FLEX", "Visible flame extinction diameter; mm", "extinction_diameter", "outcome", "mm")
col("PSI-69", "FLEX", "Burning rate; mm", "burning_rate", "outcome", "mm")
col("PSI-69", "FLEX", "Burn time; s", "burn_time", "outcome", "s")
col("PSI-69", "FLEX", "Test end", "test_end", "outcome")
for psi, fk in (("PSI-98", "SAFFIRE-1"), ("PSI-99", "SAFFIRE-2"), ("PSI-100", "SAFFIRE-3")):
    col(psi, fk, "Sample Number", "test_id", "identifier"); col(psi, fk, "Material", "fuel", "condition")
    col(psi, fk, "Air Flow (cm/s)", "flow_speed", "condition", "cm/s"); col(psi, fk, "Air Flow", "flow_speed", "condition", None)
    col(psi, fk, "Flow Direction", "flow_direction", "condition"); col(psi, fk, "Direction", "flow_direction", "condition")
    col(psi, fk, "Burn Time (s)", "burn_time", "outcome", "s")
col("PSI-98", "SAFFIRE-1", "Percent O2", "o2_ambient", "condition", "%")
col("PSI-98", "SAFFIRE-1", "Sample Thickness (cm)", "sample_thickness", "condition", "cm")
col("PSI-98", "SAFFIRE-1", "Sample Length (cm)", "sample_length", "condition", "cm")
col("PSI-98", "SAFFIRE-1", "Sample Width (cm)", "sample_width", "condition", "cm")
col("PSI-99", "SAFFIRE-2", "Percent O2 (Note 1)", "o2_ambient", "condition", "%")
col("PSI-99", "SAFFIRE-2", "Samle Thickness", "sample_thickness", "condition", None)
col("PSI-99", "SAFFIRE-2", "?-g Spread Length", "spread_rate_ug", "outcome", None)
col("PSI-99", "SAFFIRE-2", "?-g Burn Length", "burn_length_ug", "outcome", None)
col("PSI-99", "SAFFIRE-2", "1-g Spread Rate", "spread_rate_1g", "outcome", None)
col("PSI-100", "SAFFIRE-3", "Sample Thickness", "sample_thickness", "condition", None)
col("PSI-101", "SAME-R", "SAME Test #", "test_id", "identifier"); col("PSI-101", "SAME-R", "Sample Type", "fuel", "condition")
col("PSI-101", "SAME-R", "Inlet velocity (cm/s)", "flow_speed", "condition", "cm/s"); col("PSI-101", "SAME-R", "Rt/R0", "resistance_ratio", "outcome", "ratio")
col("PSI-101", "SAME-R", "Net aging time (sec)", "aging_time", "condition", "s")
col("PSI-102", "SAME", "Sample #", "test_id", "identifier"); col("PSI-102", "SAME", "Sample Material", "fuel", "condition")
col("PSI-102", "SAME", "Air Flow (cm/s)", "flow_speed", "condition", "cm/s"); col("PSI-102", "SAME", "Aging Duration (minutes)", "aging_time", "condition", "min")
col("PSI-106", "Slice", "Fuel Type", "fuel", "condition"); col("PSI-106", "Slice", "Test Date", "test_id", "identifier")
col("PSI-107", "Spice", "Fuel", "fuel", "condition"); col("PSI-107", "Spice", "Nozzle (mm)", "nozzle_diameter", "condition", "mm")
col("PSI-107", "Spice", "Fuel Rate (mg/s)", "fuel_rate", "condition", "mg/s"); col("PSI-107", "Spice", "Air Rate (cm/s)", "flow_speed", "condition", "cm/s")
col("PSI-107", "Spice", "GMT ignition", "test_id", "identifier")
col("PSI-142", "Data Summary", "Data Description", "description", "context")
col("PSI-159", "Normal Flames", "Test", "test_id", "identifier"); col("PSI-159", "Normal Flames", "Fuel", "fuel", "condition")
col("PSI-159", "Normal Flames", "XO2 before test", "o2_ambient", "condition", "mole fraction")
col("PSI-159", "Normal Flames", "approx p (bar)", "pressure", "condition", "bar")
col("PSI-159", "Normal Flames", "Cool flame?", "cool_flame", "outcome")
col("PSI-159", "Normal Flames", "Xf", "fuel_fraction", "condition", "mole fraction")
col("PSI-159", "Normal Flames", "mHC (mg/s)", "fuel_rate", "condition", "mg/s")
col("PSI-159", "Normal Flames", "Hot ignition", "hot_ignition", "outcome")
col("PSI-159", "Normal Flames", "burn time (sec)", "burn_time", "outcome", "s")
col("PSI-159", "Normal Flames", "Self-ext or flow term", "termination", "outcome")
col("PSI-159", "Inverse Flames", "Test", "test_id", "identifier"); col("PSI-159", "Inverse Flames", "Fuel", "fuel", "condition")
col("PSI-159", "Inverse Flames", "XO2", "o2_burner", "condition", "mole fraction")
col("PSI-159", "Inverse Flames", "approx p (bar)", "pressure", "condition", "bar")
col("PSI-159", "Inverse Flames", "Hot ignition", "hot_ignition", "outcome")
col("PSI-159", "Inverse Flames", "burn time (sec)", "burn_time", "outcome", "s")
col("PSI-159", "Inverse Flames", "Self -ext or flow term", "termination", "outcome")

QUANTITY_LABELS = {
    "o2_ambient": "Oxygen in the surrounding gas", "o2_ambient_final": "Oxygen at end of test",
    "o2_burner": "Oxygen in the burner stream (not cabin air)", "pressure": "Pressure", "fuel": "Fuel or material",
    "flow_speed": "Flow speed", "flow_direction": "Flow direction", "droplet_d0": "Initial droplet diameter",
    "extinction_diameter": "Visible flame extinction diameter", "burning_rate": "Burning rate", "burn_time": "Burn time",
    "test_end": "How the test ended", "hot_ignition": "Hot flame ignited", "cool_flame": "Cool flame",
    "termination": "Self-extinguished or flow terminated", "spread_rate_ug": "Flame spread rate in microgravity",
    "spread_rate_1g": "Flame spread rate in normal gravity", "co2_ambient": "CO₂ in the surrounding gas",
    "he_ambient": "Helium in the surrounding gas", "flames_ignited": "Flames ignited", "test_id": "Test identifier",
}

# ---------- record-level issues (from the PSI analysis, verified against PSI pages Nov 13)
RECORD_ISSUES = {
    "PSI-98": ["Dates on the PSI record (2001–2008) match SAME's; Saffire-I flew in 2016.",
               "Platform listed as ISS; the experiment flew on the Cygnus cargo vehicle.",
               "Length and width are swapped against NASA's Table I (40.6 cm wide, 94 cm long)."],
    "PSI-100": ["Research impacts text repeats Saffire-I's (PSI-98) word for word.",
                "Platform listed as ISS; the experiment flew on Cygnus.",
                "Thickness printed .33 cm; Saffire investigators give 0.37 mm for the same fabric."],
    "PSI-39": ["Table test dates are 2017; the PSI record gives 2020–2021."],
    "PSI-10": ["Licence field is blank on the PSI record."],
    "PSI-106": ["Investigation dates are blank on the PSI record."],
    "PSI-107": ["Investigation dates are blank on the PSI record."],
    "PSI-159": ["Investigation dates are blank on the PSI record."],
    "PSI-69": ["Header subscripts were lost: 'O', 'N', 'CO' mean O₂, N₂, CO₂. 'Burning rate; mm' lacks its unit (report: mm²/s)."],
    "PSI-99": ["Headers print '?-g' where the source has 'µ-g'."],
}

ATLAS = [
    ("flammability", "Material flammability and fire growth", [
        ("large-scale", "Large-scale fire growth", ["PSI-98", "PSI-99", "PSI-100"]),
        ("solid-spread", "Solid flame spread and limits", ["PSI-26", "PSI-25", "PSI-62"]),
        ("enriched-o2", "Burning in enriched-oxygen habitat air", ["PSI-20"])]),
    ("extinction", "Extinction and suppression", [
        ("droplet", "Droplet limits and inert suppressants", ["PSI-69", "PSI-68"]),
        ("cool-flames", "Hidden cool-flame burning", ["PSI-39", "PSI-159", "PSI-117", "PSI-142"]),
        ("gas-extinction", "Gas-flame extinction", ["PSI-23", "PSI-10"])]),
    ("detection", "Smoke, soot and detection", [
        ("smoke", "Smoke and detectors", ["PSI-102", "PSI-101", "PSI-115"]),
        ("instruments", "Instrument qualification", ["PSI-47"]),
        ("soot", "Soot and smoke points", ["PSI-107", "PSI-60"])]),
    ("fundamentals", "Flame fundamentals", [
        ("coflow", "Coflow flames", ["PSI-21", "PSI-106"]),
        ("e-field", "Electric-field control", ["PSI-22"])]),
]

MOON = {"o2_min": 0.30, "pressure_max_kpa": 10.2 * 6.894757}  # challenge text: >=30% O2, <=10.2 psi


def nums(s):
    return [float(n) for n in NUM.findall(s.replace(",", ""))]


def to_kpa(v, unit):
    return {"atm": v * 101.325, "bar": v * 100.0, "mmHg": v * 0.133322, "kPa": v, "psi": v * 6.894757}.get(unit)


def normalize(psi, quantity, raw, unit, row_cells):
    """Return (normalized dict or None, flags list)."""
    flags, s = [], raw.strip()
    if not s or s in {"-", "n/a", "none"}:
        return None, flags
    if quantity in ("o2_ambient", "o2_ambient_final", "o2_burner", "co2_ambient", "he_ambient"):
        vals = nums(s)
        if not vals:
            return None, flags
        out = []
        for v in vals:
            frac = v
            if unit == "%" or "%" in s or v > 1:
                frac = v / 100.0
            if frac > 1:  # e.g. "3400%" printed for 34%
                flags.append({"code": "percent_scale", "detail": f"Printed {v:g}%; read as {v/100:g}%."})
                frac = v / 10000.0
            out.append(round(frac, 6))
        res = {"unit": "mole fraction", "values": out} if len(out) > 1 else {"unit": "mole fraction", "value": out[0]}
        if "~" in s:
            res["approx"] = True
        if " to " in s or re.search(r"\d\s*-\s*\d", s):
            res["range"] = [min(out), max(out)] if len(out) > 1 else None
        if quantity == "o2_ambient_final" and psi == "PSI-25":
            init = nums(row_cells.get("Calibrated  initial O2 % by vol", {}).get("raw", ""))
            if init and out and abs(out[0] * 100 - init[0]) > 5:
                flags.append({"code": "implausible", "detail": f"Final O₂ {out[0]*100:g}% vs initial {init[0]:g}%; a change of more than 5 points in one test needs checking against the BASS-II report."})
        return res, flags
    if quantity in ("pressure", "pressure_initial"):
        u = unit
        if u is None:
            m = re.search(r"(atm|bar|mmHg|kPa|psi)", s)
            u = m.group(1) if m else None
        vals = nums(s)
        if not vals or not u:
            return None, flags
        kpa = [round(to_kpa(v, u), 3) for v in vals]
        res = {"unit": "kPa", "printed_unit": u}
        res.update({"values": kpa} if len(kpa) > 1 else {"value": kpa[0], "psi": round(kpa[0] / 6.894757, 3)})
        return res, flags
    if quantity in ("sample_thickness", "sample_length", "sample_width", "burn_length_ug"):
        m = re.search(r"(mm|cm)", s)
        u = (m.group(1) if m else unit) or "cm"
        vals = nums(s)
        if not vals:
            return None, flags
        v = vals[0]
        if re.match(r"^0\d", s.strip()):
            flags.append({"code": "missing_decimal", "detail": f"Printed '{s}'; read as 0.{s.strip()[1:]}."})
            v = float("0." + re.sub(r"\D", "", s.strip())[1:])
        mm = v * 10 if u == "cm" else v
        return {"unit": "mm", "value": round(mm, 4), "printed_unit": u}, flags
    if quantity in ("spread_rate_ug", "spread_rate_1g"):
        vals = nums(s)
        if vals and "mm/s" in s:
            return {"unit": "mm/s", "value": vals[0]}, flags
        return None, flags
    if quantity == "flow_speed":
        vals = nums(s)
        if not vals:
            return None, flags
        res = {"unit": "cm/s"}
        res.update({"values": vals} if len(vals) > 1 else {"value": vals[0]})
        if min(vals) < 0:  # second reading, issue #5: a flow speed cannot be negative
            flags.append({"code": "implausible", "detail": f"Printed {s} cm/s; a flow speed cannot be negative. Likely air off or a sensor offset (or no signal on 'LOS' rows); do not use as a flow condition."})
        return res, flags
    if quantity == "fuel":
        fixed = s
        if psi == "PSI-21" and re.search(r"\bCH([5-9]|1\d)\b", s):
            fixed = re.sub(r"\bCH(?:[5-9]|1\d)\b", "CH4", s)
            flags.append({"code": "autofill", "detail": f"'{s}' looks like spreadsheet auto-fill of 'CH4'; read as '{fixed}'."})
        if psi == "PSI-23" and re.search(r"\bN([3-9])\b", s):
            fixed = re.sub(r"\bN[3-9]\b", "N2", s)
            flags.append({"code": "autofill", "detail": f"'{s}' looks like spreadsheet auto-fill of 'N2'; read as '{fixed}'."})
        return {"text": fixed}, flags
    if quantity == "atmosphere":
        fixed = s
        if psi == "PSI-23" and re.search(r"\bN([3-9])\b", s):
            fixed = re.sub(r"\bN[3-9]\b", "N2", s)
            flags.append({"code": "autofill", "detail": f"'{s}' looks like spreadsheet auto-fill of 'N2'; read as '{fixed}'."})
        o2 = re.search(r"~?\s*(\d+(?:\.\d+)?)%\s*O2", fixed)
        res = {"text": fixed}
        if o2:
            res["o2"] = float(o2.group(1)) / 100
        return res, flags
    vals = nums(s)
    if unit and vals and quantity not in ("test_id",):
        return {"unit": unit, "value": vals[0]}, flags
    return {"text": s}, flags


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    invs = {i["psi"]: i for i in json.loads((DATA / "investigations.json").read_text())}
    sha = {(f["psi"], f["file_name"]): f["sha256"] for f in manifest["files"] if f["kind"] == "experimental_table"}
    observations, runs, issues = [], [], {p: {"record": RECORD_ISSUES.get(p, []), "values": []} for p in invs}
    for psi in sorted(invs, key=lambda p: int(p.split("-")[1])):
        p = DATA / "tables" / f"{psi}.json"
        if not p.exists():
            continue
        for t in json.loads(p.read_text()):
            fname = t["file_name"]
            for row in t["rows"]:
                rid = f"{psi}:{fname}:{row['csv_line']}"
                run = {"id": rid, "psi": psi, "acronym": invs[psi]["acronym"], "file": fname, "csv_line": row["csv_line"],
                       "sha256": sha.get((psi, fname)), "label": None, "conditions": {}, "outcomes": {}, "flags": [], "moon": False}
                for column, cell in row["cells"].items():
                    raw = cell["raw"]
                    if not raw.strip():
                        continue
                    key = next((k for k in COLS if k[0] == psi and k[1] in fname and k[2] == column), None)
                    quantity, role, unit = COLS[key] if key else ("other:" + column, "context", None)
                    norm, flags = (normalize(psi, quantity, raw, unit, row["cells"]) if key else (None, []))
                    if psi == "PSI-98" and quantity in ("sample_length", "sample_width"):
                        flags.append({"code": "swapped", "detail": "Length and width are swapped against NASA Table I (40.6 cm wide, 94 cm long)."})
                    if psi == "PSI-69" and quantity == "co2_ambient":
                        flags.append({"code": "header", "detail": "Header prints 'CO'; subscript lost, means CO₂."})
                    if psi == "PSI-69" and quantity == "burning_rate":
                        flags.append({"code": "unit_header", "detail": "Header unit printed 'mm'; the FLEX report gives burning rate in mm²/s."})
                    obs = {"id": f"{rid}:{column}", "run": rid, "psi": psi, "column": column, "quantity": quantity, "role": role,
                           "printed": raw, "printed_unit": unit, "normalized": norm, "flags": flags, "tier": "catalogued"}
                    observations.append(obs)
                    if flags:
                        issues[psi]["values"].append({"observation": obs["id"], "column": column, "printed": raw, "flags": flags})
                        run["flags"] += [f["code"] for f in flags]
                    if role == "identifier" and run["label"] is None:
                        run["label"] = raw.strip()
                    elif role in ("condition", "outcome") and norm is not None:
                        run["conditions" if role == "condition" else "outcomes"][quantity] = norm
                if "pressure" not in run["conditions"] and "pressure_initial" in run["conditions"]:
                    run["conditions"]["pressure"] = dict(run["conditions"]["pressure_initial"], basis="initial pressure; mean pressure blank in the PSI table")
                o2 = run["conditions"].get("o2_ambient", {}); pr = run["conditions"].get("pressure", {})
                if "value" in o2 and "value" in pr and o2["value"] >= MOON["o2_min"] and pr["value"] <= MOON["pressure_max_kpa"]:
                    run["moon"] = True
                run["label"] = run["label"] or f"line {row['csv_line']}"
                run["flags"] = sorted(set(run["flags"]))
                runs.append(run)
    atlas = []
    for akey, aname, topics in ATLAS:
        ts = []
        for tkey, tname, members in topics:
            ts.append({"key": tkey, "name": tname, "investigations": [
                {"psi": m, "acronym": invs[m]["acronym"] or invs[m]["title"], "title": invs[m]["title"],
                 "runs": sum(1 for r in runs if r["psi"] == m), "moon_runs": sum(1 for r in runs if r["psi"] == m and r["moon"])}
                for m in members]})
        atlas.append({"key": akey, "name": aname, "topics": ts})
    placed = {m for _, _, ts in ATLAS for _, _, ms in ts for m in ms}
    assert placed == set(invs), f"unplaced: {set(invs) - placed}"
    (DATA / "observations.json").write_text(json.dumps(observations, indent=1, ensure_ascii=False))
    (DATA / "runs.json").write_text(json.dumps(runs, indent=1, ensure_ascii=False))
    (DATA / "issues.json").write_text(json.dumps(issues, indent=1, ensure_ascii=False))
    (DATA / "atlas.json").write_text(json.dumps({"moon_test": MOON, "areas": atlas, "quantity_labels": QUANTITY_LABELS}, indent=1, ensure_ascii=False))
    nflag = sum(len(v["values"]) for v in issues.values())
    print(f"{len(observations)} observations, {len(runs)} runs, {sum(r['moon'] for r in runs)} at Moon conditions, "
          f"{nflag} flagged values, {sum(len(v['record']) for v in issues.values())} record issues")


if __name__ == "__main__":
    main()
