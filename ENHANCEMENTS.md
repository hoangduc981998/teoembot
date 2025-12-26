# Teoembot - Enhanced Version

## Tổng quan
Teoembot là một Telegram bot thông minh chuyên về cá độ bóng đá, có khả năng trò chuyện tự nhiên như người thật với AI.

## Cải tiến mới (V9)

### 1. Xử Lý Lỗi và Độ Ổn Định
- ✅ **Logging chi tiết**: Sử dụng Python logging với file log và console output
- ✅ **Input validation**: Kiểm tra tin nhắn để tránh XSS và injection attacks
- ✅ **Try-except cải tiến**: Tất cả các hàm có error handling với fallback
- ✅ **Rate limiting**: Sử dụng `aiolimiter` để giới hạn 20 msg/phút (Telegram) và 10 API calls/phút (OpenAI)

### 2. Bảo Mật và Rủi Ro
- ✅ **Mã hóa API keys**: Sử dụng `cryptography` (Fernet) để mã hóa .env
- ✅ **Whitelist chat IDs**: Chỉ hoạt động trong chat `-1001518116463` và `-1002336255712`
- ✅ **Retry logic**: Sử dụng `tenacity` với exponential backoff cho OpenAI API
- ✅ **Quota check**: Giới hạn 100 OpenAI calls/hour để tránh chi phí cao

### 3. Hiệu Suất và Tối Ưu Hóa
- ✅ **TTLCache**: Thay thế MD5 cache bằng `cachetools.TTLCache` với TTL 10 phút
- ✅ **Auto cleanup**: Dùng `atexit` để tự động xóa file tạm khi thoát
- ✅ **Unit tests**: Pytest với pytest-asyncio cho các hàm chính

### 4. Persistence và Scalability
- ✅ **SQLite database**: Lưu trữ trending_topics và user_context
- ✅ **SQLAlchemy ORM**: Quản lý database dễ dàng và an toàn

### 5. Bot Trò Chuyện Giống Người (V10 - Enhanced)
- ✅ **Prompt cải tiến**: Thêm rules chi tiết về giữ chủ đề, tránh lan man, giảm teencode lặp lại
- ✅ **Trending phrases**: Tích hợp 60+ câu hot trend từ TikTok/Facebook (memes, reactions)
- ✅ **Lịch sử mở rộng**: Tăng từ 10 lên 15-20 tin nhắn cho context tốt hơn
- ✅ **Context summarization nâng cao**: Tóm tắt chi tiết hơn (2-3 câu), xác định chủ đề chính
- ✅ **Semantic understanding**: Phân tích ngữ cảnh nhóm để trả lời phù hợp
- ✅ **Phản hồi ngắn gọn**: Giữ ở 3-8 từ, token limit 50
- ✅ **Relevance check cải tiến**: Kiểm tra liên quan dựa trên history và trending topics
- ✅ **Response variation**: Tự động thay đổi cách diễn đạt để tránh lặp lại
- ✅ **Natural fallbacks**: Dùng trending phrases thay vì hardcoded responses

## Cài đặt

```bash
# Clone repository
git clone https://github.com/hoangduc981998/teoembot.git
cd teoembot

# Cài đặt dependencies
pip install -r requirements.txt

# Tạo file .env
cp .env.example .env
# Điền thông tin: API_ID, API_HASH, OPENAI_API_KEY, SESSION_NAME
```

## Cấu hình

### File .env
```env
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
OPENAI_API_KEY=your_openai_api_key
SESSION_NAME=teocakhia
```

### Mã hóa API Keys (Optional)
Để mã hóa OPENAI_API_KEY:
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
cipher = Fernet(key)
encrypted = cipher.encrypt(b"your_api_key")
print(f"ENC:{encrypted.decode()}")
```
Sau đó thêm `ENC:` prefix vào .env

## Chạy Bot

```bash
# Tạo session lần đầu
python create_session.py

# Chạy bot
python teoembot.py
```

## Chạy Tests

```bash
# Chạy tất cả tests
pytest test_teoembot.py -v

# Chạy với coverage
pytest test_teoembot.py --cov=teoembot --cov-report=html
```

## Cấu trúc Database

### Table: trending_topics
- id (Integer, Primary Key)
- chat_id (Integer)
- word (String)
- timestamp (Float)

### Table: user_contexts
- id (Integer, Primary Key)
- chat_id (Integer)
- user_id (Integer)
- last_topic (String)
- sentiment (String)
- last_interaction (Float)
- interaction_count (Integer)
- context_data (JSON)

## Logs

Bot ghi logs vào:
- Console (stdout)
- File: `teoembot.log`

Levels: DEBUG, INFO, WARNING, ERROR

## Rate Limits

- **Telegram**: 20 messages/minute
- **OpenAI**: 10 API calls/minute
- **Quota**: 100 OpenAI calls/hour

## Whitelist Chat IDs

Bot chỉ hoạt động trong các chat:
- `-1001518116463`
- `-1002336255712`

## Tính năng nổi bật

1. **Mood System**: Bot có 5 trạng thái tâm trạng (hype, chill, mệt, tỉnh, say nhẹ)
2. **Trending Topics**: Tự động phát hiện chủ đề hot trong nhóm
3. **Smart Reactions**: Tự động react emoji phù hợp với sentiment
4. **Human-like Typing**: Giả lập đánh máy và sửa lỗi như người thật
5. **Vietnamese Typos**: Tự động thêm lỗi chính tả Tiếng Việt tự nhiên
6. **Image Recognition**: Nhận diện và comment ảnh bằng GPT-4o-mini
7. **Context-aware**: Nhớ ngữ cảnh và chủ đề cuộc trò chuyện

## Dependencies

- `telethon`: Telegram client
- `openai`: OpenAI API client
- `python-dotenv`: Environment variables
- `aiolimiter`: Async rate limiting
- `tenacity`: Retry with exponential backoff
- `cachetools`: TTL cache
- `cryptography`: Encryption for API keys
- `sqlalchemy`: ORM for SQLite
- `pytest`: Testing framework
- `pytest-asyncio`: Async test support

## Bảo mật

1. Không commit `.env`, `.session`, `.encryption_key`
2. API keys được mã hóa với Fernet
3. Input validation chống XSS/injection
4. Whitelist chat IDs
5. Rate limiting để tránh abuse
6. Quota check để kiểm soát chi phí

## License

MIT

## Contact

GitHub: [hoangduc981998](https://github.com/hoangduc981998)
