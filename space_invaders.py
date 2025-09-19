#!/usr/bin/env python3
"""Space Avaders - a simple but punchy Space-Invaders inspired clone.

Run with ``python3 space_invaders.py`` after installing pygame::

    pip install pygame

The game uses only generated rectangles and particles for visuals, so no
additional assets are required. All logic lives in this one file to keep the
project easy to explore and tweak.
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from typing import List, Optional

import pygame


# --- Configuration -----------------------------------------------------------------

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
FPS = 60

PLAYER_SPEED = 320
PLAYER_WIDTH = 60
PLAYER_HEIGHT = 28
PLAYER_COOLDOWN = 0.35  # seconds between shots
PLAYER_LIVES = 3
PLAYER_INVULNERABLE_TIME = 1.5

BULLET_SPEED = 540
ALIEN_BULLET_SPEED = 240

ALIEN_ROWS_START = 4
ALIEN_COLUMNS = 10
ALIEN_ROW_GAP = 60
ALIEN_COL_GAP = 60

ALIEN_BASE_SPEED = 40
ALIEN_SPEED_PER_LEVEL = 12
ALIEN_SPEED_SCALE = 220  # Added to base speed as the wave thins out
ALIEN_DROP_DISTANCE = 28

ALIEN_FIRE_MIN_INTERVAL = 1.0
ALIEN_FIRE_MAX_INTERVAL = 2.6

UFO_SPAWN_MIN = 18
UFO_SPAWN_MAX = 32
UFO_SPEED = 200
UFO_SCORE = 150

STAR_COUNT = 80

BACKGROUND_COLOR = (10, 10, 25)
PLAYER_COLOR = (100, 220, 255)
PLAYER_BULLET_COLOR = (255, 255, 120)
ALIEN_COLORS = [
    (80, 255, 120),
    (120, 240, 80),
    (255, 180, 70),
    (255, 110, 110),
    (255, 70, 180),
]
ALIEN_BULLET_COLOR = (255, 120, 120)
UFO_COLOR = (255, 60, 60)
HUD_COLOR = (240, 240, 240)
PARTICLE_COLORS = [
    (255, 190, 120),
    (255, 140, 80),
    (255, 255, 200),
]
STAR_COLORS = [
    (180, 180, 255),
    (120, 120, 220),
    (90, 90, 170),
]


# --- Helper data structures ---------------------------------------------------------

@dataclass
class Particle:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    lifetime: float
    color: pygame.Color

    def update(self, dt: float) -> bool:
        """Update particle position; return True if still alive."""
        self.lifetime -= dt
        if self.lifetime <= 0:
            return False
        self.pos += self.velocity * dt
        return True

    def draw(self, surface: pygame.Surface) -> None:
        alpha = max(0, min(255, int(255 * (self.lifetime + 0.3))))
        radius = max(1, int(2 + 2 * self.lifetime))
        color = self.color.copy()
        color.a = alpha
        pygame.draw.circle(surface, color, (int(self.pos.x), int(self.pos.y)), radius)


@dataclass
class Star:
    x: float
    y: float
    speed: float
    color: pygame.Color

    def update(self, dt: float) -> None:
        self.y += self.speed * dt
        if self.y > SCREEN_HEIGHT:
            self.y = -5
            self.x = random.uniform(0, SCREEN_WIDTH)
            self.speed = random.uniform(20, 80)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(self.color, (int(self.x), int(self.y), 2, 2))


@dataclass
class Alien:
    rect: pygame.Rect
    row: int


# --- Game implementation ------------------------------------------------------------


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Space Avaders")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 24)
        self.big_font = pygame.font.SysFont("consolas", 56)

        self.stars: List[Star] = []
        self.particles: List[Particle] = []

        self.player_rect = pygame.Rect(0, 0, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.player_rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
        self.player_velocity = 0.0
        self.player_cooldown_timer = 0.0
        self.player_invulnerable = 0.0
        self.lives = PLAYER_LIVES

        self.player_bullets: List[pygame.Rect] = []
        self.alien_bullets: List[pygame.Rect] = []

        self.aliens: List[Alien] = []
        self.alien_rows = ALIEN_ROWS_START
        self.level = 1
        self.alien_direction = 1
        self.alien_dx_buffer = 0.0  # keeps sub-pixel swarm movement smooth
        self.alien_fire_timer = 0.0

        self.ufo_rect: Optional[pygame.Rect] = None
        self.ufo_direction = 1
        self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)

        self.score = 0
        self.state = "playing"

        self._setup_stars()
        self.reset()

    # -- Setup ---------------------------------------------------------------------

    def _setup_stars(self) -> None:
        self.stars.clear()
        for _ in range(STAR_COUNT):
            self.stars.append(
                Star(
                    x=random.uniform(0, SCREEN_WIDTH),
                    y=random.uniform(0, SCREEN_HEIGHT),
                    speed=random.uniform(20, 80),
                    color=random.choice(STAR_COLORS),
                )
            )

    def reset(self) -> None:
        """Reset the game back to an initial wave."""
        self.level = 1
        self.score = 0
        self.lives = PLAYER_LIVES
        self.player_rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
        self.player_velocity = 0.0
        self.player_cooldown_timer = 0.0
        self.player_bullets.clear()
        self.alien_bullets.clear()
        self.particles.clear()
        self.ufo_rect = None
        self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)
        self.player_invulnerable = 1.5
        self.state = "playing"
        self.spawn_wave()

    def spawn_wave(self) -> None:
        """Create a fresh wave of aliens for the current level."""
        rows = ALIEN_ROWS_START + min(self.level - 1, 3)
        self.alien_rows = rows
        cols = ALIEN_COLUMNS
        top_offset = 120
        left_offset = (SCREEN_WIDTH - (cols - 1) * ALIEN_COL_GAP) // 2

        self.aliens.clear()
        for row in range(rows):
            for col in range(cols):
                rect = pygame.Rect(0, 0, 40, 30)
                rect.x = left_offset + col * ALIEN_COL_GAP
                rect.y = top_offset + row * ALIEN_ROW_GAP
                self.aliens.append(Alien(rect=rect, row=row))

        self.total_aliens = len(self.aliens)
        self.alien_direction = 1
        self.alien_dx_buffer = 0.0
        self.alien_fire_timer = random.uniform(ALIEN_FIRE_MIN_INTERVAL, ALIEN_FIRE_MAX_INTERVAL)

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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if self.state == "game_over" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.reset()

    # -- Update loop ----------------------------------------------------------------

    def update(self, dt: float) -> None:
        for star in self.stars:
            star.update(dt)

        if self.state != "playing":
            return

        self.update_player(dt)
        self.update_player_bullets(dt)
        self.update_aliens(dt)
        self.update_alien_bullets(dt)
        self.update_ufo(dt)
        self.update_particles(dt)

    def update_player(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.player_velocity = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player_velocity -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player_velocity += PLAYER_SPEED
        self.player_rect.x += int(self.player_velocity * dt)
        self.player_rect.x = max(40, min(SCREEN_WIDTH - 40 - PLAYER_WIDTH, self.player_rect.x))

        # Shooting
        if self.player_cooldown_timer > 0:
            self.player_cooldown_timer -= dt
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP]) and self.player_cooldown_timer <= 0:
            bullet = pygame.Rect(0, 0, 6, 16)
            bullet.midbottom = self.player_rect.midtop
            self.player_bullets.append(bullet)
            self.player_cooldown_timer = PLAYER_COOLDOWN

        if self.player_invulnerable > 0:
            self.player_invulnerable -= dt

    def update_player_bullets(self, dt: float) -> None:
        for bullet in self.player_bullets[:]:
            bullet.y -= int(BULLET_SPEED * dt)
            if bullet.bottom < 0:
                self.player_bullets.remove(bullet)
                continue

            # Check collision with aliens
            hit: Optional[Alien] = None
            for alien in self.aliens:
                if bullet.colliderect(alien.rect):
                    hit = alien
                    break
            if hit:
                self.aliens.remove(hit)
                self.player_bullets.remove(bullet)
                score_gain = 10 + 5 * (self.alien_rows - hit.row)
                self.score += score_gain
                self.spawn_particles(pygame.Vector2(hit.rect.center), 18)
                break

            # Check collision with UFO
            if self.ufo_rect and bullet.colliderect(self.ufo_rect):
                self.score += UFO_SCORE
                self.spawn_particles(pygame.Vector2(self.ufo_rect.center), 32)
                self.ufo_rect = None
                if bullet in self.player_bullets:
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

        # Determine horizontal bounds of the swarm
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

        # Accumulate fractional movement so the swarm doesn't stutter at low speeds
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

        # Alien firing
        self.alien_fire_timer -= dt
        if self.alien_fire_timer <= 0:
            self.fire_alien_bullet()
            interval = random.uniform(ALIEN_FIRE_MIN_INTERVAL, ALIEN_FIRE_MAX_INTERVAL)
            interval = max(0.25, interval - (self.level - 1) * 0.1)
            self.alien_fire_timer = interval

    def current_alien_speed(self) -> float:
        if not self.aliens:
            return ALIEN_BASE_SPEED
        alive_ratio = len(self.aliens) / self.total_aliens
        base = ALIEN_BASE_SPEED + (self.level - 1) * ALIEN_SPEED_PER_LEVEL
        bonus = (1.0 - alive_ratio) * ALIEN_SPEED_SCALE
        return base + bonus

    def fire_alien_bullet(self) -> None:
        if not self.aliens:
            return
        columns = {}
        for alien in self.aliens:
            columns.setdefault(alien.rect.x, []).append(alien)
        shooter_column = random.choice(list(columns.values()))
        shooter = max(shooter_column, key=lambda a: a.rect.y)

        bullet = pygame.Rect(0, 0, 6, 16)
        bullet.midtop = shooter.rect.midbottom
        self.alien_bullets.append(bullet)

    def update_alien_bullets(self, dt: float) -> None:
        for bullet in self.alien_bullets[:]:
            bullet.y += int((ALIEN_BULLET_SPEED + self.level * 30) * dt)
            if bullet.top > SCREEN_HEIGHT:
                self.alien_bullets.remove(bullet)
                continue
            if bullet.colliderect(self.player_rect):
                if self.player_invulnerable <= 0:
                    self.player_hit()
                if bullet in self.alien_bullets:
                    self.alien_bullets.remove(bullet)

    def update_ufo(self, dt: float) -> None:
        if self.ufo_rect:
            self.ufo_rect.x += int(self.ufo_direction * UFO_SPEED * dt)
            if self.ufo_rect.right < 0 or self.ufo_rect.left > SCREEN_WIDTH:
                self.ufo_rect = None
                self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)
        else:
            self.ufo_timer -= dt
            if self.ufo_timer <= 0 and self.level > 1:
                direction = random.choice([-1, 1])
                if direction == 1:
                    rect = pygame.Rect(-80, 70, 70, 28)
                else:
                    rect = pygame.Rect(SCREEN_WIDTH + 10, 70, 70, 28)
                self.ufo_rect = rect
                self.ufo_direction = direction
                self.ufo_timer = random.uniform(UFO_SPAWN_MIN, UFO_SPAWN_MAX)

    def update_particles(self, dt: float) -> None:
        alive_particles = []
        for particle in self.particles:
            if particle.update(dt):
                alive_particles.append(particle)
        self.particles = alive_particles

    def spawn_particles(self, position: pygame.Vector2, count: int) -> None:
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(50, 260)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
            lifetime = random.uniform(0.2, 0.7)
            color = random.choice(PARTICLE_COLORS)
            self.particles.append(
                Particle(
                    pos=pygame.Vector2(position),
                    velocity=velocity,
                    lifetime=lifetime,
                    color=pygame.Color(*color),
                )
            )

    def player_hit(self) -> None:
        self.lives -= 1
        self.player_invulnerable = PLAYER_INVULNERABLE_TIME
        self.spawn_particles(pygame.Vector2(self.player_rect.center), 42)
        self.player_rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
        self.alien_bullets.clear()
        if self.lives <= 0:
            self.state = "game_over"

    # -- Drawing --------------------------------------------------------------------

    def draw(self) -> None:
        self.screen.fill(BACKGROUND_COLOR)

        for star in self.stars:
            star.draw(self.screen)

        if self.ufo_rect:
            pygame.draw.rect(self.screen, UFO_COLOR, self.ufo_rect, border_radius=6)
            pygame.draw.rect(
                self.screen,
                (255, 220, 220),
                (self.ufo_rect.x + 10, self.ufo_rect.y + 8, self.ufo_rect.width - 20, 8),
            )

        # Draw aliens
        for alien in self.aliens:
            color = ALIEN_COLORS[alien.row % len(ALIEN_COLORS)]
            pygame.draw.rect(self.screen, color, alien.rect, border_radius=8)
            eye_rect = pygame.Rect(
                alien.rect.x + 8, alien.rect.y + 8, alien.rect.width - 16, 6
            )
            pygame.draw.rect(self.screen, BACKGROUND_COLOR, eye_rect)

        # Draw player with blink while invulnerable
        if int(self.player_invulnerable * 10) % 2 == 0 or self.state != "playing":
            pygame.draw.rect(self.screen, PLAYER_COLOR, self.player_rect, border_radius=10)
            cannon = pygame.Rect(0, 0, 12, 12)
            cannon.midbottom = self.player_rect.midtop
            pygame.draw.rect(self.screen, PLAYER_COLOR, cannon)

        for bullet in self.player_bullets:
            pygame.draw.rect(self.screen, PLAYER_BULLET_COLOR, bullet, border_radius=4)
        for bullet in self.alien_bullets:
            pygame.draw.rect(self.screen, ALIEN_BULLET_COLOR, bullet, border_radius=4)

        for particle in self.particles:
            particle.draw(self.screen)

        self.draw_hud()

        if self.state == "game_over":
            self.draw_game_over()

        pygame.display.flip()

    def draw_hud(self) -> None:
        score_text = self.font.render(f"SCORE {self.score:06d}", True, HUD_COLOR)
        level_text = self.font.render(f"WAVE {self.level}", True, HUD_COLOR)
        lives_text = self.font.render(f"LIVES {self.lives}", True, HUD_COLOR)
        self.screen.blit(score_text, (20, 20))
        self.screen.blit(level_text, (SCREEN_WIDTH // 2 - level_text.get_width() // 2, 20))
        self.screen.blit(lives_text, (SCREEN_WIDTH - lives_text.get_width() - 20, 20))

    def draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        title = self.big_font.render("GAME OVER", True, HUD_COLOR)
        prompt = self.font.render("Press Enter to try again", True, HUD_COLOR)
        score = self.font.render(f"Final score: {self.score}", True, HUD_COLOR)

        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 120))
        self.screen.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
        self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, SCREEN_HEIGHT // 2 + 30))


# --- Entrypoint --------------------------------------------------------------------


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
