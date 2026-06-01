# RCPSP API — Quick Reference Guide

## All Routes at a Glance

| Method | Endpoint | Purpose | Calculations |
|--------|----------|---------|--------------|
| `GET` | `/health` | Health check | None |
| `GET` | `/problems` | List problems | Count tasks, pipes, zones |
| `GET` | `/problems/default` | Get default config | Load from file |
| `GET` | `/problems/{id}` | Fetch problem | Lookup |
| `POST` | `/problems` | Create problem | Store config |
| `PUT` | `/problems/{id}` | Update problem | Store config |
| `DELETE` | `/problems/{id}` | Delete problem | Remove from store |
| `POST` | `/conflicts` | Analyze resource conflicts | **Detect conflict pairs** |
| `POST` | `/solve` | Solve (makespan or cost) | **Build & solve MILP** |
| `POST` | `/pareto` | Pareto front (ε-constraint) | **Sweep between F1*, F2*** |
| `POST` | `/weighted` | Weighted scalarization | **Sweep λ ∈ [0,1]** |

---

## Route Categories

### 🏥 Health
- `/health` → simple ping

### 📦 Problem CRUD
- `/problems`, `/problems/{id}`, `/problems/default`
- `/problems` (POST, PUT, DELETE)
- **Calculations**: Metadata counting, config storage/retrieval

### 🔍 Analysis
- `/conflicts`
- **Calculation**: Detects task pairs that violate resource capacity constraints

### ⚙️ Optimization

#### Single Objective
- `/solve` with `objective = "makespan"` or `"cost"`
- **Calculations**:
  - Builds MILP model (decision variables, constraints)
  - Solves with CBC solver
  - Extracts: start times, reinforcement flags, makespan, cost
  - Generates Gantt chart with time offsets

#### Multi-Objective (Pareto)
- `/pareto` with `n_points` (e.g., 12)
- **Calculations**:
  - Solves F1* (min makespan)
  - Solves F2* (min cost)
  - ε-constraint sweep: fixes makespan bounds and minimizes cost
  - Returns: anchor solutions + n_points Pareto trade-off points

#### Multi-Objective (Weighted)
- `/weighted` with `n_lambdas` (e.g., 15)
- **Calculations**:
  - Solves F1* and F2* to determine bounds
  - Normalizes both objectives: `F1_norm`, `F2_norm`
  - Scalarization: `λ * F2_norm + (1-λ) * F1_norm`
  - Sweeps λ from 0 to 1 and deduplicates unique solutions

---

## Key Decision Variables

| Symbol | Meaning | Type | Example |
|--------|---------|------|---------|
| `d[i][j]` | Start time of task i on pipe j | Continuous ≥0 | 45.5 hours |
| `y[i][j]` | Reinforcement flag (task i on pipe j) | Binary (0 or 1) | 1 = reinforced |
| `Cmax` | Makespan per zone | Continuous ≥0 | 168.5 hours |

**Effective duration**: `DUR[i][j] * (1 - ALPHA[i] * y[i][j])`
- If y=1 and ALPHA=0.3: duration reduced by 30%
- If y=0: full duration used

---

## Key Constraints

| Constraint | Formula | Purpose |
|-----------|---------|---------|
| **Makespan** | `Cmax ≥ d[last_task][j] + eff_dur(last_task, j)` | Define project completion |
| **Precedence** | `d[next][j] ≥ d[curr][j] + LAG[curr][j]` | Task ordering on same pipe |
| **Inter-pipe** | `d[task][j+1] ≥ d[task][j] + eff_dur(task, j)` | Sequential pipe execution |
| **Resource** | `d[waiting][0] ≥ d[blocking][last] + eff_dur(blocking, last)` | Prevent resource conflicts |

---

## Output Metrics

### Time Metrics
| Metric | Definition | Example |
|--------|-----------|---------|
| `cmax_zone_h` | Duration of one zone cycle | 168.5 hours |
| `cmax_total_h` | Total project duration (all zones + final) | 850.2 hours |
| `cmax_total_days` | Total duration in days | 35.4 days |

### Cost Metrics
| Metric | Definition | Example |
|--------|-----------|---------|
| `total_cost_da` | Total reinforcement cost | 1450 DA |
| `reinforced_count` | Number of reinforced task-pipe pairs | 5 |

