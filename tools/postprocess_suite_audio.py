from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audio_postprocess import apply_postprocess_file
from tools.eval_runner import load_suite


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic postprocessing to a suite's audio files.")
    parser.add_argument("--suite", required=True, help="Suite id under eval_set/suites/")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite audio in-place")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases processed")
    args = parser.parse_args(argv)

    suite_dir, cases = load_suite(args.suite)
    selected = cases[: max(0, int(args.limit))] if args.limit is not None else cases

    applied = 0
    skipped = 0
    results: list[dict[str, Any]] = []

    for c in selected:
        cfg = getattr(c, "postprocess", None)
        if not isinstance(cfg, dict) or not cfg:
            skipped += 1
            continue
        if args.dry_run:
            results.append({"case_id": c.case_id, "audio_path": str(c.audio_path), "postprocess": cfg, "dry_run": True})
            applied += 1
            continue
        r = apply_postprocess_file(c.audio_path, cfg, overwrite=bool(args.overwrite))
        r["case_id"] = c.case_id
        results.append(r)
        if r.get("applied"):
            applied += 1
        else:
            skipped += 1

    print(
        json.dumps(
            {
                "suite_id": args.suite,
                "suite_path": str(suite_dir),
                "applied": applied,
                "skipped": skipped,
                "results": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
