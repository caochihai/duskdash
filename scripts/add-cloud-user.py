"""Thêm người dùng mới cho bản cloud: Keycloak + bản ghi nhân viên trong Postgres.

Người dùng của hệ thống nằm ở HAI tầng và phải có đủ cả hai:
  1. Keycloak (realm bank-ai)      — đăng nhập, mật khẩu, vai trò realm.
  2. identity.employee (Postgres)  — backend từ chối token nếu subject không có
                                     bản ghi nhân viên ACTIVE (EMPLOYEE_INACTIVE).

Cách dùng (cần Docker đang chạy để gọi psql, secrets ở ~/.railway-shb-secrets):
  python scripts/add-cloud-user.py --username huy@shb.vn --fullname "Nguyen Van Huy"
  python scripts/add-cloud-user.py --username kiemtoan2@shb.vn \
      --fullname "Tran Thi B" --role auditor --password MatKhauRieng123

Vai trò hợp lệ: credit_officer, credit_manager, document_reviewer,
compliance_officer, risk_officer, loan_approver, auditor, admin.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KC = os.getenv("SHB_KEYCLOAK_URL", "https://keycloak-production-e7a5.up.railway.app")
PG_HOST = os.getenv("SHB_PG_HOST", "hayabusa.proxy.rlwy.net")
PG_PORT = os.getenv("SHB_PG_PORT", "51877")
PSQL_IMAGE = "pgvector/pgvector:0.8.5-pg18-bookworm"

BRANCH_ID = "30000000-0000-4000-8000-000000000002"  # CN demo (theo seed)
DEPARTMENT_ID = "31000000-0000-4000-8000-000000000001"
ADMIN_EMPLOYEE_ID = "10000000-0000-4000-8000-000000000007"  # assigned_by

JOB_TITLE = {
    "credit_officer": "Credit Officer",
    "credit_manager": "Credit Manager",
    "document_reviewer": "Document Reviewer",
    "compliance_officer": "Compliance Officer",
    "risk_officer": "Risk Officer",
    "loan_approver": "Loan Approver",
    "auditor": "Auditor",
    "admin": "Admin",
}


def load_secrets() -> dict[str, str]:
    path = os.path.expanduser("~/.railway-shb-secrets")
    secrets: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and "=" in line:
                key, _, value = line.partition("=")
                secrets[key] = value
    return secrets


def kc_request(method: str, path: str, token: str, body: object | None = None):
    request = urllib.request.Request(
        f"{KC}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    return urllib.request.urlopen(request)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--fullname", required=True)
    parser.add_argument("--role", default="credit_officer", choices=sorted(JOB_TITLE))
    parser.add_argument("--email", default=None, help="Mặc định dùng username nếu là dạng email")
    parser.add_argument("--password", default=None, help="Mặc định dùng CLOUD_SEED_USER_PASSWORD")
    args = parser.parse_args()

    secrets = load_secrets()
    password = args.password or secrets["CLOUD_SEED_USER_PASSWORD"]
    email = args.email or (args.username if "@" in args.username else f"{uuid.uuid4().hex[:8]}@example.local")
    parts = args.fullname.split()
    first_name, last_name = (" ".join(parts[:-1]) or parts[0]), parts[-1]

    # ---- 1. Keycloak ----
    admin_form = urllib.parse.urlencode({
        "client_id": "admin-cli", "grant_type": "password",
        "username": "admin", "password": secrets["KC_ADMIN_PASSWORD"],
    }).encode()
    token = json.load(urllib.request.urlopen(urllib.request.Request(
        f"{KC}/realms/master/protocol/openid-connect/token", data=admin_form
    )))["access_token"]

    try:
        kc_request("POST", "/admin/realms/bank-ai/users", token, {
            "username": args.username, "email": email, "enabled": True,
            "emailVerified": True, "firstName": first_name, "lastName": last_name,
        })
        print(f"[kc] đã tạo user {args.username}")
    except urllib.error.HTTPError as error:
        if error.code == 409:
            print(f"[kc] user {args.username} đã tồn tại — tiếp tục cập nhật")
        else:
            print("[kc] lỗi tạo user:", error.code, error.read()[:200])
            return 1

    with kc_request(
        "GET", f"/admin/realms/bank-ai/users?username={urllib.parse.quote(args.username)}&exact=true", token
    ) as response:
        subject = json.load(response)[0]["id"]

    kc_request("PUT", f"/admin/realms/bank-ai/users/{subject}/reset-password", token,
               {"type": "password", "value": password, "temporary": False})
    with kc_request("GET", f"/admin/realms/bank-ai/roles/{args.role}", token) as response:
        role = json.load(response)
    kc_request("POST", f"/admin/realms/bank-ai/users/{subject}/role-mappings/realm", token,
               [{"id": role["id"], "name": role["name"]}])
    print(f"[kc] mật khẩu + vai trò {args.role} đã gán (subject {subject})")

    # ---- 2. identity.employee trong Postgres ----
    employee_code = f"EMP-CLOUD-{subject[:8].upper()}"
    sql = f"""
INSERT INTO identity.employee (
    id, identity_subject, employee_code, full_name, email, branch_id,
    department_id, job_title, manager_id, employment_status, last_synced_at,
    created_at, updated_at, version
) VALUES (
    '{subject}', '{subject}', '{employee_code}', $${args.fullname}$$, '{email}',
    '{BRANCH_ID}', '{DEPARTMENT_ID}', '{JOB_TITLE[args.role]}', NULL, 'ACTIVE',
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1
) ON CONFLICT (id) DO NOTHING;

INSERT INTO identity.employee_role (id, employee_id, role_id, valid_from, valid_until, assigned_by, created_at)
SELECT gen_random_uuid(), '{subject}', r.id, CURRENT_TIMESTAMP, NULL, '{ADMIN_EMPLOYEE_ID}', CURRENT_TIMESTAMP
FROM identity.role r WHERE r.role_code = '{args.role}'
AND NOT EXISTS (
    SELECT 1 FROM identity.employee_role x WHERE x.employee_id = '{subject}' AND x.role_id = r.id
);

INSERT INTO identity.employee_scope (id, employee_id, scope_type, scope_id, permission_code, valid_from, valid_until, assigned_by, reason, created_at)
SELECT gen_random_uuid(), '{subject}', 'BRANCH', '{BRANCH_ID}', 'customer:read', CURRENT_TIMESTAMP, NULL, '{ADMIN_EMPLOYEE_ID}', 'Cloud user script.', CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1 FROM identity.employee_scope x WHERE x.employee_id = '{subject}' AND x.permission_code = 'customer:read'
);
"""
    result = subprocess.run(
        ["docker", "run", "--rm", "-i", "-e", f"PGPASSWORD={secrets['PG_MIGRATOR_PASSWORD']}",
         PSQL_IMAGE, "psql",
         f"postgresql://bank_migrator@{PG_HOST}:{PG_PORT}/bank_ai", "-v", "ON_ERROR_STOP=1"],
        input=sql.encode(), capture_output=True,
    )
    if result.returncode != 0:
        print("[db] lỗi psql:", result.stderr.decode()[:300])
        return 1
    print(f"[db] bản ghi nhân viên {employee_code} đã vào (branch demo, quyền customer:read)")

    print("\n== HOÀN TẤT ==")
    print(f"Đăng nhập: {args.username}")
    print(f"Mật khẩu:  {password}")
    print(f"Vai trò:   {args.role}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
