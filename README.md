# unreversible
UNBEATABLE Story Mode reverse-engineering/datamining tooling

This repository currently consists of an experimental decompiler for [Yarn Spinner](https://www.yarnspinner.dev/) 2.0.2 bytecode. The decompiler is NOT fully functional at the moment.

Plans exist for additional tooling around the replacement of Yarn Spinner code and editing of UNBEATABLE-exclusive `NarrativeGraph` assets.

## Getting Started
This tool currently relies on [ErikGXDev's mod](https://github.com/ErikGXDev/unbeatable-demo-song-hack) to handle the extraction of Yarn Spinner bytecode from the game.

Ensure you are using a version (3.10+) of Python that supports the `match` statement, which the decompiler heavily relies on. Install all the dependencies in `requirements.txt` using `pip install -r` in a virtual environment or globally.

Follow the [instructions on its README](https://github.com/ErikGXDev/unbeatable-demo-song-hack#installation) to install ErikGXDev's mod, and then open the game with the mod active.

Open the mod menu with the button on the top left (you may want to open Arcade mode to bring out the mouse cursor) and press the "Dump Translations" button. Ensure there is a folder created named "dumped" in the folder the game is installed in containing several files ending in `.yarnproject.json` and one `lines.json` file.

Run `python3 main.py [dumped]` where `[dumped]` is replaced with the full path to this folder (on my macOS system which uses Wine and Sikarugir to run the game, the path would be `/Volumes/exFAT Drive/Sikarugir/Steam.app/Contents/drive_c/Program Files (x86)/Steam/steamapps/common/UNBEATABLE/dumped`).

A folder called `decompiled/yarn` will be created within the folder you cloned this repository containing decompiled Yarn Spinner project scripts recovered from the game's story mode.

## Credits
Thank you to ErikGXDev for creating the mod used to extract story data from the game, the BepInEx project for enabling its usage, and the UNBEATABLE Modding Community Discord server for support during the development of this project.

This repository is not affiliated with D-CELL GAMES, Yarn Spinner or anyone involved in the development of UNBEATABLE.
