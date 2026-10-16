"""Forward the chart module entry point to the unified modern command."""

import sys


def Main(argv: list[str] | None = None) -> int:
    """Accept the same arguments as the public chart subcommand."""

    from pricegenerator.cli import Main as Command

    return Command(["chart", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    raise SystemExit(Main())
