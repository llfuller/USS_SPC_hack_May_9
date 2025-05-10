#!/usr/bin/env python
from __future__ import print_function
import pygame
import importlib.util          # ← use this instead of imp
import os
import sys
import traceback
from pygame.locals import *
from engine import *
from builder import *
from fighters import *
from menu import *
from stages import *
import menu.mainMenu


def main(debug=False):
    try:
        sys.stderr.write("\n")
        sys.stderr.flush()
    except IOError:
        class dummyStream:
            def write(self, _):  pass
            def read(self, _):   pass
            def flush(self):     pass
            def close(self):     pass
        sys.stdout = dummyStream()
        sys.stderr = open("errors.txt", "w", buffering=1)
        sys.stdin  = dummyStream()
        sys.__stdout__ = sys.stdout
        sys.__stderr__ = sys.stderr
        sys.__stdin__  = sys.stdin
    menu.mainMenu.Menu()


def importFromURI(filePath, uri, absl=False, _suffix=""):
    """Dynamically load a .py file as a module—without using the deprecated imp."""
    if not absl:
        uri = os.path.normpath(
            os.path.join(os.path.dirname(filePath).replace("main.exe", ""), uri)
        )

    path, fname = os.path.split(uri)
    mname, _ = os.path.splitext(fname)          # strip extension
    no_ext = os.path.join(path, mname)
    target = no_ext + ".py"

    if os.path.exists(target):
        try:
            spec = importlib.util.spec_from_file_location(mname + _suffix, target)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module  # optional: allows reload() later
                spec.loader.exec_module(module)
                return module
        except Exception as e:
            print(f"{mname}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main(True)
