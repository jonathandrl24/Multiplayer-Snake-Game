"""
model.py — Model layer.

Owns ALL game state and rules. Zero rendering, zero input handling.
Exposes a clean API for the Controller to read/write.

Classes:
    Direction   — immutable (dx, dy) value object
    Snake       — body, direction, score, alive flag
    Particle    — visual effect data (position, velocity, life)
    GameModel   — top-level model; owns both snakes, food, particles
"""

import math
import random
from collections import deque

from .config import (
    COLS, ROWS, GROW_ON_EAT,
    PLAYER_COL, PLAYER_DIM, AI_COL, AI_DIM,
    FOOD_COL, DIFFICULTIES,
    PARTICLE_FOOD_COUNT, PARTICLE_DEATH_COUNT,
    OFFSET_X, OFFSET_Y, CELL,
    STATE_PLAYING, STATE_OVER, STATE_MENU, STATE_PAUSED,
)


# ─────────────────────────── Direction ───────────────────────────
class Direction:
    """Immutable 2-D unit direction."""
    LEFT  = None  # filled below after class definition
    RIGHT = None
    UP    = None
    DOWN  = None

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def is_opposite(self, other: "Direction") -> bool:
        return self.x == -other.x and self.y == -other.y

    def copy(self) -> "Direction":
        return Direction(self.x, self.y)

    def __eq__(self, other):
        return isinstance(other, Direction) and self.x == other.x and self.y == other.y

    def __repr__(self):
        return f"Direction({self.x}, {self.y})"


Direction.LEFT  = Direction(-1,  0)
Direction.RIGHT = Direction( 1,  0)
Direction.UP    = Direction( 0, -1)
Direction.DOWN  = Direction( 0,  1)
ALL_DIRS = [Direction.RIGHT, Direction.LEFT, Direction.DOWN, Direction.UP]


# ──────────────────────────── Snake ──────────────────────────────
class Snake:
    """
    Pure game data for one snake (player or AI).
    No rendering. No input handling.
    """

    def __init__(
        self,
        start_x: int,
        start_y: int,
        start_dir: Direction,
        body_color: tuple,
        dim_color: tuple,
    ):
        self.body: deque[tuple[int, int]] = deque([(start_x, start_y)])
        self.dir: Direction = start_dir.copy()
        self._next_dir: Direction = start_dir.copy()
        self.color = body_color
        self.dim_color = dim_color
        self.alive: bool = True
        self.score: int = 0
        self._grow_pending: int = 0

    # ── Accessors ────────────────────────────────────────────────
    @property
    def head(self) -> tuple[int, int]:
        return self.body[0]

    @property
    def grow_pending(self) -> int:
        return self._grow_pending

    # ── Commands ─────────────────────────────────────────────────
    def request_direction(self, new_dir: Direction) -> None:
        """Queue a direction change (ignored if it would reverse the snake)."""
        if not new_dir.is_opposite(self.dir):
            self._next_dir = new_dir.copy()

    def step(self) -> bool:
        """
        Advance one cell.
        Returns True on success, False if the move killed the snake.
        """
        self.dir = self._next_dir.copy()
        hx, hy = self.head
        nx, ny = hx + self.dir.x, hy + self.dir.y

        if not (0 <= nx < COLS and 0 <= ny < ROWS):
            self.alive = False
            return False

        if (nx, ny) in self.body:
            self.alive = False
            return False

        self.body.appendleft((nx, ny))
        if self._grow_pending > 0:
            self._grow_pending -= 1
        else:
            self.body.pop()
        return True

    def eat(self) -> None:
        """Called when this snake eats food."""
        self.score += 1
        self._grow_pending += GROW_ON_EAT

    def kill(self) -> None:
        self.alive = False

    # ── Queries ──────────────────────────────────────────────────
    def occupies(self, x: int, y: int) -> bool:
        return (x, y) in self.body

    def head_at(self, x: int, y: int) -> bool:
        hx, hy = self.head
        return hx == x and hy == y


# ─────────────────────────── Particle ────────────────────────────
class Particle:
    """Visual-only data; updated by the model, rendered by the view."""

    def __init__(self, x: float, y: float, color: tuple):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.5, 4.5)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life: float = 1.0
        self.decay: float = random.uniform(0.03, 0.07)
        self.color = color
        self.size: int = random.randint(2, 4)

    @property
    def alive(self) -> bool:
        return self.life > 0

    def update(self) -> None:
        self.x  += self.vx
        self.y  += self.vy
        self.vx *= 0.90
        self.vy *= 0.90
        self.life -= self.decay


