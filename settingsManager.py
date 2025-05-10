from __future__ import print_function
import pygame.constants
import re
import os
import sys
import math
import importlib.util               # ← modern import helper
import engine.controller

try:
    from configparser import ConfigParser as SafeConfigParser
except ImportError:                 # Py-2 fallback (kept for completeness)
    from ConfigParser import SafeConfigParser

# ---------------------------------------------------------------------
# globals
settings = None
sfx_lib  = None
# ---------------------------------------------------------------------
# general helpers
def createPath(_path: str) -> str:
    """
    Build an absolute path rooted at the project directory,
    whether the code is frozen into an executable or not.
    """
    if getattr(sys, "frozen", False):
        datadir = os.path.dirname(sys.executable)
    else:
        datadir = os.path.dirname(__file__)
    return os.path.join(datadir.replace("main.exe", ""), _path)


def importFromURI(_filePath, _uri, _absl=False, _suffix=""):
    """
    Dynamically import a module from a file-path without using the deprecated
    'imp' module.  Returns the imported module or None.
    """
    # resolve relative path
    if not _absl:
        _uri = os.path.normpath(
            os.path.join(os.path.dirname(_filePath).replace("main.exe", ""), _uri)
        )

    path, fname = os.path.split(_uri)
    mname, _ = os.path.splitext(fname)
    target = os.path.join(path, mname + ".py")

    if os.path.exists(target):
        try:
            spec = importlib.util.spec_from_file_location(mname + _suffix, target)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module         # optional, for reload()
                spec.loader.exec_module(module)
                return module
        except Exception as e:
            print(f"{mname}: {e}", file=sys.stderr)
    return None
# ---------------------------------------------------------------------
# public accessors
def getSetting(_key=None):
    global settings
    if settings is None:
        settings = Settings()
    return settings.setting[_key] if _key else settings


def getControls(_playerNum):
    global settings
    if settings is None:
        settings = Settings()

    controls = None
    control_type = settings.setting["controlType_" + str(_playerNum)]

    if control_type != "Keyboard":
        try:
            controls = settings.setting[control_type]
            # carry over timing windows
            tw = settings.setting["controls_" + str(_playerNum)].timing_window
            controls.timing_window = tw
        except KeyError:
            pass

    if controls is None:
        try:
            controls = settings.setting["controls_" + str(_playerNum)]
        except KeyError:
            controls = engine.controller.Controller({})

    return controls


def getSfx():
    global sfx_lib
    if sfx_lib is None:
        sfx_lib = sfx_library()
    return sfx_lib
