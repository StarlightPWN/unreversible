import os
import sys
import yaml
import logging
import crossfiledialog

from platformdirs import PlatformDirs
dirs = PlatformDirs("unreversible", "lyskons")

CONFIG_PATH = os.path.join(dirs.user_config_dir, "config.yaml")
logger = logging.getLogger(__name__)

def find_steam_path(name, appid):
    import json
    if sys.platform == "win32": 
        from winreg import HKEY_LOCAL_MACHINE, OpenKey, QueryValueEx, REG_SZ

        with OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
            value, reg_type = QueryValueEx(key, "InstallPath")
            if reg_type != REG_SZ:
                return
    elif sys.platform == "linux":
        value = os.path.join(os.getenv("HOME"), ".local/share/Steam/steamapps/common/UNBEATABLE")
    elif sys.platform == "darwin":
        value = os.path.join(os.getenv("HOME"), "Library/Application Support/Steam/steamapps/libraryfolders.vdf")

    path = os.path.join(value, "steamapps/common/" + name)

    with open(os.path.join(value, "steamapps/libraryfolders.vdf"), "r") as f:
        for line in f:
            if line.startswith('\t\t"path"'):
                path = json.loads(line.split('\t')[-1].strip())
            if line.startswith('\t\t\t'):
                if f'"{appid}"' in line:
                    return path
    return path

def find_game_path():
    paths = [r"C:\Program Files (x86)\Steam\steamapps\common\UNBEATABLE", r"D:\Program Files (x86)\Steam\steamapps\common\UNBEATABLE"]
    valid_paths = []

    try:
        paths.append(find_steam_path("UNBEATABLE", 2240620))
    except BaseException:
        pass
    for path in paths:
        if os.path.exists(path):
            if os.path.exists(os.path.join(path, "BepInEx/plugins/UnbeatableSongHack")) or os.path.exists(os.path.join(path, "BepInEx/plugins/UnbeatableTranslations")):
                return path

            valid_paths.append(path)

    path = valid_paths[0] if valid_paths else None
    logger.warning("Game installation '%s' may not contain a valid UnbeatableSongHack or UnbeatableTranslations mod installation", path)
    logger.warning("Ensure requisite mods are installed for associated features to work!")
    return path

def get_game_path():
    game_path = None
    os.makedirs(dirs.user_config_dir, exist_ok=True)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
                game_path = config['game_path']
            except BaseException:
                logger.error("Invalid config file '%s' will be overwritten", CONFIG_PATH, exc_info=True)
    except FileNotFoundError:
        pass
    except OSError:
        logger.error("Failed to read config file '%s'!", CONFIG_PATH, exc_info=True)
    if not game_path:
        game_path = find_game_path()
    if not game_path:
        game_path = crossfiledialog.choose_folder()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump({'game_path': game_path}, f)
    return game_path

def get_mod_export_folder():
    if len(sys.argv) >= 2:
        return sys.argv[1]
    else:
        GAME_PATH = get_game_path()
        if os.path.exists(os.path.join(GAME_PATH, "translations_dumped")):
            return os.path.join(GAME_PATH, "translations_dumped")
        return os.path.join(GAME_PATH, "dumped")

def get_working_directory():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys._MEIPASS)
    return os.path.dirname(__file__)
