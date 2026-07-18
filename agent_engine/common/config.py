"""Cấu hình tập trung cho toàn hệ thống. Đọc từ biến môi trường / file .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

# ---- Ports & URLs ----
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))
MCP_CORE_BANKING_PORT = int(os.getenv("MCP_CORE_BANKING_PORT", "8200"))

AGENT_PORTS = {
    "document": int(os.getenv("DOCUMENT_AGENT_PORT", "8101")),
    "credit": int(os.getenv("CREDIT_AGENT_PORT", "8102")),
    "compliance": int(os.getenv("COMPLIANCE_AGENT_PORT", "8103")),
    "operations": int(os.getenv("OPERATIONS_AGENT_PORT", "8104")),
    "validation": int(os.getenv("VALIDATION_AGENT_PORT", "8105")),
}

HOST = os.getenv("BIND_HOST", "127.0.0.1")
GATEWAY_URL = os.getenv("GATEWAY_URL", f"http://{HOST}:{GATEWAY_PORT}")
MCP_CORE_BANKING_URL = os.getenv(
    "MCP_CORE_BANKING_URL", f"http://{HOST}:{MCP_CORE_BANKING_PORT}/mcp"
)


def agent_url(name: str) -> str:
    return f"http://{HOST}:{AGENT_PORTS[name]}"


# ---- LLM ----
# LLM_MODE:
#   "hybrid" -> rules cho tính toán số & ngưỡng chính sách (deterministic, auditable);
#               LLM cho Planner (DAG động), Document (vision), Validation (narrative).
#               => ranh giới đúng cho ngân hàng: tin cậy tuyệt đối ở số, linh hoạt ở suy luận.
#   "llm"    -> mọi agent suy luận bằng LLM (chứng minh năng lực agentic đầy đủ).
#   "rules"  -> thuần rule, không gọi LLM (baseline benchmark / offline demo).
LLM_MODE = os.getenv("LLM_MODE", "hybrid").lower()
# OpenAI-compatible endpoint (FPT AI Marketplace mặc định)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://mkp-api.fptcloud.com/v1")
LLM_API_KEY = os.getenv("FPT_API_KEY") or os.getenv("OPENAI_API_KEY", "")
# Phân vai model theo agent (kết quả probe năng lực trên FPT Marketplace):
#   Planner/Validation: cần reasoning + JSON structured -> gpt-oss-120b
#   Specialist tool-loop: cần tool-calling ổn định     -> Llama-3.3-70B
#   Document vision: cần đọc ảnh tài liệu               -> Qwen2.5-VL-7B
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "gpt-oss-120b")
SPECIALIST_MODEL = os.getenv("SPECIALIST_MODEL", "Llama-3.3-70B-Instruct")
VISION_MODEL = os.getenv("VISION_MODEL", "Qwen2.5-VL-7B-Instruct")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOOL_ITERATIONS = int(os.getenv("LLM_MAX_TOOL_ITERATIONS", "10"))

# ---- Nghiệp vụ ----
POLICY_VERSION = os.getenv("POLICY_VERSION", "2026.07")
APPROVAL_TOKEN_TTL_SECONDS = int(os.getenv("APPROVAL_TOKEN_TTL_SECONDS", "900"))
MAX_REPLAN_ROUNDS = int(os.getenv("MAX_REPLAN_ROUNDS", "2"))
MAX_CHALLENGE_ROUNDS = int(os.getenv("MAX_CHALLENGE_ROUNDS", "2"))
APPROVAL_SLA_SECONDS = int(os.getenv("APPROVAL_SLA_SECONDS", "60"))  # rút ngắn để demo
LTV_MAX = float(os.getenv("LTV_MAX", "0.70"))
DSCR_MIN = float(os.getenv("DSCR_MIN", "1.20"))
# Thẩm quyền phê duyệt theo hạn mức (VND)
BRANCH_APPROVAL_LIMIT = float(os.getenv("BRANCH_APPROVAL_LIMIT", "8000000000"))

# ---- Paths ----
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CORE_BANKING_DB = DATA_DIR / "core_banking.db"
GATEWAY_DB = DATA_DIR / "gateway.db"
RAG_CORPUS_DIR = BACKEND_DIR / "rag_corpus"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
LOGS_DIR = BACKEND_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
