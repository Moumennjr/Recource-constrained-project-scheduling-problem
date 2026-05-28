"""
Resource conflict detection.
Determines which task pairs cannot overlap due to resource capacity limits.
Returns: dict { resource_name: [(task_waiting, task_blocking), ...] }
"""

from data.problem_data import RESSOURCES, NOM_TACHE


def detect_conflicts() -> dict:
    conflicts = {}

    for resource_name, resource_data in RESSOURCES.items():
        sorted_tasks = sorted(resource_data["taches"], key=lambda x: x[0])
        capacity = resource_data["capacite"]

        cumul = 0
        current_group = []
        resource_conflicts = []

        for (task_index, unit_consumption) in sorted_tasks:
            if cumul + unit_consumption > capacity:
                if current_group:
                    blocking_task = max(current_group, key=lambda x: x[0])
                    resource_conflicts.append((task_index, blocking_task[0]))

                current_group = [(task_index, unit_consumption)]
                cumul = unit_consumption
            else:
                cumul += unit_consumption
                current_group.append((task_index, unit_consumption))

        if resource_conflicts:
            conflicts[resource_name] = resource_conflicts

    return conflicts


def get_conflicts_summary() -> list:
    """Return a serializable list of conflict records for the API."""
    conflicts = detect_conflicts()
    result = []

    for resource_name, conflict_list in conflicts.items():
        resource_data = RESSOURCES[resource_name]
        for (task_waiting, task_blocking) in conflict_list:
            result.append({
                "resource":      resource_name,
                "capacity":      resource_data["capacite"],
                "task_waiting":  task_waiting,
                "task_blocking": task_blocking,
                "task_waiting_name":  NOM_TACHE[task_waiting],
                "task_blocking_name": NOM_TACHE[task_blocking],
            })

    return result


# Pre-compute once at import time — used by the MILP model
CONFLITS = detect_conflicts()