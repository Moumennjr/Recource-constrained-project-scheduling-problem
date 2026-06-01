"""
Resource conflict detection — fully dynamic, accepts any RESSOURCES dict.
No longer imports from problem_data.py.
"""


def detect_conflicts(ressources: dict) -> dict:
    """
    Given a RESSOURCES dict (solver format), returns:
      { resource_name: [(task_waiting, task_blocking), ...] }

    Algorithm: sort tasks by index, accumulate consumption, flag overflow pairs.
    """
    conflicts = {}

    for resource_name, resource_data in ressources.items():
        sorted_tasks = sorted(resource_data["taches"], key=lambda x: x[0])
        capacity = resource_data["capacite"]

        cumul = 0
        current_group = []
        resource_conflicts = []

        for (task_index, unit_consumption) in sorted_tasks:
            if cumul + unit_consumption > capacity:
                if current_group:
                    blocking = max(current_group, key=lambda x: x[0])
                    resource_conflicts.append((task_index, blocking[0]))
                current_group = [(task_index, unit_consumption)]
                cumul = unit_consumption
            else:
                cumul += unit_consumption
                current_group.append((task_index, unit_consumption))

        if resource_conflicts:
            conflicts[resource_name] = resource_conflicts

    return conflicts


def get_conflicts_summary(cfg: dict, task_names: dict) -> list:
    """
    Return a JSON-serializable list of conflict records.
    cfg      — solver-format dict (from ProblemConfig.to_solver_format())
    task_names — {int: str} mapping
    """
    ressources = cfg["RESSOURCES"]
    conflicts = detect_conflicts(ressources)
    result = []

    for resource_name, conflict_list in conflicts.items():
        capacity = ressources[resource_name]["capacite"]
        for (task_waiting, task_blocking) in conflict_list:
            result.append({
                "resource":           resource_name,
                "capacity":           capacity,
                "task_waiting":       task_waiting,
                "task_blocking":      task_blocking,
                "task_waiting_name":  task_names.get(task_waiting, str(task_waiting)),
                "task_blocking_name": task_names.get(task_blocking, str(task_blocking)),
            })

    return result
