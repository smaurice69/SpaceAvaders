#!/usr/bin/env python3
"""Space Avaders 2084 – a side-scrolling love letter to early console shooters.

This rewrite pivots the classic fixed-screen homage into a kinetic, side-scrolling
space opera inspired by the likes of *Gradius*, *Defender*, and *R-Type*.  The
player now sprints through neon nebulae while scripted waves, parallax skylines,
and bite-sized bosses keep the pressure on.  Everything is still rendered with
procedural rectangles and gradients, but the cadence is faster, the controls are
smoother, and the pacing borrows the best set-pieces from the 8-bit era.

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

SCROLL_SPEED = 130

PLAYER_SPEED_X = 360
PLAYER_SPEED_Y = 320
PLAYER_WIDTH = 64
PLAYER_HEIGHT = 38
PLAYER_COOLDOWN = 0.35
PLAYER_RAPID_COOLDOWN = 0.18
PLAYER_LIVES = 4
PLAYER_INVULNERABLE_TIME = 2.0
PLAYER_THRUSTER_INTERVAL = 0.05

PLAYER_BULLET_DAMAGE = 1
PLAYER_BULLET_SPEED = 640

ENEMY_BULLET_DAMAGE = 1
ENEMY_BULLET_SPEED = 260

COMBO_TIMEOUT = 3.0

STAR_COUNT = 120

BACKGROUND_GRADIENT_TOP = (4, 8, 26)
BACKGROUND_GRADIENT_BOTTOM = (2, 2, 10)
PARALLAX_COLORS = [
    (12, 24, 70, 80),
    (18, 36, 110, 100),
    (32, 60, 160, 120),
]
PLAYER_COLOR = (120, 220, 255)
PLAYER_GLOW_COLOR = (80, 170, 255)
PLAYER_FLAME_COLOR = (255, 170, 90, 210)
PLAYER_BULLET_COLOR = (255, 240, 170)

ENEMY_COLOR_CYCLE = [
    (255, 160, 160),
    (255, 210, 120),
    (140, 240, 190),
    (140, 180, 255),
    (255, 140, 220),
]

ENEMY_BULLET_COLOR = (255, 120, 160)
BOSS_BULLET_COLOR = (180, 255, 180)

HUD_COLOR = (235, 235, 240)
COMBO_COLOR = (255, 200, 120)
BANNER_COLOR = (255, 255, 255)

SPARK_COLORS = [
    (255, 210, 150),
    (255, 160, 120),
    (255, 255, 200),
]
STAR_COLORS = [
    (180, 180, 255),
    (130, 130, 220),
    (90, 90, 180),
]
POWERUP_COLORS = {
    "rapid": (140, 255, 220),
    "shield": (255, 180, 120),
    "score": (255, 230, 140),
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
    pos: pygame.Vector2
    speed: float
    color: pygame.Color
    radius: float
    twinkle_speed: float
    phase: float

    def update(self, dt: float) -> None:
        self.pos.x -= self.speed * dt
        if self.pos.x < -10:
            self.pos.x = SCREEN_WIDTH + random.uniform(10, 160)
            self.pos.y = random.uniform(0, SCREEN_HEIGHT)
            self.speed = random.uniform(40, 160)
            self.radius = random.uniform(1.0, 2.6)
            self.twinkle_speed = random.uniform(0.8, 2.8)
            self.phase = random.uniform(0, math.tau)

    def draw(self, surface: pygame.Surface, time_accumulator: float) -> None:
        twinkle = 0.6 + 0.4 * math.sin(self.phase + time_accumulator * self.twinkle_speed)
        alpha = int(120 + 110 * twinkle)
        color = pygame.Color(self.color)
        color.a = alpha
        pygame.draw.circle(surface, color, (int(self.pos.x), int(self.pos.y)), int(self.radius))


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
class FloatingText:
    text: str
    pos: pygame.Vector2
    velocity: pygame.Vector2
    lifetime: float
    color: pygame.Color
    scale: float = 1.0

    def update(self, dt: float) -> bool:
        self.pos += self.velocity * dt
        self.velocity.y -= 20 * dt
        self.lifetime -= dt
        return self.lifetime > 0


@dataclass
class Enemy:
    pos: pygame.Vector2
    rect: pygame.Rect
    surface: pygame.Surface
    behavior: str
    base_y: float
    amplitude: float
    frequency: float
    speed: float
    direction: float
    health: int
    max_health: int
    score: int
    fire_rate: float = 0.0
    fire_timer: float = 0.0
    bullet_speed: float = ENEMY_BULLET_SPEED
    bullet_color: pygame.Color = field(default_factory=lambda: pygame.Color(*ENEMY_BULLET_COLOR))
    timer: float = 0.0
    hit_flash: float = 0.0
    data: Dict[str, float] = field(default_factory=dict)

    def update(self, dt: float) -> None:
        self.timer += dt
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt * 5)

        if self.behavior == "sine":
            self.pos.x += self.direction * self.speed * dt
            self.pos.y = self.base_y + math.sin(self.timer * self.frequency) * self.amplitude
        elif self.behavior == "arc":
            self.pos.x += self.direction * self.speed * dt
            angle = self.data.setdefault("angle", 0.0)
            angle += dt * self.frequency * self.direction
            radius = self.amplitude
            self.pos.y = self.base_y + math.sin(angle) * radius
            self.data["angle"] = angle
        elif self.behavior == "charger":
            delay = self.data.get("delay", 1.2)
            if self.timer < delay:
                self.pos.x += self.direction * self.speed * dt
                self.pos.y = self.base_y + math.sin(self.timer * self.frequency) * self.amplitude
            else:
                if not self.data.get("locked_dir"):
                    target: pygame.Vector2 = self.data.get("target", pygame.Vector2(self.pos))
                    direction = (target - self.pos)
                    if direction.length_squared() > 0.0:
                        direction = direction.normalize()
                    else:
                        direction = pygame.Vector2(self.direction, 0)
                    self.data["charge_dir"] = direction
                    self.data["locked_dir"] = 1.0
                direction = self.data.get("charge_dir", pygame.Vector2(self.direction, 0))
                self.pos += direction * (self.speed * 1.9) * dt
        elif self.behavior == "turret":
            self.pos.x += self.direction * self.speed * dt
            bob = math.sin(self.timer * 1.5 + self.base_y * 0.05) * (self.amplitude or 12)
            self.pos.y = self.base_y + bob
        elif self.behavior == "meteor":
            self.pos += pygame.Vector2(self.direction * self.speed, self.frequency * 40).rotate(self.base_y) * dt
        elif self.behavior == "boss":
            anchor_x = self.data.get("anchor_x", SCREEN_WIDTH - 280)
            self.pos.x += self.direction * self.speed * dt
            if self.direction < 0 and self.pos.x <= anchor_x:
                self.pos.x = anchor_x
                self.direction = 0
            self.pos.y = self.base_y + math.sin(self.timer * self.frequency) * self.amplitude
        else:
            self.pos.x += self.direction * self.speed * dt

        self.rect.center = (int(self.pos.x), int(self.pos.y))


@dataclass
class PowerUp:
    pos: pygame.Vector2
    rect: pygame.Rect
    kind: str
    velocity: pygame.Vector2
    color: pygame.Color
    lifetime: float = 14.0
    bob: float = 0.0

    def update(self, dt: float) -> bool:
        self.bob += dt * 2.5
        offset = math.sin(self.bob) * 8
        self.pos += self.velocity * dt
        self.rect.center = (int(self.pos.x), int(self.pos.y + offset))
        self.lifetime -= dt
        return self.lifetime > 0 and self.rect.right > -60


@dataclass
class StageEvent:
    time: float
    action: str
    params: Dict[str, float]


class StageDirector:
    """Coordinates scripted waves for each stage."""

    THEMES = [
        ("Launch Bay Echoes", "Galaga-style vanguards line the horizon."),
        ("Crystal Canyon Run", "Gradius turrets ignite the skyline."),
        ("Nebula Outrun", "Defender raiders chase your thrusters."),
        ("Orbital Siege", "R-Type fortress cores awake."),
        ("Starlight Rebellion", "Mega Man sky fortresses lend their rhythm."),
    ]

    def __init__(self, game: "Game") -> None:
        self.game = game
        self.elapsed = 0.0
        self.events: List[StageEvent] = []
        self.index = 0
        self.completed = False
        self.theme_name = ""
        self.tagline = ""
        self.total_duration = 0.0
        self._build_script()

    def _theme_for_level(self) -> Tuple[str, str]:
        return self.THEMES[(self.game.level - 1) % len(self.THEMES)]

    def _build_script(self) -> None:
        level = self.game.level
        self.theme_name, self.tagline = self._theme_for_level()
        self.game.stage_name = self.theme_name
        self.game.push_banner(f"Stage {level}: {self.theme_name}", hold=3.5)
        self.game.stage_tagline = self.tagline

        base_speed = 150 + level * 10
        base_amplitude = 70 + level * 6
        base_frequency = 1.6 + level * 0.08
        timeline: List[StageEvent] = []
        t = 0.6

        def schedule(delay: float, action: str, **params: float) -> None:
            nonlocal t
            t += delay
            timeline.append(StageEvent(time=t, action=action, params=params))

        schedule(0.2, "banner", text=self.tagline, hold=3.0)
        schedule(0.5, "sine_wave", count=6 + level * 2, center=SCREEN_HEIGHT * 0.32, amplitude=base_amplitude, speed=base_speed, frequency=base_frequency)
        schedule(0.4, "sine_wave", count=6 + level * 2, center=SCREEN_HEIGHT * 0.68, amplitude=base_amplitude * 0.9, speed=base_speed * 1.05, frequency=base_frequency * 1.1)
        schedule(1.2, "arc_climb", count=5 + level, center=SCREEN_HEIGHT * 0.45, radius=120 + level * 14, speed=base_speed * 0.9)
        schedule(0.8, "turret_line", count=max(3, 2 + level // 2), y=SCREEN_HEIGHT - 140, spacing=220 - level * 10, speed=80 + level * 10)
        schedule(1.4, "charger_swarm", count=3 + level, top=160, gap=90, speed=200 + level * 16)
        schedule(1.6, "meteor_field", count=5 + level * 2, speed=150 + level * 12)
        schedule(1.8, "drift_column", count=4 + level, start=100, gap=70, speed=130 + level * 8)
        schedule(2.4, "banner", text="Boss: Titan of the Neon Void", hold=3.5)
        schedule(0.6, "boss", health=28 + level * 7, speed=110 + level * 6)

        self.events = timeline
        self.elapsed = 0.0
        self.index = 0
        self.completed = False
        self.total_duration = timeline[-1].time if timeline else 0.0

    def update(self, dt: float) -> None:
        if self.completed:
            return
        self.elapsed += dt
        while self.index < len(self.events) and self.elapsed >= self.events[self.index].time:
            event = self.events[self.index]
            self.index += 1
            self._trigger(event)
        if self.index >= len(self.events):
            self.completed = True

    def _trigger(self, event: StageEvent) -> None:
        action = event.action
        params = event.params
        if action == "banner":
            text = str(params.get("text", ""))
            hold = float(params.get("hold", 3.0))
            if text:
                self.game.push_banner(text, hold=hold)
        elif action == "sine_wave":
            self.game.spawn_sine_wave(
                count=int(params.get("count", 6)),
                center=float(params.get("center", SCREEN_HEIGHT / 2)),
                amplitude=float(params.get("amplitude", 80)),
                speed=float(params.get("speed", 160)),
                frequency=float(params.get("frequency", 1.6)),
            )
        elif action == "arc_climb":
            self.game.spawn_arc_climb(
                count=int(params.get("count", 5)),
                center=float(params.get("center", SCREEN_HEIGHT / 2)),
                radius=float(params.get("radius", 140)),
                speed=float(params.get("speed", 140)),
            )
        elif action == "turret_line":
            self.game.spawn_turret_line(
                count=int(params.get("count", 3)),
                y=float(params.get("y", SCREEN_HEIGHT - 160)),
                spacing=float(params.get("spacing", 220)),
                speed=float(params.get("speed", 90)),
            )
        elif action == "charger_swarm":
            self.game.spawn_charger_swarm(
                count=int(params.get("count", 4)),
                top=float(params.get("top", 140)),
                gap=float(params.get("gap", 90)),
                speed=float(params.get("speed", 210)),
            )
        elif action == "meteor_field":
            self.game.spawn_meteor_field(
                count=int(params.get("count", 6)),
                speed=float(params.get("speed", 160)),
            )
        elif action == "drift_column":
            self.game.spawn_drift_column(
                count=int(params.get("count", 4)),
                start=float(params.get("start", 120)),
                gap=float(params.get("gap", 80)),
                speed=float(params.get("speed", 130)),
            )
        elif action == "boss":
            self.game.spawn_boss(
                health=int(params.get("health", 36)),
                speed=float(params.get("speed", 120)),
            )

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
        duration = 8.0
        samples = int(duration * sample_rate)
        buffer = array.array("h")
        progression = [196, 247, 330, 392, 262, 330, 392, 523]
        beat = int(sample_rate * 0.375)
        for i in range(samples):
            step = (i // beat) % len(progression)
            freq = progression[step]
            t = i / sample_rate
            envelope = 0.5 + 0.5 * math.sin(math.pi * ((i % beat) / beat))
            pad = math.sin(2 * math.pi * (freq / 2) * t) * 0.25
            arp = math.sin(2 * math.pi * freq * t) * 0.35
            bass = math.sin(2 * math.pi * (freq / 4) * t) * 0.18
            sample = (pad + arp + bass) * envelope
            buffer.append(int(max(-1.0, min(1.0, sample)) * 32767))
        return pygame.mixer.Sound(buffer=buffer)

    # Asset management --------------------------------------------------------------
    def _load_assets(self) -> None:
        if not self.enabled:
            return
        self.sounds["laser"] = self._generate_tone((720.0, 880.0), 0.08, 0.6)
        self.sounds["laser_dual"] = self._generate_tone((880.0, 990.0, 1200.0), 0.08, 0.6)
        self.sounds["hit"] = self._generate_tone((180.0, 320.0), 0.09, 0.5)
        self.sounds["explosion"] = self._generate_noise(0.18, 0.35)
        self.sounds["power"] = self._generate_tone((440.0, 660.0, 880.0), 0.25, 0.5)
        self.sounds["boss"] = self._generate_tone((120.0, 200.0, 280.0, 360.0), 0.6, 0.45)
        self.sounds["shield"] = self._generate_tone((240.0, 320.0, 420.0), 0.18, 0.5)
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
        pygame.display.set_caption("Space Avaders 2084")
        self.window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        self.window_size = self.window.get_size()
        self.render_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 26)
        self.small_font = pygame.font.SysFont("consolas", 18)
        self.big_font = pygame.font.SysFont("consolas", 56)

        self.audio = AudioManager()

        self.time_accumulator = 0.0
        self.glow_cache: Dict[Tuple[int, int], pygame.Surface] = {}

        self.background_surface = self._create_background_surface()
        self.parallax_layers = self._create_parallax_layers()
        self.stars: List[Star] = []
        self._setup_stars()

        self.player_surface = self._create_player_surface()
        self.player_rect = pygame.Rect(0, 0, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.player_pos = pygame.Vector2(SCREEN_WIDTH * 0.2, SCREEN_HEIGHT / 2)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        self.player_velocity = pygame.Vector2()
        self.player_fire_timer = 0.0
        self.player_invulnerable = 0.0
        self.player_thruster_timer = 0.0
        self.player_bank = 0.0
        self.player_target_bank = 0.0

        self.rapid_fire_timer = 0.0
        self.barrier_charges = 0

        self.player_bullets: List[Bullet] = []
        self.enemy_bullets: List[Bullet] = []
        self.enemies: List[Enemy] = []
        self.powerups: List[PowerUp] = []
        self.particles: List[Particle] = []
        self.floating_texts: List[FloatingText] = []

        self.score = 0
        self.combo_count = 0
        self.combo_timer = 0.0
        self.distance = 0.0
        self.lives = PLAYER_LIVES
        self.level = 1

        self.stage_director = StageDirector(self)
        self.stage_name = self.stage_director.theme_name
        self.stage_tagline = self.stage_director.tagline

        self.banner_text = ""
        self.banner_timer = 0.0

        self.state = "playing"
        self.fullscreen = False

        self.reset()

    # -- Setup ---------------------------------------------------------------------

    def reset(self) -> None:
        self.player_pos = pygame.Vector2(SCREEN_WIDTH * 0.2, SCREEN_HEIGHT / 2)
        self.player_velocity = pygame.Vector2()
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        self.player_fire_timer = 0.0
        self.player_invulnerable = 1.0
        self.player_thruster_timer = 0.0
        self.player_bank = 0.0
        self.player_target_bank = 0.0

        self.rapid_fire_timer = 0.0
        self.barrier_charges = 0

        self.player_bullets.clear()
        self.enemy_bullets.clear()
        self.enemies.clear()
        self.powerups.clear()
        self.particles.clear()
        self.floating_texts.clear()

        self.combo_count = 0
        self.combo_timer = 0.0

        self.distance = 0.0
        self.banner_text = ""
        self.banner_timer = 0.0

        self.stage_director = StageDirector(self)
        self.stage_name = self.stage_director.theme_name
        self.stage_tagline = self.stage_director.tagline

        self.state = "playing"

    def _create_background_surface(self) -> pygame.Surface:
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            color = lerp_color(BACKGROUND_GRADIENT_TOP, BACKGROUND_GRADIENT_BOTTOM, t)
            pygame.draw.line(surface, color, (0, y), (SCREEN_WIDTH, y))
        return surface.convert()

    def _create_parallax_layers(self) -> List[Dict[str, object]]:
        layers: List[Dict[str, object]] = []
        for index, color in enumerate(PARALLAX_COLORS):
            surface = pygame.Surface((SCREEN_WIDTH * 2, SCREEN_HEIGHT), pygame.SRCALPHA)
            rng = random.Random(index * 1337 + 42)
            for _ in range(14 + index * 6):
                base_y = rng.uniform(50, SCREEN_HEIGHT - 40)
                width = rng.uniform(80, 220)
                height = rng.uniform(40, 140)
                x = rng.uniform(0, SCREEN_WIDTH * 2)
                rect = pygame.Rect(int(x), int(base_y), int(width), int(height))
                pygame.draw.ellipse(surface, color, rect)
            layers.append({"surface": surface, "offset": 0.0, "speed": SCROLL_SPEED * (0.2 + index * 0.25)})
        return layers

    def _setup_stars(self) -> None:
        self.stars = []
        for _ in range(STAR_COUNT):
            pos = pygame.Vector2(random.uniform(0, SCREEN_WIDTH), random.uniform(0, SCREEN_HEIGHT))
            speed = random.uniform(40, 160)
            color = pygame.Color(*random.choice(STAR_COLORS))
            radius = random.uniform(1.0, 2.4)
            twinkle = random.uniform(0.8, 2.6)
            phase = random.uniform(0, math.tau)
            self.stars.append(Star(pos=pos, speed=speed, color=color, radius=radius, twinkle_speed=twinkle, phase=phase))

    def _create_player_surface(self) -> pygame.Surface:
        surface = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)
        body_color_top = lighten(PLAYER_COLOR, 0.3)
        body_color_bottom = darken(PLAYER_COLOR, 0.4)
        for y in range(PLAYER_HEIGHT):
            t = y / max(1, PLAYER_HEIGHT - 1)
            color = lerp_color(body_color_top, body_color_bottom, t)
            pygame.draw.line(surface, color, (10, y), (PLAYER_WIDTH - 10, y))
        pygame.draw.polygon(
            surface,
            lighten(PLAYER_COLOR, 0.5),
            [
                (PLAYER_WIDTH // 2, 0),
                (PLAYER_WIDTH - 8, PLAYER_HEIGHT // 2),
                (PLAYER_WIDTH // 2, PLAYER_HEIGHT - 6),
                (8, PLAYER_HEIGHT // 2),
            ],
        )
        canopy_rect = pygame.Rect(0, 0, PLAYER_WIDTH // 2, PLAYER_HEIGHT // 2)
        canopy_rect.center = (PLAYER_WIDTH // 2, PLAYER_HEIGHT // 2)
        pygame.draw.ellipse(surface, (255, 255, 255, 140), canopy_rect)
        return surface.convert_alpha()

    def _enemy_surface(self, variant: str, base_color: Tuple[int, int, int]) -> pygame.Surface:
        if variant == "wing":
            width, height = 64, 36
        elif variant == "orb":
            width, height = 56, 56
        elif variant == "turret":
            width, height = 60, 48
        elif variant == "meteor":
            width, height = 44, 44
        elif variant == "boss":
            width, height = 200, 120
        else:
            width, height = 58, 38

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        highlight = lighten(base_color, 0.3)
        shadow = darken(base_color, 0.5)

        if variant == "wing":
            pygame.draw.polygon(
                surface,
                base_color,
                [
                    (4, height // 2),
                    (width // 2 - 4, 6),
                    (width - 6, height // 2),
                    (width // 2 - 4, height - 6),
                ],
            )
            pygame.draw.polygon(
                surface,
                highlight,
                [
                    (width // 2 - 4, 8),
                    (width - 10, height // 2),
                    (width // 2 - 4, height - 8),
                ],
            )
            pygame.draw.rect(surface, shadow, (width // 2 - 10, 6, 12, height - 12), border_radius=6)
        elif variant == "orb":
            pygame.draw.ellipse(surface, base_color, (6, 6, width - 12, height - 12))
            pygame.draw.ellipse(surface, highlight, (width // 3, height // 3, width // 3, height // 3))
            pygame.draw.ellipse(surface, shadow, (10, height // 2, width - 20, height // 3))
        elif variant == "turret":
            pygame.draw.rect(surface, shadow, (6, height - 14, width - 12, 12), border_radius=4)
            pygame.draw.rect(surface, base_color, (10, 6, width - 20, height - 20), border_radius=8)
            pygame.draw.rect(surface, highlight, (width // 2 - 6, 0, 12, 20), border_radius=4)
        elif variant == "meteor":
            pygame.draw.circle(surface, base_color, (width // 2, height // 2), width // 2 - 2)
            for i in range(6):
                angle = math.tau * i / 6
                offset = pygame.Vector2(math.cos(angle), math.sin(angle)) * (width // 3)
                pygame.draw.circle(surface, shadow, (int(width // 2 + offset.x), int(height // 2 + offset.y)), 5)
        elif variant == "boss":
            body_rect = pygame.Rect(0, 0, width, height)
            pygame.draw.rect(surface, base_color, body_rect, border_radius=24)
            inner = body_rect.inflate(-60, -40)
            pygame.draw.rect(surface, darken(base_color, 0.3), inner, border_radius=18)
            core = pygame.Rect(0, 0, 48, 48)
            core.center = (width // 2, height // 2)
            pygame.draw.ellipse(surface, lighten(base_color, 0.45), core)
            pygame.draw.ellipse(surface, (20, 30, 60, 200), core.inflate(-20, -20))
            wing = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.draw.polygon(
                wing,
                highlight,
                [
                    (20, height // 2),
                    (width // 2, 6),
                    (width - 20, height // 2),
                    (width // 2, height - 6),
                ],
            )
            surface.blit(wing, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        else:
            pygame.draw.rect(surface, base_color, (8, 8, width - 16, height - 16), border_radius=12)
            pygame.draw.rect(surface, highlight, (width // 4, 10, width // 2, height // 3), border_radius=8)

        return surface.convert_alpha()

    def _spawn_enemy(self, variant: str, position: Tuple[float, float], **kwargs: float) -> Enemy:
        color = ENEMY_COLOR_CYCLE[len(self.enemies) % len(ENEMY_COLOR_CYCLE)]
        surface = self._enemy_surface(variant, color)
        rect = surface.get_rect()
        rect.center = (int(position[0]), int(position[1]))
        enemy = Enemy(
            pos=pygame.Vector2(position),
            rect=rect,
            surface=surface,
            behavior=str(kwargs.get("behavior", variant)),
            base_y=position[1],
            amplitude=float(kwargs.get("amplitude", 60)),
            frequency=float(kwargs.get("frequency", 1.4)),
            speed=float(kwargs.get("speed", 150)),
            direction=float(kwargs.get("direction", -1)),
            health=int(kwargs.get("health", 3)),
            max_health=int(kwargs.get("health", 3)),
            score=int(kwargs.get("score", 120)),
            fire_rate=float(kwargs.get("fire_rate", 0.0)),
            fire_timer=float(kwargs.get("fire_timer", random.uniform(0.2, 1.2))),
            bullet_speed=float(kwargs.get("bullet_speed", ENEMY_BULLET_SPEED)),
        )
        enemy.data.update({k: v for k, v in kwargs.items() if isinstance(v, (int, float))})
        self.enemies.append(enemy)
        return enemy

    def spawn_sine_wave(self, count: int, center: float, amplitude: float, speed: float, frequency: float) -> None:
        spacing = 48
        for i in range(count):
            y = center + (i - count // 2) * spacing * 0.4
            x = SCREEN_WIDTH + 120 + i * 24
            enemy = self._spawn_enemy(
                "wing",
                (x, y),
                behavior="sine",
                amplitude=amplitude,
                speed=speed,
                frequency=frequency,
                score=140,
                health=3,
                fire_rate=2.4,
            )
            enemy.fire_timer = random.uniform(0.8, 1.6)

    def spawn_arc_climb(self, count: int, center: float, radius: float, speed: float) -> None:
        for i in range(count):
            angle = math.tau * (i / count)
            x = SCREEN_WIDTH + 160 + i * 40
            y = center + math.sin(angle) * radius
            enemy = self._spawn_enemy(
                "orb",
                (x, y),
                behavior="arc",
                amplitude=radius,
                speed=speed,
                frequency=1.4,
                score=180,
                health=4,
                fire_rate=2.0,
            )
            enemy.data["angle"] = angle
            enemy.fire_timer = random.uniform(0.6, 1.2)

    def spawn_turret_line(self, count: int, y: float, spacing: float, speed: float) -> None:
        spacing = max(120, spacing)
        for i in range(count):
            x = SCREEN_WIDTH + 220 + i * spacing
            enemy = self._spawn_enemy(
                "turret",
                (x, y + random.uniform(-20, 20)),
                behavior="turret",
                amplitude=14,
                speed=speed,
                frequency=1.8,
                score=160,
                health=5,
                fire_rate=1.6,
                bullet_speed=ENEMY_BULLET_SPEED + 60,
            )
            enemy.fire_timer = random.uniform(0.4, 1.0)

    def spawn_charger_swarm(self, count: int, top: float, gap: float, speed: float) -> None:
        for i in range(count):
            y = top + i * gap
            enemy = self._spawn_enemy(
                "wing",
                (SCREEN_WIDTH + 200 + i * 40, y),
                behavior="charger",
                amplitude=50,
                speed=speed,
                frequency=2.0,
                score=200,
                health=4,
                fire_rate=0.0,
            )
            enemy.data["delay"] = 0.6 + i * 0.25
            enemy.data["target"] = pygame.Vector2(self.player_rect.center)

    def spawn_meteor_field(self, count: int, speed: float) -> None:
        for i in range(count):
            y = random.uniform(60, SCREEN_HEIGHT - 80)
            rotation = random.uniform(0, 360)
            enemy = self._spawn_enemy(
                "meteor",
                (SCREEN_WIDTH + 120 + i * 50, y),
                behavior="meteor",
                amplitude=0,
                speed=speed,
                frequency=random.uniform(-1.4, 1.4),
                score=80,
                health=2,
                fire_rate=0.0,
            )
            enemy.data["rotation"] = rotation

    def spawn_drift_column(self, count: int, start: float, gap: float, speed: float) -> None:
        for i in range(count):
            y = start + i * gap
            enemy = self._spawn_enemy(
                "orb",
                (SCREEN_WIDTH + 160 + i * 30, y),
                behavior="sine",
                amplitude=gap * 0.6,
                speed=speed,
                frequency=1.2 + i * 0.1,
                score=150,
                health=4,
                fire_rate=1.8,
            )
            enemy.fire_timer = random.uniform(0.5, 1.5)

    def spawn_boss(self, health: int, speed: float) -> None:
        if any(enemy.behavior == "boss" for enemy in self.enemies):
            return
        color = (255, 120, 190)
        surface = self._enemy_surface("boss", color)
        rect = surface.get_rect()
        rect.center = (SCREEN_WIDTH + rect.width // 2, SCREEN_HEIGHT // 2)
        boss = Enemy(
            pos=pygame.Vector2(rect.center),
            rect=rect,
            surface=surface,
            behavior="boss",
            base_y=SCREEN_HEIGHT // 2,
            amplitude=120,
            frequency=1.2,
            speed=speed,
            direction=-1,
            health=health,
            max_health=health,
            score=2000,
            fire_rate=1.2,
            fire_timer=1.2,
            bullet_speed=ENEMY_BULLET_SPEED + 120,
        )
        boss.data["anchor_x"] = SCREEN_WIDTH - 260
        self.enemies.append(boss)
        self.audio.play("boss", 0.8)
        self.push_banner("Boss fight!", hold=4.0)

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
                    self.lives = PLAYER_LIVES
                    self.score = 0
                    self.level = 1
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
        self.distance += SCROLL_SPEED * dt

        for layer in self.parallax_layers:
            offset = layer["offset"] + layer["speed"] * dt
            surface = layer["surface"]
            width = surface.get_width() // 2
            offset %= width
            layer["offset"] = offset

        for star in self.stars:
            star.update(dt)

        if self.banner_timer > 0:
            self.banner_timer = max(0.0, self.banner_timer - dt)

        if self.state != "playing":
            self.update_particles(dt)
            self.update_floating_texts(dt)
            return

        self.stage_director.update(dt)

        self.update_player(dt)
        self.update_player_bullets(dt)
        self.update_enemies(dt)
        self.update_enemy_bullets(dt)
        self.update_powerups(dt)
        self.update_particles(dt)
        self.update_floating_texts(dt)
        self.update_combo(dt)

        if self.stage_director.completed and not self.enemies and not self.enemy_bullets:
            self.advance_stage()

    def update_player(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            direction.x -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            direction.x += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            direction.y -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            direction.y += 1
        if direction.length_squared() > 0:
            direction = direction.normalize()
        self.player_velocity.x = direction.x * PLAYER_SPEED_X
        self.player_velocity.y = direction.y * PLAYER_SPEED_Y

        self.player_pos += self.player_velocity * dt
        margin_x = 40
        margin_y = 40
        self.player_pos.x = max(margin_x, min(SCREEN_WIDTH - margin_x, self.player_pos.x))
        self.player_pos.y = max(margin_y, min(SCREEN_HEIGHT - margin_y, self.player_pos.y))
        previous_center = pygame.Vector2(self.player_rect.center)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))

        delta = self.player_rect.centerx - previous_center.x
        self.player_target_bank = -delta * 0.3
        self.player_bank = lerp(self.player_bank, self.player_target_bank, min(1.0, dt * 6))

        self.player_thruster_timer += dt
        if self.player_thruster_timer >= PLAYER_THRUSTER_INTERVAL:
            self.player_thruster_timer = 0.0
            self.spawn_thruster_particles()

        if self.player_invulnerable > 0:
            self.player_invulnerable -= dt

        cooldown = PLAYER_RAPID_COOLDOWN if self.rapid_fire_timer > 0 else PLAYER_COOLDOWN
        if self.player_fire_timer > 0:
            self.player_fire_timer -= dt
        firing = keys[pygame.K_SPACE] or keys[pygame.K_z] or keys[pygame.K_j]
        if firing and self.player_fire_timer <= 0:
            self.fire_player_bullet()
            self.player_fire_timer = cooldown

        if self.rapid_fire_timer > 0:
            self.rapid_fire_timer = max(0.0, self.rapid_fire_timer - dt)
            if self.rapid_fire_timer == 0:
                self.push_banner("Rapid fire expired", hold=2.4)

    def fire_player_bullet(self) -> None:
        muzzle_left = pygame.Vector2(self.player_rect.centerx + 18, self.player_rect.centery - 8)
        muzzle_right = pygame.Vector2(self.player_rect.centerx + 18, self.player_rect.centery + 8)
        if self.rapid_fire_timer > 0:
            positions = [muzzle_left, muzzle_right]
            sound = "laser_dual"
        else:
            positions = [pygame.Vector2(self.player_rect.centerx + 20, self.player_rect.centery)]
            sound = "laser"
        for pos in positions:
            bullet = Bullet(
                pos=pygame.Vector2(pos),
                velocity=pygame.Vector2(PLAYER_BULLET_SPEED, 0),
                damage=PLAYER_BULLET_DAMAGE,
                color=pygame.Color(*PLAYER_BULLET_COLOR),
                size=(18, 6),
                from_player=True,
                glow_radius=22,
            )
            self.player_bullets.append(bullet)
            self.spawn_muzzle_flash(pygame.Vector2(pos))
        self.audio.play(sound, 0.7 if sound == "laser" else 0.8)

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
                hit_enemy.health -= bullet.damage
                hit_enemy.hit_flash = 0.3
                self.spawn_hit_sparks(pygame.Vector2(bullet.pos))
                self.audio.play("hit", 0.5)
                if hit_enemy.health <= 0:
                    self.handle_enemy_destroyed(hit_enemy)
                self.player_bullets.remove(bullet)

    def update_enemies(self, dt: float) -> None:
        for enemy in self.enemies[:]:
            if enemy.behavior == "charger":
                enemy.data["target"] = pygame.Vector2(self.player_rect.center)
            if enemy.behavior == "boss":
                enemy.base_y = lerp(enemy.base_y, self.player_rect.centery, min(1.0, dt * 0.4))
            enemy.update(dt)
            if enemy.rect.right < -160 or enemy.rect.top > SCREEN_HEIGHT + 160:
                self.enemies.remove(enemy)
                continue
            if enemy.fire_rate > 0:
                enemy.fire_timer -= dt
                if enemy.fire_timer <= 0:
                    self.fire_enemy_bullet(enemy)
                    enemy.fire_timer = random.uniform(enemy.fire_rate * 0.7, enemy.fire_rate * 1.3)
            if enemy.rect.colliderect(self.player_rect) and self.player_invulnerable <= 0:
                self.player_hit()
                if enemy in self.enemies:
                    self.handle_enemy_destroyed(enemy, award_score=False)

    def fire_enemy_bullet(self, enemy: Enemy) -> None:
        if enemy.behavior == "turret" or enemy.behavior == "boss":
            direction = pygame.Vector2(self.player_rect.center) - enemy.pos
            if direction.length_squared() == 0:
                direction = pygame.Vector2(-1, 0)
            else:
                direction = direction.normalize()
        elif enemy.behavior == "arc":
            direction = pygame.Vector2(-1, math.sin(enemy.timer * 2))
            direction = direction.normalize()
        else:
            direction = pygame.Vector2(-1, 0)
        velocity = direction * enemy.bullet_speed
        bullet_color = enemy.bullet_color if enemy.behavior != "boss" else pygame.Color(*BOSS_BULLET_COLOR)
        size = (14, 6) if enemy.behavior != "boss" else (18, 8)
        bullet = Bullet(
            pos=pygame.Vector2(enemy.rect.centerx - enemy.rect.width // 2, enemy.rect.centery),
            velocity=velocity,
            damage=ENEMY_BULLET_DAMAGE,
            color=bullet_color,
            size=size,
            from_player=False,
            glow_radius=24 if enemy.behavior == "boss" else 18,
        )
        self.enemy_bullets.append(bullet)

        if enemy.behavior == "boss":
            perpendicular = pygame.Vector2(-direction.y, direction.x)
            for offset in (-0.4, 0.4):
                alt_velocity = (direction + perpendicular * offset).normalize() * (enemy.bullet_speed * 0.9)
                alt_bullet = Bullet(
                    pos=pygame.Vector2(enemy.rect.centerx - 40, enemy.rect.centery + offset * 80),
                    velocity=alt_velocity,
                    damage=ENEMY_BULLET_DAMAGE,
                    color=bullet_color,
                    size=(16, 6),
                    from_player=False,
                    glow_radius=24,
                )
                self.enemy_bullets.append(alt_bullet)

    def update_enemy_bullets(self, dt: float) -> None:
        for bullet in self.enemy_bullets[:]:
            bullet.update(dt)
            if bullet.rect.right < -80 or bullet.rect.top > SCREEN_HEIGHT + 80 or bullet.rect.bottom < -80:
                self.enemy_bullets.remove(bullet)
                continue
            if bullet.rect.colliderect(self.player_rect):
                if self.player_invulnerable > 0:
                    self.enemy_bullets.remove(bullet)
                    continue
                if self.barrier_charges > 0:
                    self.barrier_charges -= 1
                    self.spawn_shield_flash(pygame.Vector2(self.player_rect.center))
                    self.player_invulnerable = 0.6
                    self.enemy_bullets.remove(bullet)
                    self.audio.play("shield", 0.6)
                else:
                    self.enemy_bullets.remove(bullet)
                    self.player_hit()

    def update_powerups(self, dt: float) -> None:
        for power in self.powerups[:]:
            if not power.update(dt):
                self.powerups.remove(power)
                continue
            if power.rect.colliderect(self.player_rect):
                self.apply_powerup(power)
                self.powerups.remove(power)

    def update_particles(self, dt: float) -> None:
        alive_particles = []
        for particle in self.particles:
            if particle.update(dt):
                alive_particles.append(particle)
        self.particles = alive_particles

    def update_floating_texts(self, dt: float) -> None:
        alive = []
        for text in self.floating_texts:
            if text.update(dt):
                alive.append(text)
        self.floating_texts = alive

    def update_combo(self, dt: float) -> None:
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo_count = 0
                self.combo_timer = 0.0

    def handle_enemy_destroyed(self, enemy: Enemy, award_score: bool = True) -> None:
        if enemy in self.enemies:
            self.enemies.remove(enemy)
        pos = pygame.Vector2(enemy.rect.center)
        sparks = 30 if enemy.behavior == "boss" else 18
        self.spawn_explosion(pos, sparks=sparks)
        if award_score:
            base_score = enemy.score
            combo_bonus = self.combo_count * 25
            self.score += base_score + combo_bonus
            self.combo_count = (self.combo_count + 1) if self.combo_timer > 0 else 1
            self.combo_timer = COMBO_TIMEOUT
            self.add_floating_text(f"+{base_score + combo_bonus}", pos, color=pygame.Color(*COMBO_COLOR))
        if enemy.behavior == "boss":
            for _ in range(4):
                self.spawn_powerup(pos + pygame.Vector2(random.uniform(-60, 60), random.uniform(-40, 40)))
            self.push_banner("Boss defeated!", hold=4.0)
        elif random.random() < 0.18:
            self.spawn_powerup(pos)

    def spawn_powerup(self, pos: pygame.Vector2) -> None:
        kind = random.choices(["rapid", "shield", "score"], weights=[0.4, 0.3, 0.3])[0]
        rect = pygame.Rect(0, 0, 32, 32)
        rect.center = (int(pos.x), int(pos.y))
        power = PowerUp(
            pos=pygame.Vector2(pos),
            rect=rect,
            kind=kind,
            velocity=pygame.Vector2(-80, 0),
            color=pygame.Color(*POWERUP_COLORS[kind]),
        )
        self.powerups.append(power)

    def apply_powerup(self, power: PowerUp) -> None:
        if power.kind == "rapid":
            self.rapid_fire_timer = 8.0
            self.push_banner("Rapid lasers online!", hold=3.0)
            self.audio.play("power", 0.8)
        elif power.kind == "shield":
            self.barrier_charges = min(3, self.barrier_charges + 1)
            self.push_banner("Barrier module acquired", hold=3.0)
            self.audio.play("shield", 0.7)
        elif power.kind == "score":
            bonus = 300 + self.level * 60
            self.score += bonus
            self.add_floating_text(f"BONUS +{bonus}", pygame.Vector2(power.rect.center), color=pygame.Color(255, 255, 200))
            self.audio.play("power", 0.7)

    def player_hit(self) -> None:
        if self.player_invulnerable > 0:
            return
        if self.barrier_charges > 0:
            self.barrier_charges -= 1
            self.spawn_shield_flash(pygame.Vector2(self.player_rect.center))
            self.player_invulnerable = 0.8
            self.audio.play("shield", 0.7)
            return
        self.lives -= 1
        self.player_invulnerable = PLAYER_INVULNERABLE_TIME
        self.spawn_explosion(pygame.Vector2(self.player_rect.center), sparks=40)
        self.audio.play("explosion", 0.9)
        self.player_pos = pygame.Vector2(SCREEN_WIDTH * 0.18, SCREEN_HEIGHT / 2)
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))
        self.player_velocity = pygame.Vector2()
        if self.lives <= 0:
            self.state = "game_over"
            self.push_banner("Game Over", hold=5.0)

    def advance_stage(self) -> None:
        self.level += 1
        self.lives = min(6, self.lives + 1)
        self.audio.play("power", 0.8)
        self.push_banner(f"Stage {self.level - 1} clear!", hold=3.5)
        self.stage_director = StageDirector(self)
        self.stage_name = self.stage_director.theme_name
        self.stage_tagline = self.stage_director.tagline

    # -- Drawing --------------------------------------------------------------------

    def draw(self) -> None:
        self.render_surface.blit(self.background_surface, (0, 0))

        for layer in self.parallax_layers:
            surface = layer["surface"]
            offset = layer["offset"]
            width = surface.get_width() // 2
            x = -offset
            self.render_surface.blit(surface, (x, 0))
            self.render_surface.blit(surface, (x + width, 0))

        for star in self.stars:
            star.draw(self.render_surface, self.time_accumulator)

        for power in self.powerups:
            self.draw_powerup(power)

        for enemy in self.enemies:
            self.draw_enemy(enemy)

        for bullet in self.player_bullets + self.enemy_bullets:
            self.draw_bullet(bullet)

        self.draw_player()

        for particle in self.particles:
            particle.draw(self.render_surface)

        self.draw_floating_texts()
        self.draw_hud()

        if self.banner_timer > 0 and self.banner_text:
            self.draw_banner()

        scaled = pygame.transform.smoothscale(self.render_surface, self.window_size)
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def draw_player(self) -> None:
        blink = int(self.player_invulnerable * 10) % 2 == 0 or self.player_invulnerable <= 0 or self.state != "playing"
        if not blink:
            return
        center = self.player_rect.center
        self.draw_glow(self.render_surface, center, 60, PLAYER_GLOW_COLOR)
        tilt = max(-8, min(8, self.player_bank))
        rotated = pygame.transform.rotate(self.player_surface, tilt)
        rect = rotated.get_rect(center=center)
        self.render_surface.blit(rotated, rect)
        flame_height = 26 + int(8 * math.sin(self.time_accumulator * 18))
        flame = [
            (self.player_rect.left + 4, self.player_rect.centery - 10),
            (self.player_rect.left + 4, self.player_rect.centery + 10),
            (self.player_rect.left - flame_height, self.player_rect.centery),
        ]
        pygame.draw.polygon(self.render_surface, PLAYER_FLAME_COLOR, flame)
        if self.barrier_charges > 0:
            radius = self.player_rect.width
            shield_color = pygame.Color(120, 220, 255, 80)
            pygame.draw.circle(self.render_surface, shield_color, center, radius, width=2)

    def draw_enemy(self, enemy: Enemy) -> None:
        self.draw_glow(
            self.render_surface,
            enemy.rect.center,
            max(40, enemy.rect.width),
            enemy.surface.get_at((enemy.rect.width // 2, enemy.rect.height // 2)),
        )
        self.render_surface.blit(enemy.surface, enemy.rect)
        if enemy.hit_flash > 0:
            flash = pygame.Surface(enemy.rect.size, pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(180 * enemy.hit_flash)))
            self.render_surface.blit(flash, enemy.rect)
        if enemy.behavior != "meteor":
            bar_width = enemy.rect.width
            health_ratio = max(0.0, enemy.health / max(1, enemy.max_health))
            bar_rect = pygame.Rect(enemy.rect.left, enemy.rect.top - 8, bar_width, 4)
            pygame.draw.rect(self.render_surface, (20, 30, 50, 200), bar_rect)
            pygame.draw.rect(
                self.render_surface,
                (120, 255, 180, 220) if enemy.behavior != "boss" else (255, 160, 210, 220),
                (bar_rect.x, bar_rect.y, int(bar_rect.width * health_ratio), bar_rect.height),
            )

    def draw_powerup(self, power: PowerUp) -> None:
        glow_color = power.color.lerp(pygame.Color(255, 255, 255), 0.4)
        self.draw_glow(self.render_surface, power.rect.center, 40, glow_color)
        pygame.draw.circle(self.render_surface, power.color, power.rect.center, power.rect.width // 2)
        icon_color = pygame.Color(20, 30, 60)
        center = power.rect.center
        if power.kind == "rapid":
            pygame.draw.polygon(
                self.render_surface,
                icon_color,
                [
                    (center[0] - 6, center[1] - 10),
                    (center[0] + 8, center[1]),
                    (center[0] - 6, center[1] + 10),
                ],
                width=2,
            )
        elif power.kind == "shield":
            pygame.draw.circle(self.render_surface, icon_color, center, 6, width=2)
        elif power.kind == "score":
            pygame.draw.line(self.render_surface, icon_color, (center[0] - 6, center[1]), (center[0] + 6, center[1]), width=2)
            pygame.draw.line(self.render_surface, icon_color, (center[0], center[1] - 6), (center[0], center[1] + 6), width=2)

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
        level_text = self.font.render(f"STAGE {self.level}", True, HUD_COLOR)
        lives_text = self.font.render(f"LIVES {self.lives}", True, HUD_COLOR)
        self.render_surface.blit(score_text, (22, 20))
        self.render_surface.blit(level_text, (SCREEN_WIDTH // 2 - level_text.get_width() // 2, 20))
        self.render_surface.blit(lives_text, (SCREEN_WIDTH - lives_text.get_width() - 24, 20))

        if self.combo_count > 1 and self.combo_timer > 0:
            combo_text = self.small_font.render(f"COMBO ×{self.combo_count}", True, COMBO_COLOR)
            self.render_surface.blit(combo_text, (22, 52))

        if self.rapid_fire_timer > 0:
            rapid_text = self.small_font.render(f"Rapid {self.rapid_fire_timer:0.1f}s", True, HUD_COLOR)
            self.render_surface.blit(rapid_text, (22, 80))
        if self.barrier_charges > 0:
            shield_text = self.small_font.render(f"Barrier {self.barrier_charges}", True, HUD_COLOR)
            self.render_surface.blit(shield_text, (22, 108))

        if self.audio.enabled:
            volume = int(self.audio.master_volume * 100)
            label = "MUTED" if self.audio.muted or volume == 0 else f"VOL {volume}%"
            volume_text = self.small_font.render(f"{label} (M to toggle)", True, HUD_COLOR)
        else:
            volume_text = self.small_font.render("Audio unavailable", True, HUD_COLOR)
        self.render_surface.blit(volume_text, (22, SCREEN_HEIGHT - 40))

        if self.stage_director.total_duration > 0:
            progress = min(1.0, self.stage_director.elapsed / self.stage_director.total_duration)
            bar_width = 220
            bar_rect = pygame.Rect(SCREEN_WIDTH - bar_width - 30, SCREEN_HEIGHT - 40, bar_width, 10)
            pygame.draw.rect(self.render_surface, (20, 30, 60, 200), bar_rect, border_radius=4)
            pygame.draw.rect(
                self.render_surface,
                (120, 200, 255, 220),
                (bar_rect.x + 2, bar_rect.y + 2, int((bar_rect.width - 4) * progress), bar_rect.height - 4),
                border_radius=4,
            )
            stage_text = self.small_font.render(self.stage_name, True, HUD_COLOR)
            self.render_surface.blit(stage_text, (SCREEN_WIDTH - stage_text.get_width() - 28, SCREEN_HEIGHT - 70))
            if self.stage_tagline:
                tagline_text = self.small_font.render(self.stage_tagline, True, HUD_COLOR)
                self.render_surface.blit(tagline_text, (SCREEN_WIDTH - tagline_text.get_width() - 28, SCREEN_HEIGHT - 90))

    def draw_banner(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.render_surface.blit(overlay, (0, 0))
        title = self.big_font.render(self.banner_text, True, BANNER_COLOR)
        self.render_surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 3))

    def draw_floating_texts(self) -> None:
        for floating in self.floating_texts:
            text = self.small_font.render(floating.text, True, floating.color)
            pos = (int(floating.pos.x), int(floating.pos.y))
            self.render_surface.blit(text, pos)

    def add_floating_text(self, text: str, pos: pygame.Vector2, color: pygame.Color) -> None:
        floating = FloatingText(text=text, pos=pygame.Vector2(pos), velocity=pygame.Vector2(-40, -10), lifetime=1.6, color=color)
        self.floating_texts.append(floating)

    def spawn_thruster_particles(self) -> None:
        origin = pygame.Vector2(self.player_rect.left - 10, self.player_rect.centery)
        for _ in range(3):
            velocity = pygame.Vector2(random.uniform(-140, -60), random.uniform(-40, 40))
            particle = Particle(
                pos=pygame.Vector2(origin.x, origin.y + random.uniform(-8, 8)),
                velocity=velocity,
                lifetime=random.uniform(0.4, 0.7),
                color=pygame.Color(255, random.randint(180, 220), random.randint(120, 180), 200),
                radius=random.uniform(2.5, 3.4),
                fade=1.6,
            )
            self.particles.append(particle)

    def spawn_muzzle_flash(self, position: pygame.Vector2) -> None:
        for _ in range(8):
            angle = random.uniform(-0.3, 0.3)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(120, 200)
            particle = Particle(
                pos=pygame.Vector2(position),
                velocity=velocity,
                lifetime=0.25,
                color=pygame.Color(255, 230, 160, 220),
                radius=2.0,
                fade=1.5,
            )
            self.particles.append(particle)

    def spawn_hit_sparks(self, position: pygame.Vector2) -> None:
        for _ in range(12):
            angle = random.uniform(0, math.tau)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(80, 180)
            particle = Particle(
                pos=pygame.Vector2(position),
                velocity=velocity,
                lifetime=random.uniform(0.25, 0.45),
                color=pygame.Color(*random.choice(SPARK_COLORS), 220),
                radius=random.uniform(1.8, 2.8),
                fade=1.8,
            )
            self.particles.append(particle)

    def spawn_explosion(self, position: pygame.Vector2, sparks: int = 24) -> None:
        for _ in range(sparks):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(100, 260)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
            particle = Particle(
                pos=pygame.Vector2(position),
                velocity=velocity,
                lifetime=random.uniform(0.5, 0.8),
                color=pygame.Color(*random.choice(SPARK_COLORS), 200),
                radius=random.uniform(2.5, 4.0),
                fade=1.4,
            )
            particle.gravity = 10
            self.particles.append(particle)

    def spawn_shield_flash(self, position: pygame.Vector2) -> None:
        for _ in range(18):
            angle = random.uniform(0, math.tau)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(100, 180)
            particle = Particle(
                pos=pygame.Vector2(position),
                velocity=velocity,
                lifetime=0.4,
                color=pygame.Color(120, 200, 255, 200),
                radius=2.2,
                fade=1.3,
            )
            self.particles.append(particle)

    def push_banner(self, text: str, hold: float = 3.0) -> None:
        self.banner_text = text
        self.banner_timer = hold


# --- Entrypoint --------------------------------------------------------------------


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
