"""Dragon character using per-frame PNG animations."""

import os
import pygame
import config
from player import Player, SimpleAnimationManager
from animation import Animation
from file_animation import load_animation_from_folder


class Dragon(Player):
    """Heavy melee fighter with sprite-strip based animations."""

    def __init__(self, x, y, controls=None):
        stats = {
            "speed": 185,
            "max_health": 12,
            "attack_damage": 3,
            "attack_range": 65,
            "collision_radius": 32,
        }
        cfg = {
            "stats": stats,
            "enable_shield": False,
            "enable_dash": True,
            "enable_gesture": False,
            "build_animations": self._build_animations,
            # Dragon sprites face left by default; flip logic should mirror to face right.
            "flip_on_left": False,
        }
        super().__init__(x, y, controls=controls, name="Dragon", ui_color=(200, 80, 80), character_config=cfg)
        # Broader swipe to match the larger claws
        self.attack_base_half_width = self.attack_range * 0.5
        self.breath_anim = None

    def _build_animations(self):
        """Load dragon animations from standalone PNG frames (simple, like other characters)."""
        base_path = os.path.join("Assets", "Player", "Dragon")
        idle_walk_scale = config.PLAYER_SCALE * 0.8  # 20% smaller for idle/walk
        attack_scale = config.PLAYER_SCALE
        animations_dict = {}

        idle_walk_anim = load_animation_from_folder(
            os.path.join(base_path, "dragon-idle"),
            "dragon-idle",
            6,
            scale=idle_walk_scale,
            duration=config.ANIMATION_DURATIONS["idle"],
            loop=True,
        )
        body_attack_anim = load_animation_from_folder(
            os.path.join(base_path, "dragon-attack-breath"),
            "dragon-attack-breath",
            11,
            scale=attack_scale,
            duration=config.ANIMATION_DURATIONS["attack"],
            loop=False,
        )
        self.breath_anim = None

        if idle_walk_anim:
            idle_anim = Animation(
                list(idle_walk_anim.frames),
                frame_duration=config.ANIMATION_DURATIONS["idle"],
                loop=True,
            )
            walk_anim = Animation(
                list(idle_walk_anim.frames),
                frame_duration=config.ANIMATION_DURATIONS["walk"],
                loop=True,
            )
            animations_dict["idle"] = idle_anim
            animations_dict["walk"] = walk_anim

            base_frame = idle_anim.frames[0]
            animations_dict["gesture"] = Animation(
                [base_frame],
                frame_duration=config.ANIMATION_DURATIONS["gesture"],
                loop=False,
            )
            animations_dict["hurt"] = Animation([base_frame], frame_duration=0.3, loop=False)

        if body_attack_anim:
            animations_dict["attack"] = body_attack_anim

        if not animations_dict:
            return None

        manager = SimpleAnimationManager(animations_dict)
        manager.set_animation("idle" if "idle" in animations_dict else list(animations_dict.keys())[0])
        return manager

    def on_attack_started(self, dir_x, dir_y):
        """Hook for subclasses (reset effects if needed)."""
        return []

    def update(self, dt, keys, mouse_clicked=False, mouse_world_pos=None, mouse_right_held=False, direct_input=None):
        spawned = super().update(dt, keys, mouse_clicked, mouse_world_pos, mouse_right_held, direct_input)
        return spawned

    def draw(self, screen, camera):
        """Draw body via base draw (attack includes breath in the combined sprite)."""
        super().draw(screen, camera)
