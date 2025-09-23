#!/usr/bin/env python3
"""Space Avaders: Star Cascade.

An aspirational side-scrolling reinterpretation of the original arcade homage.
Early console shooters like Gradius, Thunder Force, and Phantasy Zone inspired
this update: the action now scrolls endlessly across a luminous skyline, waves
arrive in choreographed patterns, and flashy power-ups let the player bend the
run to their style. Everything is rendered with procedural geometry and
particle effects—no art assets required, just pygame.

Run with ``python3 space_invaders.py`` after installing pygame::

    pip install pygame
"""
from __future__ import annotations

import array
import math
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pygame


# --- Configuration -----------------------------------------------------------------

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 720
FPS = 60

PLAYER_WIDTH = 66
PLAYER_HEIGHT = 40
PLAYER_SPEED = 320
PLAYER_FIRE_COOLDOWN = 0.22
PLAYER_BULLET_SPEED = 640
PLAYER_LIVES = 3
PLAYER_INVULNERABLE_TIME = 2.0
PLAYER_BOOST_MULTIPLIER = 1.45
PLAYER_MULTI_DURATION = 12.0
PLAYER_SHIELD_DURATION = 7.0
PLAYER_FLUX_DURATION = 8.0

SCROLL_SPEED_BASE = 160

PLAYER_BULLET_DAMAGE = 1
ENEMY_BULLET_DAMAGE = 1

ENEMY_BASE_SPEED = 190
ENEMY_SPEED_PER_STAGE = 18

BACKGROUND_GRADIENT_TOP = (12, 8, 34)
BACKGROUND_GRADIENT_BOTTOM = (2, 2, 12)
PLAYER_COLOR = (120, 200, 255)
PLAYER_GLOW_COLOR = (80, 160, 255)
PLAYER_BULLET_COLOR = (255, 230, 170)
ENEMY_BULLET_COLOR = (255, 150, 150)
HUD_COLOR = (230, 235, 250)

STAR_COUNT = 120
STAR_COLORS = [
    (220, 220, 255),
    (160, 180, 255),
    (120, 120, 210),
]
SPARK_COLORS = [
    (255, 210, 180),
    (255, 170, 130),
    (255, 240, 200),
    (170, 255, 220),
]

POWERUP_SETTINGS: Dict[str, Dict[str, object]] = {
    "trident": {"color": (255, 200, 120), "symbol": "≡"},
    "shield": {"color": (150, 220, 255), "symbol": "◎"},
    "flux": {"color": (180, 255, 200), "symbol": "↯"},
}

STAGE_NAMES = [
    "Orbital Rush",
    "Nebula Slipstream",
    "Crystal Mire",
    "Skyline Rebellion",
    "Edge of Dawn",
]


# --- Helper utilities --------------------------------------------------------------


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return (int(lerp(a[0], b[0], t)), int(lerp(a[1], b[1], t)), int(lerp(a[2], b[2], t)))


def lighten(color: Tuple[int, int, int], amount: float) -> Tuple[int, int, int]:
    return tuple(int(c + (255 - c) * amount) for c in color)


def darken(color: Tuple[int, int, int], amount: float) -> Tuple[int, int, int]:
    return tuple(int(c * (1 - amount)) for c in color)


# --- Helper data structures ---------------------------------------------------------


@dataclass
class Particle:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    lifetime: float
    color: pygame.Color
    radius: float = 2.0
    fade: float = 1.0
    gravity: float = 0.0
    initial_lifetime: float = field(init=False)

    def __post_init__(self) -> None:
        self.initial_lifetime = self.lifetime

    def update(self, dt: float) -> bool:
        self.velocity.y += self.gravity * dt
        self.pos += self.velocity * dt
        self.lifetime -= dt
        return self.lifetime > 0

    def draw(self, surface: pygame.Surface) -> None:
        if self.lifetime <= 0:
            return
        life_ratio = max(0.0, min(1.0, self.lifetime / self.initial_lifetime))
        alpha = max(0, min(255, int(255 * (life_ratio ** self.fade))))
        radius = max(1, int(self.radius * (0.5 + 0.5 * life_ratio)))
        color = pygame.Color(self.color)
        color.a = alpha
        pygame.draw.circle(surface, color, (int(self.pos.x), int(self.pos.y)), radius)


@dataclass
class Star:
    pos: pygame.Vector2
    speed: float
    color: pygame.Color
    radius: float
    twinkle_speed: float
    phase: float

    def update(self, dt: float, scroll_speed: float) -> None:
        self.pos.x -= (self.speed + scroll_speed * 0.3) * dt
        if self.pos.x < -5:
            self.pos.x = SCREEN_WIDTH + 5
            self.pos.y = random.uniform(0, SCREEN_HEIGHT)
            self.speed = random.uniform(40, 160)
            self.radius = random.uniform(1.0, 2.3)
            self.twinkle_speed = random.uniform(0.8, 2.4)
            self.phase = random.uniform(0, math.tau)

    def draw(self, surface: pygame.Surface, time_accumulator: float) -> None:
        twinkle = 0.6 + 0.4 * math.sin(self.phase + time_accumulator * self.twinkle_speed)
        alpha = int(150 + 100 * twinkle)
        color = pygame.Color(self.color)
        color.a = alpha
        pygame.draw.circle(surface, color, (int(self.pos.x), int(self.pos.y)), max(1, int(self.radius)))


@dataclass
class Bullet:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    damage: int
    color: pygame.Color
    size: Tuple[int, int]
    from_player: bool
    glow_radius: int = 18
    rect: pygame.Rect = field(init=False)

    def __post_init__(self) -> None:
        self.rect = pygame.Rect(0, 0, self.size[0], self.size[1])
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def update(self, dt: float) -> None:
        self.pos += self.velocity * dt
        self.rect.center = (int(self.pos.x), int(self.pos.y))


@dataclass
class PowerUp:
    kind: str
    pos: pygame.Vector2
    velocity: pygame.Vector2
    color: pygame.Color
    symbol: str
    wobble: float = field(default_factory=lambda: random.uniform(0, math.tau))
    timer: float = 0.0
    rect: pygame.Rect = field(init=False)

    def __post_init__(self) -> None:
        self.rect = pygame.Rect(0, 0, 34, 34)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def update(self, dt: float) -> bool:
        self.timer += dt
        self.pos += self.velocity * dt
        bob = math.sin(self.wobble + self.timer * 3.2) * 4
        self.rect.center = (int(self.pos.x), int(self.pos.y + bob))
        return self.rect.right > -80 and self.rect.left < SCREEN_WIDTH + 80 and -120 < self.rect.centery < SCREEN_HEIGHT + 120


@dataclass
class TextPopup:
    text: str
    pos: pygame.Vector2
    velocity: pygame.Vector2
    lifetime: float
    color: pygame.Color
    initial_lifetime: float = field(init=False)

    def __post_init__(self) -> None:
        self.initial_lifetime = self.lifetime

    def update(self, dt: float) -> bool:
        self.pos += self.velocity * dt
        self.lifetime -= dt
        return self.lifetime > 0

    def alpha(self) -> int:
        if self.initial_lifetime <= 0:
            return 0
        ratio = max(0.0, min(1.0, self.lifetime / self.initial_lifetime))
        return int(255 * (ratio ** 1.2))


