"""World rendering and tile generation"""

import pygame
import random
import config


class GrasslandTile:
    """Generates pixel art grassland tiles"""
    
    def __init__(self, size=64):
        self.size = size
        self.tiles = {}
        self.generate_tiles()
        
    def generate_tiles(self):
        """Generate variety of grassland tiles"""
        # Base grass colors
        base_colors = [
            config.GREEN_DARK, 
            config.GREEN_MEDIUM, 
            config.GREEN_LIGHT, 
            config.YELLOW_GREEN
        ]
        
        for i in range(4):
            tile = pygame.Surface((self.size, self.size))
            base_color = base_colors[i]
            
            # Fill with base color
            tile.fill(base_color)
            
            # Add texture with darker/lighter pixels
            for x in range(self.size):
                for y in range(self.size):
                    if random.random() < 0.3:  # 30% chance for variation
                        variation = random.choice([-20, -10, 10, 20])
                        r = max(0, min(255, base_color[0] + variation))
                        g = max(0, min(255, base_color[1] + variation))
                        b = max(0, min(255, base_color[2] + variation))
                        tile.set_at((x, y), (r, g, b))
            
            # Add occasional grass blades (darker vertical lines)
            for _ in range(random.randint(2, 5)):
                blade_x = random.randint(0, self.size - 1)
                blade_y = random.randint(0, self.size - 1)
                blade_height = random.randint(2, 4)
                for j in range(blade_height):
                    if blade_y + j < self.size:
                        darker = tuple(max(0, c - 30) for c in base_color)
                        tile.set_at((blade_x, blade_y + j), darker)
            
            self.tiles[i] = tile
    
    def get_tile(self, x, y):
        """Get a tile based on position (for consistent tiling)"""
        tile_index = (x + y * 7) % 4
        return self.tiles[tile_index]
    
    def draw(self, screen, camera):
        """Draw grassland tiles with isometric perspective"""
        tile_size = self.size
        
        # Calculate visible tile range
        start_x = int((camera.x - config.SCREEN_WIDTH // 2) // tile_size) - 1
        end_x = int((camera.x + config.SCREEN_WIDTH // 2) // tile_size) + 2
        start_y = int((camera.y - config.SCREEN_HEIGHT // 2) // tile_size) - 1
        end_y = int((camera.y + config.SCREEN_HEIGHT // 2) // tile_size) + 2
        
        # Draw tiles with isometric offset
        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = self.get_tile(x, y)
                world_x = x * tile_size
                world_y = y * tile_size
                
                # Apply isometric projection (Hades-style angled view)
                screen_x, screen_y = camera.apply(world_x, world_y)
                # Use fixed isometric offset based on world position, not relative position
                # This prevents wobbling as camera moves
                iso_offset_x = (world_y / tile_size) * 0.3  # Subtle depth offset
                iso_offset_y = (world_x / tile_size) * 0.2
                
                screen.blit(tile, (screen_x + iso_offset_x, screen_y + iso_offset_y))

