#!/usr/bin/env python3
"""Turn data/runs.json + data/atlas.json into the dashboard's embedded catalog.

Keeps the tuple shapes the dashboard already reads, so the Atlas and Catalog
code can stay; every row is a real PSI table row.

  study: [id, name, area, environment, sources, topicKey, topicName, psi, title]
  run:   [id, studyId, material, quality, metric, flow, oxygen, observation, conditions, locator]
         flow/oxygen/observation = [value, unit, basis, status]
         locator = [label, url, flags]

Writes data/dashboard_catalog.json. Run after psi_observations.py.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
ANALYSIS = {"PSI-60", "PSI-62", "PSI-115", "PSI-117", "PSI-142"}
OUTCOME_ORDER = ["extinction_diameter", "burn_time", "test_end", "hot_ignition", "termination", "spread_rate_ug",
                 "flames_ignited", "resistance_ratio", "burning_rate", "adiabatic_flame_temp", "co_final"]


def fmt(v):
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def main():
    runs = json.loads((DATA / "runs.json").read_text())
    # Second readings of questioned cells are kept in the team's working repository; without that file every flag uses the
    # intake's own reading, which is what the public build does.
    second_file = DATA.parent / "second_readings.json"
    second = {(x["psi"], int(x["csv_line"])): x for x in json.loads(second_file.read_text()).get("readings", [])} if second_file.exists() else {}
    issues = json.loads((DATA / "issues.json").read_text())
    details = {}
    for v in issues.values():
        for item in v["values"]:
            run_id = item["observation"].rsplit(":", 1)[0]
            details.setdefault(run_id, []).extend(f["detail"] for f in item["flags"])
    obs_q = {o["id"]: o["quantity"] for o in json.loads((DATA / "observations.json").read_text()) if o["flags"]}
    cell_flags = {}
    for v in issues.values():
        for item in v["values"]:
            run_id = item["observation"].rsplit(":", 1)[0]
            cell_flags.setdefault((run_id, obs_q.get(item["observation"])), []).extend(f["detail"] for f in item["flags"])
    atlas = json.loads((DATA / "atlas.json").read_text())
    invs = {i["psi"]: i for i in json.loads((DATA / "investigations.json").read_text())}
    labels = atlas["quantity_labels"]
    place = {}
    for a in atlas["areas"]:
        for t in a["topics"]:
            for i in t["investigations"]:
                place[i["psi"]] = (a["key"], t["key"], t["name"])
    studies, out_runs = [], []
    for psi in sorted(invs, key=lambda p: int(p.split("-")[1])):
        inv = invs[psi]
        area, tkey, tname = place[psi]
        env = "analysis" if psi in ANALYSIS else "microgravity"
        sources = [t["file_name"].split("_Experimental table_")[-1] for t in inv["tables"]] or ["PSI record only"]
        studies.append([psi.lower(), inv["acronym"] or inv["title"], area, env, sources, tkey, tname, psi, inv["title"]])
    n = 0
    for r in runs:
        n += 1
        c, o = r["conditions"], r["outcomes"]
        fuel = (c.get("fuel") or {}).get("text") or "Material not in table"
        flow = c.get("flow_speed", {})
        flow_t = [flow.get("value"), "cm/s", "PSI table", "recorded" if "value" in flow else "missing"]
        ox = c.get("o2_ambient", {})
        ox_v = ox.get("value")
        ox_t = [round(ox_v * 100, 3) if ox_v is not None else None, "vol%", "PSI table" + (" · ~" if ox.get("approx") else ""),
                "recorded" if ox_v is not None else "missing"]
        metric = next((k for k in OUTCOME_ORDER if k in o), None)
        if metric:
            m = o[metric]
            val = m.get("value", m.get("text"))
            obs = [val, m.get("unit", ""), labels.get(metric, metric.replace("_", " ")), "recorded"]
        else:
            metric = "conditions-only"
            obs = [None, "", "No outcome column in this table", "missing"]
        row_flags = [f for f in r["flags"] if f not in ("header", "unit_header")]  # header issues are table-level, shown per cell and in the panel
        quality = "flagged" if row_flags else ("complete" if metric != "conditions-only" else "partial")
        parts = [fuel]
        if ox_v is not None:
            parts.append(f"O₂ {fmt(ox_v*100)}%")
        if "o2_burner" in c and "value" in c["o2_burner"]:
            parts.append(f"burner O₂ {fmt(c['o2_burner']['value']*100)}% (not cabin air)")
        pr = c.get("pressure", {})
        if "value" in pr:
            parts.append(f"{fmt(pr['value'])} kPa ({fmt(pr['psi'])} psi)")
        if "value" in flow:
            parts.append(f"{fmt(flow['value'])} cm/s flow")
        if "flow_direction" in c:
            parts.append(c["flow_direction"].get("text", "").lower() + " flow")
        if r["moon"]:
            parts.append("meets Moon-base O₂ and pressure")
        page = f"https://psi.nasa.gov/physci/repo/data/investigations/{r['psi']}"
        locator = [f"{r['file']} · CSV line {r['csv_line']} · SHA-256 {r['sha256'][:12]}", page, sorted(set(details.get(r["id"], [])))]
        fields = []
        for role, group in (("condition", c), ("outcome", o)):
            for q, m in group.items():
                if q in ("test_id",):
                    continue
                label = labels.get(q, q.replace("_", " ").capitalize())
                if "value" in m:
                    v = f"{fmt(m['value'] * 100) + '%' if m.get('unit') == 'mole fraction' else fmt(m['value']) + (' ' + m['unit'] if m.get('unit') else '')}"
                    if q == "pressure" and "psi" in m:
                        v += f" ({fmt(m['psi'])} psi)"
                elif "values" in m:
                    vals = m["values"]
                    v = ", ".join(fmt(x * 100) + "%" if m.get("unit") == "mole fraction" else fmt(x) for x in vals) + ("" if m.get("unit") == "mole fraction" else " " + m.get("unit", ""))
                else:
                    v = m.get("text", "")
                flag = "; ".join(cell_flags.get((r["id"], q), []))
                fields.append([label, v.strip(), flag])
        out_runs.append([f"psi-run-{n:04d}", r["psi"].lower(), fuel, quality, metric, flow_t, ox_t, obs,
                         " · ".join(p for p in parts if p), locator, r["label"], fields,
                         second.get((r["psi"], r["csv_line"])), pr.get("value")])  # [13] pressure in kPa, for the habitat explorer
    by_area = {}
    for s in studies:
        by_area[s[2]] = by_area.get(s[2], 0) + 1
    runs_by_area = {}
    sid_area = {s[0]: s[2] for s in studies}
    for r in out_runs:
        runs_by_area[sid_area[r[1]]] = runs_by_area.get(sid_area[r[1]], 0) + 1
    summary = {"studyCount": len(studies), "runCount": len(out_runs), "studiesByDomain": by_area, "runsByDomain": runs_by_area,
               "source": "NASA PSI combustion repository, experimental tables", "moonRuns": sum(r["moon"] for r in runs)}
    (DATA / "dashboard_catalog.json").write_text(json.dumps({"summary": summary, "studies": studies, "runs": out_runs},
                                                            ensure_ascii=False, separators=(",", ":")))
    print(summary)


if __name__ == "__main__":
    main()
