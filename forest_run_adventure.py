"""
Forest Runner Adventure
=======================

A 2D endless-runner game built with Python Tkinter.

The player automatically runs through a scrolling forest and must jump
over ground obstacles (rocks, bushes, barriers) or slide under flying
obstacles (branches, pillars). Score grows with distance travelled and
the best score is persisted to disk.

Controls
--------
    SPACE  -> Jump
    DOWN   -> Slide
    P      -> Pause / Resume
    R      -> Restart (on Game Over screen)
    ESC    -> Back / Quit

Run
---
    python forest_run_adventure.py

Build a Windows executable
-------------------------
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "ForestRunAdventure" forest_run_adventure.py
"""

import json
import math
import os
import random
import sys
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError as exc:  # pragma: no cover - tkinter is stdlib
    raise SystemExit("Tkinter is required to run this game.") from exc


# ---------------------------------------------------------------------------
# Theme / configuration constants
# ---------------------------------------------------------------------------
THEME = {
    "sky_top": "#a8e6cf",
    "sky_mid": "#dcedc1",
    "sky_bottom": "#ffd3b6",
    "ground": "#7cb342",
    "ground_dark": "#558b2f",
    "dirt": "#8d6e63",
    "tree_trunk": "#6d4c41",
    "tree_leaf_dark": "#2e7d32",
    "tree_leaf_light": "#66bb6a",
    "hill_far": "#81c784",
    "hill_near": "#66bb6a",
    "sun": "#fff59d",
    "player_body": "#ef6c00",
    "player_belly": "#ffe0b2",
    "player_dark": "#bf360c",
    "rock": "#9e9e9e",
    "rock_dark": "#616161",
    "bush": "#9ccc65",
    "bush_dark": "#33691e",
    "bush_highlight": "#dcedc8",
    "berry": "#e53935",
    "barrier": "#5d4037",
    "barrier_stripe": "#ffca28",
    "branch": "#4e342e",
    "branch_leaf": "#43a047",
    "pillar": "#37474f",
    "text_dark": "#1b5e20",
    "text_shadow": "#335033",
    "panel": "#e8f5e9",
    "panel_dark": "#c8e6c9",
    "accent": "#ff7043",
    "good": "#43a047",
    "warn": "#fb8c00",
    "bad": "#e53935",
    "shadow": "#2e4d2e",
}

FONT_DISPLAY = ("Georgia", 44, "bold")
FONT_TITLE = ("Georgia", 38, "bold")
FONT_SUBTITLE = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_SCORE = ("Segoe UI", 22, "bold")
FONT_TAGLINE = ("Segoe UI Semibold", 13, "italic")
FONT_BUTTON = ("Segoe UI Semibold", 16, "bold")

GAME_WIDTH = 900
GAME_HEIGHT = 520
GROUND_Y = 430
FPS = 60
BASE_SPEED = 6.0


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def resource_path(relative: str) -> str:
    """Return the absolute path to a bundled resource (PyInstaller aware)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.abspath("."), relative)


def user_data_dir() -> Path:
    """Writable directory next to the executable / script for save files."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base


