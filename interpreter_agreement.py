"""Agreement between the two EarthLabel interpreters, before adjudication.

Each plot was interpreted independently by two people (``labeler_a``,
``labeler_b``); their disagreements were then reviewed. This measures how much
the two agreed before that review, from the final plot files
``data/earthlabel/<city>_imd_2018_results_cells.csv``:

- MAE between the two, in levels (ninths) and in percentage points;
- exact agreement (same number of impervious sub-cells);
- agreement within one level (one sub-cell of nine, 11.1 pp);
- quadratic weighted kappa (QWK) on the 10 levels 0/9 .. 9/9, the formula of
  notebook 05 (``validation_metrics.level_stats``).

The plots redrawn inside the combined valid mask (``resolved_by ==
'add_points'``) were interpreted jointly; both interpreters take that plot's
final level.

Writes output/interpreter_agreement/agreement_metrics.csv (one row per city)
and agreement_by_stratum.csv.

    python interpreter_agreement.py
"""

import numpy as np
import pandas as pd

import output_paths as op
import validation_metrics as vm

CITIES = ("Milan", "Hanoi", "HCMC")


def parse_level(s):
    """'8/9' -> 8."""
    num, den = str(s).split("/")
    assert int(den) == vm.K_LEVELS, s
    return int(num)


def levels(city):
    d = pd.read_csv(op.DATA / "earthlabel" / f"{city.lower()}_imd_2018_results_cells.csv")
    ref = d["cells_json"].map(vm.reference_from_cells)
    assert (ref.map(lambda t: t[1]) == 0).all(), f"{city}: unresolved sub-cells"
    final = vm.to_levels(ref.map(lambda t: t[0]).to_numpy(float))
    joint = (d["resolved_by"] == "add_points").to_numpy()
    out = pd.DataFrame({"PLOTID": d["PLOTID"], "stratum": d["ref_label"], "final": final})
    for who, col in (("a", "imperv_level_" + d["labeler_a"].iloc[0]),
                     ("b", "imperv_level_" + d["labeler_b"].iloc[0])):
        assert d.loc[~joint, col].notna().all(), (city, col)
        lv = np.full(len(d), -1)
        lv[~joint] = d.loc[~joint, col].map(parse_level).to_numpy()
        lv[joint] = final[joint]
        out[who] = lv
    return out


def agreement(a, b):
    a, b = np.asarray(a, int), np.asarray(b, int)
    d = np.abs(a - b)
    st = vm.qwk_levels(a, b)
    return dict(n=len(a), MAE_levels=float(d.mean()), MAE_pp=float(d.mean() * 100 / vm.K_LEVELS),
                exact_agreement=float((d == 0).mean()), within_1_level=float((d <= 1).mean()),
                QWK=st["quad_weighted_kappa"])


def main():
    op.INTERPRETER.mkdir(parents=True, exist_ok=True)
    rows, by_stratum = [], []
    for city in CITIES:
        lv = levels(city)
        rows.append({"city": city, **agreement(lv["a"], lv["b"])})
        for s, g in lv.groupby("stratum"):
            by_stratum.append({"city": city, "stratum": s, **agreement(g["a"], g["b"])})
    res = pd.DataFrame(rows)
    res.to_csv(op.INTERPRETER / "agreement_metrics.csv", index=False)
    pd.DataFrame(by_stratum).to_csv(op.INTERPRETER / "agreement_by_stratum.csv", index=False)
    print(res.round(4).to_string(index=False))
    print(f"-> {op.INTERPRETER / 'agreement_metrics.csv'}")


if __name__ == "__main__":
    main()
