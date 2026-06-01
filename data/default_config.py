"""
Builds the default ProblemConfig from the static problem_data.py constants.
This is the canonical "example" problem loaded on startup.
"""

from data.problem_data import (
    PIPES, TACHES, N_ZONES,
    NOM_PIPE, NOM_TACHE,
    DUR, LAG, COUT, COUT_FINAL, DUR_FINAL,
    ALPHA, BETA, RESSOURCES,
)
from solver.config import ProblemConfig, ResourceDef, ResourceTask, FinalTaskDef

DEFAULT_ID = "default-pipeline-rcpsp"


def build_default_config() -> ProblemConfig:
    return ProblemConfig(
        id=DEFAULT_ID,
        name="Pipeline RCPSP — Exemple",
        description=(
            "Optimisation bi-objectif (durée + coût) pour 3 diamètres de pipeline "
            "sur 7 zones. Équipes normales ou renforcées, contraintes de ressources."
        ),
        pipes=PIPES,
        pipe_names={str(j): NOM_PIPE[j] for j in PIPES},
        n_zones=N_ZONES,
        task_ids=TACHES,
        task_names={str(i): NOM_TACHE[i] for i in TACHES},
        durations={str(i): {str(j): DUR[i][j] for j in PIPES} for i in TACHES},
        lags={
            str(i): {str(j): LAG[i][j] for j in PIPES}
            for i in TACHES[:-1]       # no lag entry for last task
        },
        hourly_costs={str(i): {str(j): COUT[i][j] for j in PIPES} for i in TACHES},
        alpha={str(i): ALPHA[i] for i in TACHES},
        beta={str(i):  BETA[i]  for i in TACHES},
        final_tasks=[
            FinalTaskDef(id=12, name="Raccordement",       duration=DUR_FINAL[12], hourly_cost=COUT_FINAL[12]),
            FinalTaskDef(id=13, name="Test hydrostatique", duration=DUR_FINAL[13], hourly_cost=COUT_FINAL[13]),
        ],
        resources=[
            ResourceDef(
                name=name,
                capacity=data["capacite"],
                tasks=[
                    ResourceTask(task_id=t, consumption=c)
                    for (t, c) in data["taches"]
                ],
            )
            for name, data in RESSOURCES.items()
        ],
    )
