# Space Avaders: Parallax Assault

A widescreen ode to early-console horizontal shooters, built entirely with
Python 3 and pygame. Every sprite, glow, and particle burst is generated in
code—no external art required. Expect a dazzling parallax backdrop, crunchy
lasers, and a steady escalation of enemy formations.

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

The window opens at 900×700. Piloting is eight-directional—use `WASD` or the
arrow keys, tap `Space` (or `Enter`) to fire, and hold `Shift` to engage focus
mode for precise dodges. Press `Esc` to quit.

## Gameplay features

- **Side-scrolling spectacle** – Surf through a layered starfield packed with
  drifting nebulae, speed trails, and responsive parallax lighting.
- **Formation playbooks** – Streams of dart fighters, swooping flares, orbiting
  orbs, and hulking sentinels arrive on a scripted timeline inspired by
  classics like Defender and Gradius.
- **Overdrive arsenal** – Maintain your combo to trigger capsule drops. Pick up
  overdrive cores to unleash triple lasers with a lower firing cooldown.
- **Skill expression** – Eight-direction thrust with a focus toggle for tight
  weaving, score multipliers for consecutive kills, and collectible vault pods
  for bonus loot.
- **Procedural juice** – All audio, glow trails, and impact particles are
  generated on the fly for a distinctive, crunchy vibe.

Losing every ship ends the run. Hit `Enter` on the mission-failed screen to
launch another assault.
