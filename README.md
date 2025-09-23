# Space Avaders 2084

A side-scrolling remix of the original project that leans into the console-shooter
heritage of *Gradius*, *Defender*, and *R-Type*.  Every wave is scripted, the
skyline scrolls by with parallax neon clouds, and minibosses close each stage
with chunky, glowing bullet patterns.  The visuals are still fully procedural
rectangles, gradients, and particles—no external art required.

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

The game opens at 960×720. Use `← → ↑ ↓` (or `WASD`) to steer, hold `Space`,
`Z`, or `J` to fire, and tap `F` to toggle fullscreen. Press `Esc` to quit.

## Gameplay features

- **Scripted stages with nostalgic riffs** – Each wave is choreographed in a
  timeline curated by a stage director, riffing on early-console classics: Galaga
  inspired vanguard swoops, Gradius-style turret trenches, Defender chase
  squadrons, and a neon fortress boss.
- **True side-scrolling movement** – Freely strafe across the screen while the
  background and enemy formations slide in from the horizon. The ship banks and
  pulses with thruster trails as you weave through patterns.
- **Juicy combat loop** – Dual blasters, rapid-fire upgrades, and barrier
  modules drop from tougher foes. A combo timer rewards relentless offense with
  bonus points and celebratory floating text.
- **Boss finales** – Every stage concludes with a miniature bullet-hell
  encounter. The boss tracks your vertical position, fires spreads and lances,
  and showers power-ups when defeated.
- **Parallax starfields & particles** – Multiple cloud layers, twinkling stars,
  and dozens of sparks/explosions keep the screen buzzing without external
  assets.
- **Adaptive score chase** – Clear a stage to earn an extra life and roll into
  the next theme at higher intensity. HUD callouts track rapid-fire timers,
  barrier charges, and wave progression so you always know the stakes.

Lose all lives and you’ll hit the game-over banner; press `Enter` to launch back
into the neon gauntlet.
