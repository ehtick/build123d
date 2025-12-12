#!/usr/bin/env python3
"""Build both build123d and build123d-vtk wheel variants."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def build_variant(vtk: bool, version: str | None = None):
    """Build a wheel variant. If vtk=True, adds -vtk to name and removes -novtk from dep."""
    pyproject = Path("pyproject.toml")
    original = pyproject.read_text()

    if vtk:
        modified = original
        # Add -vtk to package name: build123d -> build123d-vtk
        modified = re.sub(
            r'^(name\s*=\s*"build123d)"',
            r'\1-vtk"',
            modified,
            flags=re.MULTILINE,
        )
        # Remove -novtk from dependency: cadquery-ocp-novtk -> cadquery-ocp
        modified = re.sub(
            r'"cadquery-ocp-novtk(\s*[><=!~])',
            r'"cadquery-ocp\1',
            modified,
        )
        pyproject.write_text(modified)

    env = os.environ.copy()
    if version:
        env["SETUPTOOLS_SCM_PRETEND_VERSION"] = version

    try:
        subprocess.run([sys.executable, "-m", "build"], check=True, env=env)
    finally:
        if vtk:
            pyproject.write_text(original)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Override version (sets SETUPTOOLS_SCM_PRETEND_VERSION)")
    args = parser.parse_args()

    build_variant(vtk=True, version=args.version)
    build_variant(vtk=False, version=args.version)
