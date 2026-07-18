"""Approval token: bind case_id + HASH(package) + policy version + người duyệt + expiry.

Token chết khi một trong ba thứ thay đổi: dữ liệu (hash), chính sách (version),
thời gian (expiry). Chống TOCTOU giữa phê duyệt và thực thi.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from common import config
from . import db


def package_hash(package: dict) -> str:
    canonical = json.dumps(package, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def issue(case_id: str, package: dict, approver: str) -> dict:
    token = f"apv_{uuid.uuid4().hex}"
    expires_at = time.time() + config.APPROVAL_TOKEN_TTL_SECONDS
    db.save_token(token, case_id, package_hash(package),
                  config.POLICY_VERSION, approver, expires_at)
    return {"token": token, "expires_at": expires_at}


def verify(case_id: str, token: str) -> dict:
    rec = db.get_token(token)
    if not rec or rec["case_id"] != case_id:
        return {"valid": False, "reason": "token không tồn tại hoặc sai case"}
    if rec["used"]:
        return {"valid": False, "reason": "token đã sử dụng (single-use)"}
    if time.time() > rec["expires_at"]:
        return {"valid": False, "reason": "token hết hạn"}
    if rec["policy_version"] != config.POLICY_VERSION:
        return {"valid": False,
                "reason": f"phiên bản chính sách đã thay đổi "
                          f"({rec['policy_version']} -> {config.POLICY_VERSION})"}
    case = db.get_case(case_id)
    if not case or not case.get("package"):
        return {"valid": False, "reason": "không tìm thấy Approval Package"}
    current_hash = package_hash(case["package"])
    if current_hash != rec["package_hash"]:
        return {"valid": False,
                "reason": "nội dung Approval Package đã thay đổi sau phê duyệt (hash lệch)"}
    db.mark_token_used(token)
    return {"valid": True, "approver": rec["approver"]}
