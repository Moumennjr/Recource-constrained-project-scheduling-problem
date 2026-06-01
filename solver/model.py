"""
Core MILP model builder — fully dynamic, works with any ProblemConfig.

All parameters come from cfg = ProblemConfig.to_solver_format().
No global imports from problem_data.py.

Decision variables:
  d[i][j]  start time of task i on pipe j   (continuous, >= 0)
  y[i][j]  reinforced team flag             (binary: 0=normal, 1=reinforced)
  Cmax     makespan of one zone             (continuous, >= 0)

Constraints:
  1. Cmax definition       — Cmax >= finish of last task on each pipe
  2. Precedence (SS + lag) — d[next][j] >= d[i][j] + LAG[i][j]
  3. Inter-pipe sequencing — d[i][j+1] >= d[i][j] + eff_dur(i, j)
  4. Resource conflicts    — detected dynamically from cfg["RESSOURCES"]
"""

import pulp
from solver.conflicts import detect_conflicts


def build_model(cfg: dict, name: str = "RCPSP"):
    """
    Build and return the PuLP MILP model for one zone.
    Returns: (model, d, y, Cmax, eff_dur_fn)
    """
    PIPES  = cfg["PIPES"]
    TACHES = cfg["TACHES"]
    DUR    = cfg["DUR"]
    LAG    = cfg["LAG"]
    ALPHA  = cfg["ALPHA"]

    CONFLITS = detect_conflicts(cfg["RESSOURCES"])

    model = pulp.LpProblem(name, pulp.LpMinimize)

    # ── Variables ─────────────────────────────────────────────────────────
    d = {
        i: {j: pulp.LpVariable(f"d_{i}_{j}", lowBound=0, cat="Continuous")
            for j in PIPES}
        for i in TACHES
    }
    y = {
        i: {j: pulp.LpVariable(f"y_{i}_{j}", cat="Binary")
            for j in PIPES}
        for i in TACHES
    }
    Cmax = pulp.LpVariable("Cmax", lowBound=0, cat="Continuous")

    def eff_dur(i, j):
        """Linear expression for effective duration of task i on pipe j."""
        reduction = DUR[i][j] * (1 - ALPHA[i])
        return DUR[i][j] - reduction * y[i][j]

    last_task = TACHES[-1]

    # ── Constraint 1 — Cmax definition ───────────────────────────────────
    for j in PIPES:
        model += (
            Cmax >= d[last_task][j] + eff_dur(last_task, j),
            f"cmax_pipe{j}",
        )

    # ── Constraint 2 — Precedence (index-based, handles any task ID sequence) ──
    for idx in range(len(TACHES) - 1):
        i      = TACHES[idx]
        i_next = TACHES[idx + 1]
        lag_i  = LAG.get(i, {})
        for j in PIPES:
            lag_val = lag_i.get(j, 0)
            model += (
                d[i_next][j] >= d[i][j] + lag_val,
                f"prec_t{i}_t{i_next}_p{j}",
            )

    # ── Constraint 3 — Inter-pipeline sequencing ──────────────────────────
    for i in TACHES:
        for idx_j in range(len(PIPES) - 1):
            j      = PIPES[idx_j]
            j_next = PIPES[idx_j + 1]
            model += (
                d[i][j_next] >= d[i][j] + eff_dur(i, j),
                f"seq_t{i}_p{j}_p{j_next}",
            )

    # ── Constraint 4 — Resource conflicts ────────────────────────────────
    for resource_name, conflict_list in CONFLITS.items():
        for (task_waiting, task_blocking) in conflict_list:
            last_pipe = PIPES[-1]
            model += (
                d[task_waiting][PIPES[0]] >= d[task_blocking][last_pipe] + eff_dur(task_blocking, last_pipe),
                f"res_{resource_name}_t{task_waiting}_after_t{task_blocking}",
            )

    return model, d, y, Cmax, eff_dur


def build_cost_expression(cfg: dict, y: dict):
    """
    Return (zone_cost_expr, fixed_final_cost).
    zone_cost_expr — linear PuLP expression for cost of ONE zone.
    Multiply by N_ZONES and add fixed_final_cost for total project cost.
    """
    TACHES     = cfg["TACHES"]
    PIPES      = cfg["PIPES"]
    DUR        = cfg["DUR"]
    COUT       = cfg["COUT"]
    ALPHA      = cfg["ALPHA"]
    BETA       = cfg["BETA"]
    DUR_FINAL  = cfg["DUR_FINAL"]
    COUT_FINAL = cfg["COUT_FINAL"]

    zone_cost = pulp.lpSum(0)
    for i in TACHES:
        for j in PIPES:
            base  = COUT[i][j] * DUR[i][j]
            delta = base * (ALPHA[i] * BETA[i] - 1)
            zone_cost += base + delta * y[i][j]

    fixed = sum(COUT_FINAL[t] * DUR_FINAL[t] for t in DUR_FINAL)
    return zone_cost, fixed


def read_binary(var) -> int:
    """Safely read a binary PuLP variable (handles None)."""
    val = pulp.value(var)
    return int(round(val)) if val is not None else 0


def extract_solution(cfg: dict, d: dict, y: dict, Cmax, model_name: str) -> dict:
    """
    Extract a solved model into a JSON-serializable dict.
    Call only after model.solve() returns Optimal.
    """
    TACHES     = cfg["TACHES"]
    PIPES      = cfg["PIPES"]
    N_ZONES    = cfg["N_ZONES"]
    DUR        = cfg["DUR"]
    COUT       = cfg["COUT"]
    ALPHA      = cfg["ALPHA"]
    BETA       = cfg["BETA"]
    DUR_FINAL  = cfg["DUR_FINAL"]
    COUT_FINAL = cfg["COUT_FINAL"]

    cmax_zone  = pulp.value(Cmax)
    cmax_total = cmax_zone * N_ZONES + sum(DUR_FINAL.values())

    modes  = {i: {j: read_binary(y[i][j]) for j in PIPES} for i in TACHES}
    starts = {i: {j: pulp.value(d[i][j])  for j in PIPES} for i in TACHES}

    zone_cost = sum(
        COUT[i][j] * DUR[i][j] * ALPHA[i] * BETA[i] if modes[i][j] == 1
        else COUT[i][j] * DUR[i][j]
        for i in TACHES for j in PIPES
    )
    total_cost = zone_cost * N_ZONES + sum(COUT_FINAL[t] * DUR_FINAL[t] for t in DUR_FINAL)

    return {
        "model":            model_name,
        "status":           "optimal",
        "cmax_zone_h":      round(cmax_zone, 1),
        "cmax_total_h":     round(cmax_total, 1),
        "cmax_total_days":  round(cmax_total / 24, 1),
        "total_cost_da":    round(total_cost),
        "reinforced_count": sum(modes[i][j] for i in TACHES for j in PIPES),
        "modes":            modes,
        "starts":           starts,
        "n_zones":          N_ZONES,
    }
