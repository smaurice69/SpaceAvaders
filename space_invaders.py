#!/usr/bin/env python3
"""Space Avaders: Parallax Assault.

A lavish re-imagining of the original project that leans into early-console
side-scrolling shooters. Think Defender, Gradius, and R-Type smashed together
with modern juice:

    * Wide horizontal arenas with parallax starfields and drifting nebulae.
    * Agile eight-direction flight, throttle control, and overdrive twin lasers.
    * Formation-based enemy waves that weave, dive, and strafe across the screen.
    * A cascading combo system with score multipliers and loot capsules.
    * Self-contained procedural audio for lasers, hits, and explosions.

Run with ``python3 space_invaders.py`` after installing pygame::

    pip install pygame
"""
from __future__ import annotations

import array
import math
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import pygame


# --- Configuration -----------------------------------------------------------------

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
FPS = 60

SCROLL_SPEED = 150

PLAYER_SPEED = 340
PLAYER_VERTICAL_SPEED = 300
PLAYER_WIDTH = 82
PLAYER_HEIGHT = 40
PLAYER_COOLDOWN = 0.28
PLAYER_OVERDRIVE_COOLDOWN = 0.18
PLAYER_LIVES = 4
PLAYER_INVULNERABLE_TIME = 1.6
PLAYER_FOCUS_SCALE = 0.6

BULLET_SPEED = 620
PLAYER_BULLET_DAMAGE = 1
ALIEN_BULLET_DAMAGE = 1

STAR_COUNT = 110

BACKGROUND_GRADIENT_TOP = (10, 12, 34)
BACKGROUND_GRADIENT_BOTTOM = (4, 4, 14)
PLAYER_COLOR = (90, 200, 255)
PLAYER_GLOW_COLOR = (60, 150, 255)
PLAYER_BULLET_COLOR = (255, 240, 170)
ALIEN_BULLET_COLOR = (255, 120, 140)
HUD_COLOR = (235, 240, 255)
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
NEBULA_COLORS = [
    (80, 60, 140, 90),
    (110, 70, 160, 110),
    (60, 100, 180, 120),
    (120, 40, 150, 90),
]


# Enemy archetype definitions -------------------------------------------------------

ENEMY_TYPES: Dict[str, Dict[str, object]] = {
    "dart": {
        "size": (60, 36),
        "color": (255, 170, 120),
        "accent": (255, 220, 180),
        "wing": (220, 90, 150),
        "behavior": "sine",
        "speed": 165.0,
        "amplitude": 60.0,
        "frequency": 2.4,
        "health": 2,
        "health_scale": 0,
        "fire_interval": (2.2, 3.6),
        "bullet_speed": 280.0,
        "aim": False,
        "score": 140,
    },
    "flare": {
        "size": (70, 38),
        "color": (255, 130, 170),
        "accent": (255, 200, 210),
        "wing": (200, 60, 120),
        "behavior": "dive",
        "speed": 210.0,
        "amplitude": 80.0,
        "frequency": 1.5,
        "health": 3,
        "health_scale": 1,
        "fire_interval": (1.6, 2.4),
        "bullet_speed": 320.0,
        "aim": True,
        "score": 180,
    },
    "orb": {
        "size": (54, 54),
        "color": (140, 220, 255),
        "accent": (200, 255, 255),
        "wing": (90, 180, 240),
        "behavior": "strafe",
        "speed": 120.0,
        "amplitude": 110.0,
        "frequency": 1.2,
        "health": 5,
        "health_scale": 1,
        "fire_interval": (1.4, 2.1),
        "bullet_speed": 260.0,
        "aim": True,
        "score": 260,
    },
    "sentinel": {
        "size": (120, 84),
        "color": (150, 120, 255),
        "accent": (210, 180, 255),
        "wing": (110, 70, 210),
        "behavior": "boss",
        "speed": 95.0,
        "amplitude": 90.0,
        "frequency": 0.9,
        "health": 18,
        "health_scale": 4,
        "fire_interval": (0.9, 1.4),
        "bullet_speed": 300.0,
        "aim": True,
        "score": 1200,
    },
}

