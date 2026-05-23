from __future__ import annotations
import argparse
import sys

from .cli.demo import add_demo_args, run_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recon")
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo_p = sub.add_parser("demo", help="Run the agent once")
    add_demo_args(demo_p)

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        return run_demo(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
