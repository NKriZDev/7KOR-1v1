"""Ghost enemy character"""

import pygame
import os
import random
import config
from file_animation import load_animation_from_folder


class Ghost:
    """Ghost enemy that emerges from ground when player is nearby"""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.base_speed = 40  # Base speed (will scale over time)
        self.speed = self.base_speed
        self.velocity_x = 0
        self.velocity_y = 0
        
        # Spawning mechanics
        self.spawn_trigger_range = 100  # Distance to player to trigger spawn
        self.is_spawning = False  # Currently emerging from ground
        self.spawn_progress = 0.0  # 0.0 to 1.0, how far emerged
        self.spawn_duration = 1.0  # 1 second to fully emerge
        self.spawn_timer = 0.0
        self.has_spawned = False  # Has finished spawning
        self.spawn_anchor_x = x  # Fixed position for spawn effect
        self.spawn_anchor_y = y
        
        # Collision settings
        self.collision_radius = 25  # Same as skeleton
        
        # Health system (1 HP during spawn, 4 HP after)
        self.spawn_health = 1  # Health during spawning
        self.max_health = 4  # Health after spawning
        self.health = self.spawn_health  # Start with spawn health
        self.xp_value = 10
        self.xp_awarded = False
        
        # Damage settings
        self.damage = 2  # Damage dealt to player
        self.bypasses_shield = True  # Ghosts go through shields
        
        # State tracking
        self.is_moving = False
        self.facing_direction = "down"
        self.is_dead = False
        self.is_dying = False  # Playing death animation
        
        # Speed scaling (1.1x per second)
        self.speed_scale = 1.0  # Current speed multiplier
        self.speed_scale_timer = 0.0  # Time since spawn completed
        
        # Knockback settings
        self.knockback_velocity_x = 0
        self.knockback_velocity_y = 0
        self.knockback_decay = 0.85  # How fast knockback slows down
        
        # Damage tracking (instant damage, no cooldown)
        self.damage_dealt_this_frame = False  # Track if damage was dealt this frame
        
        # Load walking animation from individual PNG files (used during spawn and movement)
        base_path = "Assets/Enemy/ghost"
        walk_anim = load_animation_from_folder(
            base_path,
            "ghost",
            4,  # 4 frames
            scale=config.ENEMY_SCALE,
            duration=0.12,
            loop=True
        )
        
        # Load appear animation (ghost-appear from Effects) - this is the effect animation
        appear_base_path = "Assets/Effects/ghost-appear"
        appear_anim = load_animation_from_folder(
            appear_base_path,
            "ghost-appear",
            6,  # 6 frames
            scale=config.ENEMY_SCALE,
            duration=0.15,
            loop=False  # Appear animation doesn't loop
        )
        
        # Load death animation (ghost-death from Effects)
        death_base_path = "Assets/Effects/ghost-death"
        death_anim = load_animation_from_folder(
            death_base_path,
            "ghost-death",
            6,  # 6 frames
            scale=config.ENEMY_SCALE,
            duration=0.15,
            loop=False  # Death animation doesn't loop
        )
        
        # Create simple animation manager for ghost sprite animations
        class SimpleAnimationManager:
            def __init__(self, walk_animation, death_animation):
                self.animations = {}
                if walk_animation:
                    self.animations['walk'] = walk_animation
                if death_animation:
                    self.animations['death'] = death_animation
                # Start with no animation (ghost is underground)
                self.current_animation = None
            
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
        
        # Create separate animation manager for appear effect
        class AppearAnimationManager:
            def __init__(self, appear_animation):
                self.animation = appear_animation
            
            def update(self, dt):
                if self.animation:
                    self.animation.update(dt)
            
            def get_current_frame(self):
                if self.animation:
                    return self.animation.get_current_frame()
                return None
            
            def reset(self):
                if self.animation:
                    self.animation.reset()
            
            def is_finished(self):
                if self.animation:
                    return self.animation.finished
                return False
        
        try:
            self.animations = SimpleAnimationManager(walk_anim, death_anim)
            self.appear_animation = AppearAnimationManager(appear_anim) if appear_anim else None
        except Exception as e:
            print(f"Error setting up ghost animations: {e}")
            self.animations = None
            self.appear_animation = None
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
        """Check if this ghost collides with another (enemy or player)"""
        dx = other.x - self.x
        dy = other.y - self.y
        distance = (dx**2 + dy**2)**0.5
        min_distance = self.collision_radius + other.collision_radius
        return distance < min_distance and distance > 0
    
    def check_player_collision(self, player):
        """Check if this ghost collides with player"""
        return self.check_collision(player)
    
    def take_damage(self, amount, knockback_x=0, knockback_y=0):
        """Take damage and apply knockback (can take damage during spawn)"""
        if self.is_dead or self.is_dying:
            return
        
        # Can take damage during spawning
        self.health = max(0, self.health - amount)
        
        # Apply knockback (same as skeleton, doubled for stronger pushback)
        knockback_strength = 600  # Pixels per second
        self.knockback_velocity_x = knockback_x * knockback_strength
        self.knockback_velocity_y = knockback_y * knockback_strength
        
        if self.health <= 0:
            self.is_dying = True
            # Freeze position on death (no further knockback)
            self.knockback_velocity_x = 0
            self.knockback_velocity_y = 0
            if self.animations:
                self.animations.set_animation('death')
        return self.health <= 0
    
    def deal_damage_to_player(self, player, dt):
        """Deal damage to player instantly on collision (only after spawning)"""
        if self.is_dead or self.is_dying or not self.has_spawned:
            return False
        
        if self.check_player_collision(player):
            # Deal damage instantly (no cooldown)
            if not self.damage_dealt_this_frame:
                # Deal damage (ghosts bypass shields, so pass self for bypass check)
                blocked = player.take_damage(self.damage, enemy=self)
                # Apply knockback to player on hit (ghosts always bypass shield)
                if not blocked:
                    dx = player.x - self.x
                    dy = player.y - self.y
                    distance = (dx**2 + dy**2)**0.5
                    if distance > 0:
                        knockback_strength = 250  # Player knockback from ghost hit
                        player.knockback_velocity_x = (dx / distance) * knockback_strength
                        player.knockback_velocity_y = (dy / distance) * knockback_strength
                self.damage_dealt_this_frame = True
                # Ghost dies when dealing damage
                self.health = 0
                self.is_dying = True
                # Freeze position on death (no further knockback)
                self.knockback_velocity_x = 0
                self.knockback_velocity_y = 0
                if self.animations:
                    self.animations.set_animation('death')
                return True
        else:
            # Reset damage flag if not colliding
            self.damage_dealt_this_frame = False
        return False
    
    def resolve_collision(self, other):
        """Push this ghost away from another enemy"""
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
            
            # Push this ghost away
            self.x -= push_x
            self.y -= push_y
    
    def update(self, dt, player_x, player_y, other_enemies, player):
        """Update ghost position and animations"""
        # Handle death animation (can happen during spawning)
        if self.is_dying:
            if self.animations:
                self.animations.set_animation('death')
                self.animations.update(dt)
                current_frame = self.animations.get_current_frame()
                if current_frame:
                    self.rect = current_frame.get_rect()
                    self.rect.center = (self.x, self.y)
                if self.animations.is_finished():
                    self.is_dead = True
        
        # Check if player is close enough to trigger spawn
        if not self.has_spawned and not self.is_spawning and not self.is_dying:
            dx = player_x - self.x
            dy = player_y - self.y
            distance = (dx**2 + dy**2)**0.5
            
            if distance <= self.spawn_trigger_range:
                # Start spawning
                self.is_spawning = True
                self.spawn_timer = 0.0
                self.spawn_progress = 0.0
                self.spawn_anchor_x = self.x
                self.spawn_anchor_y = self.y
                self.health = self.spawn_health  # Set to spawn health (1 HP)
                if self.appear_animation:
                    self.appear_animation.reset()
                if self.animations:
                    self.animations.set_animation('walk')
        
        # Handle spawning animation (fade in ghost sprite while appear effect plays)
        # Keep spawn animation playing even if dying
        if self.is_spawning:
            self.spawn_timer += dt
            self.spawn_progress = min(1.0, self.spawn_timer / self.spawn_duration)
            
            # Update appear effect animation
            if self.appear_animation:
                self.appear_animation.update(dt)
            
            # Update ghost sprite animation (walk/idle) - this will fade in
            # Only use walk animation if not dying (death animation takes priority)
            if self.animations and not self.is_dying:
                self.animations.set_animation('walk')
                self.animations.update(dt)
            
            # Check if spawn is complete
            if self.spawn_progress >= 1.0:
                # If dying during spawn, keep showing spawn visuals until death ends
                if not self.is_dying:
                    self.is_spawning = False
                    self.has_spawned = True
                    # Set health to full (4 HP) after spawning
                    self.health = self.max_health
                    self.speed_scale_timer = 0.0  # Reset speed scale timer
                    # Switch to walk animation after spawning
                    if self.animations:
                        self.animations.set_animation('walk')

        # If dying, stop further updates after processing spawn visuals
        if self.is_dying:
            # If death just finished, clean up spawn flag
            if self.animations and self.animations.is_finished():
                self.is_spawning = False
            return
        
        # Only update movement if fully spawned or spawning (can move during spawn)
        # Don't move when dying
        if self.is_dying:
            return
        if not self.has_spawned and not self.is_spawning:
            return
        
        # Update speed scaling (1.1x per second) - only after spawning starts
        if self.is_spawning or self.has_spawned:
            self.speed_scale_timer += dt
            self.speed_scale = 1.1 ** self.speed_scale_timer  # 1.1^seconds
            self.speed = self.base_speed * self.speed_scale
        
        # Apply knockback decay
        self.knockback_velocity_x *= self.knockback_decay
        self.knockback_velocity_y *= self.knockback_decay
        
        # Move towards player
        dx = player_x - self.x
        dy = player_y - self.y
        distance = (dx**2 + dy**2)**0.5
        
        if distance > 0:
            # Normalize direction
            direction_x = dx / distance
            direction_y = dy / distance
            
            # Set velocity towards player
            self.velocity_x = direction_x * self.speed
            self.velocity_y = direction_y * self.speed
            self.is_moving = True
        else:
            self.velocity_x = 0
            self.velocity_y = 0
            self.is_moving = False
        
        # Update facing direction
        self.facing_direction = self._determine_direction()
        
        # Update position
        self.x += (self.velocity_x + self.knockback_velocity_x) * dt
        self.y += (self.velocity_y + self.knockback_velocity_y) * dt
        
        # Resolve collisions with other enemies
        for other in other_enemies:
            if other is not self and not other.is_dead and not other.is_dying:
                if self.check_collision(other):
                    self.resolve_collision(other)
        
        # Reset damage flag at start of frame
        self.damage_dealt_this_frame = False
        
        # Deal damage to player (instant on collision, only after spawning)
        self.deal_damage_to_player(player, dt)
        
        # Update animations (only if not dying - death animation is handled above)
        if self.animations and not self.is_dying:
            if self.is_moving:
                self.animations.set_animation('walk')
            self.animations.update(dt)
        
        # Update rect
        current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
        if current_frame:
            self.rect = current_frame.get_rect()
        self.rect.center = (self.x, self.y)
    
    def draw(self, screen, camera):
        """Draw ghost with isometric offset"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        
        # Draw blue dot when ghost hasn't started spawning
        if not self.has_spawned and not self.is_spawning:
            # Draw small blue dot at ghost position
            pygame.draw.circle(screen, (100, 150, 255), (int(screen_x), int(screen_y)), 4)
            return
        
        # If dying, draw death animation (takes priority)
        if self.is_dying:
            # Continue drawing spawn appear effect underneath if it is still running
            if self.is_spawning and self.appear_animation:
                appear_frame = self.appear_animation.get_current_frame()
                if appear_frame:
                    anchor_screen_x, anchor_screen_y = camera.apply(self.spawn_anchor_x, self.spawn_anchor_y)
                    iso_x = anchor_screen_x - appear_frame.get_width() // 2
                    iso_y = anchor_screen_y - appear_frame.get_height() // 2
                    screen.blit(appear_frame, (iso_x, iso_y))

            death_frame = self.animations.get_current_frame() if self.animations else None
            # Fallback to appear animation if death frames are missing
            if not death_frame and self.appear_animation:
                death_frame = self.appear_animation.get_current_frame()
            # Final fallback to placeholder if both missing
            if not death_frame and hasattr(self, 'placeholder'):
                death_frame = self.placeholder
            if death_frame:
                # Apply isometric offset (Hades-style angled view)
                iso_x = screen_x - death_frame.get_width() // 2
                iso_y = screen_y - death_frame.get_height() // 2
                screen.blit(death_frame, (iso_x, iso_y))
            return
        
        # During spawning, draw both appear effect and ghost sprite (fading in)
        # Don't draw if dying (death animation is already drawn above)
        if self.is_spawning and not self.is_dying:
            # Draw appear effect animation (fully visible)
            if self.appear_animation:
                appear_frame = self.appear_animation.get_current_frame()
                if appear_frame:
                    anchor_screen_x, anchor_screen_y = camera.apply(self.spawn_anchor_x, self.spawn_anchor_y)
                    iso_x = anchor_screen_x - appear_frame.get_width() // 2
                    iso_y = anchor_screen_y - appear_frame.get_height() // 2
                    screen.blit(appear_frame, (iso_x, iso_y))
            
            # Draw ghost sprite (fading in from 0 to 100% opacity)
            if self.animations:
                ghost_frame = self.animations.get_current_frame()
            else:
                ghost_frame = self.placeholder
            
            if ghost_frame:
                # Flip sprite horizontally when facing left (default sprite faces right)
                if self.facing_direction == "left":
                    ghost_frame = pygame.transform.flip(ghost_frame, True, False)
                
                # Calculate opacity based on spawn progress (0.0 to 1.0)
                opacity = int(255 * self.spawn_progress)
                
                # Create a surface with alpha channel for fading
                fade_surface = pygame.Surface(ghost_frame.get_size(), pygame.SRCALPHA)
                # Blit the frame with alpha
                fade_surface.blit(ghost_frame, (0, 0))
                # Set alpha for the entire surface
                fade_surface.set_alpha(opacity)
                
                # Apply isometric offset (Hades-style angled view)
                iso_x = screen_x - fade_surface.get_width() // 2
                iso_y = screen_y - fade_surface.get_height() // 2
                
                screen.blit(fade_surface, (iso_x, iso_y))
                if self.health > 0:
                    self.draw_health_bar(screen, screen_x, screen_y, fade_surface.get_height())
        else:
            # After spawning, draw ghost sprite normally
            if self.animations:
                current_frame = self.animations.get_current_frame()
            else:
                current_frame = self.placeholder
            
            if current_frame:
                # Flip sprite horizontally when facing left (default sprite faces right)
                if self.facing_direction == "left":
                    current_frame = pygame.transform.flip(current_frame, True, False)
                
                # Apply isometric offset (Hades-style angled view)
                iso_x = screen_x - current_frame.get_width() // 2
                iso_y = screen_y - current_frame.get_height() // 2
                
                screen.blit(current_frame, (iso_x, iso_y))
                
                if self.health > 0:
                    self.draw_health_bar(screen, screen_x, screen_y, current_frame.get_height())

    def draw_health_bar(self, screen, screen_x, screen_y, sprite_height):
        """Draw a small health bar above the ghost"""
        bar_width = 44
        bar_height = 6
        offset_y = sprite_height // 2 + 12
        bar_x = screen_x - bar_width // 2
        bar_y = screen_y - offset_y
        
        # Background
        pygame.draw.rect(screen, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))
        # Split bar: small green sliver for spawn HP, remaining blue for post-spawn HP
        green_segment = max(4, int(bar_width * 0.15))  # very small green chunk
        blue_segment = bar_width - green_segment
        
        if not self.has_spawned:
            # Only green segment visible during spawn
            spawn_ratio = max(0, min(1, self.health / self.spawn_health if self.spawn_health else 1))
            green_width = int(green_segment * spawn_ratio)
            if green_width > 0:
                pygame.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, green_width, bar_height))
        else:
            # Green stays as fixed sliver if alive
            if self.health > 0:
                pygame.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, green_segment, bar_height))
            # Blue represents remaining health beyond spawn health
            remaining_health = max(0, self.health - self.spawn_health)
            remaining_max = max(1, self.max_health - self.spawn_health)
            blue_ratio = max(0, min(1, remaining_health / remaining_max))
            blue_width = int(blue_segment * blue_ratio)
            if blue_width > 0:
                pygame.draw.rect(screen, (80, 160, 255), (bar_x + green_segment, bar_y, blue_width, bar_height))
        # Border
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 1)
