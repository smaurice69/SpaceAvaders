#!/usr/bin/env python3
"""Space Avaders - a spruced-up Space-Invaders inspired clone.

The game now riffs on early console-era side-scrollers:
    * A constantly scrolling starfield with wide-open space lanes to dodge through.
    * Waves of hand-scripted enemy patterns, from sine-surfing scouts to diving raiders and sentry towers.
    * A mini boss encounter each sector and momentum that escalates speed and spectacle every stage.
    * Procedurally shaded sprites, glowing bullets, and light-weight particle effects.
    * A tiny procedural audio soundscape with music, lasers, and explosions.
    * Smooth HD scaling so the action looks crisp in windowed or fullscreen.

Run with ``python3 space_invaders.py`` after installing pygame::

    pip install pygame
"""
from __future__ import annotations

import array
import math
import random
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pygame


# --- Configuration -----------------------------------------------------------------

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
FPS = 60

PLAYFIELD_MARGIN_X = 80
PLAYFIELD_MARGIN_Y = 70

SCROLL_SPEED_START = 160
SCROLL_SPEED_STEP = 18
SCROLL_SPEED_MAX = 320

PLAYER_SPEED = 320
PLAYER_FOCUS_SPEED = 210
PLAYER_WIDTH = 72
PLAYER_HEIGHT = 34
PLAYER_COOLDOWN = 0.22  # seconds between shots
PLAYER_LIVES = 3
PLAYER_INVULNERABLE_TIME = 1.5

BULLET_SPEED = 680
ENEMY_BULLET_SPEED = 260
PLAYER_BULLET_DAMAGE = 1
ENEMY_BULLET_DAMAGE = 1

ENEMY_WIDTH = 52
ENEMY_HEIGHT = 36

STAR_COUNT = 140

BACKGROUND_GRADIENT_TOP = (6, 10, 22)
BACKGROUND_GRADIENT_BOTTOM = (2, 2, 12)
PLAYER_COLOR = (80, 200, 255)
PLAYER_GLOW_COLOR = (50, 140, 255)
PLAYER_BULLET_COLOR = (255, 230, 150)
ENEMY_COLOR_SETS = [
    ((120, 240, 180), (60, 190, 150)),
    ((255, 190, 120), (255, 120, 90)),
    ((255, 110, 180), (210, 70, 210)),
    ((180, 180, 255), (110, 140, 255)),
    ((255, 150, 120), (255, 210, 120)),
]
ENEMY_BULLET_COLOR = (255, 150, 150)
HUD_COLOR = (240, 240, 240)
SPARK_COLORS = [
    (255, 200, 150),
    (255, 170, 120),
    (255, 255, 200),
]
STAR_COLORS = [
    (180, 180, 255),
    (120, 120, 220),
    (90, 90, 170),
]
SECTOR_NAMES = [
    "Crystal Drift",
    "Nebula Run",
    "Luminous Reef",
    "Quantum Causeway",
    "Aurora Crusade",
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
    x: float
    y: float
    speed: float
    color: pygame.Color
    radius: float
    twinkle_speed: float
    phase: float
    parallax: float

    def update(self, dt: float, scroll_speed: float) -> None:
        self.x -= (self.speed + scroll_speed * self.parallax) * dt
        if self.x < -10:
            self.x = SCREEN_WIDTH + random.uniform(5, 40)
            self.y = random.uniform(-20, SCREEN_HEIGHT + 20)
            self.speed = random.uniform(20, 80)
            self.radius = random.uniform(1.0, 2.6)
            self.twinkle_speed = random.uniform(0.8, 2.4)
            self.phase = random.uniform(0, math.tau)
            self.parallax = random.uniform(0.25, 1.0)

    def draw(self, surface: pygame.Surface, time_accumulator: float) -> None:
        twinkle = 0.6 + 0.4 * math.sin(self.phase + time_accumulator * self.twinkle_speed)
        alpha = int(120 + 110 * twinkle)
        color = pygame.Color(self.color)
        color.a = alpha
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), int(self.radius))


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
class Enemy:
    surface: pygame.Surface
    pos: pygame.Vector2
    velocity: pygame.Vector2
    max_health: int
    health: int
    pattern: str
    amplitude: float = 0.0
    frequency: float = 1.0
    phase: float = 0.0
    shoot_range: Optional[Tuple[float, float]] = (1.6, 3.2)
    next_shot: float = -1.0
    score: int = 100
    hit_flash: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)
    rect: pygame.Rect = field(init=False)
    base_pos: pygame.Vector2 = field(init=False)
    timer: float = 0.0

    def __post_init__(self) -> None:
        self.rect = self.surface.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self.base_pos = pygame.Vector2(self.pos)
        if self.shoot_range is None:
            self.next_shot = math.inf
        elif self.next_shot <= 0:
            self.reset_shoot_timer()

    def reset_shoot_timer(self) -> None:
        if self.shoot_range is None:
            self.next_shot = math.inf
        else:
            low, high = self.shoot_range
            self.next_shot = random.uniform(low, high)

    def apply_damage(self, amount: int, impact_point: Optional[Tuple[int, int]]) -> bool:
        self.health = max(0, self.health - amount)
        self.hit_flash = 0.25
        if impact_point is not None:
            local_x = max(0, min(self.surface.get_width() - 1, impact_point[0] - self.rect.x))
            local_y = max(0, min(self.surface.get_height() - 1, impact_point[1] - self.rect.y))
            radius = random.randint(5, 9)
            crater = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(crater, (200, 200, 210, 255), (radius, radius), radius)
            self.surface.blit(
                crater,
                (local_x - radius, local_y - radius),
                special_flags=pygame.BLEND_RGBA_SUB,
            )
            outline = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(outline, (40, 40, 70, 140), (radius, radius), radius, width=2)
            self.surface.blit(outline, (local_x - radius, local_y - radius))
        return self.health <= 0

    def update(self, dt: float, scroll_speed: float) -> None:
        self.timer += dt
        self.pos.x += (self.velocity.x - scroll_speed) * dt
        self.pos.y += self.velocity.y * dt
        anchor_y = self.extra.get("anchor_y", self.base_pos.y)
        if self.pattern == "sine":
            self.pos.y = anchor_y + math.sin(self.timer * self.frequency + self.phase) * self.amplitude
        elif self.pattern == "zigzag":
            period = self.extra.get("period", 1.1)
            direction = -1 if int(self.timer / max(0.01, period)) % 2 else 1
            self.pos.y = anchor_y + direction * self.amplitude
        elif self.pattern == "dive":
            delay = self.extra.get("dive_delay", 0.6)
            if self.timer > delay:
                self.velocity.y = self.extra.get("dive_speed", 220)
        elif self.pattern == "hover":
            target = self.extra.get("target_y", anchor_y)
            self.pos.y = lerp(self.pos.y, target, min(1.0, dt * 2.4))
        elif self.pattern == "boss":
            swing = self.extra.get("swing", 130)
            self.pos.y = anchor_y + math.sin(self.timer * self.frequency) * swing
        elif self.pattern == "arc":
            factor = self.extra.get("arc_factor", 0.012)
            self.pos.y = anchor_y + math.sin((self.base_pos.x - self.pos.x) * factor + self.phase) * self.amplitude
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt * 3.5)
        if self.next_shot != math.inf:
            self.next_shot -= dt

    def ready_to_fire(self) -> bool:
        return self.shoot_range is not None and self.next_shot <= 0

    def draw(self, surface: pygame.Surface, time_accumulator: float) -> None:
        dest = self.rect.copy()
        if self.pattern != "boss":
            wobble = math.sin(time_accumulator * 2.6 + self.phase) * 2
            dest.y += int(wobble)
        surface.blit(self.surface, dest)
        if self.hit_flash > 0:
            flash_alpha = int(200 * self.hit_flash)
            pygame.draw.rect(surface, (255, 255, 255, flash_alpha), dest, border_radius=10)
        if self.health < self.max_health:
            ratio = self.health / max(1, self.max_health)
            bar_bg = pygame.Rect(dest.x + 6, dest.y - 6, dest.width - 12, 4)
            pygame.draw.rect(surface, (20, 20, 30, 180), bar_bg, border_radius=2)
            bar = bar_bg.copy()
            bar.width = max(0, int(bar.width * ratio))
            pygame.draw.rect(surface, (90, 255, 160, 220), bar, border_radius=2)


