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
        self.join_ip_input = "127.0.0.1"
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
                if self.game_state in ("menu", "host_select", "join_menu"):
                    if event.key == pygame.K_ESCAPE:
                        if self.game_state == "menu":
                            self.running = False
                        else:
                            self.game_state = "menu"
                    elif self.game_state == "menu":
                        if event.key == pygame.K_h:
                            self.game_state = "host_select"
                        elif event.key == pygame.K_j:
                            self.game_state = "join_menu"
                    elif self.game_state == "host_select":
                        if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                            self.host_choice = "mage" if self.host_choice == "rogue" else "rogue"
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.game_state = "playing"
                            self.reset_game()
                    elif self.game_state == "join_menu":
                        if event.key == pygame.K_RETURN:
                            run_join_client(self.join_ip_input)
                        elif event.key == pygame.K_BACKSPACE:
                            self.join_ip_input = self.join_ip_input[:-1]
                        else:
                            ch = event.unicode
                            if ch.isdigit() or ch == ".":
                                self.join_ip_input += ch
                elif self.game_state == "playing":
                    if event.key == pygame.K_ESCAPE:
                        self.game_state = "menu"
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
        elif self.game_state == "host_select":
            self.draw_host_menu()
        elif self.game_state == "join_menu":
            self.draw_join_menu()
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


def run_join_client(host="127.0.0.1"):
    pygame.display.set_caption("7KOR - Join")
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    camera = Camera()
    grass = GrasslandTile(size=config.GRASSLAND_TILE_SIZE)
    # Local mirrors
    p1 = RogueWarrior(-200, 0)
    p2 = Mage(200, 0)
    players = [p1, p2]
    projectiles = []
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_sock.bind(("", 0))
    state_sock.setblocking(False)
    state_sock.sendto(b"hello", (host, 50008))
    control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    game_state = "menu"
    last_winner = None
    running = True
    while running:
        dt = clock.tick(config.FPS) / 1000.0
        attack_click = False
        gesture_click = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key in (pygame.K_RCTRL, pygame.K_LCTRL, pygame.K_KP0):
                    attack_click = True
                if event.key == pygame.K_SLASH:
                    gesture_click = True

        keys = pygame.key.get_pressed()
        payload = {
            "up": keys[pygame.K_UP],
            "down": keys[pygame.K_DOWN],
            "left": keys[pygame.K_LEFT],
            "right": keys[pygame.K_RIGHT],
            "dash": keys[pygame.K_RSHIFT],
            "block": keys[pygame.K_RALT] or keys[pygame.K_LALT],
            "attack": attack_click,
            "gesture": gesture_click,
        }
        try:
            control_sock.sendto(json.dumps(payload).encode("utf-8"), (host, 50007))
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
                _apply_player_state(p1, rplayers[0])
                _apply_player_state(p2, rplayers[1])
            projectiles = []
            for pr in remote.get("projectiles", []):
                owner = p1 if pr.get("owner") == p1.name else p2
                proj = Projectile(
                    pr["x"], pr["y"], pr["dir_x"], pr["dir_y"],
                    speed=500, damage=1, owner=owner,
                    color=(200, 180, 120), radius=10, lifetime=2.0, animation=None
                )
                projectiles.append(proj)
        except BlockingIOError:
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
