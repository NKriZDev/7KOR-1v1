"""Camera system for isometric view"""

import config


class Camera:
    """Isometric-style camera that follows the player"""
    
    def __init__(self):
        self.x = 0
        self.y = 0
        self.zoom = 1.0
        
    def update(self, target_x, target_y):
        """Update camera position to follow target"""
        # Smooth camera following (Hades-style)
        self.x += (target_x - self.x) * 0.1
        self.y += (target_y - self.y) * 0.1
        
    def apply(self, x, y):
        """Apply camera transform with isometric offset"""
        screen_x = x - self.x + config.SCREEN_WIDTH // 2
        screen_y = y - self.y + config.SCREEN_HEIGHT // 2
        return screen_x, screen_y
    
    def screen_to_world(self, screen_x, screen_y):
        """Convert screen coordinates to world coordinates"""
        world_x = screen_x - config.SCREEN_WIDTH // 2 + self.x
        world_y = screen_y - config.SCREEN_HEIGHT // 2 + self.y
        return world_x, world_y

