"""Thêm khách hàng demo mới vào Postgres cloud (đủ để tra cứu + chat + thống kê).

Platform không có API tạo khách hàng (khách hàng đồng bộ từ core banking),
nên script này chèn thẳng vào DB đúng cấu trúc seed: party → person_profile →
customer → account → account_holder → giao dịch lương/chi tiêu hàng tháng.

Cách dùng (cần Docker; secrets ở ~/.railway-shb-secrets):
  python scripts/add-cloud-customer.py --name "Pham Van Moi"
  python scripts/add-cloud-customer.py --name "Le Thi Kha Gia" \
      --salary 45000000 --expense 20000000 --months 6 --balance 250000000
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PG_HOST = os.getenv("SHB_PG_HOST", "hayabusa.proxy.rlwy.net")
PG_PORT = os.getenv("SHB_PG_PORT", "51877")
PSQL_IMAGE = "pgvector/pgvector:0.8.5-pg18-bookworm"

BRANCH_ID = "30000000-0000-4000-8000-000000000002"  # CN demo (theo seed)
RM_ID = "10000000-0000-4000-8000-000000000001"  # credit.officer làm RM mặc định


def load_secret(key: str) -> str:
    path = os.path.expanduser("~/.railway-shb-secrets")
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(f"{key}="):
                return line.strip().partition("=")[2]
    raise KeyError(key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Họ tên khách hàng")
    parser.add_argument("--cif", default=None, help="Mã CIF (mặc định CIF-CLOUD-xxxx)")
    parser.add_argument("--segment", default="MASS_AFFLUENT")
    parser.add_argument("--dob", default="1990-05-20")
    parser.add_argument("--occupation", default="Nhan vien van phong")
    parser.add_argument("--salary", type=int, default=25_000_000, help="Lương vào mỗi tháng (VND)")
    parser.add_argument("--expense", type=int, default=9_000_000, help="Chi tiêu ra mỗi tháng (VND)")
    parser.add_argument("--months", type=int, default=6, choices=range(1, 12), help="Số tháng lịch sử")
    parser.add_argument("--balance", type=int, default=60_000_000, help="Số dư hiện tại (VND)")
    args = parser.parse_args()

    party_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())
    holder_id = str(uuid.uuid4())
    cif = args.cif or f"CIF-CLOUD-{uuid.uuid4().hex[:6].upper()}"
    account_hash = uuid.uuid4().hex + uuid.uuid4().hex  # 64 ký tự, đủ unique
    masked = f"******{uuid.uuid4().int % 10000:04d}"

    transaction_rows: list[str] = []
    raw = "'{\"synthetic\":true,\"source\":\"add-cloud-customer\"}'::jsonb"
    for month in range(args.months):
        base = f"date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - make_interval(months => {month})"
        transaction_rows.append(
            f"('{uuid.uuid4()}', '{account_id}', ({base}) + INTERVAL '5 days 2 hours', "
            f"(({base}) + INTERVAL '5 days')::DATE, 'CREDIT', {args.salary}.0000, 'VND', 'SALARY', "
            f"'TRANSFER', 'Luong hang thang', {args.salary}.0000, 'EMPLOYER-***', "
            f"repeat('a', 64), 'SAL-{cif}-{month}', 'POSTED', {raw}, ({base}) + INTERVAL '5 days 2 hours')"
        )
        transaction_rows.append(
            f"('{uuid.uuid4()}', '{account_id}', ({base}) + INTERVAL '12 days 9 hours', "
            f"(({base}) + INTERVAL '12 days')::DATE, 'DEBIT', {args.expense}.0000, 'VND', 'LIVING_EXPENSE', "
            f"'CARD', 'Chi tieu sinh hoat', {args.expense}.0000, 'MERCHANT-***', "
            f"repeat('b', 64), 'EXP-{cif}-{month}', 'POSTED', {raw}, ({base}) + INTERVAL '12 days 9 hours')"
        )

    transactions_values = ",\n".join(transaction_rows)
    sql = f"""
BEGIN;
INSERT INTO customer.party (id, party_type, display_name, status, created_at, created_by, updated_at, updated_by, version)
VALUES ('{party_id}', 'PERSON', $${args.name}$$, 'ACTIVE', CURRENT_TIMESTAMP, '{RM_ID}', CURRENT_TIMESTAMP, '{RM_ID}', 1);

INSERT INTO customer.person_profile (party_id, full_name, date_of_birth, gender, nationality, marital_status, occupation, updated_at)
VALUES ('{party_id}', $${args.name}$$, DATE '{args.dob}', 'UNSPECIFIED', 'VN', 'SINGLE', $${args.occupation}$$, CURRENT_TIMESTAMP);

INSERT INTO customer.customer (id, party_id, customer_number, customer_segment, home_branch_id, relationship_manager_id, onboarding_date, kyc_status, risk_rating, risk_rating_as_of, status, created_at, updated_at, version)
VALUES ('{customer_id}', '{party_id}', '{cif}', '{args.segment}', '{BRANCH_ID}', '{RM_ID}', CURRENT_DATE - INTERVAL '{args.months} months', 'VERIFIED', 'MEDIUM', CURRENT_DATE, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1);

INSERT INTO banking.account (id, account_number_masked, account_number_hash, account_type, currency, branch_id, status, opened_at, closed_at, current_balance, balance_as_of, created_at, updated_at, version)
VALUES ('{account_id}', '{masked}', '{account_hash}', 'PAYMENT', 'VND', '{BRANCH_ID}', 'ACTIVE', CURRENT_TIMESTAMP - make_interval(months => {args.months}), NULL, {args.balance}.0000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1);

INSERT INTO banking.account_holder (id, account_id, party_id, holder_role, valid_from, valid_until, created_at)
VALUES ('{holder_id}', '{account_id}', '{party_id}', 'PRIMARY', (CURRENT_DATE - INTERVAL '{args.months} months')::DATE, NULL, CURRENT_TIMESTAMP);

INSERT INTO banking."transaction" (id, account_id, booking_time, value_date, direction, amount, currency, transaction_type, channel, description, balance_after, counterparty_name_masked, counterparty_account_hash, reference_number, status, raw_payload, created_at)
VALUES
{transactions_values};
COMMIT;

SELECT c.customer_number, p.display_name,
       (SELECT count(*) FROM banking."transaction" t
        JOIN banking.account_holder ah2 ON ah2.account_id = t.account_id
        WHERE ah2.party_id = '{party_id}') AS so_giao_dich
FROM customer.customer c JOIN customer.party p ON p.id = c.party_id
WHERE c.id = '{customer_id}';
"""

    result = subprocess.run(
        ["docker", "run", "--rm", "-i", "-e", f"PGPASSWORD={load_secret('PG_MIGRATOR_PASSWORD')}",
         PSQL_IMAGE, "psql",
         f"postgresql://bank_migrator@{PG_HOST}:{PG_PORT}/bank_ai", "-v", "ON_ERROR_STOP=1"],
        input=sql.encode(), capture_output=True,
    )
    if result.returncode != 0:
        print("[db] lỗi psql:", result.stderr.decode()[:400])
        return 1
    print(result.stdout.decode().strip().splitlines()[-4:])
    print("\n== HOÀN TẤT ==")
    print(f"Khách hàng: {args.name}  (CIF: {cif})")
    print(f"customer_id: {customer_id}")
    print(f"{args.months} tháng lịch sử: +{args.salary:,}đ lương / -{args.expense:,}đ chi tiêu mỗi tháng")
    print("Trên app: gõ / trong ô chat rồi tìm theo tên hoặc CIF ở trên.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
