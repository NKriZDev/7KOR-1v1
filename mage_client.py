"""Remote mage client: send inputs to host over UDP."""

import json
import socket
import sys
import pygame

PORT = 50007


def run_mage_client(host="127.0.0.1"):
    pygame.display.set_caption("Mage Controller")
    screen = pygame.display.set_mode((480, 160))
    clock = pygame.time.Clock()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    running = True
    attack_click = False
    gesture_click = False
    while running:
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
            "block": False,
            "attack": attack_click,
            "gesture": gesture_click,
        }
        try:
            sock.sendto(json.dumps(payload).encode("utf-8"), (host, PORT))
        except OSError:
            pass

        screen.fill((20, 20, 40))
        font = pygame.font.Font(None, 28)
        lines = [
            f"Sending to {host}:{PORT}",
            "Arrows: move  |  RSHIFT: dash",
            "RCTRL/KP0: shoot  |  SLASH: emote",
            "ESC to quit",
        ]
        for i, line in enumerate(lines):
            text = font.render(line, True, (220, 220, 240))
            screen.blit(text, (20, 20 + i * 28))
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    host_arg = "127.0.0.1"
    if len(sys.argv) > 1:
        host_arg = sys.argv[1]
    run_mage_client(host_arg)
