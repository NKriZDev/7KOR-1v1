"""Hell Gato enemy character"""

import pygame
import os
import random
import math
import config
from file_animation import load_animation_from_folder
from asset_utils import asset_path


class HellGato:
    """Hell Gato enemy with walking animation and rise animation"""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 80  # Double skeleton speed (skeleton is 40)
        self.velocity_x = 0
        self.velocity_y = 0
        
        # Collision settings (larger due to double width)
        self.collision_radius = 38  # Radius for collision detection (increased for larger size, +10% from 35)
        
        # Health system
        self.max_health = config.ENEMY_MAX_HEALTH
        self.health = self.max_health
        self.xp_value = 8
        self.xp_awarded = False
        
        # Damage settings
        self.damage = 1  # Damage dealt to player
        
        # Shield knockback (100% of what hell gato gets knocked back)
        self.shield_knockback = config.HELL_GATO_SHIELD_KNOCKBACK
        
        # Lock-on/Lunge attack system
        self.base_lock_on_range = 300  # Base range to start lock-on
        self.lock_on_range = self.base_lock_on_range  # Current lock-on range (can be buffed)
        self.lock_on_duration = 1.0  # Wait 1 second in lock-on
        self.lunge_duration = 0.9  # Lunge duration (0.6 * 1.5 = 0.9 seconds)
        self.patrol_duration = 4.0  # Run around for 4 seconds after lunge
        self.attack_state = "patrol"  # patrol, lock_on, lunge, stunned
        self.attack_timer = 0.0
        self.patrol_timer = -1.0  # Timer for patrol phase (negative = can lock on immediately)
        self.follow_timer = 0.0  # Track how long following player (for lunge distance scaling)
        self.max_follow_time = 60.0  # Maximum 60 seconds
        self.lunge_distance_bonus = 0.0  # Bonus distance from following (2 per second, max 120)
        self.lock_on_target_x = None
        self.lock_on_target_y = None
        self.lunge_velocity_x = 0
        self.lunge_velocity_y = 0
        self.base_lunge_speed = 3200  # Base speed during lunge
        self.lunge_speed = self.base_lunge_speed  # Current lunge speed (can be buffed)
        self.lunge_damage_dealt = False  # Track if damage was dealt during current lunge
        
        # Stun system
        self.stun_duration = 2.0  # Stunned for 2 seconds after lunge
        self.stun_timer = 0.0
        self.is_stunned = False
        self.stun_broken = False  # Whether player broke the stun
        self.is_shield_stunned = False  # Whether stun was caused by shield block
        
        # Enrage system (when lunge deals critical damage)
        self.is_enraged = False
        self.enrage_speed_multiplier = 5.0  # 5x move speed when enraged
        self.enrage_lock_on_range_multiplier = 1.5  # 1.5x lock-on range when enraged
        self.enrage_lunge_speed_bonus = 800  # +800 lunge speed when enraged
        self.enrage_lock_on_duration_multiplier = 0.7  # 70% of normal lock-on duration (attack faster)
        
        # Speed buff system
        self.speed_buff_active = False
        self.speed_buff_timer = 0.0
        self.speed_buff_duration = 4.0  # 4 seconds of 3x speed
        self.speed_buff_multiplier = 3.0
        
        # Random movement during cooldown
        self.random_direction_angle = random.uniform(0, 2 * math.pi)
        self.random_direction_timer = 0.0
        self.random_direction_change_interval = 0.5  # Change direction every 0.5 seconds
        
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
        
        # Load walking animation from individual PNG files (4 frames)
        # Frames: 1-2 = walk, 3 = lock-on, 4 = lunge
        base_path = asset_path("Assets/Enemy/hell-gato")
        walk_frames = []
        for i in range(1, 5):
            file_path = os.path.join(base_path, f"hell-gato-{i}.png")
            try:
                frame = pygame.image.load(file_path).convert_alpha()
                # Scale: double width, normal height
                original_width, original_height = frame.get_size()
                new_width = int(original_width * config.ENEMY_SCALE * 2)  # Double width
                new_height = int(original_height * config.ENEMY_SCALE)  # Normal height
                frame = pygame.transform.scale(frame, (new_width, new_height))
                walk_frames.append(frame)
            except pygame.error:
                placeholder = pygame.Surface((32 * config.ENEMY_SCALE * 2, 32 * config.ENEMY_SCALE))
                placeholder.fill((200, 100, 100))
                walk_frames.append(placeholder)
        
        # Create walk animation (frames 1-2-3-4 loop)
        from animation import Animation
        walk_anim = Animation(walk_frames[:4], 0.12, loop=True) if len(walk_frames) >= 4 else None
        
        # Store all frames for lock-on and lunge
        self.walk_frames = walk_frames
        
        # Load death animation
        death_base_path = asset_path("Assets/Effects/enemy-death")
        death_anim = load_animation_from_folder(
            death_base_path,
            "enemy-death",
            5,  # 5 frames
            scale=config.ENEMY_SCALE,
            duration=0.15,
            loop=False  # Death animation doesn't loop
        )
        
        # Load rise animation
        rise_base_path = asset_path("Assets/Effects/hell-gato-rise")
        rise_anim = load_animation_from_folder(
            rise_base_path,
            "hell-gato-rise",
            6,  # 6 frames
            scale=config.ENEMY_SCALE,
            duration=0.30,  # Half speed (doubled from 0.15)
            loop=False  # Rise animation doesn't loop
        )
        
        # Create simple animation manager
        class SimpleAnimationManager:
            def __init__(self, walk_animation, death_animation, rise_animation, walk_frames):
                self.animations = {}
                if walk_animation:
                    self.animations['walk'] = walk_animation
                if death_animation:
                    self.animations['death'] = death_animation
                if rise_animation:
                    self.animations['rise'] = rise_animation
                # Start with rise animation if available
                self.current_animation = 'rise' if rise_animation else ('walk' if walk_animation else None)
                self.walk_frames = walk_frames  # Store all frames for lock-on/lunge
            
            def set_animation(self, anim_name):
                if anim_name in self.animations:
                    if self.current_animation != anim_name:
                        self.current_animation = anim_name
                        self.animations[anim_name].reset()
            
            def update(self, dt):
                if self.current_animation and self.current_animation in self.animations:
                    self.animations[self.current_animation].update(dt)
            
            def get_current_frame(self, attack_state=None):
                # Handle special states: stunned, lock-on, and lunge
                if attack_state == "stunned" and len(self.walk_frames) >= 1:
                    return self.walk_frames[0]  # Frame 1 (stunned)
                elif attack_state == "lock_on" and len(self.walk_frames) >= 3:
                    return self.walk_frames[2]  # Frame 3 (lock-on)
                elif attack_state == "lunge" and len(self.walk_frames) >= 4:
                    return self.walk_frames[3]  # Frame 4 (lunge)
                
                # Normal animation (walk uses frames 1-2-3-4)
                if self.current_animation and self.current_animation in self.animations:
                    return self.animations[self.current_animation].get_current_frame()
                return None
            
            def is_finished(self):
                if self.current_animation and self.current_animation in self.animations:
                    return self.animations[self.current_animation].finished
                return False
        
        try:
            self.animations = SimpleAnimationManager(walk_anim, death_anim, rise_anim, walk_frames)
        except Exception as e:
            print(f"Error setting up hell gato animations: {e}")
            self.animations = None
            self.placeholder = pygame.Surface((32 * int(config.ENEMY_SCALE), 32 * int(config.ENEMY_SCALE)))
            self.placeholder.fill((200, 100, 100))  # Reddish placeholder
        
        # Get sprite dimensions for rect
        current_frame = self.animations.get_current_frame(self.attack_state) if self.animations else self.placeholder
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
        """Check if this hell gato collides with another (enemy or player)"""
        dx = other.x - self.x
        dy = other.y - self.y
        distance = (dx**2 + dy**2)**0.5
        min_distance = self.collision_radius + other.collision_radius
        return distance < min_distance and distance > 0
    
    def check_player_collision(self, player):
        """Check if this hell gato collides with player"""
        return self.check_collision(player)
    
    def take_damage(self, amount, knockback_x=0, knockback_y=0):
        """Take damage and apply knockback"""
        if self.is_dead or self.is_dying:
            return
        self.health = max(0, self.health - amount)
        
        # If stunned, break stun and activate speed buff
        if self.is_stunned and self.attack_state == "stunned":
            self.is_stunned = False
            self.stun_broken = True
            self.stun_timer = 0.0
            
            # Both shield stun and normal stun get 4 second speed buff when broken by damage
            self.speed_buff_active = True
            self.speed_buff_timer = 0.0
            self.speed_buff_duration = 4.0
            # Immediately transition to patrol so movement can start
            self.attack_state = "patrol"
            # Reset lock-on range and lunge speed to base values
            self.lock_on_range = self.base_lock_on_range
            self.lunge_speed = self.base_lunge_speed
            # Can lock on after speed buff ends
            self.patrol_timer = -1.0
            
            # Reset shield stun flag
            self.is_shield_stunned = False
        
        # Apply knockback (increased strength)
        knockback_strength = 300  # Pixels per second (increased from 100)
        self.knockback_velocity_x = knockback_x * knockback_strength
        self.knockback_velocity_y = knockback_y * knockback_strength
        
        if self.health <= 0:
            self.is_dying = True
            self.is_rising = False  # Stop rising if dying
            # Stop any attack state when dying
            self.attack_state = "patrol"
            self.lunge_velocity_x = 0
            self.lunge_velocity_y = 0
            # Freeze knockback on death
            self.knockback_velocity_x = 0
            self.knockback_velocity_y = 0
            if self.animations:
                self.animations.set_animation('death')
        return self.health <= 0
    
    def update_attack_state(self, player, dt):
        """Update lock-on/lunge attack state"""
        if self.is_dead or self.is_dying or self.is_rising:
            return False
        
        # Calculate distance to player
        dx = player.x - self.x
        dy = player.y - self.y
        distance = (dx**2 + dy**2)**0.5
        
        if self.attack_state == "patrol":
            # Track follow time for lunge distance scaling (2 per second, max 60 seconds = 120 bonus)
            if distance < 1000:  # Within 1000 pixels (following player)
                self.follow_timer = min(self.follow_timer + dt, self.max_follow_time)
                self.lunge_distance_bonus = self.follow_timer * 2.0  # 2 distance per second
            
            # During patrol phase, wait for 4 seconds before allowing lock-on
            # OR if speed buff is active (after stun break), don't allow lock-on until buff ends
            # If enraged, can lock on immediately when at lock-on range (skip cooldown)
            if not self.is_enraged and (self.patrol_timer > 0 or self.speed_buff_active):
                if self.patrol_timer > 0:
                    self.patrol_timer -= dt
                # Can't lock on during patrol cooldown or speed buff (unless enraged)
                return False
            
            # Check if player is in lock-on range
            if self.is_enraged:
                # When enraged, must run away first until reaching lock-on range (1.5x base)
                effective_lock_on_range = self.base_lock_on_range * self.enrage_lock_on_range_multiplier
                # Only lock on when we've reached the lock-on range (ran away enough)
                # Allow small buffer to prevent jittering
                if distance >= effective_lock_on_range and distance <= effective_lock_on_range + 100:
                    # Reached lock-on range, can lock on now
                    self.attack_state = "lock_on"
                    self.attack_timer = 0.0  # Reset timer for lock-on duration
                    self.lock_on_target_x = player.x
                    self.lock_on_target_y = player.y
                    # Face the player
                    if abs(dy) > abs(dx):
                        self.facing_direction = "down" if dy > 0 else "up"
                    else:
                        self.facing_direction = "right" if dx > 0 else "left"
                    return True  # Indicate lock-on started
                else:
                    # Not at lock-on range yet, keep running (handled in movement code)
                    return False
            else:
                # Normal lock-on check
                effective_lock_on_range = self.lock_on_range + self.lunge_distance_bonus
                if distance <= effective_lock_on_range:
                    # Start lock-on
                    self.attack_state = "lock_on"
                    self.attack_timer = 0.0  # Reset timer for lock-on duration
                    self.lock_on_target_x = player.x
                    self.lock_on_target_y = player.y
                    # Face the player
                    if abs(dy) > abs(dx):
                        self.facing_direction = "down" if dy > 0 else "up"
                    else:
                        self.facing_direction = "right" if dx > 0 else "left"
                    return True  # Indicate lock-on started
        
        elif self.attack_state == "lock_on":
            # Increment timer for lock-on phase
            self.attack_timer += dt
            
            # Face the locked target
            if self.lock_on_target_x and self.lock_on_target_y:
                dx_lock = self.lock_on_target_x - self.x
                dy_lock = self.lock_on_target_y - self.y
                if abs(dy_lock) > abs(dx_lock):
                    self.facing_direction = "down" if dy_lock > 0 else "up"
                else:
                    self.facing_direction = "right" if dx_lock > 0 else "left"
            
            # Calculate lock-on duration (reduced when enraged)
            effective_lock_on_duration = self.lock_on_duration
            if self.is_enraged:
                effective_lock_on_duration = self.lock_on_duration * self.enrage_lock_on_duration_multiplier
            
            # Wait for lock-on duration, then lunge
            if self.attack_timer >= effective_lock_on_duration:
                self.attack_state = "lunge"
                self.attack_timer = 0.0
                self.lunge_damage_dealt = False  # Reset damage flag for new lunge
                # Calculate lunge direction
                if self.lock_on_target_x and self.lock_on_target_y:
                    dx_lunge = self.lock_on_target_x - self.x
                    dy_lunge = self.lock_on_target_y - self.y
                    lunge_dist = (dx_lunge**2 + dy_lunge**2)**0.5
                    if lunge_dist > 0:
                        # Calculate lunge with distance bonus (2 per second following, max 120)
                        effective_lunge_speed = self.lunge_speed * 0.75 + self.lunge_distance_bonus
                        self.lunge_velocity_x = (dx_lunge / lunge_dist) * effective_lunge_speed
                        self.lunge_velocity_y = (dy_lunge / lunge_dist) * effective_lunge_speed
                        # Reset follow timer after lunge
                        self.follow_timer = 0.0
                        self.lunge_distance_bonus = 0.0
        
        elif self.attack_state == "lunge":
            # Increment timer for lunge phase
            self.attack_timer += dt
            
            # Decay lunge velocity
            self.lunge_velocity_x *= 0.92
            self.lunge_velocity_y *= 0.92
            
            # Check if hit player during lunge (only once per lunge)
            if not self.lunge_damage_dealt and self.check_player_collision(player):
                # Calculate damage: 30% of player's max health
                import config
                lunge_damage = int(player.max_health * 0.3)
                blocked = player.take_damage(lunge_damage, enemy=self)  # Deal damage (pass self for shield blocking)
                self.lunge_damage_dealt = True
                
                # If blocked by shield, hell gato falls down and gets stunned (works whether enraged or not)
                if blocked:
                    # Take 1 damage
                    self.health = max(0, self.health - 1)
                    
                    # Shield block breaks enrage
                    self.is_enraged = False
                    # Reset to normal values
                    self.lock_on_range = self.base_lock_on_range
                    self.lunge_speed = self.base_lunge_speed
                    
                    # Instantly go to stunned state (mark as shield stun)
                    self.attack_state = "stunned"
                    self.attack_timer = 0.0
                    self.stun_timer = 0.0
                    self.is_stunned = True
                    self.stun_broken = False
                    self.is_shield_stunned = True  # Mark as shield stun
                    
                    # Stop lunge movement immediately
                    self.lunge_velocity_x = 0
                    self.lunge_velocity_y = 0
                    
                    # If health reaches 0, trigger death
                    if self.health <= 0:
                        self.is_dying = True
                        self.is_rising = False
                        # Stop attack state when dying
                        self.attack_state = "patrol"
                        if self.animations:
                            self.animations.set_animation('death')
                    else:
                        # Use stunned animation (frame 1)
                        if self.animations:
                            self.animations.set_animation('walk')  # Will use frame 1 based on attack_state
                    
                    # Skip normal lunge end logic
                    return
                else:
                    # Check if damage was critical (>25% of max health)
                    damage_percentage = (lunge_damage / player.max_health) * 100
                    if damage_percentage > 25:
                        # Critical hit - hell gato goes enraged
                        self.is_enraged = True
                        # Apply enrage buffs: increased lock-on range and lunge speed
                        self.lock_on_range = self.base_lock_on_range * self.enrage_lock_on_range_multiplier
                        self.lunge_speed = self.base_lunge_speed + self.enrage_lunge_speed_bonus
                        # Don't get stunned after this lunge, go to patrol and run away
                        # Set patrol timer to prevent immediate lock-on (must run away first)
                        self.attack_state = "patrol"
                        self.attack_timer = 0.0
                        self.patrol_timer = 0.1  # Small delay to ensure movement happens first
                        # Stop lunge movement
                        self.lunge_velocity_x = 0
                        self.lunge_velocity_y = 0
                        # Skip stun, go directly to patrol
                        return
            
            # After lunge duration, check if lunge missed (didn't hit player)
            if self.attack_timer >= self.lunge_duration:
                # Lunge missed - get stunned (like shield block but no health loss)
                # This breaks enrage
                self.is_enraged = False
                # Reset to normal values
                self.lock_on_range = self.base_lock_on_range
                self.lunge_speed = self.base_lunge_speed
                self.attack_state = "stunned"
                self.attack_timer = 0.0
                self.stun_timer = 0.0
                self.is_stunned = True
                self.stun_broken = False
                self.is_shield_stunned = False  # Normal lunge stun (miss), not from shield
                # Stop lunge movement
                self.lunge_velocity_x = 0
                self.lunge_velocity_y = 0
        
        elif self.attack_state == "stunned":
            # Check if stun was broken by player (handled in take_damage)
            # If broken, state should already be changed to patrol in take_damage
            if self.stun_broken:
                # Ensure state is patrol (in case take_damage didn't complete the transition)
                if self.attack_state == "stunned":
                    self.attack_state = "patrol"
                    self.is_stunned = False
                return False
            
            # Increment stun timer
            self.stun_timer += dt
            
            if self.stun_timer >= self.stun_duration:
                # Stun completed without being broken
                if self.is_shield_stunned:
                    # Shield stun recovery: go to patrol with 4 second speed buff
                    self.speed_buff_active = True
                    self.speed_buff_timer = 0.0
                    self.speed_buff_duration = 4.0
                    self.attack_state = "patrol"
                    self.is_stunned = False
                    # Reset lock-on range and lunge speed to base values
                    self.lock_on_range = self.base_lock_on_range
                    self.lunge_speed = self.base_lunge_speed
                    # Can lock on after speed buff ends
                    self.patrol_timer = -1.0
                else:
                    # Normal lunge stun recovery: 4 second speed boost, no lunge buffs
                    self.attack_state = "patrol"
                    self.is_stunned = False
                    # 4 second speed boost
                    self.speed_buff_active = True
                    self.speed_buff_timer = 0.0
                    self.speed_buff_duration = 4.0
                    # Still need to wait for patrol cooldown (4 seconds) before next lock-on
                    self.patrol_timer = self.patrol_duration
                    # Reset lock-on range and lunge speed to base values (no buffs)
                    self.lock_on_range = self.base_lock_on_range
                    self.lunge_speed = self.base_lunge_speed
                
                # Reset stun flags for next lunge
                self.stun_broken = False
                self.is_shield_stunned = False
        
        return False
    
    def resolve_collision(self, other):
        """Push this hell gato away from another enemy"""
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
            
            # Push this hell gato away
            self.x -= push_x
            self.y -= push_y
    
    def update(self, dt, target_x=None, target_y=None, other_enemies=None, player=None):
        """Update hell gato position and animations"""
        # Handle rise animation
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
        
        # Check if death animation finished
        if self.is_dying:
            # Stop movement while dying
            self.velocity_x = 0
            self.velocity_y = 0
            self.lunge_velocity_x = 0
            self.lunge_velocity_y = 0
            self.knockback_velocity_x = 0
            self.knockback_velocity_y = 0
            # Update death animation (don't use attack_state for death animation)
            if self.animations:
                # Ensure death animation is set
                if self.animations.current_animation != 'death':
                    self.animations.set_animation('death')
                self.animations.update(dt)
                if self.animations.is_finished():
                    self.is_dead = True
            # Update rect (don't pass attack_state when dying - use death animation)
            current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
            if current_frame:
                self.rect = current_frame.get_rect()
                self.rect.center = (self.x, self.y)
            return
        
        # Don't update if dead
        if self.is_dead:
            return
        
        # Update speed buff
        if self.speed_buff_active:
            self.speed_buff_timer += dt
            if self.speed_buff_timer >= self.speed_buff_duration:
                # Speed buff ended, reset to normal speed and allow lock-on
                self.speed_buff_active = False
                self.speed_buff_timer = 0.0
                # Reset lock-on range and lunge speed to base values (unless enraged)
                if not self.is_enraged:
                    self.lock_on_range = self.base_lock_on_range
                    self.lunge_speed = self.base_lunge_speed
                # Can lock on now
                self.patrol_timer = -1.0
        
        # Update lock-on/lunge attack (BEFORE movement calculation so state changes apply immediately)
        if player:
            self.update_attack_state(player, dt)
        
        # Calculate effective speed (with buff and enrage)
        if self.is_enraged:
            effective_speed = self.speed * self.enrage_speed_multiplier  # 5x speed when enraged
        elif self.speed_buff_active:
            effective_speed = self.speed * self.speed_buff_multiplier
        else:
            effective_speed = self.speed
        
        # Simple AI: move toward player or circle around during cooldown
        # Also check if speed buff is active (after stun break) - should move even if state check fails
        if (self.attack_state == "patrol" or self.speed_buff_active) and target_x is not None and target_y is not None:
            dx = target_x - self.x
            dy = target_y - self.y
            distance = (dx**2 + dy**2)**0.5
            
            # If enraged, run away until reaching lock-on range (1.5x base)
            if self.is_enraged:
                # Calculate effective lock-on range (1.5x when enraged)
                effective_lock_on_range = self.base_lock_on_range * self.enrage_lock_on_range_multiplier
                if distance < effective_lock_on_range:
                    # Still too close, run away from player
                    if distance > 0:
                        self.velocity_x = (-dx / distance) * effective_speed
                        self.velocity_y = (-dy / distance) * effective_speed
                        self.is_moving = True
                    else:
                        self.velocity_x = 0
                        self.velocity_y = 0
                        self.is_moving = False
                else:
                    # Reached lock-on range, stop moving (will lock on in next update)
                    self.velocity_x = 0
                    self.velocity_y = 0
                    self.is_moving = False
            # If in cooldown (patrol_timer > 0), move in random pattern
            elif self.patrol_timer > 0:
                # Update random direction periodically
                self.random_direction_timer += dt
                if self.random_direction_timer >= self.random_direction_change_interval:
                    self.random_direction_angle = random.uniform(0, 2 * math.pi)
                    self.random_direction_timer = 0.0
                
                # Move in random direction (use effective speed)
                self.velocity_x = math.cos(self.random_direction_angle) * effective_speed
                self.velocity_y = math.sin(self.random_direction_angle) * effective_speed
                self.is_moving = True
            # If speed buff is active (after stun break), move in random patterns around the lock-on range
            elif self.speed_buff_active:
                # Update random direction periodically
                self.random_direction_timer += dt
                if self.random_direction_timer >= self.random_direction_change_interval:
                    self.random_direction_angle = random.uniform(0, 2 * math.pi)
                    self.random_direction_timer = 0.0
                
                # Move in random direction, but try to stay around the lock-on range
                # If too far, bias movement toward player; if too close, bias movement away
                random_vel_x = math.cos(self.random_direction_angle) * effective_speed
                random_vel_y = math.sin(self.random_direction_angle) * effective_speed
                
                if distance > self.lock_on_range + 50:  # Too far, bias toward player
                    bias_strength = 0.3
                    self.velocity_x = random_vel_x * (1 - bias_strength) + (dx / distance) * effective_speed * bias_strength
                    self.velocity_y = random_vel_y * (1 - bias_strength) + (dy / distance) * effective_speed * bias_strength
                elif distance < self.lock_on_range - 50:  # Too close, bias away from player
                    bias_strength = 0.3
                    self.velocity_x = random_vel_x * (1 - bias_strength) - (dx / distance) * effective_speed * bias_strength
                    self.velocity_y = random_vel_y * (1 - bias_strength) - (dy / distance) * effective_speed * bias_strength
                else:  # Good range, pure random movement
                    self.velocity_x = random_vel_x
                    self.velocity_y = random_vel_y
                self.is_moving = True
            # If enraged, run away from player
            elif self.is_enraged:
                # Run away from player
                if distance > 0:
                    self.velocity_x = (-dx / distance) * effective_speed
                    self.velocity_y = (-dy / distance) * effective_speed
                    self.is_moving = True
                else:
                    self.velocity_x = 0
                    self.velocity_y = 0
                    self.is_moving = False
            else:
                # Move directly toward player (when can lock on)
                if distance > 30:
                    self.velocity_x = (dx / distance) * effective_speed
                    self.velocity_y = (dy / distance) * effective_speed
                    self.is_moving = True
                else:
                    self.velocity_x = 0
                    self.velocity_y = 0
                    self.is_moving = False
        elif self.attack_state == "stunned":
            # Don't move during stun
            self.velocity_x = 0
            self.velocity_y = 0
            self.is_moving = False
        elif self.attack_state != "lunge":  # Don't move during lock-on or lunge
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
        
        # Update position (movement + knockback, but lunge handles its own movement)
        if self.attack_state == "lunge":
            # During lunge, apply lunge movement + knockback
            self.x += (self.lunge_velocity_x + self.knockback_velocity_x) * dt
            self.y += (self.lunge_velocity_y + self.knockback_velocity_y) * dt
        else:
            # Normal movement + knockback
            self.x += (self.velocity_x + self.knockback_velocity_x) * dt
            self.y += (self.velocity_y + self.knockback_velocity_y) * dt
        
        # Handle collisions with other enemies (only if not being knocked back much)
        if other_enemies and abs(self.knockback_velocity_x) < 10 and abs(self.knockback_velocity_y) < 10:
            for other in other_enemies:
                if other != self and not other.is_dying and not other.is_dead and self.check_collision(other):
                    self.resolve_collision(other)
        
        # Update rect
        current_frame = self.animations.get_current_frame() if self.animations else self.placeholder
        if current_frame:
            self.rect = current_frame.get_rect()
            self.rect.center = (self.x, self.y)
    
    def draw(self, screen, camera):
        """Draw hell gato with isometric offset"""
        # Don't draw if dead (after death animation finished)
        if self.is_dead:
            return
        
        screen_x, screen_y = camera.apply(self.x, self.y)
        
        # Get current animation frame (pass attack_state for special frames)
        if self.animations:
            current_frame = self.animations.get_current_frame(self.attack_state)
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
        """Draw a small health bar above the hell gato"""
        bar_width = 50
        bar_height = 6
        offset_y = sprite_height // 2 + 14
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
