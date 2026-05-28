"""
Weighted aggregation (scalarisation) method.

Objective:  minimize  λ * F2_norm + (1 - λ) * F1_norm

Where:
  F1_norm = (total_duration - TEMPS_MIN) / (TEMPS_MAX - TEMPS_MIN)
  F2_norm = (total_cost     - COUT_MIN ) / (COUT_MAX  - COUT_MIN )

TEMPS_MIN / COUT_MIN come from F1* / F2* optimal solutions.
TEMPS_MAX / COUT_MAX come from F2* / F1* (worst case for each objective).
"""

import numpy as np
import pulp

from data.problem_data import PIPES, TACHES, N_ZONES, DUR_FINAL
from solver.model import build_model, build_cost_expression, read_binary


def solve_weighted(
    temps_min: float,
    temps_max: float,
    cout_min: float,
    cout_max: float,
    n_lambdas: int = 15,
) -> dict:
    """
    Run the weighted aggregation sweep for n_lambdas values of λ in [0, 1].

    Returns:
      {
        "status": "ok",
        "results": [
          { lambda, cmax_total_h, cmax_total_days, total_cost_da,
            duration_norm, cost_norm, reinforced_count, status },
          ...
        ],
        "unique_solutions": [ same fields, deduplicated ],
        "n_lambdas":  n_lambdas,
      }
    """
    lambda_values = np.linspace(0, 1, n_lambdas)
    taches_finales_dur = DUR_FINAL[12] + DUR_FINAL[13]

    raw_results = []

    for lam in lambda_values:
        model, d, y, Cmax, _ = build_model(f"WS_lam_{lam:.2f}")
        cost_expr, fixed = build_cost_expression(y)

        total_cost_expr = cost_expr * N_ZONES + fixed
        total_time_expr = Cmax * N_ZONES + taches_finales_dur

        # Normalised objectives — avoid division by zero
        denom_t = (temps_max - temps_min) or 1
        denom_c = (cout_max  - cout_min)  or 1

        f1_norm = (total_time_expr - temps_min) / denom_t
        f2_norm = (total_cost_expr - cout_min)  / denom_c

        obj = lam * f2_norm + (1 - lam) * f1_norm
        model += obj, f"Obj_WS_lam_{lam:.2f}"

        model.solve(pulp.PULP_CBC_CMD(msg=0))
        status = pulp.LpStatus[model.status]

        if status != "Optimal":
            raw_results.append({
                "lambda":          round(float(lam), 4),
                "status":          status,
                "cmax_total_h":    None,
                "cmax_total_days": None,
                "total_cost_da":   None,
                "duration_norm":   None,
                "cost_norm":       None,
                "reinforced_count": None,
            })
            continue

        cmax_zone  = pulp.value(Cmax)
        cmax_total = cmax_zone * N_ZONES + taches_finales_dur
        cost_total = pulp.value(total_cost_expr)
        n_renf     = sum(read_binary(y[i][j]) for i in TACHES for j in PIPES)

        dur_norm  = (cmax_total - temps_min) / denom_t
        cost_norm = (cost_total - cout_min)  / denom_c

        raw_results.append({
            "lambda":           round(float(lam), 4),
            "status":           "optimal",
            "cmax_total_h":     round(cmax_total, 1),
            "cmax_total_days":  round(cmax_total / 24, 1),
            "total_cost_da":    round(cost_total),
            "duration_norm":    round(dur_norm, 4),
            "cost_norm":        round(cost_norm, 4),
            "reinforced_count": n_renf,
        })

    # Deduplicate by (rounded duration, rounded cost)
    seen = {}
    for r in raw_results:
        if r["cmax_total_h"] is None:
            continue
        key = (round(r["cmax_total_h"], 1), round(r["total_cost_da"], -2))
        if key not in seen:
            seen[key] = {**r, "lambda_values": [r["lambda"]]}
        else:
            seen[key]["lambda_values"].append(r["lambda"])

    unique = sorted(seen.values(), key=lambda x: x["cmax_total_h"])

    return {
        "status":           "ok",
        "n_lambdas":        n_lambdas,
        "results":          raw_results,
        "unique_solutions": unique,
    }