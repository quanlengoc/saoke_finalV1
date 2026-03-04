11-Feb-2026

Với hướng mới làm động thì gần như toàn bộ UI sẽ bị thay đổi 
A. PHẦN CẤU HÌNH CHO 1 ĐỐI TÁC + DỊCH VỤ + khoảng thời gian áp dụng
1.Phần đưa thông tin một cặp thì component cấu hình sẽ cần 
-1. Thư tự so khớp (luôn mặc định theo thứ tự người dùng add thêm)
- 2. Đầu số data số 1 
- 3. Đầu vào đata số 2
- 4. Cấu hình so khớp key match và amount match
- 5. Out put lấy thông tin gì --> kết quả này sẽ được sử dụng để đưa vào báo cáo tổng hợp không? hay chỉ là dữ liệu trung gian cho cặp so khớp tiếp theo
==> trong đó đầu vào có thể được mở rộng cách lấy dữ liệu từ các loại nguồn: file upload lên, hay chạy file SQL truy vấn từ kết nối các loại DB, hay lấy từ sFTP đc chọn kết nối sFTP nào, giá trị đường dẫn, và mẫu file ví dụ tự động lấy file ngày hiện tại thì cấu hình đường diễn yyyymmdd/SACOMBANK_*.xlsx là lấy toàn bộ các file trong thư mục của ngày hiện tại là ngày hiện tại 20261102 và láy toàn bộ file bắt đầu là SACOMBANK định dang xlsx
==> thời gian áp dụng cho cùng 1 đối tác + dịch vụ không được phép trồng chờm lên nhau. 

2. Phần lấy thông tin report sẽ làm như hiện tại nhưng việc điền "from temp_a1" thì nó sẽ thay đổi phụ thuộc cấu hình các cặp thì output nào đc phép sử dụng để tổng hợp 

B. PHẦN TẠO BATCH cho 1 cặp đối tác và dịch vụ + chu kỳ đối soát
- Phần người dùng upload file để khi tạo 1 batch cho 1 cặp đối soát dịch vụ sẽ phụ thuộc vào:
1. Chọn đối tác nào
2. Chọn dịch vụ gì?
3. Chu kỳ đối soát từ ngày đến ngày có nằm trong thời hạn nằm trong thời gian áp dụng cấu hình  cấu hình cho đối tác và dịch vụ đó 
==> Mỗi batch sẽ  gắn với một id cấu hình khi được tạo ra. 

C. Phần hiển thị kết qua chi tiết từng batch cũng sẽ thay đổi theo số cặp được cấu hình. 