# ---------------------------------------------------------------------
#                        SETTINGS  CLASS
# ---------------------------------------------------------------------
class Settings(object):
    def __init__(self):
        # build pygame key maps once
        self.key_id_map   = {}
        self.key_name_map = {}
        for name, value in vars(pygame.constants).items():
            if name.startswith("K_"):
                self.key_id_map[value]      = name.lower()
                self.key_name_map[name.lower()] = value

        self.parser = SafeConfigParser()

        if getattr(sys, "frozen", False):
            self.datadir = os.path.dirname(sys.executable)
        else:
            self.datadir = os.path.dirname(__file__)

        ini_path = os.path.join(self.datadir.replace("main.exe", ""),
                                "settings", "settings.ini")
        self.parser.read(ini_path)

        self.setting = {}
        # ---------------- window ----------------
        self.setting["windowName"]   = getString(self.parser, "window", "windowName")
        self.setting["windowWidth"]  = getNumber(self.parser, "window", "windowWidth")
        self.setting["windowHeight"] = getNumber(self.parser, "window", "windowHeight")
        self.setting["frameCap"]     = getNumber(self.parser, "window", "frameCap")
        self.setting["windowSize"]   = [
            self.setting["windowWidth"],
            self.setting["windowHeight"],
        ]
        # ---------------- sound -----------------
        self.setting["music_volume"] = (
            getNumber(self.parser, "sound", "music_volume") / 100.0
        )
        self.setting["sfxVolume"]    = (
            getNumber(self.parser, "sound", "sfxVolume") / 100.0
        )
        # ------------- graphics flags ----------
        self.setting["showHitboxes"]      = getBoolean(self.parser, "graphics", "displayHitboxes")
        self.setting["showHurtboxes"]     = getBoolean(self.parser, "graphics", "displayHurtboxes")
        self.setting["showSpriteArea"]    = getBoolean(self.parser, "graphics", "displaySpriteArea")
        self.setting["showPlatformLines"] = getBoolean(self.parser, "graphics", "displayPlatformLines")
        self.setting["showECB"]           = getBoolean(self.parser, "graphics", "displayECB")
        # ------------- network -----------------
        self.setting["networkEnabled"]          = getBoolean(self.parser, "network", "enabled")
        self.setting["networkProtocol"]         = getString(self.parser,  "network", "protocol")
        self.setting["networkServerIP"]         = getString(self.parser,  "network", "serverip")
        self.setting["networkServerPort"]       = getNumber(self.parser,  "network", "serverport")
        self.setting["networkUDPClientPortMin"] = getNumber(self.parser,  "network", "udpclientportmin")
        self.setting["networkUDPClientPortMax"] = getNumber(self.parser,  "network", "udpclientportmax")
        self.setting["networkBufferSize"]       = getNumber(self.parser,  "network", "buffersize")
        # ------------- player colours ----------
        for p in range(4):
            self.setting[f"playerColor{p}"] = getString(
                self.parser, "playerColors", f"player{p}"
            )
        # ------------- rule preset -------------
        presets = [
            os.path.splitext(f)[0]
            for f in os.listdir(os.path.join(self.datadir, "settings", "rules"))
            if f.endswith(".ini")
        ]
        self.setting["presetLists"] = presets
        selected = self.parser.get("game", "rulePreset")
        self.new_gamepads = []
        self.loadGameSettings(selected)
        self.loadControls()

    # -----------------------------------------------------------------
    def loadGameSettings(self, _presetSuf):
        path = os.path.join(self.datadir, "settings", "rules", _presetSuf + ".ini")
        pset = SafeConfigParser()
        pset.read(path)

        preset = "preset_" + _presetSuf
        self.setting["current_preset"] = _presetSuf

        # multipliers --------------------------------------------------
        def mult(k):
            return float(getNumber(pset, preset, k)) / 100.0

        for k in (
            "gravityMultiplier",
            "weightMultiplier",
            "frictionMultiplier",
            "airControlMultiplier",
            "hitstunMultiplier",
            "hitlagMultiplier",
            "shieldStunMultiplier",
        ):
            self.setting[k[:-10] if k.endswith("Multiplier") else k] = mult(k)

        # ledge settings ----------------------------------------------
        self.setting["ledgeConflict"] = getString(pset, preset, "ledgeConflict")
        sweet_dict = {"large": (128, 128), "medium": (64, 64), "small": (32, 32)}
        self.setting["ledgeSweetspotSize"] = sweet_dict[
            getString(pset, preset, "ledgeSweetspotSize")
        ]
        for k in (
            "ledgeSweetspotForwardOnly",
            "teamLedgeConflict",
            "regrabInvincibility",
        ):
            self.setting[k] = getBoolean(pset, preset, k)

        for k in (
            "ledgeInvincibilityTime",
            "slowLedgeWakeupThreshold",
            "respawnDowntime",
            "respawnLifetime",
            "respawnInvincibility",
            "airDodgeLag",
        ):
            self.setting[k] = int(getNumber(pset, preset, k))

        # misc ---------------------------------------------------------
        self.setting["airDodgeType"]      = getString(pset, preset, "airDodgeType")
        self.setting["freeDodgeSpecialFall"] = getBoolean(pset, preset, "freeDodgeSpecialFall")
        self.setting["enableWavedash"]    = getBoolean(pset, preset, "enableWavedash")
        self.setting["lagCancel"]         = getString(pset, preset, "lagCancel")

    # -----------------------------------------------------------------
    def loadControls(self):
        player_num = 0
        self.getGamepadList(True)

        while self.parser.has_section(f"controls_{player_num}"):
            group = f"controls_{player_num}"
            bindings = {}
            control_type = self.parser.get(group, "controlType")
            self.setting[f"controlType_{player_num}"] = (
                control_type if control_type in self.setting else "Keyboard"
            )

            timing_window = {
                "smash_window":   int(self.parser.get(group, "smash_window",   fallback=4)),
                "repeat_window":  int(self.parser.get(group, "repeat_window",  fallback=8)),
                "buffer_window":  int(self.parser.get(group, "buffer_window",  fallback=8)),
                "smoothing_window": int(self.parser.get(group, "smoothing_window", fallback=64)),
            }

            for opt in self.parser.options(group):
                if opt in self.key_name_map:
                    bindings[self.key_name_map[opt]] = self.parser.get(group, opt)

            self.setting[group] = engine.controller.Controller(bindings, timing_window)
            player_num += 1

    # -----------------------------------------------------------------
    #  (game-pad helpers unchanged, but .items() replaces .iteritems())
    # -----------------------------------------------------------------
    def loadGamepad(self, _controllerName):
        pygame.joystick.init()
        parser = SafeConfigParser()
        parser.read(os.path.join(self.datadir, "settings", "gamepads.ini"))

        joystick = next(
            (pygame.joystick.Joystick(i)
             for i in range(pygame.joystick.get_count())
             if pygame.joystick.Joystick(i).get_name() == _controllerName),
            None,
        )
        if joystick:
            joystick.init()
            jid = joystick.get_id()
        else:
            jid = None

        if parser.has_section(_controllerName):
            axes = {
                int(opt[1:]): tuple(parser.get(_controllerName, opt)[1:-1].split(","))
                for opt in parser.options(_controllerName) if opt.startswith("a")
            }
            buttons = {
                int(opt[1:]): parser.get(_controllerName, opt)
                for opt in parser.options(_controllerName) if opt.startswith("b")
            }
        else:
            axes, buttons = {}, {}

        pad_bindings = engine.controller.PadBindings(_controllerName, jid, axes, buttons)
        return engine.controller.GamepadController(pad_bindings)

    # ... (getGamepadList and getGamepadByName remain the same, but use .items())

