"""
main.py — PricingEngine entry point

Usage
-----
# Run all tenants once and exit
python main.py --run-now

# Run specific tenants only
python main.py --run-now --tenants telecom_001

# Start the nightly 2 AM scheduler (runs until Ctrl-C / SIGTERM)
python main.py --schedule

# Run once, then hand off to the scheduler
python main.py --run-now --schedule
"""

import argparse
import sys

from orchestrator.engine import PricingEngineOrchestrator, configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pricing-engine",
        description="PricingEngine — Multi-tenant AI Predictive Pricing",
    )
    parser.add_argument(
        "--tenants",
        nargs="+",
        metavar="TENANT_ID",
        help="Tenant IDs to process (default: all configured tenants)",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the pipeline immediately",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the nightly 2 AM UTC scheduler (keeps process alive)",
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()

    orchestrator = PricingEngineOrchestrator(tenant_ids=args.tenants)

    if not args.run_now and not args.schedule:
        # Default: run once
        args.run_now = True

    if args.run_now:
        results = orchestrator.run_all_tenants()
        failed = [tid for tid, r in results.items() if r["status"] != "success"]
        if failed:
            print(f"\nFailed tenants: {failed}", file=sys.stderr)
            if not args.schedule:
                sys.exit(1)

    if args.schedule:
        # block=True parks the main thread until SIGINT/SIGTERM
        orchestrator.start_scheduler(block=True)
        orchestrator.stop_scheduler()


if __name__ == "__main__":
    main()
