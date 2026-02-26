"""
config.py — Shared constants for the entire application.
No logic, no imports from internal modules.
"""

# ── Window & Grid ─────────────────────────────────────────────────
WIDTH, HEIGHT   = 620, 440
PANEL_H         = 60
GAME_W, GAME_H  = 600, 400
OFFSET_X        = 10
OFFSET_Y        = PANEL_H + 10
CELL            = 10
COLS            = GAME_W // CELL
ROWS            = GAME_H // CELL
FPS             = 60

# ── Colors ────────────────────────────────────────────────────────
BG          = (10,  10,  15)
GRID_COL    = (15,  20,  32)
PLAYER_COL  = (0,   255, 136)
PLAYER_DIM  = (0,   140, 80)
AI_COL      = (255, 51,  102)
AI_DIM      = (140, 30,  60)
FOOD_COL    = (255, 228, 77)
UI_COL      = (120, 120, 170)
BLACK       = (0,   0,   0)
PANEL_BG    = (12,  12,  20)
BORDER_COL  = (26,  26,  62)

# ── Gameplay ──────────────────────────────────────────────────────
GROW_ON_EAT = 3          # segments added when eating food
PARTICLE_FOOD_COUNT  = 12
PARTICLE_DEATH_COUNT = 20

DIFFICULTIES = {
    1: {"label": "EASY",   "speed": 8,  "mistake": 0.30},
    2: {"label": "NORMAL", "speed": 12, "mistake": 0.12},
    3: {"label": "HARD",   "speed": 16, "mistake": 0.04},
    4: {"label": "INSANE", "speed": 22, "mistake": 0.00},
}

# ── Game States ───────────────────────────────────────────────────
STATE_MENU    = "menu"
STATE_PLAYING = "playing"
STATE_PAUSED  = "paused"
STATE_OVER    = "over"
