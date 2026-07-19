# KỊCH BẢN DEMO — SHB AI Assistant

> Bản demo chạy **hoàn toàn ở frontend** với dữ liệu mock. Không cần Postgres,
> Redis, Keycloak hay Azure. Đầu ra 3 agent chuyên gia là mock, nhưng **hồ sơ
> scan và toạ độ trích dẫn là thật** (ảnh gốc + Azure Document Intelligence).

## Chuẩn bị (2 phút trước khi trình bày)

```bash
cd frontend
npm install     # chỉ lần đầu
npm run dev     # http://localhost:3000
```

**Đừng tạo file `frontend/.env`.** Không có `.env` thì chế độ mock tự bật. Nếu
copy `.env.example` thành `.env`, biến `VITE_USE_MOCK_API=false` sẽ bắt frontend
gọi backend thật và **demo sẽ không đăng nhập được**.

Mở sẵn tab ẩn danh, phóng to cửa sổ, và **đăng xuất** nếu đã đăng nhập trước đó.

| Tài khoản | Mật khẩu | Chuyên viên | Khách hàng phụ trách | Hạn mức |
|---|---|---|---|---|
| `chuyenvien1` | `chuyenvien1` | Nguyễn Minh Anh — CN Hà Nội | Hồng Nhung, Văn Cường, **VinaNova** | 3 tỷ |
| `chuyenvien2` | `chuyenvien2` | Trần Quốc Bảo — CN HCM | Minh Quân, Thu Hà, Đông Đô | 1,5 tỷ |

---

# KỊCH BẢN 10 PHÚT

## Màn 1 — Cửa vào hệ thống (1 phút)

1. Mở `http://localhost:3000/` → bị đẩy về `/login?returnTo=%2F`.
   > *"Chưa đăng nhập thì không có đường nào vào được."*
2. Nhập `chuyenvien1` + mật khẩu sai → báo lỗi tại chỗ.
3. Bấm thẻ **Nguyễn Minh Anh** phía dưới (tự điền) → **Đăng nhập**.
   Hệ thống quay lại đúng trang vừa bị chặn; header hiện tên và đơn vị.

## Màn 2 — Chuyên viên chỉ thấy phần việc của mình (1 phút)

Gõ: **`Liệt kê các khách hàng tôi đang được phân công.`**

→ Bảng đúng 3 khách hàng.
> *"Danh mục này không phải lọc ở giao diện. Ở backend, phạm vi được ép thẳng
> vào câu truy vấn SQL theo quyền của nhân viên."*

## Màn 3 — Mỗi khách hàng một phiên làm việc (1,5 phút)

4. Gõ **`/`** trong ô nhập → danh sách khách hàng → chọn **Công ty CP Bao bì VinaNova**.
   - Phiên chat của khách hàng đó mở ra, header hiện **thẻ tên khách hàng**.
   - **Cửa sổ hồ sơ mở bên phải**: tóm tắt tín dụng, danh sách hồ sơ vay, nút phê
     duyệt. Kéo thanh giữa để đổi tỉ lệ hai bên.

> *"Mỗi khách hàng có một phiên riêng. Hồ sơ, tài liệu và kết luận nằm gọn trong
> phiên đó, nên ngữ cảnh không trộn lẫn và mỗi hồ sơ có một vết kiểm toán liền mạch."*

## Màn 4 — Ba chuyên gia số cùng thẩm định (2 phút)

5. Trong phiên VinaNova, gõ: **`Thẩm định hồ sơ vay này.`**

Chỉ cho người xem thấy:
- **Dấu vết phối hợp**: 6 bước qua `planner → credit → legal → product → operations`,
  chạy song song rồi hợp nhất.
- Mỗi bước có **kết quả công cụ** (`query_credit_bureau`, `screen_aml_watchlist`…)
  → giải trình được, không phải hộp đen.
- **Thẻ phê duyệt** với các chốt kiểm tra đạt/không đạt.

> *"Hệ thống đề xuất và giải trình. Quyết định vẫn thuộc chuyên viên, và được ghi vết."*

## Màn 5 — ⭐ Truy ngược về đúng chỗ trên giấy tờ (2,5 phút)

**Đây là phần trọng tâm, dành nhiều thời gian nhất.**

6. Bấm **"Xem nguồn"** trên header → ngăn trích dẫn mở ra.
7. Chọn một nguồn → bấm **"Xem trên hồ sơ"**.

→ Panel phải mở **ảnh scan thật** của hồ sơ, **khoanh đỏ đúng dòng chữ** mà agent
đã dẫn, tự cuộn tới vị trí đó, và hiện **nguyên văn** dòng chữ ở thanh dưới.

8. Bấm **‹ ›** để đi qua từng dẫn chứng — khung đỏ là chỗ đang xem, khung cam là
   các dẫn chứng khác trên cùng trang, mỗi khung có số thứ tự.
9. Bấm **zoom 200%** để soi rõ chữ dưới khung.

> *"Toạ độ này do Azure Document Intelligence trả về khi OCR hồ sơ, được lưu ở mức
> từng dòng. Chuyên viên không phải tin lời hệ thống — bấm một cái là thấy đúng chữ
> trên giấy tờ gốc."*

**Điểm đáng nói thêm:** nếu không dò được câu trích về đúng dòng nào, hệ thống **bỏ
hẳn trích dẫn đó** thay vì đoán một vị trí. Khung đỏ trỏ sai chỗ còn nguy hiểm hơn
là không có khung.

