"""Functions to prepare source files for refactoring with CST.
"""

from contextlib import contextmanager
from libcst import parse_module


@contextmanager
def module(path: str, mode: str = "r"):
    file = open(path, mode)
    try:
        yield parse_module(parse_module(file.readall()))
    finally:
        file.close()
