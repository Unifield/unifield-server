# -*- coding: utf-8 -*-
import os
import importlib
import sys

__all__ = ['addons']

with importlib.resources.as_file(importlib.resources.files('openobject').joinpath('..')) as ROOT_PATH:
    ADDONS_PATH = os.path.join(ROOT_PATH, 'addons')
    assert os.path.isdir(ADDONS_PATH), "Unable to locate addons."

    sys.path.insert(0, ADDONS_PATH)

    def addons(*sections): return os.path.join(ADDONS_PATH, *sections)
    def root(*sections): return os.path.join(ROOT_PATH, *sections)