## Màn 6 — Ranh giới của phiên (1 phút)

10. Vẫn trong phiên VinaNova, gõ: **`Cho tôi thông tin khách hàng Nguyễn Văn Cường.`**

→ **Bị từ chối**, kèm bước ghi vết `enforce_session_customer`, không lộ một dòng dữ
liệu nào — dù Văn Cường **cũng thuộc quyền** của chuyên viên này.

11. Bấm gợi ý **"Mở phiên của Nguyễn Văn Cường"** → chuyển hẳn sang phiên của người đó.

## Màn 7 — Ranh giới của quyền (1,5 phút)

12. Gõ: **`Cho tôi thông tin khách hàng Phạm Thu Hà.`** (khách của chuyên viên 2)
    → Bị chặn vì **ngoài danh mục phân công**, và **không có** gợi ý mở phiên.
13. Gõ thẳng URL `http://localhost:3000/customer/cus-005` → cũng bị chặn.
14. Đăng xuất → đăng nhập **`chuyenvien2`** → hỏi lại **đúng câu ở bước 12**
    → **giờ trả lời được đầy đủ.**

> *"Phạm vi bám theo quyền của tài khoản, không bám theo câu chữ người dùng gõ.
> Đây là chỗ nhiều hệ thống AI làm sai: chỉ dặn mô hình đừng trả lời, thay vì chặn
> ở tầng dữ liệu."*

15. Mở lại một hồ sơ bất kỳ: **hạn mức phê duyệt giờ là 1,5 tỷ** thay vì 3 tỷ; hồ
    sơ vượt hạn mức bị **khoá nút** và yêu cầu trình cấp cao hơn.

---

# Chức năng phụ (nếu còn thời gian hoặc bị hỏi)

| Thao tác | Kết quả |
|---|---|
| `Tôi muốn vay 2 tỷ mua nhà trong 20 năm.` | Thẻ ước tính + bảng + biểu đồ cơ cấu |
| `Lãi suất tiền gửi kỳ hạn 12 tháng?` | Tư vấn có nguồn trích dẫn |
| Đính kèm file bất kỳ | Luồng đọc tài liệu |
| `mô phỏng timeout` | Trạng thái lỗi có nút thử lại |
| Nút **Dừng** khi đang trả lời | Dừng giữa chừng, giữ lại phần đã sinh |
| Menu ⋮ → Giám sát hệ chuyên gia số | Bảng điều khiển agent |

---

# Câu hỏi có thể bị vặn — và cách trả lời thẳng

**"Đây có phải AI thật không, hay chỉ là màn hình dựng sẵn?"**
> Phần giao diện đang chạy mock. Engine thật đã chạy được (`services/engine/`,
> container cổng 8200) với 3 chuyên gia song song, trả 16 trích dẫn cho một hồ sơ
> thật, 0 luận điểm bịa nguồn. **Hai phần chưa nối với nhau** — đó là việc tiếp theo.

**"Toạ độ khoanh đỏ có phải vẽ tay không?"**
> Không. Ảnh là hồ sơ scan thật, toạ độ do Azure Document Intelligence `prebuilt-read`
> trả về, lưu ở mức từng dòng (migration V019, bảng `document.document_line`).

**"Chặn quyền như vậy đã đủ an toàn chưa?"**
> Ở bản demo, rào đang đặt ở tầng service của frontend. Ràng buộc thật phải nằm
> trong câu SQL của backend (`AuthorizedScope` ép vào `WHERE`). Đừng coi phần demo
> này là đã khoá được rủi ro đó.

---

# Đã nghiệm thu — 33/33 kiểm thử tự động

Chạy trên logic đã bundle (esbuild → node), không phải kiểm tra bằng mắt:

- **Phân quyền & phiên đăng nhập (6)** — từ chối mật khẩu sai; hai phạm vi rời nhau
  và phủ hết danh mục; hạn mức theo tài khoản; đăng xuất xoá phiên.
- **Hành vi agent (8)** — 6 bước qua 3 chuyên gia; 5 bước có kết quả công cụ; chặn
  ngoài phạm vi không lộ dữ liệu; mô phỏng được lỗi.
- **Phiên khách hàng (10)** — hỏi chung chung trả về đúng khách của phiên; hỏi người
  khác bị từ chối; thẩm định mặc định đúng hồ sơ; phiên chung không xử lý hồ sơ.
- **Trích dẫn → hồ sơ (6)** — 368 dòng toạ độ đều nằm trong khung trang; dò ngược
  trúng dòng; **dò không ra thì trả `null`, không bịa toạ độ**; mọi trích dẫn resolve
  về một vùng có thật.
- **Điều hướng phiên (3)** — gợi ý "Mở phiên của X" chuyển phiên thay vì gửi lại câu
  hỏi (đã sửa lỗi lặp vô tận); khách ngoài quyền không được mời mở phiên.

`npm run build` sạch, `npx tsc -b --noEmit` sạch.

---

# Ranh giới của bản demo (nên nói trước, đừng để bị hỏi)

- Đầu ra 3 agent là **mock**; Engine thật chạy riêng, chưa nối vào giao diện.
- Chỉ **VinaNova** có hồ sơ scan kèm toạ độ. Khách hàng khác không có dẫn chứng trên
  giấy tờ — đây là chủ ý, không phải lỗi: hệ thống không bịa dẫn chứng cho hồ sơ
  chưa số hoá.
- Dữ liệu khách hàng là hư cấu; không kết nối core banking.
- **Key Azure trong `.env` cần rotate sau demo.**
