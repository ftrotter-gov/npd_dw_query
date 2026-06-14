#!/usr/bin/env python3
"""Bulk-generate IDR extract scripts from cached JSON metadata.

This script implements the TODO originally noted in `make_all.sh`.

Behavior
--------
- For each `*.json` file in the configured JSON directory:
  - create an output directory under the configured output base, named after the
    JSON filename stem
    (e.g. `mdcr_prvdr.json` -> `<output_base>/mdcr_prvdr/`)
  - run `make_extract_scripts_from_json.py <json> <output_dir>`

The script is careful about paths so it works regardless of the current working
directory you run it from.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _default_json_dir(script_dir: Path) -> Path:
    return script_dir / "gen_extract_scripts" / "json_documentation_cache"


def _default_generator_script(script_dir: Path) -> Path:
    return script_dir / "gen_extract_scripts" / "make_extract_scripts_from_json.py"


def _should_skip_json(json_file: Path) -> bool:
    """Skip non-cache JSON files that live in the cache directory.

    The cache dir should ideally only contain discovery outputs, but in practice
    other JSON files may appear. The generator expects a specific schema
    containing `metadata` + `tables`.
    """
    name = json_file.name
    return name.startswith("test_") or name.startswith("sample_")


def iter_json_files(json_dir: Path) -> list[Path]:
    # stable ordering for deterministic results
    return sorted(p for p in json_dir.glob("*.json") if p.is_file() and not _should_skip_json(p))


def run_generator(*, python_exe: str, generator_script: Path, json_file: Path, output_dir: Path, dry_run: bool) -> None:
    cmd = [python_exe, str(generator_script), str(json_file), str(output_dir)]
    print("$ " + " ".join(cmd))
    if dry_run:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    # Run with a stable cwd so relative imports in the generator (asset_template.py)
    # always resolve as expected.
    subprocess.run(cmd, check=True, cwd=str(generator_script.parent))


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    dw_integrations_dir = script_dir.parent
    output_base_default = dw_integrations_dir / "idr"

    parser = argparse.ArgumentParser(
        description="Generate IDR extract scripts for every JSON metadata file in a directory",
    )
    # Primary interface: positional args
    parser.add_argument(
        "json_dir",
        type=Path,
        nargs="?",
        default=_default_json_dir(script_dir),
        help="Directory containing *.json metadata files",
    )
    parser.add_argument(
        "output_base",
        type=Path,
        nargs="?",
        default=output_base_default,
        help="Base directory under which per-json subdirectories will be created",
    )
    # Backwards-compatible named args (aliases)
    parser.add_argument(
        "--json-dir",
        dest="json_dir_opt",
        type=Path,
        default=None,
        help="Alias for positional json_dir",
    )
    parser.add_argument(
        "--output-base",
        dest="output_base_opt",
        type=Path,
        default=None,
        help="Alias for positional output_base",
    )
    parser.add_argument(
        "--generator",
        type=Path,
        default=_default_generator_script(script_dir),
        help="Path to make_extract_scripts_from_json.py (default: %(default)s)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use (default: current interpreter)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands and planned output dirs without generating files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N JSON files (useful for testing)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include sample/test JSON files if they exist in the json-dir",
    )

    args = parser.parse_args()

    json_dir: Path = (args.json_dir_opt or args.json_dir).expanduser().resolve()
    generator_script: Path = args.generator.expanduser().resolve()
    output_base: Path = (args.output_base_opt or args.output_base).expanduser().resolve()

    if not json_dir.exists():
        raise SystemExit(f"json-dir does not exist: {json_dir}")
    if not generator_script.exists():
        raise SystemExit(f"generator script not found: {generator_script}")

    json_files = sorted(p.resolve() for p in json_dir.glob("*.json") if p.is_file())
    if not args.include_tests:
        json_files = [p for p in json_files if not _should_skip_json(p)]
    # stable ordering for deterministic results
    json_files = sorted(json_files)
    if args.limit is not None:
        json_files = json_files[: max(0, args.limit)]

    if not json_files:
        print(f"No JSON files found in {json_dir}")
        return 0

    print("Bulk IDR extract script generation")
    print("================================")
    print(f"JSON dir:       {json_dir}")
    print(f"Output base:    {output_base}")
    print(f"Generator:      {generator_script}")
    print(f"Python:         {args.python}")
    print(f"Dry-run:        {args.dry_run}")
    print(f"Files to process: {len(json_files)}")
    print("")

    failures: list[tuple[Path, str]] = []

    for json_file in json_files:
        # Ensure the generator receives absolute paths, since we run it with a
        # different cwd to make its relative imports work.
        json_file = json_file.resolve()
        out_dir = (output_base / json_file.stem).resolve()
        try:
            run_generator(
                python_exe=args.python,
                generator_script=generator_script,
                json_file=json_file,
                output_dir=out_dir,
                dry_run=args.dry_run,
            )
        except subprocess.CalledProcessError as e:
            failures.append((json_file, f"exit={e.returncode}"))
        except Exception as e:  # pragma: no cover
            failures.append((json_file, str(e)))

    if failures:
        print("\nFailures:")
        for jf, err in failures:
            print(f"- {jf.name}: {err}")
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
