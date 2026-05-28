"""
Gantt schedule serializer.
Converts solver output into a list of bar records ready for Recharts.
"""

from data.problem_data import (
    PIPES, TACHES, N_ZONES,
    DUR, DUR_FINAL, NOM_TACHE, NOM_PIPE,
    ALPHA,
)

# Fixed inter-zone gap imposed between zones on the same pipeline
INTER_ZONE_LAG = 76  # hours


def build_gantt(starts: dict, modes: dict, n_zones: int = N_ZONES) -> list:
    """
    Build a flat list of Gantt bar records for the frontend.

    Each record:
      { task_id, task_name, pipe, pipe_name, zone,
        start, duration, end, reinforced }

    'start' and 'end' are absolute project hours assuming zones run sequentially:
      zone_offset(z) = (z - 1) * cmax_zone
    We derive cmax_zone from the schedule itself.
    """
    # Derive cmax_zone from starts: latest start + duration on pipe 3
    cmax_zone = max(
        starts[i][3] + DUR[i][3] * (ALPHA[i] if modes[i][3] == 1 else 1)
        for i in TACHES
    )

    bars = []

    for zone in range(1, n_zones + 1):
        zone_offset = (zone - 1) * (cmax_zone + INTER_ZONE_LAG)

        for i in TACHES:
            for j in PIPES:
                s = starts[i][j]
                dur = DUR[i][j] * (ALPHA[i] if modes[i][j] == 1 else 1)
                bars.append({
                    "task_id":    i,
                    "task_name":  NOM_TACHE[i],
                    "pipe":       j,
                    "pipe_name":  NOM_PIPE[j],
                    "zone":       zone,
                    "start":      round(zone_offset + s, 1),
                    "duration":   round(dur, 1),
                    "end":        round(zone_offset + s + dur, 1),
                    "reinforced": modes[i][j] == 1,
                })

    # Append final tasks (sequential, after all zones)
    project_end_zones = n_zones * (cmax_zone + INTER_ZONE_LAG) - INTER_ZONE_LAG
    cursor = project_end_zones

    final_tasks = [
        {"task_id": 12, "task_name": "Raccordement",       "duration": DUR_FINAL[12]},
        {"task_id": 13, "task_name": "Test hydrostatique",  "duration": DUR_FINAL[13]},
    ]
    for ft in final_tasks:
        bars.append({
            "task_id":   ft["task_id"],
            "task_name": ft["task_name"],
            "pipe":      None,
            "pipe_name": "—",
            "zone":      None,
            "start":     round(cursor, 1),
            "duration":  ft["duration"],
            "end":       round(cursor + ft["duration"], 1),
            "reinforced": False,
        })
        cursor += ft["duration"]

    return bars


def build_gantt_summary(bars: list) -> dict:
    """Return high-level metrics from the Gantt bar list."""
    ends = [b["end"] for b in bars]
    return {
        "total_hours":  round(max(ends), 1),
        "total_days":   round(max(ends) / 24, 1),
        "total_bars":   len(bars),
    }