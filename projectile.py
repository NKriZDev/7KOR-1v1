"""Simple projectile for mage ranged attacks."""

import math
import pygame
import config


class Projectile:
    def __init__(self, x, y, dir_x, dir_y, speed, damage, owner, color=(120, 200, 255), radius=10, lifetime=2.0, animation=None):
        self.x = x
        self.y = y
        mag = math.hypot(dir_x, dir_y)
        if mag == 0:
            dir_x, dir_y = 0.0, 1.0
            mag = 1.0
        self.dir_x = dir_x / mag
        self.dir_y = dir_y / mag
        self.speed = speed
        self.damage = damage
        self.owner = owner
        self.color = color
        self.radius = radius
        self.lifetime = lifetime
        self.alive = True
        self.animation = animation

    def update(self, dt):
        if not self.alive:
            return
        self.x += self.dir_x * self.speed * dt
        self.y += self.dir_y * self.speed * dt
        self.lifetime -= dt
        if self.animation:
            self.animation.update(dt)
        if self.lifetime <= 0:
            self.alive = False

    def draw(self, screen, camera):
        if not self.alive:
            return
        sx, sy = camera.apply(self.x, self.y)
        if self.animation:
            frame = self.animation.get_current_frame()
            if frame:
                # Rotate sprite to face travel direction (asset is left->right by default)
                angle = math.degrees(math.atan2(-self.dir_y, self.dir_x))
                rotated = pygame.transform.rotate(frame, angle)
                rect = rotated.get_rect(center=(int(sx), int(sy)))
                screen.blit(rotated, rect)
            # Draw a simple hitbox overlay for mage projectiles (and any others) for clarity
            hit_color = (255, 0, 0, 80)
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(
                overlay,
                hit_color,
                pygame.Rect(int(sx - self.radius), int(sy - self.radius), self.radius * 2, self.radius * 2),
                1,
            )
            screen.blit(overlay, (0, 0))
            return
        pygame.draw.circle(screen, self.color, (int(sx), int(sy)), self.radius)
        hit_color = (255, 0, 0, 80)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(
            overlay,
            hit_color,
            pygame.Rect(int(sx - self.radius), int(sy - self.radius), self.radius * 2, self.radius * 2),
            1,
        )
        screen.blit(overlay, (0, 0))

    def check_collision(self, player):
        if not self.alive or player.is_dead:
            return False
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)
        # If using animation, approximate with radius from sprite size
        effective_radius = self.radius
        if self.animation:
            frame = self.animation.get_current_frame()
            if frame:
                effective_radius = max(frame.get_width(), frame.get_height()) * 0.25
        return dist < (effective_radius + player.collision_radius)
