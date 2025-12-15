"""Animation system for individual PNG files"""

import pygame
import os
import glob
from animation import Animation


class FileAnimationManager:
    """Manages animations loaded from individual PNG files"""
    
    def __init__(self, animations_config, scale=1.0):
        """
        Args:
            animations_config: Dict mapping animation names to file paths
                Example: {
                    'idle': ['path/idle-1.png', 'path/idle-2.png', ...],
                    'walk': ['path/walk-1.png', 'path/walk-2.png', ...],
                }
            scale: Scale factor for sprites (1.0 = original size)
        """
        self.scale = scale
        self.animations = {}
        
        # Load frames for each animation
        for anim_name, file_paths in animations_config.items():
            frames = []
            for file_path in file_paths:
                try:
                    frame = pygame.image.load(file_path).convert_alpha()
                    # Scale if needed
                    if self.scale != 1.0:
                        new_width = int(frame.get_width() * self.scale)
                        new_height = int(frame.get_height() * self.scale)
                        frame = pygame.transform.scale(frame, (new_width, new_height))
                    frames.append(frame)
                except pygame.error as e:
                    print(f"Error loading frame {file_path}: {e}")
                    # Create placeholder
                    placeholder = pygame.Surface((32, 32))
                    placeholder.fill((255, 0, 255))
                    frames.append(placeholder)
            
            if frames:
                duration = animations_config.get(anim_name + '_duration', 0.1)
                loop = animations_config.get(anim_name + '_loop', True)
                self.animations[anim_name] = Animation(frames, duration, loop)
        
        # Current animation state
        self.current_animation = None
        if self.animations:
            self.current_animation = list(self.animations.keys())[0]
    
    def set_animation(self, anim_name):
        """Switch to a different animation"""
        if anim_name in self.animations:
            if anim_name != self.current_animation:
                self.current_animation = anim_name
                self.animations[anim_name].reset()
    
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


def load_animation_from_folder(folder_path, prefix, num_frames, scale=1.0, duration=0.1, loop=True):
    """
    Helper function to load animation from numbered PNG files
    
    Args:
        folder_path: Path to folder containing frames
        prefix: File prefix (e.g., 'hero-idle' for 'hero-idle-1.png')
        num_frames: Number of frames to load
        scale: Scale factor
        duration: Frame duration
        loop: Whether to loop
    """
    frames = []
    for i in range(1, num_frames + 1):
        file_path = os.path.join(folder_path, f"{prefix}-{i}.png")
        try:
            frame = pygame.image.load(file_path).convert_alpha()
            if scale != 1.0:
                new_width = int(frame.get_width() * scale)
                new_height = int(frame.get_height() * scale)
                frame = pygame.transform.scale(frame, (new_width, new_height))
            frames.append(frame)
        except (pygame.error, FileNotFoundError, OSError):
            # Try alternative naming (without dash)
            file_path = os.path.join(folder_path, f"{prefix}{i}.png")
            try:
                frame = pygame.image.load(file_path).convert_alpha()
                if scale != 1.0:
                    new_width = int(frame.get_width() * scale)
                    new_height = int(frame.get_height() * scale)
                    frame = pygame.transform.scale(frame, (new_width, new_height))
                frames.append(frame)
            except (pygame.error, FileNotFoundError, OSError):
                # Create placeholder
                placeholder = pygame.Surface((32, 32))
                placeholder.fill((255, 0, 255))
                frames.append(placeholder)
    
    return Animation(frames, duration, loop) if frames else None

