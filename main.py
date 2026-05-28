"""
RCPSP Optimization Dashboard — FastAPI Backend
Run with:  uvicorn main:app --reload --port 8000
"""

import pulp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from data.problem_data import (
    PIPES, TACHES, N_ZONES,
    NOM_TACHE, NOM_PIPE,
    DUR, DUR_FINAL, COUT, COUT_FINAL,
    ALPHA, BETA, RESSOURCES,
)
from solver.conflicts import get_conflicts_summary, CONFLITS
from solver.model import build_model, build_cost_expression, extract_solution
from solver.gantt import build_gantt, build_gantt_summary
from solver.pareto import solve_pareto, solve_f1, solve_f2
from solver.weighted import solve_weighted

app = FastAPI(title="RCPSP API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────

class SolveRequest(BaseModel):
    objective: str = Field("makespan", description="'makespan' or 'cost'")

class ParetoRequest(BaseModel):
    n_points: int = Field(12, ge=3, le=30)

class WeightedRequest(BaseModel):
    n_lambdas: int = Field(15, ge=3, le=30)


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/data")
def get_problem_data():
    """Return all static problem data (tasks, resources, constants)."""
    return {
        "pipes":    [{"id": j, "name": NOM_PIPE[j]} for j in PIPES],
        "tasks":    [{"id": i, "name": NOM_TACHE[i]} for i in TACHES],
        "n_zones":  N_ZONES,
        "dur":      {str(i): {str(j): DUR[i][j] for j in PIPES} for i in TACHES},
        "lag":      {str(i): {} for i in TACHES},          # available if needed
        "cout":     {str(i): {str(j): COUT[i][j] for j in PIPES} for i in TACHES},
        "alpha":    {str(i): ALPHA[i] for i in TACHES},
        "beta":     {str(i): BETA[i]  for i in TACHES},
        "dur_final":  {str(k): v for k, v in DUR_FINAL.items()},
        "cout_final": {str(k): v for k, v in COUT_FINAL.items()},
        "resources": {
            name: {
                "capacity": data["capacite"],
                "tasks":    data["taches"],
            }
            for name, data in RESSOURCES.items()
        },
    }


@app.get("/conflicts")
def get_conflicts():
    """Return detected resource conflicts and the full resource map."""
    summary = get_conflicts_summary()

    resource_list = []
    for name, data in RESSOURCES.items():
        resource_list.append({
            "name":     name,
            "capacity": data["capacite"],
            "tasks":    [
                {"task_id": t, "consumption": c, "task_name": NOM_TACHE[t]}
                for (t, c) in data["taches"]
            ],
        })

    return {
        "conflicts":  summary,
        "resources":  resource_list,
        "n_conflicts": len(summary),
    }


@app.post("/solve")
def solve(req: SolveRequest):
    """
    Solve a single-objective MILP (makespan OR cost minimisation).
    Returns the schedule + Gantt bars.
    """
    model, d, y, Cmax, _ = build_model(f"solve_{req.objective}")

    if req.objective == "makespan":
        model += Cmax, "Obj_Makespan"
    elif req.objective == "cost":
        cost_expr, fixed = build_cost_expression(y)
        model += cost_expr * N_ZONES + fixed, "Obj_Cost"
    else:
        raise HTTPException(status_code=400, detail="objective must be 'makespan' or 'cost'")

    model.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[model.status] != "Optimal":
        raise HTTPException(status_code=422, detail="Solver found no optimal solution.")

    solution = extract_solution(d, y, Cmax, req.objective)
    gantt_bars = build_gantt(solution["starts"], solution["modes"])
    gantt_summary = build_gantt_summary(gantt_bars)

    return {
        **solution,
        "gantt_bars":    gantt_bars,
        "gantt_summary": gantt_summary,
    }


@app.post("/pareto")
def pareto(req: ParetoRequest):
    """
    Build the Pareto front via ε-constraint method.
    Also returns F1* and F2* anchor solutions.
    """
    result = solve_pareto(n_points=req.n_points)

    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])

    # Attach Gantt bars for both anchor solutions
    f1 = result["f1"]
    f2 = result["f2"]
    result["f1"]["gantt_bars"] = build_gantt(f1["starts"], f1["modes"])
    result["f2"]["gantt_bars"] = build_gantt(f2["starts"], f2["modes"])

    return result


@app.post("/weighted")
def weighted(req: WeightedRequest):
    """
    Run the weighted aggregation sweep for n_lambdas values of λ.
    Requires F1* and F2* bounds — computes them automatically.
    """
    f1 = solve_f1()
    f2 = solve_f2()

    if f1 is None or f2 is None:
        raise HTTPException(status_code=422, detail="Could not determine F1*/F2* bounds.")

    temps_min = f1["cmax_total_h"]
    temps_max = f2["cmax_total_h"]
    cout_min  = f2["total_cost_da"]
    cout_max  = f1["total_cost_da"]

    result = solve_weighted(
        temps_min=temps_min,
        temps_max=temps_max,
        cout_min=cout_min,
        cout_max=cout_max,
        n_lambdas=req.n_lambdas,
    )

    return {
        **result,
        "bounds": {
            "temps_min": temps_min,
            "temps_max": temps_max,
            "cout_min":  cout_min,
            "cout_max":  cout_max,
        },
        "f1": f1,
        "f2": f2,
    }