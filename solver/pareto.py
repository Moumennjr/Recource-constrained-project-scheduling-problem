"""
Pareto front via the ε-constraint method.

Algorithm:
  1. Solve F1* = min Cmax  (ignoring cost)
  2. Solve F2* = min Cost  (ignoring makespan)
  3. Sweep ε from F1* to F2*:
       minimize Cost  subject to  Cmax_zone <= ε
  4. Collect non-dominated solutions.
"""

import numpy as np
import pulp

from data.problem_data import PIPES, TACHES, N_ZONES, DUR_FINAL
from solver.model import build_model, build_cost_expression, read_binary, extract_solution


def solve_f1():
    """Minimize makespan (ignoring cost). Returns extracted solution dict."""
    model, d, y, Cmax, _ = build_model("F1_Makespan")
    model += Cmax, "Obj_Makespan"
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[model.status] != "Optimal":
        return None
    return extract_solution(d, y, Cmax, "F1_Makespan")


def solve_f2():
    """Minimize cost (ignoring makespan). Returns extracted solution dict."""
    model, d, y, Cmax, _ = build_model("F2_Cost")
    cost_expr, fixed = build_cost_expression(y)
    total_cost = cost_expr * N_ZONES + fixed
    model += total_cost, "Obj_Cost"
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[model.status] != "Optimal":
        return None
    return extract_solution(d, y, Cmax, "F2_Cost")


def solve_pareto(n_points: int = 12) -> dict:
    """
    Run the full ε-constraint sweep and return Pareto results.

    Returns:
      {
        "f1": { ...solution dict... },
        "f2": { ...solution dict... },
        "pareto_points": [
          { epsilon, cmax_zone_h, cmax_total_h, cmax_total_days,
            total_cost_da, reinforced_count },
          ...
        ],
        "status": "ok" | "error",
        "message": "..."
      }
    """
    f1 = solve_f1()
    f2 = solve_f2()

    if f1 is None or f2 is None:
        return {"status": "error", "message": "Could not solve F1 or F2.", "pareto_points": []}

    eps_min = f1["cmax_zone_h"]
    eps_max = f2["cmax_zone_h"]

    epsilons = np.linspace(eps_min, eps_max, n_points)
    taches_finales_dur = DUR_FINAL[12] + DUR_FINAL[13]

    pareto_points = []

    for eps in epsilons:
        model, d, y, Cmax, _ = build_model(f"eps_{eps:.0f}")
        cost_expr, fixed = build_cost_expression(y)
        total_cost_expr = cost_expr * N_ZONES + fixed

        model += Cmax <= eps,           "epsilon_constraint"
        model += total_cost_expr,       "Obj_Cost"

        model.solve(pulp.PULP_CBC_CMD(msg=0))

        if pulp.LpStatus[model.status] != "Optimal":
            continue

        cmax_zone  = pulp.value(Cmax)
        cmax_total = cmax_zone * N_ZONES + taches_finales_dur
        cost       = pulp.value(total_cost_expr)
        n_renf     = sum(
            read_binary(y[i][j]) for i in TACHES for j in [1, 2, 3]
        )

        pareto_points.append({
            "epsilon":         round(eps, 1),
            "cmax_zone_h":     round(cmax_zone, 1),
            "cmax_total_h":    round(cmax_total, 1),
            "cmax_total_days": round(cmax_total / 24, 1),
            "total_cost_da":   round(cost),
            "reinforced_count": n_renf,
        })

    return {
        "status":        "ok",
        "message":       f"{len(pareto_points)} Pareto points found.",
        "f1":            f1,
        "f2":            f2,
        "pareto_points": pareto_points,
        "n_requested":   n_points,
    }