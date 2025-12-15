"""Game configuration and constants"""

# Screen settings
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Colors
GREEN_DARK = (34, 139, 34)
GREEN_MEDIUM = (50, 205, 50)
GREEN_LIGHT = (144, 238, 144)
BROWN = (139, 69, 19)
YELLOW_GREEN = (154, 205, 50)
SKY_BLUE = (135, 206, 235)

# Player settings
PLAYER_SPEED = 200  # pixels per second
PLAYER_SPRITE_PATH = "Assets/Player/Rostam_Animations.png"
PLAYER_FRAME_WIDTH = 32
PLAYER_FRAME_HEIGHT = 32
PLAYER_SCALE = 2.0

# Animation settings
ANIMATION_DURATIONS = {
    'idle': 0.15,
    'gesture': 0.2,
    'walk': 0.1,
    'attack': 0.08,
    'death': 0.15,
}

# Enemy settings
ENEMY_SPRITE_PATH = "Assets/Enemy/minotaurus_wild.png"
ENEMY_FRAME_WIDTH = 32
ENEMY_FRAME_HEIGHT = 32
ENEMY_SCALE = 2.0

# Health settings
PLAYER_MAX_HEALTH = 10
ENEMY_MAX_HEALTH = 5

# Shield settings
SKELETON_SHIELD_KNOCKBACK = 150  # Knockback to player when blocking skeleton (half of 300)
HELL_GATO_SHIELD_KNOCKBACK = 300  # Knockback to player when blocking hell gato (100% of 300)

# World settings
WORLD_WIDTH = 2000
WORLD_HEIGHT = 2000
GRASSLAND_TILE_SIZE = 64

