"""Skeleton enemy character"""

import pygame
import os
import random
import config
from file_animation import load_animation_from_folder


class Skeleton:
    """Skeleton enemy with walking animation"""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 40  # Slower than player
        self.velocity_x = 0
        self.velocity_y = 0
        
        # Collision settings
        self.collision_radius = 25  # Radius for collision detection
        
        # Health system
        self.max_health = config.ENEMY_MAX_HEALTH
        self.health = self.max_health
        self.xp_value = 5
        self.xp_awarded = False
        
        # Damage settings
        self.damage = 1  # Damage dealt to player
        self.attack_duration = 0.5  # Seconds to perform attack
        self.attack_cooldown = 1.0  # Seconds between attacks
        self.attack_timer = 0.0  # Current attack timer
        
        # Shield knockback (half of what skeleton gets knocked back)
        self.shield_knockback = config.SKELETON_SHIELD_KNOCKBACK
        self.damage_cooldown = self.attack_duration + self.attack_cooldown  # Total time between damage
        self.damage_timer = 0.0  # Current cooldown timer
        self.is_attacking = False  # Whether currently performing attack
        
        # State tracking
        self.is_moving = False
        self.facing_direction = "down"
        self.is_dead = False
        self.is_dying = False  # Playing death animation
        self.is_rising = True  # Start with rise animation
        
        # Knockback settings
        self.knockback_velocity_x = 0
        self.knockback_velocity_y = 0
        self.knockback_decay = 0.85  # How fast knockback slows down
        
        # Load walking animation from individual PNG files
        base_path = "Assets/Enemy/skeleton"
        walk_anim = load_animation_from_folder(
            base_path,
            "skeleton",
            8,  # 8 frames
            scale=config.ENEMY_SCALE,
            duration=0.12,
            loop=True
        )
        
        # Load death animation
        death_base_path = "Assets/Effects/enemy-death"
        death_anim = load_animation_from_folder(
            death_base_path,
            "enemy-death",
            5,  # 5 frames
            scale=config.ENEMY_SCALE,
            duration=0.15,
            loop=False  # Death animation doesn't loop
        )
        
        # Load rise animation
        rise_base_path = "Assets/Effects/skeleton-rise"
        rise_anim = load_animation_from_folder(
            rise_base_path,
            "skeleton-rise",
            6,  # 6 frames
            scale=config.ENEMY_SCALE,
            duration=0.30,  # Half speed (doubled from 0.15)
            loop=False  # Rise animation doesn't loop
        )
        
        # Create simple animation manager
        class SimpleAnimationManager:
            def __init__(self, walk_animation, death_animation, rise_animation):
                self.animations = {}
                if walk_animation:
                    self.animations['walk'] = walk_animation
                if death_animation:
                    self.animations['death'] = death_animation
                if rise_animation:
                    self.animations['rise'] = rise_animation
                # Start with rise animation if available
                self.current_animation = 'rise' if rise_animation else ('walk' if walk_animation else None)
            
            def set_animation(self, anim_name):
                if anim_name in self.animations:
                    if self.current_animation != anim_name:
                        self.current_animation = anim_name
                        self.animations[anim_name].reset()
            
            def update(self, dt):
                if self.current_animation and self.current_animation in self.animations:
                    self.animations[self.current_animation].update(dt)
            
            def get_current_frame(self):
                if self.current_animation and self.current_animation in self.animations:
                    return self.animations[self.current_animation].get_current_frame()
                return None
            
            def is_finished(self):
                if self.current_animation and self.current_animation in self.animations:
                    return self.animations[self.current_animation].finished
                return False
        
        try:
            self.animations = SimpleAnimationManager(walk_anim, death_anim, rise_anim)
        except Exception as e:
            print(f"Error setting up skeleton animations: {e}")
            self.animations = None
            self.placeholder = pygame.Surface((32 * int(config.ENEMY_SCALE), 32 * int(config.ENEMY_SCALE)))
            self.placeholder.fill((200, 200, 200))  # Gray placeholder
        
        # Get sprite dimensions for rect
        current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
        if current_frame:
            self.rect = current_frame.get_rect()
        else:
            self.rect = pygame.Rect(0, 0, 32, 32)
        self.rect.center = (self.x, self.y)
    
    def _determine_direction(self):
        """Determine facing direction based on movement"""
        if abs(self.velocity_y) > abs(self.velocity_x):
            if self.velocity_y < 0:
                return "up"
            else:
                return "down"
        elif self.velocity_x != 0:
            if self.velocity_x < 0:
                return "left"
            else:
                return "right"
        return self.facing_direction
    
    def check_collision(self, other):
        """Check if this skeleton collides with another (enemy or player)"""
        dx = other.x - self.x
        dy = other.y - self.y
        distance = (dx**2 + dy**2)**0.5
        min_distance = self.collision_radius + other.collision_radius
        return distance < min_distance and distance > 0
    
    def check_player_collision(self, player):
        """Check if this skeleton collides with player"""
        return self.check_collision(player)
    
    def take_damage(self, amount, knockback_x=0, knockback_y=0):
        """Take damage and apply knockback"""
        if self.is_dead or self.is_dying:
            return
        self.health = max(0, self.health - amount)
        
        # Apply knockback (increased strength)
        knockback_strength = 300  # Pixels per second (increased from 100)
        self.knockback_velocity_x = knockback_x * knockback_strength
        self.knockback_velocity_y = knockback_y * knockback_strength
        
        if self.health <= 0:
            self.is_dying = True
            self.is_rising = False  # Stop rising if dying
            # Freeze knockback on death
            self.knockback_velocity_x = 0
            self.knockback_velocity_y = 0
            if self.animations:
                self.animations.set_animation('death')
        return self.health <= 0
    
    def deal_damage_to_player(self, player, dt):
        """Deal damage to player if colliding and cooldown is ready"""
        if self.is_dead or self.is_dying:
            return False
        
        if self.check_player_collision(player):
            self.damage_timer += dt
            
            if not self.is_attacking:
                # Wait for reload/cooldown (1 second)
                if self.damage_timer >= self.attack_cooldown:
                    # Start attack phase
                    self.is_attacking = True
                    self.damage_timer = 0.0  # Reset timer for attack duration
            else:
                # During attack phase (0.5 seconds)
                if self.damage_timer >= self.attack_duration:
                    # Deal damage at end of attack (pass self for shield blocking check)
                    blocked = player.take_damage(self.damage, enemy=self)
                    self.is_attacking = False
                    self.damage_timer = 0.0  # Start reload timer
                    return True
        else:
            # Reset timers if not colliding
            self.damage_timer = 0.0
            self.is_attacking = False
        return False
    
    def resolve_collision(self, other):
        """Push this skeleton away from another skeleton"""
        dx = other.x - self.x
        dy = other.y - self.y
        distance = (dx**2 + dy**2)**0.5
        
        if distance == 0:
            # If exactly on top of each other, push in random direction
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
            
            # Push this skeleton away
            self.x -= push_x
            self.y -= push_y
    
    def update(self, dt, target_x=None, target_y=None, other_enemies=None, player=None):
        """Update skeleton position and animations"""
        # Check if death animation finished
        if self.is_dying:
            # Stop movement while dying
            self.velocity_x = 0
            self.velocity_y = 0
            self.knockback_velocity_x = 0
            self.knockback_velocity_y = 0
            # Update death animation
            if self.animations:
                if self.animations.current_animation != 'death':
                    self.animations.set_animation('death')
                self.animations.update(dt)
                if self.animations.is_finished():
                    self.is_dead = True
            # Update rect
            current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
            if current_frame:
                self.rect = current_frame.get_rect()
                self.rect.center = (self.x, self.y)
            return
        
        # Don't update if dead
        if self.is_dead:
            return
        
        # Handle rise animation - stay in place until complete
        if self.is_rising:
            if self.animations:
                if self.animations.current_animation != 'rise':
                    self.animations.set_animation('rise')
                self.animations.update(dt)
                # Check if rise animation finished
                if self.animations.is_finished():
                    self.is_rising = False
                    if self.animations:
                        self.animations.set_animation('walk')
            return
        
        # Simple AI: move towards target if provided
        if target_x is not None and target_y is not None:
            dx = target_x - self.x
            dy = target_y - self.y
            distance = (dx**2 + dy**2)**0.5
            
            if distance > 30:  # Always try to move towards player
                self.velocity_x = (dx / distance) * self.speed
                self.velocity_y = (dy / distance) * self.speed
                self.is_moving = True
            else:
                self.velocity_x = 0
                self.velocity_y = 0
                self.is_moving = False
        else:
            self.velocity_x = 0
            self.velocity_y = 0
            self.is_moving = False
        
        # Update facing direction
        if self.is_moving:
            self.facing_direction = self._determine_direction()
        
        # Update animations
        if self.animations:
            self.animations.update(dt)
        
        # Apply knockback (decay over time)
        self.knockback_velocity_x *= self.knockback_decay
        self.knockback_velocity_y *= self.knockback_decay
        
        # Update position (movement + knockback)
        self.x += (self.velocity_x + self.knockback_velocity_x) * dt
        self.y += (self.velocity_y + self.knockback_velocity_y) * dt
        
        # Handle collisions with other enemies (only if not being knocked back much)
        if other_enemies and abs(self.knockback_velocity_x) < 10 and abs(self.knockback_velocity_y) < 10:
            for other in other_enemies:
                if other != self and not other.is_dying and not other.is_dead and self.check_collision(other):
                    self.resolve_collision(other)
        
        # Deal damage to player if colliding (with cooldown)
        if player:
            self.deal_damage_to_player(player, dt)
        
        # Update rect
        current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
        if current_frame:
            self.rect = current_frame.get_rect()
            self.rect.center = (self.x, self.y)
    
    def draw(self, screen, camera):
        """Draw skeleton with isometric offset"""
        # Don't draw if dead (after death animation finished)
        if self.is_dead:
            return
        
        screen_x, screen_y = camera.apply(self.x, self.y)
        
        # Get current animation frame
        if self.animations:
            current_frame = self.animations.get_current_frame()
        else:
            current_frame = self.placeholder
        
        if current_frame:
            # Don't flip death or rise animations
            if not self.is_dying and not self.is_rising and self.facing_direction == "right":
                current_frame = pygame.transform.flip(current_frame, True, False)
            
            # Apply isometric offset (Hades-style angled view)
            iso_x = screen_x - current_frame.get_width() // 2
            iso_y = screen_y - current_frame.get_height() // 2
            
            screen.blit(current_frame, (iso_x, iso_y))
            
            if self.health > 0:
                self.draw_health_bar(screen, screen_x, screen_y, current_frame.get_height())

    def draw_health_bar(self, screen, screen_x, screen_y, sprite_height):
        """Draw a small health bar above the skeleton"""
        bar_width = 44
        bar_height = 6
        offset_y = sprite_height // 2 + 12
        bar_x = screen_x - bar_width // 2
        bar_y = screen_y - offset_y
        
        # Background
        pygame.draw.rect(screen, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))
        # Health fill
        health_ratio = max(0, min(1, self.health / self.max_health))
        fill_width = int(bar_width * health_ratio)
        if fill_width > 0:
            pygame.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, fill_width, bar_height))
        # Border
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 1)
