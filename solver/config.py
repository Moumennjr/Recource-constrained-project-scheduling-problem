"""
ProblemConfig — the single schema for all RCPSP problem instances.

All solver functions accept cfg = problem_config.to_solver_format()
so they are fully decoupled from problem_data.py constants.

Design:
  - JSON dict keys are always strings (JSON spec); to_solver_format() converts them to int.
  - extra_constraints is an open extension point for future constraint types.
"""

import uuid
from typing import Optional
from pydantic import BaseModel, Field


class ResourceTask(BaseModel):
    task_id: int
    consumption: int


class ResourceDef(BaseModel):
    name: str
    capacity: int
    tasks: list[ResourceTask]


class FinalTaskDef(BaseModel):
    id: int
    name: str
    duration: float       # hours
    hourly_cost: float    # DA/h — total fixed cost = duration * hourly_cost


class ProblemConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""

    # ── Scheduling topology ───────────────────────────────────────────────
    pipes:      list[int]             # e.g. [1, 2, 3]
    pipe_names: dict[str, str]        # {"1": '16"', "2": '20"', "3": '24"'}
    n_zones:    int                   # number of zones (default 7)

    # ── Task catalogue ────────────────────────────────────────────────────
    task_ids:   list[int]             # ordered list, e.g. [1, 2, ..., 11]
    task_names: dict[str, str]        # {"1": "Ouverture piste", ...}

    # ── Per-task × per-pipe parameters (outer key = task_id str, inner = pipe_id str) ──
    durations:    dict[str, dict[str, float]]   # hours
    lags:         dict[str, dict[str, float]]   # start-to-start lag to NEXT task (h)
    hourly_costs: dict[str, dict[str, float]]   # DA/h

    # ── Reinforced team parameters (per task) ────────────────────────────
    alpha: dict[str, float]   # speed factor < 1  (eff_dur = DUR * alpha)
    beta:  dict[str, float]   # cost  factor > 1  (eff_cost_rate = rate * beta)

    # ── Final sequential tasks (after all zones) ─────────────────────────
    final_tasks: list[FinalTaskDef]

    # ── Resources ────────────────────────────────────────────────────────
    resources: list[ResourceDef]

    # ── Extension point — new constraint types go here ───────────────────
    extra_constraints: list[dict] = []

    # ─────────────────────────────────────────────────────────────────────

    def to_solver_format(self) -> dict:
        """
        Convert to int-keyed dicts for direct use inside PuLP model builders.
        This is the ONLY place string→int conversion happens.
        """
        DUR   = {int(i): {int(j): v for j, v in row.items()} for i, row in self.durations.items()}
        LAG   = {int(i): {int(j): v for j, v in row.items()} for i, row in self.lags.items()}
        COUT  = {int(i): {int(j): v for j, v in row.items()} for i, row in self.hourly_costs.items()}

        DUR_FINAL  = {ft.id: ft.duration     for ft in self.final_tasks}
        COUT_FINAL = {ft.id: ft.hourly_cost  for ft in self.final_tasks}

        RESSOURCES = {
            r.name: {
                "taches":   [(t.task_id, t.consumption) for t in r.tasks],
                "capacite": r.capacity,
            }
            for r in self.resources
        }

        return {
            "PIPES":      self.pipes,
            "TACHES":     self.task_ids,
            "N_ZONES":    self.n_zones,
            "NOM_PIPE":   {int(k): v for k, v in self.pipe_names.items()},
            "NOM_TACHE":  {int(k): v for k, v in self.task_names.items()},
            "DUR":        DUR,
            "LAG":        LAG,
            "COUT":       COUT,
            "ALPHA":      {int(k): v for k, v in self.alpha.items()},
            "BETA":       {int(k): v for k, v in self.beta.items()},
            "DUR_FINAL":  DUR_FINAL,
            "COUT_FINAL": COUT_FINAL,
            "RESSOURCES": RESSOURCES,
        }
