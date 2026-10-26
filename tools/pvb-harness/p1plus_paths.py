"""Canonical research model identity and repository/package library locations."""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
P1PLUS_BASELINE_ID = 'p1plus-2026-10-26'
P1PLUS_FLAGS = 6


def default_library(control='hq'):
    """Prefer repository build output, retaining the original standalone bundle."""
    filename = 'pvbcapi.dll' if os.name == 'nt' else 'libpvbcapi.so'
    repository = HERE / 'build' / filename if control == 'hq' else HERE / 'build' / control / filename
    package = HERE.parents[2] / 'windows-x64' / control / 'pvbcapi.dll'
    return repository if repository.is_file() or not package.is_file() else package
