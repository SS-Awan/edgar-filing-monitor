from __future__ import annotations

import argparse
from pathlib import Path

from edgar_monitor.dashboard_data import write_dashboard_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate static dashboard data from EDGAR pipeline state."
    )
    parser.add_argument(
        "--curated-directory",
        type=Path,
        default=Path("data/state/curated"),
        help="Directory containing curated Parquet files.",
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=Path("data/state/run_ledger.jsonl"),
        help="Path to the pipeline run ledger.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("site/data/dashboard.json"),
        help="Path for the generated dashboard JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dashboard_data = write_dashboard_data(
        curated_directory=args.curated_directory,
        ledger_path=args.ledger_path,
        output_path=args.output_path,
    )
    print(
        "Dashboard data written: "
        f"{args.output_path} "
        f"({dashboard_data['dataset']['curated_relationships']} relationships)"
    )


if __name__ == "__main__":
    main()