# ─────────────────────────── GameModel ───────────────────────────
class GameModel:
    """
    Top-level model.  Owns all game state.
    The controller calls update() once per game tick.
    """

    def __init__(self):
        self.difficulty: int = 2
        self.state: str = STATE_MENU
        self.tick: int = 0
        self.step_timer: float = 0.0
        self.player: Snake = None
        self.ai: Snake = None
        self.food: tuple[int, int] = (0, 0)
        self.particles: list[Particle] = []
        self._reset_entities()

    # ── Public API ───────────────────────────────────────────────
    def set_difficulty(self, level: int) -> None:
        if level in DIFFICULTIES:
            self.difficulty = level

    def start(self) -> None:
        self._reset_entities()
        self.state = STATE_PLAYING

    def pause(self) -> None:
        if self.state == STATE_PLAYING:
            self.state = STATE_PAUSED

    def resume(self) -> None:
        if self.state == STATE_PAUSED:
            self.state = STATE_PLAYING

    def restart(self) -> None:
        self._reset_entities()
        self.state = STATE_PLAYING

    def update(self, dt: float) -> None:
        """Advance game logic by dt seconds. Called every frame."""
        self.tick += 1
        if self.state != STATE_PLAYING:
            return

        self._update_particles()

        speed = DIFFICULTIES[self.difficulty]["speed"]
        self.step_timer += dt
        if self.step_timer >= 1.0 / speed:
            self.step_timer -= 1.0 / speed
            self._game_step()

    @property
    def diff_config(self) -> dict:
        return DIFFICULTIES[self.difficulty]

    # ── Private helpers ──────────────────────────────────────────
    def _reset_entities(self) -> None:
        self.player = Snake(
            COLS // 4, ROWS // 2,
            Direction.RIGHT,
            PLAYER_COL, PLAYER_DIM,
        )
        self.ai = Snake(
            3 * COLS // 4, ROWS // 2,
            Direction.LEFT,
            AI_COL, AI_DIM,
        )
        self.food = self._spawn_food()
        self.particles = []
        self.step_timer = 0.0
        self.tick = 0

    def _spawn_food(self) -> tuple[int, int]:
        occupied = set(self.player.body) | set(self.ai.body)
        while True:
            pos = (random.randint(0, COLS - 1), random.randint(0, ROWS - 1))
            if pos not in occupied:
                return pos

    def _game_step(self) -> None:
        from .ai_brain import compute_direction  # local import to avoid circular
        # AI decides its next move
        new_dir = compute_direction(
            self.ai, self.food, self.player,
            DIFFICULTIES[self.difficulty]["mistake"],
        )
        self.ai.request_direction(new_dir)

        # Advance both snakes
        self.player.step()
        self.ai.step()

        # Cross-collision (only when both still alive)
        if self.player.alive and self.ai.alive:
            ph, ah = self.player.head, self.ai.head
            # Head-on-head
            if ph == ah:
                self.player.kill()
                self.ai.kill()
            # Player head into AI body
            elif self.ai.occupies(*ph) and ph != self.ai.head:
                self.player.kill()
            # AI head into player body
            elif self.player.occupies(*ah) and ah != self.player.head:
                self.ai.kill()

        # Food pickup
        for snake in (self.player, self.ai):
            if snake.alive and snake.head_at(*self.food):
                snake.eat()
                fx = OFFSET_X + self.food[0] * CELL + CELL // 2
                fy = OFFSET_Y + self.food[1] * CELL + CELL // 2
                self._burst(fx, fy, FOOD_COL, PARTICLE_FOOD_COUNT)
                self.food = self._spawn_food()
                break  # only one snake eats per tick

        # Transition to game-over
        if not self.player.alive or not self.ai.alive:
            dead = self.player if not self.player.alive else self.ai
            hx = OFFSET_X + dead.head[0] * CELL + CELL // 2
            hy = OFFSET_Y + dead.head[1] * CELL + CELL // 2
            self._burst(hx, hy, dead.color, PARTICLE_DEATH_COUNT)
            self.state = STATE_OVER

    def _burst(self, x: float, y: float, color: tuple, count: int) -> None:
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def _update_particles(self) -> None:
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.alive]
