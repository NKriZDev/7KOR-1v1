"""Wizard form assets/animation helpers."""

import os
import config
from animation import Animation
from player import SimpleAnimationManager
from file_animation import load_animation_from_folder


class Wizard:
    """Wizard form data/animations."""

    def __init__(self):
        self.animations = self._build_animations()
        self.attack_effect_anim = self._build_attack_effect()
        self.attack_effect_radius = self._compute_effect_radius(self.attack_effect_anim)
        self.death_anim = self._build_death_animation()

    def _build_animations(self):
        """Load wizard idle and attack animation frames."""
        base_path = os.path.join("Assets", "Player", "mage")
        animations = {}
        idle_anim = load_animation_from_folder(
            os.path.join(base_path, "wizard-idle"),
            "wizard-idle",
            5,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['idle'],
            loop=True,
        )
        attack_anim = load_animation_from_folder(
            os.path.join(base_path, "wizard-attack"),
            "wizard-attack",
            10,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['attack'],
            loop=False,
        )
        if idle_anim:
            animations["idle"] = idle_anim
        if attack_anim:
            animations["attack"] = attack_anim
        elif idle_anim:
            animations["attack"] = Animation(list(idle_anim.frames), frame_duration=config.ANIMATION_DURATIONS['attack'], loop=False)

        manager = SimpleAnimationManager(animations)
        if idle_anim:
            manager.set_animation("idle")
        return manager

    def _build_attack_effect(self):
        """Load fire-bomb effect used at the tip of the attack."""
        base_path = os.path.join("Assets", "Player", "mage")
        return load_animation_from_folder(
            os.path.join(base_path, "fire-bomb"),
            "fire-bomb",
            15,
            scale=config.PLAYER_SCALE,
            duration=config.ANIMATION_DURATIONS['attack'],
            loop=False,
        )

    def _build_death_animation(self):
        """Load wizard death animation (used for explosion visual)."""
        base_path = os.path.join("Assets", "Player", "mage")
        frame_count = 9
        total_duration = 3.0
        frame_duration = total_duration / frame_count
        return load_animation_from_folder(
            os.path.join(base_path, "wizard-death"),
            "wizard-death",
            frame_count,
            scale=config.PLAYER_SCALE * 2.0,
            duration=frame_duration,
            loop=False,
        )

    def _compute_effect_radius(self, anim):
        """Pick a conservative hitbox radius that fits inside the effect frames."""
        if not anim or not getattr(anim, "frames", None):
            return None
        frame = anim.frames[0]
        w, h = frame.get_size()
        return min(w, h) * 0.35

    def reset_to_idle(self):
        """Reset wizard animation to idle pose."""
        if not self.animations:
            return
        if "idle" in self.animations.animations:
            self.animations.set_animation("idle")
            self.animations.animations["idle"].reset()

    def clone_attack_effect(self):
        """Return a fresh instance of the fire-bomb animation."""
        if not self.attack_effect_anim:
            return None
        anim = Animation(
            list(self.attack_effect_anim.frames),
            frame_duration=self.attack_effect_anim.frame_duration,
            loop=self.attack_effect_anim.loop,
        )
        anim.reset()
        return anim

    def clone_death_animation(self):
        """Return a fresh instance of the wizard death animation."""
        if not self.death_anim:
            return None
        anim = Animation(
            list(self.death_anim.frames),
            frame_duration=self.death_anim.frame_duration,
            loop=self.death_anim.loop,
        )
        anim.reset()
        return anim
