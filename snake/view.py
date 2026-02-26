"""
view.py — View layer (enhanced).

Rendering improvements over v1:
  - Pre-rendered grid surface (drawn once, blitted every frame)
  - CRT scanline overlay for retro atmosphere
  - Rounded snake segments with gradient tail fade
  - Per-frame glow compositing using additive blending
  - Animated pulsing title on menu/overlay screens
  - Animated difficulty pip selector in HUD
  - Snake head inner highlight stripe
  - Smooth score rack-up animation
  - High-score tracking displayed in HUD
  - Score comparison bar on game-over screen
  - Controls hint grid on menu
  - Cleaner overlay layout with proper spacing

Public API (unchanged):
    GameView(screen)    — bind to a pygame surface
    view.render(model)  — draw the current frame
"""

import math
import pygame

from .config import (
    WIDTH, HEIGHT, PANEL_H, GAME_W, GAME_H,
    OFFSET_X, OFFSET_Y, CELL, COLS, ROWS,
    BG, GRID_COL, FOOD_COL, UI_COL, BLACK,
    PANEL_BG, BORDER_COL, PLAYER_COL, AI_COL,
    DIFFICULTIES,
    STATE_MENU, STATE_OVER, STATE_PAUSED, STATE_PLAYING,
)
from .model import GameModel, Snake, Particle


# ─────────────────────── colour helpers ──────────────────────────
def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _with_alpha(color: tuple, alpha: int) -> tuple:
    return (*color[:3], max(0, min(255, alpha)))


def _brighten(color: tuple, factor: float) -> tuple:
    return tuple(min(255, int(c * factor)) for c in color[:3])


