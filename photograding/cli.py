from __future__ import annotations

import argparse
from pathlib import Path
from .recipe import load_recipe
from .processor import process_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a PhotoGrading JSON recipe to an image")
    sub = parser.add_subparsers(dest="command", required=True)
    process = sub.add_parser("process", help="Process one image")
    process.add_argument("--input", required=True, type=Path)
    process.add_argument("--recipe", required=True, type=Path)
    process.add_argument("--output-dir", default=Path("output"), type=Path)
    args = parser.parse_args()
    if args.command == "process":
        recipe = load_recipe(args.recipe)
        result = process_file(args.input, recipe, args.output_dir)
        print(f"Saved: {result.resolve()}")


if __name__ == "__main__":
    main()