POWERUP_TYPES: Dict[str, Dict[str, object]] = {
    "resupply": {
        "color": (120, 220, 180),
        "glow": (170, 255, 220),
        "label": "▲",
    },
    "overdrive": {
        "color": (255, 190, 120),
        "glow": (255, 230, 150),
        "label": "∞",
    },
    "vault": {
        "color": (160, 200, 255),
        "glow": (200, 240, 255),
        "label": "$",
    },
}


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

    def update(self, dt: float) -> None:
        self.x -= self.speed * dt
        if self.x < -6:
            self.x = SCREEN_WIDTH + 6
            self.y = random.uniform(30, SCREEN_HEIGHT - 30)
            self.speed = random.uniform(50, 200)
            self.radius = random.uniform(1.0, 2.8)
            self.twinkle_speed = random.uniform(0.9, 2.6)
            self.phase = random.uniform(0, math.tau)

    def draw(self, surface: pygame.Surface, time_accumulator: float) -> None:
        twinkle = 0.6 + 0.4 * math.sin(self.phase + time_accumulator * self.twinkle_speed)
        alpha = int(130 + 110 * twinkle)
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
    pos: pygame.Vector2
    sprite: pygame.Surface
    max_health: int
    health: int
    behavior: str
    speed: float
    amplitude: float
    frequency: float
    fire_interval: Tuple[float, float]
    bullet_speed: float
    aim_player: bool
    score: int
    drift: float = 0.0
    anchor_x: Optional[float] = None
    phase: float = field(default_factory=lambda: random.uniform(0, math.tau))
    hit_flash: float = 0.0
    time_alive: float = 0.0
    rect: pygame.Rect = field(init=False)
    fire_timer: float = field(init=False)

    def __post_init__(self) -> None:
        self.rect = self.sprite.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self.fire_timer = random.uniform(*self.fire_interval)

    def apply_damage(self, amount: int) -> bool:
        self.health = max(0, self.health - amount)
        self.hit_flash = 0.3
        return self.health <= 0

    def update(self, dt: float, player_pos: pygame.Vector2) -> List[Bullet]:
        self.time_alive += dt
        bullets: List[Bullet] = []
        if self.behavior == "sine":
            target_y = self.pos.y + math.sin(self.phase + self.time_alive * self.frequency) * self.amplitude * dt
            self.pos.x -= self.speed * dt
            self.pos.y = lerp(self.pos.y, target_y, min(1.0, dt * 6))
        elif self.behavior == "dive":
            self.pos.x -= self.speed * dt
            desired = player_pos.y + math.sin(self.phase + self.time_alive * self.frequency) * self.amplitude
            self.pos.y = lerp(self.pos.y, desired, min(1.0, dt * 4))
        elif self.behavior == "strafe":
            self.pos.x -= self.speed * dt
            offset = math.sin(self.phase + self.time_alive * self.frequency) * self.amplitude
            self.pos.y = lerp(self.pos.y, offset + (SCREEN_HEIGHT / 2), min(1.0, dt * 3))
        elif self.behavior == "boss":
            target_x = self.anchor_x if self.anchor_x is not None else SCREEN_WIDTH * 0.65
            if self.pos.x > target_x:
                self.pos.x = max(target_x, self.pos.x - self.speed * dt)
            else:
                self.pos.x = lerp(self.pos.x, target_x, min(1.0, dt * 2))
            wiggle = math.sin(self.phase + self.time_alive * self.frequency) * self.amplitude
            self.pos.y = lerp(self.pos.y, SCREEN_HEIGHT / 2 + wiggle, min(1.0, dt * 2.5))
        else:
            self.pos.x -= self.speed * dt

        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt * 4)

        self.fire_timer -= dt
        if self.fire_timer <= 0:
            direction = pygame.Vector2(-1, 0)
            if self.aim_player:
                to_player = pygame.Vector2(player_pos) - self.pos
                if to_player.length_squared() > 0.01:
                    direction = to_player.normalize()
            bullet = Bullet(
                pos=pygame.Vector2(self.pos.x, self.pos.y),
                velocity=direction * self.bullet_speed,
                damage=ALIEN_BULLET_DAMAGE,
                color=pygame.Color(*ALIEN_BULLET_COLOR),
                size=(14, 6) if abs(direction.x) >= abs(direction.y) else (6, 14),
                from_player=False,
                glow_radius=22,
            )
            bullets.append(bullet)
            self.fire_timer = random.uniform(*self.fire_interval)
        return bullets

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.sprite, self.rect)
        if self.hit_flash > 0:
            flash_alpha = int(220 * self.hit_flash)
            overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            overlay.fill((255, 255, 255, flash_alpha))
            surface.blit(overlay, self.rect)
        if self.health < self.max_health:
            ratio = self.health / self.max_health
            bar_bg = pygame.Rect(self.rect.x + 8, self.rect.y - 8, self.rect.width - 16, 5)
            pygame.draw.rect(surface, (20, 20, 40, 140), bar_bg, border_radius=3)
            bar = bar_bg.copy()
            bar.width = max(0, int(bar.width * ratio))
            pygame.draw.rect(surface, (100, 255, 160, 200), bar, border_radius=3)


@dataclass
class PowerUp:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    kind: str
    surface: pygame.Surface
    glow_color: pygame.Color
    wobble_phase: float = field(default_factory=lambda: random.uniform(0, math.tau))
    rect: pygame.Rect = field(init=False)

    def __post_init__(self) -> None:
        self.rect = self.surface.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def update(self, dt: float) -> None:
        self.pos += self.velocity * dt
        self.wobble_phase += dt * 2.8
        wobble = math.sin(self.wobble_phase) * 12
        self.rect.center = (int(self.pos.x), int(self.pos.y + wobble))

    def draw(self, surface: pygame.Surface, draw_glow) -> None:
        draw_glow(surface, self.rect.center, 46, self.glow_color)
        surface.blit(self.surface, self.rect)


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
        duration = 8.0
        samples = int(duration * sample_rate)
        buffer = array.array("h")
        progression = [196, 247, 294, 392, 262, 330, 392, 523]
        beat = int(sample_rate * 0.4)
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
        self.sounds["laser"] = self._generate_tone((720.0, 880.0, 960.0), 0.1, 0.6)
        self.sounds["hit"] = self._generate_tone((200.0, 320.0, 400.0), 0.08, 0.5)
        self.sounds["explosion"] = self._generate_noise(0.18, 0.35)
        self.sounds["pickup"] = self._generate_tone((520.0, 660.0, 840.0), 0.14, 0.6)
        self.music_sound = self._generate_music()
        if self.music_channel and self.music_sound:
            self.music_channel.play(self.music_sound, loops=-1)
            self.music_channel.set_volume(self.master_volume * 0.6)

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
        volume = 0.0 if self.muted else self.master_volume * 0.6
        self.music_channel.set_volume(volume)