### Normalized Metrics (Weighted)
| Metric | Formula | Range |
|--------|---------|-------|
| `duration_norm` | `(time - min_time) / (max_time - min_time)` | [0, 1] |
| `cost_norm` | `(cost - min_cost) / (max_cost - min_cost)` | [0, 1] |

---

## Response Structure Template

### Single Objective (Makespan/Cost)
```json
{
  "objective": "makespan|cost",
  "status": "optimal",
  "cmax_zone_h": 168.5,
  "cmax_total_h": 850.2,
  "cmax_total_days": 35.4,
  "total_cost_da": 1450,
  "reinforced_count": 5,
  "starts": { "task": { "pipe": start_time } },
  "modes": { "task": { "pipe": 0|1 } },
  "gantt_bars": [ { task_id, task_name, pipe, start, duration, end, reinforced } ],
  "gantt_summary": { total_hours, total_days, total_bars },
  "config_id": "...",
  "config_name": "..."
}
```

### Pareto Front
```json
{
  "status": "ok",
  "f1": { objective, status, cmax_zone_h, cmax_total_h, total_cost_da, ... },
  "f2": { objective, status, cmax_zone_h, cmax_total_h, total_cost_da, ... },
  "pareto_points": [
    { epsilon, cmax_zone_h, cmax_total_h, total_cost_da, reinforced_count }
  ],
  "n_requested": 12
}
```

### Weighted Scalarization
```json
{
  "status": "ok",
  "bounds": { temps_min, temps_max, cout_min, cout_max },
  "f1": { ... },
  "f2": { ... },
  "results": [
    { lambda, status, cmax_total_h, total_cost_da, duration_norm, cost_norm, reinforced_count }
  ],
  "unique_solutions": [
    { lambda_values: [...], cmax_total_h, total_cost_da, ... }
  ]
}
```

---

## Workflow Examples

### Quickest Schedule (F1)
```bash
POST /solve { objective: "makespan" }
→ Returns: shortest duration, highest cost
```

### Cheapest Schedule (F2)
```bash
POST /solve { objective: "cost" }
→ Returns: lowest cost, longest duration
```

### Explore Trade-Offs
```bash
POST /pareto { n_points: 12 }
→ Returns: 12 intermediate solutions + F1* + F2*
```

### Smooth Interpolation
```bash
POST /weighted { n_lambdas: 15 }
→ Returns: 15 solutions from λ=0 (fastest) to λ=1 (cheapest)
```

---

## Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| `/solve` | 1–5 sec | Single MILP solve |
| `/pareto` (12 points) | 30–60 sec | 12 × MILP solves |
| `/weighted` (15 λ) | 20–40 sec | 15 × MILP solves |
| `/conflicts` | <100 ms | Simple detection |

---

## Common Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `204` | Deleted successfully |
| `400` | Bad request (invalid data) |
| `404` | Not found |
| `422` | Solver failed (no feasible solution) |

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Route definitions |
| `solver/model.py` | MILP model builder |
| `solver/pareto.py` | Pareto front (ε-constraint) |
| `solver/weighted.py` | Weighted scalarization |
| `solver/conflicts.py` | Resource conflict detection |
| `solver/gantt.py` | Gantt chart serialization |
| `data/default_config.py` | Default problem config |

---

## Testing

**Bootstrap with default problem**:
```bash
curl http://localhost:8000/problems/default
```

**List all problems**:
```bash
curl http://localhost:8000/problems
```

**Health check**:
```bash
curl http://localhost:8000/health
```

**API docs** (interactive):
```
http://localhost:8000/docs
```

---

## Glossary

| Term | Definition |
|------|-----------|
| **RCPSP** | Resource-Constrained Project Scheduling Problem |
| **Makespan** | Total project duration |
| **Reinforcement** | Hiring extra personnel to reduce task duration |
| **ALPHA** | Reduction factor when reinforced (e.g., 0.3 = 30% faster) |
| **Conflict** | Two tasks cannot run in parallel (resource limit) |
| **Pareto** | Non-dominated solutions (can't improve one without worsening another) |
| **ε-Constraint** | Method: fix one objective as a constraint, minimize the other |
| **Weighted** | Method: minimize weighted sum of normalized objectives |
| **MILP** | Mixed Integer Linear Programming optimization model |
| **CBC** | Coin-or-Branch-and-Cut (open-source MILP solver) |

