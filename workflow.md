flowchart TD
    %% ============ 1. TIẾP NHẬN & PHÂN LUỒNG ============
    A[Chuyên viên mở Case Workspace] --> B[Nhập đề nghị vay SME: số tiền, mục đích, kỳ hạn<br/>+ đính kèm hồ sơ doanh nghiệp]
    B --> C[Gateway: xác thực, che PII, validate đầu vào]

    C -->|Câu hỏi đơn giản, chỉ đọc| DA[Direct Answer Agent<br/>chỉ tool ĐỌC + FAQ RAG]
    DA -->|Trả lời được| DA1[Trả lời trực tiếp trên Dashboard]
    DA -->|Nhận ra phức tạp giữa chừng| P0

    C -->|Thiếu / sai dữ liệu| C1[UI yêu cầu bổ sung hồ sơ]
    C1 --> DOC[Document Intelligence Agent — vision-LLM<br/>ĐKKD, BCTC rút gọn, sao kê DN, CCCD người đại diện, sổ đỏ<br/>trích xuất có cấu trúc + cross-check chéo tài liệu]
    DOC -->|Dữ liệu chuẩn hóa + cờ bất thường| B

    C -->|Hồ sơ hợp lệ| P0

    %% ============ 2. PLANNER ĐỘNG ============
    P0[Planner đọc Agent Card registry] --> P1[LLM sinh Task DAG theo đặc điểm hồ sơ<br/>validate schema, chỉ giao việc cho agent trong registry]
    P1 --> P2[Có TSĐB → + task định giá & pháp lý TSĐB<br/>Tín chấp → bỏ nhánh TSĐB<br/>Ngành rủi ro cao → + task đánh giá ngành<br/>Khách hiện hữu → KYB rút gọn]
    P2 --> EX[Plan Executor: topo-sort DAG<br/>task độc lập chạy song song, checkpoint từng bước]

    %% ============ 3. SPECIALIST + A2A ============
    EX --> E[Credit Agent<br/>BCTC: DSCR, đòn bẩy, vốn lưu động<br/>→ đề xuất hạn mức + điều kiện]
    EX --> F[Compliance Agent<br/>KYB, UBO, blacklist/AML, pháp lý TSĐB]
    EX --> G[Operations Agent — pha DRY-RUN<br/>kiểm tra điều kiện + draft hồ sơ vay, KHÔNG ghi]

    E <-.->|A2A info_request| F
    E <-.->|A2A info_request| DOC

    E --> H
    F --> H
    G --> H

    %% ============ 4. VALIDATION + MÁY TỰ GIẢI ============
    H[Validation — bước 1: xác thực facts,<br/>evidence, citations, policy, nhất quán] --> H2[Validation — bước 2:<br/>khuyến nghị có cấu trúc]
    H -->|Mâu thuẫn / thiếu evidence| CH{Máy tự giải được?}
    CH -->|A2A challenge — tối đa 2 vòng| CH1[Agent liên quan điều chỉnh verdict + ghi lý do]
    CH1 --> H
    CH -->|Không hội tụ| J
    H2 --> I{Đủ dữ liệu và qua policy?}

    I -->|Không| J[Escalate: Needs Info / Exception]
    J --> K[Chuyên viên bổ sung hồ sơ / xử lý ngoại lệ]
    K --> DOC2[Document Agent trích xuất tài liệu bổ sung]
    DOC2 --> RP[Planner RE-PLAN: DAG phiên bản mới<br/>chỉ chạy lại task bị ảnh hưởng, GIỚI HẠN SỐ VÒNG]
    RP -->|Trong giới hạn| EX
    RP -->|Vượt giới hạn vòng| J

    I -->|Có| L[Approval Package<br/>khuyến nghị + evidence + trace đầy đủ]

    %% ============ 5. HITL + SLA ============
L --> M[Pending Approval<br/>định tuyến đúng thẩm quyền theo hạn mức]
    M --> M1{Phản hồi trước SLA?}
    M1 -->|Phê duyệt| O[Backend phát approval token — bind:<br/>case_id + HASH package + policy/plan version<br/>+ người duyệt + expiry]
    M1 -->|Từ chối| N[Đóng case hoặc trả về điều chỉnh]
    M1 -->|Cần thêm thông tin| K
    M1 -->|Chưa phản hồi| M2[Nhắc theo SLA, ghi audit, giữ checkpoint]
    M2 --> M3{Hết SLA / người duyệt vắng?}
    M3 -->|Chưa| M
    M3 -->|Có| M4[Escalate cấp dự phòng / hàng đợi phê duyệt]
    M4 --> M

    %% ============ 6. COMMIT AN TOÀN ============
    O --> P[Operations Agent — pha COMMIT<br/>xác minh token + RE-CHECK preconditions<br/>+ idempotency key]
    P -->|Hash lệch / policy đổi / phát sinh<br/>nợ quá hạn mới sau phê duyệt| PV[Token vô hiệu → re-plan<br/>→ quay lại luồng phê duyệt]
    PV --> RP
    P -->|Preconditions OK| Q{Thực thi thành công?}
    Q -->|Có| S[Cập nhật case, thông báo, audit bất biến]
    Q -->|Không rõ trạng thái| R0[Đối soát transaction ID<br/>với hệ thống nghiệp vụ]
    R0 -->|Đã ghi nhận| S
    R0 -->|Chưa ghi nhận| RT[Retry ĐÚNG 1 LẦN<br/>cùng idempotency key]
    RT -->|Thành công| S
    RT -->|Vẫn lỗi / mơ hồ| R
    Q -->|Thất bại rõ ràng| R[KHÔNG retry thêm side effect<br/>→ Escalated, người xử lý xong quay lại M hoặc P]
    S --> T[Dashboard: Completed]