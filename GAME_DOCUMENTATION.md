# 7KOR Game Documentation

## Game Overview

**7KOR** is a top-down roguelike action game built with Pygame. The player controls a character named "Rostam" who fights various enemies in a grassland environment. The game features a shield blocking system, multiple enemy types with unique behaviors, and a critical hit system.

## Core Gameplay Mechanics

### Player Controls
- **WASD**: Move character
- **Left Click**: Attack (melee, directional towards mouse)
- **Right Click (Hold)**: Block with shield (shield faces mouse direction)
- **G**: Gesture animation
- **1/2/3**: Spawn enemies (Skeleton/Hell Gato/Ghost) near player
- **ESC**: Return to menu or quit

### Coordinate System
- **X-axis**: Left-right (negative = left, positive = right)
- **Y-axis**: Up-down (negative = up, positive = down)
- Camera follows player with isometric-style offset rendering

## Player System

### Player Class (`player.py`)

**Health & Stats:**
- Max Health: 10 HP (configurable in `config.py`)
- Base Speed: 200 pixels/second
- Attack Damage: 2 per hit
- Attack Range: 50 pixels
- Collision Radius: 20 pixels

**Shield Mechanic:**
- Hold right mouse button to raise shield
- Shield direction follows mouse cursor (up/down/left/right)
- Shield blocks damage if facing enemy (within 60-degree cone)
- When blocking:
  - Player takes no damage
  - Player receives knockback (amount depends on enemy)
  - Enemy receives knockback (half of what they normally get when attacked)
- Shield uses `hero-shield` sprite from `Assets/Player/hero-shield`

**Damage System:**
- Takes damage from enemy attacks
- Critical hits: Damage >25% of max health triggers critical hit effects
- Slow debuff: 80% speed reduction for 1.5 seconds after taking damage
- Damage flash: Red tint for 0.2 seconds
- Hurt animation: Plays `hero-hurt` sprite when damaged

**Animations:**
- Idle: 4 frames, loops
- Walk/Run: 6 frames, loops
- Attack: 5 frames, directional (towards mouse)
- Shield: Single frame, directional
- Hurt: Single frame
- Gesture: 4 frames
- Death: 4 frames

**Attack System:**
- Can only attack when attack animation is finished
- Attack hits enemies in a 50-pixel range in the direction of the mouse
- Tracks which enemies were hit in current attack to prevent multi-hits

## Enemy Types

### 1. Skeleton (`skeleton.py`)

**Basic Stats:**
- Speed: 40 pixels/second
- Health: 5 HP
- Damage: 1 per attack
- Collision Radius: 25 pixels
- Shield Knockback: 150 pixels (half of 300)

**Behavior:**
- Simple melee enemy
- Moves towards player
- Attack pattern:
  - 0.5 second attack duration
  - 1.0 second cooldown between attacks
  - Deals damage at end of attack animation
- Starts with "rise" animation (6 frames, 0.3s duration)
- Death animation: 5 frames from `Assets/Effects/enemy-death`

**Attack Mechanics:**
- Must be in collision range to attack
- Attack has cooldown timer system
- Passes `self` to `player.take_damage()` for shield blocking checks

### 2. Hell Gato (`hell_gato.py`)

**Basic Stats:**
- Speed: 80 pixels/second (2x skeleton)
- Health: 5 HP
- Damage: 30% of player's max health per lunge
- Collision Radius: 38.5 pixels (10% larger than base 35)
- Shield Knockback: 300 pixels (100% of 300)

**Attack States:**
1. **Patrol**: Random movement, waits 4 seconds before allowing lock-on
2. **Lock-On**: Targets player, waits 1.0 second (0.7s if enraged)
3. **Lunge**: Dashes at player at high speed
4. **Stunned**: After missed lunge or shield block, 2 seconds

**Lunge System:**
- Lunge damage: 30% of player's max health
- Lunge speed: 3200 base (+800 if enraged)
- Lunge distance bonus: +2 per second following player (max 60 seconds = +120)
- Lunge duration: 0.9 seconds
- If lunge hits:
  - Critical hit (>25% max health): Hell Gato becomes **enraged**
  - Non-critical hit: Returns to patrol normally
- If lunge misses: Stunned for 2 seconds, then patrol with 4-second speed buff
- If blocked by shield: Takes 1 damage, stunned for 2 seconds, breaks enrage, 4-second speed buff

**Enrage System:**
- Triggered when lunge deals critical damage (>25% of player max health)
- Effects:
  - 5x move speed
  - 1.5x lock-on range
  - +800 lunge speed
  - 0.7x lock-on duration (attacks faster)
- Behavior when enraged:
  - Must run away from player until reaching 1.5x lock-on range
  - Then immediately locks on and lunges again
  - No stun after successful lunge (if critical)
  - Remains enraged until:
    - Shield block (breaks enrage)
    - Missed lunge (breaks enrage)
    - Death

