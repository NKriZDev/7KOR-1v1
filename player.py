"""Player character with animations and movement"""

import pygame
import math
import config
from player_stats import apply_buffs
from animation import Animation

# Default keyboard/mouse bindings for a player
DEFAULT_CONTROLS = {
    "up": pygame.K_w,
    "down": pygame.K_s,
    "left": pygame.K_a,
    "right": pygame.K_d,
    "dash": pygame.K_SPACE,
    "gesture": pygame.K_g,
    "attack": "mouse_left",
    "block": "mouse_right",
}


class SimpleAnimationManager:
    """Minimal animation wrapper so subclasses can swap in real animations."""
    def __init__(self, animations_dict):
        self.animations = animations_dict or {}
        self.current_animation = None
        if self.animations:
            self.current_animation = list(self.animations.keys())[0]
    
    def set_animation(self, anim_name):
        if anim_name in self.animations:
            if anim_name != self.current_animation:
                self.current_animation = anim_name
                self.animations[anim_name].reset()
    
    def update(self, dt):
        if self.current_animation and self.current_animation in self.animations:
            self.animations[self.current_animation].update(dt)
    
    def get_current_frame(self):
        if self.current_animation and self.current_animation in self.animations:
            return self.animations[self.current_animation].get_current_frame()
        return None


