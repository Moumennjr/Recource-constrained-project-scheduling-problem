"""
RCPSP Optimization Dashboard — FastAPI Backend
Run with:  uvicorn main:app --reload --port 8000
"""

import pulp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from solver.config import ProblemConfig
from data.default_config import build_default_config
from solver.conflicts import get_conflicts_summary, detect_conflicts
from solver.model import build_model, build_cost_expression, extract_solution
from solver.gantt import build_gantt, build_gantt_summary
from solver.pareto import solve_pareto, solve_f1, solve_f2
from solver.weighted import solve_weighted

app = FastAPI(title="RCPSP API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── In-memory problem store (no DB needed for MVP) ────────────────────────
_problems: dict[str, ProblemConfig] = {}


@app.on_event("startup")
def _load_defaults():
    default = build_default_config()
    _problems[default.id] = default


# ── Request schemas ───────────────────────────────────────────────────────

class SolveRequest(BaseModel):
    config:    ProblemConfig
    objective: str = Field("makespan", description="'makespan' or 'cost'")

class ParetoRequest(BaseModel):
    config:   ProblemConfig
    n_points: int = Field(12, ge=3, le=30)

class WeightedRequest(BaseModel):
    config:    ProblemConfig
    n_lambdas: int = Field(15, ge=3, le=30)

class ConflictsRequest(BaseModel):
    config: ProblemConfig


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Problem CRUD (in-memory) ──────────────────────────────────────────────

@app.get("/problems")
def list_problems():
    return [
        {"id": p.id, "name": p.name, "description": p.description,
         "n_zones": p.n_zones, "n_tasks": len(p.task_ids), "n_pipes": len(p.pipes)}
        for p in _problems.values()
    ]


@app.get("/problems/default")
def get_default_problem():
    """Return the default problem config — used to bootstrap the frontend."""
    default = build_default_config()
    return default


@app.get("/problems/{problem_id}")
def get_problem(problem_id: str):
    if problem_id not in _problems:
        raise HTTPException(404, "Problem not found.")
    return _problems[problem_id]


@app.post("/problems", status_code=201)
def create_problem(config: ProblemConfig):
    _problems[config.id] = config
    return {"id": config.id, "name": config.name}


@app.put("/problems/{problem_id}")
def update_problem(problem_id: str, config: ProblemConfig):
    if problem_id not in _problems:
        raise HTTPException(404, "Problem not found.")
    config.id = problem_id          # ensure ID consistency
    _problems[problem_id] = config
    return {"id": config.id, "name": config.name}


@app.delete("/problems/{problem_id}", status_code=204)
def delete_problem(problem_id: str):
    if problem_id == "default-pipeline-rcpsp":
        raise HTTPException(400, "Cannot delete the default problem.")
    _problems.pop(problem_id, None)


# ── Conflict analysis ─────────────────────────────────────────────────────

@app.post("/conflicts")
def compute_conflicts(req: ConflictsRequest):
    cfg       = req.config.to_solver_format()
    task_names = cfg["NOM_TACHE"]
    summary   = get_conflicts_summary(cfg, task_names)

    resource_list = []
    for r in req.config.resources:
        resource_list.append({
            "name":     r.name,
            "capacity": r.capacity,
            "tasks": [
                {"task_id": t.task_id, "consumption": t.consumption,
                 "task_name": task_names.get(t.task_id, str(t.task_id))}
                for t in r.tasks
            ],
        })

    return {
        "conflicts":   summary,
        "resources":   resource_list,
        "n_conflicts": len(summary),
    }


# ── Solve — single objective ──────────────────────────────────────────────

@app.post("/solve")
def solve(req: SolveRequest):
    cfg   = req.config.to_solver_format()
    model, d, y, Cmax, _ = build_model(cfg, f"solve_{req.objective}")

    if req.objective == "makespan":
        model += Cmax, "Obj_Makespan"
    elif req.objective == "cost":
        cost_expr, fixed = build_cost_expression(cfg, y)
        model += cost_expr * cfg["N_ZONES"] + fixed, "Obj_Cost"
    else:
        raise HTTPException(400, "objective must be 'makespan' or 'cost'")

    model.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[model.status] != "Optimal":
        raise HTTPException(422, "Solver found no optimal solution.")

    solution   = extract_solution(cfg, d, y, Cmax, req.objective)
    gantt_bars = build_gantt(cfg, solution["starts"], solution["modes"])

    return {
        **solution,
        "gantt_bars":    gantt_bars,
        "gantt_summary": build_gantt_summary(gantt_bars),
        "config_id":     req.config.id,
        "config_name":   req.config.name,
    }


# ── Pareto front ──────────────────────────────────────────────────────────

@app.post("/pareto")
def pareto(req: ParetoRequest):
    cfg    = req.config.to_solver_format()
    result = solve_pareto(cfg, n_points=req.n_points)

    if result["status"] == "error":
        raise HTTPException(422, result["message"])

    # Attach Gantt bars to anchor solutions
    for key in ("f1", "f2"):
        sol = result[key]
        result[key]["gantt_bars"] = build_gantt(cfg, sol["starts"], sol["modes"])

    result["config_id"]   = req.config.id
    result["config_name"] = req.config.name
    return result


# ── Weighted aggregation ──────────────────────────────────────────────────

@app.post("/weighted")
def weighted(req: WeightedRequest):
    cfg = req.config.to_solver_format()

    f1 = solve_f1(cfg)
    f2 = solve_f2(cfg)

    if not f1 or not f2:
        raise HTTPException(422, "Could not determine F1*/F2* bounds.")

    result = solve_weighted(
        cfg,
        temps_min=f1["cmax_total_h"],
        temps_max=f2["cmax_total_h"],
        cout_min=f2["total_cost_da"],
        cout_max=f1["total_cost_da"],
        n_lambdas=req.n_lambdas,
    )

    result["bounds"]      = {
        "temps_min": f1["cmax_total_h"],
        "temps_max": f2["cmax_total_h"],
        "cout_min":  f2["total_cost_da"],
        "cout_max":  f1["total_cost_da"],
    }
    result["f1"]          = f1
    result["f2"]          = f2
    result["config_id"]   = req.config.id
    result["config_name"] = req.config.name
    return result
