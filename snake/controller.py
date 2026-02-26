"""
controller.py — Controller layer.

Responsibilities:
  - Own the pygame event loop.
  - Translate raw keyboard events into model commands.
  - Drive the game loop: tick the model, ask the view to render.
  - Manage background music (load, loop, pause/resume/stop).
  - Know nothing about rendering details (that's the View's job).
  - Know nothing about game rules (that's the Model's job).

Music notes:
  - song.mp3 must live in the same folder as this file (snake/song.mp3).
  - Music starts as soon as the game window opens and loops forever.
  - It pauses automatically when the game is paused (P key) and
    resumes when unpaused.
  - If the file is missing the game runs silently with a console warning.

The controller is the only layer that imports pygame directly for events.
"""

import os
import sys
import pygame

from .config import (
    WIDTH, HEIGHT, FPS,
    STATE_MENU, STATE_PLAYING, STATE_PAUSED, STATE_OVER,
)
from .model import Direction, GameModel
from .view import GameView

# Music file is expected next to this module: snake/song.mp3
_MUSIC_PATH = os.path.join(os.path.dirname(__file__), "song.mp3")


class GameController:
    """
    Owns the main loop.
    Glues Model <-> View without them knowing about each other.
    Also owns the pygame mixer so music lifecycle stays in one place.
    """

    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen    = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("SNAKE.IO — Player vs AI")
        self.clock     = pygame.time.Clock()
        self.model     = GameModel()
        self.view      = GameView(self.screen)
        self._music_ok = self._load_music()

    # ── Public entry point ────────────────────────────────────────
    def run(self) -> None:
        """Start and run the game loop until the player quits."""
        self._play_music()
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self.model.update(dt)
            self.view.render(self.model)

    # ── Music helpers ─────────────────────────────────────────────
    def _load_music(self) -> bool:
        """Load song.mp3. Returns True on success, False on any failure."""
        if not os.path.isfile(_MUSIC_PATH):
            print(f"[audio] song.mp3 not found at '{_MUSIC_PATH}' — running without music.")
            return False
        try:
            pygame.mixer.music.load(_MUSIC_PATH)
            pygame.mixer.music.set_volume(0.6)
            return True
        except pygame.error as exc:
            print(f"[audio] Could not load song.mp3: {exc}")
            return False

    def _play_music(self) -> None:
        """Start looping playback from the beginning."""
        if self._music_ok:
            pygame.mixer.music.play(loops=-1)   # -1 = loop forever

    def _pause_music(self) -> None:
        """Freeze playback at current position."""
        if self._music_ok and pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()

    def _resume_music(self) -> None:
        """Continue from where it was paused."""
        if self._music_ok:
            pygame.mixer.music.unpause()

    # ── Event dispatch ────────────────────────────────────────────
    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

    def _handle_keydown(self, key: int) -> None:
        # Q quits from any state
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
            self._pause_music()           # freeze music when game pauses
        elif key == pygame.K_r:
            self.model.restart()

    def _handle_paused_keys(self, key: int) -> None:
        if key in (pygame.K_p, pygame.K_SPACE):
            self.model.resume()
            self._resume_music()          # unfreeze music when game resumes
        elif key == pygame.K_r:
            self.model.restart()
            self._resume_music()          # restart also unpauses music

    def _handle_over_keys(self, key: int) -> None:
        if key in (pygame.K_r, pygame.K_SPACE, pygame.K_RETURN):
            self.model.restart()
            # Music keeps playing through game-over; no action needed
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
        pygame.mixer.music.stop()
        pygame.quit()
        sys.exit()
