"""
controller.py — Controller layer.

Responsibilities:
  - Own the pygame event loop.
  - Translate raw keyboard events into model commands.
  - Drive the game loop: tick the model, ask the view to render.
  - Know nothing about rendering details (that's the View's job).
  - Know nothing about game rules (that's the Model's job).

The controller is the only layer that imports pygame directly for events.
"""

import sys
import pygame

from .config import (
    WIDTH, HEIGHT, FPS,
    STATE_MENU, STATE_PLAYING, STATE_PAUSED, STATE_OVER,
)
from .model import Direction, GameModel
from .view import GameView


class GameController:
    """
    Owns the main loop.
    Glues Model ↔ View together without them knowing about each other.
    """

    def __init__(self):
        pygame.init()
        self.screen  = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("SNAKE.IO — Player vs AI")
        self.clock   = pygame.time.Clock()
        self.model   = GameModel()
        self.view    = GameView(self.screen)

    # ── Public entry point ────────────────────────────────────────
    def run(self) -> None:
        """Start and run the game loop until the player quits."""
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self.model.update(dt)
            self.view.render(self.model)

    # ── Event dispatch ────────────────────────────────────────────
    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

    def _handle_keydown(self, key: int) -> None:
        # Global keys — work in every state
        if key == pygame.K_q:
            self._quit()

        state = self.model.state

        if state == STATE_MENU:
            self._handle_menu_keys(key)
        elif state == STATE_PLAYING:
            self._handle_playing_keys(key)
        elif state == STATE_PAUSED:
            self._handle_paused_keys(key)
        elif state == STATE_OVER:
            self._handle_over_keys(key)

    # ── Per-state key handlers ────────────────────────────────────
    def _handle_menu_keys(self, key: int) -> None:
        if key in (pygame.K_RETURN, pygame.K_SPACE):
            self.model.start()
        self._handle_difficulty_keys(key)

    def _handle_playing_keys(self, key: int) -> None:
        direction_map = {
            pygame.K_LEFT:  Direction.LEFT,
            pygame.K_RIGHT: Direction.RIGHT,
            pygame.K_UP:    Direction.UP,
            pygame.K_DOWN:  Direction.DOWN,
        }
        if key in direction_map:
            self.model.player.request_direction(direction_map[key])
        elif key == pygame.K_p:
            self.model.pause()
        elif key == pygame.K_r:
            self.model.restart()

    def _handle_paused_keys(self, key: int) -> None:
        if key in (pygame.K_p, pygame.K_SPACE):
            self.model.resume()
        elif key == pygame.K_r:
            self.model.restart()

    def _handle_over_keys(self, key: int) -> None:
        if key in (pygame.K_r, pygame.K_SPACE, pygame.K_RETURN):
            self.model.restart()
        self._handle_difficulty_keys(key)

    def _handle_difficulty_keys(self, key: int) -> None:
        diff_map = {
            pygame.K_1: 1,
            pygame.K_2: 2,
            pygame.K_3: 3,
            pygame.K_4: 4,
        }
        if key in diff_map:
            self.model.set_difficulty(diff_map[key])

    # ── Utilities ─────────────────────────────────────────────────
    @staticmethod
    def _quit() -> None:
        pygame.quit()
        sys.exit()
