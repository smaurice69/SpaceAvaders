# Space Avaders

A compact Space-Invaders inspired arcade game built with Python 3 and pygame. The
visuals are all generated with simple rectangles, gradients, and particles—no
external assets are required. Expect quick rounds, crunchy laser blasts, and
waves that keep pushing back.

## Getting started

1. Ensure Python 3.9+ is installed.
2. Install pygame:
   ```bash
   pip install pygame
   ```
3. Launch the game:
   ```bash
   python3 space_invaders.py
   ```

The window opens at 900×700. Use `←` / `→` (or `A` / `D`) to move and `Space`
to fire. Press `Esc` to quit.

## Gameplay features

- **Classic formation battles** – Aliens march as a block, dive closer when
  touching the arena edges, and their pace accelerates as you thin the horde.
- **Responsive controls** – Tight, smooth left/right movement and a comfortable
  firing cadence that encourages staying aggressive.
- **Enemy fire** – Invaders shoot back from the front line, forcing you to weave
  between incoming bolts.
- **Scaling difficulty** – Clearing a wave bumps the difficulty: higher alien
  speeds, denser formations, and quicker shots.
- **Score chasing** – Rack up points with clean kills, tag the occasional bonus
  UFO for a big payout, and keep an eye on the HUD for lives, wave, and score.
- **Juice** – Simple particle bursts and a drifting starfield give every blast a
  little extra flair.

Losing all three lives ends the run. Hit `Enter` on the game-over screen to try
again.
