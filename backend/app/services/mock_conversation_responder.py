"""Development-only User Agent responder over the synthetic expert scenarios."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.agents.base import AgentName
from app.schemas.conversation import ConversationReply
from app.services.agent_simulation_service import (
    AgentSimulationResponse,
    AgentSimulationService,
)
from app.services.protocols import PrincipalLike

_INCOMPLETE_TERMS = (
    "thiếu",
    "mâu thuẫn",
    "xung đột",
    "dấu đỏ",
    "con dấu",
    "chưa đủ",
    "incomplete",
    "conflict",
    "missing",
)
_AGENT_BY_NAME = {
    "DOCUMENT": AgentName.DOCUMENT,
    "CREDIT": AgentName.CREDIT,
    "LEGAL_COMPLIANCE": AgentName.LEGAL_COMPLIANCE,
}


class MockConversationResponder:
    """Render inspectable mock conclusions; never present synthetic facts as real data."""

    def __init__(self, simulation: AgentSimulationService | None = None) -> None:
        self._simulation = simulation or AgentSimulationService()

    async def respond(
        self,
        *,
        principal: PrincipalLike,
        conversation: Mapping[str, Any],
        message: str,
        route: Mapping[str, Any],
        attachment_ids: Sequence[UUID] = (),
    ) -> ConversationReply:
        del principal
        intent = str(route.get("intent") or "DIRECT_QUERY")
        route_type = str(route.get("route_type") or "DIRECT")
        complexity = _optional_int(route.get("complexity_level"))
        attachment_metadata = {
            "input_attachment_ids": [str(value) for value in attachment_ids],
            # The design-mode simulation does not read uploaded bytes.  This
            # flag prevents synthetic output from implying otherwise.
            "attachments_used_for_mock_analysis": False,
        }

        if route_type == "REFUSE" or intent == "OUT_OF_SCOPE":
            return ConversationReply(
                content=(
                    "Tôi chỉ hỗ trợ nghiệp vụ ngân hàng trong phạm vi khách hàng, giao dịch, "
                    "hồ sơ, chính sách tín dụng và phân tích khoản vay. Tôi không xử lý yêu cầu "
                    "lệch khỏi phạm vi này."
                ),
                route_type="REFUSE",
                complexity_level=complexity,
                metadata={
                    "mode": "MOCK",
                    "intent": intent,
                    "refused": True,
                    **attachment_metadata,
                },
            )

        missing = tuple(str(item) for item in route.get("missing_context", ()))
        if missing:
            labels = {
                "customer_id": "khách hàng đang xử lý",
                "loan_application_id": "hồ sơ khoản vay đang xử lý",
                "question": "câu hỏi cần phân tích",
            }
            requested = ", ".join(labels.get(item, item) for item in missing)
            return ConversationReply(
                content=f"Tôi chưa đủ ngữ cảnh. Vui lòng chọn hoặc cung cấp: {requested}.",
                route_type=route_type,
                complexity_level=complexity,
                metadata={
                    "mode": "MOCK",
                    "intent": intent,
                    "missing_context": list(missing),
                    **attachment_metadata,
                },
            )

        if route_type == "DIRECT":
            return _direct_reply(
                message,
                intent=intent,
                complexity=complexity,
                attachment_metadata=attachment_metadata,
            )

        customer_id = _optional_uuid(conversation.get("active_customer_id"))
        loan_id = _optional_uuid(conversation.get("active_loan_application_id"))
        scenario = (
            "INCOMPLETE"
            if any(term in message.casefold() for term in _INCOMPLETE_TERMS)
            else "READY"
        )
        result = await self._simulation.run(
            scenario,
            objective=message,
            customer_id=customer_id,
            loan_application_id=loan_id,
        )
        selected_agents = _selected_agents(route)
        content = _render_simulation_reply(result, selected_agents)
        return ConversationReply(
            content=content,
            route_type=route_type,
            complexity_level=complexity,
            metadata={
                "mode": result.mode,
                "synthetic_data": True,
                "synthetic_analysis_case_id": str(result.analysis_case_id),
                "intent": intent,
                "scenario_code": result.scenario_code.value,
                "report_status": result.report_status,
                "report_writer_executed": result.report_writer_executed,
                "ready_for_human_review": result.ready_for_human_review,
                "validation_status": result.validation.validation_status,
                "expert_evaluation_approved": result.expert_evaluation.approved,
                "human_decision_required": result.human_decision_required,
                **attachment_metadata,
                "citations": [
                    citation.model_dump(mode="json") for citation in result.citations
                ],
            },
        )


def _direct_reply(
    message: str,
    *,
    intent: str,
    complexity: int | None,
    attachment_metadata: Mapping[str, Any],
) -> ConversationReply:
    lowered = message.casefold()
    definitions = {
        "dti": (
            "DTI là tỷ lệ tổng nghĩa vụ trả nợ định kỳ trên thu nhập được chấp nhận. "
            "Khi đánh giá một hồ sơ cụ thể, hệ thống phải dùng CalculationService deterministic."
        ),
        "dscr": (
            "DSCR phản ánh mức độ dòng tiền hoặc thu nhập có thể bao phủ nghĩa vụ trả nợ. "
            "Giá trị hồ sơ phải lấy từ calculation record có nguồn."
        ),
        "ltv": (
            "LTV là tỷ lệ dư nợ hoặc khoản vay trên giá trị "
            "tài sản bảo đảm đủ điều kiện. "
            "Ngưỡng chấp nhận thuộc policy hiệu lực, không được hard-code trong agent."
        ),
    }
    definition = next((text for term, text in definitions.items() if term in lowered), None)
    content = definition or (
        "Yêu cầu đã được định tuyến sang DIRECT_TOOL. "
        "Ở chế độ mô phỏng tôi không tạo số liệu "
        "khách hàng. Dữ liệu thực phải được truy vấn bằng repository/tool deterministic có RLS "
        "và trả kèm nguồn."
    )
    return ConversationReply(
        content=content,
        route_type="DIRECT",
        complexity_level=complexity,
        metadata={
            "mode": "MOCK",
            "intent": intent,
            "synthetic_data": True,
            **attachment_metadata,
        },
    )


def _render_simulation_reply(
    result: AgentSimulationResponse,
    selected_agents: frozenset[AgentName],
) -> str:
    findings_with_agent = tuple(
        (output.agent_name, finding)
        for output in result.expert_outputs
        for finding in output.findings
    )
    lines = [result.display_notice, result.user_summary]
    used_numbers: list[int] = []
    if result.report_writer_executed:
        selected_claims = tuple(
            claim
            for (agent_name, _finding), claim in zip(
                findings_with_agent, result.cited_claims, strict=True
            )
            if not selected_agents or agent_name in selected_agents
        )
        lines.extend(f"- {claim.rendered_claim}" for claim in selected_claims[:8])
        used_numbers.extend(
            number for claim in selected_claims[:8] for number in claim.citation_numbers
        )
    else:
        citation_numbers = _citation_numbers_by_reference(result)
        for agent_name, finding in findings_with_agent:
            if selected_agents and agent_name not in selected_agents:
                continue
            numbers = _finding_citation_numbers(finding, citation_numbers)
            suffix = " ".join(f"[{number}]" for number in numbers)
            lines.append(
                f"- [{agent_name.value} - CHƯA TỔNG HỢP] {finding.description} {suffix}".rstrip()
            )
            used_numbers.extend(numbers)
            if len(lines) >= 10:
                break

    unique_numbers = tuple(dict.fromkeys(used_numbers))
    citations_by_number = {citation.number: citation for citation in result.citations}
    if unique_numbers:
        lines.append("Nguồn mô phỏng nội tuyến:")
        lines.extend(
            f"[{number}] {citations_by_number[number].quoted_text}"
            for number in unique_numbers
            if number in citations_by_number
        )
    lines.append(result.human_decision_notice)
    return "\n".join(lines)


def _citation_numbers_by_reference(
    result: AgentSimulationResponse,
) -> dict[tuple[str, UUID], int]:
    return {
        (citation.citation_type, citation.source_id): citation.number
        for citation in result.citations
    }


def _finding_citation_numbers(
    finding: Any,
    numbers: Mapping[tuple[str, UUID], int],
) -> tuple[int, ...]:
    result = [
        numbers[("EVIDENCE", reference.source_id)]
        for reference in finding.evidence
        if ("EVIDENCE", reference.source_id) in numbers
    ]
    result.extend(
        numbers[("CALCULATION", calculation_id)]
        for calculation_id in finding.calculation_ids
        if ("CALCULATION", calculation_id) in numbers
    )
    result.extend(
        numbers[("POLICY", clause_id)]
        for clause_id in finding.policy_clause_ids
        if ("POLICY", clause_id) in numbers
    )
    return tuple(dict.fromkeys(result))


def _selected_agents(route: Mapping[str, Any]) -> frozenset[AgentName]:
    raw = route.get("required_agents", ())
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(
        _AGENT_BY_NAME[str(item)]
        for item in raw
        if str(item) in _AGENT_BY_NAME
    )


def _optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Conversation resource context must contain UUID values") from exc


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