# ─────────────────────────── GameView ────────────────────────────
class GameView:
    """Renders the complete game frame from a GameModel snapshot."""

    # ── Construction ─────────────────────────────────────────────
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._init_fonts()
        self._build_static_surfaces()

        # Score rack-up animation state
        self._disp_player_score: float = 0.0
        self._disp_ai_score: float = 0.0
        self._high_score: int = 0

        # For overlay title pulse animation
        self._anim_tick: int = 0

    # ── Main entry ───────────────────────────────────────────────
    def render(self, model: GameModel) -> None:
        self._anim_tick += 1

        # Update animated score counters
        self._disp_player_score += (model.player.score - self._disp_player_score) * 0.25
        self._disp_ai_score     += (model.ai.score     - self._disp_ai_score)     * 0.25
        if model.player.score > self._high_score:
            self._high_score = model.player.score

        # ── Base layers
        self.screen.fill(BG)
        self.screen.blit(self._grid_surf, (OFFSET_X, OFFSET_Y))

        # ── Game content
        self._draw_food(model.food, model.tick)

        if model.state != STATE_MENU:
            self._draw_snake_glow(model.player)
            self._draw_snake_glow(model.ai)
            self._draw_snake(model.player)
            self._draw_snake(model.ai)

        self._draw_particles(model.particles)

        # ── CRT scanlines (over everything)
        self.screen.blit(self._scanline_surf, (0, 0))

        # ── Chrome
        self._draw_border()
        self._draw_panel(model)

        # ── State overlays
        if model.state == STATE_MENU:
            self._draw_menu_overlay(model)
        elif model.state == STATE_PAUSED:
            self._draw_paused_overlay()
        elif model.state == STATE_OVER:
            self._draw_game_over_overlay(model)

        pygame.display.flip()

    # ── Static surface pre-builds ─────────────────────────────────
    def _build_static_surfaces(self) -> None:
        # Grid (drawn once, alpha so BG shows through slightly)
        self._grid_surf = pygame.Surface((GAME_W, GAME_H), pygame.SRCALPHA)
        for x in range(COLS + 1):
            pygame.draw.line(self._grid_surf, (*GRID_COL, 160),
                             (x * CELL, 0), (x * CELL, GAME_H))
        for y in range(ROWS + 1):
            pygame.draw.line(self._grid_surf, (*GRID_COL, 160),
                             (0, y * CELL), (GAME_W, y * CELL))

        # CRT scanlines — every other horizontal line, very subtle
        self._scanline_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(0, HEIGHT, 2):
            pygame.draw.line(self._scanline_surf, (0, 0, 0, 18), (0, y), (WIDTH, y))

        # Edge vignette — darkens borders of the game area
        edge = pygame.Surface((GAME_W, GAME_H), pygame.SRCALPHA)
        for i in range(28):
            a = int(55 * (1 - i / 28) ** 1.8)
            pygame.draw.rect(edge, (0, 0, 0, a),
                             (i, i, GAME_W - 2 * i, GAME_H - 2 * i), 1)
        self._edge_surf = edge

    # ── Food ─────────────────────────────────────────────────────
    def _draw_food(self, food: tuple[int, int], tick: int) -> None:
        pulse = 0.70 + 0.30 * math.sin(tick * 0.10)
        r = max(2, int((CELL / 2 + 1) * pulse))
        x = OFFSET_X + food[0] * CELL + CELL // 2
        y = OFFSET_Y + food[1] * CELL + CELL // 2

        # Layered outer glow
        glow_r = r + 10
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        for gr in range(glow_r, r, -1):
            a = int(90 * (1 - (gr - r) / (glow_r - r)) * pulse)
            pygame.draw.circle(glow, _with_alpha(FOOD_COL, a), (glow_r, glow_r), gr)
        self.screen.blit(glow, (x - glow_r, y - glow_r))

        # Core dot
        pygame.draw.circle(self.screen, FOOD_COL, (x, y), r)
        # Bright specular highlight
        pygame.draw.circle(self.screen, (255, 255, 220),
                           (x - max(1, r // 3), y - max(1, r // 3)),
                           max(1, r // 3))

    # ── Snake glow pass ───────────────────────────────────────────
    def _draw_snake_glow(self, snake: Snake) -> None:
        """Soft ambient glow around the snake head, drawn first (additive)."""
        if not snake.body or not snake.alive:
            return
        hx, hy = snake.body[0]
        cx = OFFSET_X + hx * CELL + CELL // 2
        cy = OFFSET_Y + hy * CELL + CELL // 2
        glow_size = 26
        glow = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        for gr in range(glow_size, 0, -2):
            a = int(28 * (gr / glow_size) ** 0.6)
            pygame.draw.circle(glow, _with_alpha(snake.color, a),
                               (glow_size, glow_size), gr)
        self.screen.blit(glow, (cx - glow_size, cy - glow_size),
                         special_flags=pygame.BLEND_RGBA_ADD)

    # ── Snake body ───────────────────────────────────────────────
    def _draw_snake(self, snake: Snake) -> None:
        if not snake.body:
            return

        length = len(snake.body)
        body_list = list(snake.body)

        for i, (sx, sy) in enumerate(body_list):
            # Colour fades from bright head to dim tail
            t = 1.0 - (i / max(length - 1, 1)) * 0.72
            color = _lerp_color(snake.dim_color, snake.color, t)

            # Tail segments gradually shrink
            shrink = 0 if i == 0 else min(3, 1 + i // max(1, length // 4))
            rect = pygame.Rect(
                OFFSET_X + sx * CELL + shrink,
                OFFSET_Y + sy * CELL + shrink,
                CELL - shrink * 2,
                CELL - shrink * 2,
            )
            if rect.width <= 0 or rect.height <= 0:
                continue

            # Rounded head, slightly rounded body segments
            radius = max(1, rect.width // 2 - 1) if i == 0 else max(1, rect.width // 4)
            pygame.draw.rect(self.screen, color, rect, border_radius=radius)

            # Inner highlight stripe on head only
            if i == 0:
                hi_color = _brighten(color, 1.6)
                hi_h = max(2, rect.h // 3)
                hi = pygame.Rect(rect.x + 2, rect.y + 2, max(1, rect.w - 4), hi_h)
                pygame.draw.rect(self.screen, hi_color, hi, border_radius=2)

        # Eyes drawn on top
        if body_list:
            self._draw_eyes(snake)

    def _draw_eyes(self, snake: Snake) -> None:
        hx, hy = snake.body[0]
        cx = OFFSET_X + hx * CELL + CELL // 2
        cy = OFFSET_Y + hy * CELL + CELL // 2
        dx, dy = snake.dir.x, snake.dir.y
        px, py = -dy, dx  # perpendicular

        for sign in (+1, -1):
            ex = int(cx + dx * 3 + sign * px * 2)
            ey = int(cy + dy * 3 + sign * py * 2)
            pygame.draw.rect(self.screen, (220, 220, 220), (ex - 1, ey - 1, 3, 3))  # sclera
            pygame.draw.rect(self.screen, BLACK,           (ex,     ey,     1, 1))  # pupil

    # ── Particles ────────────────────────────────────────────────
    def _draw_particles(self, particles: list[Particle]) -> None:
        for p in particles:
            if not p.alive:
                continue
            alpha = int(p.life * 255)
            # Soft halo behind each particle
            halo = p.size + 3
            h = pygame.Surface((halo * 2, halo * 2), pygame.SRCALPHA)
            pygame.draw.rect(h, _with_alpha(p.color, alpha // 4),
                             (0, 0, halo * 2, halo * 2), border_radius=halo)
            self.screen.blit(h, (int(p.x) - halo, int(p.y) - halo))
            # Core square
            s = pygame.Surface((p.size * 2, p.size * 2), pygame.SRCALPHA)
            pygame.draw.rect(s, _with_alpha(p.color, alpha),
                             (0, 0, p.size * 2, p.size * 2), border_radius=p.size)
            self.screen.blit(s, (int(p.x) - p.size, int(p.y) - p.size))

    # ── Border & corner accents ───────────────────────────────────
    def _draw_border(self) -> None:
        ox, oy = OFFSET_X, OFFSET_Y
        # Edge vignette (darkens game area borders)
        self.screen.blit(self._edge_surf, (ox, oy))
        # Outer rectangle
        pygame.draw.rect(self.screen, BORDER_COL,
                         (ox - 1, oy - 1, GAME_W + 2, GAME_H + 2), 1)
        size = 14
        # Player corners — green, left side
        for pts in [
            [(ox - 1, oy + size),         (ox - 1, oy - 1),      (ox + size, oy - 1)],
            [(ox - 1, oy + GAME_H - size), (ox - 1, oy + GAME_H), (ox + size, oy + GAME_H)],
        ]:
            pygame.draw.lines(self.screen, PLAYER_COL, False, pts, 2)
        # AI corners — red, right side
        for pts in [
            [(ox + GAME_W - size, oy - 1),      (ox + GAME_W, oy - 1),      (ox + GAME_W, oy + size)],
            [(ox + GAME_W - size, oy + GAME_H),  (ox + GAME_W, oy + GAME_H), (ox + GAME_W, oy + GAME_H - size)],
        ]:
            pygame.draw.lines(self.screen, AI_COL, False, pts, 2)

    # ── HUD Panel ─────────────────────────────────────────────────
    def _draw_panel(self, model: GameModel) -> None:
        pygame.draw.rect(self.screen, PANEL_BG, (0, 0, WIDTH, PANEL_H))
        pygame.draw.line(self.screen, BORDER_COL,
                         (0, PANEL_H - 1), (WIDTH, PANEL_H - 1), 1)

        # Subtle colour accent strips on left/right edges of panel
        for px_x, color in [(0, PLAYER_COL), (WIDTH - 3, AI_COL)]:
            strip = pygame.Surface((3, PANEL_H), pygame.SRCALPHA)
            strip.fill(_with_alpha(color, 45))
            self.screen.blit(strip, (px_x, 0))

        # Player score (left)
        self.screen.blit(self.font_small.render("YOU", True, PLAYER_COL), (16, 6))
        self.screen.blit(
            self.font_big.render(str(int(self._disp_player_score)), True, PLAYER_COL),
            (16, 24),
        )

        # AI score (right)
        self.screen.blit(self.font_small.render("AI", True, AI_COL), (WIDTH - 56, 6))
        self.screen.blit(
            self.font_big.render(str(int(self._disp_ai_score)), True, AI_COL),
            (WIDTH - 56, 24),
        )

        # Centre — difficulty pips + label + VS tag
        self._draw_difficulty_pips(WIDTH // 2, 8, model.difficulty)
        diff_label = DIFFICULTIES[model.difficulty]["label"]
        diff_surf = self.font_small.render(diff_label, True, FOOD_COL)
        self.screen.blit(diff_surf, diff_surf.get_rect(center=(WIDTH // 2, 26)))
        vs = self.font_tiny.render("VS", True, UI_COL)
        self.screen.blit(vs, vs.get_rect(center=(WIDTH // 2, 44)))

        # High score (bottom-left of panel)
        if self._high_score > 0:
            hs = self.font_tiny.render(f"BEST {self._high_score}",
                                       True, _lerp_color(UI_COL, FOOD_COL, 0.35))
            self.screen.blit(hs, hs.get_rect(bottomleft=(18, PANEL_H - 4)))

        # Paused badge (bottom-centre)
        if model.state == STATE_PAUSED:
            badge = self.font_tiny.render("[ PAUSED ]", True, FOOD_COL)
            bx = WIDTH // 2 - badge.get_width() // 2
            pygame.draw.rect(self.screen, _lerp_color(PANEL_BG, (40, 40, 5), 0.4),
                             (bx - 5, PANEL_H - 17, badge.get_width() + 10, 13))
            self.screen.blit(badge, (bx, PANEL_H - 17))

    def _draw_difficulty_pips(self, cx: int, y: int, active: int) -> None:
        """Four small circular pips representing 1–4 difficulty."""
        spacing = 12
        n = len(DIFFICULTIES)
        sx = cx - ((n - 1) * spacing) // 2
        pip_colors = [
            (0,   200, 100),
            (255, 200,   0),
            (255, 120,   0),
            (255,  51, 102),
        ]
        for i in range(1, n + 1):
            px = sx + (i - 1) * spacing
            is_active = (i == active)
            r = 4 if is_active else 2
            c = pip_colors[i - 1] if is_active else _lerp_color(UI_COL, BG, 0.3)
            if is_active:
                pygame.draw.circle(self.screen, _with_alpha(c, 55), (px, y + 4), r + 4)
            pygame.draw.circle(self.screen, c, (px, y + 4), r)

    # ── Overlay infrastructure ────────────────────────────────────
    def _draw_overlay_base(self) -> None:
        surf = pygame.Surface((GAME_W, GAME_H), pygame.SRCALPHA)
        surf.fill((5, 5, 12, 215))
        self.screen.blit(surf, (OFFSET_X, OFFSET_Y))
        pygame.draw.rect(self.screen, _lerp_color(BG, UI_COL, 0.12),
                         (OFFSET_X + 8, OFFSET_Y + 8, GAME_W - 16, GAME_H - 16), 1)

    def _draw_animated_title(self, title: str, color: tuple,
                              cy: int, font: pygame.font.Font) -> int:
        pulse = 0.82 + 0.18 * math.sin(self._anim_tick * 0.05)
        bright = _brighten(color, pulse)
        surf = font.render(title, True, bright)
        # Background glow slab
        gw, gh = surf.get_width() + 50, surf.get_height() + 16
        glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
        glow.fill(_with_alpha(color, int(35 * pulse)))
        self.screen.blit(glow, (WIDTH // 2 - gw // 2, cy - 8))
        self.screen.blit(surf, surf.get_rect(center=(WIDTH // 2, cy + surf.get_height() // 2)))
        return cy + surf.get_height() + 14

    def _draw_text_line(self, text: str, color: tuple,
                        cy: int, font: pygame.font.Font) -> int:
        if not text:
            return cy + 10
        surf = font.render(text, True, color)
        self.screen.blit(surf, surf.get_rect(center=(WIDTH // 2, cy)))
        return cy + surf.get_height() + 8

    def _draw_button(self, label: str, color: tuple, cy: int) -> int:
        btn_w = max(260, self.font_small.size(label)[0] + 40)
        btn_h = 38
        bx = WIDTH // 2 - btn_w // 2
        # Filled background
        bg = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        bg.fill(_with_alpha(color, 22))
        self.screen.blit(bg, (bx, cy))
        # Border
        pygame.draw.rect(self.screen, color, (bx, cy, btn_w, btn_h), 2, border_radius=4)
        # Label
        txt = self.font_small.render(label, True, color)
        self.screen.blit(txt, txt.get_rect(center=(WIDTH // 2, cy + btn_h // 2)))
        return cy + btn_h + 10

    def _draw_controls_hint(self, cy: int) -> None:
        hints = [("ARROWS", "MOVE"), ("P", "PAUSE"), ("R", "RESTART"), ("1-4", "DIFF")]
        total_w = len(hints) * 108
        sx = WIDTH // 2 - total_w // 2
        for i, (key, action) in enumerate(hints):
            x = sx + i * 108 + 54
            k_surf = self.font_tiny.render(key,    True, (200, 200, 255))
            a_surf = self.font_tiny.render(action, True, UI_COL)
            kw = k_surf.get_width() + 12
            kh = k_surf.get_height() + 4
            # Key cap background
            pygame.draw.rect(self.screen, (28, 28, 48),
                             (x - kw // 2, cy, kw, kh), border_radius=3)
            pygame.draw.rect(self.screen, (55, 55, 88),
                             (x - kw // 2, cy, kw, kh), 1, border_radius=3)
            self.screen.blit(k_surf, k_surf.get_rect(center=(x, cy + kh // 2)))
            self.screen.blit(a_surf, a_surf.get_rect(center=(x, cy + kh + 10)))

    # ── State overlays ────────────────────────────────────────────
    def _draw_menu_overlay(self, model: GameModel) -> None:
        self._draw_overlay_base()
        cy = OFFSET_Y + 28

        cy = self._draw_animated_title("SNAKE.IO", PLAYER_COL, cy, self.font_title)
        cy += 4
        cy = self._draw_text_line("PLAYER  vs  AI", UI_COL, cy, self.font_med)
        cy += 14

        diff_colors = {1: (0,200,100), 2: (255,200,0), 3: (255,120,0), 4: (255,51,102)}
        diff_label  = DIFFICULTIES[model.difficulty]["label"]
        cy = self._draw_text_line(
            f"◄   {diff_label}   ►",
            diff_colors[model.difficulty], cy, self.font_med,
        )
        cy = self._draw_text_line(
            "PRESS  1  2  3  4  TO CHANGE", UI_COL, cy, self.font_tiny,
        )
        cy += 18
        cy = self._draw_button("ENTER — START GAME", PLAYER_COL, cy)
        cy += 6
        self._draw_controls_hint(cy)

    def _draw_paused_overlay(self) -> None:
        self._draw_overlay_base()
        cy = OFFSET_Y + GAME_H // 2 - 36
        cy = self._draw_animated_title("PAUSED", FOOD_COL, cy, self.font_title)
        cy += 6
        self._draw_text_line("PRESS  P  TO RESUME", UI_COL, cy, self.font_med)

    def _draw_game_over_overlay(self, model: GameModel) -> None:
        self._draw_overlay_base()

        p_dead = not model.player.alive
        a_dead = not model.ai.alive
        if p_dead and a_dead:
            title, color, sub = "DRAW!",    FOOD_COL,   "BOTH SNAKES CRASHED"
        elif p_dead:
            title, color, sub = "GAME OVER", AI_COL,    "THE AI WINS!"
        else:
            title, color, sub = "YOU WIN!",  PLAYER_COL, "YOU BEAT THE AI!"

        cy = OFFSET_Y + 26
        cy = self._draw_animated_title(title, color, cy, self.font_title)
        cy += 2
        cy = self._draw_text_line(sub, _lerp_color(UI_COL, color, 0.5), cy, self.font_med)
        cy += 10

        cy = self._draw_score_comparison(model, cy)
        cy += 10

        if model.player.score > 0 and model.player.score >= self._high_score:
            cy = self._draw_text_line("★  NEW HIGH SCORE  ★", FOOD_COL, cy, self.font_small)
        else:
            cy = self._draw_text_line(f"BEST: {self._high_score}", UI_COL, cy, self.font_tiny)
        cy += 4

        diff_label = DIFFICULTIES[model.difficulty]["label"]
        cy = self._draw_text_line(
            f"DIFFICULTY: {diff_label}   |   PRESS 1-4 TO CHANGE",
            UI_COL, cy, self.font_tiny,
        )
        cy += 10
        self._draw_button("R / ENTER — PLAY AGAIN", color, cy)

    def _draw_score_comparison(self, model: GameModel, cy: int) -> int:
        """Horizontal bar split proportionally between player and AI scores."""
        bar_w, bar_h = 300, 20
        bx = WIDTH // 2 - bar_w // 2
        total = max(1, model.player.score + model.ai.score)
        pw = max(0, min(bar_w, int(bar_w * model.player.score / total)))
        aw = bar_w - pw

        # Background track
        pygame.draw.rect(self.screen, (18, 18, 30),
                         (bx, cy, bar_w, bar_h), border_radius=5)

        # Player fill
        if pw > 0:
            pygame.draw.rect(self.screen, PLAYER_COL,
                             (bx, cy, pw, bar_h), border_radius=5)
        # AI fill
        if aw > 0:
            pygame.draw.rect(self.screen, AI_COL,
                             (bx + pw, cy, aw, bar_h), border_radius=5)

        # Score labels inside the bar
        p_txt = self.font_small.render(f"YOU {model.player.score}", True, BLACK if pw > 50 else PLAYER_COL)
        a_txt = self.font_small.render(f"{model.ai.score} AI",      True, BLACK if aw > 50 else AI_COL)
        self.screen.blit(p_txt, (bx + 6, cy + bar_h // 2 - p_txt.get_height() // 2))
        self.screen.blit(a_txt, (bx + bar_w - a_txt.get_width() - 6,
                                  cy + bar_h // 2 - a_txt.get_height() // 2))
        return cy + bar_h + 6

    # ── Font init ─────────────────────────────────────────────────
    def _init_fonts(self) -> None:
        specs = [
            ("font_title", "courier", 42, True),
            ("font_big",   "courier", 26, True),
            ("font_med",   "courier", 17, False),
            ("font_small", "courier", 13, True),
            ("font_tiny",  "courier", 11, False),
        ]
        for attr, name, size, bold in specs:
            try:
                setattr(self, attr, pygame.font.SysFont(name, size, bold=bold))
            except Exception:
                setattr(self, attr, pygame.font.SysFont(None, size))
