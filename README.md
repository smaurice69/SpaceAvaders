# Space Avaders

A compact Space-Invaders inspired arcade game built with Python 3 and pygame. The
visuals are all generated with simple rectangles, gradients, and particles—no
external assets are required. Expect a side-scrolling gauntlet of enemy waves,
flashy lasers, and a synthy starfield that keeps the run feeling alive.

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

The window opens at 900×700. Fly with `←` / `→` / `↑` / `↓` (or `WASD`), hold
`Shift` to tighten your dodge window, and tap `Space` (or `Z` / `X`) to fire.
Press `Esc` to quit.

## Gameplay features

- **Scrolling space lanes** – Each sector auto-scrolls like the early console
  greats, pushing you to weave through debris and enemy fire.
- **Hand-scripted waves** – Sine-surfing scouts, dive-bombing raiders, hovering
  turrets, and mine walls keep the action varied.
- **Sector bosses** – Every stage culminates with a hulking warship that floods
  the screen with patterns straight out of the 8-bit era.
- **Responsive controls** – Smooth omni-directional movement, a focus/slowdown
  option on `Shift`, and a rapid-fire blaster encourage daring dodges.
- **Escalating pace** – Clear a sector to jump to a faster scroll speed and a
  remixed spawn schedule.
- **Juice** – Particle bursts, glowing projectiles, and procedural sprites keep
  the minimalist presentation energetic.

Losing all three lives ends the run. Hit `Enter` on the game-over screen to try
again.
