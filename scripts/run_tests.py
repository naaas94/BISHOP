"""Run each tests/test_*.py in its own pytest process.

Whole-suite ``python -m pytest tests/`` is unreliable: every service under
``services/*/`` ships its own top-level ``app/`` package, and test modules
manipulate ``sys.path`` / ``sys.modules`` to import the right one. In a
single pytest process those collide (for example
``ModuleNotFoundError: No module named 'app.db'``). Per-file isolation is
the only trustworthy measurement of this suite.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _test_files(root: Path, pattern: str | None) -> list[Path]:
    files = sorted((root / "tests").glob("test_*.py"))
    if pattern is not None:
        files = [path for path in files if pattern in path.name]
    return files


def _run_file(root: Path, path: Path) -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(path.relative_to(root))],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run each tests/test_*.py in an isolated pytest process.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a summary line for every file, not only failures.",
    )
    parser.add_argument(
        "-k",
        dest="pattern",
        default=None,
        help="Only run files whose filename contains PATTERN.",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    files = _test_files(root, args.pattern)
    failing = 0

    for path in files:
        rel = path.relative_to(root).as_posix()
        code = _run_file(root, path)
        if code != 0:
            failing += 1
            print(f"FAILED {rel}")
        elif args.verbose:
            print(f"clean  {rel}")

    total = len(files)
    clean = total - failing
    print(f"{total} total / {clean} clean / {failing} failing")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