**Speed Buff System:**
- After shield stun or missed lunge recovery: 3x speed for 4 seconds
- No lunge speed or lock-on range buffs, just movement speed

**Animations:**
- Walk: 4 frames (frames 1-2 = walk, 3 = lock-on, 4 = lunge)
- Death: 5 frames from `Assets/Effects/enemy-death`
- Rise: 6 frames from `Assets/Effects/hell-gato-rise`
- Sprite is double width (2x) but normal height

**Special Mechanics:**
- Can be stunned by player attacks (breaks stun, goes to patrol)
- Follow timer tracks how long following player (for lunge distance scaling)
- Random direction changes during patrol phase

### 3. Ghost (`ghost.py`)

**Basic Stats:**
- Base Speed: 40 pixels/second (scales multiplicatively)
- Health: 1 HP during spawn, 4 HP after spawn
- Damage: 2 per hit
- Collision Radius: 25 pixels
- **Bypasses Shield**: Ghosts go through shields and deal damage immediately

**Spawning System:**
- Spawn trigger range: 100 pixels from player
- Spawn duration: 1.0 second
- Spawn animation:
  - `ghost-appear` effect plays (6 frames from `Assets/Effects/ghost-appear`)
  - Ghost sprite fades in from 0% to 100% opacity
  - Ghost can move and take damage during spawn
- Health changes:
  - 1 HP during spawn animation
  - 4 HP after spawn completes
- Blue dot indicator shows ghost location before spawning

**Speed Scaling:**
- Speed increases multiplicatively: `1.1^seconds` (1.1x per second)
- Timer starts when spawning begins
- Resets to 0 when spawn completes (but speed continues scaling)

**Behavior:**
- Moves towards player instantly (even during spawn)
- Deals damage immediately on collision (no cooldown)
- Dies immediately after dealing damage
- Can take damage during spawn animation

**Death System:**
- Death animation: 6 frames from `Assets/Effects/ghost-death`
- Death animation plays even if spawn animation hasn't completed
- Spawn appear effect continues playing even after death
- Ghost sprite flips horizontally when facing left (default faces right)

**Animations:**
- Walk/Idle: Same animation, 4 frames from `Assets/Enemy/ghost`
- Death: 6 frames from `Assets/Effects/ghost-death`
- Appear effect: 6 frames from `Assets/Effects/ghost-appear` (separate animation)

## Shield Blocking System

### Blocking Logic (`player.py` - `take_damage` method)

**Blocking Conditions:**
1. Player must be holding right mouse button (`is_blocking == True`)
2. Shield must be facing enemy (within 60-degree cone)
3. Enemy must pass `self` to `player.take_damage()` for shield check

**Blocking Effects:**
- Player takes no damage
- Player receives knockback (enemy-specific amount)
- Enemy receives knockback (half of their normal knockback amount)
- Returns `True` to indicate damage was blocked

**Enemy Shield Knockback Values:**
- Skeleton: 150 pixels (half of 300)
- Hell Gato: 300 pixels (100% of 300)
- Ghost: N/A (bypasses shield)

**Direction Calculation:**
- Uses angle between enemy and player
- Shield direction mapped to angles:
  - Right: 0° (0 radians)
  - Down: 90° (π/2 radians)
  - Left: 180° (π radians)
  - Up: -90° (-π/2 radians)
- Blocking cone: ±60° (π/3 radians) from shield direction

## Critical Hit System

**Definition:**
- Critical hit occurs when damage >25% of player's max health
- For player with 10 max health: critical = damage >2.5

**Effects:**
- Red border flash around screen (1.5 seconds)
- "CRITICAL HIT!" text appears at hit location
- Text floats upward and fades out (2 seconds)
- Triggers Hell Gato enrage if from Hell Gato lunge

## Animation System

### File Structure
- Animations loaded from individual PNG files in folders
- Format: `{name}-{frame_number}.png` (e.g., `hero-idle-1.png`)
- Uses `file_animation.py` for loading

### Animation Classes
- **Animation**: Basic animation class with frame duration and looping
- **FileAnimationManager**: Manages multiple animations for player
- **SimpleAnimationManager**: Custom managers for enemies (Skeleton, Hell Gato, Ghost)

### Animation States
- Animations have `finished` property when non-looping animation completes
- Can check `is_finished()` to determine when to transition states
- Animations can be reset with `reset()` method

## Collision System

### Collision Detection
- Uses circular collision detection with `collision_radius`
- Player collision radius: 20 pixels
- Enemy collision radii vary (Skeleton: 25, Hell Gato: 38.5, Ghost: 25)

### Collision Resolution
- Player-enemy collisions: Player pushes enemies away
- Enemy-enemy collisions: Enemies push each other away
- Uses overlap calculation and directional push

