"""
main.py — Entry point.

Run with:
    python main.py

Requires:
    pip install pygame
"""

from snake.controller import GameController


def main() -> None:
    GameController().run()


if __name__ == "__main__":
    main()
