"""Animation system for sprite sheets"""

import pygame


class Animation:
    """Handles a single animation sequence from a sprite sheet"""
    
    def __init__(self, frames, frame_duration=0.1, loop=True):
        """
        Args:
            frames: List of pygame.Surface objects (animation frames)
            frame_duration: Time each frame is displayed (in seconds)
            loop: Whether animation loops or plays once
        """
        self.frames = frames
        self.frame_duration = frame_duration
        self.loop = loop
        self.current_frame = 0
        self.timer = 0.0
        self.finished = False
        
    def update(self, dt):
        """Update animation frame"""
        if self.finished and not self.loop:
            return
            
        self.timer += dt
        if self.timer >= self.frame_duration:
            self.timer = 0.0
            self.current_frame += 1
            
            if self.current_frame >= len(self.frames):
                if self.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = len(self.frames) - 1
                    self.finished = True
    
    def get_current_frame(self):
        """Get the current frame surface"""
        if not self.frames:
            return None
        return self.frames[self.current_frame]
    
    def reset(self):
        """Reset animation to first frame"""
        self.current_frame = 0
        self.timer = 0.0
        self.finished = False


class AnimationManager:
    """Manages multiple animations for a sprite"""
    
    def __init__(self, sprite_sheet_path, frame_width, frame_height, 
                 animations_config, scale=1.0):
        """
        Args:
            sprite_sheet_path: Path to sprite sheet image
            frame_width: Width of each frame in pixels
            frame_height: Height of each frame in pixels
            animations_config: Dict mapping animation names to config
                Example: {
                    'idle': {'row': 0, 'frames': 10, 'duration': 0.15},
                    'walk': {'row': 2, 'frames': 10, 'duration': 0.1},
                }
            scale: Scale factor for sprites (1.0 = original size)
        """
        # Load sprite sheet
        try:
            self.sprite_sheet = pygame.image.load(sprite_sheet_path).convert_alpha()
        except pygame.error as e:
            print(f"Error loading sprite sheet: {e}")
            # Create placeholder
            self.sprite_sheet = pygame.Surface((frame_width, frame_height))
            self.sprite_sheet.fill((255, 0, 255))
        
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.scale = scale
        
        # Extract frames for each animation
        self.animations = {}
        for anim_name, config in animations_config.items():
            frames = self._extract_frames(
                config['row'],
                config.get('frames', 1),
                config.get('start_col', 0)
            )
            duration = config.get('duration', 0.1)
            loop = config.get('loop', True)
            self.animations[anim_name] = Animation(frames, duration, loop)
        
        # Current animation state
        self.current_animation = None
        if self.animations:
            self.current_animation = list(self.animations.keys())[0]
    
    def _extract_frames(self, row, num_frames, start_col=0):
        """Extract frames from sprite sheet at specified row"""
        frames = []
        sheet_width, sheet_height = self.sprite_sheet.get_size()
        
        for col in range(start_col, start_col + num_frames):
            x = col * self.frame_width
            y = row * self.frame_height
            
            # Check bounds
            if x + self.frame_width > sheet_width or y + self.frame_height > sheet_height:
                # Create placeholder frame if out of bounds
                frame = pygame.Surface((self.frame_width, self.frame_height))
                frame.fill((255, 0, 0))  # Red placeholder
            else:
                # Extract frame
                frame = pygame.Surface((self.frame_width, self.frame_height), pygame.SRCALPHA)
                frame.blit(self.sprite_sheet, (0, 0), (x, y, self.frame_width, self.frame_height))
            
            # Scale if needed
            if self.scale != 1.0:
                new_width = int(self.frame_width * self.scale)
                new_height = int(self.frame_height * self.scale)
                frame = pygame.transform.scale(frame, (new_width, new_height))
            
            frames.append(frame)
        
        return frames
    
    def set_animation(self, anim_name):
        """Switch to a different animation"""
        if anim_name in self.animations:
            if anim_name != self.current_animation:
                self.current_animation = anim_name
                self.animations[anim_name].reset()
            # If same animation, don't reset (allows animation to continue)
    
    def update(self, dt):
        """Update current animation"""
        if self.current_animation:
            self.animations[self.current_animation].update(dt)
    
    def get_current_frame(self):
        """Get current frame of current animation"""
        if self.current_animation:
            return self.animations[self.current_animation].get_current_frame()
        return None
    
    def get_animation_names(self):
        """Get list of available animation names"""
        return list(self.animations.keys())