@dataclass
class Enemy:
    kind: str
    pos: pygame.Vector2
    velocity: pygame.Vector2
    health: int
    score: int
    behavior: str
    width: int
    height: int
    color: pygame.Color
    glow_color: pygame.Color
    amplitude: float = 0.0
    frequency: float = 1.0
    fire_interval: Optional[Tuple[float, float]] = None
    bullet_speed: float = 0.0
    aim_player: bool = False
    shot_kind: str = "forward"
    spin: float = 0.0
    wobble_phase: float = field(default_factory=lambda: random.uniform(0, math.tau))
    fire_timer: float = 0.0
    rotation: float = 0.0
    anchor_y: float = 0.0
    time_alive: float = 0.0
    hit_flash: float = 0.0
    trail_timer: float = 0.0
    rect: pygame.Rect = field(init=False)
    max_health: int = field(init=False)

    def __post_init__(self) -> None:
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.anchor_y = self.pos.y
        self.max_health = self.health
        if self.fire_interval:
            self.fire_timer = random.uniform(*self.fire_interval)

    def apply_damage(self, amount: int) -> bool:
        self.health = max(0, self.health - amount)
        self.hit_flash = 0.3
        return self.health <= 0

    def update(self, dt: float, game: "Game") -> bool:
        self.time_alive += dt
        self.hit_flash = max(0.0, self.hit_flash - dt * 4)
        if self.behavior == "sine":
            self.pos.x += self.velocity.x * dt
            self.pos.y = self.anchor_y + math.sin(self.time_alive * self.frequency + self.wobble_phase) * self.amplitude
        elif self.behavior == "loop":
            self.pos.x += self.velocity.x * dt
            base = self.anchor_y + math.sin((self.time_alive + self.wobble_phase) * self.frequency) * self.amplitude
            self.pos.y = base + math.sin(self.time_alive * 0.7 + self.wobble_phase) * 22
        elif self.behavior == "dive":
            self.pos += self.velocity * dt
            if self.time_alive > 1.0:
                direction = pygame.Vector2(game.player_rect.center) - self.pos
                if direction.length_squared() > 0:
                    direction = direction.normalize()
                    self.pos += direction * self.velocity.length() * 0.6 * dt
        elif self.behavior == "bomber":
            self.pos += self.velocity * dt
            self.pos.y += math.sin(self.time_alive * 1.7 + self.wobble_phase) * 12
        elif self.behavior == "meteor":
            self.pos += self.velocity * dt
            if self.spin:
                self.rotation = (self.rotation + self.spin * dt) % math.tau
        elif self.behavior == "drift":
            self.pos += self.velocity * dt
        else:
            self.pos += self.velocity * dt
        if self.spin and self.behavior not in {"meteor"}:
            self.rotation = (self.rotation + self.spin * dt) % math.tau
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.fire_interval:
            self.fire_timer -= dt
            if self.fire_timer <= 0:
                self.fire_timer = random.uniform(*self.fire_interval)
                self.fire(game)
        if self.kind in {"fighter", "serpent", "ranger"}:
            self.trail_timer += dt
            if self.trail_timer >= 0.09:
                self.trail_timer = 0.0
                game.spawn_enemy_trail(self)
        return self.rect.right > -160 and self.rect.left < SCREEN_WIDTH + 200 and self.rect.bottom > -200 and self.rect.top < SCREEN_HEIGHT + 200

    def fire(self, game: "Game") -> None:
        if self.bullet_speed <= 0:
            return
        if self.shot_kind == "aim" and game.player_rect:
            direction = pygame.Vector2(game.player_rect.center) - self.pos
        elif self.shot_kind == "down":
            direction = pygame.Vector2(0, 1)
        elif self.shot_kind == "spray":
            sway = math.sin(self.time_alive * 2.0 + self.wobble_phase)
            direction = pygame.Vector2(-1, sway * 0.6)
        else:
            direction = pygame.Vector2(-1, 0)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(-1, 0)
        direction = direction.normalize()
        velocity = direction * self.bullet_speed
        if self.shot_kind == "down":
            color = pygame.Color(255, 200, 120)
            size = (10, 20)
        elif self.shot_kind == "spray":
            color = pygame.Color(255, 120, 220)
            size = (16, 8)
        else:
            color = pygame.Color(*ENEMY_BULLET_COLOR)
            size = (18, 6)
        bullet = Bullet(
            pos=self.pos.copy(),
            velocity=velocity,
            damage=ENEMY_BULLET_DAMAGE,
            color=color,
            size=size,
            from_player=False,
            glow_radius=24,
        )
        game.enemy_bullets.append(bullet)
        game.audio.play("laser", 0.5)

    def draw(self, game: "Game") -> None:
        surface = game.render_surface
        base_rect = self.rect.copy()
        base_rect.y += int(math.sin(game.time_accumulator * 2.4 + self.wobble_phase) * 2)
        game.draw_glow(surface, base_rect.center, max(base_rect.width, base_rect.height), self.glow_color)
        color = pygame.Color(self.color)
        if self.kind == "fighter":
            nose = (base_rect.right - 6, base_rect.centery)
            tail_top = (base_rect.left + 8, base_rect.top + 6)
            tail_bottom = (base_rect.left + 8, base_rect.bottom - 6)
            wing_top = (base_rect.centerx, base_rect.top + 4)
            wing_bottom = (base_rect.centerx, base_rect.bottom - 4)
            pygame.draw.polygon(surface, color, [tail_top, nose, tail_bottom, wing_bottom, wing_top])
            accent = pygame.Color(lighten(self.glow_color, 0.25))
            pygame.draw.polygon(surface, accent, [
                (base_rect.centerx - 6, base_rect.centery - 6),
                (base_rect.right - 14, base_rect.centery),
                (base_rect.centerx - 6, base_rect.centery + 6),
            ])
        elif self.kind == "serpent":
            segments = 6
            for i in range(segments):
                t = i / max(1, segments - 1)
                radius = int(base_rect.height * (0.4 + 0.2 * math.sin(self.time_alive * 3 + i * 0.6)))
                cx = base_rect.left + int(t * base_rect.width)
                cy = base_rect.centery + int(math.sin(self.time_alive * 2.4 + i) * 18)
                pygame.draw.circle(surface, color, (cx, cy), max(6, radius))
            pygame.draw.circle(surface, lighten(self.glow_color, 0.3), (base_rect.right - 8, base_rect.centery), max(6, base_rect.height // 3))
        elif self.kind == "bomber":
            body_rect = base_rect.inflate(-8, -4)
            pygame.draw.ellipse(surface, color, body_rect)
            stripe = pygame.Rect(body_rect.left + 12, body_rect.centery - 6, body_rect.width - 40, 12)
            pygame.draw.rect(surface, lighten(self.glow_color, 0.25), stripe, border_radius=6)
            engine_rect = pygame.Rect(body_rect.left - 8, body_rect.centery - 10, 18, 20)
            pygame.draw.rect(surface, lighten(color, 0.15), engine_rect, border_radius=6)
        elif self.kind == "spinner":
            center = base_rect.center
            radius = base_rect.width // 2
            pygame.draw.circle(surface, color, center, radius)
            blade_color = pygame.Color(lighten(self.glow_color, 0.3))
            for i in range(3):
                angle = self.rotation + i * (math.tau / 3)
                end = (
                    center[0] + math.cos(angle) * radius * 1.1,
                    center[1] + math.sin(angle) * radius * 1.1,
                )
                pygame.draw.line(surface, blade_color, center, end, width=4)
            core_radius = max(6, radius // 2)
            pygame.draw.circle(surface, lighten(color, 0.2), center, core_radius)
        elif self.kind == "meteor":
            center = base_rect.center
            radius = base_rect.width // 2
            points: List[Tuple[float, float]] = []
            segments = 8
            for i in range(segments):
                angle = self.rotation + i / segments * math.tau
                noise = 0.7 + 0.3 * math.sin(self.wobble_phase + i * 1.2)
                r = radius * noise
                points.append((center[0] + math.cos(angle) * r, center[1] + math.sin(angle) * r))
            pygame.draw.polygon(surface, color, points)
            pygame.draw.polygon(surface, darken(color, 0.4), points, width=2)
        else:
            pygame.draw.rect(surface, color, base_rect, border_radius=8)
        if self.hit_flash > 0:
            flash_alpha = int(160 * self.hit_flash)
            overlay = pygame.Surface((base_rect.width, base_rect.height), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, flash_alpha))
            surface.blit(overlay, base_rect)
        if self.max_health > 1 and self.health > 0:
            ratio = self.health / self.max_health
            bar_bg = pygame.Rect(base_rect.x, base_rect.y - 8, base_rect.width, 4)
            pygame.draw.rect(surface, (20, 30, 60), bar_bg)
            bar = bar_bg.copy()
            bar.width = max(0, int(bar.width * ratio))
            pygame.draw.rect(surface, lighten(self.glow_color, 0.2), bar)


# --- Audio -------------------------------------------------------------------------


class AudioManager:
    def __init__(self) -> None:
        self.enabled = False
        self.master_volume = 0.7
        self.muted = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.music_sound: Optional[pygame.mixer.Sound] = None
        self.music_channel: Optional[pygame.mixer.Channel] = None
        self.effect_channels: List[pygame.mixer.Channel] = []
        self._channel_index = 0
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(8)
            self.music_channel = pygame.mixer.Channel(0)
            self.effect_channels = [pygame.mixer.Channel(i) for i in range(1, 8)]
            self.enabled = True
            self._load_assets()
        except pygame.error:
            self.enabled = False

    def _generate_tone(self, frequencies: Tuple[float, ...], duration: float, volume: float) -> pygame.mixer.Sound:
        sample_rate = 44100
        samples = int(duration * sample_rate)
        buffer = array.array("h")
        for i in range(samples):
            t = i / sample_rate
            sample = 0.0
            for freq in frequencies:
                sample += math.sin(2 * math.pi * freq * t)
            sample /= len(frequencies)
            sample *= volume
            sample = max(-1.0, min(1.0, sample))
            buffer.append(int(sample * 32767))
        return pygame.mixer.Sound(buffer=buffer)

    def _generate_noise(self, duration: float, volume: float) -> pygame.mixer.Sound:
        sample_rate = 44100
        samples = int(duration * sample_rate)
        buffer = array.array("h")
        for _ in range(samples):
            sample = random.uniform(-1.0, 1.0) * volume
            buffer.append(int(sample * 32767))
        return pygame.mixer.Sound(buffer=buffer)

    def _generate_music(self) -> pygame.mixer.Sound:
        sample_rate = 44100
        duration = 6.0
        samples = int(duration * sample_rate)
        buffer = array.array("h")
        progression = [196, 247, 294, 392, 262, 330, 392, 523]
        beat = int(sample_rate * 0.375)
        for i in range(samples):
            step = (i // beat) % len(progression)
            freq = progression[step]
            t = i / sample_rate
            envelope = 0.5 + 0.5 * math.sin(math.pi * ((i % beat) / beat))
            pad = math.sin(2 * math.pi * (freq / 2) * t) * 0.2
            arp = math.sin(2 * math.pi * freq * t) * 0.35
            bass = math.sin(2 * math.pi * (freq / 4) * t) * 0.15
            sample = (pad + arp + bass) * envelope
            buffer.append(int(max(-1.0, min(1.0, sample)) * 32767))
        return pygame.mixer.Sound(buffer=buffer)

    def _load_assets(self) -> None:
        if not self.enabled:
            return
        self.sounds["laser"] = self._generate_tone((720.0, 880.0), 0.1, 0.6)
        self.sounds["hit"] = self._generate_tone((180.0, 320.0), 0.08, 0.5)
        self.sounds["explosion"] = self._generate_noise(0.18, 0.35)
        self.sounds["shield"] = self._generate_tone((260.0, 200.0), 0.12, 0.5)
        self.sounds["powerup"] = self._generate_tone((660.0, 990.0, 1320.0), 0.16, 0.45)
        self.music_sound = self._generate_music()
        if self.music_channel and self.music_sound:
            self.music_channel.play(self.music_sound, loops=-1)
            self.music_channel.set_volume(self.master_volume * 0.7)

    def play(self, name: str, volume_scale: float = 1.0) -> None:
        if not self.enabled or name not in self.sounds:
            return
        channel = None
        for _ in range(len(self.effect_channels)):
            idx = self._channel_index % len(self.effect_channels)
            self._channel_index += 1
            candidate = self.effect_channels[idx]
            if not candidate.get_busy():
                channel = candidate
                break
        if channel is None and self.effect_channels:
            channel = self.effect_channels[0]
        if channel is None:
            return
        volume = 0.0 if self.muted else max(0.0, min(1.0, self.master_volume * volume_scale))
        channel.set_volume(volume)
        channel.play(self.sounds[name])

    def toggle_mute(self) -> None:
        if not self.enabled:
            return
        self.muted = not self.muted
        self._refresh_music_volume()

    def adjust_volume(self, delta: float) -> None:
        if not self.enabled:
            return
        self.master_volume = max(0.0, min(1.0, self.master_volume + delta))
        self._refresh_music_volume()

    def _refresh_music_volume(self) -> None:
        if not self.enabled or not self.music_channel:
            return
        volume = 0.0 if self.muted else self.master_volume * 0.7
        self.music_channel.set_volume(volume)


# --- Game implementation ------------------------------------------------------------


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Space Avaders: Star Cascade")
        self.window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        self.window_size = self.window.get_size()
        self.render_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 22)
        self.small_font = pygame.font.SysFont("consolas", 18)
        self.big_font = pygame.font.SysFont("consolas", 48)
        self.title_font = pygame.font.SysFont("consolas", 70)

        self.audio = AudioManager()

        self.time_accumulator = 0.0
        self.glow_cache: Dict[Tuple[int, Tuple[int, int, int]], pygame.Surface] = {}

        self.background_surface = self._create_background_surface()
        self.parallax_layers: List[pygame.Surface] = []
        self.parallax_offsets: List[float] = []
        self.parallax_speeds: List[float] = []
        self._create_parallax_layers()

        self.stars: List[Star] = []
        self._setup_stars()

        self.player_surface = self._create_player_surface()
        self.player_rect = pygame.Rect(0, 0, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.player_pos = pygame.Vector2(140, SCREEN_HEIGHT // 2)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        self.player_velocity = pygame.Vector2(0, 0)
        self.player_cooldown = 0.0
        self.player_invulnerable = 0.0
        self.player_tilt = 0.0
        self.player_thruster_timer = 0.0
        self.player_multishot_timer = 0.0
        self.player_shield_timer = 0.0
        self.player_flux_timer = 0.0

        self.player_bullets: List[Bullet] = []
        self.enemy_bullets: List[Bullet] = []

        self.particles: List[Particle] = []
        self.powerups: List[PowerUp] = []
        self.popups: List[TextPopup] = []

        self.enemies: List[Enemy] = []
        self.stage = 1
        self.stage_time = 0.0
        self.stage_duration = 0.0
        self.wave_schedule: List[Dict[str, object]] = []
        self.wave_index = 0

        self.scroll_speed = SCROLL_SPEED_BASE
        self.distance = 0.0

        self.score = 0
        self.lives = PLAYER_LIVES
        self.combo = 0
        self.combo_timer = 0.0

        self.banner_text = ""
        self.banner_timer = 0.0
        self.title_timer = 0.0

        self.state = "title"
        self.fullscreen = False

        self.reset_run()

    # -- Setup ---------------------------------------------------------------------

    def reset_run(self) -> None:
        self.score = 0
        self.distance = 0.0
        self.lives = PLAYER_LIVES
        self.stage = 1
        self.stage_time = 0.0
        self.stage_duration = self._compute_stage_duration()
        self.wave_schedule = self._build_wave_schedule()
        self.wave_index = 0
        self.scroll_speed = SCROLL_SPEED_BASE
        self.combo = 0
        self.combo_timer = 0.0
        self.player_pos = pygame.Vector2(140, SCREEN_HEIGHT // 2)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        self.player_invulnerable = 0.0
        self.player_cooldown = 0.0
        self.player_tilt = 0.0
        self.player_thruster_timer = 0.0
        self.player_multishot_timer = 0.0
        self.player_shield_timer = 0.0
        self.player_flux_timer = 0.0
        self.player_bullets.clear()
        self.enemy_bullets.clear()
        self.enemies.clear()
        self.particles.clear()
        self.powerups.clear()
        self.popups.clear()
        self.banner_text = self._stage_banner()
        self.banner_timer = 4.0

    def _stage_banner(self) -> str:
        name = STAGE_NAMES[(self.stage - 1) % len(STAGE_NAMES)] if STAGE_NAMES else f"Stage {self.stage}"
        if self.stage > len(STAGE_NAMES):
            name = f"Stellar Loop {self.stage - len(STAGE_NAMES)}"
        return f"STAGE {self.stage} · {name.upper()}"

    def _compute_stage_duration(self) -> float:
        return max(28.0, 42.0 - (self.stage - 1) * 2.5)

    def _create_background_surface(self) -> pygame.Surface:
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            color = lerp_color(BACKGROUND_GRADIENT_TOP, BACKGROUND_GRADIENT_BOTTOM, t)
            pygame.draw.line(surface, color, (0, y), (SCREEN_WIDTH, y))
        return surface.convert()

    def _create_parallax_layers(self) -> None:
        rng = random.Random(1337)
        self.parallax_layers.clear()
        self.parallax_offsets.clear()
        self.parallax_speeds.clear()
        for idx in range(3):
            layer = pygame.Surface((SCREEN_WIDTH * 2, SCREEN_HEIGHT), pygame.SRCALPHA)
            if idx == 0:
                for _ in range(12):
                    radius = rng.randint(60, 220)
                    x = rng.randint(-100, layer.get_width() + 100)
                    y = rng.randint(-80, SCREEN_HEIGHT // 2)
                    color = pygame.Color(40, 30, 70, rng.randint(30, 60))
                    pygame.draw.circle(layer, color, (x, y), radius)
                for _ in range(6):
                    rect = pygame.Rect(0, 0, rng.randint(120, 280), rng.randint(18, 38))
                    rect.center = (rng.randint(0, layer.get_width()), rng.randint(80, SCREEN_HEIGHT // 2 + 120))
                    color = pygame.Color(80, 60, 140, 70)
                    pygame.draw.ellipse(layer, color, rect)
            elif idx == 1:
                base_y = SCREEN_HEIGHT - 180
                step = 120
                for i in range(-2, int(layer.get_width() / step) + 4):
                    x = i * step + rng.randint(-40, 40)
                    height = rng.randint(60, 180)
                    color = pygame.Color(80 + rng.randint(0, 40), 70 + rng.randint(0, 30), 140 + rng.randint(0, 30), 120)
                    rect = pygame.Rect(x, base_y - height, 50, height)
                    pygame.draw.rect(layer, color, rect, border_radius=12)
                    for j in range(3):
                        window_y = rect.bottom - 14 - j * 22
                        pygame.draw.rect(layer, pygame.Color(255, 200, 120, 120), (rect.x + 10, window_y, rect.width - 20, 8), border_radius=3)
            else:
                base_y = SCREEN_HEIGHT - 70
                points: List[Tuple[int, int]] = []
                for x in range(-120, layer.get_width() + 120, 40):
                    y = base_y + int(math.sin(x * 0.04 + rng.random()) * 24)
                    points.append((x, y))
                points.append((layer.get_width(), SCREEN_HEIGHT))
                points.append((0, SCREEN_HEIGHT))
                pygame.draw.polygon(layer, pygame.Color(50, 40, 80, 220), points)
                for _ in range(80):
                    x = rng.randint(0, layer.get_width())
                    y = rng.randint(base_y - 10, base_y + 30)
                    color = pygame.Color(255, 200, 120, rng.randint(80, 160))
                    pygame.draw.circle(layer, color, (x, y), rng.randint(1, 3))
            self.parallax_layers.append(layer)
            self.parallax_offsets.append(0.0)
            speed_factor = 0.25 + idx * 0.25
            self.parallax_speeds.append(SCROLL_SPEED_BASE * speed_factor)

    def _setup_stars(self) -> None:
        self.stars = []
        for _ in range(STAR_COUNT):
            pos = pygame.Vector2(random.uniform(0, SCREEN_WIDTH), random.uniform(0, SCREEN_HEIGHT))
            speed = random.uniform(40, 160)
            color = pygame.Color(*random.choice(STAR_COLORS))
            radius = random.uniform(1.0, 2.4)
            twinkle_speed = random.uniform(0.8, 2.0)
            phase = random.uniform(0, math.tau)
            self.stars.append(Star(pos=pos, speed=speed, color=color, radius=radius, twinkle_speed=twinkle_speed, phase=phase))

    def _create_player_surface(self) -> pygame.Surface:
        surface = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)
        body_color_top = lighten(PLAYER_COLOR, 0.3)
        body_color_bottom = darken(PLAYER_COLOR, 0.35)
        for y in range(PLAYER_HEIGHT):
            t = y / max(1, PLAYER_HEIGHT - 1)
            color = lerp_color(body_color_top, body_color_bottom, t)
            pygame.draw.line(surface, color, (10, y), (PLAYER_WIDTH - 6, y))
        canopy = pygame.Rect(0, 0, PLAYER_WIDTH // 2, PLAYER_HEIGHT // 2)
        canopy.center = (PLAYER_WIDTH // 2 + 6, PLAYER_HEIGHT // 2)
        pygame.draw.ellipse(surface, (255, 255, 255, 90), canopy)
        wing_color = lighten(PLAYER_COLOR, 0.5)
        pygame.draw.polygon(surface, wing_color, [
            (8, PLAYER_HEIGHT // 2),
            (PLAYER_WIDTH // 2, 4),
            (PLAYER_WIDTH - 12, PLAYER_HEIGHT // 2),
            (PLAYER_WIDTH // 2, PLAYER_HEIGHT - 4),
        ])
        return surface

    # -- Main loop ------------------------------------------------------------------

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                if not self.fullscreen:
                    self.window = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                self.window_size = self.window.get_size()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state in {"title", "game_over"}:
                        self.start_game()
                if event.key == pygame.K_m:
                    self.audio.toggle_mute()
                if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.audio.adjust_volume(-0.1)
                if event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    self.audio.adjust_volume(0.1)
                if event.key == pygame.K_f:
                    self.toggle_fullscreen()

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        self.window_size = self.window.get_size()

    def start_game(self) -> None:
        self.reset_run()
        self.state = "playing"

    # -- Update loop ----------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self.state == "playing":
            self.update_playing(dt)
        elif self.state == "title":
            self.update_title(dt)
        elif self.state == "game_over":
            self.update_game_over(dt)

    def update_title(self, dt: float) -> None:
        self.time_accumulator += dt
        self.title_timer += dt
        self.update_background(dt)
        self.update_stars(dt)
        self.update_particles(dt)
        self.update_popups(dt)
        if self.banner_timer > 0:
            self.banner_timer = max(0.0, self.banner_timer - dt)

    def update_game_over(self, dt: float) -> None:
        self.time_accumulator += dt
        self.update_background(dt)
        self.update_stars(dt)
        self.update_particles(dt)
        self.update_popups(dt)
        if self.banner_timer > 0:
            self.banner_timer = max(0.0, self.banner_timer - dt)

    def update_playing(self, dt: float) -> None:
        self.time_accumulator += dt
        target_speed = SCROLL_SPEED_BASE + (self.stage - 1) * 18
        self.scroll_speed = lerp(self.scroll_speed, target_speed, min(1.0, dt * 0.5))
        self.stage_time += dt
        self.distance += self.scroll_speed * dt

        self.update_background(dt)
        self.update_stars(dt)
        self.update_player(dt)
        self.update_player_bullets(dt)
        self.update_enemies(dt)
        self.update_enemy_bullets(dt)
        self.update_powerups(dt)
        self.update_particles(dt)
        self.update_popups(dt)

        self._trigger_waves()

        if self.player_invulnerable > 0:
            self.player_invulnerable = max(0.0, self.player_invulnerable - dt)
        if self.player_multishot_timer > 0:
            self.player_multishot_timer = max(0.0, self.player_multishot_timer - dt)
        if self.player_shield_timer > 0:
            self.player_shield_timer = max(0.0, self.player_shield_timer - dt)
        if self.player_flux_timer > 0:
            self.player_flux_timer = max(0.0, self.player_flux_timer - dt)
        if self.player_cooldown > 0:
            self.player_cooldown = max(0.0, self.player_cooldown - dt)
        if self.banner_timer > 0:
            self.banner_timer = max(0.0, self.banner_timer - dt)
        if self.combo_timer > 0:
            self.combo_timer = max(0.0, self.combo_timer - dt)
            if self.combo_timer <= 0:
                self.combo = 0

        if self.wave_index >= len(self.wave_schedule) and not self.enemies and self.stage_time >= self.stage_duration:
            self._start_next_stage()

    def update_background(self, dt: float) -> None:
        for i, speed in enumerate(self.parallax_speeds):
            width = self.parallax_layers[i].get_width()
            self.parallax_offsets[i] = (self.parallax_offsets[i] + speed * dt) % width

    def update_stars(self, dt: float) -> None:
        for star in self.stars:
            star.update(dt, self.scroll_speed)

    def update_player(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        move = pygame.Vector2(0, 0)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move.x -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move.x += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move.y -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move.y += 1
        if move.length_squared() > 0:
            move = move.normalize()
        speed = PLAYER_SPEED
        if self.player_flux_timer > 0:
            speed *= 1.2
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            speed *= PLAYER_BOOST_MULTIPLIER
        self.player_pos += move * speed * dt
        self.player_pos.x = max(70, min(SCREEN_WIDTH * 0.7, self.player_pos.x))
        self.player_pos.y = max(70, min(SCREEN_HEIGHT - 70, self.player_pos.y))
        previous_x = self.player_rect.centerx
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        delta_x = self.player_rect.centerx - previous_x
        self.player_tilt = lerp(self.player_tilt, -delta_x * 0.4, min(1.0, dt * 10))

        fire_pressed = keys[pygame.K_SPACE] or keys[pygame.K_z]
        if fire_pressed and self.player_cooldown <= 0:
            base_cooldown = PLAYER_FIRE_COOLDOWN * (0.75 if self.player_flux_timer > 0 else 1.0)
            self.fire_player_bullets()
            self.player_cooldown = base_cooldown

        self.player_thruster_timer += dt
        thruster_rate = 0.055
        if self.player_flux_timer > 0:
            thruster_rate *= 0.7
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            thruster_rate *= 0.6
        while self.player_thruster_timer >= thruster_rate:
            self.player_thruster_timer -= thruster_rate
            self.spawn_thruster_particles()

    def update_player_bullets(self, dt: float) -> None:
        for bullet in self.player_bullets[:]:
            bullet.update(dt)
            if bullet.rect.left > SCREEN_WIDTH + 80 or bullet.rect.bottom < -80 or bullet.rect.top > SCREEN_HEIGHT + 80:
                self.player_bullets.remove(bullet)
                continue
            hit_enemy = None
            for enemy in self.enemies:
                if bullet.rect.colliderect(enemy.rect):
                    hit_enemy = enemy
                    break
            if hit_enemy:
                destroyed = hit_enemy.apply_damage(PLAYER_BULLET_DAMAGE)
                self.spawn_hit_sparks(pygame.Vector2(bullet.rect.center), color=(hit_enemy.glow_color.r, hit_enemy.glow_color.g, hit_enemy.glow_color.b))
                self.audio.play("hit", 0.5)
                if destroyed:
                    self.destroy_enemy(hit_enemy, by_player=True)
                    if hit_enemy in self.enemies:
                        self.enemies.remove(hit_enemy)
                self.player_bullets.remove(bullet)
                continue

    def update_enemies(self, dt: float) -> None:
        for enemy in self.enemies[:]:
            alive = enemy.update(dt, self)
            if not alive or enemy.rect.right < -160 or enemy.rect.top > SCREEN_HEIGHT + 200 or enemy.rect.bottom < -200:
                self.enemies.remove(enemy)
                continue
            if enemy.rect.colliderect(self.player_rect):
                if self.player_shield_timer > 0:
                    self.spawn_hit_sparks(pygame.Vector2(enemy.rect.center), color=(enemy.color.r, enemy.color.g, enemy.color.b))
                    self.destroy_enemy(enemy, by_player=True)
                    if enemy in self.enemies:
                        self.enemies.remove(enemy)
                    self.player_shield_timer = max(0.0, self.player_shield_timer - 2.0)
                    self.spawn_shield_burst()
                else:
                    self.destroy_enemy(enemy, by_player=False)
                    if enemy in self.enemies:
                        self.enemies.remove(enemy)
                    self.damage_player("ram")

    def update_enemy_bullets(self, dt: float) -> None:
        for bullet in self.enemy_bullets[:]:
            bullet.update(dt)
            if bullet.rect.right < -80 or bullet.rect.left > SCREEN_WIDTH + 80 or bullet.rect.bottom < -80 or bullet.rect.top > SCREEN_HEIGHT + 80:
                self.enemy_bullets.remove(bullet)
                continue
            if bullet.rect.colliderect(self.player_rect):
                self.spawn_hit_sparks(pygame.Vector2(bullet.rect.center), color=(255, 150, 150))
                self.enemy_bullets.remove(bullet)
                self.damage_player("bullet")

    def update_powerups(self, dt: float) -> None:
        for powerup in self.powerups[:]:
            if not powerup.update(dt):
                self.powerups.remove(powerup)
                continue
            if powerup.rect.colliderect(self.player_rect):
                self.apply_powerup(powerup.kind)
                self.spawn_text_popup(powerup.kind.upper(), pygame.Vector2(powerup.rect.centerx, powerup.rect.centery - 20), color=powerup.color)
                self.audio.play("powerup", 0.6)
                self.powerups.remove(powerup)

    def update_particles(self, dt: float) -> None:
        alive_particles = []
        for particle in self.particles:
            if particle.update(dt):
                alive_particles.append(particle)
        self.particles = alive_particles

    def update_popups(self, dt: float) -> None:
        alive = []
        for popup in self.popups:
            if popup.update(dt):
                alive.append(popup)
        self.popups = alive

    def _trigger_waves(self) -> None:
        while self.wave_index < len(self.wave_schedule) and self.stage_time >= self.wave_schedule[self.wave_index]["time"]:
            info = self.wave_schedule[self.wave_index]
            self.spawn_wave(info)
            self.wave_index += 1

    def _start_next_stage(self) -> None:
        self.stage += 1
        self.stage_time = 0.0
        self.stage_duration = self._compute_stage_duration()
        self.wave_schedule = self._build_wave_schedule()
        self.wave_index = 0
        self.scroll_speed = SCROLL_SPEED_BASE + (self.stage - 1) * 14
        self.combo = 0
        self.combo_timer = 0.0
        self.banner_text = self._stage_banner()
        self.banner_timer = 4.0
        if self.stage % 2 == 0 and self.lives < 5:
            self.lives += 1
            self.spawn_text_popup("+1 LIFE", pygame.Vector2(self.player_rect.centerx + 20, self.player_rect.centery - 60), color=pygame.Color(150, 220, 255))

    def fire_player_bullets(self) -> None:
        count = 3 if self.player_multishot_timer > 0 else 1
        offsets = [0]
        if count == 3:
            offsets = [-12, 0, 12]
        for offset in offsets:
            direction = pygame.Vector2(1.0, offset * 0.04)
            direction = direction.normalize()
            speed = PLAYER_BULLET_SPEED * (1.1 if self.player_flux_timer > 0 else 1.0)
            bullet = Bullet(
                pos=pygame.Vector2(self.player_rect.right + 8, self.player_rect.centery + offset),
                velocity=direction * speed,
                damage=PLAYER_BULLET_DAMAGE,
                color=pygame.Color(*PLAYER_BULLET_COLOR),
                size=(18, 8),
                from_player=True,
                glow_radius=28,
            )
            self.player_bullets.append(bullet)
        self.spawn_muzzle_flash(pygame.Vector2(self.player_rect.right + 12, self.player_rect.centery))
        self.audio.play("laser", 0.8)

    def spawn_thruster_particles(self) -> None:
        tail = pygame.Vector2(self.player_rect.left - 12, self.player_rect.centery)
        flux = self.player_flux_timer > 0
        for _ in range(2):
            velocity = pygame.Vector2(random.uniform(-180, -80), random.uniform(-80, 80))
            color = pygame.Color(255, random.randint(160, 210), random.randint(100, 150))
            if flux:
                color = pygame.Color(180, 255, 220)
            particle = Particle(
                pos=tail.copy(),
                velocity=velocity,
                lifetime=random.uniform(0.25, 0.45),
                color=color,
                radius=random.uniform(2.4, 3.4),
                fade=1.6,
            )
            self.particles.append(particle)

    def spawn_muzzle_flash(self, position: pygame.Vector2) -> None:
        for _ in range(12):
            velocity = pygame.Vector2(random.uniform(120, 240), random.uniform(-120, 120))
            particle = Particle(
                pos=position.copy(),
                velocity=velocity,
                lifetime=0.22,
                color=pygame.Color(255, 230, 180),
                radius=random.uniform(2.0, 3.5),
                fade=1.8,
            )
            self.particles.append(particle)

    def spawn_hit_sparks(self, position: pygame.Vector2, color: Optional[Tuple[int, int, int]] = None) -> None:
        base_color = pygame.Color(*(color or random.choice(SPARK_COLORS)))
        for _ in range(10):
            velocity = pygame.Vector2(random.uniform(-200, 200), random.uniform(-200, 200))
            particle = Particle(
                pos=position.copy(),
                velocity=velocity,
                lifetime=random.uniform(0.25, 0.5),
                color=base_color,
                radius=random.uniform(1.8, 3.0),
                fade=1.7,
            )
            self.particles.append(particle)

    def spawn_explosion(self, position: pygame.Vector2, sparks: int = 40) -> None:
        for _ in range(sparks):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(80, 320)
            velocity = pygame.Vector2(math.cos(angle) * speed, math.sin(angle) * speed)
            color = pygame.Color(*random.choice(SPARK_COLORS))
            particle = Particle(
                pos=position.copy(),
                velocity=velocity,
                lifetime=random.uniform(0.4, 0.9),
                color=color,
                radius=random.uniform(2.0, 4.5),
                fade=1.6,
            )
            self.particles.append(particle)

    def spawn_shield_burst(self) -> None:
        center = pygame.Vector2(self.player_rect.center)
        for _ in range(30):
            angle = random.uniform(0, math.tau)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(120, 220)
            particle = Particle(
                pos=center.copy(),
                velocity=velocity,
                lifetime=random.uniform(0.3, 0.6),
                color=pygame.Color(150, 220, 255),
                radius=random.uniform(2.0, 3.2),
                fade=1.5,
            )
            self.particles.append(particle)

    def spawn_enemy_trail(self, enemy: Enemy) -> None:
        tail = pygame.Vector2(enemy.rect.centerx + enemy.rect.width * 0.4, enemy.rect.centery)
        velocity = pygame.Vector2(random.uniform(40, 120), random.uniform(-40, 40))
        particle = Particle(
            pos=tail,
            velocity=velocity,
            lifetime=random.uniform(0.25, 0.45),
            color=enemy.glow_color,
            radius=random.uniform(1.6, 2.4),
            fade=1.5,
        )
        self.particles.append(particle)

    def spawn_text_popup(self, text: str, position: pygame.Vector2, velocity: Optional[pygame.Vector2] = None, color: Optional[pygame.Color] = None) -> None:
        vel = velocity or pygame.Vector2(-40, -30)
        popup_color = color or pygame.Color(255, 240, 200)
        popup = TextPopup(text=text, pos=position.copy(), velocity=vel, lifetime=1.4, color=popup_color)
        self.popups.append(popup)

    def spawn_powerup(self, kind: str, position: pygame.Vector2) -> None:
        settings = POWERUP_SETTINGS.get(kind)
        if not settings:
            return
        velocity = pygame.Vector2(-(self.scroll_speed * 0.6), 0)
        powerup = PowerUp(
            kind=kind,
            pos=position.copy(),
            velocity=velocity,
            color=pygame.Color(*settings["color"]),
            symbol=str(settings["symbol"]),
        )
        self.powerups.append(powerup)

    def apply_powerup(self, kind: str) -> None:
        if kind == "trident":
            self.player_multishot_timer = PLAYER_MULTI_DURATION
        elif kind == "shield":
            self.player_shield_timer = PLAYER_SHIELD_DURATION
            self.spawn_shield_burst()
        elif kind == "flux":
            self.player_flux_timer = PLAYER_FLUX_DURATION
        self.combo_timer = max(self.combo_timer, 2.0)

    def maybe_drop_powerup(self, enemy: Enemy) -> None:
        drop_chance = 0.12 + 0.02 * self.stage
        if enemy.kind == "meteor":
            drop_chance *= 0.5
        if random.random() < drop_chance:
            kind = random.choices(["trident", "shield", "flux"], weights=[3, 2, 2])[0]
            self.spawn_powerup(kind, pygame.Vector2(enemy.rect.center))

    def destroy_enemy(self, enemy: Enemy, by_player: bool = True) -> None:
        if by_player:
            self.combo += 1
            self.combo_timer = 4.0
        else:
            self.combo = 0
            self.combo_timer = 0.0
        stage_bonus = 1 + (self.stage - 1) * 0.05
        combo_bonus = 1 + max(0, self.combo - 1) * 0.1 if by_player else 1.0
        score_gain = int(enemy.score * stage_bonus * combo_bonus)
        self.score += score_gain
        self.spawn_explosion(pygame.Vector2(enemy.rect.center), sparks=32 + enemy.max_health * 4)
        text_color = pygame.Color(enemy.glow_color)
        self.spawn_text_popup(f"+{score_gain}", pygame.Vector2(enemy.rect.centerx, enemy.rect.centery - 20), color=text_color)
        if by_player and self.combo > 1 and self.combo % 4 == 0:
            self.spawn_text_popup(f"COMBO x{self.combo}", pygame.Vector2(enemy.rect.centerx + 10, enemy.rect.centery - 70), color=pygame.Color(255, 210, 120))
        if by_player:
            self.maybe_drop_powerup(enemy)
        self.audio.play("explosion", 0.7)

    def damage_player(self, reason: str) -> None:
        if self.player_shield_timer > 0:
            self.player_shield_timer = max(0.0, self.player_shield_timer - 2.5)
            self.spawn_shield_burst()
            self.audio.play("shield", 0.6)
            return
        if self.player_invulnerable > 0:
            return
        self.combo = 0
        self.combo_timer = 0.0
        self.lives -= 1
        self.player_invulnerable = PLAYER_INVULNERABLE_TIME
        self.spawn_explosion(pygame.Vector2(self.player_rect.center), sparks=70)
        self.audio.play("explosion", 0.9)
        self.player_pos = pygame.Vector2(140, SCREEN_HEIGHT // 2)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        if self.lives <= 0:
            self.state = "game_over"
            self.banner_text = "MISSION FAILED"
            self.banner_timer = 3.0

    def _build_wave_schedule(self) -> List[Dict[str, object]]:
        rng = random.Random(self.stage * 8731)
        script: List[Dict[str, object]] = []
        time_cursor = 2.0
        wave_types = ["fighters", "serpents", "bombers", "rangers", "spinners"]
        weights = [5, 3, 2 + self.stage, 4, max(1, self.stage - 1)]
        for _ in range(5 + self.stage):
            wave = rng.choices(wave_types, weights=weights, k=1)[0]
            script.append({"time": time_cursor, "type": wave})
            spacing = max(1.6, 3.4 - self.stage * 0.18) + rng.uniform(-0.3, 0.5)
            time_cursor += spacing
        script.append({"time": time_cursor + 3.0, "type": "meteor_shower"})
        return script

    def spawn_wave(self, wave: Dict[str, object]) -> None:
        wave_type = wave.get("type")
        stage_speed = ENEMY_BASE_SPEED + (self.stage - 1) * ENEMY_SPEED_PER_STAGE
        if wave_type == "fighters":
            count = 6 + self.stage
            base_y = random.uniform(140, SCREEN_HEIGHT - 160)
            for i in range(count):
                x = SCREEN_WIDTH + 70 + i * 56
                y = base_y + math.sin(i * 0.6) * (26 + self.stage * 2)
                self.spawn_enemy(
                    kind="fighter",
                    position=(x, y),
                    velocity=(-(stage_speed + 40), 0),
                    health=1 + self.stage // 3,
                    score=120 + self.stage * 10,
                    behavior="sine",
                    size=(52, 32),
                    color=(255, 150, 120),
                    glow_color=(255, 190, 160),
                    amplitude=28 + self.stage * 2,
                    frequency=2.5,
                    fire_interval=(2.0, 3.0),
                    bullet_speed=360 + self.stage * 18,
                    shot_kind="aim",
                )
        elif wave_type == "serpents":
            count = 4 + self.stage // 2
            base_y = random.uniform(160, SCREEN_HEIGHT - 160)
            for i in range(count):
                x = SCREEN_WIDTH + 90 + i * 90
                y = base_y + math.sin(i * 0.9) * 80
                self.spawn_enemy(
                    kind="serpent",
                    position=(x, y),
                    velocity=(-(stage_speed - 20), 0),
                    health=2 + self.stage // 2,
                    score=160 + self.stage * 14,
                    behavior="loop",
                    size=(92, 48),
                    color=(120, 255, 190),
                    glow_color=(180, 255, 210),
                    amplitude=70 + self.stage * 5,
                    frequency=1.5,
                )
        elif wave_type == "bombers":
            count = 2 + max(1, self.stage // 2)
            for i in range(count):
                x = SCREEN_WIDTH + 140 + i * 220
                y = random.uniform(160, SCREEN_HEIGHT - 200)
                self.spawn_enemy(
                    kind="bomber",
                    position=(x, y),
                    velocity=(-(stage_speed - 60), 0),
                    health=4 + self.stage,
                    score=280 + self.stage * 40,
                    behavior="bomber",
                    size=(104, 68),
                    color=(255, 210, 120),
                    glow_color=(255, 180, 90),
                    fire_interval=(1.6, 2.4),
                    bullet_speed=240 + self.stage * 12,
                    shot_kind="down",
                )
        elif wave_type == "rangers":
            count = 7 + self.stage
            base_y = random.uniform(120, SCREEN_HEIGHT - 140)
            for i in range(count):
                x = SCREEN_WIDTH + 60 + i * 48
                vy = math.sin(i * 0.6 + self.stage) * 60
                self.spawn_enemy(
                    kind="fighter",
                    position=(x, base_y + (i % 2) * 36 - 18),
                    velocity=(-(stage_speed + 80), vy),
                    health=1 + max(0, self.stage // 4),
                    score=150 + self.stage * 12,
                    behavior="drift",
                    size=(48, 30),
                    color=(255, 120, 200),
                    glow_color=(255, 170, 220),
                    fire_interval=(1.4, 2.2),
                    bullet_speed=340 + self.stage * 20,
                    shot_kind="spray",
                    spin=1.2,
                )
        elif wave_type == "spinners":
            count = 1 + self.stage // 2
            for i in range(count):
                x = SCREEN_WIDTH + 220 + i * 220
                y = random.uniform(200, SCREEN_HEIGHT - 220)
                self.spawn_enemy(
                    kind="spinner",
                    position=(x, y),
                    velocity=(-(stage_speed - 70), 0),
                    health=3 + self.stage,
                    score=260 + self.stage * 30,
                    behavior="sine",
                    size=(84, 84),
                    color=(180, 140, 255),
                    glow_color=(220, 180, 255),
                    amplitude=24,
                    frequency=1.2,
                    fire_interval=(1.0, 1.6),
                    bullet_speed=320 + self.stage * 18,
                    shot_kind="spray",
                    spin=2.0,
                )
        elif wave_type == "meteor_shower":
            count = 5 + self.stage
            for _ in range(count):
                x = SCREEN_WIDTH + random.uniform(0, 220)
                y = random.uniform(100, SCREEN_HEIGHT - 100)
                velocity = (-random.uniform(stage_speed * 0.8, stage_speed * 1.2), random.uniform(-40, 40))
                self.spawn_enemy(
                    kind="meteor",
                    position=(x, y),
                    velocity=velocity,
                    health=2 + self.stage // 2,
                    score=140 + self.stage * 16,
                    behavior="meteor",
                    size=(64, 64),
                    color=(180, 160, 140),
                    glow_color=(255, 200, 120),
                    spin=random.uniform(-2.6, 2.6),
                )

    def spawn_enemy(
        self,
        *,
        kind: str,
        position: Tuple[float, float],
        velocity: Tuple[float, float],
        health: int,
        score: int,
        behavior: str,
        size: Tuple[int, int],
        color: Tuple[int, int, int],
        glow_color: Tuple[int, int, int],
        amplitude: float = 0.0,
        frequency: float = 1.0,
        fire_interval: Optional[Tuple[float, float]] = None,
        bullet_speed: float = 0.0,
        shot_kind: str = "forward",
        spin: float = 0.0,
    ) -> None:
        enemy = Enemy(
            kind=kind,
            pos=pygame.Vector2(position),
            velocity=pygame.Vector2(velocity),
            health=health,
            score=score,
            behavior=behavior,
            width=size[0],
            height=size[1],
            color=pygame.Color(*color),
            glow_color=pygame.Color(*glow_color),
            amplitude=amplitude,
            frequency=frequency,
            fire_interval=fire_interval,
            bullet_speed=bullet_speed,
            shot_kind=shot_kind,
            spin=spin,
        )
        self.enemies.append(enemy)

    # -- Drawing --------------------------------------------------------------------

    def draw(self) -> None:
        self.render_surface.blit(self.background_surface, (0, 0))
        self.draw_parallax()

        for star in self.stars:
            star.draw(self.render_surface, self.time_accumulator)

        for powerup in self.powerups:
            self.draw_powerup(powerup)

        for enemy in self.enemies:
            enemy.draw(self)

        for bullet in self.player_bullets:
            self.draw_bullet(bullet)
        for bullet in self.enemy_bullets:
            self.draw_bullet(bullet)

        self.draw_player()

        for particle in self.particles:
            particle.draw(self.render_surface)

        self.draw_popups()
        self.draw_hud()

        if self.state == "title":
            self.draw_title()
        elif self.state == "game_over":
            self.draw_game_over()

        if self.banner_timer > 0 and self.banner_text:
            self.draw_banner()

        scaled = pygame.transform.smoothscale(self.render_surface, self.window_size)
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def draw_parallax(self) -> None:
        for layer, offset in zip(self.parallax_layers, self.parallax_offsets):
            width = layer.get_width()
            x = int(offset % width)
            self.render_surface.blit(layer, (-x, 0))
            if x > 0:
                self.render_surface.blit(layer, (width - x, 0))

    def draw_player(self) -> None:
        blink = True
        if self.state == "playing" and self.player_invulnerable > 0:
            blink = int(self.player_invulnerable * 10) % 2 == 0
        if not blink:
            return
        center = self.player_rect.center
        glow_color = pygame.Color(PLAYER_GLOW_COLOR)
        if self.player_flux_timer > 0:
            glow_color = pygame.Color(170, 255, 210)
        self.draw_glow(self.render_surface, center, 60, glow_color)
        tilt = max(-12, min(12, self.player_tilt))
        rotated = pygame.transform.rotate(self.player_surface, tilt)
        rect = rotated.get_rect(center=center)
        self.render_surface.blit(rotated, rect)
        flame_color = pygame.Color(255, 200, 130)
        if self.player_flux_timer > 0:
            flame_color = pygame.Color(180, 255, 220)
        flame = [
            (self.player_rect.left - 18, self.player_rect.centery - 6),
            (self.player_rect.left - 18, self.player_rect.centery + 6),
            (self.player_rect.left - 4, self.player_rect.centery + int(10 * math.sin(self.time_accumulator * 16))),
        ]
        pygame.draw.polygon(self.render_surface, flame_color, flame)
        if self.player_shield_timer > 0:
            radius = int(40 + 6 * math.sin(self.time_accumulator * 6))
            shield_color = pygame.Color(150, 220, 255)
            shield_color.a = 140
            pygame.draw.circle(self.render_surface, shield_color, center, radius, width=3)

    def draw_powerup(self, powerup: PowerUp) -> None:
        self.draw_glow(self.render_surface, powerup.rect.center, 50, powerup.color)
        pygame.draw.circle(self.render_surface, powerup.color, powerup.rect.center, 18)
        glyph = self.small_font.render(powerup.symbol, True, pygame.Color(10, 10, 24))
        glyph_rect = glyph.get_rect(center=powerup.rect.center)
        self.render_surface.blit(glyph, glyph_rect)

    def draw_bullet(self, bullet: Bullet) -> None:
        self.draw_glow(self.render_surface, bullet.rect.center, bullet.glow_radius, bullet.color)
        pygame.draw.rect(
            self.render_surface,
            bullet.color,
            bullet.rect,
            border_radius=max(3, bullet.rect.height // 2),
        )

    def draw_glow(
        self,
        surface: pygame.Surface,
        position: Tuple[int, int],
        radius: int,
        color: Tuple[int, int, int] | pygame.Color,
    ) -> None:
        radius = max(4, radius)
        if isinstance(color, pygame.Color):
            color_rgb = (color.r, color.g, color.b)
        else:
            color_rgb = color
        key = (radius, color_rgb)
        glow = self.glow_cache.get(key)
        if glow is None:
            glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            for r in range(radius, 0, -1):
                alpha = int(255 * (1 - (r / radius)) ** 2)
                pygame.draw.circle(glow, (*color_rgb, alpha), (radius, radius), r)
            self.glow_cache[key] = glow
        rect = glow.get_rect(center=position)
        surface.blit(glow, rect)

    def draw_hud(self) -> None:
        score_text = self.font.render(f"SCORE {self.score:07d}", True, HUD_COLOR)
        distance_text = self.font.render(f"DIST {self.distance / 1000.0:05.1f} Mm", True, HUD_COLOR)
        stage_text = self.font.render(f"STAGE {self.stage}", True, HUD_COLOR)
        lives_text = self.font.render(f"LIVES {self.lives}", True, HUD_COLOR)
        self.render_surface.blit(score_text, (24, 18))
        self.render_surface.blit(distance_text, (24, 48))
        self.render_surface.blit(stage_text, (SCREEN_WIDTH // 2 - stage_text.get_width() // 2, 18))
        self.render_surface.blit(lives_text, (SCREEN_WIDTH - lives_text.get_width() - 24, 18))
        if self.combo > 1:
            combo_text = self.small_font.render(f"COMBO x{self.combo}", True, pygame.Color(255, 210, 120))
            self.render_surface.blit(combo_text, (SCREEN_WIDTH - combo_text.get_width() - 24, 52))
        status_x = SCREEN_WIDTH - 220
        offset_y = 80
        if self.player_multishot_timer > 0:
            multi_text = self.small_font.render(f"TRIDENT {self.player_multishot_timer:4.1f}s", True, pygame.Color(255, 200, 120))
            self.render_surface.blit(multi_text, (status_x, offset_y))
            offset_y += 24
        if self.player_shield_timer > 0:
            shield_text = self.small_font.render(f"SHIELD {self.player_shield_timer:4.1f}s", True, pygame.Color(150, 220, 255))
            self.render_surface.blit(shield_text, (status_x, offset_y))
            offset_y += 24
        if self.player_flux_timer > 0:
            flux_text = self.small_font.render(f"FLUX {self.player_flux_timer:4.1f}s", True, pygame.Color(180, 255, 200))
            self.render_surface.blit(flux_text, (status_x, offset_y))

    def draw_title(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.render_surface.blit(overlay, (0, 0))
        title = self.title_font.render("STAR CASCADE", True, pygame.Color(255, 240, 200))
        subtitle = self.font.render("A console-era dream of speed and color", True, HUD_COLOR)
        prompt = self.font.render(
            "Press Enter / Space to launch",
            True,
            pygame.Color(255, 220, 160 if int(self.title_timer * 2) % 2 == 0 else 120),
        )
        self.render_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 200))
        self.render_surface.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, SCREEN_HEIGHT // 2 - 130))
        controls = [
            "Move: Arrow keys or WASD",
            "Fire: Space or Z",
            "Boost: Hold Shift",
            "Toggle fullscreen: F",
            "Mute: M    Volume: - / +",
        ]
        for i, text in enumerate(controls):
            line = self.small_font.render(text, True, HUD_COLOR)
            self.render_surface.blit(line, (SCREEN_WIDTH // 2 - line.get_width() // 2, SCREEN_HEIGHT // 2 - 40 + i * 28))
        self.render_surface.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT // 2 + 150))

    def draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.render_surface.blit(overlay, (0, 0))
        title = self.big_font.render("MISSION FAILED", True, pygame.Color(255, 180, 160))
        score_text = self.font.render(f"Score {self.score:07d}", True, HUD_COLOR)
        distance_text = self.font.render(f"Distance {self.distance / 1000.0:05.1f} Mm", True, HUD_COLOR)
        prompt = self.font.render("Press Enter to try again", True, HUD_COLOR)
        self.render_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 140))
        self.render_surface.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, SCREEN_HEIGHT // 2 - 60))
        self.render_surface.blit(distance_text, (SCREEN_WIDTH // 2 - distance_text.get_width() // 2, SCREEN_HEIGHT // 2 - 10))
        self.render_surface.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT // 2 + 120))

    def draw_banner(self) -> None:
        ratio = min(1.0, self.banner_timer / 4.0)
        alpha = int(200 * ratio)
        banner = pygame.Surface((SCREEN_WIDTH, 110), pygame.SRCALPHA)
        banner.fill((10, 10, 30, alpha))
        self.render_surface.blit(banner, (0, 60))
        text = self.big_font.render(self.banner_text, True, pygame.Color(255, 230, 180))
        self.render_surface.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 90))

    def draw_popups(self) -> None:
        for popup in self.popups:
            alpha = popup.alpha()
            if alpha <= 0:
                continue
            surface = self.small_font.render(popup.text, True, popup.color)
            surface.set_alpha(alpha)
            self.render_surface.blit(surface, (int(popup.pos.x), int(popup.pos.y)))


# --- Entrypoint --------------------------------------------------------------------


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
