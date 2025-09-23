# Space Avaders: Star Cascade

A bold, side-scrolling remix of the original Space Avaders project. Inspired by
early console greats—think Gradius, Phantasy Zone, and Thunder Force—the action
now surges across a neon skyline with parallax cities, rolling meteor storms,
and enemy squadrons that arrive in choreographed waves. Procedural sprites,
particles, and synthy bleeps keep everything cohesive without external assets.

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

The game renders at 960×720 by default and scales smoothly if you resize the
window or toggle fullscreen with `F`.

## Controls

| Action                | Input                                  |
|-----------------------|-----------------------------------------|
| Thrust / drift        | Arrow keys or `W` `A` `S` `D`           |
| Fire                  | `Space` or `Z`                          |
| Boost burst           | Hold `Shift`                            |
| Start / Restart run   | `Enter` (or `Space` on the title screen) |
| Toggle fullscreen     | `F`                                     |
| Mute / adjust volume  | `M`, `-`, `+`                           |
| Quit                  | `Esc`                                   |

## Highlights

- **Side-scrolling stages** – Drift through looping acts with bespoke parallax
  skylines and stars that warp by the faster you fly.
- **Enemy archetypes** – Fighters weave in sine waves, serpents slither in huge
  arcs, bombers drop gravity bombs, spinners spray bullets, and meteor showers
  demand last-second dodges.
- **Power-up fantasy** – Snag Trident (triple shots), Shield (orbital barrier),
  and Flux (speed & rate-of-fire boost) capsules to bend a wave in your favour.
- **Distance & combo chasing** – The HUD tracks score, travelled mega-meters,
  lives, and active buffs; chaining takedowns keeps a multiplier climbing.
- **Juicy feedback** – Procedural muzzle flashes, thruster plumes, and crunchy
  synth audio lean into the 1980s fantasy.

Lose all lives and your run ends—press `Enter` to launch again and chase a
longer ride.