class Player:
    """Base player: shared movement, health, hitboxes. Character-specific data comes from config/subclasses."""
    
    def __init__(self, x, y, controls=None, name="Player", ui_color=(0, 200, 0), character_config=None):
        self.x = x
        self.y = y
        self.name = name
        cfg = character_config or {}
        stats = cfg.get("stats", {})
        # Base stats (overridable per character)
        self.base_speed = stats.get("speed", config.PLAYER_SPEED)
        self.speed = self.base_speed
        self.velocity_x = 0
        self.velocity_y = 0
        # Control bindings
        self.controls = (controls or DEFAULT_CONTROLS).copy()
        # Sprite facing configuration (flip when facing left by default)
        self.flip_on_left = cfg.get("flip_on_left", True)
        
        # Health system
        self.base_max_health = stats.get("max_health", config.PLAYER_MAX_HEALTH)
        self.max_health = self.base_max_health
        self.health = self.max_health
        self.is_dead = False
        self.ui_color = ui_color
        self.enable_shield = cfg.get("enable_shield", True)
        self.enable_dash = cfg.get("enable_dash", True)
        self.enable_gesture = cfg.get("enable_gesture", True)
        
        # Damage effects
        self.damage_flash_timer = 0.0
        self.damage_flash_duration = 0.2  # Flash red for 0.2 seconds
        self.slow_debuff_timer = 0.0
        self.slow_debuff_duration = 1.5  # Slow for 1.5 seconds
        self.slow_multiplier = 0.2  # 80% speed reduction (20% of original speed)
        self.critical_hit_timer = 0.0
        self.critical_hit_duration = 2.0  # Show critical text for 2 seconds
        self.critical_border_timer = 0.0
        self.critical_border_duration = 1.5  # Red borders for 1.5 seconds
        self.critical_text_world_x = 0.0  # World position where critical hit occurred
        self.critical_text_world_y = 0.0
        self.critical_text_offset_y = 0.0  # Vertical offset for floating effect
        self.critical_text_world_x = 0.0  # World position where critical hit occurred
        self.critical_text_world_y = 0.0
        self.critical_text_offset_y = 0.0  # Vertical offset for floating effect
        # Shielded popup effects
        self.shield_block_timer = 0.0
        self.shield_block_duration = 1.2
        self.shield_text_world_x = 0.0
        self.shield_text_world_y = 0.0
        self.shield_text_offset_y = 0.0
        
        # Mouse/attack direction tracking
        self.mouse_world_x = 0.0
        self.mouse_world_y = 0.0
        self.attack_direction = "down"  # Direction of attack (towards mouse)
        
        # Hitbox/collision settings
        self.collision_radius = stats.get("collision_radius", 20)  # Radius for collision detection
        
        # Shield/knockback settings
        self.knockback_velocity_x = 0.0
        self.knockback_velocity_y = 0.0
        self.knockback_decay = 0.92  # Decay per frame
        
        # Attack settings
        self.base_attack_damage = stats.get("attack_damage", 2)
        self.attack_range = stats.get("attack_range", 50)  # Range of attack in pixels
        self.attack_damage = self.base_attack_damage
        self.attack_hit_enemies = set()  # Track enemies hit in current attack
        self.attack_origin_x = x
        self.attack_origin_y = y
        self.attack_dir_x = 0.0
        self.attack_dir_y = 1.0
        self.attack_length = self.attack_range
        self.attack_base_half_width = self.attack_range * 0.35
        # Apply buffs to stats
        self.refresh_stats_from_buffs()
        
        # XP/level
        self.level = 1
        self.xp = 0
        
        # Movement state tracking
        self.facing_direction = "down"
        self.is_moving = False
        self.is_attacking = False
        self.is_gesturing = False
        self.is_blocking = False  # Shield up
        self.shield_direction = "down"  # Direction shield is facing
        self.shield_angle = math.pi / 2  # Continuous radians, defaults to down
        # Dash settings
        self.is_dashing = False
        self.dash_timer = 0.0
        self.dash_duration = 0.2
        self.dash_cooldown = 0.6
        self.dash_cooldown_timer = 0.0
        self.dash_speed_multiplier = 4.0
        self.dash_dir_x = 0.0
        self.dash_dir_y = 0.0
        self._dash_key_was_down = False
        self.is_hurt = False  # Playing hurt animation
        self.hurt_timer = 0.0  # Timer for hurt animation
        
        # Load animations (subclass/builder can supply, otherwise placeholder)
        self.animations = None
        anim_builder = cfg.get("build_animations")
        if anim_builder:
            try:
                self.animations = anim_builder()
            except Exception as e:
                print(f"Error building animations for {self.name}: {e}")
        if not self.animations:
            self.animations = self._build_placeholder_animations()
        
        # Get sprite dimensions for rect
        current_frame = self.animations.get_current_frame() if self.animations else None
        if current_frame:
            self.rect = current_frame.get_rect()
        else:
            self.rect = pygame.Rect(0, 0, config.PLAYER_FRAME_WIDTH, config.PLAYER_FRAME_HEIGHT)
        self.rect.center = (self.x, self.y)

    def _build_placeholder_animations(self):
        """Fallback animations so base class works without character assets."""
        size = (
            int(config.PLAYER_FRAME_WIDTH * config.PLAYER_SCALE),
            int(config.PLAYER_FRAME_HEIGHT * config.PLAYER_SCALE),
        )
        base = pygame.Surface(size, pygame.SRCALPHA)
        # Slight translucency to differentiate placeholders
        base.fill((*self.ui_color, 220))
        idle = Animation([base], frame_duration=config.ANIMATION_DURATIONS['idle'], loop=True)
        walk = Animation([base], frame_duration=config.ANIMATION_DURATIONS['walk'], loop=True)
        attack = Animation([base], frame_duration=config.ANIMATION_DURATIONS['attack'], loop=False)
        gesture = Animation([base], frame_duration=config.ANIMATION_DURATIONS['gesture'], loop=False)
        shield = Animation([base], frame_duration=config.ANIMATION_DURATIONS.get('idle', 0.15), loop=True)
        hurt = Animation([base], frame_duration=0.3, loop=False)
        anims = {
            "idle": idle,
            "walk": walk,
            "attack": attack,
            "gesture": gesture,
            "shield": shield,
            "hurt": hurt,
        }
        manager = SimpleAnimationManager(anims)
        manager.set_animation('idle')
        return manager
        
    def _determine_direction(self):
        """Determine facing direction based on movement"""
        if abs(self.velocity_y) > abs(self.velocity_x):
            # Vertical movement takes priority
            if self.velocity_y < 0:
                return "up"
            else:
                return "down"
        elif self.velocity_x != 0:
            # Horizontal movement
            if self.velocity_x < 0:
                return "left"
            else:
                return "right"
        # No movement, keep current direction
        return self.facing_direction

    def _angle_to_direction(self, angle_rad):
        """Map continuous angle to a cardinal direction for sprite facing"""
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)
        if abs(dy) > abs(dx):
            return "down" if dy > 0 else "up"
        else:
            return "right" if dx > 0 else "left"

    def _direction_vector(self, direction):
        """Return a unit vector for a cardinal direction string"""
        if direction == "up":
            return 0.0, -1.0
        if direction == "down":
            return 0.0, 1.0
        if direction == "left":
            return -1.0, 0.0
        if direction == "right":
            return 1.0, 0.0
        return 0.0, 1.0
    
    def _normalize_angle(self, angle):
        """Wrap angle to [-pi, pi]"""
        while angle <= -math.pi:
            angle += 2 * math.pi
        while angle > math.pi:
            angle -= 2 * math.pi
        return angle

    def _unwrap_angle(self, prev_angle, new_angle):
        """Unwrap new_angle relative to prev_angle to keep continuity"""
        delta = new_angle - prev_angle
        while delta <= -math.pi:
            delta += 2 * math.pi
        while delta > math.pi:
            delta -= 2 * math.pi
        return prev_angle + delta

    def refresh_stats_from_buffs(self):
        """Recalculate derived stats using buffs"""
        base_stats = {
            "speed": self.base_speed,
            "max_health": self.base_max_health,
            "attack_damage": self.base_attack_damage,
            "attack_range": self.attack_range,
        }
        buffed = apply_buffs(base_stats)
        old_max = self.max_health
        self.speed = buffed["speed"]
        # Preserve current health proportionally when max changes
        if old_max > 0:
            health_ratio = self.health / old_max
        else:
            health_ratio = 1.0
        self.max_health = buffed["max_health"]
        self.health = min(self.max_health, self.max_health * health_ratio)
        self.attack_damage = buffed["attack_damage"]
        self.attack_range = buffed["attack_range"]

    def on_attack_started(self, dir_x, dir_y):
        """Hook for subclasses (e.g., ranged attacks). Return list of spawned projectiles."""
        return []

    def _xp_threshold(self):
        """XP needed for next level"""
        return 50 + 25 * (self.level - 1)

    def add_xp(self, amount):
        """Add XP and handle level-ups"""
        self.xp += amount
        levels_gained = 0
        while self.xp >= self._xp_threshold():
            self.xp -= self._xp_threshold()
            self.level += 1
            levels_gained += 1
        return levels_gained
    
    def update(self, dt, keys, mouse_clicked=False, mouse_world_pos=None, mouse_right_held=False, direct_input=None):
        """Update player position and animations based on input. Returns any spawned projectiles."""
        spawned = []
        if self.health <= 0:
            self.is_dead = True
        if self.is_dead:
            self.velocity_x = 0
            self.velocity_y = 0
            return spawned

        if mouse_world_pos is None:
            dir_x, dir_y = self._direction_vector(self.attack_direction)
            mouse_world_pos = (self.x + dir_x * self.attack_range * 2,
                               self.y + dir_y * self.attack_range * 2)

        if mouse_world_pos:
            self.mouse_world_x, self.mouse_world_y = mouse_world_pos
            dx = self.mouse_world_x - self.x
            dy = self.mouse_world_y - self.y
            if abs(dy) > abs(dx):
                self.attack_direction = "down" if dy > 0 else "up"
            else:
                self.attack_direction = "right" if dx > 0 else "left"
            if dx != 0 or dy != 0:
                raw_angle = math.atan2(dy, dx)
                self.shield_angle = self._unwrap_angle(self.shield_angle, raw_angle)
                self.shield_direction = self._angle_to_direction(self.shield_angle)
        
        attack_in_progress = self.is_attacking or (
            self.animations
            and self.animations.current_animation == 'attack'
            and 'attack' in self.animations.animations
            and not self.animations.animations['attack'].finished
        )

        self.is_blocking = self.enable_shield and mouse_right_held and not attack_in_progress
        if not self.enable_shield:
            self.is_blocking = False
        if self.is_blocking and not self.is_attacking:
            self.facing_direction = self.shield_direction
        
        self.knockback_velocity_x *= self.knockback_decay
        self.knockback_velocity_y *= self.knockback_decay
        
        if self.damage_flash_timer > 0:
            self.damage_flash_timer = max(0, self.damage_flash_timer - dt)
        if self.slow_debuff_timer > 0:
            self.slow_debuff_timer = max(0, self.slow_debuff_timer - dt)
            self.speed = self.base_speed * self.slow_multiplier
        else:
            self.speed = self.base_speed
        if self.dash_cooldown_timer > 0:
            self.dash_cooldown_timer = max(0, self.dash_cooldown_timer - dt)
        if self.is_dashing:
            self.dash_timer -= dt
            if self.dash_timer <= 0:
                self.is_dashing = False
        if self.critical_hit_timer > 0:
            self.critical_hit_timer = max(0, self.critical_hit_timer - dt)
            self.critical_text_offset_y -= 30 * dt
        if self.critical_border_timer > 0:
            self.critical_border_timer = max(0, self.critical_border_timer - dt)
        if self.shield_block_timer > 0:
            self.shield_block_timer = max(0, self.shield_block_timer - dt)
            self.shield_text_offset_y -= 25 * dt
        if self.is_hurt:
            self.hurt_timer -= dt
            if self.hurt_timer <= 0:
                self.is_hurt = False
                if self.animations and 'hurt' in self.animations.animations:
                    self.animations.animations['hurt'].reset()
        
        if self.animations:
            current_anim = self.animations.current_animation
            if current_anim == 'attack' and 'attack' in self.animations.animations and self.animations.animations['attack'].finished:
                self.is_attacking = False
            if current_anim == 'gesture' and 'gesture' in self.animations.animations and self.animations.animations['gesture'].finished:
                self.is_gesturing = False
                self.animations.animations['gesture'].reset()
            if current_anim == 'hurt' and 'hurt' in self.animations.animations and self.animations.animations['hurt'].finished:
                self.is_hurt = False
        
        if self.is_attacking:
            self.velocity_x = 0
            self.velocity_y = 0
            self.is_moving = False
        else:
            self.velocity_x = 0
            self.velocity_y = 0
            move_speed = self.speed * (0.5 if self.is_blocking else 1.0)
            up_pressed = direct_input.get("up", False) if direct_input else keys[self.controls["up"]]
            down_pressed = direct_input.get("down", False) if direct_input else keys[self.controls["down"]]
            left_pressed = direct_input.get("left", False) if direct_input else keys[self.controls["left"]]
            right_pressed = direct_input.get("right", False) if direct_input else keys[self.controls["right"]]
            if up_pressed:
                self.velocity_y = -move_speed
            if down_pressed:
                self.velocity_y = move_speed
            if left_pressed:
                self.velocity_x = -move_speed
            if right_pressed:
                self.velocity_x = move_speed
            if self.velocity_x != 0 and self.velocity_y != 0:
                self.velocity_x *= 0.707
                self.velocity_y *= 0.707
            self.is_moving = (self.velocity_x != 0 or self.velocity_y != 0)
            if not self.is_attacking:
                if self.is_blocking:
                    self.facing_direction = self.shield_direction
                else:
                    self.facing_direction = self._determine_direction()
                if direct_input and mouse_world_pos is None:
                    self.attack_direction = self.facing_direction
        
        dash_key = self.controls.get("dash", pygame.K_SPACE)
        dash_key_down = (direct_input.get("dash", False) if direct_input else (keys[dash_key] if dash_key is not None else False))
        if (self.enable_dash and dash_key_down and not self._dash_key_was_down and not self.is_dashing 
                and self.dash_cooldown_timer <= 0 and not self.is_attacking and not self.is_hurt):
            dir_x, dir_y = 0.0, 0.0
            if self.velocity_x != 0 or self.velocity_y != 0:
                mag = (self.velocity_x**2 + self.velocity_y**2) ** 0.5
                if mag > 0:
                    dir_x = self.velocity_x / mag
                    dir_y = self.velocity_y / mag
            else:
                dir_x, dir_y = self._direction_vector(self.facing_direction)
            self.dash_dir_x = dir_x
            self.dash_dir_y = dir_y
            self.is_dashing = True
            self.dash_timer = self.dash_duration
            self.dash_cooldown_timer = self.dash_cooldown
        if not self.enable_dash:
            self.is_dashing = False
        if self.is_dashing:
            dash_speed = self.base_speed * self.dash_speed_multiplier
            self.velocity_x = self.dash_dir_x * dash_speed
            self.velocity_y = self.dash_dir_y * dash_speed
            self.is_moving = True
        
        if mouse_clicked and not self.is_gesturing:
            can_attack = True
            if self.animations and 'attack' in self.animations.animations:
                attack_anim = self.animations.animations['attack']
                is_attack_playing = self.animations.current_animation == 'attack'
                can_attack = (not is_attack_playing) or attack_anim.finished
            
            if can_attack and not self.is_attacking:
                self.is_attacking = True
                self.attack_hit_enemies.clear()
                self.is_blocking = False
                self.attack_origin_x = self.x
                self.attack_origin_y = self.y
                dx = self.mouse_world_x - self.x
                dy = self.mouse_world_y - self.y
                dist = (dx ** 2 + dy ** 2) ** 0.5
                if dist > 0:
                    self.attack_dir_x = dx / dist
                    self.attack_dir_y = dy / dist
                else:
                    self.attack_dir_x, self.attack_dir_y = self._direction_vector(self.facing_direction)
                self.attack_length = self.attack_range * 2.0
                self.attack_base_half_width = self.attack_range * 0.35
                self.facing_direction = self.attack_direction
                if self.animations and 'attack' in self.animations.animations:
                    self.animations.set_animation('attack')
                    self.animations.animations['attack'].reset()
                spawned.extend(self.on_attack_started(self.attack_dir_x, self.attack_dir_y))
        
        gesture_key = self.controls.get("gesture", pygame.K_g)
        gesture_pressed = direct_input.get("gesture", False) if direct_input else (keys[gesture_key] if gesture_key is not None else False)
        if (self.enable_gesture and gesture_pressed
                and not self.is_attacking and not self.is_gesturing):
            if self.animations:
                if self.animations.current_animation != 'gesture' or self.animations.animations['gesture'].finished:
                    self.is_gesturing = True
                    self.animations.set_animation('gesture')
        
        if self.animations:
            if self.is_hurt:
                self.animations.set_animation('hurt')
            elif self.is_blocking and 'shield' in self.animations.animations:
                self.animations.set_animation('shield')
            elif self.is_attacking:
                self.animations.set_animation('attack')
            elif self.is_gesturing:
                self.animations.set_animation('gesture')
            elif self.is_moving:
                self.animations.set_animation('walk')
            else:
                self.animations.set_animation('idle')
        
        if self.animations:
            self.animations.update(dt)
        
        self.x += (self.velocity_x + self.knockback_velocity_x) * dt
        self.y += (self.velocity_y + self.knockback_velocity_y) * dt
        
        self._dash_key_was_down = dash_key_down
        
        current_frame = self.animations.get_current_frame() if self.animations else None
        if current_frame:
            self.rect = current_frame.get_rect()
            self.rect.center = (self.x, self.y)
        
        return spawned
    
    def check_collision(self, other):
        """Check if player collides with another entity (enemy)"""
        dx = other.x - self.x
        dy = other.y - self.y
        distance = (dx**2 + dy**2)**0.5
        min_distance = self.collision_radius + other.collision_radius
        return distance < min_distance and distance > 0
    
    def resolve_collision(self, other):
        """Push player away from another entity (enemy)"""
        dx = other.x - self.x
        dy = other.y - self.y
        distance = (dx**2 + dy**2)**0.5
        
        if distance == 0:
            # If exactly on top of each other, push in random direction
            import random
            dx = random.choice([-1, 1])
            dy = random.choice([-1, 1])
            distance = 1.0
        
        min_distance = self.collision_radius + other.collision_radius
        overlap = min_distance - distance
        
        if overlap > 0:
            # Normalize direction
            if distance > 0:
                push_x = (dx / distance) * overlap * 0.5
                push_y = (dy / distance) * overlap * 0.5
            else:
                push_x = overlap * 0.5
                push_y = overlap * 0.5
            
            # Push player away
            self.x -= push_x
            self.y -= push_y
    
    def draw(self, screen, camera):
        """Draw player with isometric offset"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        
        # Draw shield coverage visualization underneath sprite when blocking
        if self.is_blocking:
            self.draw_shield_coverage(screen, screen_x, screen_y)
        
        # Get current animation frame
        current_frame = self.animations.get_current_frame() if self.animations else None
        
        if current_frame:
            # Flip sprite horizontally (reverse when hurt)
            flip_left = self.facing_direction == "left"
            if self.is_hurt:
                flip_left = not flip_left
            should_flip = flip_left if self.flip_on_left else not flip_left
            if should_flip:
                current_frame = pygame.transform.flip(current_frame, True, False)
            # Apply red tint if taking damage
            if self.damage_flash_timer > 0:
                # Create a red-tinted version of the frame
                red_tint = pygame.Surface(current_frame.get_size(), pygame.SRCALPHA)
                red_tint.fill((255, 0, 0, 128))  # Red with 50% opacity
                current_frame = current_frame.copy()
                current_frame.blit(red_tint, (0, 0), special_flags=pygame.BLEND_MULT)
            
            # Apply isometric offset (Hades-style angled view)
            iso_x = screen_x - current_frame.get_width() // 2
            iso_y = screen_y - current_frame.get_height() // 2
            
            screen.blit(current_frame, (iso_x, iso_y))
            
            # Draw directional arrow indicator under player
            self.draw_direction_indicator(screen, screen_x, screen_y)
        
        # Draw attack hitbox visualization when attacking
        if self.is_attacking:
            self.draw_attack_hitbox(screen, camera, screen_x, screen_y)

    def draw_attack_hitbox(self, screen, camera, screen_x, screen_y):
        """Visualize current attack hitbox"""
        apex, base_left, base_right = self.get_attack_triangle_points()
        points_screen = [
            camera.apply(apex[0], apex[1]),
            camera.apply(base_left[0], base_left[1]),
            camera.apply(base_right[0], base_right[1]),
        ]
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(overlay, (255, 255, 0, 60), points_screen)
        pygame.draw.polygon(overlay, (255, 200, 0, 180), points_screen, 2)
        screen.blit(overlay, (0, 0))
    
    def draw_shield_coverage(self, screen, screen_x, screen_y):
        """Visualize shield coverage cone around player"""
        cone_radius = self.collision_radius + 60  # Original cone reach
        arc_radius = self.collision_radius + 55  # Slightly further arc
        cone_half_angle = math.pi / 3  # Matches block tolerance (~60 deg each side)
        arc_half_angle = math.pi / 4   # Shorter arc sweep
        base_angle = self.shield_angle
        
        # Build fan polygon for filled cone
        segments = 12
        points = []
        for i in range(-segments, segments + 1):
            angle = base_angle + (cone_half_angle * i / segments)
            px = screen_x + math.cos(angle) * cone_radius
            py = screen_y + math.sin(angle) * cone_radius
            points.append((px, py))
        polygon_points = [(screen_x, screen_y)] + points
        
        # Draw translucent cone on a small overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        fill_color = (80, 160, 255, 70)  # Light blue, transparent
        pygame.draw.polygon(overlay, fill_color, polygon_points)

        # Draw a faint arc behind the player (opposite the shield cone), using poly points to avoid wrap issues
        edge_color = (90, 170, 255, 210)
        back_angle = base_angle + math.pi  # Opposite direction
        arc_points = []
        for i in range(-segments, segments + 1):
            angle = back_angle + (arc_half_angle * i / segments)
            px = screen_x + math.cos(angle) * arc_radius
            py = screen_y + math.sin(angle) * arc_radius
            arc_points.append((px, py))
        if len(arc_points) >= 2:
            pygame.draw.lines(overlay, edge_color, False, arc_points, 4)
        screen.blit(overlay, (0, 0))
    
    def take_damage(self, amount, enemy=None, knockback_x=None, knockback_y=None):
        """Take damage and ensure health doesn't go below 0. Returns True if damage was blocked"""
        # Check if enemy can bypass shield (ghosts go through shields)
        can_bypass_shield = False
        if enemy is not None and hasattr(enemy, 'bypasses_shield'):
            can_bypass_shield = enemy.bypasses_shield
        
        # Check if shield is blocking (unless enemy bypasses shield)
        if self.is_blocking and enemy is not None and not can_bypass_shield:
            # Check if shield is facing towards enemy
            dx = getattr(enemy, "x", None)
            dy = getattr(enemy, "y", None)
            if dx is None or dy is None:
                # If attacker has no position (e.g., placeholder knockback values), treat as unblocked
                dx = dy = 0
            else:
                dx = dx - self.x
                dy = dy - self.y
            distance = (dx**2 + dy**2)**0.5
            
            # If distance is 0 or very small, can't determine direction, so don't block
            if distance > 1.0:
                # Calculate angle between shield aim and enemy
                angle_to_enemy = math.atan2(dy, dx)
                # Properly wrap angular difference to [0, pi]
                angle_diff = abs((angle_to_enemy - self.shield_angle + math.pi) % (2 * math.pi) - math.pi)
                
                # Block if enemy is within 60 degrees (pi/3 radians) of shield direction
                shield_blocks = angle_diff <= math.pi / 3
                
                if shield_blocks:
                    # Block damage, apply knockback to player
                    knockback_strength = 0
                    if hasattr(enemy, 'shield_knockback'):
                        knockback_strength = enemy.shield_knockback
                    else:
                        # Default knockback if enemy doesn't have shield_knockback attribute
                        knockback_strength = 150
                    
                    if knockback_strength > 0:
                        # Normalize direction (enemy to player)
                        knockback_x = -dx / distance
                        knockback_y = -dy / distance
                        
                        self.knockback_velocity_x = knockback_x * knockback_strength
                        self.knockback_velocity_y = knockback_y * knockback_strength
                    
                    # Apply knockback to enemy (half of what they get when attacked)
                    enemy_knockback_strength = 0
                    if hasattr(enemy, 'shield_knockback'):
                        # Skeleton: half of shield knockback (which is already half of attack knockback)
                        # Hell Gato: half of shield knockback (which is 100% of attack knockback)
                        enemy_knockback_strength = enemy.shield_knockback * 0.5
                    
                    if enemy_knockback_strength > 0:
                        # Direction away from player
                        enemy_knockback_x = dx / distance
                        enemy_knockback_y = dy / distance
                        
                        if hasattr(enemy, 'knockback_velocity_x'):
                            enemy.knockback_velocity_x = enemy_knockback_x * enemy_knockback_strength
                            enemy.knockback_velocity_y = enemy_knockback_y * enemy_knockback_strength
                    
                    # Return True to prevent damage
                    # Trigger shielded popup
                    self.shield_block_timer = self.shield_block_duration
                    self.shield_text_world_x = self.x
                    self.shield_text_world_y = self.y
                    self.shield_text_offset_y = 0.0
                    return True  # Blocked, no damage taken
        
        # Not blocked, take damage normally
        self.health = max(0, self.health - amount)
        if self.health <= 0:
            self.is_dead = True
        
        # Apply knockback from attackers (player vs player)
        if knockback_x is not None and knockback_y is not None:
            knockback_strength = 280
            self.knockback_velocity_x = knockback_x * knockback_strength
            self.knockback_velocity_y = knockback_y * knockback_strength
        
        # Trigger hurt animation
        self.is_hurt = True
        self.hurt_timer = 0.3  # Duration of hurt animation
        if self.animations and 'hurt' in self.animations.animations:
            self.animations.set_animation('hurt')
            self.animations.animations['hurt'].reset()
        
        # Trigger damage flash (red tint)
        self.damage_flash_timer = self.damage_flash_duration
        
        # Check if damage is more than 25% of max health
        damage_percentage = (amount / self.max_health) * 100
        if damage_percentage > 25:
            # Apply slow debuff (80% speed reduction for 1.5 seconds)
            self.slow_debuff_timer = self.slow_debuff_duration
            # Trigger critical hit effects
            self.critical_hit_timer = self.critical_hit_duration
            self.critical_border_timer = self.critical_border_duration
            # Store world position where critical hit occurred
            self.critical_text_world_x = self.x
            self.critical_text_world_y = self.y
            self.critical_text_offset_y = 0.0  # Reset offset
        
        return False  # Not blocked, damage taken
    
    def heal(self, amount):
        """Heal and ensure health doesn't exceed max"""
        self.health = min(self.max_health, self.health + amount)
    
    def get_attack_triangle_points(self):
        """Return triangle points (apex, base_left, base_right) for current attack"""
        ox, oy = self.attack_origin_x, self.attack_origin_y
        dir_x, dir_y = self.attack_dir_x, self.attack_dir_y
        length = self.attack_length
        base_half = self.attack_base_half_width
        # Base is near the player (origin); tip is forward along attack direction
        perp_x = -dir_y
        perp_y = dir_x
        base_left = (ox + perp_x * base_half, oy + perp_y * base_half)
        base_right = (ox - perp_x * base_half, oy - perp_y * base_half)
        apex = (ox + dir_x * length, oy + dir_y * length)
        return apex, base_left, base_right
    
    def check_attack_hit(self, enemy):
        """Check if enemy is within attack hitbox"""
        if not self.is_attacking:
            return False
        
        # Don't hit same enemy twice in one attack
        if id(enemy) in self.attack_hit_enemies:
            return False
        
        # Triangle thrust check using snapshotted attack origin/direction
        ox, oy = self.attack_origin_x, self.attack_origin_y
        dir_x, dir_y = self.attack_dir_x, self.attack_dir_y
        length = max(1e-5, self.attack_length)
        dx = enemy.x - ox
        dy = enemy.y - oy
        proj = dx * dir_x + dy * dir_y
        if proj < 0 or proj > length + enemy.collision_radius:
            return False
        perp = abs(dx * (-dir_y) + dy * dir_x)
        # Base is near the player; width tapers to the tip
        max_width = self.attack_base_half_width * max(0.0, 1.0 - (proj / length))
        if perp <= max_width + enemy.collision_radius:
            self.attack_hit_enemies.add(id(enemy))
            return True
        return False
    
    def attack_enemies(self, enemies):
        """Attack enemies within hitbox"""
        if not self.is_attacking:
            return
        
        for enemy in enemies:
            if self.check_attack_hit(enemy):
                # Calculate knockback direction (away from player)
                dx = enemy.x - self.x
                dy = enemy.y - self.y
                distance = (dx**2 + dy**2)**0.5
                if distance > 0:
                    knockback_x = dx / distance
                    knockback_y = dy / distance
                else:
                    # If exactly on top, use facing direction
                    if self.facing_direction == "up":
                        knockback_x, knockback_y = 0, -1
                    elif self.facing_direction == "down":
                        knockback_x, knockback_y = 0, 1
                    elif self.facing_direction == "left":
                        knockback_x, knockback_y = -1, 0
                    else:  # right
                        knockback_x, knockback_y = 1, 0
                
                # Deal damage to enemy with knockback
                if hasattr(enemy, 'take_damage'):
                    enemy.take_damage(self.attack_damage, enemy=self, knockback_x=knockback_x, knockback_y=knockback_y)
    
    def draw_health_bar(self, screen):
        """Draw health bar at top of screen"""
        bar_width = 200
        bar_height = 20
        bar_x = 10
        bar_y = 10
        
        # Background (red)
        pygame.draw.rect(screen, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))
        
        # Health (green)
        health_width = int((self.health / self.max_health) * bar_width)
        if health_width > 0:
            pygame.draw.rect(screen, self.ui_color, (bar_x, bar_y, health_width, bar_height))
        
        # Border
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 2)
        
        # Health text
        font = pygame.font.Font(None, 18)
        health_text = font.render(f"{int(self.health)}/{self.max_health}", True, (255, 255, 255))
        text_x = bar_x + (bar_width - health_text.get_width()) // 2
        text_y = bar_y + (bar_height - health_text.get_height()) // 2
        screen.blit(health_text, (text_x, text_y))

    def draw_xp_bar(self, screen):
        """Draw XP bar below health bar"""
        bar_width = 200
        bar_height = 12
        bar_x = 10
        bar_y = 36
        
        xp_needed = self._xp_threshold()
        xp_ratio = 0 if xp_needed <= 0 else self.xp / xp_needed
        xp_ratio = max(0, min(1, xp_ratio))
        
        # Background
        pygame.draw.rect(screen, (30, 30, 60), (bar_x, bar_y, bar_width, bar_height))
        # Fill
        fill_width = int(bar_width * xp_ratio)
        if fill_width > 0:
            pygame.draw.rect(screen, (70, 130, 255), (bar_x, bar_y, fill_width, bar_height))
        # Border
        pygame.draw.rect(screen, (200, 200, 255), (bar_x, bar_y, bar_width, bar_height), 1)
        # Text
        font = pygame.font.Font(None, 18)
        xp_text = font.render(f"LV {self.level}  {self.xp}/{xp_needed}", True, (200, 200, 255))
        text_x = bar_x + (bar_width - xp_text.get_width()) // 2
        text_y = bar_y + (bar_height - xp_text.get_height()) // 2
        screen.blit(xp_text, (text_x, text_y))
    
    def draw_direction_indicator(self, screen, screen_x, screen_y):
        """Draw directional arrow indicator showing mouse direction"""
        # Calculate direction to mouse
        dx = self.mouse_world_x - self.x
        dy = self.mouse_world_y - self.y
        distance = (dx**2 + dy**2)**0.5
        
        if distance > 0:
            # Normalize direction
            dir_x = dx / distance
            dir_y = dy / distance
            
            # Draw arrow under player (offset by sprite height)
            arrow_length = 30
            arrow_start_x = screen_x
            arrow_start_y = screen_y + 40  # Below player sprite
            arrow_end_x = screen_x + dir_x * arrow_length
            arrow_end_y = screen_y + 40 + dir_y * arrow_length
            
            # Draw arrow line
            pygame.draw.line(screen, (255, 255, 0), (arrow_start_x, arrow_start_y), 
                           (arrow_end_x, arrow_end_y), 3)
            
            # Draw arrowhead
            arrowhead_size = 8
            # Perpendicular vectors for arrowhead
            perp_x = -dir_y
            perp_y = dir_x
            
            # Arrowhead points
            tip_x = arrow_end_x
            tip_y = arrow_end_y
            left_x = arrow_end_x - dir_x * arrowhead_size + perp_x * arrowhead_size * 0.5
            left_y = arrow_end_y - dir_y * arrowhead_size + perp_y * arrowhead_size * 0.5
            right_x = arrow_end_x - dir_x * arrowhead_size - perp_x * arrowhead_size * 0.5
            right_y = arrow_end_y - dir_y * arrowhead_size - perp_y * arrowhead_size * 0.5
            
            pygame.draw.polygon(screen, (255, 255, 0), 
                              [(tip_x, tip_y), (left_x, left_y), (right_x, right_y)])
    
    def draw_critical_effects(self, screen, camera):
        """Draw critical hit effects (text and borders) and shield blocks"""
        # Draw "CRITICAL" text at world position
        if self.critical_hit_timer > 0:
            # Convert world position to screen coordinates
            screen_x, screen_y = camera.apply(self.critical_text_world_x, 
                                            self.critical_text_world_y + self.critical_text_offset_y)
            
            # Create styled text with outline
            font = pygame.font.Font(None, 48)  # Smaller size
            text = "CRITICAL"
            
            # Calculate alpha based on timer (fade out)
            alpha = int(255 * (self.critical_hit_timer / self.critical_hit_duration))
            
            # Create text with outline effect
            # Render outline (black, larger)
            outline_surfaces = []
            for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
                outline_text = font.render(text, True, (0, 0, 0))
                outline_surfaces.append((outline_text, dx, dy))
            
            # Render main text (red with alpha)
            main_text = font.render(text, True, (255, 0, 0))
            main_text.set_alpha(alpha)
            
            # Blit outline first
            for outline_text, dx, dy in outline_surfaces:
                outline_text.set_alpha(alpha)
                text_rect = outline_text.get_rect(center=(screen_x + dx, screen_y + dy))
                screen.blit(outline_text, text_rect)
            
            # Blit main text on top
            text_rect = main_text.get_rect(center=(screen_x, screen_y))
            screen.blit(main_text, text_rect)
        
        # Draw gradient red borders (like shooter games) only for the local player
        if self.critical_border_timer > 0 and getattr(self, "is_local_player", False):
            border_thickness = 30
            fade_distance = 50  # Distance for gradient fade
            
            # Calculate alpha based on timer
            max_alpha = int(180 * (self.critical_border_timer / self.critical_border_duration))
            red_surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
            
            # Top border with gradient
            for i in range(border_thickness):
                alpha = int(max_alpha * (1.0 - i / border_thickness))
                if alpha > 0:
                    pygame.draw.rect(red_surface, (255, 0, 0, alpha), 
                                   (0, i, config.SCREEN_WIDTH, 1))
            
            # Bottom border with gradient
            for i in range(border_thickness):
                alpha = int(max_alpha * (1.0 - i / border_thickness))
                if alpha > 0:
                    pygame.draw.rect(red_surface, (255, 0, 0, alpha), 
                                   (0, config.SCREEN_HEIGHT - border_thickness + i, config.SCREEN_WIDTH, 1))
            
            # Left border with gradient
            for i in range(border_thickness):
                alpha = int(max_alpha * (1.0 - i / border_thickness))
                if alpha > 0:
                    pygame.draw.rect(red_surface, (255, 0, 0, alpha), 
                                   (i, 0, 1, config.SCREEN_HEIGHT))
            
            # Right border with gradient
            for i in range(border_thickness):
                alpha = int(max_alpha * (1.0 - i / border_thickness))
                if alpha > 0:
                    pygame.draw.rect(red_surface, (255, 0, 0, alpha), 
                                   (config.SCREEN_WIDTH - border_thickness + i, 0, 1, config.SCREEN_HEIGHT))
            
            screen.blit(red_surface, (0, 0))

        # Draw "SHIELDED" popup when blocking attacks
        if self.shield_block_timer > 0:
            screen_x, screen_y = camera.apply(
                self.shield_text_world_x,
                self.shield_text_world_y + self.shield_text_offset_y
            )
            font = pygame.font.Font(None, 42)
            text = "SHIELDED"
            alpha = int(255 * (self.shield_block_timer / self.shield_block_duration))
            outline_surfaces = []
            for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
                outline_text = font.render(text, True, (0, 0, 0))
                outline_surfaces.append((outline_text, dx, dy))
            main_text = font.render(text, True, (120, 200, 255))
            main_text.set_alpha(alpha)
            for outline_text, dx, dy in outline_surfaces:
                outline_text.set_alpha(alpha)
                text_rect = outline_text.get_rect(center=(screen_x + dx, screen_y + dy))
                screen.blit(outline_text, text_rect)
            text_rect = main_text.get_rect(center=(screen_x, screen_y))
            screen.blit(main_text, text_rect)
