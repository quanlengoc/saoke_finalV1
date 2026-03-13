# Hướng dẫn Deploy lên Server

> Tài liệu hướng dẫn triển khai Reconciliation System V2 lên server production.
> Ví dụ minh họa: deploy tại `ptdata.vnptmone.vh/Sokhop`

## Mục lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Chuẩn bị source code](#2-chuẩn-bị-source-code)
3. [Cấu hình Backend](#3-cấu-hình-backend)
4. [Cấu hình Frontend](#4-cấu-hình-frontend)
5. [Cấu hình Nginx](#5-cấu-hình-nginx)
6. [Deploy với Docker Compose](#6-deploy-với-docker-compose)
7. [Deploy không dùng Docker](#7-deploy-không-dùng-docker)
8. [Chuyển từ SQLite sang Oracle](#8-chuyển-từ-sqlite-sang-oracle)
9. [Checklist trước khi Go Live](#9-checklist-trước-khi-go-live)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu |
|---|---|
| OS | Linux (Ubuntu 20.04+ / CentOS 7+) hoặc Windows Server |
| Docker | 20.10+ & Docker Compose 2.x |
| RAM | 2GB+ |
| Disk | 10GB+ (tùy lượng file upload) |
| Python | 3.9+ (nếu không dùng Docker) |
| Node.js | 18+ (nếu không dùng Docker) |
| Oracle Client | Instant Client 19c+ (nếu dùng Oracle DB) |

---

## 2. Chuẩn bị source code

```bash
# Clone hoặc copy source lên server
git clone <repo-url> /opt/reconciliation-system-v2
cd /opt/reconciliation-system-v2

# Tạo file .env từ template
cp .env.example .env

# Tạo các thư mục storage cần thiết
mkdir -p backend/data backend/logs redis/data
mkdir -p backend/storage/{uploads,exports,processed,mock_data,templates,sql_templates,custom_matching}
```

---

## 3. Cấu hình Backend

### 3.1. File `.env` (cho Docker Compose)

```ini
# === DATABASE ===
DB_TYPE=oracle                    # Đổi từ sqlite sang oracle cho production
ORACLE_HOST=10.0.0.1
ORACLE_PORT=1521
ORACLE_USER=recon_user
ORACLE_PASSWORD=<mật_khẩu_mạnh>
ORACLE_SID=ORCL

# === APPLICATION ===
MOCK_MODE=false                   # TẮT mock mode cho production
API_HOST=0.0.0.0
API_PORT=8001

# === SECURITY ===
SECRET_KEY=<random-string-64-ký-tự>    # ĐỔI! Dùng: python -c "import secrets; print(secrets.token_hex(32))"

# === CORS ===
# Thêm domain thật vào danh sách
CORS_ORIGINS=https://ptdata.vnptmone.vh,http://localhost:3000

# === FRONTEND ===
VITE_API_URL=/Sokhop/api          # Sub-path prefix cho API

# === LOGGING ===
LOG_LEVEL=INFO
```

### 3.2. File `backend/config.ini`

```ini
[server]
host = 0.0.0.0
port = 8001

[database.app]
type = oracle
dsn = 10.0.0.1:1521/ORCL
user = recon_user
password = <mật_khẩu>

# Kết nối VNPT Money DB
[database.vnptmoney_main]
type = oracle
dsn = 10.0.0.1:1521/vnptmoney
user = readonly_user
password = <mật_khẩu>

[app]
secret_key = <random-string-64-ký-tự>    # Phải GIỐNG với SECRET_KEY trong .env
algorithm = HS256
access_token_expire_minutes = 480

[storage]
base_path = ./storage
uploads = ./storage/uploads
processed = ./storage/processed
exports = ./storage/exports
templates = ./storage/templates
sql_templates = ./storage/sql_templates
mock_data = ./storage/mock_data
custom_matching = ./storage/custom_matching

[mock]
enabled = false
```

### 3.3. CORS Origins (backend/app/core/config.py)

Thêm domain production vào danh sách CORS:

```python
CORS_ORIGINS: list = [
    "https://ptdata.vnptmone.vh",
    "http://localhost:3000",
]
```

Hoặc tốt hơn: đọc từ biến môi trường `CORS_ORIGINS` trong `.env`.

---

## 4. Cấu hình Frontend

### 4.1. Sub-path: `vite.config.js`

Khi deploy tại sub-path `/Sokhop`, cần cấu hình `base`:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/Sokhop/',                     // ← Sub-path
  server: {
    port: 3000,
    proxy: {
      '/Sokhop/api': {                  // ← Proxy cho dev
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/Sokhop/, ''),
      },
    },
  },
})
```

> **Không dùng sub-path?** Để `base: '/'` và proxy `/api` bình thường.

### 4.2. React Router basename: `src/main.jsx`

```jsx
<BrowserRouter basename="/Sokhop">
  <App />
  <Toaster position="top-right" />
</BrowserRouter>
```

### 4.3. API baseURL: `src/services/api.js`

```js
const api = axios.create({
  baseURL: '/Sokhop/api/v2',     // ← Thêm sub-path prefix
  headers: {
    'Content-Type': 'application/json',
  },
})
```

Cũng cập nhật tất cả URL tải file trực tiếp (download URLs):

```js
// Trong reportsApi
downloadUrl: (batchId, fileType, format = 'csv') =>
  `/Sokhop/api/v2/reports/download/${batchId}/${fileType}?format=${format}`,

// Trong mockDataApi
download: (filename) => `/Sokhop/api/v2/mock-data/download/${filename}`,
```

### 4.4. Auth store: `src/stores/authStore.js`

```js
const authAxios = axios.create({
  baseURL: '/Sokhop/api/v2',     // ← Thêm sub-path prefix
  headers: { 'Content-Type': 'application/json' },
})
```

### 4.5. Redirect 401: `src/services/api.js`

```js
// Response interceptor
if (error.response?.status === 401) {
  localStorage.removeItem('auth-storage')
  setAuthToken(null)
  window.location.href = '/Sokhop/login'    // ← Thêm sub-path
}
```

### Tóm tắt: Các chỗ cần đổi khi thay sub-path

| File | Thuộc tính | Giá trị (ví dụ `/Sokhop`) |
|---|---|---|
| `vite.config.js` | `base` | `'/Sokhop/'` |
| `src/main.jsx` | `BrowserRouter basename` | `'/Sokhop'` |
| `src/services/api.js` | `baseURL` | `'/Sokhop/api/v2'` |
| `src/services/api.js` | download URLs (2 chỗ) | `'/Sokhop/api/v2/...'` |
| `src/services/api.js` | 401 redirect | `'/Sokhop/login'` |
| `src/stores/authStore.js` | `baseURL` | `'/Sokhop/api/v2'` |

> **Tip**: Có thể dùng biến `VITE_BASE_PATH` trong `.env` để quản lý tập trung thay vì sửa từng file. Xem phần [Nâng cao](#nâng-cao-dùng-env-cho-sub-path) bên dưới.

---

## 5. Cấu hình Nginx

### 5.1. Deploy tại sub-path `/Sokhop`

Tạo file `nginx.conf` hoặc thêm vào config hiện có:

```nginx
server {
    listen 80;
    server_name ptdata.vnptmone.vh;

    # Frontend - SPA tại /Sokhop
    location /Sokhop/ {
        proxy_pass http://localhost:3000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API tại /Sokhop/api
    location /Sokhop/api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # File upload - tăng giới hạn
        client_max_body_size 100M;

        # Timeout cho các API chạy lâu (đối soát, tạo report)
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Health check
    location /Sokhop/health {
        proxy_pass http://localhost:8001/health;
    }
}
```

### 5.2. Deploy tại root domain (không sub-path)

```nginx
server {
    listen 80;
    server_name recon.vnptmone.vh;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 100M;
        proxy_read_timeout 300s;
    }
}
```

### 5.3. HTTPS (khuyến nghị cho production)

```nginx
server {
    listen 443 ssl;
    server_name ptdata.vnptmone.vh;

    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # ... (các location block giống ở trên)
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name ptdata.vnptmone.vh;
    return 301 https://$host$request_uri;
}
```

---

## 6. Deploy với Docker Compose

### 6.1. Build và chạy

```bash
cd /opt/reconciliation-system-v2

# Build images
docker compose build

# Chạy ở background
docker compose up -d

# Kiểm tra trạng thái
docker compose ps
docker compose logs -f backend    # Xem log backend
docker compose logs -f frontend   # Xem log frontend
```

### 6.2. Bật Nginx container (tùy chọn)

Uncomment phần nginx trong `docker-compose.yml` nếu muốn chạy Nginx trong Docker:

```yaml
nginx:
  image: nginx:alpine
  container_name: reconciliation-nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf:ro
    - ./ssl:/etc/nginx/ssl:ro
  depends_on:
    - backend
    - frontend
  restart: unless-stopped
  networks:
    - reconciliation-network
```

### 6.3. Các lệnh quản lý thường dùng

```bash
# Restart service
docker compose restart backend
docker compose restart frontend

# Rebuild sau khi sửa code
docker compose build backend && docker compose up -d backend

# Xem log realtime
docker compose logs -f --tail=100 backend

# Vào shell container
docker compose exec backend bash
docker compose exec frontend sh

# Dừng tất cả
docker compose down

# Dừng và xóa volumes (CẢNH BÁO: mất data!)
docker compose down -v
```

---

## 7. Deploy không dùng Docker

### 7.1. Backend

```bash
cd /opt/reconciliation-system-v2/backend

# Tạo virtual environment
python3 -m venv venv
source venv/bin/activate

# Cài dependencies
pip install -r requirements.txt

# Nếu dùng Oracle: cài thêm Oracle Instant Client
# sudo apt install libaio1
# export LD_LIBRARY_PATH=/opt/oracle/instantclient_19_22:$LD_LIBRARY_PATH

# Khởi tạo database (lần đầu)
python -c "from app.init_db import init_database; init_database()"

# Chạy với uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

**Chạy như service (systemd):**

```ini
# /etc/systemd/system/reconciliation-backend.service
[Unit]
Description=Reconciliation Backend API
After=network.target

[Service]
Type=exec
User=www-data
WorkingDirectory=/opt/reconciliation-system-v2/backend
ExecStart=/opt/reconciliation-system-v2/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable reconciliation-backend
sudo systemctl start reconciliation-backend
```

### 7.2. Frontend

```bash
cd /opt/reconciliation-system-v2/frontend

# Cài dependencies
npm ci

# Build production
npm run build

# Serve static files (chọn 1 trong 2 cách)

# Cách 1: dùng serve
npm install -g serve
serve -s dist -l 3000

# Cách 2: dùng Nginx trực tiếp serve static files (khuyến nghị)
# Copy dist/ vào thư mục Nginx
cp -r dist/* /var/www/reconciliation/
```

**Nếu dùng Nginx serve static (không cần Node.js runtime):**

```nginx
location /Sokhop/ {
    alias /var/www/reconciliation/;
    try_files $uri $uri/ /Sokhop/index.html;    # SPA fallback
}
```

---

## 8. Chuyển từ SQLite sang Oracle

### 8.1. Cài Oracle Instant Client

```bash
# Ubuntu/Debian
sudo apt install libaio1
# Download và giải nén Oracle Instant Client
# https://www.oracle.com/database/technologies/instant-client/linux-x86-64-downloads.html

export LD_LIBRARY_PATH=/opt/oracle/instantclient_19_22:$LD_LIBRARY_PATH
```

### 8.2. Cài Python package

```bash
pip install cx_Oracle    # hoặc oracledb (mới hơn)
```

### 8.3. Cấu hình

Trong `config.ini`:

```ini
[database.app]
type = oracle
dsn = <oracle_host>:1521/<service_name>
user = recon_user
password = <mật_khẩu>
```

Trong `.env`:

```ini
DB_TYPE=oracle
ORACLE_HOST=<oracle_host>
ORACLE_PORT=1521
ORACLE_USER=recon_user
ORACLE_PASSWORD=<mật_khẩu>
ORACLE_SID=ORCL
```

### 8.4. Tạo schema

Hệ thống sẽ tự tạo bảng qua SQLAlchemy nếu chưa tồn tại. Hoặc tạo thủ công:

```bash
python -c "from app.init_db import init_database; init_database()"
```

---

## 9. Checklist trước khi Go Live

### Bảo mật
- [ ] Đổi `SECRET_KEY` trong cả `.env` và `config.ini` (dùng chuỗi random 64+ ký tự)
- [ ] Tắt `MOCK_MODE` (`false`)
- [ ] Cấu hình `CORS_ORIGINS` chỉ cho domain thật (xóa `*` và `localhost`)
- [ ] Bật HTTPS trên Nginx
- [ ] Đổi mật khẩu default admin account
- [ ] Kiểm tra file `.env` không bị commit vào git

### Database
- [ ] Cấu hình Oracle connection (nếu dùng Oracle)
- [ ] Chạy khởi tạo database (`init_database()`)
- [ ] Kiểm tra kết nối tới các database VNPT Money

### Frontend
- [ ] Cấu hình `base` trong `vite.config.js` đúng sub-path
- [ ] Cấu hình `basename` trong `BrowserRouter`
- [ ] Cập nhật `baseURL` trong `api.js` và `authStore.js`
- [ ] Cập nhật download URLs trong `api.js`
- [ ] Cập nhật 401 redirect URL
- [ ] Build lại frontend: `npm run build`

### Infrastructure
- [ ] Cấu hình Nginx reverse proxy
- [ ] Tăng `client_max_body_size` cho file upload (ít nhất 100M)
- [ ] Tăng `proxy_read_timeout` cho API chạy lâu (300s+)
- [ ] Cấu hình firewall cho ports cần thiết
- [ ] Setup log rotation

### Kiểm tra sau deploy
- [ ] Truy cập `https://ptdata.vnptmone.vh/Sokhop` → hiện trang login
- [ ] Đăng nhập thành công
- [ ] API health check: `curl https://ptdata.vnptmone.vh/Sokhop/api/v2/health`
- [ ] Upload file hoạt động
- [ ] Chạy đối soát thành công
- [ ] Download report hoạt động

---

## 10. Troubleshooting

### Frontend trả về 404 khi refresh trang

**Nguyên nhân**: SPA cần fallback về `index.html` cho client-side routing.

**Giải pháp**: Thêm `try_files` trong Nginx:

```nginx
location /Sokhop/ {
    # ...
    try_files $uri $uri/ /Sokhop/index.html;
}
```

### API trả về CORS error

**Giải pháp**: Kiểm tra `CORS_ORIGINS` trong `backend/app/core/config.py` hoặc `.env` có chứa domain frontend không. Domain phải khớp chính xác (bao gồm protocol `https://`).

### File upload lỗi 413 (Request Entity Too Large)

**Giải pháp**: Tăng `client_max_body_size` trong Nginx:

```nginx
location /Sokhop/api/ {
    client_max_body_size 100M;
    # ...
}
```

### API timeout khi chạy đối soát

**Giải pháp**: Tăng timeout trong Nginx:

```nginx
proxy_read_timeout 600s;
proxy_send_timeout 600s;
```

### Oracle connection error

**Kiểm tra**:
1. Oracle Instant Client đã cài và `LD_LIBRARY_PATH` đúng
2. Firewall cho phép kết nối tới Oracle port (1521)
3. DSN, user, password đúng trong `config.ini`
4. Test kết nối: `python -c "import cx_Oracle; cx_Oracle.connect('user/pass@host:1521/sid')"`

### Docker: container không start

```bash
# Xem log
docker compose logs backend

# Kiểm tra port conflict
sudo lsof -i :8001
sudo lsof -i :3000

# Kiểm tra volume permissions
ls -la backend/data/
ls -la backend/storage/
```

---

## Nâng cao: Dùng ENV cho sub-path

Thay vì sửa từng file khi đổi sub-path, có thể tập trung qua biến môi trường:

### `.env`
```ini
VITE_BASE_PATH=/Sokhop
```

### `vite.config.js`
```js
export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  // ...
})
```

### `src/services/api.js`
```js
const basePath = import.meta.env.VITE_BASE_PATH || ''
const api = axios.create({
  baseURL: `${basePath}/api/v2`,
})
```

### `src/main.jsx`
```jsx
const basePath = import.meta.env.VITE_BASE_PATH || ''
<BrowserRouter basename={basePath}>
```

Khi đó chỉ cần đổi `VITE_BASE_PATH` trong `.env` và build lại frontend.
