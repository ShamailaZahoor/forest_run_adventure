# Forest Runner Adventure

A 2D endless-runner game built with **Python + Tkinter**. The player automatically
runs through a scrolling forest and must **jump** over ground obstacles or **slide**
under flying obstacles. Score grows with distance, the best score is saved to disk,
and speed ramps up the longer you survive.

All graphics are drawn with Tkinter canvas primitives (no external image files),
so the game runs anywhere Python + Tkinter are available. Sound effects use the
built-in Windows `winsound` module and degrade gracefully on other platforms.

## Features

- Start screen with game logo, title, **Play / Instructions / Exit** buttons
- Mobile-thumbnail-style **game logo** (rounded forest scene with a running fox
  and a "Forest Run Adventure" title ribbon) shown on the start screen **and**
  the game-over screen — drawn with canvas primitives, no image files
- Auto-running fox-like character with animated legs, tail and dust particles
- Parallax scrolling forest (sky gradient, sun, clouds, hills, trees, grass)
- Keyboard controls: `SPACE` = jump, `DOWN` = slide, `P` = pause, `R` = restart
- Ground obstacles (rock, bush, barrier) -> jump over
- Flying obstacles (branch, pillar) -> slide under
- Collision detection with Game Over overlay
- Score system + persistent high score (`highscore.json`)
- Restart and back-to-menu buttons after game over
- Modern rounded buttons with hover/press animations
- Soft forest color theme with green/yellow/red status indicators
- Clean class-based architecture

## Run

```bash
python forest_run_adventure.py
```

Requires Python 3.8+ (Tkinter ships with the standard CPython installer on Windows).

## Build a Windows executable

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name ForestRunAdventure forest_run_adventure.py
```

or simply double-click `build_windows.bat`. The standalone executable appears at
`dist/ForestRunAdventure.exe`. The high-score file is written next to the EXE.
## ScreenShots
![Start Screen](SS/start_screen.png) 
![GamePlay](SS/gameplay.png)  
![Game Over](SS/game_over.png)

## Project layout

```
p5/
├── forest_run_adventure.py      # the game (single file, class-based)
├── forest_run_adventure.spec    # PyInstaller spec
├── build_windows.bat            # one-click Windows build script
├── requirements.txt             # build tooling
└── highscore.json               # created at runtime (best score)
```

## Controls

| Key     | Action                          |
|---------|---------------------------------|
| SPACE   | Jump over ground obstacles      |
| DOWN    | Slide under flying obstacles    |
| P       | Pause / resume                  |
| R       | Restart (on Game Over screen)   |
| ESC     | Back to menu / quit             |
