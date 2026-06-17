"""
Weighted aggregation (scalarisation) — matches notebook cells 22–23 exactly.

Key rules from notebook:
  - TEMPS_MIN = cmax_total_f1  (duration of makespan-optimal solution)
  - TEMPS_MAX = cmax_total_f2  (duration of cost-optimal solution)
  - COUT_MIN  = cout_total_f2  (cost of cost-optimal solution)
  - COUT_MAX  = cout_total_f1  (cost of makespan-optimal solution)

  - taches_finales_duree = DUR_FINAL[12] + DUR_FINAL[13]
    (used consistently in both bounds and objective expression)

  - expr_temps_total = Cmax * N_ZONES + taches_finales_duree
  - expr_cout_total  = cost_zone * N_ZONES + cout_fixe

  - F1_norm = (temps_total - TEMPS_MIN) / (TEMPS_MAX - TEMPS_MIN)
  - F2_norm = (cout_total  - COUT_MIN)  / (COUT_MAX  - COUT_MIN)
  - obj      = lambda * F2_norm + (1 - lambda) * F1_norm

  - cost is extracted by recomputing from modes (not from pulp expression value)
    to match exactly how notebook computes cout_total
"""

import numpy as np
import pulp

from solver.model import build_model, build_cost_expression, read_binary


def solve_weighted(cfg: dict, temps_min: float, temps_max: float,
                   cout_min: float, cout_max: float, n_lambdas: int = 15) -> dict:
    """
    Sweep λ ∈ [0,1] and minimize: λ*F2_norm + (1-λ)*F1_norm

    temps_min = cmax_total_f1  (from solve_f1)
    temps_max = cmax_total_f2  (from solve_f2)
    cout_min  = cout_total_f2  (from solve_f2)
    cout_max  = cout_total_f1  (from solve_f1)
    """
    TACHES     = cfg["TACHES"]
    PIPES      = cfg["PIPES"]
    N_ZONES    = cfg["N_ZONES"]
    DUR        = cfg["DUR"]
    DUR_FINAL  = cfg["DUR_FINAL"]
    COUT       = cfg["COUT"]
    COUT_FINAL = cfg["COUT_FINAL"]
    ALPHA      = cfg["ALPHA"]
    BETA       = cfg["BETA"]

    # Notebook cell 23: taches_finales_duree = DUR_FINAL[12] + DUR_FINAL[13]
    # This is used consistently in the objective expression AND in bound calculation
    taches_finales_duree = DUR_FINAL.get(12, 0) + DUR_FINAL.get(13, 0)

    denom_t = max(temps_max - temps_min, 1e-6)
    denom_c = max(cout_max  - cout_min,  1e-6)

    lambda_values = np.linspace(0, 1, n_lambdas)
    raw_results   = []

    for lam in lambda_values:
        model, d, y, Cmax, _ = build_model(cfg, f"WS_lam_{lam:.4f}")
        cost_expr, cost_fixe = build_cost_expression(cfg, y)

        # Total time and cost expressions — matches notebook cell 23 exactly
        expr_cout_total  = cost_expr * N_ZONES + cost_fixe
        expr_temps_total = Cmax * N_ZONES + taches_finales_duree

        # Normalized objectives
        expr_f1_norm = (expr_temps_total - temps_min) / denom_t
        expr_f2_norm = (expr_cout_total  - cout_min)  / denom_c

        # Weighted objective
        obj = lam * expr_f2_norm + (1 - lam) * expr_f1_norm
        model += obj, f"Obj_WS_{lam:.4f}"

        model.solve(pulp.PULP_CBC_CMD(msg=0))
        status = pulp.LpStatus[model.status]

        if status != "Optimal":
            raw_results.append({
                "lambda":           round(float(lam), 4),
                "status":           status,
                "cmax_total_h":     None,
                "cmax_total_days":  None,
                "total_cost_da":    None,
                "duration_norm":    None,
                "cost_norm":        None,
                "reinforced_count": None,
            })
            continue

        # Extract solution — matches notebook cell 23 exactly
        temps_total = pulp.value(expr_temps_total)

        modes = {i: {j: read_binary(y[i][j]) for j in PIPES} for i in TACHES}

        # Recompute cost from modes (matches notebook: cout_zone_ws + sum(COUT_FINAL))
        cout_zone = sum(
            COUT[i][j] * DUR[i][j] * ALPHA[i] * BETA[i] if modes[i][j] == 1
            else COUT[i][j] * DUR[i][j]
            for i in TACHES for j in PIPES
        )
        cout_total = cout_zone * N_ZONES + sum(
            COUT_FINAL[t] * DUR_FINAL[t] for t in DUR_FINAL
        )

        temps_norm = (temps_total - temps_min) / denom_t
        cout_norm  = (cout_total  - cout_min)  / denom_c
        nb_renf   = sum(modes[i][j] for i in TACHES for j in PIPES)
        NOM_TACHE = cfg.get("NOM_TACHE", {})
        NOM_PIPE  = cfg.get("NOM_PIPE", {})
        reinforced_tasks = [
            {
                "task_id":   i,
                "task_name": NOM_TACHE.get(i, f"Tache {i}"),
                "pipes":     [NOM_PIPE.get(j, f"Pipe {j}") for j in PIPES if modes[i][j] == 1],
            }
            for i in TACHES
            if any(modes[i][j] == 1 for j in PIPES)
        ]

        raw_results.append({
            "lambda":            round(float(lam), 4),
            "status":            "optimal",
            "cmax_total_h":      round(temps_total, 1),
            "cmax_total_days":   round(temps_total / 24, 1),
            "total_cost_da":     round(cout_total),
            "duration_norm":     round(temps_norm, 4),
            "cost_norm":         round(cout_norm,  4),
            "reinforced_count":  nb_renf,
            "reinforced_tasks":  reinforced_tasks,
            "modes":             modes,
            "starts":            starts,
        })

    # Deduplicate — matches notebook cell 24 exactly
    # key = (round(temps_total, 1), round(cout_total, 0))
    ws_uniques = {}
    for r in raw_results:
        if r["cmax_total_h"] is None:
            continue
        key = (round(r["cmax_total_h"], 1), round(r["total_cost_da"], 0))
        if key not in ws_uniques:
            ws_uniques[key] = {**r, "lambda_values": [r["lambda"]]}
        else:
            ws_uniques[key]["lambda_values"].append(r["lambda"])

    unique = sorted(ws_uniques.values(), key=lambda x: x["cmax_total_h"])

    return {
        "status":           "ok",
        "n_lambdas":        n_lambdas,
        "results":          raw_results,
        "unique_solutions": unique,
    }