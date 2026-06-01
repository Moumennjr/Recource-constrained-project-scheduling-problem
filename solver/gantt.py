"""
Gantt schedule serializer — dynamic, works with any ProblemConfig.
"""

INTER_ZONE_LAG = 76  # hours between zones (fixed pipeline coupling lag)


def build_gantt(cfg: dict, starts: dict, modes: dict) -> list:
    """
    Build flat Gantt bar records from a solved schedule.

    Returns list of dicts:
      { task_id, task_name, pipe, pipe_name, zone, start, duration, end, reinforced }
    All times are absolute project hours.
    """
    PIPES      = cfg["PIPES"]
    TACHES     = cfg["TACHES"]
    N_ZONES    = cfg["N_ZONES"]
    DUR        = cfg["DUR"]
    DUR_FINAL  = cfg["DUR_FINAL"]
    ALPHA      = cfg["ALPHA"]
    NOM_TACHE  = cfg["NOM_TACHE"]
    NOM_PIPE   = cfg["NOM_PIPE"]

    # Derive cmax_zone from schedule
    last_task = TACHES[-1]
    last_pipe = PIPES[-1]
    cmax_zone = max(
        starts[i][j] + DUR[i][j] * (ALPHA[i] if modes[i][j] == 1 else 1)
        for i in TACHES for j in PIPES
    )

    bars = []

    for zone in range(1, N_ZONES + 1):
        zone_offset = (zone - 1) * (cmax_zone + INTER_ZONE_LAG)

        for i in TACHES:
            for j in PIPES:
                s   = starts[i][j]
                dur = DUR[i][j] * (ALPHA[i] if modes[i][j] == 1 else 1.0)
                bars.append({
                    "task_id":    i,
                    "task_name":  NOM_TACHE.get(i, f"Task {i}"),
                    "pipe":       j,
                    "pipe_name":  NOM_PIPE.get(j, f"Pipe {j}"),
                    "zone":       zone,
                    "start":      round(zone_offset + s, 1),
                    "duration":   round(dur, 1),
                    "end":        round(zone_offset + s + dur, 1),
                    "reinforced": modes[i][j] == 1,
                })

    # Final sequential tasks — appended after all zones
    project_zone_end = N_ZONES * cmax_zone + (N_ZONES - 1) * INTER_ZONE_LAG
    cursor = project_zone_end

    for task_id, duration in cfg["DUR_FINAL"].items():
        task_name = cfg["NOM_TACHE"].get(task_id, f"Task {task_id}")
        bars.append({
            "task_id":    task_id,
            "task_name":  task_name,
            "pipe":       None,
            "pipe_name":  "—",
            "zone":       None,
            "start":      round(cursor, 1),
            "duration":   round(duration, 1),
            "end":        round(cursor + duration, 1),
            "reinforced": False,
        })
        cursor += duration

    return bars


def build_gantt_summary(bars: list) -> dict:
    ends = [b["end"] for b in bars]
    return {
        "total_hours": round(max(ends), 1),
        "total_days":  round(max(ends) / 24, 1),
        "total_bars":  len(bars),
    }
