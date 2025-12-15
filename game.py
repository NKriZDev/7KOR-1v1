"""Main game loop and initialization"""

import pygame
import json
import socket
import sys
import requests
from pathlib import Path
import config
from camera import Camera
from world import GrasslandTile
from rogue_warrior import RogueWarrior
from mage import Mage
from projectile import Projectile
from mage_client import run_mage_client


def _load_version():
    try:
        return Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except Exception:
        return "0.0.0"


GAME_VERSION = _load_version()


class Game:
    """Main game class"""
    
    def __init__(self):
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption(f"Roguelike Game - Rostam v{GAME_VERSION}")
        self.clock = pygame.time.Clock()
        self.running = True
        self.game_state = "menu"  # "menu", "host_select", "join_menu", "playing"
        
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
        self.host_choice = "rogue"  # or "mage"
        self.join_ip_input = "195.248.240.117"
        self.lobby_server_url = "http://195.248.240.117:3000"
        self.advertised_ip_input = "195.248.240.117"
        self.join_online_code_input = ""
        self.host_online_status = ""
        self.join_online_status = ""
        self.host_online_field = "ip"  # "ip" or "server"
        self.join_online_field = "code"  # "code" or "server"
        self.current_lobby_id = None
        self.using_relay = False
        self.relay_host = None
        self.relay_control_port = 40007
        self.relay_state_port = 40008
        self.relay_keepalive_timer = 0.0
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
        if self.host_choice == "rogue":
            self.player1 = RogueWarrior(-200, 0, controls=p1_controls)
            self.player2 = Mage(200, 0, controls=p2_controls)
        else:
            self.player1 = Mage(-200, 0, controls=p1_controls)
            self.player2 = RogueWarrior(200, 0, controls=p2_controls)
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
                    if self.game_state == "menu":
                        self.running = False
                    else:
                        self.game_state = "menu"
                elif self.game_state == "menu":
                    if event.key == pygame.K_h:
                        self.game_state = "host_select"
                        self.using_relay = False
                        self.current_lobby_id = None
                    elif event.key == pygame.K_j:
                        self.game_state = "join_menu"
                        self.using_relay = False
                        self.current_lobby_id = None
                    elif event.key == pygame.K_o:
                        self.game_state = "host_online"
                        self.host_online_status = ""
                        self.host_online_field = "ip"
                        self.current_lobby_id = None
                    elif event.key == pygame.K_p:
                        self.game_state = "join_online"
                        self.join_online_status = ""
                        self.join_online_field = "code"
                        self.current_lobby_id = None
                elif self.game_state == "host_select":
                    if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                        self.host_choice = "mage" if self.host_choice == "rogue" else "rogue"
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.game_state = "playing"
                        self.current_lobby_id = None
                        self.reset_game()
                elif self.game_state == "join_menu":
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        run_join_client(self.join_ip_input)
                    elif event.key == pygame.K_BACKSPACE:
                        self.join_ip_input = self.join_ip_input[:-1]
                    else:
                        ch = event.unicode
                        if ch.isdigit() or ch == ".":
                            self.join_ip_input += ch
                elif self.game_state == "host_online":
                    if event.key == pygame.K_BACKSPACE:
                        if self.host_online_field == "ip":
                            self.advertised_ip_input = self.advertised_ip_input[:-1]
                        else:
                            self.lobby_server_url = self.lobby_server_url[:-1]
                    elif event.key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
                        self.host_online_field = "server" if self.host_online_field == "ip" else "ip"
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        self.host_choice = "mage" if self.host_choice == "rogue" else "rogue"
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.create_online_lobby()
                    else:
                        ch = event.unicode
                        if ch and ch.isprintable():
                            if self.host_online_field == "ip":
                                self.advertised_ip_input += ch
                            else:
                                self.lobby_server_url += ch
                elif self.game_state == "join_online":
                    if event.key == pygame.K_BACKSPACE:
                        if self.join_online_field == "code":
                            self.join_online_code_input = self.join_online_code_input[:-1]
                        else:
                            self.lobby_server_url = self.lobby_server_url[:-1]
                    elif event.key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
                        self.join_online_field = "server" if self.join_online_field == "code" else "code"
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.join_online_lobby()
                    else:
                        ch = event.unicode
                        if ch and ch.isprintable():
                            if self.join_online_field == "code":
                                self.join_online_code_input += ch
                            else:
                                self.lobby_server_url += ch
                elif self.game_state == "playing":
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
        if self.using_relay and self.current_lobby_id:
            self.tick_relay(dt)
        
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
        p2_mouse_world = None
        if self.remote_input and "mouse_x" in self.remote_input and "mouse_y" in self.remote_input:
            mx = self.remote_input.get("mouse_x", config.SCREEN_WIDTH // 2)
            my = self.remote_input.get("mouse_y", config.SCREEN_HEIGHT // 2)
            p2_mouse_world = self.camera.screen_to_world(mx, my)
        
        # Update players
        spawned1 = self.player1.update(dt, keys, self.input_state["p1"]["attack"], (mouse_world_x, mouse_world_y), self.input_state["p1"]["block"])
        spawned2 = self.player2.update(
            dt,
            keys,
            self.input_state["p2"]["attack"],
            p2_mouse_world,
            self.input_state["p2"]["block"],
            direct_input=p2_direct,
        )
        # Persist mouse world for broadcast
        self.player1.mouse_world_x, self.player1.mouse_world_y = mouse_world_x, mouse_world_y
        if p2_mouse_world:
            self.player2.mouse_world_x, self.player2.mouse_world_y = p2_mouse_world
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
        elif self.game_state == "host_select":
            self.draw_host_menu()
        elif self.game_state == "join_menu":
            self.draw_join_menu()
        elif self.game_state == "host_online":
            self.draw_host_online_menu()
        elif self.game_state == "join_online":
            self.draw_join_online_menu()
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
        host_text = font.render("Press H to Host", True, (200, 200, 200))
        host_rect = host_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2))
        self.screen.blit(host_text, host_rect)
        
        join_text = font.render("Press J to Join", True, (200, 200, 200))
        join_rect = join_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 40))
        self.screen.blit(join_text, join_rect)

        online_host = font.render("Press O to Host Online", True, (200, 230, 230))
        online_host_rect = online_host.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 80))
        self.screen.blit(online_host, online_host_rect)

        online_join = font.render("Press P to Join Online", True, (200, 230, 230))
        online_join_rect = online_join.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 120))
        self.screen.blit(online_join, online_join_rect)

        esc_text = font.render("Press ESC to Quit", True, (200, 200, 200))
        esc_rect = esc_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 170))
        self.screen.blit(esc_text, esc_rect)
        
        if self.last_winner:
            win_text = font.render(f"Last winner: {self.last_winner}", True, (220, 220, 80))
            win_rect = win_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 140))
            self.screen.blit(win_text, win_rect)
        version_font = pygame.font.Font(None, 24)
        version_text = version_font.render(f"v{GAME_VERSION}", True, (180, 180, 180))
        self.screen.blit(version_text, (10, config.SCREEN_HEIGHT - 30))

    def draw_host_menu(self):
        font = pygame.font.Font(None, 52)
        title = font.render("Host Game", True, (255, 255, 255))
        self.screen.blit(title, (config.SCREEN_WIDTH // 2 - title.get_width() // 2, 140))
        font_small = pygame.font.Font(None, 36)
        current = font_small.render(f"Your hero: {self.host_choice.title()}", True, (220, 220, 220))
        self.screen.blit(current, (config.SCREEN_WIDTH // 2 - current.get_width() // 2, 220))
        hint = font_small.render("LEFT/RIGHT to toggle hero", True, (200, 200, 200))
        self.screen.blit(hint, (config.SCREEN_WIDTH // 2 - hint.get_width() // 2, 270))
        start = font_small.render("ENTER to start, ESC to cancel", True, (200, 200, 200))
        self.screen.blit(start, (config.SCREEN_WIDTH // 2 - start.get_width() // 2, 320))

    def draw_join_menu(self):
        font = pygame.font.Font(None, 52)
        title = font.render("Join Game", True, (255, 255, 255))
        self.screen.blit(title, (config.SCREEN_WIDTH // 2 - title.get_width() // 2, 140))
        font_small = pygame.font.Font(None, 36)
        prompt = font_small.render("Host IP:", True, (220, 220, 220))
        self.screen.blit(prompt, (config.SCREEN_WIDTH // 2 - prompt.get_width() // 2, 220))
        ip_text = font_small.render(self.join_ip_input or " ", True, (255, 255, 0))
        box_rect = pygame.Rect(config.SCREEN_WIDTH // 2 - 200, 260, 400, 48)
        pygame.draw.rect(self.screen, (40, 40, 60), box_rect)
        pygame.draw.rect(self.screen, (200, 200, 200), box_rect, 2)
        self.screen.blit(ip_text, (box_rect.x + 10, box_rect.y + 10))
        hint = font_small.render("Type IP, ENTER to connect, ESC to cancel", True, (200, 200, 200))
        self.screen.blit(hint, (config.SCREEN_WIDTH // 2 - hint.get_width() // 2, 330))

    def draw_host_online_menu(self):
        font = pygame.font.Font(None, 52)
        title = font.render("Host Online", True, (255, 255, 255))
        self.screen.blit(title, (config.SCREEN_WIDTH // 2 - title.get_width() // 2, 90))
        font_small = pygame.font.Font(None, 32)
        hero = font_small.render(f"Your hero: {self.host_choice.title()}  (LEFT/RIGHT to toggle)", True, (220, 220, 220))
        self.screen.blit(hero, (config.SCREEN_WIDTH // 2 - hero.get_width() // 2, 150))

        ip_label = font_small.render("Advertised IP (what others connect to):", True, (200, 200, 200))
        self.screen.blit(ip_label, (config.SCREEN_WIDTH // 2 - ip_label.get_width() // 2, 210))
        ip_box = pygame.Rect(config.SCREEN_WIDTH // 2 - 260, 245, 520, 44)
        pygame.draw.rect(self.screen, (40, 40, 60), ip_box)
        pygame.draw.rect(self.screen, (230, 230, 120) if self.host_online_field == "ip" else (200, 200, 200), ip_box, 2)
        ip_text = font_small.render(self.advertised_ip_input or " ", True, (255, 255, 0))
        self.screen.blit(ip_text, (ip_box.x + 10, ip_box.y + 8))

        srv_label = font_small.render("Lobby server URL:", True, (200, 200, 200))
        self.screen.blit(srv_label, (config.SCREEN_WIDTH // 2 - srv_label.get_width() // 2, 305))
        srv_box = pygame.Rect(config.SCREEN_WIDTH // 2 - 260, 340, 520, 44)
        pygame.draw.rect(self.screen, (40, 40, 60), srv_box)
        pygame.draw.rect(self.screen, (230, 230, 120) if self.host_online_field == "server" else (200, 200, 200), srv_box, 2)
        srv_text = font_small.render(self.lobby_server_url or " ", True, (200, 255, 255))
        self.screen.blit(srv_text, (srv_box.x + 10, srv_box.y + 8))

        hint = font_small.render("TAB to switch field, ENTER to create lobby & start, ESC to cancel", True, (200, 200, 200))
        self.screen.blit(hint, (config.SCREEN_WIDTH // 2 - hint.get_width() // 2, 400))
        if self.host_online_status:
            status = font_small.render(self.host_online_status, True, (220, 180, 120))
            self.screen.blit(status, (config.SCREEN_WIDTH // 2 - status.get_width() // 2, 450))

    def draw_join_online_menu(self):
        font = pygame.font.Font(None, 52)
        title = font.render("Join Online", True, (255, 255, 255))
        self.screen.blit(title, (config.SCREEN_WIDTH // 2 - title.get_width() // 2, 90))
        font_small = pygame.font.Font(None, 32)

        code_label = font_small.render("Lobby code:", True, (200, 200, 200))
        self.screen.blit(code_label, (config.SCREEN_WIDTH // 2 - code_label.get_width() // 2, 170))
        code_box = pygame.Rect(config.SCREEN_WIDTH // 2 - 200, 205, 400, 44)
        pygame.draw.rect(self.screen, (40, 40, 60), code_box)
        pygame.draw.rect(self.screen, (230, 230, 120) if self.join_online_field == "code" else (200, 200, 200), code_box, 2)
        code_text = font_small.render(self.join_online_code_input or " ", True, (255, 255, 0))
        self.screen.blit(code_text, (code_box.x + 10, code_box.y + 8))

        srv_label = font_small.render("Lobby server URL:", True, (200, 200, 200))
        self.screen.blit(srv_label, (config.SCREEN_WIDTH // 2 - srv_label.get_width() // 2, 270))
        srv_box = pygame.Rect(config.SCREEN_WIDTH // 2 - 260, 305, 520, 44)
        pygame.draw.rect(self.screen, (40, 40, 60), srv_box)
        pygame.draw.rect(self.screen, (230, 230, 120) if self.join_online_field == "server" else (200, 200, 200), srv_box, 2)
        srv_text = font_small.render(self.lobby_server_url or " ", True, (200, 255, 255))
        self.screen.blit(srv_text, (srv_box.x + 10, srv_box.y + 8))

        hint = font_small.render("TAB to switch field, ENTER to join, ESC to cancel", True, (200, 200, 200))
        self.screen.blit(hint, (config.SCREEN_WIDTH // 2 - hint.get_width() // 2, 360))
        if self.join_online_status:
            status = font_small.render(self.join_online_status, True, (220, 180, 120))
            self.screen.blit(status, (config.SCREEN_WIDTH // 2 - status.get_width() // 2, 410))
    
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
        if self.current_lobby_id:
            font = pygame.font.Font(None, 24)
            label = f"Lobby {self.current_lobby_id} | Share IP: {self.advertised_ip_input}"
            lobby_text = font.render(label, True, (220, 220, 120))
            self.screen.blit(lobby_text, (config.SCREEN_WIDTH // 2 - lobby_text.get_width() // 2, 36))
    
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

    def create_online_lobby(self):
        """Create a lobby on the backend server and start hosting the match."""
        base_url = (self.lobby_server_url or "").rstrip("/")
        if not base_url:
            self.host_online_status = "Lobby server URL required."
            return
        payload = {
            "host_ip": self.advertised_ip_input.strip() or None,
            "control_port": 50007,
            "state_port": 50008,
            "host_choice": self.host_choice,
        }
        try:
            resp = requests.post(f"{base_url}/lobbies", json=payload, timeout=4)
            if resp.status_code >= 400:
                self.host_online_status = f"Server error: {resp.status_code}"
                return
            data = resp.json()
            lobby_id = data.get("id") or data.get("lobbyId")
            if not lobby_id:
                self.host_online_status = "No lobby id returned."
                return
            self.relay_host = data.get("relay_host") or self._extract_host_from_base(self.lobby_server_url)
            self.relay_control_port = data.get("relay_control_port", self.relay_control_port)
            self.relay_state_port = data.get("relay_state_port", self.relay_state_port)
            self.using_relay = bool(self.relay_host)
            self.current_lobby_id = lobby_id
            self.host_online_status = f"Lobby {lobby_id} created. Share code + IP {self.advertised_ip_input}"
            self.game_state = "playing"
            self.reset_game()
        except requests.RequestException as exc:
            self.host_online_status = f"Network error: {exc}"

    def join_online_lobby(self):
        """Fetch lobby info from backend and connect as client."""
        code = (self.join_online_code_input or "").strip().lower()
        if not code:
            self.join_online_status = "Lobby code is required."
            return
        base_url = (self.lobby_server_url or "").rstrip("/")
        if not base_url:
            self.join_online_status = "Lobby server URL required."
            return
        try:
            resp = requests.get(f"{base_url}/lobbies/{code}", timeout=4)
            if resp.status_code == 404:
                self.join_online_status = "Lobby not found or expired."
                return
            if resp.status_code >= 400:
                self.join_online_status = f"Server error: {resp.status_code}"
                return
            data = resp.json()
            host_ip = data.get("host_ip") or data.get("hostIp") or data.get("host")
            if not host_ip:
                self.join_online_status = "Lobby missing host IP."
                return
            self.join_online_status = f"Connecting to {host_ip} ..."
            self.join_ip_input = host_ip
            relay_host = data.get("relay_host") or self._extract_host_from_base(self.lobby_server_url)
            relay_control_port = data.get("relay_control_port", 40007)
            relay_state_port = data.get("relay_state_port", 40008)
            use_relay = bool(relay_host)
            run_join_client(
                host_ip,
                lobby_id=code,
                relay_host=relay_host if use_relay else None,
                relay_control_port=relay_control_port,
                relay_state_port=relay_state_port,
            )
            # When client window closes, return to main menu
            self.game_state = "menu"
        except requests.RequestException as exc:
            self.join_online_status = f"Network error: {exc}"

    def _extract_host_from_base(self, base_url):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            return parsed.hostname
        except Exception:
            return None

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
                    "attack_dir_x": getattr(p, "attack_dir_x", 0.0),
                    "attack_dir_y": getattr(p, "attack_dir_y", 1.0),
                    "attack_origin_x": getattr(p, "attack_origin_x", p.x),
                    "attack_origin_y": getattr(p, "attack_origin_y", p.y),
                    "shield_angle": getattr(p, "shield_angle", 0.0),
                    "mouse_world_x": getattr(p, "mouse_world_x", p.x),
                    "mouse_world_y": getattr(p, "mouse_world_y", p.y),
                    "critical_hit_timer": getattr(p, "critical_hit_timer", 0.0),
                    "critical_border_timer": getattr(p, "critical_border_timer", 0.0),
                    "critical_text_world_x": getattr(p, "critical_text_world_x", p.x),
                    "critical_text_world_y": getattr(p, "critical_text_world_y", p.y),
                    "critical_text_offset_y": getattr(p, "critical_text_offset_y", 0.0),
                    "shield_block_timer": getattr(p, "shield_block_timer", 0.0),
                    "shield_text_world_x": getattr(p, "shield_text_world_x", p.x),
                    "shield_text_world_y": getattr(p, "shield_text_world_y", p.y),
                    "shield_text_offset_y": getattr(p, "shield_text_offset_y", 0.0),
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
        if self.state_targets:
            payload = json.dumps(state).encode("utf-8")
            for addr in list(self.state_targets):
                try:
                    self.state_socket.sendto(payload, addr)
                except OSError:
                    self.state_targets.discard(addr)
        if self.using_relay and self.current_lobby_id and self.relay_host:
            self.broadcast_state_via_relay(state)

    def tick_relay(self, dt):
        """Keep relay registration alive so the server can forward packets."""
        if not self.relay_host:
            return
        self.relay_keepalive_timer += dt
        if self.relay_keepalive_timer >= 1.5:
            self.relay_keepalive_timer = 0.0
            try:
                reg = {"lobby": self.current_lobby_id, "role": "host", "kind": "control", "type": "register"}
                self.udp_socket.sendto(json.dumps(reg).encode("utf-8"), (self.relay_host, self.relay_control_port))
            except OSError:
                pass
            try:
                reg_state = {"lobby": self.current_lobby_id, "role": "host", "kind": "state", "type": "register"}
                self.state_socket.sendto(json.dumps(reg_state).encode("utf-8"), (self.relay_host, self.relay_state_port))
            except OSError:
                pass

    def broadcast_state_via_relay(self, state):
        """Send state to relay server which forwards to clients."""
        envelope = {
            "lobby": self.current_lobby_id,
            "role": "host",
            "kind": "state",
            "payload": state,
        }
        try:
            self.state_socket.sendto(json.dumps(envelope).encode("utf-8"), (self.relay_host, self.relay_state_port))
        except OSError:
            pass

    def run(self):
        """Main game loop for the host instance."""
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


# Helpers for client rendering
def _apply_player_state(player, data):
    player.x = data["x"]
    player.y = data["y"]
    player.health = data["health"]
    player.max_health = data["max_health"]
    player.is_dead = player.health <= 0
    player.facing_direction = data["facing"]
    player.is_attacking = data["is_attacking"]
    player.is_blocking = data["is_blocking"]
    player.is_gesturing = data["is_gesturing"]
    player.is_moving = data["is_moving"]
    player.mouse_world_x = data.get("mouse_world_x", player.x)
    player.mouse_world_y = data.get("mouse_world_y", player.y)
    player.shield_angle = data.get("shield_angle", getattr(player, "shield_angle", 0.0))
    player.critical_hit_timer = data.get("critical_hit_timer", 0.0)
    player.critical_border_timer = data.get("critical_border_timer", 0.0)
    player.critical_text_world_x = data.get("critical_text_world_x", player.x)
    player.critical_text_world_y = data.get("critical_text_world_y", player.y)
    player.critical_text_offset_y = data.get("critical_text_offset_y", 0.0)
    player.shield_block_timer = data.get("shield_block_timer", 0.0)
    player.shield_text_world_x = data.get("shield_text_world_x", player.x)
    player.shield_text_world_y = data.get("shield_text_world_y", player.y)
    player.shield_text_offset_y = data.get("shield_text_offset_y", 0.0)
    # Sync attack visualization for remote viewers
    if player.is_attacking:
        player.attack_origin_x = data.get("attack_origin_x", player.x)
        player.attack_origin_y = data.get("attack_origin_y", player.y)
        dx = data.get("attack_dir_x", 0.0)
        dy = data.get("attack_dir_y", 1.0)
        if dx == 0 and dy == 0:
            dir_map = {
                "up": (0.0, -1.0),
                "down": (0.0, 1.0),
                "left": (-1.0, 0.0),
                "right": (1.0, 0.0),
            }
            dx, dy = dir_map.get(player.facing_direction, (0.0, 1.0))
        player.attack_dir_x = dx
        player.attack_dir_y = dy
        player.attack_direction = player.facing_direction
        player.attack_length = player.attack_range * 2.0
        player.attack_base_half_width = player.attack_range * 0.35

    if player.animations:
        if player.is_attacking:
            player.animations.set_animation("attack")
        elif player.is_gesturing:
            player.animations.set_animation("gesture")
        elif player.is_blocking and "shield" in player.animations.animations:
            player.animations.set_animation("shield")
        elif player.is_moving:
            player.animations.set_animation("walk")
        else:
            player.animations.set_animation("idle")


def run_join_client(host="127.0.0.1", lobby_id=None, relay_host=None, relay_control_port=40007, relay_state_port=40008):
    pygame.display.set_caption("7KOR - Join")
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    camera = Camera()
    grass = GrasslandTile(size=config.GRASSLAND_TILE_SIZE)
    # Local mirrors (will be swapped once we know hero types)
    p1 = RogueWarrior(-200, 0)
    p2 = Mage(200, 0)
    players = [p1, p2]
    projectiles = []
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_sock.bind(("", 0))
    state_sock.setblocking(False)
    control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    control_dest = (relay_host, relay_control_port) if relay_host else (host, 50007)
    state_dest = (relay_host, relay_state_port) if relay_host else (host, 50008)
    if relay_host:
        try:
            reg = {"lobby": lobby_id or "", "role": "client", "kind": "state", "type": "register"}
            state_sock.sendto(json.dumps(reg).encode("utf-8"), state_dest)
        except OSError:
            pass
    else:
        state_sock.sendto(b"hello", state_dest)
    game_state = "menu"
    last_winner = None
    running = True
    while running:
        dt = clock.tick(config.FPS) / 1000.0
        attack_click = False
        gesture_click = False
        left_down = False
        right_down = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_g:
                    gesture_click = True
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    attack_click = True
                    left_down = True
                if event.button == 3:
                    right_down = True
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    left_down = False
                if event.button == 3:
                    right_down = False

        keys = pygame.key.get_pressed()
        mouse_x, mouse_y = pygame.mouse.get_pos()
        mouse_buttons = pygame.mouse.get_pressed()
        left_down = left_down or mouse_buttons[0]
        right_down = right_down or mouse_buttons[2]
        payload = {
            "up": keys[pygame.K_w],
            "down": keys[pygame.K_s],
            "left": keys[pygame.K_a],
            "right": keys[pygame.K_d],
            "dash": keys[pygame.K_SPACE],
            "block": right_down,
            "attack": attack_click or left_down,
            "gesture": gesture_click,
            "mouse_x": mouse_x,
            "mouse_y": mouse_y,
        }
        try:
            if relay_host:
                envelope = {"lobby": lobby_id or "", "role": "client", "kind": "control", "payload": payload}
                control_sock.sendto(json.dumps(envelope).encode("utf-8"), control_dest)
            else:
                control_sock.sendto(json.dumps(payload).encode("utf-8"), control_dest)
        except OSError:
            pass

        try:
            data, _ = state_sock.recvfrom(8192)
            remote = json.loads(data.decode("utf-8"))
            game_state = remote.get("game_state", game_state)
            last_winner = remote.get("last_winner", last_winner)
            cam = remote.get("camera", {})
            camera.x = cam.get("x", camera.x)
            camera.y = cam.get("y", camera.y)
            rplayers = remote.get("players", [])
            if len(rplayers) >= 2:
                # Rebuild local mirrors if hero types differ
                def build(hero_name, x, y):
                    if hero_name.lower().startswith("mage"):
                        return Mage(x, y)
                    return RogueWarrior(x, y)
                if (rplayers[0].get("name", "").lower().startswith("mage") and not isinstance(p1, Mage)) or (
                    rplayers[0].get("name", "").lower().startswith("rogue") and not isinstance(p1, RogueWarrior)
                ):
                    p1 = build(rplayers[0].get("name", ""), p1.x, p1.y)
                if (rplayers[1].get("name", "").lower().startswith("mage") and not isinstance(p2, Mage)) or (
                    rplayers[1].get("name", "").lower().startswith("rogue") and not isinstance(p2, RogueWarrior)
                ):
                    p2 = build(rplayers[1].get("name", ""), p2.x, p2.y)
                players = [p1, p2]
                _apply_player_state(p1, rplayers[0])
                _apply_player_state(p2, rplayers[1])
            projectiles = []
            for pr in remote.get("projectiles", []):
                owner = p1 if pr.get("owner") == p1.name else p2
                anim = None
                if isinstance(owner, Mage) and hasattr(owner, "_clone_projectile_animation"):
                    anim = owner._clone_projectile_animation()
                proj = Projectile(
                    pr["x"], pr["y"], pr["dir_x"], pr["dir_y"],
                    speed=500, damage=1, owner=owner,
                    color=(120, 200, 255), radius=10, lifetime=2.0, animation=anim
                )
                projectiles.append(proj)
        except (BlockingIOError, ConnectionResetError, ConnectionAbortedError, OSError):
            # Ignore transient socket errors on client
            pass

        for pl in players:
            if pl.animations:
                pl.animations.update(dt)

        screen.fill(config.SKY_BLUE)
        if game_state == "menu":
            font = pygame.font.Font(None, 48)
            txt = font.render("Waiting for host...", True, (230, 230, 230))
            screen.blit(txt, (config.SCREEN_WIDTH // 2 - txt.get_width() // 2, config.SCREEN_HEIGHT // 2))
        else:
            grass.draw(screen, camera)
            for proj in projectiles:
                proj.draw(screen, camera)
            for pl in players:
                pl.draw(screen, camera)
            for pl in players:
                pl.draw_critical_effects(screen, camera)
            def draw_bar(player, bar_x):
                bar_width = 200
                bar_height = 18
                bar_y = config.SCREEN_HEIGHT - 70
                pygame.draw.rect(screen, (60, 0, 0), (bar_x, bar_y, bar_width, bar_height))
                ratio = max(0, min(1, player.health / player.max_health if player.max_health else 1))
                fill = int(bar_width * ratio)
                if fill > 0:
                    pygame.draw.rect(screen, player.ui_color, (bar_x, bar_y, fill, bar_height))
                pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 2)
                font = pygame.font.Font(None, 22)
                label = font.render(f"{player.name} {int(player.health)}/{int(player.max_health)}", True, (230, 230, 230))
                screen.blit(label, (bar_x, bar_y - 22))
            draw_bar(p1, 10)
            draw_bar(p2, config.SCREEN_WIDTH - 210)
            font = pygame.font.Font(None, 24)
            status = font.render("You are the remote player. Arrows move, RCTRL shoot, RSHIFT dash, ALT block (if applicable).", True, (230, 230, 230))
            screen.blit(status, (config.SCREEN_WIDTH // 2 - status.get_width() // 2, 10))

        pygame.display.flip()

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
