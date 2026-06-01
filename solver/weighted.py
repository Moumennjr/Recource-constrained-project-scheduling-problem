"""
Weighted aggregation (scalarisation) — fully dynamic, accepts any cfg dict.
"""

import numpy as np
import pulp

from solver.model import build_model, build_cost_expression, read_binary


def solve_weighted(cfg: dict, temps_min: float, temps_max: float,
                   cout_min: float, cout_max: float, n_lambdas: int = 15) -> dict:
    """
    Sweep λ in [0, 1] and minimize:  λ * F2_norm + (1-λ) * F1_norm

    Returns raw results + deduplicated unique solutions.
    """
    TACHES    = cfg["TACHES"]
    PIPES     = cfg["PIPES"]
    N_ZONES   = cfg["N_ZONES"]
    DUR_FINAL = cfg["DUR_FINAL"]

    lambda_values  = np.linspace(0, 1, n_lambdas)
    final_dur      = sum(DUR_FINAL.values())
    denom_t        = max(temps_max - temps_min, 1)
    denom_c        = max(cout_max  - cout_min,  1)

    raw_results = []

    for lam in lambda_values:
        model, d, y, Cmax, _ = build_model(cfg, f"WS_lam_{lam:.2f}")
        cost_expr, fixed = build_cost_expression(cfg, y)

        total_cost_expr = cost_expr * N_ZONES + fixed
        total_time_expr = Cmax * N_ZONES + final_dur

        f1_norm = (total_time_expr - temps_min) / denom_t
        f2_norm = (total_cost_expr - cout_min)  / denom_c
        obj     = lam * f2_norm + (1 - lam) * f1_norm

        model += obj, f"Obj_WS_lam_{lam:.2f}"
        model.solve(pulp.PULP_CBC_CMD(msg=0))
        status = pulp.LpStatus[model.status]

        if status != "Optimal":
            raw_results.append({
                "lambda": round(float(lam), 4),
                "status": status,
                "cmax_total_h":    None,
                "cmax_total_days": None,
                "total_cost_da":   None,
                "duration_norm":   None,
                "cost_norm":       None,
                "reinforced_count": None,
            })
            continue

        cmax_zone  = pulp.value(Cmax)
        cmax_total = cmax_zone * N_ZONES + final_dur
        cost_total = pulp.value(total_cost_expr)
        
        # Handle None cost_total from solver
        if cost_total is None:
            cost_total = 0.0
        
        n_renf     = sum(read_binary(y[i][j]) for i in TACHES for j in PIPES)

        raw_results.append({
            "lambda":           round(float(lam), 4),
            "status":           "optimal",
            "cmax_total_h":     round(cmax_total, 1),
            "cmax_total_days":  round(cmax_total / 24, 1),
            "total_cost_da":    round(cost_total),
            "duration_norm":    round((cmax_total - temps_min) / denom_t, 4),
            "cost_norm":        round((cost_total  - cout_min)  / denom_c, 4),
            "reinforced_count": n_renf,
        })

    # Deduplicate
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
