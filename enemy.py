"""Enemy character with animations"""

import pygame
import config
from animation import AnimationManager


class Enemy:
    """Enemy character with animations"""
    
    def __init__(self, x, y, sprite_sheet_path, frame_width=32, frame_height=32, scale=2.0):
        self.x = x
        self.y = y
        self.speed = 50  # Slower than player
        self.velocity_x = 0
        self.velocity_y = 0
        
        # State tracking
        self.is_moving = False
        self.is_attacking = False
        self.facing_direction = "down"
        
        # Animation configuration
        # Row 0: idle (2 columns)
        # Row 1: walk (4 columns)
        # Row 2: attack (5 columns)
        animations_config = {
            'idle': {
                'row': 0,
                'frames': 2,
                'start_col': 0,
                'duration': 0.2,
                'loop': True
            },
            'walk': {
                'row': 1,
                'frames': 4,
                'start_col': 0,
                'duration': 0.15,
                'loop': True
            },
            'attack': {
                'row': 2,
                'frames': 5,
                'start_col': 0,
                'duration': 0.1,
                'loop': False
            },
        }
        
        # Initialize animation manager
        try:
            self.animations = AnimationManager(
                sprite_sheet_path,
                frame_width,
                frame_height,
                animations_config,
                scale=scale
            )
            self.animations.set_animation('idle')
        except Exception as e:
            print(f"Error setting up enemy animations: {e}")
            self.animations = None
            self.placeholder = pygame.Surface(
                (frame_width * int(scale), frame_height * int(scale))
            )
            self.placeholder.fill((255, 0, 0))  # Red placeholder
        
        # Get sprite dimensions for rect
        current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
        if current_frame:
            self.rect = current_frame.get_rect()
        else:
            self.rect = pygame.Rect(0, 0, frame_width, frame_height)
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
    
    def update(self, dt, target_x=None, target_y=None):
        """Update enemy position and animations"""
        # Reset attack state if animation finished
        if self.animations:
            current_anim = self.animations.current_animation
            if current_anim == 'attack' and self.animations.animations['attack'].finished:
                self.is_attacking = False
        
        # Simple AI: move towards target if provided
        if target_x is not None and target_y is not None and not self.is_attacking:
            dx = target_x - self.x
            dy = target_y - self.y
            distance = (dx**2 + dy**2)**0.5
            
            if distance > 50:  # Only move if far enough
                self.velocity_x = (dx / distance) * self.speed
                self.velocity_y = (dy / distance) * self.speed
                self.is_moving = True
            else:
                # Close enough, attack
                self.velocity_x = 0
                self.velocity_y = 0
                self.is_moving = False
                if not self.is_attacking:
                    self.is_attacking = True
                    if self.animations:
                        self.animations.set_animation('attack')
        else:
            self.velocity_x = 0
            self.velocity_y = 0
            self.is_moving = False
        
        # Update facing direction
        if self.is_moving:
            self.facing_direction = self._determine_direction()
        
        # Update animation based on state
        if self.animations and not self.is_attacking:
            if self.is_moving:
                self.animations.set_animation('walk')
            else:
                self.animations.set_animation('idle')
        
        # Update animations
        if self.animations:
            self.animations.update(dt)
        
        # Update position
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt
        
        # Update rect
        current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
        if current_frame:
            self.rect = current_frame.get_rect()
            self.rect.center = (self.x, self.y)
    
    def draw(self, screen, camera):
        """Draw enemy with isometric offset"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        
        # Get current animation frame
        if self.animations:
            current_frame = self.animations.get_current_frame()
        else:
            current_frame = self.placeholder
        
        if current_frame:
            # Flip sprite horizontally when facing left
            if self.facing_direction == "left":
                current_frame = pygame.transform.flip(current_frame, True, False)
            
            # Apply isometric offset (Hades-style angled view)
            iso_x = screen_x - current_frame.get_width() // 2
            iso_y = screen_y - current_frame.get_height() // 2
            
            screen.blit(current_frame, (iso_x, iso_y))

