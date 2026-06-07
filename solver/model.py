"""
Core MILP model builder — fully dynamic, works with any ProblemConfig.

cmax_total formula — matches notebook cells 10 and 12 exactly:
  cmax_total = cmax_zone * N_ZONES + DUR_FINAL[12] + DUR_FINAL[13]

This is the formula used in F1*, F2*, AND the weighted aggregation bounds.
All three must be consistent or normalization breaks.

NOTE: DUR_FINAL[12] here acts as the total raccordement cost/schedule lump.
The Gantt chart uses a different formula (76h per gap) for *visual* placement,
but the optimization objective and bounds all use DUR_FINAL[12]+DUR_FINAL[13].
"""

import pulp
from solver.conflicts import detect_conflicts


def build_model(cfg: dict, name: str = "RCPSP"):
    PIPES  = cfg["PIPES"]
    TACHES = cfg["TACHES"]
    DUR    = cfg["DUR"]
    LAG    = cfg["LAG"]
    ALPHA  = cfg["ALPHA"]

    CONFLITS = detect_conflicts(cfg["RESSOURCES"])

    model = pulp.LpProblem(name, pulp.LpMinimize)

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
        reduction = DUR[i][j] * (1 - ALPHA[i])
        return DUR[i][j] - reduction * y[i][j]

    last_task = TACHES[-1]

    # Constraint 1 — Cmax definition
    for j in PIPES:
        model += (Cmax >= d[last_task][j] + eff_dur(last_task, j), f"cmax_pipe{j}")

    # Constraint 2 — Precedence
    for idx in range(len(TACHES) - 1):
        i      = TACHES[idx]
        i_next = TACHES[idx + 1]
        lag_i  = LAG.get(i, {})
        for j in PIPES:
            model += (d[i_next][j] >= d[i][j] + lag_i.get(j, 0), f"prec_t{i}_t{i_next}_p{j}")

    # Constraint 3 — Inter-pipeline sequencing
    for i in TACHES:
        for idx_j in range(len(PIPES) - 1):
            j      = PIPES[idx_j]
            j_next = PIPES[idx_j + 1]
            model += (d[i][j_next] >= d[i][j] + eff_dur(i, j), f"seq_t{i}_p{j}_p{j_next}")

    # Constraint 4 — Resource conflicts
    for resource_name, conflict_list in CONFLITS.items():
        for (task_waiting, task_blocking) in conflict_list:
            model += (
                d[task_waiting][PIPES[0]] >= d[task_blocking][PIPES[-1]] + eff_dur(task_blocking, PIPES[-1]),
                f"res_{resource_name}_t{task_waiting}_after_t{task_blocking}",
            )

    return model, d, y, Cmax, eff_dur


def build_cost_expression(cfg: dict, y: dict):
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
    val = pulp.value(var)
    return int(round(val)) if val is not None else 0


def extract_solution(cfg: dict, d: dict, y: dict, Cmax, model_name: str) -> dict:
    """
    Extract solved model to dict.

    cmax_total = cmax_zone * N_ZONES + DUR_FINAL[12] + DUR_FINAL[13]
    Matches notebook cells 10 and 12 exactly.
    This ensures F1*, F2* bounds are consistent with the weighted objective expression.
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

    cmax_zone = pulp.value(Cmax)

    # Notebook formula: cmax_total = cmax_zone * N_ZONES + DUR_FINAL[12] + DUR_FINAL[13]
    cmax_total = cmax_zone * N_ZONES + DUR_FINAL.get(12, 0) + DUR_FINAL.get(13, 0)

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