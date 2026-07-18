"""Principal-scoped Outbox process entry point."""

from __future__ import annotations

from app.workers.runtime import run_cli


def main() -> None:
    run_cli("outbox_publisher")


if __name__ == "__main__":
    main()
