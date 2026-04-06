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

## Editing
To modify decompiled scripts and put them back into the game, this tool once again relies on ErikGXDev's mod.

You'll need the official Yarn Spinner compiler [`ysc`](https://github.com/YarnSpinnerTool/YarnSpinner-Console/tree/v2.0.2). Download the [GitHub release](https://github.com/YarnSpinnerTool/YarnSpinner-Console/releases/tag/v2.0.2) pointing to the version of Yarn Spinner the game uses (2.0.2), and put the executable somewhere on your `PATH` so the tool can find it.

So that the tool can read compiled projects to convert them into JSON, you'll need the Protocol Buffers generated code for a Yarn project. Download and install version 5.29.3 of Protocol Buffers `protoc` according to its [installation instructions](https://protobuf.dev/installation/).

Download the Protocol Buffers [specification](https://github.com/YarnSpinnerTool/YarnSpinner/blob/v2.0.2/YarnSpinner/yarn_spinner.proto) for that version and use `protoc` to generate the Python source to read compiled projects:

```sh
$ protoc ./yarn_spinner.proto --python_out=./unreversible/yarn
```

Now edit the scripts in `decompiled/yarn` to your heart's content, and run `python3 build_translation.py [dumped]` where `[dumped]` is still the path to the mod export folder. This should create a `Translation` folder in the repository you can copy and paste into your UNBEATABLE installation for the mod to inject into the game's scripts. Happy modding!

## Credits
Thank you to ErikGXDev for creating the mod used to extract story data from the game, the BepInEx project for enabling its usage, and the UNBEATABLE Modding Community Discord server for support during the development of this project.

This repository is not affiliated with D-CELL GAMES, Yarn Spinner or anyone involved in the development of UNBEATABLE.
