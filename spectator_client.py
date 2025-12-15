"""Spectator client that renders the game using host state updates."""

import json
import socket
import sys
import pygame
import config
from camera import Camera
from world import GrasslandTile
from rogue_warrior import RogueWarrior
from mage import Mage
from projectile import Projectile

STATE_PORT = 50008


def apply_player_state(player, data):
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
    # Set animation based on state
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


def run_spectator(host="127.0.0.1"):
    pygame.display.set_caption("7KOR - Spectator")
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    camera = Camera()
    grass = GrasslandTile(size=config.GRASSLAND_TILE_SIZE)
    player1 = RogueWarrior(-200, 0)
    player2 = Mage(200, 0)
    players = [player1, player2]
    projectiles = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 0))
    sock.setblocking(False)
    sock.sendto(b"hello", (host, STATE_PORT))

    game_state = "menu"
    last_winner = None

    running = True
    while running:
        dt = clock.tick(config.FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        try:
            data, _ = sock.recvfrom(8192)
            payload = json.loads(data.decode("utf-8"))
            game_state = payload.get("game_state", "menu")
            last_winner = payload.get("last_winner")
            cam = payload.get("camera", {})
            camera.x = cam.get("x", camera.x)
            camera.y = cam.get("y", camera.y)
            remote_players = payload.get("players", [])
            if len(remote_players) >= 2:
                apply_player_state(player1, remote_players[0])
                apply_player_state(player2, remote_players[1])
            # Rebuild projectiles
            projectiles = []
            for p in payload.get("projectiles", []):
                owner = player1 if p.get("owner") == player1.name else player2
                proj = Projectile(
                    p["x"],
                    p["y"],
                    p["dir_x"],
                    p["dir_y"],
                    speed=500,
                    damage=1,
                    owner=owner,
                    color=(200, 180, 120),
                    radius=10,
                    lifetime=2.0,
                    animation=None,
                )
                projectiles.append(proj)
        except BlockingIOError:
            pass

        # Advance animations a bit to keep them alive
        for p in players:
            if p.animations:
                p.animations.update(dt)

        # Draw
        screen.fill(config.SKY_BLUE)
        if game_state == "menu":
            font = pygame.font.Font(None, 48)
            txt = font.render("Waiting for host (menu)...", True, (230, 230, 230))
            screen.blit(txt, (config.SCREEN_WIDTH // 2 - txt.get_width() // 2, config.SCREEN_HEIGHT // 2))
            if last_winner:
                winner_txt = font.render(f"Last winner: {last_winner}", True, (220, 220, 120))
                screen.blit(winner_txt, (config.SCREEN_WIDTH // 2 - winner_txt.get_width() // 2, config.SCREEN_HEIGHT // 2 + 50))
        else:
            grass.draw(screen, camera)
            for proj in projectiles:
                proj.draw(screen, camera)
            for p in players:
                p.draw(screen, camera)
            # UI bars
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
            draw_bar(player1, 10)
            draw_bar(player2, config.SCREEN_WIDTH - 210)

        pygame.display.flip()


if __name__ == "__main__":
    host = "127.0.0.1"
    if len(sys.argv) > 1:
        host = sys.argv[1]
    run_spectator(host)