# ---------------------------------------------------------------------
#  Saving helpers (iteritems → items, tuple keys for sweetSpotDict, etc.)
# ---------------------------------------------------------------------
def saveSettings(_settings):
    key_id_map = {
        v: k.lower() for k, v in vars(pygame.constants).items() if k.startswith("K_")
    }

    parser = SafeConfigParser()
    # window
    parser.add_section("window")
    parser.set("window", "windowName", _settings["windowName"])
    parser.set("window", "windowSize", str(_settings["windowSize"]))
    parser.set("window", "windowWidth", str(_settings["windowSize"][0]))
    parser.set("window", "windowHeight", str(_settings["windowSize"][1]))
    parser.set("window", "frameCap", str(_settings["frameCap"]))
    # sound
    parser.add_section("sound")
    parser.set("sound", "music_volume", str(_settings["music_volume"] * 100))
    parser.set("sound", "sfxVolume", str(_settings["sfxVolume"] * 100))
    # graphics
    parser.add_section("graphics")
    for key in (
        ("displayHitboxes", "showHitboxes"),
        ("displayHurtboxes", "showHurtboxes"),
        ("displaySpriteArea", "showSpriteArea"),
        ("displayPlatformLines", "showPlatformLines"),
        ("displayECB", "showECB"),
    ):
        parser.set("graphics", key[0], str(_settings[key[1]]))
    # player colours
    parser.add_section("playerColors")
    for p in range(4):
        parser.set("playerColors", f"player{p}", str(_settings[f"playerColor{p}"]))
    # game
    parser.add_section("game")
    parser.set("game", "rulePreset", _settings["current_preset"])
    # controls
    for i in range(4):
        sect = f"controls_{i}"
        parser.add_section(sect)
        parser.set(sect, "controlType", _settings[f"controlType_{i}"])
        for key, val in _settings[sect].key_bindings.items():
            parser.set(sect, key_id_map[key], str(val))
        for k, v in _settings[sect].timing_window.items():
            parser.set(sect, k, str(v))

    cfg = os.path.join(getSetting().datadir, "settings", "settings.ini")
    with open(cfg, "w", buffering=1) as fp:
        parser.write(fp)

    saveGamepad(_settings)


