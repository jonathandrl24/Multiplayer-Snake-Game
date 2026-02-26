"""
ai_brain.py — AI pathfinding module.

Completely isolated from rendering and input.
Receives read-only references to model objects and returns a Direction.

Strategy:
  - With probability `mistake_chance`: pick a random legal direction (simulates mistakes).
  - Otherwise: BFS to find the shortest path to the food, return the first step.
  - Fallback: if no path exists, pick the nearest-to-food safe direction.
"""

import random
from collections import deque

from .config import COLS, ROWS
from .model import Direction, Snake

ALL_DIRS = [Direction.RIGHT, Direction.LEFT, Direction.DOWN, Direction.UP]


def compute_direction(
    ai: Snake,
    food: tuple[int, int],
    player: Snake,
    mistake_chance: float,
) -> Direction:
    """
    Return the Direction the AI should move this tick.

    Parameters
    ----------
    ai             : the AI snake (read-only — we only read its state)
    food           : (x, y) grid position of the food
    player         : the player snake (currently unused but available for
                     future avoidance logic)
    mistake_chance : probability [0, 1] of making a random move
    """
    if random.random() < mistake_chance:
        return _random_legal(ai)

    found = _bfs(ai, food)
    if found:
        return found

    return _safest_fallback(ai, food)


# ── Internal helpers ──────────────────────────────────────────────

def _legal_dirs(snake: Snake) -> list[Direction]:
    """All directions that don't immediately kill the snake."""
    legal = []
    for d in ALL_DIRS:
        if d.is_opposite(snake.dir):
            continue
        nx, ny = snake.head[0] + d.x, snake.head[1] + d.y
        if not (0 <= nx < COLS and 0 <= ny < ROWS):
            continue
        if snake.occupies(nx, ny):
            continue
        legal.append(d)
    return legal


def _random_legal(snake: Snake) -> Direction:
    legal = _legal_dirs(snake)
    if legal:
        return random.choice(legal)
    return snake.dir  # can't do anything — keep current direction


def _bfs(snake: Snake, target: tuple[int, int]) -> Direction | None:
    """
    BFS from the snake's head to `target`.
    Returns the first Direction to take, or None if no path exists.
    """
    hx, hy = snake.head
    blocked = set(snake.body)  # treat entire body as obstacle

    queue: deque[tuple[int, int, Direction | None]] = deque()
    queue.append((hx, hy, None))
    visited: set[tuple[int, int]] = {(hx, hy)}

    while queue:
        cx, cy, first_dir = queue.popleft()

        if (cx, cy) == target and first_dir is not None:
            return first_dir

        for d in ALL_DIRS:
            nx, ny = cx + d.x, cy + d.y
            if not (0 <= nx < COLS and 0 <= ny < ROWS):
                continue
            if (nx, ny) in blocked or (nx, ny) in visited:
                continue
            visited.add((nx, ny))
            queue.append((nx, ny, first_dir or d))

    return None


def _safest_fallback(snake: Snake, target: tuple[int, int]) -> Direction:
    """
    When BFS finds no path, pick the legal direction that minimises
    Manhattan distance to the target.
    """
    legal = _legal_dirs(snake)
    if not legal:
        return snake.dir

    hx, hy = snake.head
    tx, ty = target
    legal.sort(key=lambda d: abs(hx + d.x - tx) + abs(hy + d.y - ty))
    return legal[0]
