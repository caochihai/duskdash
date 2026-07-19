from __future__ import annotations

from datetime import date
from pathlib import Path

from app.schemas.input_ocr_bundle import OCRBundle, PolicyContext
from app.schemas.output_report import ActionableFinding, GroundingStatus
from app.schemas.policy_action import (
    ActionAudience,
    ActionPlan,
    ActionStatus,
    ActionType,
    BankPolicyBasis,
    BlockingStage,
    OwnerRole,
    PolicyActionRegistry,
    RecommendedAction,
    RequirementLevel,
)


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "policy" / "legal_action_registry_v1.json"
)


def load_action_registry(path: Path = DEFAULT_REGISTRY_PATH) -> PolicyActionRegistry:
    return PolicyActionRegistry.model_validate_json(path.read_text(encoding="utf-8"))


def build_action_plan(
    *,
    bundle: OCRBundle,
    findings: list[ActionableFinding],
    registry: PolicyActionRegistry | None = None,
    as_of: date | None = None,
) -> ActionPlan:
    """Map grounded findings to versioned rules; LLM wording is never an action source."""

    resolved_registry = registry or load_action_registry()
    evaluated_as_of = as_of or date.today()
    active_rules = {
        rule.issue_category: rule
        for rule in resolved_registry.rules
        if rule.is_effective(evaluated_as_of)
    }
    actions: list[RecommendedAction] = []
    for finding in findings:
        if finding.grounding_status != GroundingStatus.VERIFIED:
            actions.append(_source_verification_action(finding, resolved_registry, evaluated_as_of))
            continue
        rule = active_rules.get(finding.category)
        if rule is None:
            actions.append(_manual_unmapped_action(finding, resolved_registry, evaluated_as_of))
            continue
        bank_basis = _bank_policy_basis(bundle.policy_context, finding.category.value)
        missing_required_policy = rule.requires_bank_policy and not bank_basis
        action_status = (
            ActionStatus.MANUAL_POLICY_REVIEW_REQUIRED
            if missing_required_policy
            else ActionStatus.READY_FOR_HUMAN_EXECUTION
        )
        audience = ActionAudience.INTERNAL if missing_required_policy else rule.audience
        actions.append(
            RecommendedAction(
                action_id=f"ACT-{finding.finding_id}-{rule.rule_id}",
                finding_ids=[finding.finding_id],
                action_type=rule.action_type,
                owner_role=rule.owner_role,
                requirement_level=(
                    RequirementLevel.MANUAL_REVIEW
                    if missing_required_policy
                    else rule.requirement_level
                ),
                action_status=action_status,
                audience=audience,
                why_required=(
                    rule.why_required
                    + (
                        " Chưa có đủ policy_id, version, effective_from và section nội bộ; "
                        "không được gửi yêu cầu khách hàng hoặc tự động ảnh hưởng quyết định."
                        if missing_required_policy
                        else ""
                    )
                ),
                legal_basis=rule.legal_basis,
                bank_policy_basis=bank_basis,
                required_evidence=rule.required_evidence,
                completion_criteria=rule.completion_criteria,
                blocking_stage=rule.blocking_stage,
                priority=rule.priority,
                next_state_after_completion=rule.next_state_after_completion,
                source_rule_id=rule.rule_id,
                source_rule_version=rule.version,
            )
        )

    if not _has_usable_bank_policy(bundle.policy_context):
        actions.append(
            _missing_bank_policy_action(
                findings=findings,
                registry=resolved_registry,
            )
        )

    actions.sort(key=lambda item: (-item.priority, item.action_id))
    return ActionPlan(
        registry_id=resolved_registry.registry_id,
        registry_version=resolved_registry.version,
        evaluated_as_of=evaluated_as_of,
        manual_policy_review_required=any(
            item.action_status == ActionStatus.MANUAL_POLICY_REVIEW_REQUIRED
            for item in actions
        ),
        next_actions=actions,
        customer_actions=[
            item
            for item in actions
            if item.audience == ActionAudience.CUSTOMER
            and item.action_status == ActionStatus.READY_FOR_HUMAN_EXECUTION
        ],
        internal_actions=[item for item in actions if item.audience == ActionAudience.INTERNAL],
        regulatory_escalations=[
            item for item in actions if item.audience == ActionAudience.REGULATORY
        ],
    )


def _bank_policy_basis(
    context: PolicyContext | None,
    category: str,
) -> list[BankPolicyBasis]:
    if (
        context is None
        or context.policy_id is None
        or context.effective_from is None
        or category not in context.action_rule_sections
    ):
        return []
    return [
        BankPolicyBasis(
            policy_id=context.policy_id,
            version=context.policy_version,
            section=context.action_rule_sections[category],
            effective_from=context.effective_from,
        )
    ]


def _has_usable_bank_policy(context: PolicyContext | None) -> bool:
    return bool(
        context is not None
        and context.policy_id
        and context.effective_from
        and context.action_rule_sections
    )


