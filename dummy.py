"""Training dummy entity for practice targets."""

import pygame
from player import Player


class TrainingDummy(Player):
    """Simple 1000 HP dummy that never moves, shows HP + stack count."""

    def __init__(self, x, y):
        stats = {
            "speed": 0,
            "max_health": 1000,
            "attack_damage": 0,
            "attack_range": 0,
            "collision_radius": 28,
        }
        cfg = {
            "stats": stats,
            "enable_shield": False,
            "enable_dash": False,
            "enable_gesture": False,
        }
        super().__init__(x, y, controls=None, name="Dummy", ui_color=(180, 180, 180), character_config=cfg)
        self.stack_display = 0
        self.curse_count = 0
        # Keep a neutral pose for visuals
        if self.animations:
            self.animations.set_animation("idle")

    def update(self, dt, keys, mouse_clicked=False, mouse_world_pos=None, mouse_right_held=False, direct_input=None):
        """Dummies stay stationary; only health/visual timers update."""
        if self.health <= 0:
            self.is_dead = True
        self.velocity_x = 0
        self.velocity_y = 0
        self.is_moving = False
        # Maintain idle animation if available
        if self.animations:
            self.animations.set_animation("idle")
            self.animations.update(dt)
            frame = self.animations.get_current_frame()
            if frame:
                self.rect = frame.get_rect()
                self.rect.center = (self.x, self.y)
        return []

    def attack_enemies(self, enemies):
        """Dummies do not attack."""
        return

    def draw(self, screen, camera):
        sx, sy = camera.apply(self.x, self.y)
        pygame.draw.circle(screen, (120, 120, 120), (int(sx), int(sy)), self.collision_radius)
        pygame.draw.circle(screen, (200, 200, 200), (int(sx), int(sy)), self.collision_radius, 2)
        # Draw HP and stack count above the dummy
        font = pygame.font.Font(None, 22)
        hp_text = font.render(f"{int(self.health)}/{self.max_health}", True, (230, 230, 230))
        stack_val = getattr(self, "stack_display", 0)
        stack_text = font.render(f"Stacks: {stack_val}", True, (255, 200, 120))
        hp_rect = hp_text.get_rect(center=(sx, sy - self.collision_radius - 16))
        stack_rect = stack_text.get_rect(center=(sx, sy - self.collision_radius - 32))
        screen.blit(stack_text, stack_rect)
        screen.blit(hp_text, hp_rect)
