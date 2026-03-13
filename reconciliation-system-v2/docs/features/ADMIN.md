# Tính năng: Quản trị (Users & Mock Data)

> Trang quản lý user/phân quyền và quản lý mock data cho testing.

## Pages & Routes

| Route | Page | Mô tả |
|---|---|---|
| `/admin/users` | `UsersPage` | CRUD users + phân quyền theo partner/service |
| `/admin/mock-data` | `MockDataPage` | Upload/preview/xóa mock CSV files |

---

## 1. Quản lý Users (`UsersPage`)

### Chức năng
- Danh sách users (bảng)
- Tạo / sửa / xóa user
- Phân quyền: gán user được truy cập partner + service nào
- Quyền admin: `is_admin = true` → toàn quyền

### API Endpoints

```
GET    /users/                              → Danh sách users
GET    /users/{id}                          → Chi tiết user
POST   /users/                              → Tạo user {email, password, full_name, is_admin}
PUT    /users/{id}                          → Sửa user
DELETE /users/{id}                          → Xóa user
POST   /users/{id}/permissions              → Thêm permission cho user
DELETE /users/{id}/permissions/{permId}      → Xóa 1 permission
PUT    /users/{id}/permissions/bulk          → Bulk update permissions
```

### Files liên quan

| File | Vai trò |
|---|---|
| `src/pages/admin/UsersPage.jsx` | CRUD users + modal permissions |
| `src/services/api.js` → `usersApi` | Tất cả user endpoints |
| `app/api/v2/endpoints/users.py` | Backend API users |
| `app/api/v2/endpoints/auth.py` | Login, me, change-password |
| `app/models/user.py` | Model `User`, `UserPermission` |

### Phân quyền

```
UserPermission {
  user_id
  partner_code    ← được phép truy cập partner nào
  service_code    ← được phép truy cập service nào
  can_view        ← xem batch
  can_execute     ← chạy đối soát
  can_approve     ← phê duyệt
}
```

- Admin (`is_admin=true`): bỏ qua permission check, toàn quyền
- User thường: chỉ thấy/thao tác batch thuộc partner+service mà mình có permission

---

## 2. Mock Data (`MockDataPage`)

### Chức năng
- Upload file CSV mock (thay thế cho query DB thật khi dev/test)
- Preview nội dung file mock (bảng, giới hạn dòng)
- Download / xóa file mock
- Xem columns của file mock (dùng cho cấu hình matching rules)

### API Endpoints

```
GET    /mock-data/                                   → Danh sách mock files
POST   /mock-data/upload?partner_code=X&service_code=Y → Upload CSV
GET    /mock-data/preview/{filename}?limit=20         → Preview nội dung
GET    /mock-data/download/{filename}                 → Download file
DELETE /mock-data/{filename}                          → Xóa file
GET    /mock-data/columns/{partner}/{service}         → Lấy column names
```

### Files liên quan

| File | Vai trò |
|---|---|
| `src/pages/admin/MockDataPage.jsx` | Upload, preview, delete mock files |
| `src/services/api.js` → `mockDataApi` | Tất cả mock data endpoints |
| `app/api/v2/endpoints/mock_data.py` | Backend API mock data |

### Convention tên file mock

```
{PARTNER_CODE}_{SERVICE_CODE}_b4_mock.csv
VD: SACOMBANK_TOPUP_b4_mock.csv
```

- Khi `config.ini` → `[mock] enabled = true`: hệ thống đọc mock file thay vì query Oracle
- File lưu tại: `storage/mock_data/`

---

## Lưu ý khi nâng cấp

- **UsersPage load configs**: Trang users cần gọi `configsApi.list()` để lấy danh sách partner/service cho dropdown phân quyền
- **Mock mode**: Chỉ dùng cho dev/test — production phải tắt (`[mock] enabled = false` trong `config.ini`)
- **Mock data chỉ cho admin**: Tất cả endpoint mock_data đều require `get_current_admin`
- **Password**: Hash bằng bcrypt, không lưu plaintext
