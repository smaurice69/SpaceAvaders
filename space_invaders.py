#!/usr/bin/env python3
"""Space Avaders - a spruced-up Space-Invaders inspired clone.

The game keeps the classic arcadey gameplay while adding modern flourishes:
    * Aliens and shields take partial damage with visible wear and tear.
    * New procedural sprites, glowing bullets, and light-weight animations.
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
from typing import Dict, List, Optional, Tuple

import pygame


# --- Configuration -----------------------------------------------------------------

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
FPS = 60

PLAYER_SPEED = 320
PLAYER_WIDTH = 72
PLAYER_HEIGHT = 34
PLAYER_COOLDOWN = 0.3  # seconds between shots
PLAYER_LIVES = 3
PLAYER_INVULNERABLE_TIME = 1.5

BULLET_SPEED = 540
ALIEN_BULLET_SPEED = 240
PLAYER_BULLET_DAMAGE = 1
ALIEN_BULLET_DAMAGE = 1

ALIEN_ROWS_START = 4
ALIEN_COLUMNS = 10
ALIEN_ROW_GAP = 62
ALIEN_COL_GAP = 72
ALIEN_WIDTH = 52
ALIEN_HEIGHT = 36

ALIEN_BASE_SPEED = 40
ALIEN_SPEED_PER_LEVEL = 12
ALIEN_SPEED_SCALE = 220
ALIEN_DROP_DISTANCE = 26

ALIEN_FIRE_MIN_INTERVAL = 1.0
ALIEN_FIRE_MAX_INTERVAL = 2.6

UFO_SPAWN_MIN = 18
UFO_SPAWN_MAX = 32
UFO_SPEED = 210
UFO_SCORE = 150

SHIELD_COUNT = 3
SHIELD_TILE_ROWS = 4
SHIELD_TILE_COLS = 7
SHIELD_TILE_SIZE = 18
SHIELD_TILE_MAX_HEALTH = 4

STAR_COUNT = 90

BACKGROUND_GRADIENT_TOP = (10, 12, 28)
BACKGROUND_GRADIENT_BOTTOM = (4, 4, 12)
PLAYER_COLOR = (80, 200, 255)
PLAYER_GLOW_COLOR = (50, 140, 255)
PLAYER_BULLET_COLOR = (255, 230, 150)
ALIEN_COLORS = [
    (100, 255, 170),
    (120, 240, 100),
    (255, 190, 100),
    (255, 120, 150),
    (255, 100, 210),
]
ALIEN_BULLET_COLOR = (255, 150, 150)
UFO_COLOR = (255, 120, 120)
HUD_COLOR = (240, 240, 240)
SHIELD_COLOR = (120, 220, 180)
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
        self.y += self.speed * dt
        if self.y > SCREEN_HEIGHT + 5:
            self.y = -5
            self.x = random.uniform(0, SCREEN_WIDTH)
            self.speed = random.uniform(20, 90)
            self.radius = random.uniform(1.0, 2.3)
            self.twinkle_speed = random.uniform(0.8, 2.4)
            self.phase = random.uniform(0, math.tau)

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
class Alien:
    rect: pygame.Rect
    row: int
    surface: pygame.Surface
    max_health: int
    health: int
    wobble_phase: float = field(default_factory=lambda: random.uniform(0, math.tau))
    hit_flash: float = 0.0

    def apply_damage(self, amount: int, impact_point: Tuple[int, int]) -> bool:
        self.health = max(0, self.health - amount)
        self.hit_flash = 0.2
        local_x = max(0, min(self.surface.get_width() - 1, impact_point[0] - self.rect.x))
        local_y = max(0, min(self.surface.get_height() - 1, impact_point[1] - self.rect.y))
        radius = random.randint(6, 10)
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

    def update(self, dt: float) -> None:
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt * 4)

    def draw(self, surface: pygame.Surface, time_accumulator: float) -> None:
        dest = self.rect.copy()
        dest.y += int(math.sin(time_accumulator * 3.0 + self.wobble_phase + self.row) * 3)
        surface.blit(self.surface, dest)
        if self.hit_flash > 0:
            flash_alpha = int(200 * self.hit_flash)
            pygame.draw.rect(surface, (255, 255, 255, flash_alpha), dest, border_radius=10)
        if self.health < self.max_health:
            ratio = self.health / self.max_health
            bar_bg = pygame.Rect(dest.x + 6, dest.y - 6, dest.width - 12, 4)
            pygame.draw.rect(surface, (20, 20, 30, 180), bar_bg, border_radius=2)
            bar = bar_bg.copy()
            bar.width = max(0, int(bar.width * ratio))
            pygame.draw.rect(surface, (90, 255, 160, 220), bar, border_radius=2)


@dataclass
class ShieldTile:
    rect: pygame.Rect
    max_health: int
    health: int
    hit_flash: float = 0.0
    crack_seed: float = field(default_factory=random.random)


@dataclass
class Shield:
    rect: pygame.Rect
    tiles: List[ShieldTile]
    color: pygame.Color

    def update(self, dt: float) -> None:
        for tile in self.tiles:
            if tile.hit_flash > 0:
                tile.hit_flash = max(0.0, tile.hit_flash - dt * 3)

    def apply_damage(self, bullet_rect: pygame.Rect, damage: int) -> bool:
        for tile in self.tiles:
            if tile.health <= 0:
                continue
            if tile.rect.colliderect(bullet_rect):
                tile.health = max(0, tile.health - damage)
                tile.hit_flash = 0.2
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        for tile in self.tiles:
            if tile.health <= 0:
                continue
            ratio = tile.health / tile.max_health
            base = pygame.Color(self.color)
            color = pygame.Color(
                int(base.r * (0.6 + 0.4 * ratio)),
                int(base.g * (0.6 + 0.4 * ratio)),
                int(base.b * (0.6 + 0.4 * ratio)),
                235,
            )
            if tile.hit_flash > 0:
                color = color.lerp(pygame.Color(255, 255, 255), 0.6 * tile.hit_flash)
            pygame.draw.rect(surface, color, tile.rect, border_radius=6)
            if ratio < 1.0:
                crack_color = pygame.Color(30, 50, 70, 180)
                rand = random.Random(tile.crack_seed)
                cracks = 1 + int((1 - ratio) * 3)
                for _ in range(cracks):
                    start = (
                        tile.rect.x + rand.randint(0, tile.rect.width),
                        tile.rect.y + rand.randint(0, tile.rect.height),
                    )
                    end = (
                        tile.rect.x + rand.randint(0, tile.rect.width),
                        tile.rect.y + rand.randint(0, tile.rect.height),
                    )
                    pygame.draw.line(surface, crack_color, start, end, width=1)


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
        self.player_rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
        self.player_x = float(self.player_rect.x)
        self.player_velocity = 0.0
        self.player_cooldown_timer = 0.0
        self.player_invulnerable = 0.0
        self.player_thruster_timer = 0.0
        self.player_tilt = 0.0
        self.lives = PLAYER_LIVES

        self.player_bullets: List[Bullet] = []
        self.alien_bullets: List[Bullet] = []

        self.particles: List[Particle] = []

        self.aliens: List[Alien] = []
        self.alien_rows = ALIEN_ROWS_START
        self.total_aliens = 0
        self.level = 1
        self.alien_direction = 1
        self.alien_dx_buffer = 0.0
        self.alien_fire_timer = 0.0

        self.shields: List[Shield] = []

        self.ufo_rect: Optional[pygame.Rect] = None
        self.ufo_direction = 1
        self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)
        self.ufo_surface = self._create_ufo_surface()

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
        surface = surface.convert()
        return surface

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

    def _create_ufo_surface(self) -> pygame.Surface:
        width, height = 90, 34
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        for y in range(height):
            t = y / max(1, height - 1)
            color = lerp_color(lighten(UFO_COLOR, 0.2), darken(UFO_COLOR, 0.6), t)
            pygame.draw.line(surface, color, (10, y), (width - 10, y))
        pygame.draw.ellipse(surface, (255, 220, 220, 220), (18, 6, width - 36, height - 12))
        pygame.draw.rect(surface, (255, 240, 240, 200), (width // 2 - 12, 4, 24, 12), border_radius=6)
        return surface.convert_alpha()

    def _setup_stars(self) -> None:
        self.stars.clear()
        for _ in range(STAR_COUNT):
            self.stars.append(
                Star(
                    x=random.uniform(0, SCREEN_WIDTH),
                    y=random.uniform(0, SCREEN_HEIGHT),
                    speed=random.uniform(20, 90),
                    color=pygame.Color(*random.choice(STAR_COLORS)),
                    radius=random.uniform(1.0, 2.3),
                    twinkle_speed=random.uniform(0.8, 2.4),
                    phase=random.uniform(0, math.tau),
                )
            )

    def reset(self) -> None:
        self.level = 1
        self.score = 0
        self.lives = PLAYER_LIVES
        self.player_rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
        self.player_x = float(self.player_rect.x)
        self.player_velocity = 0.0
        self.player_cooldown_timer = 0.0
        self.player_invulnerable = 1.0
        self.player_thruster_timer = 0.0
        self.player_tilt = 0.0
        self.player_bullets.clear()
        self.alien_bullets.clear()
        self.particles.clear()
        self.alien_rows = ALIEN_ROWS_START
        self.alien_direction = 1
        self.alien_dx_buffer = 0.0
        self.alien_fire_timer = random.uniform(ALIEN_FIRE_MIN_INTERVAL, ALIEN_FIRE_MAX_INTERVAL)
        self.ufo_rect = None
        self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)
        self.state = "playing"
        self.shields = self._create_shields()
        self.spawn_wave()

    def _create_shields(self) -> List[Shield]:
        shields: List[Shield] = []
        shield_width = SHIELD_TILE_COLS * SHIELD_TILE_SIZE
        y = SCREEN_HEIGHT - 170
        spacing = SCREEN_WIDTH // (SHIELD_COUNT + 1)
        for index in range(SHIELD_COUNT):
            center_x = spacing * (index + 1)
            left = int(center_x - shield_width / 2)
            rect = pygame.Rect(left, y, shield_width, SHIELD_TILE_ROWS * SHIELD_TILE_SIZE)
            tiles: List[ShieldTile] = []
            for row in range(SHIELD_TILE_ROWS):
                for col in range(SHIELD_TILE_COLS):
                    if row == 0 and (col < 1 or col > SHIELD_TILE_COLS - 2):
                        continue
                    if row == 1 and (col == 0 or col == SHIELD_TILE_COLS - 1):
                        continue
                    if row == SHIELD_TILE_ROWS - 1 and col in (0, SHIELD_TILE_COLS - 1):
                        continue
                    tile_rect = pygame.Rect(
                        rect.x + col * SHIELD_TILE_SIZE,
                        rect.y + row * SHIELD_TILE_SIZE,
                        SHIELD_TILE_SIZE - 2,
                        SHIELD_TILE_SIZE - 2,
                    )
                    tiles.append(
                        ShieldTile(
                            rect=tile_rect,
                            max_health=SHIELD_TILE_MAX_HEALTH,
                            health=SHIELD_TILE_MAX_HEALTH,
                        )
                    )
            shields.append(Shield(rect=rect, tiles=tiles, color=pygame.Color(*SHIELD_COLOR)))
        return shields

    def spawn_wave(self) -> None:
        rows = ALIEN_ROWS_START + min(self.level - 1, 3)
        self.alien_rows = rows
        cols = ALIEN_COLUMNS
        top_offset = 120
        left_offset = (SCREEN_WIDTH - (cols - 1) * ALIEN_COL_GAP) // 2 - ALIEN_WIDTH // 2

        self.aliens.clear()
        for row in range(rows):
            for col in range(cols):
                rect = pygame.Rect(0, 0, ALIEN_WIDTH, ALIEN_HEIGHT)
                rect.x = left_offset + col * ALIEN_COL_GAP
                rect.y = top_offset + row * ALIEN_ROW_GAP
                base_color = ALIEN_COLORS[row % len(ALIEN_COLORS)]
                alien_surface = self._create_alien_surface(base_color)
                base_health = 2 + (self.level - 1) // 2
                health = base_health + row // 2
                self.aliens.append(
                    Alien(
                        rect=rect,
                        row=row,
                        surface=alien_surface,
                        max_health=health,
                        health=health,
                    )
                )
        self.total_aliens = len(self.aliens)
        self.alien_direction = 1
        self.alien_dx_buffer = 0.0
        self.alien_fire_timer = random.uniform(ALIEN_FIRE_MIN_INTERVAL, ALIEN_FIRE_MAX_INTERVAL)

    def _create_alien_surface(self, base_color: Tuple[int, int, int]) -> pygame.Surface:
        surface = pygame.Surface((ALIEN_WIDTH, ALIEN_HEIGHT), pygame.SRCALPHA)
        highlight = lighten(base_color, 0.25)
        shadow = darken(base_color, 0.55)
        for y in range(ALIEN_HEIGHT):
            t = y / max(1, ALIEN_HEIGHT - 1)
            color = lerp_color(highlight, shadow, t)
            pygame.draw.line(surface, color, (8, y), (ALIEN_WIDTH - 8, y))
        pygame.draw.ellipse(surface, lighten(base_color, 0.4), (10, 4, ALIEN_WIDTH - 20, 20))
        pygame.draw.ellipse(surface, (20, 20, 35, 120), (14, 8, ALIEN_WIDTH - 28, 12))
        eye_color = pygame.Color(10, 20, 30, 200)
        pygame.draw.circle(surface, eye_color, (ALIEN_WIDTH // 3, ALIEN_HEIGHT // 2), 5)
        pygame.draw.circle(surface, eye_color, (ALIEN_WIDTH * 2 // 3, ALIEN_HEIGHT // 2), 5)
        glow = pygame.Surface((ALIEN_WIDTH, ALIEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*lighten(base_color, 0.6), 120), (-10, ALIEN_HEIGHT // 2, ALIEN_WIDTH + 20, ALIEN_HEIGHT))
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return surface.convert_alpha()

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

        for shield in self.shields:
            shield.update(dt)

        if self.state != "playing":
            self.update_particles(dt)
            return

        self.update_player(dt)
        self.update_player_bullets(dt)
        self.update_aliens(dt)
        self.update_alien_bullets(dt)
        self.update_ufo(dt)
        self.update_particles(dt)

    def update_player(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        target_velocity = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            target_velocity -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            target_velocity += PLAYER_SPEED
        self.player_velocity = target_velocity
        self.player_x += self.player_velocity * dt
        self.player_x = max(40, min(SCREEN_WIDTH - 40 - PLAYER_WIDTH, self.player_x))
        previous_x = self.player_rect.x
        self.player_rect.x = int(self.player_x)
        delta_x = self.player_rect.x - previous_x
        self.player_tilt = lerp(self.player_tilt, -delta_x * 0.3, min(1.0, dt * 10))

        if self.player_cooldown_timer > 0:
            self.player_cooldown_timer -= dt
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP]) and self.player_cooldown_timer <= 0:
            bullet = Bullet(
                pos=pygame.Vector2(self.player_rect.centerx, self.player_rect.top - 8),
                velocity=pygame.Vector2(0, -BULLET_SPEED),
                damage=PLAYER_BULLET_DAMAGE,
                color=pygame.Color(*PLAYER_BULLET_COLOR),
                size=(8, 20),
                from_player=True,
                glow_radius=26,
            )
            self.player_bullets.append(bullet)
            self.player_cooldown_timer = PLAYER_COOLDOWN
            self.audio.play("laser", 0.8)
            self.spawn_muzzle_flash(pygame.Vector2(bullet.pos))

        self.player_thruster_timer += dt
        if self.player_thruster_timer >= 0.05:
            self.player_thruster_timer = 0.0
            self.spawn_thruster_particles()

        if self.player_invulnerable > 0:
            self.player_invulnerable -= dt

    def update_player_bullets(self, dt: float) -> None:
        for bullet in self.player_bullets[:]:
            bullet.update(dt)
            if bullet.rect.bottom < 0:
                self.player_bullets.remove(bullet)
                continue
            if self.damage_shields(bullet.rect, PLAYER_BULLET_DAMAGE):
                self.player_bullets.remove(bullet)
                self.audio.play("shield", 0.4)
                self.spawn_hit_sparks(pygame.Vector2(bullet.pos), tone="shield")
                continue
            hit_alien = None
            for alien in self.aliens:
                if bullet.rect.colliderect(alien.rect):
                    hit_alien = alien
                    break
            if hit_alien:
                destroyed = hit_alien.apply_damage(PLAYER_BULLET_DAMAGE, bullet.rect.center)
                self.spawn_hit_sparks(pygame.Vector2(bullet.pos))
                self.audio.play("hit", 0.5)
                if destroyed:
                    self.aliens.remove(hit_alien)
                    score_gain = 20 + 6 * (self.alien_rows - hit_alien.row)
                    self.score += score_gain
                    self.spawn_explosion(pygame.Vector2(hit_alien.rect.center))
                    self.audio.play("explosion", 0.7)
                self.player_bullets.remove(bullet)
                continue
            if self.ufo_rect and bullet.rect.colliderect(self.ufo_rect):
                self.score += UFO_SCORE
                self.spawn_explosion(pygame.Vector2(self.ufo_rect.center), sparks=30)
                self.audio.play("explosion", 0.7)
                self.ufo_rect = None
                self.player_bullets.remove(bullet)
                continue
        if not self.aliens:
            self.level += 1
            self.player_bullets.clear()
            self.alien_bullets.clear()
            self.spawn_wave()

    def update_aliens(self, dt: float) -> None:
        if not self.aliens:
            return
        min_x = min(alien.rect.x for alien in self.aliens)
        max_x = max(alien.rect.x + alien.rect.width for alien in self.aliens)

        speed = self.current_alien_speed()
        dx = speed * self.alien_direction * dt

        if min_x + dx < 30 or max_x + dx > SCREEN_WIDTH - 30:
            self.alien_direction *= -1
            dx = self.alien_direction * speed * dt
            for alien in self.aliens:
                alien.rect.y += ALIEN_DROP_DISTANCE
                if alien.rect.bottom >= self.player_rect.top:
                    self.player_hit()

        self.alien_dx_buffer += dx
        move = 0
        if self.alien_dx_buffer >= 1:
            move = int(self.alien_dx_buffer)
        elif self.alien_dx_buffer <= -1:
            move = int(self.alien_dx_buffer)
        if move:
            for alien in self.aliens:
                alien.rect.x += move
            self.alien_dx_buffer -= move

        for alien in self.aliens:
            alien.update(dt)

        self.alien_fire_timer -= dt
        if self.alien_fire_timer <= 0:
            self.fire_alien_bullet()
            interval = random.uniform(ALIEN_FIRE_MIN_INTERVAL, ALIEN_FIRE_MAX_INTERVAL)
            interval = max(0.25, interval - (self.level - 1) * 0.1)
            self.alien_fire_timer = interval

    def current_alien_speed(self) -> float:
        if not self.aliens:
            return ALIEN_BASE_SPEED
        alive_ratio = len(self.aliens) / max(1, self.total_aliens)
        base = ALIEN_BASE_SPEED + (self.level - 1) * ALIEN_SPEED_PER_LEVEL
        bonus = (1.0 - alive_ratio) * ALIEN_SPEED_SCALE
        return base + bonus

    def fire_alien_bullet(self) -> None:
        if not self.aliens:
            return
        columns: Dict[int, List[Alien]] = {}
        for alien in self.aliens:
            columns.setdefault(alien.rect.x, []).append(alien)
        shooter_column = random.choice(list(columns.values()))
        shooter = max(shooter_column, key=lambda a: a.rect.y)
        bullet = Bullet(
            pos=pygame.Vector2(shooter.rect.centerx, shooter.rect.bottom + 10),
            velocity=pygame.Vector2(0, ALIEN_BULLET_SPEED + self.level * 32),
            damage=ALIEN_BULLET_DAMAGE,
            color=pygame.Color(*ALIEN_BULLET_COLOR),
            size=(6, 16),
            from_player=False,
            glow_radius=20,
        )
        self.alien_bullets.append(bullet)

    def update_alien_bullets(self, dt: float) -> None:
        for bullet in self.alien_bullets[:]:
            bullet.update(dt)
            if bullet.rect.top > SCREEN_HEIGHT + 40:
                self.alien_bullets.remove(bullet)
                continue
            if self.damage_shields(bullet.rect, ALIEN_BULLET_DAMAGE):
                self.alien_bullets.remove(bullet)
                self.audio.play("shield", 0.5)
                self.spawn_hit_sparks(pygame.Vector2(bullet.pos), tone="shield")
                continue
            if bullet.rect.colliderect(self.player_rect):
                if self.player_invulnerable <= 0:
                    self.player_hit()
                if bullet in self.alien_bullets:
                    self.alien_bullets.remove(bullet)

    def update_ufo(self, dt: float) -> None:
        if self.ufo_rect:
            self.ufo_rect.x += int(self.ufo_direction * UFO_SPEED * dt)
            if self.ufo_rect.right < -100 or self.ufo_rect.left > SCREEN_WIDTH + 100:
                self.ufo_rect = None
                self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)
        else:
            self.ufo_timer -= dt
            if self.ufo_timer <= 0 and self.level > 1:
                direction = random.choice([-1, 1])
                if direction == 1:
                    rect = pygame.Rect(-120, 80, self.ufo_surface.get_width(), self.ufo_surface.get_height())
                else:
                    rect = pygame.Rect(
                        SCREEN_WIDTH + 50,
                        80,
                        self.ufo_surface.get_width(),
                        self.ufo_surface.get_height(),
                    )
                self.ufo_rect = rect
                self.ufo_direction = direction
                self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)

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
        self.player_rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
        self.player_x = float(self.player_rect.x)
        self.alien_bullets.clear()
        if self.lives <= 0:
            self.state = "game_over"

    def damage_shields(self, rect: pygame.Rect, damage: int) -> bool:
        for shield in self.shields:
            if shield.apply_damage(rect, damage):
                return True
        return False

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
            speed_range=(60, 180),
            colors=colors,
            lifetime_range=(0.1, 0.3),
        )

    def spawn_thruster_particles(self) -> None:
        base = pygame.Vector2(self.player_rect.centerx, self.player_rect.bottom + 4)
        colors = [(255, 150, 90), (255, 200, 120), (255, 255, 160)]
        for _ in range(3):
            velocity = pygame.Vector2(random.uniform(-20, 20), random.uniform(120, 200))
            particle = Particle(
                pos=pygame.Vector2(base.x + random.uniform(-8, 8), base.y),
                velocity=velocity,
                lifetime=random.uniform(0.2, 0.4),
                color=pygame.Color(*random.choice(colors)),
                radius=random.uniform(2, 4),
                fade=random.uniform(1.4, 2.0),
                gravity=-40,
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

        for star in self.stars:
            star.draw(self.render_surface, self.time_accumulator)

        if self.ufo_rect:
            self.draw_glow(self.render_surface, self.ufo_rect.center, 70, (255, 60, 80))
            self.render_surface.blit(self.ufo_surface, self.ufo_rect)

        for alien in self.aliens:
            alien.draw(self.render_surface, self.time_accumulator)

        for shield in self.shields:
            shield.draw(self.render_surface)

        for bullet in self.player_bullets + self.alien_bullets:
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

    def draw_player(self) -> None:
        blink = int(self.player_invulnerable * 10) % 2 == 0 or self.player_invulnerable <= 0 or self.state != "playing"
        if not blink:
            return
        center = self.player_rect.center
        self.draw_glow(self.render_surface, center, 60, PLAYER_GLOW_COLOR)
        tilt = max(-8, min(8, self.player_tilt))
        rotated = pygame.transform.rotate(self.player_surface, tilt)
        rect = rotated.get_rect(center=center)
        self.render_surface.blit(rotated, rect)
        flame_height = 18 + int(6 * math.sin(self.time_accumulator * 18))
        flame_color = pygame.Color(255, 170, 90, 200)
        flame = [
            (self.player_rect.centerx - 10, self.player_rect.bottom - 4),
            (self.player_rect.centerx + 10, self.player_rect.bottom - 4),
            (self.player_rect.centerx, self.player_rect.bottom + flame_height),
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
        score_text = self.font.render(f"SCORE {self.score:06d}", True, HUD_COLOR)
        level_text = self.font.render(f"WAVE {self.level}", True, HUD_COLOR)
        lives_text = self.font.render(f"LIVES {self.lives}", True, HUD_COLOR)
        self.render_surface.blit(score_text, (22, 20))
        self.render_surface.blit(level_text, (SCREEN_WIDTH // 2 - level_text.get_width() // 2, 20))
        self.render_surface.blit(lives_text, (SCREEN_WIDTH - lives_text.get_width() - 24, 20))
        if self.audio.enabled:
            volume = int(self.audio.master_volume * 100)
            label = "MUTED" if self.audio.muted or volume == 0 else f"VOL {volume}%"
            volume_text = self.small_font.render(f"{label} (M to toggle)", True, HUD_COLOR)
        else:
            volume_text = self.small_font.render("Audio unavailable", True, HUD_COLOR)
        self.render_surface.blit(volume_text, (22, 52))

    def draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.render_surface.blit(overlay, (0, 0))

        title = self.big_font.render("GAME OVER", True, HUD_COLOR)
        prompt = self.font.render("Press Enter to try again", True, HUD_COLOR)
        score = self.font.render(f"Final score: {self.score}", True, HUD_COLOR)

        self.render_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 120))
        self.render_surface.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
        self.render_surface.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT // 2 + 30))


# --- Entrypoint --------------------------------------------------------------------


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