@dataclass
class EnemySpawn:
    time: float
    pattern: str
    kwargs: Dict[str, Any]


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

    # Procedural synthesis helpers -------------------------------------------------
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

    # Asset management --------------------------------------------------------------
    def _load_assets(self) -> None:
        if not self.enabled:
            return
        self.sounds["laser"] = self._generate_tone((720.0, 880.0), 0.1, 0.6)
        self.sounds["hit"] = self._generate_tone((180.0, 320.0), 0.08, 0.5)
        hit_noise = self._generate_noise(0.15, 0.35)
        self.sounds["explosion"] = hit_noise
        self.sounds["shield"] = self._generate_tone((260.0, 200.0), 0.12, 0.5)
        self.music_sound = self._generate_music()
        if self.music_channel and self.music_sound:
            self.music_channel.play(self.music_sound, loops=-1)
            self.music_channel.set_volume(self.master_volume)

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
        pygame.display.set_caption("Space Avaders")
        self.window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        self.window_size = self.window.get_size()
        self.render_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 24)
        self.small_font = pygame.font.SysFont("consolas", 18)
        self.big_font = pygame.font.SysFont("consolas", 56)

        self.audio = AudioManager()

        self.time_accumulator = 0.0
        self.glow_cache: Dict[Tuple[int, int], pygame.Surface] = {}

        self.background_surface = self._create_background_surface()
        self.stars: List[Star] = []
        self._setup_stars()

        self.player_surface = self._create_player_surface()
        self.player_rect = pygame.Rect(0, 0, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.player_pos = pygame.Vector2(0.0, 0.0)
        self.player_velocity = pygame.Vector2(0.0, 0.0)
        self.player_cooldown_timer = 0.0
        self.player_invulnerable = 0.0
        self.player_thruster_timer = 0.0
        self.player_tilt = 0.0
        self.focus_mode = False
        self.lives = PLAYER_LIVES

        self.player_bullets: List[Bullet] = []
        self.enemy_bullets: List[Bullet] = []

        self.particles: List[Particle] = []

        self.enemies: List[Enemy] = []
        self.spawn_events: List[EnemySpawn] = []

        self.scroll_speed = SCROLL_SPEED_START
        self.target_scroll_speed = self.scroll_speed
        self.stage_duration = 70.0
        self.stage_timer = 0.0
        self.stage_banner_timer = 0.0
        self.level = 1
        self.current_sector_name = SECTOR_NAMES[0]

        self.score = 0
        self.state = "playing"
        self.fullscreen = False

        self.reset()

    # -- Setup ---------------------------------------------------------------------

    def _create_background_surface(self) -> pygame.Surface:
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            color = lerp_color(BACKGROUND_GRADIENT_TOP, BACKGROUND_GRADIENT_BOTTOM, t)
            pygame.draw.line(surface, color, (0, y), (SCREEN_WIDTH, y))
        for x in range(-SCREEN_HEIGHT, SCREEN_WIDTH, 120):
            pygame.draw.line(surface, (12, 18, 38), (x, 0), (x + SCREEN_HEIGHT, SCREEN_HEIGHT), width=1)
        return surface.convert()

    def _create_player_surface(self) -> pygame.Surface:
        surface = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)
        body_color_top = lighten(PLAYER_COLOR, 0.25)
        body_color_bottom = darken(PLAYER_COLOR, 0.35)
        for y in range(PLAYER_HEIGHT):
            t = y / max(1, PLAYER_HEIGHT - 1)
            color = lerp_color(body_color_top, body_color_bottom, t)
            pygame.draw.line(surface, color, (10, y), (PLAYER_WIDTH - 10, y))
        pygame.draw.polygon(
            surface,
            lighten(PLAYER_COLOR, 0.4),
            [
                (PLAYER_WIDTH // 2, 2),
                (PLAYER_WIDTH - 18, PLAYER_HEIGHT // 2),
                (PLAYER_WIDTH // 2, PLAYER_HEIGHT - 4),
                (18, PLAYER_HEIGHT // 2),
            ],
        )
        canopy_rect = pygame.Rect(0, 0, PLAYER_WIDTH // 2, PLAYER_HEIGHT // 2)
        canopy_rect.center = (PLAYER_WIDTH // 2, PLAYER_HEIGHT // 2)
        pygame.draw.ellipse(surface, (255, 255, 255, 120), canopy_rect)
        pygame.draw.ellipse(surface, (120, 200, 255, 180), canopy_rect.inflate(-6, -4))
        return surface.convert_alpha()

    def _setup_stars(self) -> None:
        self.stars.clear()
        for _ in range(STAR_COUNT):
            self.stars.append(
                Star(
                    x=random.uniform(0, SCREEN_WIDTH),
                    y=random.uniform(-20, SCREEN_HEIGHT + 20),
                    speed=random.uniform(10, 70),
                    color=pygame.Color(*random.choice(STAR_COLORS)),
                    radius=random.uniform(1.0, 2.4),
                    twinkle_speed=random.uniform(0.6, 2.0),
                    phase=random.uniform(0, math.tau),
                    parallax=random.uniform(0.2, 1.0),
                )
            )
    def _create_enemy_surface(
        self,
        palette_index: int,
        size: Tuple[int, int] = (ENEMY_WIDTH, ENEMY_HEIGHT),
        wing_style: str = "standard",
    ) -> pygame.Surface:
        width, height = size
        base, accent = ENEMY_COLOR_SETS[palette_index % len(ENEMY_COLOR_SETS)]
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        highlight = lighten(base, 0.3)
        shadow = darken(base, 0.5)
        for y in range(height):
            t = y / max(1, height - 1)
            color = lerp_color(highlight, shadow, t)
            pygame.draw.line(surface, color, (8, y), (width - 8, y))
        nose = [
            (width - 6, height // 2),
            (width - 20, 4),
            (width - 24, height - 4),
        ]
        pygame.draw.polygon(surface, lighten(accent, 0.15), nose)
        pygame.draw.ellipse(surface, lighten(base, 0.45), (12, height // 3, width - 40, height // 3))
        canopy = pygame.Rect(0, 0, width // 3, height // 2)
        canopy.center = (width // 3, height // 2)
        pygame.draw.ellipse(surface, (255, 255, 255, 140), canopy)
        glow = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*lighten(accent, 0.4), 120), (-12, height // 2, width + 24, height))
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        if wing_style == "heavy":
            pygame.draw.rect(surface, darken(accent, 0.4), (6, height // 2 - 6, width // 3, 12), border_radius=4)
        return surface.convert_alpha()

    def _create_boss_surface(self, palette_index: int) -> pygame.Surface:
        width, height = 180, 120
        base, accent = ENEMY_COLOR_SETS[palette_index % len(ENEMY_COLOR_SETS)]
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        highlight = lighten(base, 0.25)
        shadow = darken(base, 0.6)
        for y in range(height):
            t = y / max(1, height - 1)
            color = lerp_color(highlight, shadow, t)
            pygame.draw.line(surface, color, (20, y), (width - 20, y))
        pygame.draw.ellipse(surface, lighten(accent, 0.2), (40, 10, width - 80, height - 20))
        pygame.draw.ellipse(surface, (255, 255, 255, 140), (width // 2 - 30, height // 2 - 24, 60, 48))
        spine = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.polygon(
            spine,
            (*lighten(accent, 0.5), 180),
            [(width - 10, height // 2), (width - 60, 8), (width - 60, height - 8)],
        )
        surface.blit(spine, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return surface.convert_alpha()

    def reset(self) -> None:
        self.score = 0
        self.lives = PLAYER_LIVES
        self.level = 1
        self.scroll_speed = SCROLL_SPEED_START
        self.target_scroll_speed = self.scroll_speed
        self.player_pos.update(SCREEN_WIDTH * 0.18, SCREEN_HEIGHT * 0.5)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        self.player_velocity.update(0, 0)
        self.player_cooldown_timer = 0.0
        self.player_invulnerable = 0.0
        self.player_thruster_timer = 0.0
        self.player_tilt = 0.0
        self.focus_mode = False
        self.player_bullets.clear()
        self.enemy_bullets.clear()
        self.particles.clear()
        self.enemies.clear()
        self.spawn_events.clear()
        self.stage_banner_timer = 3.5
        self.state = "playing"
        self.current_sector_name = SECTOR_NAMES[0]
        self.start_stage()

    def start_stage(self) -> None:
        self.stage_timer = 0.0
        self.stage_duration = max(54.0, 72.0 - (self.level - 1) * 4.0)
        self.spawn_events.clear()
        self.enemies.clear()
        self.enemy_bullets.clear()
        self.player_bullets.clear()
        self.current_sector_name = SECTOR_NAMES[(self.level - 1) % len(SECTOR_NAMES)]
        self.plan_stage()

    def plan_stage(self) -> None:
        pace = max(0.65, 1.0 - (self.level - 1) * 0.05)
        strength = 1.0 + (self.level - 1) * 0.2
        bonus = min(3, self.level - 1)
        base_time = 1.5
        self.queue_spawn(
            base_time,
            "sine",
            count=6 + bonus,
            y=SCREEN_HEIGHT * 0.35,
            amplitude=70 + 8 * strength,
            spacing=54,
            speed=190 + 12 * strength,
            palette=0,
        )
        base_time += 4.0 * pace
        self.queue_spawn(
            base_time,
            "sine_lower",
            count=5 + min(4, self.level),
            y=SCREEN_HEIGHT * 0.68,
            amplitude=60 + 10 * strength,
            spacing=58,
            speed=200 + 10 * strength,
            palette=1,
            phase_offset=math.pi / 3,
        )
        base_time += 4.6 * pace
        self.queue_spawn(
            base_time,
            "dive",
            count=4 + self.level,
            y=PLAYFIELD_MARGIN_Y + 30,
            spacing=42,
            speed=200 + 18 * strength,
            palette=2,
        )
        base_time += 5.2 * pace
        self.queue_spawn(
            base_time,
            "arc",
            count=6 + min(4, self.level),
            y=SCREEN_HEIGHT * 0.5,
            amplitude=90 + 12 * strength,
            spacing=52,
            speed=180 + 14 * strength,
            palette=3,
        )
        base_time += 6.0 * pace
        self.queue_spawn(
            base_time,
            "turrets",
            count=2 + (self.level // 2),
            y=PLAYFIELD_MARGIN_Y + 120,
            spacing=160,
            speed=120 + 10 * strength,
            palette=4,
        )
        base_time += 4.8 * pace
        self.queue_spawn(
            base_time,
            "mines",
            count=5 + self.level,
            y=SCREEN_HEIGHT * 0.55,
            spacing=86,
            palette=1,
        )
        boss_time = max(self.stage_duration - 16.0, base_time + 6.0 * pace)
        self.queue_spawn(
            boss_time,
            "boss",
            y=SCREEN_HEIGHT * 0.5,
            palette=(self.level - 1) % len(ENEMY_COLOR_SETS),
        )

    def queue_spawn(self, time: float, pattern: str, **kwargs: Any) -> None:
        self.spawn_events.append(EnemySpawn(time=time, pattern=pattern, kwargs=kwargs))
        self.spawn_events.sort(key=lambda event: event.time)

    def _handle_spawn_event(self, event: EnemySpawn) -> None:
        pattern = event.pattern
        if pattern == "sine":
            self._spawn_sine_wave(event.kwargs)
        elif pattern == "sine_lower":
            params = dict(event.kwargs)
            params.setdefault("phase_offset", math.pi / 3)
            self._spawn_sine_wave(params)
        elif pattern == "dive":
            self._spawn_dive_squad(event.kwargs)
        elif pattern == "arc":
            self._spawn_arc_dancers(event.kwargs)
        elif pattern == "turrets":
            self._spawn_turret_line(event.kwargs)
        elif pattern == "mines":
            self._spawn_mine_field(event.kwargs)
        elif pattern == "boss":
            self._spawn_boss(event.kwargs)
    def _spawn_enemy(
        self,
        *,
        position: Tuple[float, float],
        velocity: Tuple[float, float],
        pattern: str,
        health: int,
        palette_index: int,
        amplitude: float = 0.0,
        frequency: float = 1.0,
        phase: float = 0.0,
        shoot_range: Optional[Tuple[float, float]] = (1.6, 3.0),
        score: int = 120,
        size: Tuple[int, int] = (ENEMY_WIDTH, ENEMY_HEIGHT),
        wing_style: str = "standard",
        extra: Optional[Dict[str, Any]] = None,
        surface: Optional[pygame.Surface] = None,
    ) -> Enemy:
        if surface is None:
            surface = self._create_enemy_surface(palette_index, size, wing_style)
        extra_data = dict(extra or {})
        extra_data.setdefault("anchor_y", position[1])
        enemy = Enemy(
            surface=surface,
            pos=pygame.Vector2(position),
            velocity=pygame.Vector2(velocity),
            max_health=health,
            health=health,
            pattern=pattern,
            amplitude=amplitude,
            frequency=frequency,
            phase=phase,
            shoot_range=shoot_range,
            score=score,
            extra=extra_data,
        )
        self.enemies.append(enemy)
        return enemy

    def _spawn_sine_wave(self, params: Dict[str, Any]) -> None:
        count = params.get("count", 5)
        base_y = params.get("y", SCREEN_HEIGHT * 0.5)
        amplitude = params.get("amplitude", 70)
        spacing = params.get("spacing", 52)
        speed = params.get("speed", 180)
        palette = params.get("palette", 0)
        phase_offset = params.get("phase_offset", 0.0)
        frequency = 1.4 + 0.05 * self.level
        health = 3 + (self.level - 1) // 2
        for i in range(count):
            pos_x = SCREEN_WIDTH + 100 + i * spacing * 0.4
            pos_y = base_y + math.sin((i / max(1, count - 1)) * math.pi) * 12
            enemy = self._spawn_enemy(
                position=(pos_x, pos_y),
                velocity=(-speed, 0),
                pattern="sine",
                health=health,
                palette_index=palette,
                amplitude=amplitude,
                frequency=frequency,
                phase=phase_offset + i * 0.45,
                shoot_range=(1.5, 2.9),
                score=140 + 12 * self.level,
            )
            enemy.extra["anchor_y"] = base_y + (i % 2) * 16 - 8

    def _spawn_dive_squad(self, params: Dict[str, Any]) -> None:
        count = params.get("count", 6)
        start_y = params.get("y", PLAYFIELD_MARGIN_Y + 40)
        spacing = params.get("spacing", 42)
        speed = params.get("speed", 210)
        palette = params.get("palette", 2)
        health = 2 + (self.level // 2)
        for i in range(count):
            pos_x = SCREEN_WIDTH + 80 + i * 36
            pos_y = start_y - i * spacing * 0.4
            enemy = self._spawn_enemy(
                position=(pos_x, pos_y),
                velocity=(-speed, 0),
                pattern="dive",
                health=health,
                palette_index=palette,
                amplitude=70 + i * 6,
                extra={"dive_delay": 0.4 + i * 0.12, "dive_speed": 240 + 20 * self.level},
                shoot_range=(2.4, 3.6) if self.level > 1 else None,
                score=160 + 14 * self.level,
            )
            enemy.extra["anchor_y"] = pos_y

    def _spawn_arc_dancers(self, params: Dict[str, Any]) -> None:
        count = params.get("count", 5)
        base_y = params.get("y", SCREEN_HEIGHT * 0.5)
        amplitude = params.get("amplitude", 80)
        spacing = params.get("spacing", 54)
        speed = params.get("speed", 170)
        palette = params.get("palette", 3)
        health = 3 + (self.level - 1) // 2
        for i in range(count):
            pos_x = SCREEN_WIDTH + 120 + i * spacing
            pos_y = base_y + (i % 3 - 1) * 26
            self._spawn_enemy(
                position=(pos_x, pos_y),
                velocity=(-speed, 0),
                pattern="arc",
                health=health,
                palette_index=palette,
                amplitude=amplitude,
                frequency=1.1 + 0.03 * self.level,
                phase=i * 0.6,
                shoot_range=(1.2, 2.4),
                score=150 + 15 * self.level,
                extra={"arc_factor": 0.014 + 0.002 * (self.level - 1)},
            )

    def _spawn_turret_line(self, params: Dict[str, Any]) -> None:
        count = params.get("count", 3)
        base_y = params.get("y", PLAYFIELD_MARGIN_Y + 120)
        spacing = params.get("spacing", 160)
        speed = params.get("speed", 120)
        palette = params.get("palette", 4)
        health = 4 + self.level
        for i in range(count):
            target_y = base_y + (i % 2) * 160
            enemy = self._spawn_enemy(
                position=(SCREEN_WIDTH + 140 + i * spacing, target_y - 120),
                velocity=(-speed, 0),
                pattern="hover",
                health=health,
                palette_index=palette,
                amplitude=40,
                frequency=1.0,
                phase=i * 0.3,
                shoot_range=(0.8, 1.6),
                score=220 + 20 * self.level,
                size=(ENEMY_WIDTH + 18, ENEMY_HEIGHT + 12),
                wing_style="heavy",
                extra={"target_y": target_y, "anchor_y": target_y - 40, "persistent": 1.0},
            )
            enemy.extra["anchor_y"] = target_y - 40

    def _spawn_mine_field(self, params: Dict[str, Any]) -> None:
        count = params.get("count", 6)
        base_y = params.get("y", SCREEN_HEIGHT * 0.5)
        spacing = params.get("spacing", 90)
        palette = params.get("palette", 1)
        health = 3 + (self.level // 3)
        for i in range(count):
            offset = (i % 3 - 1) * 28
            self._spawn_enemy(
                position=(SCREEN_WIDTH + 100 + i * spacing, base_y + offset),
                velocity=(-(self.scroll_speed * 0.6 + 80), 0),
                pattern="zigzag",
                health=health,
                palette_index=palette,
                amplitude=50 + 10 * (i % 3),
                frequency=1.0,
                shoot_range=None,
                score=90 + 8 * self.level,
                extra={"period": 0.8 + 0.1 * (i % 3)},
            )

    def _spawn_boss(self, params: Dict[str, Any]) -> None:
        y = params.get("y", SCREEN_HEIGHT * 0.5)
        palette = params.get("palette", 0)
        health = 60 + (self.level - 1) * 18
        self._spawn_enemy(
            position=(SCREEN_WIDTH + 220, y),
            velocity=(-self.scroll_speed * 0.45, 0),
            pattern="boss",
            health=health,
            palette_index=palette,
            amplitude=0.0,
            frequency=0.8 + 0.05 * self.level,
            phase=0.0,
            shoot_range=(0.6, 1.1),
            score=1500 + 150 * self.level,
            size=(180, 120),
            extra={"anchor_y": y, "swing": 140 + 12 * self.level, "persistent": 1.0},
            surface=self._create_boss_surface(palette),
        )
        self.audio.play("hit", 0.6)

    # -- Game loop -----------------------------------------------------------------

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

    # -- Event handling ------------------------------------------------------------

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
                if event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.state == "game_over":
                    self.reset()
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

    # -- Update loop ----------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.time_accumulator += dt
        for star in self.stars:
            star.update(dt, self.scroll_speed)
        if self.stage_banner_timer > 0:
            self.stage_banner_timer = max(0.0, self.stage_banner_timer - dt)

        if self.state != "playing":
            self.update_particles(dt)
            return

        self.update_player(dt)
        self.update_player_bullets(dt)
        self.update_enemies(dt)
        self.update_enemy_bullets(dt)
        self.update_particles(dt)
    def update_player(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(0, 0)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            direction.x -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            direction.x += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            direction.y -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            direction.y += 1
        focus = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        speed = PLAYER_FOCUS_SPEED if focus else PLAYER_SPEED
        if direction.length_squared() > 0:
            direction = direction.normalize()
        self.player_pos += direction * speed * dt
        left_bound = PLAYFIELD_MARGIN_X
        right_bound = SCREEN_WIDTH - PLAYFIELD_MARGIN_X
        top_bound = PLAYFIELD_MARGIN_Y
        bottom_bound = SCREEN_HEIGHT - PLAYFIELD_MARGIN_Y
        self.player_pos.x = max(left_bound, min(right_bound, self.player_pos.x))
        self.player_pos.y = max(top_bound, min(bottom_bound, self.player_pos.y))
        previous_center = self.player_rect.center
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        delta = self.player_rect.centerx - previous_center[0]
        self.player_tilt = lerp(self.player_tilt, -delta * 0.2, min(1.0, dt * 10))
        self.focus_mode = focus

        if self.player_cooldown_timer > 0:
            self.player_cooldown_timer -= dt
        if (keys[pygame.K_SPACE] or keys[pygame.K_z] or keys[pygame.K_x]) and self.player_cooldown_timer <= 0:
            bullet = Bullet(
                pos=pygame.Vector2(self.player_rect.midright[0] + 12, self.player_rect.midright[1]),
                velocity=pygame.Vector2(BULLET_SPEED, 0),
                damage=PLAYER_BULLET_DAMAGE,
                color=pygame.Color(*PLAYER_BULLET_COLOR),
                size=(22, 8),
                from_player=True,
                glow_radius=28,
            )
            self.player_bullets.append(bullet)
            self.player_cooldown_timer = PLAYER_COOLDOWN * (0.7 if focus else 1.0)
            self.audio.play("laser", 0.8)
            self.spawn_muzzle_flash(pygame.Vector2(self.player_rect.midright))

        self.player_thruster_timer += dt
        thruster_rate = 0.04 if focus else 0.06
        if self.player_thruster_timer >= thruster_rate:
            self.player_thruster_timer = 0.0
            self.spawn_thruster_particles(focus)

        if self.player_invulnerable > 0:
            self.player_invulnerable -= dt

    def update_player_bullets(self, dt: float) -> None:
        for bullet in self.player_bullets[:]:
            bullet.update(dt)
            if self.bullet_offscreen(bullet):
                self.player_bullets.remove(bullet)
                continue
            hit_enemy = None
            for enemy in self.enemies:
                if bullet.rect.colliderect(enemy.rect):
                    hit_enemy = enemy
                    break
            if hit_enemy:
                destroyed = hit_enemy.apply_damage(PLAYER_BULLET_DAMAGE, bullet.rect.center)
                self.spawn_hit_sparks(pygame.Vector2(bullet.pos))
                self.audio.play("hit", 0.55)
                if destroyed:
                    self.enemies.remove(hit_enemy)
                    self.score += hit_enemy.score
                    sparks = 60 if hit_enemy.pattern == "boss" else 28
                    self.spawn_explosion(pygame.Vector2(hit_enemy.rect.center), sparks=sparks)
                    self.audio.play("explosion", 1.0 if hit_enemy.pattern == "boss" else 0.7)
                self.player_bullets.remove(bullet)

    def update_enemies(self, dt: float) -> None:
        self.scroll_speed = lerp(self.scroll_speed, self.target_scroll_speed, min(1.0, dt * 0.5))
        self.stage_timer += dt
        while self.spawn_events and self.spawn_events[0].time <= self.stage_timer:
            event = self.spawn_events.pop(0)
            self._handle_spawn_event(event)

        for enemy in self.enemies[:]:
            enemy.update(dt, self.scroll_speed)
            offscreen = (
                enemy.rect.right < -160
                or enemy.rect.top > SCREEN_HEIGHT + 160
                or enemy.rect.bottom < -160
            )
            if offscreen and enemy.extra.get("persistent", 0.0) < 0.5:
                self.enemies.remove(enemy)
                continue
            if enemy.ready_to_fire() and enemy.rect.centerx < SCREEN_WIDTH + 40:
                self.fire_enemy_bullet(enemy)

        if not self.enemies and not self.spawn_events and self.stage_timer > 2.0:
            self.level += 1
            self.stage_banner_timer = 3.0
            self.target_scroll_speed = min(SCROLL_SPEED_MAX, self.target_scroll_speed + SCROLL_SPEED_STEP)
            self.audio.play("hit", 0.5)
            self.start_stage()

    def fire_enemy_bullet(self, enemy: Enemy) -> None:
        enemy.reset_shoot_timer()
        origin = pygame.Vector2(enemy.rect.center)
        aim = pygame.Vector2(self.player_rect.center) - origin
        if aim.length_squared() == 0:
            direction = pygame.Vector2(-1, 0)
        else:
            direction = aim.normalize()
        speed = ENEMY_BULLET_SPEED + self.level * 14
        velocity = direction * speed
        bullet = Bullet(
            pos=pygame.Vector2(origin),
            velocity=velocity,
            damage=ENEMY_BULLET_DAMAGE,
            color=pygame.Color(*ENEMY_BULLET_COLOR),
            size=(12, 12),
            from_player=False,
            glow_radius=24,
        )
        self.enemy_bullets.append(bullet)
        self.audio.play("laser", 0.45)
        if enemy.pattern == "boss":
            for angle in (-18, 18):
                rotated = pygame.Vector2(-1, 0).rotate(angle)
                spread_velocity = rotated.normalize() * (speed * 0.85)
                spread = Bullet(
                    pos=pygame.Vector2(origin),
                    velocity=spread_velocity,
                    damage=ENEMY_BULLET_DAMAGE,
                    color=pygame.Color(*ENEMY_BULLET_COLOR),
                    size=(14, 14),
                    from_player=False,
                    glow_radius=28,
                )
                self.enemy_bullets.append(spread)

    def update_enemy_bullets(self, dt: float) -> None:
        for bullet in self.enemy_bullets[:]:
            bullet.update(dt)
            if self.bullet_offscreen(bullet):
                self.enemy_bullets.remove(bullet)
                continue
            if bullet.rect.colliderect(self.player_rect):
                if self.player_invulnerable <= 0:
                    self.player_hit()
                if bullet in self.enemy_bullets:
                    self.enemy_bullets.remove(bullet)

    def bullet_offscreen(self, bullet: Bullet) -> bool:
        margin = 140
        rect = bullet.rect
        return (
            rect.right < -margin
            or rect.left > SCREEN_WIDTH + margin
            or rect.bottom < -margin
            or rect.top > SCREEN_HEIGHT + margin
        )

    def update_particles(self, dt: float) -> None:
        alive_particles = []
        for particle in self.particles:
            if particle.update(dt):
                alive_particles.append(particle)
        self.particles = alive_particles

    def player_hit(self) -> None:
        self.lives -= 1
        self.player_invulnerable = PLAYER_INVULNERABLE_TIME
        self.spawn_explosion(pygame.Vector2(self.player_rect.center), sparks=50)
        self.audio.play("explosion", 0.9)
        self.player_pos.update(SCREEN_WIDTH * 0.18, SCREEN_HEIGHT * 0.5)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        self.player_velocity.update(0, 0)
        self.enemy_bullets.clear()
        if self.lives <= 0:
            self.state = "game_over"

    def spawn_particles(
        self,
        position: pygame.Vector2,
        count: int,
        speed_range: Tuple[float, float],
        colors: List[Tuple[int, int, int]],
        lifetime_range: Tuple[float, float],
        gravity: float = 0.0,
    ) -> None:
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(*speed_range)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
            lifetime = random.uniform(*lifetime_range)
            color = pygame.Color(*random.choice(colors))
            particle = Particle(
                pos=pygame.Vector2(position),
                velocity=velocity,
                lifetime=lifetime,
                color=color,
                radius=random.uniform(2, 4),
                fade=random.uniform(1.2, 2.2),
                gravity=gravity,
            )
            self.particles.append(particle)

    def spawn_hit_sparks(self, position: pygame.Vector2, tone: str = "alien") -> None:
        colors = SPARK_COLORS if tone == "alien" else [(170, 230, 255), (120, 200, 220), (200, 255, 255)]
        self.spawn_particles(
            position,
            count=10,
            speed_range=(80, 220),
            colors=colors,
            lifetime_range=(0.15, 0.45),
        )

    def spawn_muzzle_flash(self, position: pygame.Vector2) -> None:
        colors = [(255, 220, 180), (255, 255, 200)]
        self.spawn_particles(
            position,
            count=6,
            speed_range=(80, 220),
            colors=colors,
            lifetime_range=(0.12, 0.28),
        )

    def spawn_thruster_particles(self, focus: bool = False) -> None:
        base = pygame.Vector2(self.player_rect.left - 6, self.player_rect.centery)
        colors = [(255, 150, 90), (255, 200, 120), (255, 255, 160)]
        count = 2 if focus else 3
        for _ in range(count):
            velocity = pygame.Vector2(random.uniform(-220, -140), random.uniform(-40, 40))
            if focus:
                velocity *= 0.7
            particle = Particle(
                pos=pygame.Vector2(base.x, base.y + random.uniform(-10, 10)),
                velocity=velocity,
                lifetime=random.uniform(0.25, 0.45),
                color=pygame.Color(*random.choice(colors)),
                radius=random.uniform(2, 4),
                fade=random.uniform(1.4, 2.0),
            )
            self.particles.append(particle)

    def spawn_explosion(self, position: pygame.Vector2, sparks: int = 24) -> None:
        colors = [(255, 200, 120), (255, 160, 80), (255, 240, 200)]
        self.spawn_particles(
            position,
            count=sparks,
            speed_range=(80, 320),
            colors=colors,
            lifetime_range=(0.2, 0.7),
        )
    # -- Drawing --------------------------------------------------------------------

    def draw(self) -> None:
        self.render_surface.blit(self.background_surface, (0, 0))

        parallax_shift = (self.stage_timer * self.scroll_speed * 0.2) % SCREEN_WIDTH
        for i in range(-1, 3):
            x = int(SCREEN_WIDTH - parallax_shift - i * 220)
            stripe_rect = pygame.Rect(x, 0, 4, SCREEN_HEIGHT)
            pygame.draw.rect(self.render_surface, (24, 36, 66, 70), stripe_rect)

        for star in self.stars:
            star.draw(self.render_surface, self.time_accumulator)

        for enemy in self.enemies:
            color_sample = enemy.surface.get_at((enemy.surface.get_width() // 2, enemy.surface.get_height() // 2))
            glow_color = (color_sample.r, color_sample.g, color_sample.b)
            radius = 90 if enemy.pattern == "boss" else 46
            self.draw_glow(self.render_surface, enemy.rect.center, radius, glow_color)
            enemy.draw(self.render_surface, self.time_accumulator)

        for bullet in self.player_bullets + self.enemy_bullets:
            self.draw_bullet(bullet)

        self.draw_player()

        for particle in self.particles:
            particle.draw(self.render_surface)

        self.draw_hud()
        self.draw_stage_banner()

        if self.state == "game_over":
            self.draw_game_over()

        scaled = pygame.transform.smoothscale(self.render_surface, self.window_size)
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def draw_player(self) -> None:
        blink = (
            int(self.player_invulnerable * 10) % 2 == 0
            or self.player_invulnerable <= 0
            or self.state != "playing"
        )
        if not blink:
            return
        center = self.player_rect.center
        self.draw_glow(self.render_surface, (center[0] + 10, center[1]), 68, PLAYER_GLOW_COLOR)
        tilt = max(-10, min(10, self.player_tilt))
        rotated = pygame.transform.rotate(self.player_surface, tilt)
        rect = rotated.get_rect(center=center)
        self.render_surface.blit(rotated, rect)
        flame_length = 26 + int(6 * math.sin(self.time_accumulator * 16))
        flame_color = pygame.Color(255, 170, 90, 200)
        flame = [
            (self.player_rect.left - flame_length, self.player_rect.centery),
            (self.player_rect.left - 6, self.player_rect.centery - 10),
            (self.player_rect.left - 6, self.player_rect.centery + 10),
        ]
        pygame.draw.polygon(self.render_surface, flame_color, flame)

    def draw_bullet(self, bullet: Bullet) -> None:
        self.draw_glow(self.render_surface, bullet.rect.center, bullet.glow_radius, bullet.color)
        pygame.draw.rect(
            self.render_surface,
            bullet.color,
            bullet.rect,
            border_radius=max(3, bullet.rect.width // 2),
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
        sector_text = self.font.render(f"SECTOR {self.level}", True, HUD_COLOR)
        voyage = min(1.0, self.stage_timer / self.stage_duration) if self.stage_duration > 0 else 0.0
        voyage_text = self.font.render(f"VOYAGE {int(voyage * 100):02d}%", True, HUD_COLOR)
        self.render_surface.blit(score_text, (22, 20))
        self.render_surface.blit(sector_text, (SCREEN_WIDTH // 2 - sector_text.get_width() // 2, 20))
        self.render_surface.blit(voyage_text, (SCREEN_WIDTH - voyage_text.get_width() - 24, 20))
        bar_bg = pygame.Rect(22, 56, 220, 6)
        pygame.draw.rect(self.render_surface, (20, 30, 50, 160), bar_bg, border_radius=3)
        bar = bar_bg.copy()
        bar.width = int(bar.width * voyage)
        pygame.draw.rect(self.render_surface, (80, 210, 255, 200), bar, border_radius=3)
        lives_text = self.small_font.render(f"LIVES {self.lives}", True, HUD_COLOR)
        self.render_surface.blit(lives_text, (22, 68))
        if self.audio.enabled:
            volume = int(self.audio.master_volume * 100)
            label = "MUTED" if self.audio.muted or volume == 0 else f"VOL {volume}%"
            volume_text = self.small_font.render(f"{label} (M)", True, HUD_COLOR)
        else:
            volume_text = self.small_font.render("Audio unavailable", True, HUD_COLOR)
        self.render_surface.blit(volume_text, (SCREEN_WIDTH - volume_text.get_width() - 24, 52))

    def draw_stage_banner(self) -> None:
        if self.stage_banner_timer <= 0:
            return
        t = min(1.0, self.stage_banner_timer / 3.0)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(120 * t)))
        self.render_surface.blit(overlay, (0, 0))
        title = self.big_font.render(f"SECTOR {self.level}", True, HUD_COLOR)
        subtitle = self.font.render(self.current_sector_name, True, HUD_COLOR)
        y = SCREEN_HEIGHT * 0.28
        self.render_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, int(y)))
        self.render_surface.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, int(y + 64)))

    def draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.render_surface.blit(overlay, (0, 0))
        title = self.big_font.render("MISSION FAILED", True, HUD_COLOR)
        prompt = self.font.render("Press Enter to relaunch", True, HUD_COLOR)
        score = self.font.render(f"Final score: {self.score}", True, HUD_COLOR)
        self.render_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 120))
        self.render_surface.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
        self.render_surface.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT // 2 + 30))
# --- Entrypoint --------------------------------------------------------------------


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
