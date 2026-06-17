"""
Pareto front via ε-constraint — fully dynamic, accepts any cfg dict.
"""

import numpy as np
import pulp

from solver.model import build_model, build_cost_expression, read_binary, extract_solution


def solve_f1(cfg: dict):
    """Minimize makespan. Returns extracted solution dict or None."""
    model, d, y, Cmax, _ = build_model(cfg, "F1_Makespan")
    model += Cmax, "Obj_Makespan"
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[model.status] != "Optimal":
        return None
    return extract_solution(cfg, d, y, Cmax, "F1_Makespan")


def solve_f2(cfg: dict):
    """Minimize cost. Returns extracted solution dict or None."""
    model, d, y, Cmax, _ = build_model(cfg, "F2_Cost")
    cost_expr, fixed = build_cost_expression(cfg, y)
    model += cost_expr * cfg["N_ZONES"] + fixed, "Obj_Cost"
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[model.status] != "Optimal":
        return None
    return extract_solution(cfg, d, y, Cmax, "F2_Cost")


def solve_pareto(cfg: dict, n_points: int = 12) -> dict:
    """
    ε-constraint sweep between F1* and F2*.
    Returns Pareto points + F1/F2 anchors.
    """
    TACHES    = cfg["TACHES"]
    PIPES     = cfg["PIPES"]
    N_ZONES   = cfg["N_ZONES"]
    DUR_FINAL = cfg["DUR_FINAL"]

    f1 = solve_f1(cfg)
    f2 = solve_f2(cfg)

    if not f1 or not f2:
        return {"status": "error", "message": "Could not solve F1 or F2.", "pareto_points": []}

    eps_min = f1["cmax_zone_h"]
    eps_max = f2["cmax_zone_h"]
    epsilons = np.linspace(eps_min, eps_max, n_points)
    final_dur = sum(DUR_FINAL.values())

    pareto_points = []

    for eps in epsilons:
        model, d, y, Cmax, _ = build_model(cfg, f"eps_{eps:.0f}")
        cost_expr, fixed = build_cost_expression(cfg, y)
        total_cost_expr = cost_expr * N_ZONES + fixed

        model += Cmax <= eps,        "epsilon_constraint"
        model += total_cost_expr,    "Obj_Cost"
        model.solve(pulp.PULP_CBC_CMD(msg=0))

        if pulp.LpStatus[model.status] != "Optimal":
            continue

        cmax_zone  = pulp.value(Cmax)
        cmax_total = cmax_zone * N_ZONES + final_dur
        cost       = pulp.value(total_cost_expr)
        modes      = {i: {j: read_binary(y[i][j]) for j in PIPES} for i in TACHES}
        starts     = {i: {j: pulp.value(d[i][j]) for j in PIPES} for i in TACHES}
        n_renf     = sum(modes[i][j] for i in TACHES for j in PIPES)
        NOM_TACHE  = cfg.get("NOM_TACHE", {})
        NOM_PIPE   = cfg.get("NOM_PIPE", {})
        reinforced_tasks = [
            {
                "task_id":   i,
                "task_name": NOM_TACHE.get(i, f"Tache {i}"),
                "pipes":     [NOM_PIPE.get(j, f"Pipe {j}") for j in PIPES if modes[i][j] == 1],
            }
            for i in TACHES
            if any(modes[i][j] == 1 for j in PIPES)
        ]

        pareto_points.append({
            "epsilon":          round(eps, 1),
            "cmax_zone_h":      round(cmax_zone, 1),
            "cmax_total_h":     round(cmax_total, 1),
            "cmax_total_days":  round(cmax_total / 24, 1),
            "total_cost_da":    round(cost),
            "reinforced_count": n_renf,
            "reinforced_tasks": reinforced_tasks,
            "modes":            modes,
            "starts":           starts,
        })

    return {
        "status":        "ok",
        "message":       f"{len(pareto_points)} Pareto points found.",
        "f1":            f1,
        "f2":            f2,
        "pareto_points": pareto_points,
        "n_requested":   n_points,
    }
