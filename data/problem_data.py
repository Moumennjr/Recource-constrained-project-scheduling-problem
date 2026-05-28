"""
All problem constants for the pipeline RCPSP.
Source: RCPSP_3.ipynb
"""

PIPES  = [1, 2, 3]
TACHES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
N_ZONES = 7

NOM_PIPE = {1: '16"', 2: '20"', 3: '24"'}

NOM_TACHE = {
    1:  "Ouverture piste",
    2:  "Transport tubes",
    3:  "Bardage tubes",
    4:  "Soudage",
    5:  "Radiographie",
    6:  "Enrobage joints",
    7:  "Ouverture tranchée",
    8:  "Lit de sable",
    9:  "Mise en fouille",
    10: "Pré-remblai",
    11: "Grand remblai",
}

# DUR[i][j] = durée de la tâche i sur le pipeline j (heures)
DUR = {
    1:  {1: 24,  2: 24,  3: 24},
    2:  {1: 244, 2: 264, 3: 295},
    3:  {1: 97,  2: 105, 3: 117},
    4:  {1: 300, 2: 375, 3: 450},
    5:  {1: 43,  2: 46,  3: 50},
    6:  {1: 70,  2: 73,  3: 76},
    7:  {1: 44,  2: 53,  3: 63},
    8:  {1: 53,  2: 57,  3: 58},
    9:  {1: 68,  2: 72,  3: 77},
    10: {1: 37,  2: 38,  3: 40},
    11: {1: 23,  2: 24,  3: 25},
}

# LAG[i][j] = délai min entre le DÉBUT de la tâche i et le DÉBUT de i+1
LAG = {
    1:  {1: 24,  2: 24,  3: 24},
    2:  {1: 37,  2: 40,  3: 45},
    3:  {1: 10,  2: 11,  3: 12},
    4:  {1: 77,  2: 97,  3: 116},
    5:  {1: 10,  2: 11,  3: 12},
    6:  {1: 70,  2: 73,  3: 76},
    7:  {1: 44,  2: 53,  3: 63},
    8:  {1: 53,  2: 57,  3: 56},
    9:  {1: 68,  2: 72,  3: 77},
    10: {1: 37,  2: 38,  3: 40},
}

# Tâches finales (après toutes les zones) — durée et coût fixes
DUR_FINAL = {
    12: 456,   # Raccordement
    13: 1641,  # Test hydrostatique
}

# COUT[i][j] = coût horaire de l'équipe pour la tâche i sur le pipeline j (DA/h)
COUT = {
    1:  {1: 1500, 2: 1500, 3: 1500},
    2:  {1: 1600, 2: 1600, 3: 1600},
    3:  {1: 1500, 2: 1500, 3: 1500},
    4:  {1: 2000, 2: 2100, 3: 2200},
    5:  {1: 2000, 2: 2100, 3: 2200},
    6:  {1: 1800, 2: 1900, 3: 2000},
    7:  {1: 1700, 2: 1800, 3: 1900},
    8:  {1: 1400, 2: 1500, 3: 1600},
    9:  {1: 1900, 2: 2000, 3: 2100},
    10: {1: 1500, 2: 1600, 3: 1700},
    11: {1: 1600, 2: 1700, 3: 1800},
}

COUT_FINAL = {
    12: 1034520,
    13: 3760400,
}

# ALPHA[i] = facteur d'accélération de l'équipe renforcée (< 1)
ALPHA = {
    1:  0.85,
    2:  0.80,
    3:  0.75,
    4:  0.70,
    5:  0.85,
    6:  0.80,
    7:  0.75,
    8:  0.80,
    9:  0.75,
    10: 0.80,
    11: 0.85,
}

# BETA[i] = multiplicateur du coût horaire de l'équipe renforcée (> 1)
BETA = {
    1:  1.30,
    2:  1.40,
    3:  1.50,
    4:  1.60,
    5:  1.35,
    6:  1.40,
    7:  1.45,
    8:  1.35,
    9:  1.50,
    10: 1.35,
    11: 1.30,
}

# RESSOURCES : capacité et tâches associées (tache_index, consommation_unitaire)
RESSOURCES = {
    "Bull": {
        "taches":   [(7, 1), (11, 1)],
        "capacite": 2,
    },
    "Pipe_layer": {
        "taches":   [(3, 2), (9, 2)],
        "capacite": 4,
    },
    "Camion": {
        "taches":   [(4, 1), (9, 1)],
        "capacite": 3,
    },
    "Vehicule_TT": {
        "taches":   [(5, 1), (6, 1)],
        "capacite": 1,
    },
    "Tracteur_chenilles": {
        "taches":   [(4, 1), (6, 1)],
        "capacite": 2,
    },
    "Camion_benne": {
        "taches":   [(8, 2), (10, 2)],
        "capacite": 5,
    },
    "Chargeur": {
        "taches":   [(8, 2), (10, 2), (11, 1)],
        "capacite": 4,
    },
    "Conducteur_engins": {
        "taches":   [(3, 2), (7, 2), (8, 2), (9, 2), (10, 2), (11, 2)],
        "capacite": 12,
    },
    "MO": {
        "taches":   [(2, 4), (3, 3), (4, 4), (6, 2), (8, 3), (10, 2), (11, 2)],
        "capacite": 20,
    },
    "Chauffeur": {
        "taches":   [(4, 1), (5, 1), (6, 1), (7, 1), (8, 2), (9, 1), (10, 2)],
        "capacite": 10,
    },
}