def _missing_bank_policy_action(
    *,
    findings: list[ActionableFinding],
    registry: PolicyActionRegistry,
) -> RecommendedAction:
    policy_rule = next(
        rule
        for rule in registry.rules
        if rule.issue_category.value == "POLICY_REVIEW_REQUIRED"
    )
    return RecommendedAction(
        action_id="ACT-CASE-BANK-POLICY-REQUIRED",
        finding_ids=[finding.finding_id for finding in findings],
        action_type=ActionType.POLICY_REVIEW,
        owner_role=OwnerRole.CREDIT_APPRAISER,
        requirement_level=RequirementLevel.MANUAL_REVIEW,
        action_status=ActionStatus.MANUAL_POLICY_REVIEW_REQUIRED,
        audience=ActionAudience.INTERNAL,
        why_required=(
            "Luật yêu cầu ngân hàng có quy định nội bộ về hồ sơ, thẩm định, phê duyệt, "
            "phân quyền và kiểm soát rủi ro. Request hiện chưa cung cấp policy_id, version, "
            "effective_from và section áp dụng; hệ thống chỉ được nêu finding, chưa được tự "
            "đặt yêu cầu khách hàng hoặc quyết định tín dụng."
        ),
        legal_basis=policy_rule.legal_basis,
        bank_policy_basis=[],
        required_evidence=[
            "Quy định cấp tín dụng nội bộ hiện hành",
            "Checklist hồ sơ theo sản phẩm",
            "Ma trận thẩm quyền và rule CIC/DTI/DSCR áp dụng",
        ],
        completion_criteria=[
            "Cấu hình policy_id, version và ngày hiệu lực",
            "Ánh xạ từng nhóm finding tới đúng section nội bộ",
            "Người có thẩm quyền xác nhận rule trước khi chạy lại",
        ],
        blocking_stage=BlockingStage.APPROVAL,
        priority=99,
        next_state_after_completion="REASSESS",
        source_rule_id=policy_rule.rule_id,
        source_rule_version=policy_rule.version,
    )


def _source_verification_action(
    finding: ActionableFinding,
    registry: PolicyActionRegistry,
    as_of: date,
) -> RecommendedAction:
    sources = [
        f"{source.source_filename} - trang {source.page_number} - {source.source_excerpt}"
        for source in finding.sources
    ]
    return RecommendedAction(
        action_id=f"ACT-{finding.finding_id}-VERIFY-SOURCE",
        finding_ids=[finding.finding_id],
        action_type=ActionType.VERIFY_EXTRACTED_SOURCE,
        owner_role=OwnerRole.CREDIT_APPRAISER,
        requirement_level=RequirementLevel.RISK_CONTROL_RECOMMENDED,
        action_status=ActionStatus.READY_FOR_HUMAN_EXECUTION,
        audience=ActionAudience.INTERNAL,
        why_required=(
            "Finding chưa được grounding đầy đủ vào text/dữ liệu nguồn. Phải phân biệt lỗi của "
            "hồ sơ với lỗi trích xuất trước khi liên hệ khách hàng hoặc dùng cho quyết định."
        ),
        legal_basis=[],
        bank_policy_basis=[],
        required_evidence=sources or ["Trang và đoạn text nguồn của finding"],
        completion_criteria=[
            "Đối chiếu đúng file, trang và chủ thể",
            "Xác nhận trích đoạn/giá trị tồn tại trong dữ liệu upstream",
            "Đánh dấu VERIFIED hoặc loại finding sai",
        ],
        blocking_stage=BlockingStage.ASSESSMENT,
        priority=100,
        next_state_after_completion="REASSESS",
        source_rule_id=f"{registry.registry_id}-SOURCE-GROUNDING-CONTROL",
        source_rule_version=registry.version,
    )


def _manual_unmapped_action(
    finding: ActionableFinding,
    registry: PolicyActionRegistry,
    as_of: date,
) -> RecommendedAction:
    return RecommendedAction(
        action_id=f"ACT-{finding.finding_id}-POLICY-NOT-CONFIGURED",
        finding_ids=[finding.finding_id],
        action_type=ActionType.POLICY_REVIEW,
        owner_role=OwnerRole.CREDIT_APPRAISER,
        requirement_level=RequirementLevel.MANUAL_REVIEW,
        action_status=ActionStatus.MANUAL_POLICY_REVIEW_REQUIRED,
        audience=ActionAudience.INTERNAL,
        why_required=(
            "Không có rule còn hiệu lực cho finding tại ngày đánh giá; hệ thống không được tự "
            "đặt hành động hoặc ảnh hưởng quyết định."
        ),
        legal_basis=[],
        bank_policy_basis=[],
        required_evidence=["Quy định nội bộ hiện hành và checklist sản phẩm"],
        completion_criteria=["Cấu hình rule có phiên bản, thời gian hiệu lực và người phê duyệt"],
        blocking_stage=BlockingStage.APPROVAL,
        priority=90,
        next_state_after_completion="REASSESS",
        source_rule_id=f"{registry.registry_id}-NO-ACTIVE-RULE",
        source_rule_version=registry.version,
    )
