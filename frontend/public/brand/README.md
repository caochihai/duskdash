# SHB Brand Assets

Các file trong thư mục này là tài sản thương hiệu chính thức của SHB, được sử dụng để nhận diện
thương hiệu trong giao diện ứng dụng **SHB AI Assistant** (frontend demo).

## Nguồn

| Thông tin | Chi tiết |
| --- | --- |
| Source | Official SHB website |
| Reference | https://new.shb.com.vn/vi |
| Origin CDN | `https://cdn.prod-shbwebsite.aws.shb.com.vn/media/` |
| Retrieved for | SHB AI Assistant frontend demo |
| Usage | Brand identification in application UI |

Assets được tải về và lưu local trong repository. Ứng dụng **không hotlink** logo từ CDN ở
production — mọi tham chiếu đều trỏ tới `/brand/*.svg`.

## Danh sách file

| File | Kích thước gốc | Màu | Nguồn gốc |
| --- | --- | --- | --- |
| `shb-logo.svg` | 87 × 32 | `#F37021` + `#2F2E79` | `media/Logo_fe2b7455f8.svg` (header website) |
| `shb-logo-white.svg` | 144 × 54 | `#F37021` + `white` | `media/Logo_7ac40ce706.svg` (footer website) |

### Ghi chú về biến thể symbol

Website chính thức **không cung cấp** file symbol (logomark) riêng biệt. Theo nguyên tắc thương
hiệu, dự án **không tự crop** logo để tạo symbol. Ở trạng thái sidebar thu gọn, ứng dụng hiển thị
logo đầy đủ được thu nhỏ theo đúng tỷ lệ.

Nếu sau này SHB cung cấp `shb-symbol.svg` chính thức, chỉ cần thêm file vào thư mục này và cập nhật
`src/components/common/SHBLogo.tsx`.

## Màu thương hiệu chính thức

Các mã màu dưới đây được trích xuất trực tiếp từ file SVG chính thức, không phải giá trị phỏng đoán:

```
Orange (primary)  #F37021
Indigo (navy)     #2F2E79
```

Hai giá trị này là nguồn chuẩn cho `src/theme/tokens.ts`.

## Quy tắc sử dụng

- Không thay đổi màu logo.
- Không bóp méo hoặc thay đổi tỷ lệ.
- Không crop.
- Không thêm shadow hoặc viền trực tiếp lên logo.
- Không áp dụng CSS filter để tạo biến thể trắng — dùng `shb-logo-white.svg`.
- Giữ khoảng trắng an toàn xung quanh logo.

## Favicon

Ứng dụng sử dụng trực tiếp `shb-logo.svg` làm favicon (`index.html`). Không tạo file `.ico`
raster từ nguồn không chính thức.
