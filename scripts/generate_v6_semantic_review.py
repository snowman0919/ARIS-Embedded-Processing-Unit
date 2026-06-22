#!/usr/bin/env python3
"""Generate and validate an advisory-only V6 semantic review report."""

from __future__ import annotations

import argparse
from pathlib import Path

from aris_ai_semantics.review_report import (
    generate_review_report,
    load_review_inputs,
    validate_review_report,
    write_review_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = generate_review_report(load_review_inputs(args.manifest, args.compare))
    failures = validate_review_report(report)
    write_review_report(report, args.out)
    summary = report["summary"]
    print(
        "v6_semantic_review path={} advisory_only={} control_authority={} "
        "review_items={} events={} high_risk_cells={} label_changes={}".format(
            args.out,
            report["advisory_only"],
            report["control_authority"],
            summary["review_item_count"],
            summary["event_count"],
            summary["high_risk_cells"],
            summary["label_changes"],
        )
    )
    if failures:
        raise SystemExit("; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
