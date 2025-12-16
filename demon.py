"""Demon character using per-frame PNG animations."""

import os
import math
import time
import pygame
import config
from player import Player, SimpleAnimationManager
from animation import Animation
from file_animation import load_animation_from_folder


class Demon(Player):
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
            # Demon sprites face left by default; flip logic should mirror to face right.
            "flip_on_left": False,
        }
        super().__init__(x, y, controls=controls, name="Demon", ui_color=(200, 80, 80), character_config=cfg)
        # Broader swipe to match the larger claws
        self.attack_base_half_width = self.attack_range * 0.5
        self.breath_anim = None
        self.collision_directional_offset = 2
        self._attack_hold_timer = 0.0
        self._attack_hold_looped = False
        self._attack_force_finish = False
        self.attack_hit_counts = {}
        self.attack_last_frame_hit = {}
        self.circle_immunity_active = False
        self.attack_last_effect_time = {}
        # Stack-based damage circle state
        self.stack_counts = {}           # Persistent stacks per enemy across circles
        self.circle_timers = {}          # Time spent inside the current circle per enemy
        self.circle_entry_hit = set()    # Enemies that already took the entry hit for this circle
        self._attack_tick_last_time = None

    def _build_animations(self):
        """Load demon animations from standalone PNG frames (simple, like other characters)."""
        base_path = os.path.join("Assets", "Player", "Demon")
        idle_walk_scale = config.PLAYER_SCALE * 0.8  # 20% smaller for idle/walk
        attack_scale = config.PLAYER_SCALE
        animations_dict = {}

        idle_walk_anim = load_animation_from_folder(
            os.path.join(base_path, "demon-idle"),
            "demon-idle",
            6,
            scale=idle_walk_scale,
            duration=config.ANIMATION_DURATIONS["idle"],
            loop=True,
        )
        body_attack_anim = load_animation_from_folder(
            os.path.join(base_path, "demon-attack-breath"),
            "demon-attack-breath",
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

    def get_collision_center(self):
        """Offset hitbox slightly toward facing direction; shift further when attacking."""
        dx = 0
        if self.facing_direction == "right":
            dx = getattr(self, "collision_directional_offset", 0)
        elif self.facing_direction == "left":
            dx = -getattr(self, "collision_directional_offset", 0)

        dy = getattr(self, "collision_offset_y", 0)

        # When attacking, shift the collision circle farther diagonally (right = west/south, left = east/north)
        if self.is_attacking:
            if self.facing_direction == "right":
                dx -= 40
                dy += 40
            elif self.facing_direction == "left":
                dx += 40
                dy += 40

        return self.x + dx, self.y + dy

    def take_damage(self, amount, enemy=None, knockback_x=None, knockback_y=None):
        """Demons can gain temporary immunity at high hit counts."""
        if self.circle_immunity_active and self.is_attacking:
            return True
        return super().take_damage(amount, enemy=enemy, knockback_x=knockback_x, knockback_y=knockback_y)

    def on_attack_started(self, dir_x, dir_y):
        """Hook for subclasses (reset effects if needed)."""
        self._attack_hold_looped = False
        self._attack_force_finish = False
        self.attack_hit_counts.clear()
        self.attack_last_frame_hit.clear()
        self.attack_last_effect_time.clear()
        self.circle_immunity_active = False
        self.circle_timers.clear()
        self.circle_entry_hit.clear()
        self._attack_tick_last_time = time.time()
        return []

    def update(self, dt, keys, mouse_clicked=False, mouse_world_pos=None, mouse_right_held=False, direct_input=None):
        # Detect attack hold (local mouse or direct input attack bool)
        hold = False
        try:
            mouse_state = pygame.mouse.get_pressed()
            hold = mouse_state[0]
        except Exception:
            hold = False
        if direct_input:
            hold = direct_input.get("attack", hold)
        # When P2 is controlled locally via keyboard (e.g., RCTRL), treat held key as a held attack
        if not hold and keys is not None:
            try:
                hold = keys[pygame.K_RCTRL] or keys[pygame.K_LCTRL] or keys[pygame.K_KP0]
            except Exception:
                pass

        spawned = super().update(dt, keys, mouse_clicked, mouse_world_pos, mouse_right_held, direct_input)

        # Control attack animation hold on frames 8-10 (indices 7-9), release to finish 11
        attack_anim = None
        if self.animations and "attack" in self.animations.animations:
            attack_anim = self.animations.animations["attack"]

        attack_active = self.is_attacking or (
            attack_anim
            and self.animations.current_animation == "attack"
            and not attack_anim.finished
        )

        if (attack_active or hold) and attack_anim:
            # If we already released and forced finish, let it play out naturally
            if getattr(self, "_attack_force_finish", False):
                if attack_anim.finished:
                    self._attack_force_finish = False
                return spawned

            hold_start = 7  # zero-based indices for frames 8,9,10
            hold_end = 9
            max_idx = len(attack_anim.frames) - 1
            hold_start = min(hold_start, max_idx)
            hold_end = min(hold_end, max_idx)
            if hold:
                self.is_attacking = True
                attack_anim.finished = False
                # Toggle between hold frames while held
                if attack_anim.current_frame < hold_start:
                    # Let it naturally reach the hold band
                    self._attack_hold_timer = 0.0
                else:
                    self._attack_hold_timer += dt
                    if self._attack_hold_timer >= attack_anim.frame_duration:
                        self._attack_hold_timer = 0.0
                        # Advance within hold band, loop back to start
                        next_frame = attack_anim.current_frame + 1
                        if next_frame > hold_end or next_frame > max_idx:
                            next_frame = hold_start
                        attack_anim.current_frame = next_frame
                        self._attack_hold_looped = True
                    # Clamp to hold band
                    if attack_anim.current_frame < hold_start or attack_anim.current_frame > hold_end:
                        attack_anim.current_frame = hold_start
                    attack_anim.timer = 0.0
            else:
                # Release: always finish starting from frame 8 if we reached/looped in the hold band
                if attack_anim.current_frame >= hold_start or self._attack_hold_looped:
                    attack_anim.finished = False
                    attack_anim.current_frame = hold_start
                    attack_anim.timer = 0.0
                    self._attack_hold_looped = False
                    self._attack_force_finish = True
                self._attack_hold_timer = 0.0
        else:
            self._attack_hold_timer = 0.0
            self._attack_force_finish = False
            self.circle_immunity_active = False
            self.circle_timers.clear()
            self.circle_entry_hit.clear()
            self._attack_tick_last_time = None

        return spawned

    def draw(self, screen, camera):
        """Draw body via base draw (attack includes breath in the combined sprite)."""
        super().draw(screen, camera)

    def draw_attack_hitbox(self, screen, camera, screen_x, screen_y):
        """Visualize circular swipe area when attacking."""
        if not self.is_attacking:
            return
        max_stack = max(self.stack_counts.values()) if self.stack_counts else 0
        radius_mult = 1.5 ** max(0, max_stack - 5)
        center_x, center_y, radius = self._attack_circle(radius_mult=radius_mult)
        cx, cy = camera.apply(center_x, center_y)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (255, 140, 0, 70), (int(cx), int(cy)), int(radius))
        pygame.draw.circle(overlay, (255, 200, 0, 180), (int(cx), int(cy)), int(radius), 2)
        screen.blit(overlay, (0, 0))

    def _attack_circle(self, radius_mult=1.0):
        """Return (cx, cy, radius) for demon's body slam/breath melee area."""
        # Use diagonal-only offsets (X pattern) and a larger reach.
        diag_map = {
            "right": (math.sqrt(0.5), math.sqrt(0.5)),   # bottom-right
            "left": (-math.sqrt(0.5), math.sqrt(0.5)),   # bottom-left
        }
        dir_x, dir_y = diag_map.get(self.facing_direction, (math.sqrt(0.5), math.sqrt(0.5)))
        # Push further outward with added margin
        offset = self.collision_radius * 0.6 + 80
        cx = self.x + dir_x * offset
        cy = self.y + dir_y * offset
        return cx, cy, self.collision_radius * 2 * radius_mult

    def attack_enemies(self, enemies):
        """Stack-based damage circle: apply entry hit, then per-second stacking effects."""
        if not self.is_attacking:
            return

        base_cx, base_cy, base_radius = self._attack_circle(radius_mult=1.0)
        now = time.time()
        if self._attack_tick_last_time is None:
            self._attack_tick_last_time = now
        dt = max(0.0, now - self._attack_tick_last_time)
        self._attack_tick_last_time = now

        for enemy in enemies:
            eid = id(enemy)
            stack = self.stack_counts.get(eid, 0)
            # Radius grows only after 5 stacks: 1.5x per stack above 5
            radius_mult = 1.5 ** max(0, stack - 5)
            cx, cy, radius = base_cx, base_cy, base_radius * radius_mult
            setattr(enemy, "stack_display", stack)

            ex, ey = getattr(enemy, "x", 0), getattr(enemy, "y", 0)
            enemy_r = getattr(enemy, "collision_radius", 0)
            dist = math.hypot(ex - cx, ey - cy)
            if dist > radius + enemy_r:
                continue

            # First time inside this circle: 1 damage + knockback 50
            if eid not in self.circle_entry_hit:
                self.circle_entry_hit.add(eid)
                self._apply_entry_hit(enemy, ex, ey)

            # Accumulate time spent inside this circle
            timer = self.circle_timers.get(eid, 0.0) + dt
            # Convert time into stacks (interval shortens once at 5 stacks)
            while True:
                interval = 0.5 if stack >= 5 else 1.0
                if timer < interval:
                    break
                timer -= interval
                stack += 1
                self.stack_counts[eid] = stack
                self._apply_stack_effect(enemy, stack)
                # Loop again in case large dt or doubled tick speed triggers multiple stacks
            self.circle_timers[eid] = timer
            setattr(enemy, "stack_display", stack)

    def _apply_entry_hit(self, enemy, ex, ey):
        """First entry into a fresh circle: 1 damage + 50 knockback."""
        if not enemy or not hasattr(enemy, "take_damage"):
            return
        dx = ex - self.x
        dy = ey - self.y
        mag = math.hypot(dx, dy)
        scale = 50.0 / 280.0  # Player.take_damage uses 280 as base knockback strength
        if mag > 1e-5:
            knockback_x = dx / mag * scale
            knockback_y = dy / mag * scale
        else:
            dir_x, dir_y = self._direction_vector(self.facing_direction)
            knockback_x = dir_x * scale
            knockback_y = dir_y * scale
        enemy.take_damage(1, enemy=self, knockback_x=knockback_x, knockback_y=knockback_y)
        # Ensure display shows current stack (stacks persist across circles)
        setattr(enemy, "stack_display", self.stack_counts.get(id(enemy), 0))

    def _apply_stack_effect(self, enemy, stack_count):
        """Apply stack-specific effects when an enemy gains a new stack."""
        if enemy is None:
            return
        dmg = 0
        heal_amt = 0
        slow_mult = None
        slow_time = 1.5

        if stack_count == 1:
            dmg = 1  # apply base damage on first stack tick
            slow_mult = 0.5  # 50% slow
        elif stack_count == 2:
            dmg = 2
            slow_mult = 0.5
        elif stack_count == 3:
            slow_mult = 0.2  # 80% slow
        elif stack_count == 4:
            heal_amt = 1
            slow_mult = 0.2
        elif stack_count == 5:
            slow_mult = 0.2  # Speed boost for stacking handled via shorter interval
        elif stack_count >= 6:
            dmg = max(1, stack_count - 5)  # +1 damage per stack above 5
            heal_amt = max(1, stack_count - 5)  # +1 heal per stack above 5
            slow_mult = 0.2

        if dmg > 0 and hasattr(enemy, "take_damage"):
            enemy.take_damage(dmg, enemy=self, knockback_x=None, knockback_y=None)
        if heal_amt > 0 and hasattr(self, "heal"):
            self.heal(heal_amt)
        if slow_mult is not None:
            if hasattr(enemy, "slow_debuff_timer"):
                enemy.slow_debuff_timer = max(slow_time, getattr(enemy, "slow_debuff_timer", 0))
            if hasattr(enemy, "slow_multiplier"):
                current_mult = getattr(enemy, "slow_multiplier", 1.0)
                enemy.slow_multiplier = min(current_mult, slow_mult)
