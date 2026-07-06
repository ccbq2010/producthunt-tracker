"""Product Hunt Trend Tracker — track daily/weekly trends on Product Hunt."""

import argparse
import logging
import os
import sys

import yaml

from src.analyzer import Analyzer
from src.fetcher import ProductHuntFetcher
from src.notifier import Notifier
from src.reporter import Reporter
from src.storage import Storage

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(config_path: str = "config/settings.yml") -> dict:
    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}")
        print(f"Copy config/settings.example.yml to {config_path} and fill in your values.")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_fetch(args, config: dict):
    """Fetch latest data from Product Hunt and store it."""
    fetcher = ProductHuntFetcher(
        token=config["token"],
        timeout=config.get("fetch", {}).get("timeout", 15),
    )
    storage = Storage(config["database"]["path"])

    topics = config.get("topics", [])
    limit = config.get("fetch", {}).get("max_items_per_topic", 20)

    logger.info(f"Fetching {len(topics)} topics...")
    posts = fetcher.fetch_all_topics(topics, limit)
    storage.upsert_posts(posts)
    storage.cleanup_old_snapshots()
    storage.close()

    print(f"✓ Fetched {len(posts)} unique posts across {len(topics)} topics")
    print(f"  Database: {config['database']['path']}")


def cmd_report(args, config: dict):
    """Generate a trend report from stored data."""
    period = args.period or config.get("report", {}).get("frequency", "day")
    hours = 24 if period == "day" else 168

    storage = Storage(config["database"]["path"])
    analyzer = Analyzer(
        min_votes=config.get("analysis", {}).get("min_votes", 50),
        top_n=config.get("analysis", {}).get("top_n", 10),
    )
    reporter = Reporter(output_dir=config.get("notify", {}).get("file", {}).get("path", "data/reports/"))
    notifier = Notifier(config)

    trending = storage.get_trending(hours=hours, limit=50)
    trending = analyzer.rank_trending(trending)

    velocity_days = 1 if period == "day" else 7
    velocity = storage.get_velocity(days=velocity_days, limit=10)

    topic_dist = storage.get_topic_distribution(hours=hours)
    cat_analysis = analyzer.analyze_categories(topic_dist)

    report_data = analyzer.build_report_data(trending, velocity, cat_analysis, period)

    md = reporter.render_markdown(report_data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✓ Report saved to {args.output}")

    notifier.send(report_data, md)
    storage.close()

    if args.print:
        print()
        print(md)


def cmd_run(args, config: dict):
    """Fetch + generate report in one go."""
    cmd_fetch(args, config)
    cmd_report(args, config)


def cmd_web(args, config: dict):
    """Launch web dashboard."""
    from src.web import serve
    port = args.port or 8000
    serve(db_path=config["database"]["path"], port=port)


def main():
    parser = argparse.ArgumentParser(description="Product Hunt Trend Tracker")
    parser.add_argument("-c", "--config", default="config/settings.yml",
                        help="Path to config file (default: config/settings.yml)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Fetch latest data from PH")

    # report
    p_report = subparsers.add_parser("report", help="Generate trend report")
    p_report.add_argument("-p", "--period", choices=["day", "week"],
                          help="Report period (overrides config)")
    p_report.add_argument("-o", "--output", help="Save report to file")
    p_report.add_argument("--print", action="store_true",
                          help="Print report to stdout")

    # run (fetch + report)
    p_run = subparsers.add_parser("run", help="Fetch data and generate report")
    p_run.add_argument("-p", "--period", choices=["day", "week"],
                       help="Report period (overrides config)")
    p_run.add_argument("-o", "--output", help="Save report to file")
    p_run.add_argument("--print", action="store_true",
                       help="Print report to stdout")

    # web
    p_web = subparsers.add_parser("web", help="Launch web dashboard")
    p_web.add_argument("-p", "--port", type=int, default=8000,
                       help="Port to listen on (default: 8000)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    setup_logging(args.verbose)
    config = load_config(args.config)

    dispatch = {
        "fetch": cmd_fetch,
        "report": cmd_report,
        "run": cmd_run,
        "web": cmd_web,
    }

    dispatch[args.command](args, config)


if __name__ == "__main__":
    main()
