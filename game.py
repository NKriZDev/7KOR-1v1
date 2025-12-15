"""Main game loop and initialization"""

import pygame
import json
import socket
import sys
import config
from camera import Camera
from world import GrasslandTile
from rogue_warrior import RogueWarrior
from mage import Mage
from projectile import Projectile
from mage_client import run_mage_client


class Game:
    """Main game class"""
    
    def __init__(self):
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption("Roguelike Game - Rostam")
        self.clock = pygame.time.Clock()
        self.running = True
        self.game_state = "menu"  # "menu" or "playing"
        
        # Create game objects
        self.camera = Camera()
        self.grassland = GrasslandTile(size=config.GRASSLAND_TILE_SIZE)
        self.players = []
        self.player1 = None
        self.player2 = None
        self.last_winner = None
        self.projectiles = []
        self.remote_input = None
        self.remote_addr = None
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", 50007))
        self.udp_socket.setblocking(False)
        self.state_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.state_socket.bind(("", 50008))
        self.state_socket.setblocking(False)
        self.state_targets = set()
        # Input tracking per player
        self.input_state = {
            "p1": {"attack": False, "block": False},
            "p2": {"attack": False, "block": False},
        }
        self.reset_game()
    
    def reset_game(self):
        """Reset game state for a fresh 1v1 round."""
        p1_controls = None  # Default WASD + mouse
        p2_controls = {
            "up": pygame.K_UP,
            "down": pygame.K_DOWN,
            "left": pygame.K_LEFT,
            "right": pygame.K_RIGHT,
            "dash": pygame.K_RSHIFT,
            "gesture": pygame.K_SLASH,
            "attack": "key_attack",
            "block": "key_block",
        }
        self.player1 = RogueWarrior(-200, 0, controls=p1_controls)
        self.player2 = Mage(200, 0, controls=p2_controls)
        self.players = [self.player1, self.player2]
        self.projectiles = []
        self.input_state["p1"]["attack"] = False
        self.input_state["p1"]["block"] = False
        self.input_state["p2"]["attack"] = False
        self.input_state["p2"]["block"] = False
        
    def handle_events(self):
        """Handle pygame events"""
        # Reset per-frame attack clicks
        self.input_state["p1"]["attack"] = False
        self.input_state["p2"]["attack"] = False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.game_state == "playing":
                        self.game_state = "menu"
                    else:
                        self.running = False
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    if self.game_state == "menu":
                        self.game_state = "playing"
                        self.reset_game()
                if self.game_state == "playing":
                    if event.key in (pygame.K_RCTRL, pygame.K_LCTRL, pygame.K_KP0):
                        self.input_state["p2"]["attack"] = True
                    if event.key == pygame.K_RSHIFT:
                        self.input_state["p2"]["block"] = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_RSHIFT:
                    self.input_state["p2"]["block"] = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button for P1 attack
                    self.input_state["p1"]["attack"] = True
                if event.button == 3:  # Right mouse for P1 block
                    self.input_state["p1"]["block"] = True
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    self.input_state["p1"]["block"] = False
    
    def update(self, dt):
        """Update game state"""
        if self.game_state != "playing":
            return
        
        self.poll_remote_input()
        self.poll_state_clients()
        
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        self.input_state["p1"]["block"] = mouse_buttons[2]
        mouse_screen_x, mouse_screen_y = pygame.mouse.get_pos()
        mouse_world_x, mouse_world_y = self.camera.screen_to_world(mouse_screen_x, mouse_screen_y)
        p2_direct = self.remote_input if self.remote_input else None
        if self.remote_input:
            self.input_state["p2"]["attack"] = self.remote_input.get("attack", False)
            self.input_state["p2"]["block"] = self.remote_input.get("block", False)
        
        # Update players
        spawned1 = self.player1.update(dt, keys, self.input_state["p1"]["attack"], (mouse_world_x, mouse_world_y), self.input_state["p1"]["block"])
        spawned2 = self.player2.update(dt, keys, self.input_state["p2"]["attack"], None, self.input_state["p2"]["block"], direct_input=p2_direct)
        self.projectiles.extend(spawned1)
        self.projectiles.extend(spawned2)
        # Reset one-shot attack flags
        self.input_state["p1"]["attack"] = False
        self.input_state["p2"]["attack"] = False
        
        # Camera follows the midpoint between players
        avg_x = sum(p.x for p in self.players) / len(self.players)
        avg_y = sum(p.y for p in self.players) / len(self.players)
        self.camera.update(avg_x, avg_y)
        
        # Resolve collisions between players
        if self.player1.check_collision(self.player2):
            self.player1.resolve_collision(self.player2)
            self.player2.resolve_collision(self.player1)
        
        # Apply damage if attacks connect
        self.player1.attack_enemies([self.player2])
        self.player2.attack_enemies([self.player1])

        # Update projectiles and check collisions
        for proj in list(self.projectiles):
            proj.update(dt)
            for player in self.players:
                if player is proj.owner:
                    continue
                if proj.check_collision(player):
                    player.take_damage(proj.damage, enemy=proj.owner, knockback_x=proj.dir_x, knockback_y=proj.dir_y)
                    proj.alive = False
                    break
            if not proj.alive:
                self.projectiles.remove(proj)
        
        # Determine winner
        winner = None
        if self.player1.is_dead or self.player1.health <= 0:
            winner = self.player2
        elif self.player2.is_dead or self.player2.health <= 0:
            winner = self.player1
        if winner:
            self.last_winner = winner.name
            self.game_state = "menu"
        
        self.broadcast_state()
    
    def draw(self):
        """Draw everything"""
        # Clear screen
        self.screen.fill(config.SKY_BLUE)
        
        if self.game_state == "menu":
            self.draw_menu()
        else:
            self.draw_game()
        
        pygame.display.flip()
    
    def draw_menu(self):
        """Draw start menu"""
        # Title
        title_font = pygame.font.Font(None, 72)
        title_text = title_font.render("7KOR - 1v1 Duel", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 - 100))
        self.screen.blit(title_text, title_rect)
        
        # Instructions
        font = pygame.font.Font(None, 36)
        start_text = font.render("Press SPACE or ENTER to Start", True, (200, 200, 200))
        start_rect = start_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2))
        self.screen.blit(start_text, start_rect)
        
        esc_text = font.render("Press ESC to Quit", True, (200, 200, 200))
        esc_rect = esc_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 50))
        self.screen.blit(esc_text, esc_rect)
        
        if self.last_winner:
            win_text = font.render(f"Last winner: {self.last_winner}", True, (220, 220, 80))
            win_rect = win_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 110))
            self.screen.blit(win_text, win_rect)
    
    def draw_game(self):
        """Draw game screen"""
        # Draw grassland
        self.grassland.draw(self.screen, self.camera)

        # Draw projectiles
        for proj in self.projectiles:
            proj.draw(self.screen, self.camera)
        
        # Draw players
        for player in self.players:
            player.draw(self.screen, self.camera)
        for player in self.players:
            player.draw_critical_effects(self.screen, self.camera)
        
        # Draw UI info
        font = pygame.font.Font(None, 24)
        info_lines_left = [
            "P1 (Rogue): WASD to move",
            "Mouse Left to attack, Right to block",
            "Space to dash, G to emote",
        ]
        for i, line in enumerate(info_lines_left):
            info_text = font.render(line, True, (255, 255, 255))
            self.screen.blit(info_text, (10, 20 + i * 22))
        
        info_lines_right = [
            "P2 (Mage): Arrow keys to move",
            "Right Ctrl to shoot, Right Shift to dash",
            "Slash to emote (no shield; uses projectiles)",
        ]
        for i, line in enumerate(info_lines_right):
            info_text = font.render(line, True, (255, 255, 255))
            self.screen.blit(info_text, (config.SCREEN_WIDTH - info_text.get_width() - 10, 20 + i * 22))
        
        # Health bars
        self.draw_player_ui(self.player1, 10, config.SCREEN_HEIGHT - 70)
        self.draw_player_ui(self.player2, config.SCREEN_WIDTH - 210, config.SCREEN_HEIGHT - 70)
        if self.remote_input:
            font = pygame.font.Font(None, 24)
            info_text = font.render("Remote mage connected", True, (120, 220, 120))
            self.screen.blit(info_text, (config.SCREEN_WIDTH // 2 - info_text.get_width() // 2, 10))
    
    def draw_player_ui(self, player, bar_x, bar_y):
        """Draw a simple health bar for a player at a given screen position."""
        bar_width = 200
        bar_height = 18
        pygame.draw.rect(self.screen, (60, 0, 0), (bar_x, bar_y, bar_width, bar_height))
        health_ratio = max(0, min(1, player.health / player.max_health))
        fill_width = int(bar_width * health_ratio)
        if fill_width > 0:
            pygame.draw.rect(self.screen, player.ui_color, (bar_x, bar_y, fill_width, bar_height))
        pygame.draw.rect(self.screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 2)
        font = pygame.font.Font(None, 22)
        label = font.render(f"{player.name}  {int(player.health)}/{int(player.max_health)}", True, (230, 230, 230))
        self.screen.blit(label, (bar_x, bar_y - 22))

    def poll_remote_input(self):
        """Receive remote mage input via UDP (localhost LAN)."""
        if not self.udp_socket:
            return
        try:
            data, addr = self.udp_socket.recvfrom(2048)
            payload = json.loads(data.decode("utf-8"))
            self.remote_input = payload
            self.remote_addr = addr
        except BlockingIOError:
            pass

    def poll_state_clients(self):
        """Register spectators requesting state sync."""
        if not self.state_socket:
            return
        while True:
            try:
                data, addr = self.state_socket.recvfrom(512)
                if data:
                    self.state_targets.add(addr)
            except BlockingIOError:
                break

    def broadcast_state(self):
        """Send lightweight game state to connected clients."""
        if not self.state_targets:
            return
        state = {
            "game_state": self.game_state,
            "last_winner": self.last_winner,
            "camera": {"x": self.camera.x, "y": self.camera.y},
            "players": [
                {
                    "name": p.name,
                    "x": p.x,
                    "y": p.y,
                    "health": p.health,
                    "max_health": p.max_health,
                    "facing": p.facing_direction,
                    "is_attacking": p.is_attacking,
                    "is_blocking": p.is_blocking,
                    "is_gesturing": p.is_gesturing,
                    "is_moving": p.is_moving,
                    "ui_color": p.ui_color,
                }
                for p in self.players
            ],
            "projectiles": [
                {
                    "x": proj.x,
                    "y": proj.y,
                    "dir_x": proj.dir_x,
                    "dir_y": proj.dir_y,
                    "owner": proj.owner.name if proj.owner else "",
                }
                for proj in self.projectiles
            ],
        }
        payload = json.dumps(state).encode("utf-8")
        for addr in list(self.state_targets):
            try:
                self.state_socket.sendto(payload, addr)
            except OSError:
                self.state_targets.discard(addr)

    
    def run(self):
        """Main game loop"""
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0  # Delta time in seconds
            
            self.handle_events()
            self.update(dt)
            self.draw()
        
        pygame.quit()


if __name__ == "__main__":
    pygame.init()
    if "--join-mage" in sys.argv:
        idx = sys.argv.index("--join-mage")
        host = "127.0.0.1"
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]
        run_mage_client(host)
    elif "--client" in sys.argv:
        idx = sys.argv.index("--client")
        host = "127.0.0.1"
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]
        from spectator_client import run_spectator
        run_spectator(host)
    else:
        game = Game()
        game.run()
