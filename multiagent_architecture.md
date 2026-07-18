## Hệ thống agent này là xương sống của toàn bộ hệ thống với các lớp thiết kế như sau:

### 1 . Agent user

agent này sẽ làm việc trực tiếp với người dùng(Nhân viên ngân hàng) có tác dụng hiểu câu hỏi của người dùng ở các mức độ như sau:

Mực độ 1: Câu hỏi lệch chủ đề : Không trả lời những câu hỏi lệch chủ đề
Mực độ 2: Câu hỏi đúng chủ đề nhưng chưa đủ context: hỏi lại nhân viên ngân hàng yêu cầu cấp thêm context, không trả lời khi chưa đủ ngữ cảnh
Mức độ 3 với câu hỏi dể đơn giản: Có thể trả lời ngay thì trả lời ngay nếu cần có tài liệu thì agent sẽ phải sinh ra 1 cái gì đó đề người dùng có thể truy xuất lại tài liệu tham chiếu

Mức độ 4: Câu hỏi đủ context nhưng chuyên sâu vào 1 lĩnh vực agent sẽ gọi các agent như (SQL agent, creadit agent, agent pháp luật hoặc agent tài liệu) thực thực hiện làm các nhiệm vụ chuyên biệt sau đó trả cho agent user kết quả đã được kiểm chứng và có nguồn để trả về thông tin cho người dùng

Mức độ 5: Đã đầy đủ context, câu hỏi quá phức tạp cần nhiều agent phối hợp hoặc phân tích các khoản vay, khách hàng có khả năng chi trả cho khoảng vay,.... Gọi đến hệ thống multi agent ở phía sau để giải quyết vấn đề khó. hệ thống multi agent này sẽ được trình bày ngay sau đây

### Hệ thống multi agent

Hệ thống này gồm nhiều agent làm việc với nhau với mục tiêu là phân nhỏ câu hỏi phức tạp sau đó trả lời câu hỏi nhỏ => từ đó phân tích và đưa đáp án cho những câu hỏi phức tạp

1. Agent điều phối:

đây là agent đầu tiên tiếp nhận nhiệm vụ và bắt đầu sinh các câu hỏi nhỏ để giải quyết. agent này sẽ tách nhỏ nhiệm vụ tạo plan dựa vào nhiệm vụ được phân nhỏ và yêu cầu các agent chuyên gia sẽ bắt tày vào làm việc. Sau khi các agent chuyên gia hoàn thành công việc sẽ có 1 agent để eval đánh giá kết quả phân tích của các chuyên gia.

2. các agent chuyên gia bao gồm:
-Chuyên gia đánh giá tài chính. nhìn vào các giao dịch và quyết định tài chính của khách hàng để đánh giá
-Chuyên gia về pháp luật sẽ nhìn vào pháp lý của nhà nước, quy định, chính sách của công ty để đưa ra đánh giá
- Chuyên gia về tài liệu: Nhìn vào hồ sơ người dùng xem hồ sơ của họ có đanghg thiếu gì không có sai sót gì trong các hồ sơ không để đánh giá 

- 3 chuyên gia này sẽ có thể được chạy song song hoặc tuần tự dựa vào sự điều phối của agent điều phối

- 3 agent này đều có 1 agent đánh giá kết quả nếu được mới cho phép 1 agent viết báo cáo tổng hợp để trả về thông tin phân tích cho nhân viên ngân hàng, dựa vào đó sẽ hỗ trợ khả năng quyết định của những người có thẩm quyền

- hệ thống khi đưa ra câu trả lời đều phải chẳng hạn như nguồn 1 có số 1 khi nhấn vào sô 1 đó sẽ hiển thị lại nguồn gốc chính của thông tin dựa vào

3. Agents đánh giá

Agent đánh giá ở đây là các agent là các chuyên gia chúng sẽ chỉ nhìn vào kết quả cuối cùng và các viết để đánh giá xem agent chuyên gia có đang bị ảo giác hay không. Có đang viết đúng hay không hay những khuyến nghị có phù hợp hay không. Chúng sẽ gửi feedback về các agent chuyên gia để chúng xử lý sao cho phù hợp

Hệ thống agent này không chỉ để xử lý và phân tích những khoản vay của khách hàng mà còn trả lời những câu hỏi phức tạp của nhân viên ngân hàng