def round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    """Create a smooth rounded-rectangle polygon on ``canvas``.

    Returns the canvas item id. ``kwargs`` are forwarded to
    ``create_polygon`` (e.g. ``fill``, ``outline``, ``width``).
    """
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def lerp_color(c1, c2, t):
    """Linearly interpolate between two ``#rrggbb`` colors."""
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r = int(int(c1[0:2], 16) * (1 - t) + int(c2[0:2], 16) * t)
    g = int(int(c1[2:4], 16) * (1 - t) + int(c2[2:4], 16) * t)
    b = int(int(c1[4:6], 16) * (1 - t) + int(c2[4:6], 16) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# Sound manager (optional, gracefully degrades)
# ---------------------------------------------------------------------------
class SoundManager:
    """Play simple sound effects.

    Uses Windows ``winsound`` when available and falls back to a silent
    no-op on other platforms so the game never crashes for lack of audio.
    """

    def __init__(self) -> None:
        self.enabled = True
        try:
            import winsound  # type: ignore

            self._winsound = winsound
        except Exception:
            self._winsound = None
            self.enabled = False

    def _beep(self, frequency: int, duration: int) -> None:
        if not self.enabled or self._winsound is None:
            return
        try:
            self._winsound.Beep(frequency, duration)
        except Exception:
            self.enabled = False

    def jump(self) -> None:
        self._beep(880, 90)

    def slide(self) -> None:
        self._beep(420, 120)

    def coin(self) -> None:
        self._beep(1200, 60)

    def hit(self) -> None:
        self._beep(180, 300)

    def click(self) -> None:
        self._beep(660, 50)

    def toggle(self) -> None:
        self.enabled = not self.enabled


# ---------------------------------------------------------------------------
# Score manager with persistent high score
# ---------------------------------------------------------------------------
class ScoreManager:
    """Track current score and persist the high score to disk."""

    def __init__(self) -> None:
        self.score = 0
        self.high_score = 0
        self._path = user_data_dir() / "highscore.json"
        self.load_high_score()

    def load_high_score(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self.high_score = int(data.get("high_score", 0))
        except Exception:
            self.high_score = 0

    def save_high_score(self) -> None:
        try:
            self._path.write_text(
                json.dumps({"high_score": self.high_score}), encoding="utf-8"
            )
        except Exception:
            pass

    def reset(self) -> None:
        self.score = 0

    def add(self, amount: float) -> None:
        self.score += amount

    def commit(self) -> bool:
        """Return True if a new high score was set."""
        if int(self.score) > self.high_score:
            self.high_score = int(self.score)
            self.save_high_score()
            return True
        return False


# ---------------------------------------------------------------------------
# Reusable UI: modern button with hover effect
# ---------------------------------------------------------------------------
class HoverButton(tk.Canvas):
    """A rounded button drawn on canvas with hover/press animations."""

    def __init__(
        self,
        parent,
        text,
        command=None,
        width=220,
        height=58,
        bg=THEME["good"],
        fg="white",
        font=FONT_BUTTON,
        icon=None,
        accent=None,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent["bg"],
            highlightthickness=0,
            bd=0,
        )
        self._text = text
        self._command = command
        self._bw = width
        self._bh = height
        self._bg = bg
        self._fg = fg
        self._font = font
        self._icon = icon
        self._accent = accent or self._lighten(bg, 0.25)
        self._draw(bg)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self, color, hover=False, pressed=False):
        """Render the button with shadow, gradient and optional icon.

        ``hover`` lifts the button 2px and deepens the shadow; ``pressed``
        sinks it back down for a tactile click feel.
        """
        self.delete("all")
        w, h = self._bw, self._bh
        r = 18
        lift = 2 if (hover and not pressed) else 0
        # Drop shadow (translucent via stipple).
        sh_dx, sh_dy = (1, 1) if pressed else (2, 4 + (2 if hover else 0))
        self.create_round_rect(
            sh_dx, sh_dy + 2, w - 2 + sh_dx, h - 2 + sh_dy, r,
            fill=THEME["shadow"], outline="", stipple="gray50",
        )
        # Body.
        self.create_round_rect(
            2, 2 - lift, w - 2, h - 2 - lift, r, fill=color, outline="",
        )
        # Glossy top highlight.
        self.create_round_rect(
            4, 4 - lift, w - 4, (h // 2) - lift, r - 4,
            fill=self._lighten(color, 0.18), outline="",
        )
        # Bottom shade for a subtle 3D gradient.
        self.create_round_rect(
            3, (h // 2) - lift, w - 3, h - 3 - lift, r,
            fill=self._darken(color, 0.06), outline="",
        )
        # Thin accent line at the very top.
        self.create_round_rect(
            4, 3 - lift, w - 4, 6 - lift, 2,
            fill=self._lighten(color, 0.45), outline="",
        )
        # Icon + text.
        has_icon = self._icon is not None
        text_x = (w // 2) + (12 if has_icon else 0)
        if has_icon:
            self._draw_icon(26, (h // 2) - lift, self._lighten(color, 0.55))
        self.create_text(
            text_x, (h // 2) + 1 - lift,
            text=self._text, fill=self._fg, font=self._font,
        )

    def _draw_icon(self, cx, cy, color):
        """Draw a simple vector icon centered at ``(cx, cy)``."""
        kind = self._icon
        if kind == "play":
            self.create_polygon(
                cx - 6, cy - 8, cx - 6, cy + 8, cx + 8, cy,
                fill=color, outline="",
            )
        elif kind == "help":
            self.create_oval(cx - 9, cy - 9, cx + 9, cy + 9,
                             outline=color, width=2)
            self.create_text(cx, cy, text="?", font=("Segoe UI", 12, "bold"),
                             fill=color)
        elif kind == "exit":
            self.create_line(cx - 7, cy - 7, cx + 7, cy + 7,
                             fill=color, width=3, capstyle="round")
            self.create_line(cx + 7, cy - 7, cx - 7, cy + 7,
                             fill=color, width=3, capstyle="round")
        elif kind == "restart":
            self.create_arc(cx - 9, cy - 9, cx + 9, cy + 9,
                            start=30, extent=270, style="arc",
                            outline=color, width=2)
            self.create_polygon(
                cx + 8, cy - 9, cx + 2, cy - 11, cx + 5, cy - 2,
                fill=color, outline="",
            )
        elif kind == "menu":
            for off in (-6, 0, 6):
                self.create_line(cx - 8, cy + off, cx + 8, cy + off,
                                 fill=color, width=2, capstyle="round")
        elif kind == "back":
            self.create_polygon(
                cx + 6, cy - 8, cx - 6, cy, cx + 6, cy + 8,
                fill=color, outline="",
            )

    def create_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    @staticmethod
    def _lighten(hex_color, factor=0.18):
        hex_color = hex_color.lstrip("#")
        r, g, b = (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _darken(hex_color, factor=0.10):
        hex_color = hex_color.lstrip("#")
        r, g, b = (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_enter(self, _):
        self._draw(self._lighten(self._bg, 0.08), hover=True)

    def _on_leave(self, _):
        self._draw(self._bg)

    def _on_press(self, _):
        self._draw(self._darken(self._bg, 0.10), pressed=True)

    def _on_release(self, _):
        self._draw(self._bg, hover=True)
        if self._command:
            self._command()


# ---------------------------------------------------------------------------
# Scrolling forest background (parallax layers drawn with canvas shapes)
# ---------------------------------------------------------------------------
class ForestBackground:
    """Multi-layer parallax forest drawn entirely with canvas primitives."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self._build_sky()
        self._build_hills()
        self._build_trees()
        self._build_ground()
        self.offset_far = 0.0
        self.offset_mid = 0.0
        self.offset_near = 0.0
        self.offset_ground = 0.0

    def _build_sky(self):
        # Vertical gradient sky using stacked rectangles
        top = THEME["sky_top"]
        mid = THEME["sky_mid"]
        bot = THEME["sky_bottom"]
        steps = 40
        for i in range(steps):
            t = i / (steps - 1)
            if t < 0.5:
                color = self._lerp_color(top, mid, t * 2)
            else:
                color = self._lerp_color(mid, bot, (t - 0.5) * 2)
            y0 = int(i * GROUND_Y / steps)
            y1 = int((i + 1) * GROUND_Y / steps)
            self.canvas.create_rectangle(
                0, y0, GAME_WIDTH, y1, fill=color, outline="", tags="sky"
            )
        # Sun
        self.canvas.create_oval(
            GAME_WIDTH - 130, 40, GAME_WIDTH - 40, 130,
            fill=THEME["sun"], outline="", tags="sky",
        )
        # Soft clouds
        for cx, cy, s in [(120, 80, 1.0), (340, 60, 0.8), (560, 100, 1.1)]:
            self._draw_cloud(cx, cy, s, "sky")

    def _draw_cloud(self, x, y, scale, tag):
        c = "#ffffff"
        for dx, dy, r in [(-20, 0, 18), (0, -10, 22), (20, 0, 18), (10, 8, 16)]:
            self.canvas.create_oval(
                x + dx * scale, y + dy * scale,
                x + (dx + r) * scale * 1.4, y + (dy + r) * scale * 1.4,
                fill=c, outline="", tags=tag,
            )

    def _build_hills(self):
        # Two layers of rolling hills as polygons
        self._hill_far = self._make_hill_layer(
            base_y=GROUND_Y - 60, amp=40, color=THEME["hill_far"], tag="hill_far"
        )
        self._hill_near = self._make_hill_layer(
            base_y=GROUND_Y - 30, amp=25, color=THEME["hill_near"], tag="hill_near"
        )

    def _make_hill_layer(self, base_y, amp, color, tag):
        points = []
        for x in range(0, GAME_WIDTH * 2 + 1, 20):
            y = base_y - amp * math.sin(x / 180.0)
            points.extend([x, y])
        points.extend([GAME_WIDTH * 2, GROUND_Y, 0, GROUND_Y])
        return self.canvas.create_polygon(points, fill=color, outline="", tags=tag)

    def _build_trees(self):
        self._trees_mid = []
        self._trees_near = []
        spacing_mid = 220
        spacing_near = 300
        for i in range(10):
            x = i * spacing_mid
            self._trees_mid.append(self._draw_tree(x, GROUND_Y - 5, scale=0.8, tag="tree_mid"))
        for i in range(8):
            x = i * spacing_near + 80
            self._trees_near.append(
                self._draw_tree(x, GROUND_Y + 5, scale=1.1, tag="tree_near")
            )
        self._spacing_mid = spacing_mid
        self._spacing_near = spacing_near

    def _draw_tree(self, x, base_y, scale=1.0, tag="tree"):
        trunk_w = 14 * scale
        trunk_h = 50 * scale
        trunk = self.canvas.create_rectangle(
            x - trunk_w / 2, base_y - trunk_h,
            x + trunk_w / 2, base_y,
            fill=THEME["tree_trunk"], outline="", tags=tag,
        )
        # layered foliage (three ovals)
        leaves = []
        for dx, dy, r in [(0, -trunk_h - 10 * scale, 32 * scale),
                          (-18 * scale, -trunk_h + 4 * scale, 24 * scale),
                          (18 * scale, -trunk_h + 4 * scale, 24 * scale)]:
            leaves.append(self.canvas.create_oval(
                x + dx - r, base_y + dy - r,
                x + dx + r, base_y + dy + r,
                fill=THEME["tree_leaf_dark"], outline="", tags=tag,
            ))
        for dx, dy, r in [(0, -trunk_h - 18 * scale, 22 * scale)]:
            leaves.append(self.canvas.create_oval(
                x + dx - r, base_y + dy - r,
                x + dx + r, base_y + dy + r,
                fill=THEME["tree_leaf_light"], outline="", tags=tag,
            ))
        return (trunk, leaves, x, base_y, scale)

    def _build_ground(self):
        # Grass strip
        self.canvas.create_rectangle(
            0, GROUND_Y, GAME_WIDTH, GROUND_Y + 18,
            fill=THEME["ground"], outline="", tags="ground",
        )
        self.canvas.create_rectangle(
            0, GROUND_Y + 18, GAME_WIDTH, GAME_HEIGHT,
            fill=THEME["dirt"], outline="", tags="ground",
        )
        # Grass blades pattern (repeating)
        self._grass_blades = []
        for x in range(0, GAME_WIDTH * 2, 14):
            blade = self.canvas.create_line(
                x, GROUND_Y, x + 3, GROUND_Y - 6,
                fill=THEME["ground_dark"], width=2, tags="grass",
            )
            self._grass_blades.append(blade)
        self._grass_spacing = 14

    @staticmethod
    def _lerp_color(c1, c2, t):
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r = int(int(c1[0:2], 16) * (1 - t) + int(c2[0:2], 16) * t)
        g = int(int(c1[2:4], 16) * (1 - t) + int(c2[2:4], 16) * t)
        b = int(int(c1[4:6], 16) * (1 - t) + int(c2[4:6], 16) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def update(self, speed):
        """Scroll all parallax layers by ``speed`` pixels per frame."""
        self.offset_far += speed * 0.2
        self.offset_mid += speed * 0.45
        self.offset_near += speed * 0.75
        self.offset_ground += speed

        self.canvas.move("hill_far", -speed * 0.2, 0)
        self.canvas.move("tree_mid", -speed * 0.45, 0)
        self.canvas.move("tree_near", -speed * 0.75, 0)
        self.canvas.move("grass", -speed, 0)

        # Wrap hills (two-screen-wide polygon)
        if self.offset_far >= GAME_WIDTH:
            self.canvas.move("hill_far", GAME_WIDTH, 0)
            self.offset_far -= GAME_WIDTH

        # Wrap mid trees
        for item in self._trees_mid:
            trunk, leaves, x, base_y, scale = item
            cur = self.canvas.coords(trunk)
            if cur[2] < -40:
                shift = self._spacing_mid * len(self._trees_mid)
                self.canvas.move(trunk, shift, 0)
                for leaf in leaves:
                    self.canvas.move(leaf, shift, 0)
        # Wrap near trees
        for item in self._trees_near:
            trunk, leaves, x, base_y, scale = item
            cur = self.canvas.coords(trunk)
            if cur[2] < -40:
                shift = self._spacing_near * len(self._trees_near)
                self.canvas.move(trunk, shift, 0)
                for leaf in leaves:
                    self.canvas.move(leaf, shift, 0)

        # Wrap grass blades
        for blade in self._grass_blades:
            coords = self.canvas.coords(blade)
            if coords[2] < -5:
                self.canvas.move(blade, self._grass_spacing * len(self._grass_blades), 0)


# ---------------------------------------------------------------------------
# Player character (drawn fox-like runner with animated legs)
# ---------------------------------------------------------------------------
class Player:
    """The running character with jump and slide states."""

    STATE_RUN = "run"
    STATE_JUMP = "jump"
    STATE_SLIDE = "slide"

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.x = 130
        self.ground_y = GROUND_Y - 10
        self.y = self.ground_y
        self.vy = 0.0
        self.state = self.STATE_RUN
        self.run_frame = 0
        self.slide_timer = 0.0
        self.slide_duration = 0.65
        self.gravity = 1800.0
        self.jump_velocity = -780.0
        self.width = 54
        self.height = 70
        self.slide_height = 40
        self.alive = True
        self._dust = []
        self._build()

    def _build(self):
        self.ids = []
        # Body (oval), belly, head, ears, eye, legs, tail
        self.body = self.canvas.create_oval(0, 0, 1, 1, fill=THEME["player_body"], outline="")
        self.belly = self.canvas.create_oval(0, 0, 1, 1, fill=THEME["player_belly"], outline="")
        self.head = self.canvas.create_oval(0, 0, 1, 1, fill=THEME["player_body"], outline="")
        self.ear_l = self.canvas.create_polygon(0, 0, fill=THEME["player_dark"], outline="")
        self.ear_r = self.canvas.create_polygon(0, 0, fill=THEME["player_dark"], outline="")
        self.eye = self.canvas.create_oval(0, 0, 1, 1, fill="white", outline="")
        self.pupil = self.canvas.create_oval(0, 0, 1, 1, fill="#1b1b1b", outline="")
        self.nose = self.canvas.create_oval(0, 0, 1, 1, fill="#1b1b1b", outline="")
        self.leg_l = self.canvas.create_rectangle(0, 0, 1, 1, fill=THEME["player_dark"], outline="")
        self.leg_r = self.canvas.create_rectangle(0, 0, 1, 1, fill=THEME["player_dark"], outline="")
        self.arm = self.canvas.create_rectangle(0, 0, 1, 1, fill=THEME["player_dark"], outline="")
        self.tail = self.canvas.create_polygon(0, 0, fill=THEME["player_body"], outline="", smooth=True)
        self.ids = [
            self.tail, self.leg_l, self.leg_r, self.arm, self.body, self.belly,
            self.head, self.ear_l, self.ear_r, self.eye, self.pupil, self.nose,
        ]

    def jump(self, sound: SoundManager):
        if self.state == self.STATE_RUN and self.alive:
            self.vy = self.jump_velocity
            self.state = self.STATE_JUMP
            sound.jump()

    def slide(self, sound: SoundManager):
        if self.state == self.STATE_RUN and self.alive:
            self.state = self.STATE_SLIDE
            self.slide_timer = self.slide_duration
            sound.slide()

    def update(self, dt: float, sound: SoundManager):
        if not self.alive:
            return
        # Physics
        if self.state == self.STATE_JUMP:
            self.vy += self.gravity * dt
            self.y += self.vy * dt
            if self.y >= self.ground_y:
                self.y = self.ground_y
                self.vy = 0.0
                self.state = self.STATE_RUN
                self._spawn_dust()
        elif self.state == self.STATE_SLIDE:
            self.slide_timer -= dt
            if self.slide_timer <= 0:
                self.state = self.STATE_RUN
        # Run animation cycle
        if self.state == self.STATE_RUN:
            self.run_frame += dt * 14
        self._draw()
        self._update_dust(dt)

    def _spawn_dust(self):
        for _ in range(6):
            dx = random.uniform(-6, 6)
            dy = random.uniform(-4, 0)
            oid = self.canvas.create_oval(
                self.x - 10, self.ground_y + 8,
                self.x - 4, self.ground_y + 14,
                fill=THEME["dirt"], outline="",
            )
            self._dust.append([oid, dx, dy, 0.4])

    def _update_dust(self, dt):
        alive = []
        for oid, dx, dy, life in self._dust:
            life -= dt
            if life <= 0:
                self.canvas.delete(oid)
                continue
            self.canvas.move(oid, dx, dy)
            dy += 0.3
            alive.append([oid, dx, dy, life])
        self._dust = alive

    def _draw(self):
        c = self.canvas
        x = self.x
        sliding = self.state == self.STATE_SLIDE
        jumping = self.state == self.STATE_JUMP
        if sliding:
            # Compressed slide pose
            body_w, body_h = 70, 34
            by = self.ground_y - body_h + 6
            c.coords(self.body, x - body_w / 2, by, x + body_w / 2, by + body_h)
            c.coords(self.belly, x - body_w / 2 + 6, by + 8, x + body_w / 2 - 6, by + body_h - 4)
            # Head forward low
            hx = x + body_w / 2 - 6
            hy = by + 4
            c.coords(self.head, hx - 18, hy - 14, hx + 18, hy + 14)
            c.coords(self.ear_l, hx - 14, hy - 12, hx - 6, hy - 22, hx - 2, hy - 10)
            c.coords(self.ear_r, hx + 2, hy - 10, hx + 6, hy - 22, hx + 14, hy - 12)
            c.coords(self.eye, hx + 4, hy - 6, hx + 12, hy)
            c.coords(self.pupil, hx + 7, hy - 5, hx + 11, hy - 1)
            c.coords(self.nose, hx + 14, hy - 1, hx + 18, hy + 3)
            # Legs tucked
            c.coords(self.leg_l, x - 18, by + body_h - 6, x - 6, by + body_h + 4)
            c.coords(self.leg_r, x - 4, by + body_h - 6, x + 8, by + body_h + 4)
            c.coords(self.arm, x - 24, by + 6, x - 14, by + 16)
            # Tail low
            c.coords(self.tail, x - body_w / 2, by + 8, x - body_w / 2 - 18, by + 18,
                     x - body_w / 2 - 8, by + 24)
        else:
            body_w, body_h = 50, 44
            by = self.y - body_h
            c.coords(self.body, x - body_w / 2, by, x + body_w / 2, by + body_h)
            c.coords(self.belly, x - body_w / 2 + 6, by + 12, x + body_w / 2 - 6, by + body_h - 2)
            # Head
            hx = x + body_w / 2 - 4
            hy = by - 6
            head_size = 22
            c.coords(self.head, hx - head_size, hy - head_size,
                     hx + head_size, hy + head_size)
            c.coords(self.ear_l, hx - 16, hy - 14, hx - 8, hy - 30, hx - 2, hy - 12)
            c.coords(self.ear_r, hx + 2, hy - 12, hx + 8, hy - 30, hx + 16, hy - 14)
            c.coords(self.eye, hx + 6, hy - 8, hx + 16, hy)
            c.coords(self.pupil, hx + 9, hy - 7, hx + 14, hy - 2)
            c.coords(self.nose, hx + 18, hy + 2, hx + 24, hy + 8)
            # Animated legs
            phase = self.run_frame
            swing = math.sin(phase) * 10
            swing2 = math.sin(phase + math.pi) * 10
            leg_y = by + body_h - 4
            if jumping:
                c.coords(self.leg_l, x - 14, leg_y - 6, x - 6, leg_y + 10)
                c.coords(self.leg_r, x + 2, leg_y - 6, x + 10, leg_y + 10)
                c.coords(self.arm, x - 18, by + 8, x - 10, by + 20)
            else:
                c.coords(self.leg_l, x - 14 + swing, leg_y, x - 6 + swing, leg_y + 18)
                c.coords(self.leg_r, x + 2 + swing2, leg_y, x + 10 + swing2, leg_y + 18)
                c.coords(self.arm, x - 18, by + 8 + swing, x - 10, by + 18 + swing)
            # Tail wag
            tail_wag = math.sin(phase * 0.8) * 6
            c.coords(self.tail,
                     x - body_w / 2, by + 10,
                     x - body_w / 2 - 22, by + 4 + tail_wag,
                     x - body_w / 2 - 14, by + 22 + tail_wag,
                     x - body_w / 2, by + 20)

    def bbox(self):
        """Collision bounding box (slightly forgiving)."""
        if self.state == self.STATE_SLIDE:
            return (self.x - 30, self.ground_y - 30, self.x + 34, self.ground_y + 6)
        return (self.x - 22, self.y - 64, self.x + 24, self.y + 4)

    def reset(self):
        self.y = self.ground_y
        self.vy = 0.0
        self.state = self.STATE_RUN
        self.slide_timer = 0.0
        self.alive = True
        for oid, *_ in self._dust:
            self.canvas.delete(oid)
        self._dust.clear()

    def destroy(self):
        for oid in self.ids:
            self.canvas.delete(oid)
        for oid, *_ in self._dust:
            self.canvas.delete(oid)
        self._dust.clear()


# ---------------------------------------------------------------------------
# Obstacles
# ---------------------------------------------------------------------------
class Obstacle:
    """Base obstacle. Subclasses define drawing and required action."""

    KIND_GROUND = "ground"   # jump over
    KIND_FLYING = "flying"   # slide under

    def __init__(self, canvas: tk.Canvas, x: float, kind: str):
        self.canvas = canvas
        self.x = x
        self.kind = kind
        self.ids = []
        self.width = 0
        self.height = 0
        self.dead = False

    def _add_shadow(self, width, x_offset=0.0, height=8):
        """Draw a translucent ground shadow beneath the obstacle.

        Drawn first so the obstacle body sits on top of it. Uses a stippled
        fill to fake translucency (Tk has no real alpha).
        """
        cx = self.x + x_offset + width / 2
        self.ids.append(self.canvas.create_oval(
            cx - width / 2, GROUND_Y + 2,
            cx + width / 2, GROUND_Y + 2 + height,
            fill=THEME["shadow"], outline="", stipple="gray50",
        ))

    def move(self, dx: float):
        self.x -= dx
        for oid in self.ids:
            self.canvas.move(oid, -dx, 0)

    def bbox(self):
        raise NotImplementedError

    def off_screen(self):
        return self.x + self.width < -20

    def destroy(self):
        for oid in self.ids:
            self.canvas.delete(oid)
        self.ids.clear()


class RockObstacle(Obstacle):
    """A gray rock on the ground - jump over it."""

    def __init__(self, canvas, x):
        super().__init__(canvas, x, Obstacle.KIND_GROUND)
        self.width = 46
        self.height = 36
        self._add_shadow(self.width + 4)
        pts = [
            x, GROUND_Y,
            x + 8, GROUND_Y - 22,
            x + 20, GROUND_Y - 34,
            x + 36, GROUND_Y - 30,
            x + 46, GROUND_Y - 14,
            x + 44, GROUND_Y,
        ]
        self.ids.append(self.canvas.create_polygon(
            pts, fill=THEME["rock"], outline=THEME["rock_dark"], width=2,
        ))
        # darker shading
        pts2 = [
            x + 20, GROUND_Y - 34,
            x + 36, GROUND_Y - 30,
            x + 46, GROUND_Y - 14,
            x + 44, GROUND_Y,
            x + 30, GROUND_Y,
            x + 28, GROUND_Y - 18,
        ]
        self.ids.append(self.canvas.create_polygon(pts2, fill=THEME["rock_dark"], outline=""))
        # highlight on the lit side
        self.ids.append(self.canvas.create_oval(
            x + 8, GROUND_Y - 30, x + 18, GROUND_Y - 20,
            fill="#cfcfcf", outline="",
        ))

    def bbox(self):
        return (self.x + 4, GROUND_Y - self.height, self.x + self.width - 2, GROUND_Y)


class BushObstacle(Obstacle):
    """A leafy bush with berries - jump over it.

    Drawn in a bright green with a dark outline and red berries so it stays
    clearly visible against the darker forest background foliage.
    """

    def __init__(self, canvas, x):
        super().__init__(canvas, x, Obstacle.KIND_GROUND)
        self.width = 64
        self.height = 38
        self._add_shadow(self.width + 6)
        # Leaf clusters: dark outline, bright body, light highlight.
        for dx, dy, r in [(2, -6, 19), (24, -2, 17), (46, -6, 19),
                          (14, -18, 15), (36, -18, 15)]:
            self.ids.append(self.canvas.create_oval(
                x + dx - r, GROUND_Y + dy - r,
                x + dx + r, GROUND_Y + dy + r,
                fill=THEME["bush_dark"], outline="",
            ))
        for dx, dy, r in [(2, -6, 16), (24, -2, 14), (46, -6, 16),
                          (14, -18, 12), (36, -18, 12)]:
            self.ids.append(self.canvas.create_oval(
                x + dx - r, GROUND_Y + dy - r,
                x + dx + r, GROUND_Y + dy + r,
                fill=THEME["bush"], outline="",
            ))
        # Top highlights for volume.
        for dx, dy, r in [(6, -16, 7), (28, -12, 6), (48, -16, 7)]:
            self.ids.append(self.canvas.create_oval(
                x + dx - r, GROUND_Y + dy - r,
                x + dx + r, GROUND_Y + dy + r,
                fill=THEME["bush_highlight"], outline="",
            ))
        # Red berries so the bush reads clearly as an obstacle.
        for bx, by, br in [(10, -12, 4), (30, -22, 4), (44, -10, 4),
                           (20, -26, 3), (50, -22, 3)]:
            self.ids.append(self.canvas.create_oval(
                x + bx - br, GROUND_Y + by - br,
                x + bx + br, GROUND_Y + by + br,
                fill=THEME["berry"], outline=THEME["bush_dark"], width=1,
            ))

    def bbox(self):
        return (self.x + 4, GROUND_Y - self.height, self.x + self.width - 4, GROUND_Y)


class BarrierObstacle(Obstacle):
    """A wooden barrier with caution stripe - jump over it."""

    def __init__(self, canvas, x):
        super().__init__(canvas, x, Obstacle.KIND_GROUND)
        self.width = 34
        self.height = 64
        self._add_shadow(self.width + 8)
        # posts
        self.ids.append(self.canvas.create_rectangle(
            x - 4, GROUND_Y - 64, x + 4, GROUND_Y, fill=THEME["tree_trunk"], outline="",
        ))
        self.ids.append(self.canvas.create_rectangle(
            x + 30, GROUND_Y - 64, x + 38, GROUND_Y, fill=THEME["tree_trunk"], outline="",
        ))
        # barrier body with outline
        self.ids.append(self.canvas.create_rectangle(
            x, GROUND_Y - 60, x + 34, GROUND_Y,
            fill=THEME["barrier"], outline=THEME["tree_trunk"], width=2,
        ))
        # caution stripes (two bands)
        self.ids.append(self.canvas.create_rectangle(
            x, GROUND_Y - 44, x + 34, GROUND_Y - 34,
            fill=THEME["barrier_stripe"], outline="",
        ))
        self.ids.append(self.canvas.create_rectangle(
            x, GROUND_Y - 22, x + 34, GROUND_Y - 12,
            fill=THEME["barrier_stripe"], outline="",
        ))
        # post caps
        self.ids.append(self.canvas.create_oval(
            x - 6, GROUND_Y - 68, x + 6, GROUND_Y - 56, fill=THEME["tree_trunk"], outline="",
        ))
        self.ids.append(self.canvas.create_oval(
            x + 28, GROUND_Y - 68, x + 40, GROUND_Y - 56, fill=THEME["tree_trunk"], outline="",
        ))

    def bbox(self):
        return (self.x, GROUND_Y - self.height, self.x + self.width, GROUND_Y)


class BranchObstacle(Obstacle):
    """A low tree branch - slide under it."""

    def __init__(self, canvas, x):
        super().__init__(canvas, x, Obstacle.KIND_FLYING)
        self.width = 90
        self.height = 26
        self._add_shadow(40, x_offset=20)
        # support trunk on right (drawn first so branch sits on top)
        self.ids.append(self.canvas.create_rectangle(
            x + 86, GROUND_Y - 95, x + 92, GROUND_Y,
            fill=THEME["tree_trunk"], outline="",
        ))
        # branch bar with outline
        self.ids.append(self.canvas.create_rectangle(
            x, GROUND_Y - 95, x + 90, GROUND_Y - 70,
            fill=THEME["branch"], outline=THEME["tree_trunk"], width=2,
        ))
        # hanging leaves with darker outline
        for dx in range(6, 90, 18):
            self.ids.append(self.canvas.create_oval(
                x + dx, GROUND_Y - 78, x + dx + 14, GROUND_Y - 64,
                fill=THEME["branch_leaf"], outline=THEME["tree_leaf_dark"], width=1,
            ))

    def bbox(self):
        return (self.x + 4, GROUND_Y - 95, self.x + self.width - 4, GROUND_Y - 70)


class PillarObstacle(Obstacle):
    """A stone pillar gap - slide under the overhang."""

    def __init__(self, canvas, x):
        super().__init__(canvas, x, Obstacle.KIND_FLYING)
        self.width = 70
        self.height = 40
        self._add_shadow(50, x_offset=10)
        # top overhang with outline
        self.ids.append(self.canvas.create_rectangle(
            x, GROUND_Y - 110, x + 70, GROUND_Y - 70,
            fill=THEME["pillar"], outline="#263238", width=2,
        ))
        # hanging columns
        self.ids.append(self.canvas.create_rectangle(
            x + 4, GROUND_Y - 70, x + 16, GROUND_Y - 40,
            fill=THEME["pillar"], outline="",
        ))
        self.ids.append(self.canvas.create_rectangle(
            x + 54, GROUND_Y - 70, x + 66, GROUND_Y - 40,
            fill=THEME["pillar"], outline="",
        ))
        # warning chevron on the overhang
        self.ids.append(self.canvas.create_polygon(
            x + 30, GROUND_Y - 104, x + 40, GROUND_Y - 92,
            x + 20, GROUND_Y - 92, fill=THEME["barrier_stripe"], outline="",
        ))

    def bbox(self):
        return (self.x + 2, GROUND_Y - 110, self.x + self.width - 2, GROUND_Y - 70)


GROUND_OBSTACLES = [RockObstacle, BushObstacle, BarrierObstacle]
FLYING_OBSTACLES = [BranchObstacle, PillarObstacle]


# ---------------------------------------------------------------------------
# Game logo (mobile-thumbnail style, drawn with canvas primitives)
# ---------------------------------------------------------------------------
class GameLogo(tk.Canvas):
    """A mobile-game-thumbnail-style logo rendered with canvas primitives.

    Draws a framed forest scene (gradient sky, sun, clouds, hills, trees,
    grass) with a running fox character and an optional title ribbon. The
    logo is fully self-contained (no image files) so it remains
    PyInstaller-friendly and can be reused on the start and game-over screens.
    """

    def __init__(self, parent, width=300, height=150, show_title=True):
        super().__init__(
            parent, width=width, height=height,
            bg=parent["bg"], highlightthickness=0, bd=0,
        )
        self._lw = width
        self._lh = height
        self._show_title = show_title
        self._draw()

    def _draw(self):
        w, h = self._lw, self._lh
        c = self
        border = 6
        r_out = 18
        r_in = 12
        ix1, iy1 = border, border
        ix2, iy2 = w - border, h - border
        iw, ih = ix2 - ix1, iy2 - iy1

        # Drop shadow (offset down/right, drawn first so frame covers most).
        round_rect(c, 3, 5, w - 2, h - 1, r_out, fill="#33691e", outline="")
        # Outer frame / border.
        round_rect(c, 0, 0, w, h, r_out, fill=THEME["tree_leaf_dark"], outline="")
        # Inner scene base (sky top color, rounded).
        round_rect(c, ix1, iy1, ix2, iy2, r_in, fill=THEME["sky_top"], outline="")

        # Vertical sky gradient inside the inner area (narrow near rounded corners).
        self._gradient(ix1, iy1, ix2, iy2, THEME["sky_top"], THEME["sky_mid"],
                       steps=26, corner_r=r_in)

        # Ground line and ground strip.
        ground_top = iy2 - int(ih * 0.22)
        c.create_rectangle(ix1, ground_top, ix2, iy2, fill=THEME["ground"], outline="")
        c.create_rectangle(ix1, iy2 - max(3, ih * 0.05), ix2, iy2,
                           fill=THEME["ground_dark"], outline="")

        # Sun (top-right).
        sr = max(6, int(ih * 0.10))
        sx, sy = ix2 - sr * 2.4, iy1 + sr * 1.6
        c.create_oval(sx - sr, sy - sr, sx + sr, sy + sr, fill=THEME["sun"], outline="")

        # Clouds.
        self._draw_cloud(ix1 + iw * 0.22, iy1 + ih * 0.20, ih * 0.012)
        self._draw_cloud(ix1 + iw * 0.60, iy1 + ih * 0.12, ih * 0.010)

        # Hills (two layers).
        self._draw_hills(ix1, ground_top, ix2, ih * 0.10, THEME["hill_far"])
        self._draw_hills(ix1, ground_top + int(ih * 0.03), ix2, ih * 0.06,
                         THEME["hill_near"])

        # Trees on the hills.
        tree_scale = ih / 150.0
        self._draw_tree(ix1 + iw * 0.82, ground_top, tree_scale * 0.9)
        self._draw_tree(ix1 + iw * 0.12, ground_top + int(ih * 0.02), tree_scale * 0.7)

        # Running fox character standing on the ground.
        fox_scale = ih / 150.0 * 0.95
        self._draw_fox(ix1 + iw * 0.34, ground_top, fox_scale)

        # Grass blades along the ground for texture.
        for gx in range(int(ix1), int(ix2), 6):
            c.create_line(gx, ground_top, gx + 2, ground_top - 4,
                          fill=THEME["ground_dark"], width=1)

        # Title ribbon.
        if self._show_title:
            self._draw_title_ribbon(ix1, iy1, ix2, iy2, iw, ih)

        # Subtle glossy highlight along the top inner edge.
        round_rect(c, ix1 + 2, iy1 + 2, ix2 - 2, iy1 + max(4, ih * 0.10),
                   r_in - 2, fill=lerp_color(THEME["sky_top"], "#ffffff", 0.25),
                   outline="")

    def _gradient(self, x1, y1, x2, y2, top, bottom, steps=24, corner_r=0):
        for i in range(steps):
            t = i / (steps - 1)
            col = lerp_color(top, bottom, t)
            yy1 = y1 + (y2 - y1) * i / steps
            yy2 = y1 + (y2 - y1) * (i + 1) / steps
            if corner_r and (yy1 < y1 + corner_r or yy2 > y2 - corner_r):
                xx1, xx2 = x1 + corner_r, x2 - corner_r
            else:
                xx1, xx2 = x1, x2
            self.create_rectangle(xx1, yy1, xx2, yy2, fill=col, outline="")

    def _draw_cloud(self, x, y, s):
        c = self
        for dx, dy, r in [(-2, 0, 1.6), (0, -0.8, 2.0), (2, 0, 1.6)]:
            c.create_oval(x + dx * s * 4 - r * s * 4, y + dy * s * 4 - r * s * 4,
                          x + dx * s * 4 + r * s * 4, y + dy * s * 4 + r * s * 4,
                          fill="#ffffff", outline="")

    def _draw_hills(self, x1, base_y, x2, amp, color):
        pts = []
        for x in range(int(x1), int(x2) + 1, 6):
            y = base_y - amp * math.sin((x - x1) / 60.0) - amp * 0.4
            pts.extend([x, y])
        pts.extend([x2, base_y + 40, x1, base_y + 40])
        self.create_polygon(pts, fill=color, outline="")

    def _draw_tree(self, x, base_y, scale):
        c = self
        tw, th = 10 * scale, 40 * scale
        c.create_rectangle(x - tw / 2, base_y - th, x + tw / 2, base_y,
                           fill=THEME["tree_trunk"], outline="")
        for dx, dy, r in [(0, -th - 8 * scale, 22 * scale),
                          (-14 * scale, -th + 2 * scale, 16 * scale),
                          (14 * scale, -th + 2 * scale, 16 * scale)]:
            c.create_oval(x + dx - r, base_y + dy - r, x + dx + r, base_y + dy + r,
                          fill=THEME["tree_leaf_dark"], outline="")
        c.create_oval(x - 16 * scale, base_y - th - 20 * scale,
                      x + 16 * scale, base_y - th + 4 * scale,
                      fill=THEME["tree_leaf_light"], outline="")

    def _draw_fox(self, cx, cy, s):
        """Draw a mid-run fox. ``(cx, cy)`` is the foot position on the ground."""
        c = self
        ox, oy = cx, cy  # feet at oy, body extends upward (negative local y)
        # Tail (curved up behind).
        c.create_polygon(
            ox - 25 * s, oy - 40 * s, ox - 44 * s, oy - 50 * s,
            ox - 40 * s, oy - 26 * s, ox - 24 * s, oy - 30 * s,
            smooth=True, fill=THEME["player_body"], outline="",
        )
        # Legs (mid-stride: front forward, back trailing).
        c.create_rectangle(ox + 6 * s, oy - 14 * s, ox + 16 * s, oy + 2 * s,
                           fill=THEME["player_dark"], outline="")
        c.create_rectangle(ox - 16 * s, oy - 14 * s, ox - 6 * s, oy + 2 * s,
                           fill=THEME["player_dark"], outline="")
        # Arm.
        c.create_rectangle(ox - 20 * s, oy - 42 * s, ox - 11 * s, oy - 28 * s,
                           fill=THEME["player_dark"], outline="")
        # Body.
        c.create_oval(ox - 25 * s, oy - 52 * s, ox + 25 * s, oy - 12 * s,
                      fill=THEME["player_body"], outline="")
        c.create_oval(ox - 18 * s, oy - 40 * s, ox + 18 * s, oy - 16 * s,
                      fill=THEME["player_belly"], outline="")
        # Head.
        c.create_oval(ox + 2 * s, oy - 76 * s, ox + 40 * s, oy - 38 * s,
                      fill=THEME["player_body"], outline="")
        # Ears.
        c.create_polygon(ox + 2 * s, oy - 70 * s, ox + 8 * s, oy - 88 * s,
                         ox + 14 * s, oy - 68 * s, fill=THEME["player_dark"], outline="")
        c.create_polygon(ox + 16 * s, oy - 68 * s, ox + 24 * s, oy - 88 * s,
                         ox + 32 * s, oy - 70 * s, fill=THEME["player_dark"], outline="")
        # Eye + nose.
        c.create_oval(ox + 16 * s, oy - 66 * s, ox + 25 * s, oy - 58 * s,
                      fill="white", outline="")
        c.create_oval(ox + 19 * s, oy - 64 * s, ox + 23 * s, oy - 60 * s,
                      fill="#1b1b1b", outline="")
        c.create_oval(ox + 33 * s, oy - 58 * s, ox + 38 * s, oy - 53 * s,
                      fill="#1b1b1b", outline="")

    def _draw_title_ribbon(self, ix1, iy1, ix2, iy2, iw, ih):
        c = self
        rib_h = max(16, int(ih * 0.20))
        ry1 = iy2 - rib_h - 4
        ry2 = iy2 - 4
        rx1 = ix1 + 6
        rx2 = ix2 - 6
        # Ribbon shadow.
        round_rect(c, rx1 + 2, ry1 + 3, rx2 + 2, ry2 + 3, 8,
                   fill="#1b5e20", outline="")
        # Ribbon body.
        round_rect(c, rx1, ry1, rx2, ry2, 8, fill=THEME["good"], outline="")
        # Thin accent underline.
        round_rect(c, rx1, ry2 - 4, rx2, ry2, 2, fill=THEME["accent"], outline="")
        font_size = max(10, int(iw / 24))
        c.create_text((rx1 + rx2) / 2, (ry1 + ry2) / 2 + 1,
                      text="Forest Run Adventure",
                      font=("Segoe UI", font_size, "bold"), fill="white")


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
class StartScreen:
    """Title screen with logo, title, Play / Instructions / Exit buttons.

    Polished forest-adventure menu: Georgia display title with tagline and an
    accent divider, icon buttons with hover lift, a logo pop-in animation, an
    overlay rise animation, and drifting leaves for ambiance.
    """

    LEAF_COLORS = [THEME["tree_leaf_light"], THEME["accent"], "#fbc02d", THEME["tree_leaf_dark"]]

    def __init__(self, app: "GameApp"):
        self.app = app
        self.frame = tk.Frame(app.root, bg=THEME["sky_top"], width=GAME_WIDTH, height=GAME_HEIGHT)
        self.frame.pack_propagate(False)
        self._after_ids = []
        self._leaves = []
        self._leaves_running = False
        self._build()

    def _build(self):
        # Decorative canvas backdrop with floating leaves.
        self.canvas = tk.Canvas(
            self.frame, width=GAME_WIDTH, height=GAME_HEIGHT,
            bg=THEME["sky_top"], highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self._draw_backdrop()
        self._init_leaves()

        # Overlay card holding the menu content.
        self.overlay = tk.Frame(self.frame, bg=THEME["sky_top"])
        self.overlay.place(relx=0.5, rely=0.5, anchor="center")

        # Mobile-thumbnail-style game logo.
        self.logo = GameLogo(self.overlay, width=260, height=110, show_title=True)
        self.logo.grid(row=0, column=0, pady=(0, 6))

        # Two-line display title (Georgia for a storybook adventure feel).
        tk.Label(
            self.overlay, text="Forest Runner", font=("Georgia", 36, "bold"),
            fg=THEME["text_dark"], bg=THEME["sky_top"],
        ).grid(row=1, column=0, pady=(0, 0))
        tk.Label(
            self.overlay, text="Adventure", font=("Georgia", 26, "bold"),
            fg=THEME["accent"], bg=THEME["sky_top"],
        ).grid(row=2, column=0, pady=(0, 4))

        # Tagline + accent divider.
        tk.Label(
            self.overlay, text="Run  •  Jump  •  Slide  •  Survive the forest",
            font=FONT_TAGLINE, fg=THEME["text_shadow"], bg=THEME["sky_top"],
        ).grid(row=3, column=0, pady=(0, 3))
        self._divider = tk.Canvas(self.overlay, width=220, height=6,
                                  bg=THEME["sky_top"], highlightthickness=0, bd=0)
        self._divider.create_line(10, 3, 210, 3, fill=THEME["accent"], width=2)
        self._divider.grid(row=4, column=0, pady=(0, 12))

        # Icon buttons.
        HoverButton(self.overlay, "Play", command=self.app.start_game,
                    bg=THEME["good"], width=240, icon="play").grid(row=5, column=0, pady=4)
        HoverButton(self.overlay, "Instructions", command=self.app.show_instructions,
                    bg=THEME["warn"], width=240, icon="help").grid(row=6, column=0, pady=4)
        HoverButton(self.overlay, "Exit", command=self.app.quit,
                    bg=THEME["bad"], width=240, icon="exit").grid(row=7, column=0, pady=4)

        # Footer hint.
        tk.Label(
            self.frame, text="Space = Jump     ↓ = Slide     P = Pause     Esc = Quit",
            font=FONT_SMALL, fg=THEME["text_dark"], bg=THEME["sky_top"],
        ).place(relx=0.5, rely=0.98, anchor="center")

    def _draw_backdrop(self):
        c = self.canvas
        # gradient sky
        top, mid, bot = THEME["sky_top"], THEME["sky_mid"], THEME["sky_bottom"]
        steps = 40
        for i in range(steps):
            t = i / (steps - 1)
            color = lerp_color(top, mid, t * 2) if t < 0.5 \
                else lerp_color(mid, bot, (t - 0.5) * 2)
            y0 = int(i * GAME_HEIGHT / steps)
            y1 = int((i + 1) * GAME_HEIGHT / steps)
            c.create_rectangle(0, y0, GAME_WIDTH, y1, fill=color, outline="")
        # sun with soft glow
        c.create_oval(GAME_WIDTH - 150, 20, GAME_WIDTH - 30, 140,
                      fill=lerp_color(THEME["sun"], "#ffffff", 0.3), outline="")
        c.create_oval(GAME_WIDTH - 130, 40, GAME_WIDTH - 50, 120,
                      fill=THEME["sun"], outline="")
        # two hill layers
        for base, amp, col in [(GROUND_Y - 30, 34, THEME["hill_far"]),
                               (GROUND_Y - 10, 22, THEME["hill_near"])]:
            pts = []
            for x in range(0, GAME_WIDTH + 1, 16):
                pts.extend([x, base - amp * math.sin(x / 180.0)])
            pts.extend([GAME_WIDTH, GAME_HEIGHT, 0, GAME_HEIGHT])
            c.create_polygon(pts, fill=col, outline="")
        # ground
        c.create_rectangle(0, GROUND_Y, GAME_WIDTH, GAME_HEIGHT, fill=THEME["ground"], outline="")
        c.create_rectangle(0, GROUND_Y + 18, GAME_WIDTH, GAME_HEIGHT, fill=THEME["dirt"], outline="")
        # decorative trees framing the menu
        for x in [60, 180, 740, 860]:
            self._draw_tree(x, GROUND_Y)

    def _draw_tree(self, x, base_y):
        c = self.canvas
        c.create_rectangle(x - 8, base_y - 50, x + 8, base_y, fill=THEME["tree_trunk"], outline="")
        for dx, dy, r in [(0, -60, 30), (-18, -46, 22), (18, -46, 22)]:
            c.create_oval(x + dx - r, base_y + dy - r, x + dx + r, base_y + dy + r,
                          fill=THEME["tree_leaf_dark"], outline="")
        c.create_oval(x - 16, base_y - 80, x + 16, base_y - 48,
                      fill=THEME["tree_leaf_light"], outline="")

    # ---- floating leaves ambiance ----
    def _init_leaves(self):
        c = self.canvas
        for _ in range(18):
            x = random.uniform(0, GAME_WIDTH)
            y = random.uniform(-GAME_HEIGHT, GAME_HEIGHT)
            size = random.uniform(6, 12)
            color = random.choice(self.LEAF_COLORS)
            oid = c.create_polygon(
                x, y - size, x + size, y, x, y + size, x - size, y,
                fill=color, outline="",
            )
            self._leaves.append({
                "id": oid, "x": x, "y": y, "size": size,
                "vy": random.uniform(20, 55), "phase": random.uniform(0, 6.28),
                "sway": random.uniform(18, 40), "spin": random.uniform(-1.5, 1.5),
            })

    def _animate_leaves(self):
        if not self._leaves_running:
            return
        c = self.canvas
        dt = 0.03
        for leaf in self._leaves:
            leaf["phase"] += dt * 2.0
            leaf["x"] += math.sin(leaf["phase"]) * leaf["sway"] * dt
            leaf["y"] += leaf["vy"] * dt
            if leaf["y"] > GAME_HEIGHT + 20:
                leaf["y"] = -20
                leaf["x"] = random.uniform(0, GAME_WIDTH)
            c.coords(
                leaf["id"],
                leaf["x"], leaf["y"] - leaf["size"],
                leaf["x"] + leaf["size"], leaf["y"],
                leaf["x"], leaf["y"] + leaf["size"],
                leaf["x"] - leaf["size"], leaf["y"],
            )
        self._schedule(30, self._animate_leaves)

    # ---- entrance animations ----
    def _start_intro(self):
        # Overlay rises into place.
        self.overlay.place(relx=0.5, rely=0.55, anchor="center")
        # Logo pops in from 60% scale.
        self._logo_scale = 0.6
        cx, cy = self.logo._lw / 2, self.logo._lh / 2
        self.logo.scale("all", cx, cy, self._logo_scale, self._logo_scale)
        self._rise_step = 0
        self._pop_step = 0
        self._rise()
        self._pop_logo()

    def _rise(self, total=16):
        if self._rise_step >= total:
            self.overlay.place(relx=0.5, rely=0.5, anchor="center")
            return
        self._rise_step += 1
        t = self._rise_step / total
        ease = 1 - (1 - t) ** 3
        rely = 0.55 - 0.05 * ease
        self.overlay.place(relx=0.5, rely=rely, anchor="center")
        self._schedule(18, self._rise)

    def _pop_logo(self, total=14):
        if self._pop_step >= total:
            return
        self._pop_step += 1
        t = self._pop_step / total
        ease = 1 - (1 - t) ** 3
        target = 0.6 + 0.4 * ease
        factor = target / self._logo_scale
        self._logo_scale = target
        cx, cy = self.logo._lw / 2, self.logo._lh / 2
        self.logo.scale("all", cx, cy, factor, factor)
        self._schedule(20, self._pop_logo)

    # ---- scheduling helpers ----
    def _schedule(self, ms, fn):
        self._after_ids.append(self.app.root.after(ms, fn))

    def _cancel_anims(self):
        for aid in self._after_ids:
            try:
                self.app.root.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()

    def show(self):
        self.frame.pack(fill="both", expand=True)
        self._cancel_anims()
        self._leaves_running = True
        self._animate_leaves()
        self._start_intro()

    def hide(self):
        self._leaves_running = False
        self._cancel_anims()
        self.frame.pack_forget()


class InstructionsScreen:
    """Instructions / how-to-play screen."""

    def __init__(self, app: "GameApp"):
        self.app = app
        self.frame = tk.Frame(app.root, bg=THEME["panel"], width=GAME_WIDTH, height=GAME_HEIGHT)
        self.frame.pack_propagate(False)
        self._build()

    def _build(self):
        title = tk.Label(
            self.frame, text="How to Play", font=FONT_TITLE,
            fg=THEME["text_dark"], bg=THEME["panel"],
        )
        title.pack(pady=(30, 20))

        lines = [
            ("Goal", "Run as far as you can through the forest without hitting anything."),
            ("Jump", "Press SPACE to jump over rocks, bushes and barriers."),
            ("Slide", "Press DOWN ARROW to slide under branches and pillars."),
            ("Score", "Your score grows the longer you survive. Speed increases over time."),
            ("High Score", "Your best run is saved automatically and shown on Game Over."),
            ("Pause", "Press P to pause/resume during a run."),
            ("Restart", "Press R on the Game Over screen, or click Restart."),
        ]
        body = tk.Frame(self.frame, bg=THEME["panel"])
        body.pack()
        for i, (label, text) in enumerate(lines):
            color = THEME["good"] if i % 2 == 0 else THEME["warn"]
            tk.Label(
                body, text=label, font=FONT_SUBTITLE, fg=color, bg=THEME["panel"],
                width=12, anchor="w",
            ).grid(row=i, column=0, sticky="w", padx=(20, 8), pady=6)
            tk.Label(
                body, text=text, font=FONT_BODY, fg=THEME["text_dark"], bg=THEME["panel"],
                wraplength=560, anchor="w", justify="left",
            ).grid(row=i, column=1, sticky="w", pady=6)

        btn_back = HoverButton(self.frame, "Back to Menu", command=self.app.show_start,
                               bg=THEME["good"], width=220, icon="back")
        btn_back.pack(pady=24)

    def show(self):
        self.frame.pack(fill="both", expand=True)

    def hide(self):
        self.frame.pack_forget()


class GameOverScreen:
    """Overlay shown when the player collides with an obstacle."""

    def __init__(self, app: "GameApp"):
        self.app = app
        self.overlay = None

    def show(self, score: int, high_score: int, new_best: bool):
        c = self.app.game.canvas
        self.overlay = tk.Frame(c, bg=THEME["panel"], bd=2, relief="ridge")
        self.overlay.place(relx=0.5, rely=0.5, anchor="center", width=420, height=420)

        # Game logo thumbnail at the top of the overlay.
        self.logo = GameLogo(self.overlay, width=260, height=130, show_title=True)
        self.logo.pack(pady=(14, 6))

        tk.Label(
            self.overlay, text="Game Over", font=FONT_TITLE,
            fg=THEME["bad"], bg=THEME["panel"],
        ).pack(pady=(2, 6))

        if new_best:
            tk.Label(
                self.overlay, text="New High Score!", font=FONT_SUBTITLE,
                fg=THEME["good"], bg=THEME["panel"],
            ).pack(pady=2)

        info = tk.Frame(self.overlay, bg=THEME["panel"])
        info.pack(pady=6)
        tk.Label(
            info, text="Score", font=FONT_BODY, fg=THEME["text_dark"], bg=THEME["panel"],
        ).grid(row=0, column=0, padx=20)
        tk.Label(
            info, text=str(score), font=FONT_SCORE, fg=THEME["accent"], bg=THEME["panel"],
        ).grid(row=1, column=0, padx=20)
        tk.Label(
            info, text="Best", font=FONT_BODY, fg=THEME["text_dark"], bg=THEME["panel"],
        ).grid(row=0, column=1, padx=20)
        tk.Label(
            info, text=str(high_score), font=FONT_SCORE, fg=THEME["good"], bg=THEME["panel"],
        ).grid(row=1, column=1, padx=20)

        btns = tk.Frame(self.overlay, bg=THEME["panel"])
        btns.pack(pady=14)
        HoverButton(btns, "Restart", command=self.app.restart_game,
                    bg=THEME["good"], width=170, icon="restart").grid(row=0, column=0, padx=8)
        HoverButton(btns, "Menu", command=self.app.show_start,
                    bg=THEME["warn"], width=170, icon="menu").grid(row=0, column=1, padx=8)

    def hide(self):
        if self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None


# ---------------------------------------------------------------------------
# Main game screen
# ---------------------------------------------------------------------------
class GameScreen:
    """The gameplay canvas, game loop and obstacle spawning."""

    def __init__(self, app: "GameApp"):
        self.app = app
        self.frame = tk.Frame(app.root, bg="black", width=GAME_WIDTH, height=GAME_HEIGHT)
        self.frame.pack_propagate(False)
        self.canvas = tk.Canvas(
            self.frame, width=GAME_WIDTH, height=GAME_HEIGHT,
            bg=THEME["sky_top"], highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # HUD
        self.hud = tk.Frame(self.frame, bg=THEME["panel"])
        self.hud.place(x=10, y=10)
        self.score_label = tk.Label(
            self.hud, text="Score: 0", font=FONT_SCORE, fg=THEME["text_dark"], bg=THEME["panel"],
            padx=12, pady=4,
        )
        self.score_label.grid(row=0, column=0, padx=4)
        self.high_label = tk.Label(
            self.hud, text="Best: 0", font=FONT_BODY, fg=THEME["good"], bg=THEME["panel"],
            padx=12, pady=4,
        )
        self.high_label.grid(row=0, column=1, padx=4)
        self.speed_label = tk.Label(
            self.hud, text="Speed: 1.0x", font=FONT_SMALL, fg=THEME["warn"], bg=THEME["panel"],
            padx=12, pady=4,
        )
        self.speed_label.grid(row=0, column=2, padx=4)

        self.pause_label = tk.Label(
            self.frame, text="Paused  (press P to resume)", font=FONT_TITLE,
            fg="white", bg="black",
        )

        # Game state
        self.background = None
        self.player = None
        self.obstacles = []
        self.running = False
        self.paused = False
        self.game_over = False
        self.speed = BASE_SPEED
        self.spawn_timer = 0.0
        self.next_spawn = 1.6
        self.last_time = 0.0
        self._after_id = None

    def reset(self):
        """Clear the canvas and (re)initialise a fresh run."""
        self.canvas.delete("all")
        self.obstacles.clear()
        self.speed = BASE_SPEED
        self.spawn_timer = 0.0
        self.next_spawn = 1.6
        self.game_over = False
        self.paused = False
        self.pause_label.place_forget()
        self.app.score.reset()
        self.background = ForestBackground(self.canvas)
        self.player = Player(self.canvas)
        self._update_hud()

    def start(self):
        self.reset()
        self.running = True
        self.last_time = time.perf_counter()
        self._loop()

    def stop(self):
        self.running = False
        if self._after_id is not None:
            self.app.root.after_cancel(self._after_id)
            self._after_id = None

    def _loop(self):
        if not self.running:
            return
        now = time.perf_counter()
        dt = min(now - self.last_time, 1.0 / 30.0)
        self.last_time = now
        if not self.paused and not self.game_over:
            self._update(dt)
        self._after_id = self.app.root.after(int(1000 / FPS), self._loop)

    def _update(self, dt: float):
        # Difficulty rises slowly: +1 speed per 600 score points, capped at +6.
        self.speed = BASE_SPEED + min(6.0, self.app.score.score / 600.0)
        self.background.update(self.speed)
        self.player.update(dt, self.app.sound)

        # Score from distance
        self.app.score.add(self.speed * dt * 4.0)

        # Spawn obstacles
        self.spawn_timer += dt
        if self.spawn_timer >= self.next_spawn:
            self.spawn_timer = 0.0
            self._spawn_obstacle()
            # next spawn tightens gently as speed rises
            base = max(0.9, 1.8 - (self.speed - BASE_SPEED) * 0.05)
            self.next_spawn = base + random.uniform(0.0, 0.8)

        # Move obstacles and check collisions
        for ob in list(self.obstacles):
            ob.move(self.speed)
            if ob.off_screen():
                ob.destroy()
                self.obstacles.remove(ob)
                continue
            if self._collides(self.player.bbox(), ob.bbox()):
                self._on_hit()
                break

        self._update_hud()

    def _spawn_obstacle(self):
        x = GAME_WIDTH + 40
        # Mix ground and flying; avoid impossible combos by spacing
        if random.random() < 0.6:
            cls = random.choice(GROUND_OBSTACLES)
        else:
            cls = random.choice(FLYING_OBSTACLES)
        ob = cls(self.canvas, x)
        self.obstacles.append(ob)

    @staticmethod
    def _collides(a, b):
        return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])

    def _on_hit(self):
        self.game_over = True
        self.player.alive = False
        self.app.sound.hit()
        new_best = self.app.score.commit()
        self.app.game_over_screen.show(
            int(self.app.score.score), self.app.score.high_score, new_best
        )

    def _update_hud(self):
        self.score_label.config(text=f"Score: {int(self.app.score.score)}")
        self.high_label.config(text=f"Best: {self.app.score.high_score}")
        mult = self.speed / BASE_SPEED
        self.speed_label.config(text=f"Speed: {mult:.1f}x")

    def toggle_pause(self):
        if self.game_over or not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.pause_label.place_forget()

    def show(self):
        self.frame.pack(fill="both", expand=True)

    def hide(self):
        self.stop()
        self.frame.pack_forget()


# ---------------------------------------------------------------------------
# Top-level application controller
# ---------------------------------------------------------------------------
class GameApp:
    """Wire the screens together and handle global key bindings."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Forest Runner Adventure")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.sound = SoundManager()
        self.score = ScoreManager()

        self.start_screen = StartScreen(self)
        self.instructions_screen = InstructionsScreen(self)
        self.game = GameScreen(self)
        self.game_over_screen = GameOverScreen(self)

        self._current = None
        self.show_start()

        self.root.bind("<space>", self._on_space)
        self.root.bind("<Down>", self._on_down)
        self.root.bind("<p>", self._on_pause)
        self.root.bind("<P>", self._on_pause)
        self.root.bind("<r>", self._on_restart)
        self.root.bind("<R>", self._on_restart)
        self.root.bind("<Escape>", self._on_escape)

    # ---- screen switching ----
    def _switch(self, screen):
        if self._current is not None:
            self._current.hide()
        screen.show()
        self._current = screen

    def show_start(self):
        self.sound.click()
        self.game_over_screen.hide()
        self._switch(self.start_screen)

    def show_instructions(self):
        self.sound.click()
        self._switch(self.instructions_screen)

    def start_game(self):
        self.sound.click()
        self.game_over_screen.hide()
        self._switch(self.game)
        self.game.start()

    def restart_game(self):
        self.sound.click()
        self.game_over_screen.hide()
        self.game.start()

    def quit(self):
        self.sound.click()
        self.root.destroy()

    # ---- key handlers ----
    def _on_space(self, _):
        if self._current is self.game and self.game.running:
            self.game.player.jump(self.sound)

    def _on_down(self, _):
        if self._current is self.game and self.game.running:
            self.game.player.slide(self.sound)

    def _on_pause(self, _):
        if self._current is self.game:
            self.game.toggle_pause()

    def _on_restart(self, _):
        if self._current is self.game and self.game.game_over:
            self.restart_game()

    def _on_escape(self, _):
        if self._current is self.game:
            self.game.stop()
            self.show_start()
        elif self._current is self.instructions_screen:
            self.show_start()
        else:
            self.quit()

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    GameApp().run()


if __name__ == "__main__":
    main()