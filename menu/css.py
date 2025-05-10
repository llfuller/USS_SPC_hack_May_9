import settingsManager
import spriteManager
import os
import pygame
import battle
import sys
import stages.true_arena as stage
import engine.cpuPlayer as cpuPlayer
import engine.abstractFighter as abstractFighter
import sss
import musicManager


class CSSScreen:
    def __init__(self, _rules=None):
        settings = settingsManager.getSetting().setting

        self.rules = _rules
        self.height = settings["windowHeight"]
        self.width = settings["windowWidth"]

        pygame.init()
        screen = pygame.display.get_surface()

        background = pygame.Surface(screen.get_size())
        background = background.convert()

        clock = pygame.time.Clock()
        self.player_controls = []
        self.player_panels = []

        # ------------------------------------------------------------------
        for i in range(4):
            self.player_controls.append(settingsManager.getControls(i))
            self.player_panels.append(PlayerPanel(i))
            # let the panels receive inputs
            self.player_controls[i].linkObject(self.player_panels[i])
            self.player_controls[i].flushInputs()
        # ------------------------------------------------------------------

        status = 0

        while status == 0:
            music = musicManager.getMusicManager()
            music.doMusicEvent()
            if not music.isPlaying():
                music.rollMusic("menu")

            # ---------------- event loop ----------------------------------
            for bindings in self.player_controls:
                bindings.passInputs()

            for event in pygame.event.get():
                for bindings in self.player_controls:
                    k = bindings.getInputs(event)
                    if k == "attack":
                        if self.checkForSelections():
                            sss.StageScreen(self.rules, self.getFightersFromPanels())
                            # reset panels
                            for panel in self.player_panels:
                                panel.active_object = panel.wheel
                                panel.chosen_fighter = None
                                panel.bg_surface = None
                            for i in range(4):
                                self.player_controls[i].linkObject(self.player_panels[i])
                                self.player_controls[i].flushInputs()

                if event.type == pygame.QUIT:
                    status = -1
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    status = 1
            # --------------------------------------------------------------

            screen.fill((128, 128, 128))
            for panel in self.player_panels:
                panel.update()
                panel.draw(screen)

            pygame.display.flip()
            clock.tick(60)

    # ----------------------------------------------------------------------
    def checkForSelections(self):
        """All active panels must have a fighter chosen, and at least one panel must be active."""
        if not any(p.active for p in self.player_panels):
            return False
        return all(p.chosen_fighter is not None for p in self.player_panels)

    def getFightersFromPanels(self):
        return [p.chosen_fighter for p in self.player_panels if p.active]


# ==========================================================================
#   Widgets
# ==========================================================================
class CSSWidget:
    def __init__(self, _panel, _displayList, _choicesList):
        self.previous_widget = None
        self.next_widget = None
        self.panel = _panel
        self.choices = [(key, _choicesList[i]) for i, key in _displayList]

    def onConfirm(self):
        pass

    def draw(self):
        pass


