"""Rogue warrior character (sword/shield/dash) built on top of base Player."""

import os
import pygame
import config
from player import Player, SimpleAnimationManager
from animation import Animation
from file_animation import load_animation_from_folder


class RogueWarrior(Player):
    """Melee-focused fighter with shield and dash."""

    def __init__(self, x, y, controls=None):
        stats = {
            "speed": config.PLAYER_SPEED,
            "max_health": config.PLAYER_MAX_HEALTH,
            "attack_damage": 2,
            "attack_range": 50,
            "collision_radius": 20,
        }
        cfg = {
            "stats": stats,
            "enable_shield": True,
            "enable_dash": True,
            "enable_gesture": True,
            "build_animations": self._build_animations,
        }
        super().__init__(x, y, controls=controls, name="Rogue Warrior", ui_color=(0, 200, 0), character_config=cfg)

    def _build_animations(self):
        """Load hero animations from disk."""
        base_path = "Assets/Player/rogue_warrior"
        animations_dict = {}

        idle_anim = load_animation_from_folder(
            os.path.join(base_path, "hero-idle"),
            "hero-idle",
            4,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['idle'],
            loop=True,
        )
        if idle_anim:
            animations_dict['idle'] = idle_anim

        walk_anim = load_animation_from_folder(
            os.path.join(base_path, "hero-run"),
            "hero-run",
            6,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['walk'],
            loop=True,
        )
        if walk_anim:
            animations_dict['walk'] = walk_anim

        attack_anim = load_animation_from_folder(
            os.path.join(base_path, "hero-attack"),
            "hero-attack",
            5,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['attack'],
            loop=False,
        )
        if attack_anim:
            animations_dict['attack'] = attack_anim

        jump_anim = load_animation_from_folder(
            os.path.join(base_path, "hero-jump"),
            "hero-jump",
            4,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['gesture'],
            loop=False,
        )
        if jump_anim:
            animations_dict['gesture'] = jump_anim

        shield_path = os.path.join(base_path, "hero-shield")
        if os.path.exists(shield_path):
            shield_file = os.path.join(shield_path, "hero-shield.png")
            if os.path.isfile(shield_file):
                try:
                    frame = pygame.image.load(shield_file).convert_alpha()
                    if config.PLAYER_SCALE != 1.0:
                        new_width = int(frame.get_width() * config.PLAYER_SCALE)
                        new_height = int(frame.get_height() * config.PLAYER_SCALE)
                        frame = pygame.transform.scale(frame, (new_width, new_height))
                    shield_anim = Animation([frame], frame_duration=0.1, loop=True)
                    animations_dict['shield'] = shield_anim
                except Exception as e:
                    print(f"Error loading shield animation: {e}")
            else:
                shield_anim = load_animation_from_folder(
                    shield_path,
                    "hero-shield",
                    1,
                    scale=config.PLAYER_SCALE,
                    duration=config.ANIMATION_DURATIONS.get('idle', 0.15),
                    loop=True,
                )
                if shield_anim:
                    animations_dict['shield'] = shield_anim

        hurt_path = os.path.join(base_path, "hero-hurt")
        if os.path.exists(hurt_path):
            hurt_file = os.path.join(hurt_path, "hero-hurt.png")
            if os.path.isfile(hurt_file):
                try:
                    frame = pygame.image.load(hurt_file).convert_alpha()
                    if config.PLAYER_SCALE != 1.0:
                        new_width = int(frame.get_width() * config.PLAYER_SCALE)
                        new_height = int(frame.get_height() * config.PLAYER_SCALE)
                        frame = pygame.transform.scale(frame, (new_width, new_height))
                    hurt_anim = Animation([frame], frame_duration=0.3, loop=False)
                    animations_dict['hurt'] = hurt_anim
                except Exception as e:
                    print(f"Error loading hurt animation: {e}")

        manager = SimpleAnimationManager(animations_dict)
        if animations_dict:
            manager.set_animation('idle')
        return manager