def saveGamepad(_settings):
    parser = SafeConfigParser()
    for controller_name in getSetting().getGamepadList():
        gamepad = getSetting(controller_name)
        if not parser.has_section(controller_name):
            parser.add_section(controller_name)

        for key, value in gamepad.key_bindings.axis_bindings.items():
            neg, pos = value
            parser.set(controller_name, f"a{key}",
                       f"({neg or 'none'},{pos or 'none'})")

        for key, value in gamepad.key_bindings.button_bindings.items():
            parser.set(controller_name, f"b{key}", str(value))

    fp = os.path.join(getSetting().datadir, "settings", "gamepads.ini")
    with open(fp, "w", buffering=1) as f:
        parser.write(f)

# ---------------------------------------------------------------------
# preset save (tuple keys)
def savePreset(_settings, _preset):
    parser = SafeConfigParser()
    if not parser.has_section(_preset):
        parser.add_section(_preset)

    mul = lambda k: str(_settings[k] * 100)
    for k in (
        "gravity", "weight", "friction", "airControl",
        "hitstun", "hitlag", "shieldStun"
    ):
        parser.set(_preset, k + "Multiplier", mul(k))

    parser.set(_preset, "ledgeConflict", _settings["ledgeConflict"])
    sweet = {(128, 128): "large", (64, 64): "medium", (32, 32): "small"}
    parser.set(_preset, "ledgeSweetspotSize",
               sweet[tuple(_settings["ledgeSweetspotSize"])])
    for k in (
        "ledgeSweetspotForwardOnly", "teamLedgeConflict",
        "regrabInvincibility"
    ):
        parser.set(_preset, k, str(_settings[k]))

    for k in (
        "ledgeInvincibilityTime", "slowLedgeWakeupThreshold",
        "airDodgeType", "freeDodgeSpecialFall", "enableWavedash"
    ):
        parser.set(_preset, k, str(_settings[k]))

    fp = os.path.join(_settings.datadir, "settings", "rules", _preset + ".ini")
    with open(fp, "w", buffering=1) as f:
        parser.write(f)
# ---------------------------------------------------------------------
# SFX LIBRARY (unchanged except for .has_key → in)
class sfx_library(object):
    supported_file_types = (".wav", ".ogg")

    def __init__(self):
        self.sounds = {}
        self.initializeLibrary()

    def initializeLibrary(self):
        self.sounds = {}
        directory = createPath("sfx")
        for f in os.listdir(directory):
            root, ext = os.path.splitext(f)
            if ext in self.supported_file_types:
                self.sounds["base_" + root] = pygame.mixer.Sound(
                    os.path.join(directory, f)
                )

    def playSound(self, _name, _category="base"):
        name = f"{_category}_{_name}"
        if name in self.sounds:
            snd = self.sounds[name]
            snd.set_volume(getSetting().setting["sfxVolume"])
            snd.play()

    def hasSound(self, _name, _category):
        return f"{_category}_{_name}" in self.sounds

    def addSoundsFromDirectory(self, _path, _category):
        for f in os.listdir(_path):
            root, ext = os.path.splitext(f)
            if ext in self.supported_file_types:
                self.sounds[f"{_category}_{root}"] = pygame.mixer.Sound(
                    os.path.join(_path, f)
                )
# ---------------------------------------------------------------------
# misc helpers (unchanged, but has_key removed)
def getNumbersFromString(_string, _many=False):
    return list(map(int, re.findall(r"\d+", _string))) if _many else int(
        re.search(r"\d+", _string).group()
    )


def boolean(_string):  # noqa: N802
    return _string.lower() in (
        "true","t","1","#t","y","yes","on","enabled"
    )


def getString(_parser, _preset, _key):
    try:
        return _parser.get(_preset, _key).lower()
    except Exception as e:
        print(e)
        return ""


def getBoolean(_parser, _preset, _key):
    try:
        return boolean(_parser.get(_preset, _key))
    except Exception as e:
        print(e)
        return False


def getNumber(_parser, _preset, _key, _islist=False):
    try:
        return getNumbersFromString(_parser.get(_preset, _key), _islist)
    except Exception as e:
        print(e)
        return 0


def test():
    print(getSetting().setting)  # simple sanity check


def getXYFromDM(_direction, _magnitude):
    rad = math.radians(_direction)
    return round(math.cos(rad) * _magnitude, 5), -round(
        math.sin(rad) * _magnitude, 5
    )


if __name__ == "__main__":
    test()
