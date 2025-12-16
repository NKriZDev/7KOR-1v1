"""Mage character: ranged-leaning fighter without a shield."""

import os
import pygame
import config
from projectile import Projectile
from animation import Animation
from file_animation import load_animation_from_folder
from player import Player, SimpleAnimationManager
from wizard import Wizard


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
        self.mage_animations = self.animations
        self.wizard_form = Wizard()
        self.wizard_animations = getattr(self.wizard_form, "animations", None)
        self.is_wizard_form = False
        self._right_click_prev = False
        self._wizard_attack_move_buffered = False
        self._wizard_attack_frozen = False
        self.active_wizard_effects = []
        self._wizard_placement_preview = None
        self.wizard_attack_count = 0
        self.wizard_cooldown_timer = 0.0
        self.wizard_invisible_timer = 0.0
        self.is_invisible = False
        self.wizard_explosion_pending = False
        self.wizard_explosion_data = None
        self.active_wizard_explosions = []
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

    def update(self, dt, keys, mouse_clicked=False, mouse_world_pos=None, mouse_right_held=False, direct_input=None):
        """Handle one-time wizard transform trigger before base updates."""
        # Tick cooldowns and invisibility
        if self.wizard_cooldown_timer > 0:
            self.wizard_cooldown_timer = max(0.0, self.wizard_cooldown_timer - dt)
        if self.wizard_invisible_timer > 0:
            self.wizard_invisible_timer = max(0.0, self.wizard_invisible_timer - dt)
        self.is_invisible = self.wizard_invisible_timer > 0

        self._handle_wizard_form(mouse_right_held)
        movement_pressed = self._is_movement_pressed(keys, direct_input)

        # Apply invisibility move buff and block attacks while invisible
        base_speed_before = self.base_speed
        if self.is_invisible:
            self.base_speed = base_speed_before * 2.0  # 100% buff
            mouse_clicked = False
            if direct_input:
                direct_input = dict(direct_input)
                direct_input["attack"] = False

        spawned = super().update(dt, keys, mouse_clicked, mouse_world_pos, mouse_right_held, direct_input)

        # Restore base speed after update
        self.base_speed = base_speed_before

        if self.is_wizard_form:
            self._wizard_placement_preview = self._clamp_bomb_target((self.mouse_world_x, self.mouse_world_y))
        else:
            self._wizard_placement_preview = None
        if self.is_wizard_form and self.is_attacking and movement_pressed:
            self._wizard_attack_move_buffered = True
        self._update_wizard_attack_effect(dt)
        self._update_wizard_explosions(dt)
        self._apply_wizard_attack_freeze(movement_pressed)
        return spawned

    def _handle_wizard_form(self, mouse_right_held):
        right_down = bool(mouse_right_held)
        clicked = right_down and not getattr(self, "_right_click_prev", False)
        self._right_click_prev = right_down
        if clicked and not self.is_wizard_form and self.wizard_cooldown_timer <= 0 and not self.is_invisible:
            self._enter_wizard_form()

    def _enter_wizard_form(self):
        self.is_wizard_form = True
        self.is_attacking = False
        self.attack_hit_enemies.clear()
        self._wizard_attack_move_buffered = False
        self._wizard_attack_frozen = False
        self.active_wizard_effects.clear()
        self.wizard_attack_count = 0
        self.animations = self.wizard_animations or self.mage_animations
        if self.wizard_form:
            self.wizard_form.reset_to_idle()
        elif self.animations and "idle" in self.animations.animations:
            self.animations.set_animation("idle")

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

    def on_attack_started(self, dir_x, dir_y):
        """Fire a projectile in the aimed direction."""
        if self.is_wizard_form:
            # Wizard form plays melee attack and spawns a fire-bomb effect at the tip.
            self._wizard_attack_move_buffered = False
            self._wizard_attack_frozen = False
            self.wizard_attack_count += 1
            if self.wizard_attack_count >= 5:
                self._trigger_wizard_explosion()
                return []
            effect_anim = self.wizard_form.clone_attack_effect()
            target_x, target_y = self._clamp_bomb_target((self.mouse_world_x, self.mouse_world_y))
            if effect_anim:
                self.active_wizard_effects.append(
                    {
                        "anim": effect_anim,
                        "pos": (target_x, target_y),
                        "radius": self._bomb_hitbox_radius(),
                        "hit": set(),
                    }
                )
            return []
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
        """For mage, draw a small rectangle at the aimed point; wizard skips melee visualization."""
        if self.is_wizard_form:
            return
        if self.is_attacking:
            target_x, target_y = self.last_shot_target
            tx, ty = camera.apply(target_x, target_y)
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            size = self.projectile_speed * 0 + 12  # constant size rectangle
            rect = pygame.Rect(0, 0, size, size)
            rect.center = (int(tx), int(ty))
            pygame.draw.rect(overlay, (255, 200, 0, 80), rect)
            pygame.draw.rect(overlay, (255, 150, 0, 180), rect, 2)
            screen.blit(overlay, (0, 0))

    def attack_enemies(self, enemies):
        """Mage uses projectiles; wizard form uses placed bomb effects."""
        if self.wizard_explosion_pending:
            self._damage_enemies_with_explosion(enemies)
            self.wizard_explosion_pending = False
            self.wizard_explosion_data = None
            return
        if self.is_wizard_form:
            self._damage_enemies_with_bombs(enemies)
            return
        return

    def _draw_wizard_fire_bombs(self, screen, camera):
        """Render all active wizard fire-bomb animations at their stored world positions."""
        for eff in self.active_wizard_effects:
            anim = eff.get("anim")
            pos = eff.get("pos", (self.x, self.y))
            if not anim:
                continue
            frame = anim.get_current_frame()
            if not frame:
                continue
            sx, sy = camera.apply(pos[0], pos[1])
            rect = frame.get_rect(center=(int(sx), int(sy)))
            screen.blit(frame, rect)

    def _update_wizard_attack_effect(self, dt):
        if not self.active_wizard_effects:
            return
        still_active = []
        for eff in self.active_wizard_effects:
            anim = eff.get("anim")
            if not anim:
                continue
            anim.update(dt)
            if not anim.finished:
                still_active.append(eff)
        self.active_wizard_effects = still_active

    def _trigger_wizard_explosion(self):
        """Trigger the 5th-attack explosion, invisibility, and cooldown."""
        radius = self._bomb_max_range()
        center = (self.x, self.y)
        exp_anim = self.wizard_form.clone_death_animation() if hasattr(self.wizard_form, "clone_death_animation") else None
        self.active_wizard_explosions.append({"anim": exp_anim, "pos": center, "radius": radius})
        self.wizard_explosion_pending = False
        self.wizard_explosion_data = None
        self.wizard_attack_count = 0
        self.wizard_cooldown_timer = 20.0
        self.wizard_invisible_timer = 5.0
        self.is_invisible = True
        self.is_wizard_form = False
        self.animations = self.mage_animations or self.animations
        self.active_wizard_effects.clear()
        self.is_attacking = False
        self._wizard_placement_preview = None
        self._wizard_attack_move_buffered = False
        self._wizard_attack_frozen = False

    def _update_wizard_explosions(self, dt):
        if not self.active_wizard_explosions:
            return
        remaining = []
        for exp in self.active_wizard_explosions:
            anim = exp.get("anim")
            if anim:
                anim.update(dt)
                if not anim.finished:
                    remaining.append(exp)
                else:
                    self.wizard_explosion_pending = True
                    self.wizard_explosion_data = {"pos": exp.get("pos", (self.x, self.y)), "radius": exp.get("radius", self._bomb_max_range())}
            else:
                # No anim; trigger immediately
                self.wizard_explosion_pending = True
                self.wizard_explosion_data = {"pos": exp.get("pos", (self.x, self.y)), "radius": exp.get("radius", self._bomb_max_range())}
        self.active_wizard_explosions = remaining

    def _apply_wizard_attack_freeze(self, movement_pressed):
        """If movement was buffered during attack, hold last attack frame while moving."""
        if not self.is_wizard_form:
            self._wizard_attack_move_buffered = False
            self._wizard_attack_frozen = False
            return
        if self.is_attacking:
            return
        if self._wizard_attack_move_buffered and movement_pressed:
            self._wizard_attack_frozen = True
            if self.animations and "attack" in self.animations.animations:
                self.animations.current_animation = "attack"
                atk_anim = self.animations.animations["attack"]
                if atk_anim.frames:
                    atk_anim.current_frame = len(atk_anim.frames) - 1
                atk_anim.finished = True
                atk_anim.timer = 0.0
        else:
            self._wizard_attack_frozen = False
            self._wizard_attack_move_buffered = False

    def _is_movement_pressed(self, keys, direct_input):
        """Check if any movement input is currently pressed."""
        if direct_input:
            return any(
                direct_input.get(axis, False)
                for axis in ("up", "down", "left", "right")
            )
        def pressed(key_name):
            key_code = self.controls.get(key_name)
            return bool(keys[key_code]) if key_code is not None else False
        return pressed("up") or pressed("down") or pressed("left") or pressed("right")

    def draw(self, screen, camera):
        """Draw mage and any lingering wizard fire-bomb effects."""
        if self.is_wizard_form:
            self._draw_wizard_range_indicator(screen, camera)
        if not self.is_invisible:
            super().draw(screen, camera)
        if self.is_wizard_form and getattr(self, "is_local_player", False):
            self._draw_wizard_mouse_preview(screen, camera)
        self._draw_wizard_fire_bombs(screen, camera)
        self._draw_wizard_explosions(screen, camera)
        if not self.is_wizard_form and getattr(self, "is_local_player", False):
            self._draw_wizard_cooldown(screen)

    def _draw_wizard_explosions(self, screen, camera):
        """Draw explosion visuals at the wizard's attack range."""
        for exp in self.active_wizard_explosions:
            pos = exp.get("pos", (self.x, self.y))
            radius = exp.get("radius", self._bomb_max_range())
            anim = exp.get("anim")
            cx, cy = camera.apply(pos[0], pos[1])
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(overlay, (255, 80, 0, 60), (int(cx), int(cy)), int(radius), 0)
            pygame.draw.circle(overlay, (255, 120, 0, 200), (int(cx), int(cy)), int(radius), 3)
            screen.blit(overlay, (0, 0))
            if anim:
                frame = anim.get_current_frame()
                if frame:
                    rect = frame.get_rect(center=(int(cx), int(cy)))
                    screen.blit(frame, rect)

    def _draw_wizard_range_indicator(self, screen, camera):
        """Show placement range circle (visible to all)."""
        center_x, center_y = camera.apply(self.x, self.y)
        range_pixels = self._bomb_max_range()
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (255, 180, 80, 40), (int(center_x), int(center_y)), int(range_pixels), 0)
        pygame.draw.circle(overlay, (255, 140, 60, 140), (int(center_x), int(center_y)), int(range_pixels), 2)
        screen.blit(overlay, (0, 0))

    def _draw_wizard_mouse_preview(self, screen, camera):
        """Local-only preview circle clamped inside placement range."""
        if not self._wizard_placement_preview:
            return
        radius = self._bomb_hitbox_radius()
        if radius <= 0:
            return
        px, py = self._wizard_placement_preview
        sx, sy = camera.apply(px, py)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (255, 210, 120, 60), (int(sx), int(sy)), int(radius), 0)
        pygame.draw.circle(overlay, (255, 160, 80, 200), (int(sx), int(sy)), int(radius), 2)
        screen.blit(overlay, (0, 0))

    def _bomb_hitbox_radius(self):
        """Radius of bomb hitbox that fits inside effect sprite."""
        return self.wizard_form.attack_effect_radius or (self.collision_radius * 1.1)

    def _bomb_max_range(self):
        """Maximum placement range from wizard center."""
        return self.attack_range * 2.0

    def _clamp_bomb_target(self, pos):
        """Clamp desired bomb position inside placement range."""
        if pos is None:
            return (self.x, self.y)
        tx, ty = pos
        dx = tx - self.x
        dy = ty - self.y
        dist_sq = dx * dx + dy * dy
        max_range = self._bomb_max_range()
        max_sq = max_range * max_range
        if dist_sq <= max_sq or dist_sq == 0:
            return (tx, ty)
        dist = dist_sq ** 0.5
        scale = max_range / dist
        return (self.x + dx * scale, self.y + dy * scale)

    def _damage_enemies_with_bombs(self, enemies):
        """Damage enemies inside any active bomb radius (one hit per bomb per enemy)."""
        radius = self._bomb_hitbox_radius()
        if radius <= 0:
            return
        for eff in self.active_wizard_effects:
            anim = eff.get("anim")
            # Only damage during frames 9-15 (0-based frames 8-14)
            if not anim or anim.current_frame < 8:
                continue
            pos = eff.get("pos", (self.x, self.y))
            hit_set = eff.setdefault("hit", set())
            for enemy in enemies:
                if id(enemy) in hit_set:
                    continue
                dx = enemy.x - pos[0]
                dy = enemy.y - pos[1]
                dist = (dx * dx + dy * dy) ** 0.5
                if dist <= radius + getattr(enemy, "collision_radius", 0):
                    if hasattr(enemy, "take_damage"):
                        enemy.take_damage(self.attack_damage, enemy=self, knockback_x=0, knockback_y=0)
                    hit_set.add(id(enemy))

    def _damage_enemies_with_explosion(self, enemies):
        """Damage all enemies within the full placement range explosion."""
        data = self.wizard_explosion_data or {"pos": (self.x, self.y), "radius": self._bomb_max_range()}
        pos = data.get("pos", (self.x, self.y))
        radius = data.get("radius", self._bomb_max_range())
        for enemy in enemies:
            dx = enemy.x - pos[0]
            dy = enemy.y - pos[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius + getattr(enemy, "collision_radius", 0):
                if hasattr(enemy, "take_damage"):
                    enemy.take_damage(self.attack_damage, enemy=self, knockback_x=0, knockback_y=0)

    def _draw_wizard_cooldown(self, screen):
        """Show cooldown countdown text for local player only."""
        if self.wizard_cooldown_timer <= 0:
            return
        font = pygame.font.Font(None, 28)
        txt = font.render(f"Wizard CD: {self.wizard_cooldown_timer:0.1f}s", True, (255, 200, 120))
        x = screen.get_width() // 2 - txt.get_width() // 2
        y = screen.get_height() - txt.get_height() - 12
        screen.blit(txt, (x, y))
