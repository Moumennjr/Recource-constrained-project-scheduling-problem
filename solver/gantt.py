"""
Gantt schedule serializer — dynamic, works with any ProblemConfig.

Timeline matches the notebook exactly:
  - Each zone takes cmax_zone hours
  - Between zones: raccordement inter-zone = 76h (DUR_RACCORDEMENT_INTER)
  - After all zones: test hydrostatique (task 13)
  - DUR_FINAL[12] = 456h is the COST basis for raccordement, NOT the schedule gap
"""

# Fixed inter-zone raccordement duration (matches notebook: DUR_RACCORDEMENT_INTER = 76)
DUR_RACCORDEMENT_INTER = 76.0


def build_gantt(cfg: dict, starts: dict, modes: dict) -> list:
    """
    Build flat Gantt bar records from a solved schedule.

    Returns list of dicts:
      { task_id, task_name, pipe, pipe_name, zone, start, duration, end, reinforced }
    All times are absolute project hours.

    Structure (matches notebook right-side Gantt):
      Zone 1 tasks
      Raccordement 1-2 (76h)
      Zone 2 tasks
      Raccordement 2-3 (76h)
      ...
      Zone N tasks
      Test hydrostatique (task 13)
    """
    PIPES      = cfg["PIPES"]
    TACHES     = cfg["TACHES"]
    N_ZONES    = cfg["N_ZONES"]
    DUR        = cfg["DUR"]
    DUR_FINAL  = cfg["DUR_FINAL"]
    ALPHA      = cfg["ALPHA"]
    NOM_TACHE  = cfg["NOM_TACHE"]
    NOM_PIPE   = cfg["NOM_PIPE"]

    # Derive cmax_zone from the solved schedule
    cmax_zone = max(
        starts[i][j] + DUR[i][j] * (ALPHA[i] if modes[i][j] == 1 else 1)
        for i in TACHES for j in PIPES
    )

    bars = []

    for zone in range(1, N_ZONES + 1):
        # Each zone is offset by (cmax_zone + 76h raccordement) per preceding zone
        zone_offset = (zone - 1) * (cmax_zone + DUR_RACCORDEMENT_INTER)

        # Tasks 1–11 for this zone across all pipes
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
                    "type":       "task",
                })

        # Raccordement inter-zone: external task between zone `zone` and zone `zone+1`
        # zone=None — it does not belong to any zone
        # label reflects the transition: "Raccordement Z1→Z2"
        if zone < N_ZONES:
            trans_start = zone_offset + cmax_zone
            bars.append({
                "task_id":    12,
                "task_name":  NOM_TACHE.get(12, f"Raccordement Z{zone}→Z{zone + 1}"),
                "pipe":       None,
                "pipe_name":  "—",
                "zone":       None,          # not part of any zone
                "zone_from":  zone,          # for display: "between zone X and zone X+1"
                "zone_to":    zone + 1,
                "start":      round(trans_start, 1),
                "duration":   round(DUR_RACCORDEMENT_INTER, 1),
                "end":        round(trans_start + DUR_RACCORDEMENT_INTER, 1),
                "reinforced": False,
                "type":       "inter_zone_connection",
            })

    # Test hydrostatique (task 13) — once, after the last zone
    project_zone_end = N_ZONES * cmax_zone + (N_ZONES - 1) * DUR_RACCORDEMENT_INTER
    cursor = project_zone_end

    for task_id in sorted(DUR_FINAL.keys()):
        if task_id == 12:
            continue   # task 12 is handled as inter-zone raccordement above
        duration  = DUR_FINAL[task_id]
        task_name = NOM_TACHE.get(task_id, f"Task {task_id}")
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
            "type":       "final",
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