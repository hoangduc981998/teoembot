# 🔐 Hướng dẫn A-Z: Tạo User Riêng cho Từng Dự Án trên Linux
> **Mục tiêu:** Bỏ thói quen chạy service bằng `root`, mỗi dự án có 1 user riêng,  
> bị tấn công cũng chỉ mất 1 dự án — không mất toàn bộ máy chủ.

---

## 📋 Mục lục
1. [Tại sao không dùng root?](#1-tại-sao-không-dùng-root)
2. [Quy ước đặt tên](#2-quy-ước-đặt-tên)
3. [Tạo user mới cho dự án](#3-tạo-user-mới-cho-dự-án)
4. [Chuyển dự án đang chạy root sang user riêng](#4-chuyển-dự-án-đang-chạy-root-sang-user-riêng)
5. [Viết file systemd service chuẩn](#5-viết-file-systemd-service-chuẩn)
6. [Kiểm tra và vận hành](#6-kiểm-tra-và-vận-hành)
7. [Làm lại toàn bộ dự án cũ — checklist](#7-làm-lại-toàn-bộ-dự-án-cũ--checklist)
8. [Xử lý các tình huống đặc biệt](#8-xử-lý-các-tình-huống-đặc-biệt)
9. [Lệnh hay dùng hàng ngày](#9-lệnh-hay-dùng-hàng-ngày)

---

## 1. Tại sao không dùng root?

```
root = chìa khoá master toàn bộ máy chủ
  → xoá file hệ thống     ✅
  → cài phần mềm bất kỳ   ✅
  → đọc mọi mật khẩu      ✅
  → tắt/format máy chủ    ✅

projectuser = chìa khoá 1 căn phòng
  → chỉ đọc/ghi thư mục dự án  ✅
  → không làm được gì khác      ❌
```

**Kịch bản thực tế:**
- Bot/app bị khai thác lỗ hổng
- Chạy bằng `root` → attacker **chiếm toàn bộ máy chủ**, toàn bộ dự án khác
- Chạy bằng `projectuser` → attacker **chỉ vào được 1 thư mục dự án đó**

---

## 2. Quy ước đặt tên

> Đặt tên nhất quán giúp dễ quản lý khi có nhiều dự án.

| Dự án | User | Thư mục | Service file |
|---|---|---|---|
| Bot nhắc việc | `bot-nhiecvu` | `/opt/bot-nhiecvu/` | `bot-nhiecvu.service` |
| Bot trading | `bot-trading` | `/opt/bot-trading/` | `bot-trading.service` |
| Web API | `api-main` | `/opt/api-main/` | `api-main.service` |
| Crawl data | `crawler-x` | `/opt/crawler-x/` | `crawler-x.service` |

**Quy tắc:**
- Tên user: chữ thường, dùng dấu `-`, tối đa 32 ký tự
- Thư mục: luôn đặt trong `/opt/` — **không dùng `/root/`**
- Service file: trùng tên user cho dễ nhớ

---

## 3. Tạo user mới cho dự án

### Bước 3.1 — Tạo user hệ thống
```bash
# Cú pháp:
sudo useradd --system --no-create-home --shell /usr/sbin/nologin TÊN_USER

# Ví dụ thực tế:
sudo useradd --system --no-create-home --shell /usr/sbin/nologin bot-nhiecvu
sudo useradd --system --no-create-home --shell /usr/sbin/nologin bot-trading
sudo useradd --system --no-create-home --shell /usr/sbin/nologin api-main
```

| Tham số | Ý nghĩa |
|---|---|
| `--system` | User hệ thống — không phải người dùng thật |
| `--no-create-home` | Không tạo `/home/username` — không cần thiết |
| `--shell /usr/sbin/nologin` | **Không thể SSH hay login** vào máy bằng user này |

### Bước 3.2 — Kiểm tra user đã tạo chưa
```bash
id bot-nhiecvu
# Kết quả đúng:
# uid=999(bot-nhiecvu) gid=999(bot-nhiecvu) groups=999(bot-nhiecvu)
```

### Bước 3.3 — Tạo thư mục dự án trong `/opt/`
```bash
# Tạo thư mục
sudo mkdir -p /opt/TÊN_DỰ_ÁN

# Ví dụ:
sudo mkdir -p /opt/bot-nhiecvu
sudo mkdir -p /opt/bot-trading
```

### Bước 3.4 — Cấp quyền thư mục cho user
```bash
# Cú pháp:
sudo chown -R TÊN_USER:TÊN_USER /opt/TÊN_DỰ_ÁN

# Ví dụ:
sudo chown -R bot-nhiecvu:bot-nhiecvu /opt/bot-nhiecvu
```

### Bước 3.5 — Kiểm tra quyền
```bash
ls -la /opt/bot-nhiecvu
# Kết quả đúng:
# drwxr-xr-x  bot-nhiecvu bot-nhiecvu  .
```

---

## 4. Chuyển dự án đang chạy root sang user riêng

> Làm theo thứ tự này để không bị gián đoạn dịch vụ.

### Bước 4.1 — Dừng service cũ
```bash
sudo systemctl stop TÊN_SERVICE_CŨ
sudo systemctl disable TÊN_SERVICE_CŨ

# Ví dụ: dự án đang chạy tên là asnhiemvu-bot
sudo systemctl stop asnhiemvu-bot
sudo systemctl disable asnhiemvu-bot
```

### Bước 4.2 — Tạo user mới (nếu chưa tạo ở Bước 3)
```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin bot-nhiecvu
```

### Bước 4.3 — Copy toàn bộ dự án sang `/opt/`
```bash
# Cú pháp:
sudo cp -r /root/THƯMỤC_CŨ /opt/TÊN_MỚI

# Ví dụ: dự án đang ở /root/telegram_bots/asnhiemvu
sudo cp -r /root/telegram_bots/asnhiemvu /opt/bot-nhiecvu
```

### Bước 4.4 — Cấp quyền thư mục mới cho user
```bash
sudo chown -R bot-nhiecvu:bot-nhiecvu /opt/bot-nhiecvu
```

### Bước 4.5 — Bảo vệ file .env (chỉ user đó đọc được)
```bash
# .env chứa token, mật khẩu → chỉ owner đọc được, người khác không
sudo chmod 600 /opt/bot-nhiecvu/.env

# Kiểm tra lại
ls -la /opt/bot-nhiecvu/.env
# Kết quả đúng:
# -rw-------  bot-nhiecvu bot-nhiecvu  .env
```

### Bước 4.6 — Tạo lại virtual environment (nếu dùng Python venv)
```bash
# Xoá venv cũ (đã copy sang, nhưng path bên trong venv trỏ về /root/)
sudo rm -rf /opt/bot-nhiecvu/venv

# Tạo venv mới đúng path
sudo -u bot-nhiecvu python3 -m venv /opt/bot-nhiecvu/venv

# Cài lại thư viện
sudo -u bot-nhiecvu /opt/bot-nhiecvu/venv/bin/pip install -r /opt/bot-nhiecvu/requirements.txt
```

> ⚠️ **Quan trọng:** Luôn xoá và tạo lại `venv` vì `venv` cũ hardcode đường dẫn `/root/...`
> bên trong — copy sang `/opt/` sẽ bị lỗi path.

### Bước 4.7 — Kiểm tra bot chạy được không (test thủ công trước)
```bash
# Chạy thử bằng đúng user mới — nếu không lỗi thì mới tạo service
sudo -u bot-nhiecvu /opt/bot-nhiecvu/venv/bin/python /opt/bot-nhiecvu/bot.py
# Ctrl+C để dừng sau khi thấy chạy được
```

---

## 5. Viết file systemd service chuẩn

### Template chuẩn — copy và sửa các chỗ có `<...>`
```ini
[Unit]
Description=<MÔ TẢ DỰ ÁN>
After=network-online.target
Wants=network-online.target

[Service]
# ✅ User riêng — KHÔNG dùng root
User=<TÊN_USER>
Group=<TÊN_USER>
WorkingDirectory=/opt/<TÊN_DỰ_ÁN>

# Lệnh chạy
ExecStart=/opt/<TÊN_DỰ_ÁN>/venv/bin/python /opt/<TÊN_DỰ_ÁN>/bot.py

# Load file .env
EnvironmentFile=/opt/<TÊN_DỰ_ÁN>/.env

# Python log realtime
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/opt/<TÊN_DỰ_ÁN>

# Tự restart nếu crash
Restart=always
RestartSec=10

# Dừng restart nếu crash liên tục 5 lần trong 60 giây
# (tránh restart bão làm nặng máy chủ)
StartLimitIntervalSec=60
StartLimitBurst=5

Type=simple
StandardOutput=journal
StandardError=journal
SyslogIdentifier=<TÊN_USER>

# Resource limits
LimitNOFILE=1024
MemoryMax=256M

# Timeouts
TimeoutStartSec=60
TimeoutStopSec=30

# Tự kill và restart nếu bot treo quá 60 giây không phản hồi
WatchdogSec=60

# Bảo mật bổ sung
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Ví dụ thực tế — bot nhắc việc
```ini
[Unit]
Description=Telegram NhiemVu Bot Service
After=network-online.target
Wants=network-online.target

[Service]
User=bot-nhiecvu
Group=bot-nhiecvu
WorkingDirectory=/opt/bot-nhiecvu
ExecStart=/opt/bot-nhiecvu/venv/bin/python /opt/bot-nhiecvu/bot.py
EnvironmentFile=/opt/bot-nhiecvu/.env
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/opt/bot-nhiecvu
Restart=always
RestartSec=10
StartLimitIntervalSec=60
StartLimitBurst=5
Type=simple
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bot-nhiecvu
LimitNOFILE=1024
MemoryMax=256M
TimeoutStartSec=60
TimeoutStopSec=30
WatchdogSec=60
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Lưu file service
```bash
# Cú pháp:
sudo nano /etc/systemd/system/<TÊN_USER>.service

# Ví dụ:
sudo nano /etc/systemd/system/bot-nhiecvu.service
# → paste nội dung vào → Ctrl+O → Enter → Ctrl+X
```

---

## 6. Kiểm tra và vận hành

### Kích hoạt service mới
```bash
# Reload systemd đọc file service mới
sudo systemctl daemon-reload

# Bật tự chạy khi boot
sudo systemctl enable bot-nhiecvu

# Khởi động ngay
sudo systemctl start bot-nhiecvu

# Kiểm tra trạng thái
sudo systemctl status bot-nhiecvu
```

### Kết quả đúng khi `status`:
```
● bot-nhiecvu.service - Telegram NhiemVu Bot Service
     Loaded: loaded (/etc/systemd/system/bot-nhiecvu.service; enabled)
     Active: active (running) since 2026-03-26 08:00:00 +07; 5s ago
   Main PID: 12345 (python)
      Tasks: 3
     Memory: 45.2M
```

### Xem log realtime
```bash
journalctl -u bot-nhiecvu -f

# Xem 100 dòng gần nhất
journalctl -u bot-nhiecvu -n 100

# Xem log từ hôm nay
journalctl -u bot-nhiecvu --since today
```

---

## 7. Làm lại toàn bộ dự án cũ — Checklist

> In ra, làm từng dự án một, tick vào ô khi xong.

```
Tên dự án: ________________________
User mới:  ________________________

[ ] 1. Dừng service cũ
        sudo systemctl stop <tên_service_cũ>
        sudo systemctl disable <tên_service_cũ>

[ ] 2. Tạo user mới
        sudo useradd --system --no-create-home --shell /usr/sbin/nologin <user>

[ ] 3. Copy dự án sang /opt/
        sudo cp -r /root/... /opt/<tên_dự_án>

[ ] 4. Cấp quyền
        sudo chown -R <user>:<user> /opt/<tên_dự_án>

[ ] 5. Bảo vệ .env
        sudo chmod 600 /opt/<tên_dự_án>/.env

[ ] 6. Xoá venv cũ, tạo lại
        sudo rm -rf /opt/<tên_dự_án>/venv
        sudo -u <user> python3 -m venv /opt/<tên_dự_án>/venv
        sudo -u <user> /opt/<tên_dự_án>/venv/bin/pip install -r /opt/<tên_dự_án>/requirements.txt

[ ] 7. Test chạy thủ công
        sudo -u <user> /opt/<tên_dự_án>/venv/bin/python /opt/<tên_dự_án>/bot.py

[ ] 8. Tạo file service mới
        sudo nano /etc/systemd/system/<user>.service

[ ] 9. Kích hoạt service
        sudo systemctl daemon-reload
        sudo systemctl enable <user>
        sudo systemctl start <user>

[ ] 10. Kiểm tra chạy đúng
        sudo systemctl status <user>
        journalctl -u <user> -n 50

[ ] 11. Xoá thư mục cũ trong /root/ (sau khi chắc chắn OK)
        sudo rm -rf /root/...
```

---

## 8. Xử lý các tình huống đặc biệt

### Dự án cần đọc/ghi file ngoài thư mục `/opt/`
```bash
# Ví dụ: bot cần ghi log ra /var/log/mybot/
sudo mkdir -p /var/log/mybot
sudo chown bot-nhiecvu:bot-nhiecvu /var/log/mybot
```

### Dự án dùng Node.js thay vì Python
```ini
# Trong file .service thay ExecStart thành:
ExecStart=/usr/bin/node /opt/TÊN_DỰ_ÁN/index.js
```

### Dự án dùng Node.js với PM2
```bash
# Chạy PM2 bằng user riêng
sudo -u bot-trading pm2 start /opt/bot-trading/index.js --name bot-trading
sudo -u bot-trading pm2 save
```

### Dự án cần kết nối database (MySQL/PostgreSQL)
```bash
# Cấp quyền user DB cho projectuser
# MySQL:
mysql -u root -e "GRANT ALL ON mydb.* TO 'bot-nhiecvu'@'localhost';"
```

### Kiểm tra user nào đang chạy process nào
```bash
ps aux | grep python
ps aux | grep node
# Cột đầu tiên là username — đảm bảo không còn root
```

---

## 9. Lệnh hay dùng hàng ngày

```bash
# ── Xem tất cả service đang chạy ──
systemctl list-units --type=service --state=running

# ── Xem service nào đang lỗi ──
systemctl list-units --type=service --state=failed

# ── Xem log của 1 service ──
journalctl -u TÊN_SERVICE -f          # realtime
journalctl -u TÊN_SERVICE -n 100      # 100 dòng gần nhất
journalctl -u TÊN_SERVICE --since today

# ── Quản lý service ──
sudo systemctl start   TÊN_SERVICE    # khởi động
sudo systemctl stop    TÊN_SERVICE    # dừng
sudo systemctl restart TÊN_SERVICE    # kh��i động lại
sudo systemctl status  TÊN_SERVICE    # xem trạng thái
sudo systemctl enable  TÊN_SERVICE    # tự chạy khi boot
sudo systemctl disable TÊN_SERVICE    # bỏ tự chạy khi boot

# ── Xem user nào đang chạy process ──
ps aux | grep python
ps aux | grep node

# ── Liệt kê tất cả system user ──
getent passwd | grep -v nologin | awk -F: '$3 < 1000'
# hoặc xem tất cả user của dự án:
getent passwd | grep /usr/sbin/nologin

# ── Kiểm tra quyền thư mục ──
ls -la /opt/

# ── Xem user đang sở hữu file nào ──
find /opt -user bot-nhiecvu
```

---

## ⚠️ Những lỗi hay gặp khi chuyển đổi

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `Permission denied` | User chưa có quyền thư mục | `sudo chown -R user:user /opt/dự_án` |
| `venv không chạy được` | Copy venv cũ từ `/root/` | Xoá và tạo lại venv |
| `BOT_TOKEN = None` | Thiếu `EnvironmentFile` trong service | Thêm `EnvironmentFile=/opt/.../env` |
| `Module not found` | Cài pip bằng root, không phải user | `sudo -u user venv/bin/pip install ...` |
| `active (start)` mãi không lên `running` | Bot crash ngay khi start | `journalctl -u service -n 50` xem lỗi |
| Service không tự restart khi reboot | Chưa `enable` | `sudo systemctl enable TÊN_SERVICE` |