"""
Core MILP model builder for one pipeline zone.

Decision variables:
  d[i][j]  — start time of task i on pipeline j  (continuous, >= 0)
  y[i][j]  — reinforced team for task i on pipe j (binary: 0=normal, 1=reinforced)
  Cmax     — makespan of the zone

Effective duration:
  normal:     DUR[i][j]
  reinforced: DUR[i][j] * ALPHA[i]
  → linear:   DUR[i][j] - DUR[i][j] * (1 - ALPHA[i]) * y[i][j]

Cost of task (i, j):
  normal:     COUT[i][j] * DUR[i][j]
  reinforced: COUT[i][j] * DUR[i][j] * ALPHA[i] * BETA[i]
  → linear:   cout_base + (ALPHA[i]*BETA[i] - 1) * cout_base * y[i][j]
"""

import pulp

from data.problem_data import (
    PIPES, TACHES, N_ZONES,
    DUR, LAG, COUT, COUT_FINAL, DUR_FINAL,
    ALPHA, BETA,
)
from solver.conflicts import CONFLITS


def build_model(name: str = "RCPSP"):
    """
    Build and return the PuLP MILP model for one zone.
    Returns: (model, d, y, Cmax, effective_duration_fn)
    """
    model = pulp.LpProblem(name, pulp.LpMinimize)

    # ── Decision variables ────────────────────────────────────────────────
    d = {i: {j: pulp.LpVariable(f"d_{i}_{j}", lowBound=0, cat="Continuous")
             for j in PIPES} for i in TACHES}

    y = {i: {j: pulp.LpVariable(f"y_{i}_{j}", cat="Binary")
             for j in PIPES} for i in TACHES}

    Cmax = pulp.LpVariable("Cmax", lowBound=0, cat="Continuous")

    def eff_dur(i, j):
        """Effective duration as a linear expression in y[i][j]."""
        reduction = DUR[i][j] * (1 - ALPHA[i])
        return DUR[i][j] - reduction * y[i][j]

    # ── Constraint 1 — Cmax definition ───────────────────────────────────
    for j in PIPES:
        model += (
            Cmax >= d[11][j] + eff_dur(11, j),
            f"cmax_pipe{j}",
        )

    # ── Constraint 2 — Precedence (start-to-start with lag) ──────────────
    for i in TACHES[:-1]:
        for j in PIPES:
            model += (
                d[i + 1][j] >= d[i][j] + LAG[i][j],
                f"prec_t{i}_t{i+1}_p{j}",
            )

    # ── Constraint 3 — Inter-pipeline sequencing (same task) ─────────────
    for i in TACHES:
        for j in PIPES[:-1]:
            model += (
                d[i][j + 1] >= d[i][j] + eff_dur(i, j),
                f"seq_t{i}_p{j}_p{j+1}",
            )

    # ── Constraint 4 — Resource conflicts ────────────────────────────────
    # Task waiting must start after the blocking task finishes on pipe 3
    for resource_name, conflict_list in CONFLITS.items():
        for (task_waiting, task_blocking) in conflict_list:
            model += (
                d[task_waiting][1] >= d[task_blocking][3] + eff_dur(task_blocking, 3),
                f"res_{resource_name}_t{task_waiting}_after_t{task_blocking}",
            )

    return model, d, y, Cmax, eff_dur


def build_cost_expression(y):
    """
    Return (zone_cost_expr, fixed_final_cost).
    zone_cost_expr is a linear PuLP expression for one zone.
    Multiply by N_ZONES and add fixed_final_cost for total project cost.
    """
    zone_cost = pulp.lpSum(0)
    for i in TACHES:
        for j in PIPES:
            base = COUT[i][j] * DUR[i][j]
            delta = base * (ALPHA[i] * BETA[i] - 1)
            zone_cost += base + delta * y[i][j]

    fixed = sum(COUT_FINAL[t] * DUR_FINAL[t] for t in [12, 13])
    return zone_cost, fixed


def read_binary(var) -> int:
    """Safely read a binary PuLP variable (handles None from solver)."""
    val = pulp.value(var)
    return int(round(val)) if val is not None else 0


def extract_solution(d, y, Cmax, model_name: str) -> dict:
    """
    Extract a solved model's schedule into a JSON-serializable dict.
    Call only after model.solve().
    """
    cmax_zone = pulp.value(Cmax)
    cmax_total = cmax_zone * N_ZONES + DUR_FINAL[12] + DUR_FINAL[13]

    modes = {i: {j: read_binary(y[i][j]) for j in PIPES} for i in TACHES}
    starts = {i: {j: pulp.value(d[i][j]) for j in PIPES} for i in TACHES}

    zone_cost = sum(
        COUT[i][j] * DUR[i][j] * ALPHA[i] * BETA[i] if modes[i][j] == 1
        else COUT[i][j] * DUR[i][j]
        for i in TACHES for j in PIPES
    )
    total_cost = zone_cost * N_ZONES + sum(COUT_FINAL[t] * DUR_FINAL[t] for t in [12, 13])

    reinforced_count = sum(modes[i][j] for i in TACHES for j in PIPES)

    return {
        "model":             model_name,
        "status":            "optimal",
        "cmax_zone_h":       round(cmax_zone, 1),
        "cmax_total_h":      round(cmax_total, 1),
        "cmax_total_days":   round(cmax_total / 24, 1),
        "total_cost_da":     round(total_cost),
        "reinforced_count":  reinforced_count,
        "modes":             modes,
        "starts":            starts,
        "n_zones":           N_ZONES,
    }