# --- Game implementation ------------------------------------------------------------


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Space Avaders: Parallax Assault")
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
        self._setup_stars()
        self._setup_nebulae()
        self._setup_speed_trails()

        self.player_surface = self._create_player_surface()
        self.player_rect = pygame.Rect(0, 0, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.player_rect.midleft = (120, SCREEN_HEIGHT // 2)
        self.player_pos = pygame.Vector2(self.player_rect.center)
        self.player_velocity = pygame.Vector2(0, 0)
        self.player_cooldown_timer = 0.0
        self.player_invulnerable = 0.0
        self.player_thruster_timer = 0.0
        self.player_tilt = 0.0
        self.hyper_timer = 0.0
        self.focus_mode = False

        self.player_bullets: List[Bullet] = []
        self.enemy_bullets: List[Bullet] = []

        self.particles: List[Particle] = []

        self.enemy_surfaces = {key: self._create_enemy_surface(key, value) for key, value in ENEMY_TYPES.items()}
        self.enemies: List[Enemy] = []

        self.powerup_surfaces = {key: self._create_powerup_surface(key, value) for key, value in POWERUP_TYPES.items()}
        self.powerups: List[PowerUp] = []

        self.score = 0
        self.combo = 0
        self.combo_timer = 0.0
        self.stage = 1
        self.lives = PLAYER_LIVES
        self.max_lives = PLAYER_LIVES + 2
        self.distance = 0.0
        self.stage_time = 0.0
        self.stage_length = 60.0
        self.stage_events: List[Dict[str, object]] = []
        self.next_spawn_index = 0

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
        return surface.convert()

    def _setup_stars(self) -> None:
        self.stars: List[Star] = []
        for _ in range(STAR_COUNT):
            star = Star(
                x=random.uniform(0, SCREEN_WIDTH),
                y=random.uniform(30, SCREEN_HEIGHT - 30),
                speed=random.uniform(40, 200),
                color=pygame.Color(*random.choice(STAR_COLORS)),
                radius=random.uniform(1.0, 2.6),
                twinkle_speed=random.uniform(0.9, 2.8),
                phase=random.uniform(0, math.tau),
            )
            self.stars.append(star)

    def _setup_nebulae(self) -> None:
        self.nebulae: List[Dict[str, object]] = []
        for _ in range(8):
            width = random.randint(140, 260)
            height = random.randint(90, 160)
            surf = pygame.Surface((width, height), pygame.SRCALPHA)
            base_color = random.choice(NEBULA_COLORS)
            for y in range(height):
                for x in range(width):
                    dx = (x - width / 2) / (width / 2)
                    dy = (y - height / 2) / (height / 2)
                    distance = math.sqrt(dx * dx + dy * dy)
                    alpha = max(0.0, 1.0 - distance ** 1.8)
                    color = pygame.Color(base_color[0], base_color[1], base_color[2], int(base_color[3] * alpha))
                    surf.set_at((x, y), color)
            self.nebulae.append(
                {
                    "surface": surf,
                    "x": random.uniform(0, SCREEN_WIDTH),
                    "y": random.uniform(40, SCREEN_HEIGHT - 200),
                    "speed": random.uniform(20, 60),
                }
            )

    def _setup_speed_trails(self) -> None:
        self.speed_trails: List[Dict[str, float]] = []
        for _ in range(16):
            self.speed_trails.append(
                {
                    "x": random.uniform(0, SCREEN_WIDTH),
                    "y": random.uniform(80, SCREEN_HEIGHT - 80),
                    "length": random.uniform(60, 160),
                    "speed": random.uniform(SCROLL_SPEED * 1.2, SCROLL_SPEED * 2.3),
                    "thickness": random.uniform(1.5, 3.5),
                }
            )

    def _create_player_surface(self) -> pygame.Surface:
        surface = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)
        body_top = lighten(PLAYER_COLOR, 0.35)
        body_bottom = darken(PLAYER_COLOR, 0.4)
        for x in range(PLAYER_WIDTH):
            t = x / max(1, PLAYER_WIDTH - 1)
            color = lerp_color(body_top, body_bottom, t)
            pygame.draw.line(surface, color, (x, 10), (x, PLAYER_HEIGHT - 10))
        nose = [
            (PLAYER_WIDTH - 2, PLAYER_HEIGHT // 2),
            (PLAYER_WIDTH - 18, PLAYER_HEIGHT - 6),
            (PLAYER_WIDTH - 18, 6),
        ]
        pygame.draw.polygon(surface, lighten(PLAYER_COLOR, 0.5), nose)
        wing_color = lighten(PLAYER_COLOR, 0.2)
        pygame.draw.polygon(surface, wing_color, [(12, PLAYER_HEIGHT - 4), (40, PLAYER_HEIGHT - 4), (6, PLAYER_HEIGHT // 2)])
        pygame.draw.polygon(surface, wing_color, [(12, 4), (40, 4), (6, PLAYER_HEIGHT // 2)])
        canopy_rect = pygame.Rect(0, 0, 30, 18)
        canopy_rect.center = (PLAYER_WIDTH // 2, PLAYER_HEIGHT // 2)
        pygame.draw.ellipse(surface, (255, 255, 255, 160), canopy_rect)
        return surface.convert_alpha()

    def _create_enemy_surface(self, key: str, spec: Dict[str, object]) -> pygame.Surface:
        size = spec["size"]  # type: ignore[assignment]
        width, height = int(size[0]), int(size[1])  # type: ignore[index]
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        primary = pygame.Color(*spec["color"])  # type: ignore[index]
        accent = pygame.Color(*spec["accent"])  # type: ignore[index]
        wing = pygame.Color(*spec["wing"])  # type: ignore[index]
        for x in range(width):
            t = x / max(1, width - 1)
            color = lerp_color(lighten(primary, 0.3), darken(primary, 0.5), t)
            pygame.draw.line(surface, color, (x, 10), (x, height - 10))
        pygame.draw.polygon(surface, wing, [(12, height - 6), (width // 2, height - 2), (6, height // 2)])
        pygame.draw.polygon(surface, wing, [(12, 6), (width // 2, 2), (6, height // 2)])
        pygame.draw.ellipse(surface, accent, (width // 2 - 16, height // 2 - 10, 32, 20))
        pygame.draw.circle(surface, (20, 20, 40, 160), (width // 2 - 6, height // 2), 4)
        pygame.draw.circle(surface, (20, 20, 40, 160), (width // 2 + 6, height // 2), 4)
        if key == "sentinel":
            pygame.draw.polygon(surface, darken(wing, 0.3), [(width - 6, height // 2), (width - 26, height - 8), (width - 26, 8)])
            pygame.draw.circle(surface, (255, 255, 255, 120), (width - 18, height // 2), 12)
        return surface.convert_alpha()

    def _create_powerup_surface(self, key: str, spec: Dict[str, object]) -> pygame.Surface:
        surface = pygame.Surface((40, 40), pygame.SRCALPHA)
        color = pygame.Color(*spec["color"])  # type: ignore[index]
        glow = lighten((color.r, color.g, color.b), 0.4)
        for r in range(18, 0, -1):
            alpha = int(255 * (r / 18) ** 1.8)
            pygame.draw.circle(surface, (*glow, alpha), (20, 20), r)
        pygame.draw.circle(surface, color, (20, 20), 12)
        label = spec["label"]  # type: ignore[index]
        text = self.small_font.render(str(label), True, (0, 0, 40))
        surface.blit(text, (20 - text.get_width() // 2, 20 - text.get_height() // 2))
        return surface.convert_alpha()

    def reset(self) -> None:
        self.player_rect.midleft = (120, SCREEN_HEIGHT // 2)
        self.player_pos = pygame.Vector2(self.player_rect.center)
        self.player_velocity = pygame.Vector2(0, 0)
        self.player_cooldown_timer = 0.0
        self.player_invulnerable = 0.0
        self.player_thruster_timer = 0.0
        self.player_tilt = 0.0
        self.hyper_timer = 0.0
        self.focus_mode = False

        self.player_bullets.clear()
        self.enemy_bullets.clear()
        self.particles.clear()
        self.enemies.clear()
        self.powerups.clear()

        self.score = 0
        self.combo = 0
        self.combo_timer = 0.0
        self.stage = 1
        self.lives = PLAYER_LIVES
        self.distance = 0.0
        self.stage_time = 0.0
        self.stage_events, self.stage_length = self.create_stage_script(self.stage)
        self.next_spawn_index = 0

        self.state = "playing"

    def create_stage_script(self, stage: int) -> Tuple[List[Dict[str, object]], float]:
        events: List[Dict[str, object]] = []
        time_cursor = 2.0
        band_positions = [140, 220, 300, 380, 460]
        for wave in range(4 + stage):
            events.append(
                {
                    "time": time_cursor,
                    "formation": "stream",
                    "kind": "dart",
                    "count": 4 + stage,
                    "spacing": 46,
                    "start_y": random.choice(band_positions),
                }
            )
            time_cursor += 5.2
            events.append(
                {
                    "time": time_cursor,
                    "formation": "swoop",
                    "kind": "flare",
                    "count": 3 + stage // 2,
                }
            )
            time_cursor += 6.0
            events.append(
                {
                    "time": time_cursor,
                    "formation": "arc",
                    "kind": "orb",
                    "count": 4 + stage // 2,
                    "center_y": random.randint(200, SCREEN_HEIGHT - 200),
                    "amplitude": 130 + stage * 10,
                }
            )
            time_cursor += 6.4
            if random.random() < 0.55:
                events.append(
                    {
                        "time": time_cursor,
                        "formation": "powerup",
                        "kind": random.choice(list(POWERUP_TYPES.keys())),
                        "y": random.randint(160, SCREEN_HEIGHT - 160),
                    }
                )
                time_cursor += 2.8
        events.append(
            {
                "time": time_cursor + 4.5,
                "formation": "sentinel",
                "kind": "sentinel",
                "y": SCREEN_HEIGHT // 2,
            }
        )
        stage_length = time_cursor + 18.0
        events.sort(key=lambda e: e["time"])
        return events, stage_length

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
            star.update(dt)
        for nebula in self.nebulae:
            nebula["x"] = float(nebula["x"]) - (SCROLL_SPEED * 0.3 + float(nebula["speed"])) * dt
            if nebula["x"] < -nebula["surface"].get_width():
                nebula["x"] = SCREEN_WIDTH + random.uniform(30, 240)
                nebula["y"] = random.uniform(40, SCREEN_HEIGHT - 200)
        for trail in self.speed_trails:
            trail["x"] -= trail["speed"] * dt
            if trail["x"] < -trail["length"]:
                trail["x"] = SCREEN_WIDTH + random.uniform(20, 180)
                trail["y"] = random.uniform(80, SCREEN_HEIGHT - 80)
                trail["length"] = random.uniform(60, 160)
                trail["speed"] = random.uniform(SCROLL_SPEED * 1.2, SCROLL_SPEED * 2.5)
                trail["thickness"] = random.uniform(1.5, 3.5)

        if self.state != "playing":
            self.update_particles(dt)
            return

        self.stage_time += dt
        self.distance += SCROLL_SPEED * dt
        while self.next_spawn_index < len(self.stage_events) and self.stage_time >= float(self.stage_events[self.next_spawn_index]["time"]):
            event = self.stage_events[self.next_spawn_index]
            self.handle_spawn_event(event)
            self.next_spawn_index += 1

        self.update_player(dt)
        self.update_player_bullets(dt)
        self.update_enemies(dt)
        self.update_enemy_bullets(dt)
        self.update_powerups(dt)
        self.update_particles(dt)

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

        if self.hyper_timer > 0:
            self.hyper_timer = max(0.0, self.hyper_timer - dt)

        if (
            self.stage_time >= self.stage_length
            and self.next_spawn_index >= len(self.stage_events)
            and not self.enemies
            and not self.enemy_bullets
        ):
            self.stage += 1
            self.score += 750 * self.stage
            self.stage_time = 0.0
            self.distance = 0.0
            self.stage_events, self.stage_length = self.create_stage_script(self.stage)
            self.next_spawn_index = 0

    def handle_spawn_event(self, event: Dict[str, object]) -> None:
        formation = event.get("formation")
        if formation == "stream":
            self.spawn_stream(event)
        elif formation == "swoop":
            self.spawn_swoop(event)
        elif formation == "arc":
            self.spawn_arc(event)
        elif formation == "sentinel":
            self.spawn_sentinel(event)
        elif formation == "powerup":
            self.spawn_powerup(event)

    def spawn_stream(self, event: Dict[str, object]) -> None:
        kind = event.get("kind", "dart")
        count = int(event.get("count", 5))
        spacing = float(event.get("spacing", 46))
        start_y = float(event.get("start_y", SCREEN_HEIGHT // 2))
        for i in range(count):
            y = start_y + i * spacing
            while y > SCREEN_HEIGHT - 120:
                y -= 260
            enemy = self.create_enemy(kind, pygame.Vector2(SCREEN_WIDTH + 50 + i * 36, y))
            self.enemies.append(enemy)

    def spawn_swoop(self, event: Dict[str, object]) -> None:
        kind = event.get("kind", "flare")
        count = int(event.get("count", 3))
        for i in range(count):
            offset = 60 * (i - (count - 1) / 2)
            y = SCREEN_HEIGHT / 2 + offset
            enemy = self.create_enemy(kind, pygame.Vector2(SCREEN_WIDTH + 90 + i * 20, y))
            self.enemies.append(enemy)

    def spawn_arc(self, event: Dict[str, object]) -> None:
        kind = event.get("kind", "orb")
        count = max(2, int(event.get("count", 4)))
        center_y = float(event.get("center_y", SCREEN_HEIGHT / 2))
        amplitude = float(event.get("amplitude", 140))
        for i in range(count):
            t = i / max(1, count - 1)
            y = center_y + math.cos(t * math.pi) * amplitude
            enemy = self.create_enemy(kind, pygame.Vector2(SCREEN_WIDTH + 80 + i * 60, y))
            self.enemies.append(enemy)

    def spawn_sentinel(self, event: Dict[str, object]) -> None:
        kind = event.get("kind", "sentinel")
        y = float(event.get("y", SCREEN_HEIGHT / 2))
        enemy = self.create_enemy(kind, pygame.Vector2(SCREEN_WIDTH + 140, y))
        enemy.anchor_x = SCREEN_WIDTH * 0.68
        enemy.fire_interval = (max(0.4, enemy.fire_interval[0] * 0.7), max(0.7, enemy.fire_interval[1] * 0.8))
        self.enemies.append(enemy)

    def spawn_powerup(self, event: Dict[str, object]) -> None:
        kind = str(event.get("kind", "resupply"))
        y = float(event.get("y", SCREEN_HEIGHT / 2))
        self.spawn_powerup_drop(kind, pygame.Vector2(SCREEN_WIDTH + 40, y))

    def create_enemy(self, kind: object, position: pygame.Vector2) -> Enemy:
        key = str(kind)
        spec = ENEMY_TYPES.get(key, ENEMY_TYPES["dart"])
        surface = self.enemy_surfaces[key]
        health = int(spec["health"]) + max(0, self.stage - 1) * int(spec["health_scale"])
        speed = float(spec["speed"]) + (self.stage - 1) * 12
        fire_min, fire_max = spec["fire_interval"]  # type: ignore[assignment]
        fire_scale = 0.94 ** max(0, self.stage - 1)
        fire_interval = (max(0.3, fire_min * fire_scale), max(0.6, fire_max * fire_scale))
        bullet_speed = float(spec["bullet_speed"]) + (self.stage - 1) * 8
        enemy = Enemy(
            pos=pygame.Vector2(position),
            sprite=surface,
            max_health=health,
            health=health,
            behavior=str(spec["behavior"]),
            speed=speed,
            amplitude=float(spec["amplitude"]),
            frequency=float(spec["frequency"]),
            fire_interval=fire_interval,
            bullet_speed=bullet_speed,
            aim_player=bool(spec["aim"]),
            score=int(spec["score"]) + (self.stage - 1) * 40,
        )
        return enemy

    def spawn_powerup_drop(self, kind: str, position: pygame.Vector2) -> None:
        spec = POWERUP_TYPES.get(kind, POWERUP_TYPES["resupply"])
        surface = self.powerup_surfaces[kind]
        glow_color = pygame.Color(*spec["glow"])  # type: ignore[index]
        powerup = PowerUp(
            pos=pygame.Vector2(position),
            velocity=pygame.Vector2(-SCROLL_SPEED * 0.6, 0),
            kind=kind,
            surface=surface,
            glow_color=glow_color,
        )
        self.powerups.append(powerup)

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
        focus = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        self.focus_mode = focus
        speed_scale = PLAYER_FOCUS_SCALE if focus else 1.0
        if move.length_squared() > 0:
            move = move.normalize()
        self.player_velocity.x = move.x * PLAYER_SPEED * speed_scale
        self.player_velocity.y = move.y * PLAYER_VERTICAL_SPEED * speed_scale
        self.player_pos += self.player_velocity * dt
        min_x = 40
        max_x = SCREEN_WIDTH - 160
        min_y = 60
        max_y = SCREEN_HEIGHT - 60
        self.player_pos.x = max(min_x, min(max_x, self.player_pos.x))
        self.player_pos.y = max(min_y, min(max_y, self.player_pos.y))
        previous_center = pygame.Vector2(self.player_rect.center)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        delta = self.player_rect.center[1] - previous_center.y
        self.player_tilt = lerp(self.player_tilt, -delta * 0.4, min(1.0, dt * 6))

        if self.player_cooldown_timer > 0:
            self.player_cooldown_timer -= dt
        if (keys[pygame.K_SPACE] or keys[pygame.K_k] or keys[pygame.K_RETURN]) and self.player_cooldown_timer <= 0:
            self.fire_player_weapon()

        self.player_thruster_timer += dt
        if self.player_thruster_timer >= 0.05:
            self.player_thruster_timer = 0.0
            self.spawn_thruster_particles()

        if self.player_invulnerable > 0:
            self.player_invulnerable -= dt

    def fire_player_weapon(self) -> None:
        hyper = self.hyper_timer > 0
        offsets: Iterable[float]
        if hyper:
            offsets = (-10, 0, 10)
            cooldown = PLAYER_OVERDRIVE_COOLDOWN
            damage = PLAYER_BULLET_DAMAGE + 1
        else:
            offsets = (0.0,)
            cooldown = PLAYER_COOLDOWN
            damage = PLAYER_BULLET_DAMAGE
        for offset in offsets:
            position = pygame.Vector2(self.player_rect.midright) + pygame.Vector2(0, offset)
            velocity = pygame.Vector2(BULLET_SPEED, offset * 4 * 0.3)
            bullet = Bullet(
                pos=position,
                velocity=velocity,
                damage=damage,
                color=pygame.Color(*PLAYER_BULLET_COLOR),
                size=(24, 8),
                from_player=True,
                glow_radius=32 if hyper else 24,
            )
            self.player_bullets.append(bullet)
        self.player_cooldown_timer = cooldown
        self.audio.play("laser", 1.0 if hyper else 0.8)
        self.spawn_muzzle_flash(pygame.Vector2(self.player_rect.midright))

    def update_player_bullets(self, dt: float) -> None:
        for bullet in self.player_bullets[:]:
            bullet.update(dt)
            if bullet.rect.left > SCREEN_WIDTH + 60:
                self.player_bullets.remove(bullet)
                continue
            hit_enemy = None
            for enemy in self.enemies:
                if bullet.rect.colliderect(enemy.rect):
                    hit_enemy = enemy
                    break
            if hit_enemy:
                destroyed = hit_enemy.apply_damage(bullet.damage)
                self.spawn_hit_sparks(pygame.Vector2(bullet.pos))
                self.audio.play("hit", 0.6)
                if destroyed:
                    self.handle_enemy_destroyed(hit_enemy)
                self.player_bullets.remove(bullet)

    def handle_enemy_destroyed(self, enemy: Enemy) -> None:
        if enemy in self.enemies:
            self.enemies.remove(enemy)
        self.spawn_explosion(pygame.Vector2(enemy.rect.center), sparks=32)
        self.audio.play("explosion", 0.7)
        combo_multiplier = 1.0 + 0.12 * self.combo
        self.combo += 1
        self.combo_timer = 3.0
        score_gain = int(enemy.score * combo_multiplier)
        self.score += score_gain
        drop_chance = 0.08 + 0.01 * self.stage
        if enemy.behavior == "boss":
            drop_chance = 1.0
        if random.random() < drop_chance:
            kind = random.choices(
                ["resupply", "overdrive", "vault"],
                weights=[0.45, 0.35, 0.2],
            )[0]
            self.spawn_powerup_drop(kind, pygame.Vector2(enemy.rect.center))

    def update_enemies(self, dt: float) -> None:
        player_pos = pygame.Vector2(self.player_rect.center)
        for enemy in self.enemies[:]:
            bullets = enemy.update(dt, player_pos)
            for bullet in bullets:
                self.enemy_bullets.append(bullet)
            if enemy.rect.right < -120 or enemy.rect.bottom < -120 or enemy.rect.top > SCREEN_HEIGHT + 120:
                self.enemies.remove(enemy)
                continue
            if enemy.rect.colliderect(self.player_rect) and self.player_invulnerable <= 0:
                self.player_hit()
                self.spawn_explosion(pygame.Vector2(enemy.rect.center), sparks=28)
                if enemy in self.enemies:
                    self.enemies.remove(enemy)

    def update_enemy_bullets(self, dt: float) -> None:
        for bullet in self.enemy_bullets[:]:
            bullet.update(dt)
            if bullet.rect.right < -40 or bullet.rect.top > SCREEN_HEIGHT + 40 or bullet.rect.bottom < -40:
                self.enemy_bullets.remove(bullet)
                continue
            if bullet.rect.colliderect(self.player_rect):
                if self.player_invulnerable <= 0:
                    self.player_hit()
                if bullet in self.enemy_bullets:
                    self.enemy_bullets.remove(bullet)

    def update_powerups(self, dt: float) -> None:
        for powerup in self.powerups[:]:
            powerup.update(dt)
            if powerup.rect.right < -60:
                self.powerups.remove(powerup)
                continue
            if powerup.rect.colliderect(self.player_rect):
                self.apply_powerup(powerup)
                if powerup in self.powerups:
                    self.powerups.remove(powerup)

    def update_particles(self, dt: float) -> None:
        alive_particles = []
        for particle in self.particles:
            if particle.update(dt):
                alive_particles.append(particle)
        self.particles = alive_particles

    def player_hit(self) -> None:
        self.lives -= 1
        self.player_invulnerable = PLAYER_INVULNERABLE_TIME
        self.spawn_explosion(pygame.Vector2(self.player_rect.center), sparks=40)
        self.audio.play("explosion", 0.9)
        self.player_rect.midleft = (120, SCREEN_HEIGHT // 2)
        self.player_pos = pygame.Vector2(self.player_rect.center)
        self.player_velocity = pygame.Vector2(0, 0)
        self.enemy_bullets.clear()
        self.combo = 0
        self.hyper_timer = 0.0
        if self.lives <= 0:
            self.state = "game_over"

    def apply_powerup(self, powerup: PowerUp) -> None:
        if powerup.kind == "resupply":
            if self.lives < self.max_lives:
                self.lives += 1
            else:
                self.score += 800
        elif powerup.kind == "overdrive":
            self.hyper_timer = max(self.hyper_timer, 8.0)
        elif powerup.kind == "vault":
            self.score += 1200 + 80 * self.stage
        self.audio.play("pickup", 0.8)
        color_value = POWERUP_TYPES[powerup.kind]["color"]  # type: ignore[index]
        colors = [tuple(color_value)]  # type: ignore[arg-type]
        self.spawn_particles(
            pygame.Vector2(powerup.rect.center),
            count=26,
            speed_range=(60, 220),
            colors=colors,
            lifetime_range=(0.25, 0.6),
        )

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

    def spawn_hit_sparks(self, position: pygame.Vector2) -> None:
        self.spawn_particles(
            position,
            count=10,
            speed_range=(90, 240),
            colors=SPARK_COLORS,
            lifetime_range=(0.15, 0.45),
        )

    def spawn_muzzle_flash(self, position: pygame.Vector2) -> None:
        colors = [(255, 220, 180), (255, 255, 200)]
        self.spawn_particles(
            position,
            count=8,
            speed_range=(80, 200),
            colors=colors,
            lifetime_range=(0.1, 0.3),
        )

    def spawn_thruster_particles(self) -> None:
        base = pygame.Vector2(self.player_rect.left - 6, self.player_rect.centery)
        colors = [(255, 150, 90), (255, 200, 120), (255, 255, 160)]
        for _ in range(3):
            velocity = pygame.Vector2(random.uniform(-200, -120), random.uniform(-40, 40))
            particle = Particle(
                pos=pygame.Vector2(base.x, base.y + random.uniform(-10, 10)),
                velocity=velocity,
                lifetime=random.uniform(0.25, 0.4),
                color=pygame.Color(*random.choice(colors)),
                radius=random.uniform(2, 4),
                fade=random.uniform(1.4, 2.0),
                gravity=20,
            )
            self.particles.append(particle)

    def spawn_explosion(self, position: pygame.Vector2, sparks: int = 24) -> None:
        colors = [(255, 200, 120), (255, 160, 80), (255, 240, 200)]
        self.spawn_particles(
            position,
            count=sparks,
            speed_range=(80, 340),
            colors=colors,
            lifetime_range=(0.2, 0.7),
        )

    # -- Drawing --------------------------------------------------------------------

    def draw(self) -> None:
        self.render_surface.blit(self.background_surface, (0, 0))
        self.draw_nebulae()
        self.draw_speed_trails()

        for star in self.stars:
            star.draw(self.render_surface, self.time_accumulator)

        for powerup in self.powerups:
            powerup.draw(self.render_surface, self.draw_glow)

        for enemy in self.enemies:
            self.draw_glow(self.render_surface, enemy.rect.center, 60, (140, 160, 255))
            enemy.draw(self.render_surface)

        for bullet in self.player_bullets + self.enemy_bullets:
            self.draw_bullet(bullet)

        self.draw_player()

        for particle in self.particles:
            particle.draw(self.render_surface)

        self.draw_hud()

        if self.state == "game_over":
            self.draw_game_over()

        scaled = pygame.transform.smoothscale(self.render_surface, self.window_size)
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def draw_nebulae(self) -> None:
        for nebula in self.nebulae:
            surface = nebula["surface"]
            x = int(nebula["x"])
            y = int(nebula["y"])
            self.render_surface.blit(surface, (x, y), special_flags=pygame.BLEND_RGBA_ADD)

    def draw_speed_trails(self) -> None:
        for trail in self.speed_trails:
            start = (trail["x"], trail["y"])
            end = (trail["x"] + trail["length"], trail["y"])
            color = pygame.Color(120, 140, 210, 120)
            pygame.draw.line(self.render_surface, color, start, end, width=int(trail["thickness"]))

    def draw_player(self) -> None:
        blink = (
            int(self.player_invulnerable * 10) % 2 == 0
            or self.player_invulnerable <= 0
            or self.state != "playing"
        )
        if not blink:
            return
        center = self.player_rect.center
        self.draw_glow(self.render_surface, center, 70 if self.hyper_timer > 0 else 56, PLAYER_GLOW_COLOR)
        tilt = max(-12, min(12, self.player_tilt))
        rotated = pygame.transform.rotate(self.player_surface, tilt)
        rect = rotated.get_rect(center=center)
        self.render_surface.blit(rotated, rect)
        flame_length = 28 + int(6 * math.sin(self.time_accumulator * 18))
        flame_color = pygame.Color(255, 170, 90, 200)
        flame = [
            (self.player_rect.left - flame_length, self.player_rect.centery),
            (self.player_rect.left - 10, self.player_rect.centery - 8),
            (self.player_rect.left - 10, self.player_rect.centery + 8),
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
        progress = min(1.0, self.stage_time / max(1e-5, self.stage_length))
        zone_text = self.font.render(f"SECTOR {self.stage} {int(progress * 100):02d}%", True, HUD_COLOR)
        lives_text = self.font.render(f"SHIPS {self.lives}", True, HUD_COLOR)
        self.render_surface.blit(score_text, (22, 20))
        self.render_surface.blit(zone_text, (SCREEN_WIDTH // 2 - zone_text.get_width() // 2, 20))
        self.render_surface.blit(lives_text, (SCREEN_WIDTH - lives_text.get_width() - 24, 20))
        if self.combo > 1:
            combo_text = self.small_font.render(f"COMBO x{self.combo}", True, HUD_COLOR)
            self.render_surface.blit(combo_text, (22, 52))
        if self.hyper_timer > 0:
            timer = self.small_font.render(f"OVERDRIVE {self.hyper_timer:0.1f}s", True, HUD_COLOR)
            self.render_surface.blit(timer, (SCREEN_WIDTH - timer.get_width() - 24, 52))
        elif self.focus_mode:
            focus_text = self.small_font.render("FOCUS", True, HUD_COLOR)
            self.render_surface.blit(focus_text, (SCREEN_WIDTH - focus_text.get_width() - 24, 52))
        if self.audio.enabled:
            volume = int(self.audio.master_volume * 100)
            label = "MUTED" if self.audio.muted or volume == 0 else f"VOL {volume}%"
            volume_text = self.small_font.render(f"{label} (M to toggle)", True, HUD_COLOR)
        else:
            volume_text = self.small_font.render("Audio unavailable", True, HUD_COLOR)
        self.render_surface.blit(volume_text, (22, 82))

    def draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.render_surface.blit(overlay, (0, 0))

        title = self.big_font.render("MISSION FAILED", True, HUD_COLOR)
        prompt = self.font.render("Press Enter to relaunch", True, HUD_COLOR)
        score = self.font.render(f"Final score: {self.score}", True, HUD_COLOR)

        self.render_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 140))
        self.render_surface.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
        self.render_surface.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT // 2 + 30))


# --- Entrypoint --------------------------------------------------------------------


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
