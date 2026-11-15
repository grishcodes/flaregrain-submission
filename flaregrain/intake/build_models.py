#!/usr/bin/env python3
"""Descriptive trend models fitted by Flaregrain on PSI table rows. Not NASA findings.

M1  FLEX (PSI-69): visible flame extinction diameter (mm) against oxygen mole
    fraction, per fuel, adjusting for initial droplet diameter, CO2 and He
    fractions and log pressure. Ordinary least squares.
M2  CFI-G (PSI-159, normal flames): probability of hot-flame ignition against
    oxygen mole fraction and log pressure. Logistic regression.

Uncertainty: 1,000 bootstrap resamples of rows (fixed seed), 90% bands.
Curves are drawn only inside the oxygen range measured at that setting.
Standard library only. Writes data/models.json. Run after psi_observations.py.
"""
import json, math, random
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
B = 1000
LABEL = "Fitted by Flaregrain to PSI table rows. A descriptive model, not a NASA finding. Not valid outside the measured range."


def solve(a, b):
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            raise ValueError("singular")
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def ols(X, y):
    k = len(X[0])
    xtx = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * yy for r, yy in zip(X, y)) for i in range(k)]
    return solve(xtx, xty)


def logistic(X, y, iters=50, ridge=1e-6):
    k = len(X[0])
    w = [0.0] * k
    for _ in range(iters):
        p = [1 / (1 + math.exp(-max(-30, min(30, sum(a * b for a, b in zip(r, w)))))) for r in X]
        g = [sum((yy - pp) * r[i] for r, yy, pp in zip(X, y, p)) - ridge * w[i] for i in range(k)]
        h = [[sum(pp * (1 - pp) * r[i] * r[j] for r, pp in zip(X, p)) + (ridge if i == j else 0) for j in range(k)] for i in range(k)]
        step = solve(h, g)
        w = [a + b for a, b in zip(w, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    return w


def pct(vals, q):
    s = sorted(vals)
    i = (len(s) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def val(d, key):
    v = (d.get(key) or {})
    return v.get("value")


def flex_model(runs):
    rng = random.Random(13)
    out = []
    for fuel in ("Heptane", "Methanol"):
        rows = []
        for r in runs:
            if r["psi"] != "PSI-69" or (r["conditions"].get("fuel") or {}).get("text") != fuel:
                continue
            c, o = r["conditions"], r["outcomes"]
            vals = [val(c, "o2_ambient"), val(c, "droplet_d0"), val(c, "co2_ambient"), val(c, "he_ambient"), val(c, "pressure"), val(o, "extinction_diameter")]
            if None in vals or vals[4] <= 0:
                continue
            if vals[5] <= 0:
                continue
            rows.append({"run": r["id"], "label": r["label"], "o2": vals[0], "d0": vals[1], "co2": vals[2], "he": vals[3], "kpa": vals[4], "y": vals[5],
                         "line": r["csv_line"]})
        X = [[1, q["o2"], q["d0"], q["co2"], q["he"], math.log(q["kpa"])] for q in rows]
        y = [math.log(q["y"]) for q in rows]  # log scale keeps predicted diameters positive
        coef = ols(X, y)
        resid = [yy - sum(a * b for a, b in zip(x, coef)) for x, yy in zip(X, y)]
        ss_res = sum(e * e for e in resid)
        mean = sum(y) / len(y)
        r2 = 1 - ss_res / sum((yy - mean) ** 2 for yy in y)
        air = [q for q in rows if q["co2"] == 0 and q["he"] == 0 and abs(q["kpa"] - 101.325) <= 15]
        d0 = sorted(q["d0"] for q in rows)[len(rows) // 2]
        o2s = [q["o2"] for q in air] or [q["o2"] for q in rows]
        lo, hi = min(o2s), max(o2s)
        grid = [lo + (hi - lo) * i / 24 for i in range(25)]
        ref = math.log(101.325)
        boots = []
        for _ in range(B):
            idx = [rng.randrange(len(rows)) for _ in rows]
            try:
                boots.append(ols([X[i] for i in idx], [y[i] for i in idx]))
            except ValueError:
                pass
        curve = []
        for g in grid:
            x = [1, g, d0, 0, 0, ref]
            preds = [math.exp(sum(a * b for a, b in zip(x, w))) for w in boots]
            curve.append({"o2": round(g, 4), "fit": round(math.exp(sum(a * b for a, b in zip(x, coef))), 4),
                          "lo": round(pct(preds, .05), 4), "hi": round(pct(preds, .95), 4)})
        slope = [w[1] for w in boots]  # change in log diameter per unit O2 mole fraction
        out.append({
            "fuel": fuel, "n": len(rows), "r2": round(r2, 3),
            "o2_effect_pct_per_0_01": {"fit": round((math.exp(coef[1] * 0.01) - 1) * 100, 2), "lo": round((math.exp(pct(slope, .05) * 0.01) - 1) * 100, 2),
                                       "hi": round((math.exp(pct(slope, .95) * 0.01) - 1) * 100, 2)},
            "o2_range_at_1_atm": [lo, hi],
            "held_at": {"initial_diameter_mm": d0, "co2": 0, "he": 0, "pressure_kpa": 101.325},
            "curve": curve,
            "points": [{"run": q["run"], "label": q["label"], "o2": q["o2"], "y": q["y"], "kpa": q["kpa"], "diluted": bool(q["co2"] or q["he"]), "line": q["line"]} for q in rows],
        })
    return {"id": "flex-extinction-diameter", "psi": "PSI-69", "title": "FLEX: flame extinction diameter against oxygen",
            "outcome": "Visible flame extinction diameter (mm)", "method": "Least squares per fuel on log diameter: log d ~ O₂ + initial diameter + CO₂ + He + log pressure. 90% bootstrap band, 1,000 resamples.",
            "curve_note": "Curve at 1 atm, no CO₂ or He, median initial diameter; drawn only across the oxygen range FLEX measured at about 1 atm without diluent.",
            "label": LABEL, "fits": out}


def cfig_model(runs):
    rng = random.Random(14)
    rows = []
    for r in runs:
        if r["psi"] != "PSI-159" or "Normal" not in r["file"]:
            continue
        c, o = r["conditions"], r["outcomes"]
        ign = (o.get("hot_ignition") or {}).get("text", "").strip().lower()
        xf = val(c, "fuel_fraction")
        if ign not in ("yes", "no") or val(c, "o2_ambient") is None or val(c, "pressure") is None or not xf or xf <= 0:
            continue
        rows.append({"run": r["id"], "label": r["label"], "o2": val(c, "o2_ambient"), "kpa": val(c, "pressure"), "xf": xf, "y": 1 if ign == "yes" else 0,
                     "moon": r["moon"], "fuel": (c.get("fuel") or {}).get("text"), "line": r["csv_line"]})
    X = [[1, q["o2"], math.log(q["kpa"]), math.log(q["xf"])] for q in rows]
    y = [q["y"] for q in rows]
    coef = logistic(X, y)
    # 5-fold cross-validated accuracy, fixed fold assignment
    folds = [i % 5 for i in range(len(rows))]
    random.Random(15).shuffle(folds)
    cv_ok = 0
    for k in range(5):
        tr = [i for i in range(len(rows)) if folds[i] != k]
        w = logistic([X[i] for i in tr], [y[i] for i in tr])
        cv_ok += sum(1 for i in range(len(rows)) if folds[i] == k and (sum(a * b for a, b in zip(X[i], w)) > 0) == bool(y[i]))
    boots = []
    for _ in range(B):
        idx = [rng.randrange(len(rows)) for _ in rows]
        if len({y[i] for i in idx}) < 2:
            continue
        try:
            boots.append(logistic([X[i] for i in idx], [y[i] for i in idx], iters=30))
        except ValueError:
            pass
    curves = []
    for name, kpa, tol in (("about 7.35 psi (Moon base pressure range)", 50.67, 6), ("about 1 atm", 101.3, 8)):
        nearq = [q for q in rows if abs(q["kpa"] - kpa) <= tol]
        if len(nearq) < 5:
            continue
        near = [q["o2"] for q in nearq]
        lo, hi = min(near), max(near)
        xf = sorted(q["xf"] for q in nearq)[len(nearq) // 2]
        pts = []
        for i in range(25):
            g = lo + (hi - lo) * i / 24
            x = [1, g, math.log(kpa), math.log(xf)]
            f = lambda w: 1 / (1 + math.exp(-max(-30, min(30, sum(a * b for a, b in zip(x, w))))))
            preds = [f(w) for w in boots]
            pts.append({"o2": round(g, 4), "fit": round(f(coef), 4), "lo": round(pct(preds, .05), 4), "hi": round(pct(preds, .95), 4)})
        curves.append({"pressure": name, "kpa": kpa, "fuel_fraction": xf, "rows_near": len(near), "curve": pts})
    correct = sum(1 for x, yy in zip(X, y) if (sum(a * b for a, b in zip(x, coef)) > 0) == bool(yy))
    return {"id": "cfig-hot-ignition", "psi": "PSI-159", "title": "CFI-G: chance of hot-flame ignition against oxygen",
            "outcome": "Hot flame ignited (Yes/No), normal flames", "method": "Logistic regression: ignition ~ O₂ + log pressure + log fuel fraction. 90% bootstrap band, 1,000 resamples; 5-fold cross-validated accuracy.",
            "n": len(rows), "ignited": sum(y), "moon_rows": sum(q["moon"] for q in rows), "in_sample_accuracy": round(correct / len(rows), 3), "cv_accuracy": round(cv_ok / len(rows), 3), "base_rate": round(sum(y) / len(y), 3),
            "coef": {"o2": round(coef[1], 3), "log_pressure": round(coef[2], 3), "log_fuel_fraction": round(coef[3], 3)},
            "label": LABEL, "curves": curves,
            "points": [{"run": q["run"], "label": q["label"], "o2": q["o2"], "kpa": q["kpa"], "y": q["y"], "moon": q["moon"], "fuel": q["fuel"], "line": q["line"]} for q in rows]}


def main():
    runs = json.loads((DATA / "runs.json").read_text())
    models = [flex_model(runs), cfig_model(runs)]
    (DATA / "models.json").write_text(json.dumps({"models": models}, ensure_ascii=False, separators=(",", ":")))
    for m in models:
        if "fits" in m:
            for f in m["fits"]:
                print(m["id"], f["fuel"], "n", f["n"], "R2", f["r2"], "% per +0.01 O2", f["o2_effect_pct_per_0_01"], "range", f["o2_range_at_1_atm"])
        else:
            print(m["id"], "n", m["n"], "base", m["base_rate"], "acc", m["in_sample_accuracy"], "cv", m["cv_accuracy"], m["coef"], [(c["pressure"], c["rows_near"], c["curve"][0]["o2"], c["curve"][-1]["o2"]) for c in m["curves"]])


if __name__ == "__main__":
    main()