# ==========================================================================
#   Fighter Wheel
# ==========================================================================
class FighterWheel:
    def __init__(self, _playerNum):
        self.fighters = []

        # ------------------------------------------------------------------
        directory = settingsManager.createPath("fighters")
        fighter_count = 0
        for subdir in next(os.walk(directory))[1]:
            if subdir == "__pycache__":
                continue

            fighter_py = settingsManager.importFromURI(
                directory, os.path.join(directory, subdir, "fighter.py"), _suffix=str(fighter_count)
            )
            if fighter_py:
                fighter = fighter_py.getFighter(os.path.join(directory, subdir), _playerNum)
            else:
                fighter = abstractFighter.AbstractFighter(os.path.join(directory, subdir), _playerNum)

            if fighter is None:
                print("No fighter found at", os.path.join(directory, subdir, "fighter.py"))
            else:
                fighter_count += 1
                self.fighters.append(fighter)
        # ------------------------------------------------------------------

        self.current_index = 0
        self.current_fighter = self.fighters[0]
        self.wheel_size = 9
        self.visible_sprites = [None] * self.wheel_size
        self.animateWheel()
        self.wheel_shadow = spriteManager.ImageSprite(
            settingsManager.createPath(os.path.join("sprites", "cssbar_shadow.png"))
        )
        self.fill_color = "#000000"

    # ----------------------------------------------------------------------
    def setFillColor(self, _color):
        self.wheel_shadow.recolor(
            self.wheel_shadow.image, pygame.Color(self.fill_color), pygame.Color(_color)
        )
        self.fill_color = _color

    def changeSelected(self, _increment):
        self.current_index = (self.current_index + _increment) % len(self.fighters)
        self.current_fighter = self.fighters[self.current_index]
        self.animateWheel()

    def fighterAt(self, _offset):
        return self.fighters[(self.current_index + _offset) % len(self.fighters)]

    def animateWheel(self):
        self.visible_sprites[0] = self.fighterAt(0).css_icon
        for i in range(1, (self.wheel_size // 2) + 1):
            self.visible_sprites[2 * i - 1] = self.fighterAt(i).css_icon
            self.visible_sprites[2 * i] = self.fighterAt(-i).css_icon

        [spriteManager.ImageSprite.alpha(s, 128) for s in self.visible_sprites]
        self.visible_sprites[0].alpha(255)

    def draw(self, _screen, _location):
        center = 112
        blank = pygame.Surface((256, 32), pygame.SRCALPHA).convert_alpha()
        blank.blit(self.visible_sprites[0].image, (center, 0))
        for i in range(1, (self.wheel_size // 2) + 1):
            blank.blit(self.visible_sprites[2 * i - 1].image, (center + 32 * i, 0))
            blank.blit(self.visible_sprites[2 * i].image, (center - 32 * i, 0))

        blank.blit(self.wheel_shadow.image, (0, 0))
        _screen.blit(blank, _location)


# ==========================================================================
#   Player Panel
# ==========================================================================
class PlayerPanel(pygame.Surface):
    def __init__(self, _playerNum):
        super().__init__(
            (
                settingsManager.getSetting("windowWidth") // 2,
                settingsManager.getSetting("windowHeight") // 2,
            )
        )

        self.keys = settingsManager.getControls(_playerNum)
        self.player_num = _playerNum
        self.wheel = FighterWheel(_playerNum)
        self.active = False
        self.ready = False
        self.active_object = self.wheel
        self.chosen_fighter = None
        self.myBots = []

        self.wheel_increment = 0
        self.hold_time = 0
        self.hold_distance = 0
        self.wheel_offset = [
            (self.get_width() - 256) // 2,
            (self.get_height() - 32),
        ]
        self.bg_surface = None
        self.current_color = _playerNum
        self.current_costume = 0

        self.icon = spriteManager.ImageSprite(
            settingsManager.createPath("sprites/default_franchise_icon.png")
        )
        self.icon.rect.center = self.get_rect().center
        self.icon_color = pygame.Color("#cccccc")

        self.fill_color = "#000000"
        self.wheel.setFillColor(self.fill_color)

        self.recolorIcon()

    # ----------------------------------------------------------------------
    def update(self):
        if self.wheel_increment != 0:
            if self.hold_time > self.hold_distance:
                if self.hold_distance == 0:
                    self.hold_distance = 30
                elif self.hold_distance == 30:
                    self.hold_distance = 20
                elif self.hold_distance == 20:
                    self.hold_distance = 10
                settingsManager.getSfx().playSound("selectL")

                self.wheel.changeSelected(self.wheel_increment)

                self.current_color = self.player_num
                self.recolorIcon(True)

                self.icon = self.wheel.fighterAt(0).franchise_icon
                self.icon.rect.center = self.get_rect().center
                self.recolorIcon()
                self.hold_time = 0
            else:
                self.hold_time += 1

        if self.bg_surface and self.bg_surface.get_alpha() > 128:
            self.bg_surface.set_alpha(self.bg_surface.get_alpha() - 10)

    # ----------------------------------------------------------------------
    def keyPressed(self, _key):
        if _key != "special" and not self.active:
            self.active = True
            return

        if _key == "special" and self.active:
            if self.myBots:
                pass  # TODO: disable bots
            elif self.active_object == self.wheel:
                self.active = False
                return
            else:
                self.active_object = self.wheel
                self.chosen_fighter = None
                self.bg_surface = None
                return

        if _key == "left" and self.active_object == self.wheel:
            self.wheel_increment = -1
        elif _key == "right" and self.active_object == self.wheel:
            self.wheel_increment = 1
        elif _key == "attack" and self.active_object == self.wheel:
            self.bg_surface = self.copy()
            self.bg_surface.set_alpha(240)
            self.recolorIcon(True)
            self.recolorIcon()
            self.active_object = None
            self.chosen_fighter = self.wheel.fighterAt(0)
            self.chosen_fighter.current_color = self.current_color
            self.chosen_fighter.current_costume = self.current_costume
        elif _key == "jump":
            self.current_color += 1
            self.recolorIcon()
        elif _key == "shield":
            self.current_costume += 1

    def keyReleased(self, _key):
        if _key in ("right", "left"):
            self.wheel_increment = 0
            self.hold_distance = 0
            self.hold_time = 0

    # ----------------------------------------------------------------------
    def draw(self, _screen):
        if self.active:
            self.fill(pygame.Color(self.fill_color))
            if self.bg_surface:
                self.blit(self.bg_surface, (0, 0))
            else:
                self.wheel.draw(self, self.wheel_offset)
                self.icon.draw(self, self.icon.rect.topleft, 1.0)
        else:
            self.fill(
                pygame.Color(settingsManager.getSetting(f"playerColor{self.player_num}"))
            )
            # TODO: draw closed shutter

        offset = [0, 0]
        if self.player_num in (1, 3):
            offset[0] = self.get_width()
        if self.player_num in (2, 3):
            offset[1] = self.get_height()
        _screen.blit(self, offset)

    # ----------------------------------------------------------------------
    def recolorIcon(self, _reset=False):
        if _reset:
            self.icon.recolor(self.icon.image, self.icon_color, pygame.Color("#cccccc"))
            self.icon_color = pygame.Color("#cccccc")
        else:
            display_color = self.wheel.fighterAt(0).palette_display
            new_color = display_color[self.current_color % len(display_color)]

            # prevent icon from blending into its panel
            if new_color == pygame.Color(self.fill_color):
                new_color = pygame.Color("#cccccc")

            self.icon.recolor(self.icon.image, self.icon_color, new_color)
            self.icon_color = new_color
