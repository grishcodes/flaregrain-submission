#!/usr/bin/env python3
"""Compact NASA data-issues summary for the dashboard panel. Run after psi_observations.py.

Groups the flagged values in data/issues.json by investigation, column and flag code,
keeping counts and up to three examples (printed value -> reading used), plus the
record-level issues. Writes data/issues_summary.json.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
CODES = {"percent_scale": "Percent printed 100× too large", "autofill": "Spreadsheet auto-fill damage",
         "missing_decimal": "Missing decimal point", "swapped": "Length and width swapped",
         "header": "Header lost a subscript", "unit_header": "Header unit missing or wrong",
         "implausible": "Implausible value, flagged for checking"}


def main():
    issues = json.loads((DATA / "issues.json").read_text())
    invs = {i["psi"]: i for i in json.loads((DATA / "investigations.json").read_text())}
    out, total = [], 0
    for psi in sorted(issues, key=lambda p: int(p.split("-")[1])):
        v = issues[psi]
        groups = {}
        for item in v["values"]:
            for f in item["flags"]:
                g = groups.setdefault((item["column"], f["code"]), {"column": item["column"], "code": f["code"], "kind": CODES.get(f["code"], f["code"]),
                                                                     "count": 0, "examples": []})
                g["count"] += 1
                if len(g["examples"]) < 3 and f["detail"] not in [e["detail"] for e in g["examples"]]:
                    g["examples"].append({"printed": item["printed"], "detail": f["detail"], "observation": item["observation"]})
        if not groups and not v["record"]:
            continue
        total += len(v["values"])
        out.append({"psi": psi, "name": invs[psi]["acronym"] or invs[psi]["title"], "page": invs[psi]["psi_page"],
                    "record": v["record"], "groups": sorted(groups.values(), key=lambda g: -g["count"]), "flagged_values": len(v["values"])})
    summary = {"flagged_values": total, "record_issues": sum(len(x["record"]) for x in out), "investigations": out, "codes": CODES}
    (DATA / "issues_summary.json").write_text(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    print(summary["flagged_values"], "flagged values,", summary["record_issues"], "record issues,", len(out), "investigations")


if __name__ == "__main__":
    main()
