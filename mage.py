"""Mage character: ranged-leaning fighter without a shield."""

import os
import pygame
import config
from projectile import Projectile
from animation import Animation
from file_animation import load_animation_from_folder
from player import Player, SimpleAnimationManager


class Mage(Player):
    """Light armor caster using the shared player base."""

    def __init__(self, x, y, controls=None):
        stats = {
            "speed": 190,
            "max_health": 8,
            "attack_damage": 3,
            "attack_range": 70,
            "collision_radius": 18,
        }
        cfg = {
            "stats": stats,
            "enable_shield": False,
            "enable_dash": True,
            "enable_gesture": True,
            "build_animations": self._build_animations,
            "flip_on_left": False,  # Mage sprites face left by default; flip when facing right
        }
        super().__init__(x, y, controls=controls, name="Mage", ui_color=(90, 140, 255), character_config=cfg)
        # Slight directional hitbox nudge
        self.collision_directional_offset = 2
        self.last_shot_target = (x, y)
        # Slightly wider cone for spell swipe feel
        self.attack_base_half_width = self.attack_range * 0.55
        # Softer dash than the rogue
        self.dash_speed_multiplier = 3.0
        # Projectile tuning
        self.projectile_speed = 520
        self.projectile_lifetime = 2.0
        self.projectile_animation = load_animation_from_folder(
            os.path.join("Assets", "Player", "mage", "mage-shoot"),
            "mage-shoot",
            2,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['attack'],
            loop=True,
        )

    def _build_animations(self):
        """Load mage animations from mage asset folders."""
        base_path = "Assets/Player/mage"
        animations_dict = {}

        move_anim = load_animation_from_folder(
            os.path.join(base_path, "mage-move"),
            "mage-move",
            4,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['walk'],
            loop=True,
        )
        if move_anim:
            animations_dict["walk"] = move_anim
            animations_dict["idle"] = move_anim
            animations_dict["attack"] = Animation(
                list(move_anim.frames),
                frame_duration=config.ANIMATION_DURATIONS['attack'],
                loop=False,
            )

        # Use move frame for gesture/hurt placeholders
        if move_anim:
            frame = move_anim.frames[0]
            gesture_anim = Animation([frame], frame_duration=config.ANIMATION_DURATIONS['gesture'], loop=False)
            hurt_anim = Animation([frame], frame_duration=0.3, loop=False)
            animations_dict["gesture"] = gesture_anim
            animations_dict["hurt"] = hurt_anim

        manager = SimpleAnimationManager(animations_dict)
        if animations_dict:
            manager.set_animation("idle")
        return manager

    def attack_enemies(self, enemies):
        """Mage uses projectiles for damage; skip melee hitbox."""
        return

    def on_attack_started(self, dir_x, dir_y):
        """Fire a projectile in the aimed direction."""
        # Remember where we aimed for debug hitbox
        self.last_shot_target = (self.mouse_world_x, self.mouse_world_y)
        proj = Projectile(
            self.x,
            self.y,
            dir_x,
            dir_y,
            speed=self.projectile_speed,
            damage=self.attack_damage,
            owner=self,
            color=(120, 200, 255),
            radius=10,
            lifetime=self.projectile_lifetime,
            animation=self._clone_projectile_animation(),
        )
        return [proj]

    def _clone_projectile_animation(self):
        """Create a fresh animation instance for the projectile."""
        if not self.projectile_animation:
            return None
        anim = Animation(
            list(self.projectile_animation.frames),
            frame_duration=self.projectile_animation.frame_duration,
            loop=self.projectile_animation.loop,
        )
        anim.reset()
        return anim

    def get_collision_center(self):
        """Offset hitbox slightly toward facing direction (left/right)."""
        dx = 0
        if self.facing_direction == "right":
            dx = getattr(self, "collision_directional_offset", 0)
        elif self.facing_direction == "left":
            dx = -getattr(self, "collision_directional_offset", 0)
        return (
            self.x + dx,
            self.y + getattr(self, "collision_offset_y", 0),
        )

    def draw_attack_hitbox(self, screen, camera, screen_x, screen_y):
        """For mage, draw a small rectangle at the aimed point instead of triangle."""
        if not self.is_attacking:
            return
        target_x, target_y = self.last_shot_target
        tx, ty = camera.apply(target_x, target_y)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        size = self.projectile_speed * 0 + 12  # constant size rectangle
        rect = pygame.Rect(0, 0, size, size)
        rect.center = (int(tx), int(ty))
        pygame.draw.rect(overlay, (255, 200, 0, 80), rect)
        pygame.draw.rect(overlay, (255, 150, 0, 180), rect, 2)
        screen.blit(overlay, (0, 0))