### Attack Collision
- Player attacks use range-based collision (50 pixels)
- Directional: Only hits enemies in attack direction
- Tracks hit enemies to prevent multi-hits per attack

## Damage System

### Player Taking Damage
- `player.take_damage(amount, enemy=None)` method
- Returns `True` if blocked by shield, `False` if damage taken
- Applies slow debuff, damage flash, hurt animation
- Updates health (clamped to 0)

### Enemy Taking Damage
- Each enemy has `take_damage(amount, knockback_x, knockback_y)` method
- Applies knockback velocity
- Updates health
- Triggers death animation when health <= 0

### Knockback System
- Knockback velocity applied on damage
- Decays over time (player: 0.92 per frame, enemies: 0.85 per frame)
- Direction: Away from damage source

## Game State Management

### States
- **"menu"**: Start menu screen
- **"playing"**: Active gameplay

### Game Loop (`game.py`)
1. Handle events (keyboard, mouse)
2. Update game state (player, enemies, camera)
3. Draw everything (world, enemies, player, UI)
4. Remove dead enemies (after death animation)

## File Structure

```
7KOR/
├── game.py              # Main game loop and state management
├── player.py            # Player class with movement, attacks, shield
├── skeleton.py          # Skeleton enemy implementation
├── hell_gato.py         # Hell Gato enemy with lunge/enrage system
├── ghost.py             # Ghost enemy with spawning mechanics
├── enemy.py             # Base enemy class (legacy, not used)
├── config.py            # Game configuration constants
├── camera.py            # Camera system (follows player)
├── world.py             # World/background rendering
├── animation.py         # Animation base classes
├── file_animation.py    # Animation loading from files
├── requirements.txt     # Python dependencies
└── Assets/
    ├── Player/          # Player sprites
    ├── Enemy/           # Enemy sprites
    └── Effects/         # Effect animations (death, rise, appear)
```

## Important Implementation Details

### Shield Direction
- Shield direction updated every frame based on mouse position
- Stored in `player.shield_direction` ("up", "down", "left", "right")
- Used for blocking angle calculation

### Enemy State Machines
- **Skeleton**: Simple (patrol → attack → cooldown)
- **Hell Gato**: Complex (patrol → lock-on → lunge → stunned/patrol, with enrage states)
- **Ghost**: Spawn state machine (underground → spawning → spawned)

### Animation Priority
- Death animations take priority over all other animations
- Shield animation takes priority over walk/idle when blocking
- Attack animation prevents movement

### Enemy Spawning
- Press 1/2/3 to spawn enemies at random positions near player (±200 pixels)
- Enemies spawn with their initial animations (rise for Skeleton/Hell Gato, blue dot for Ghost)

### Coordinate System Notes
- World coordinates: Large world (2000x2000 pixels)
- Screen coordinates: 1280x720 pixels
- Camera converts between world and screen coordinates
- Isometric-style offset applied when drawing sprites

## Configuration Constants (`config.py`)

**Screen:**
- Width: 1280, Height: 720
- FPS: 60

**Player:**
- Speed: 200 pixels/second
- Max Health: 10
- Scale: 2.0x

**Enemy:**
- Scale: 2.0x
- Max Health: 5

**Shield Knockback:**
- Skeleton: 150
- Hell Gato: 300

**Animation Durations:**
- Idle: 0.15s
- Walk: 0.1s
- Attack: 0.08s
- Gesture: 0.2s
- Death: 0.15s
- Hurt: 0.3s

## Common Patterns

### Enemy Update Pattern
```python
def update(self, dt, player_x, player_y, other_enemies, player):
    # Handle death/dying states first
    if self.is_dying:
        # Update death animation
        return
    
    # Update AI/behavior
    # Update movement
    # Update animations
    # Resolve collisions
    # Deal damage to player
```

### Damage Dealing Pattern
```python
# Enemy deals damage to player
blocked = player.take_damage(self.damage, enemy=self)
if blocked:
    # Handle shield block effects
    pass
```

### Animation Management Pattern
```python
# Set animation
if self.animations:
    self.animations.set_animation('walk')
    
# Update animation
if self.animations:
    self.animations.update(dt)
    
# Get current frame
frame = self.animations.get_current_frame() if self.animations else None
```

## Debugging Tips

1. **Shield not blocking**: Ensure enemy passes `self` to `player.take_damage()`
2. **Death animation not playing**: Check `is_dying` flag and animation state
3. **Enemy not moving**: Check if in `is_rising` or `is_dying` state
4. **Collision issues**: Verify collision radius values match sprite sizes
5. **Animation not playing**: Check animation file paths and frame counts

## Future Considerations

- Enemy spawn system could be expanded
- More enemy types could be added following existing patterns
- Shield blocking could have stamina/durability system
- Player could have more abilities/attacks
- World could have more interactive elements

