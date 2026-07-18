"""Khởi động toàn bộ hệ thống: MCP server + 5 agents + gateway.

Chạy: python run_all.py   (Ctrl+C để dừng tất cả)
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from common import config  # noqa: E402

SERVICES = [
    ("mcp-core-banking", [sys.executable, "-m", "mcp_core_banking.server"]),
    ("agent-document", [sys.executable, "-m", "uvicorn", "agents.document_agent:app",
                        "--port", str(config.AGENT_PORTS["document"]), "--log-level", "warning"]),
    ("agent-credit", [sys.executable, "-m", "uvicorn", "agents.credit_agent:app",
                      "--port", str(config.AGENT_PORTS["credit"]), "--log-level", "warning"]),
    ("agent-compliance", [sys.executable, "-m", "uvicorn", "agents.compliance_agent:app",
                          "--port", str(config.AGENT_PORTS["compliance"]), "--log-level", "warning"]),
    ("agent-operations", [sys.executable, "-m", "uvicorn", "agents.operations_agent:app",
                          "--port", str(config.AGENT_PORTS["operations"]), "--log-level", "warning"]),
    ("agent-validation", [sys.executable, "-m", "uvicorn", "agents.validation_agent:app",
                          "--port", str(config.AGENT_PORTS["validation"]), "--log-level", "warning"]),
    ("gateway", [sys.executable, "-m", "gateway.main"]),
]


def main() -> None:
    if not config.CORE_BANKING_DB.exists():
        print("Seed dữ liệu core banking...")
        subprocess.run([sys.executable, "-m", "mcp_core_banking.seed"], cwd=BACKEND, check=True)

    procs: list[tuple[str, subprocess.Popen]] = []
    for name, cmd in SERVICES:
        log = open(config.LOGS_DIR / f"{name}.log", "w", encoding="utf-8")
        p = subprocess.Popen(cmd, cwd=BACKEND, stdout=log, stderr=subprocess.STDOUT)
        procs.append((name, p))
        print(f"  [up] {name} (pid {p.pid})")
        time.sleep(0.6)

    print(f"\nGateway:  http://{config.HOST}:{config.GATEWAY_PORT}/docs")
    print(f"LLM_MODE: {config.LLM_MODE}")
    print("Ctrl+C để dừng tất cả.\n")
    try:
        while True:
            time.sleep(5)
            for name, p in procs:
                if p.poll() is not None:
                    print(f"!! {name} đã dừng (exit {p.returncode}) — xem logs/{name}.log")
    except KeyboardInterrupt:
        print("\nDừng các service...")
        for _, p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
