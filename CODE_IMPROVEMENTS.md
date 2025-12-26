# Key Code Examples - Before and After

## 1. Error Handling & Logging

### Before (V8):
```python
def debug_log(msg):
    if DEBUG:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] 🐛 {msg}")

try:
    # some code
except Exception as e:
    print(f"❌ Lỗi: {e}")
```

### After (V9):
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('teoembot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def debug_log(msg):
    if DEBUG:
        logger.debug(msg)

try:
    # some code
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
```

## 2. Cache System

### Before (V8):
```python
message_cache = {}

def get_message_hash(text):
    return hashlib.md5(text.lower().encode()).hexdigest()

def get_cached_response(text):
    msg_hash = get_message_hash(text)
    if msg_hash in message_cache:
        cached = message_cache[msg_hash]
        if time.time() - cached['time'] < 600:
            return cached['response']
    return None

def cache_response(text, response):
    msg_hash = get_message_hash(text)
    message_cache[msg_hash] = {
        'response': response,
        'time': time.time()
    }
    if len(message_cache) > 100:
        oldest = min(message_cache.items(), key=lambda x: x[1]['time'])
        del message_cache[oldest[0]]
```

### After (V9):
```python
from cachetools import TTLCache

message_cache = TTLCache(maxsize=100, ttl=600)

def get_cached_response(text):
    try:
        text_key = text.lower().strip()
        return message_cache.get(text_key)
    except Exception as e:
        logger.error(f"Cache retrieval error: {e}")
        return None

def cache_response(text, response):
    try:
        text_key = text.lower().strip()
        message_cache[text_key] = response
    except Exception as e:
        logger.error(f"Cache storage error: {e}")
```

## 3. Rate Limiting

### Before (V8):
```python
RATE_LIMIT_SECONDS = 10
last_chat_time = {}

# In handler:
if unique_key in last_chat_time:
    time_diff = now - last_chat_time[unique_key]
    if time_diff < RATE_LIMIT_SECONDS:
        return
```

### After (V9):
```python
from aiolimiter import AsyncLimiter

telegram_limiter = AsyncLimiter(max_rate=20, time_period=60)
openai_limiter = AsyncLimiter(max_rate=10, time_period=60)

# In handler:
async with telegram_limiter:
    await client.send_message(...)

async with openai_limiter:
    response = await call_openai_with_retry(...)
```

## 4. OpenAI API with Retry Logic

### Before (V8):
```python
async def get_ai_reply_multimodal(...):
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=80,
            temperature=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Lỗi AI: {e}")
        return random.choice(["uh", "oke r", "vl"])
```

### After (V9):
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)
async def call_openai_with_retry(messages, max_tokens=50, temperature=0.9):
    async with openai_limiter:
        try:
            client = get_ai_client()
            if client is None:
                raise Exception("OpenAI client not initialized")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
```

## 5. Input Validation

### Before (V8):
```python
# No input validation
msg_text = event.raw_text.lower() if event.raw_text else ""
```

### After (V9):
```python
def validate_message_input(text):
    if not text:
        return True
    
    suspicious_patterns = [
        r'<script',
        r'javascript:',
        r'onerror=',
        r'eval\(',
        r'exec\('
    ]
    
    text_lower = text.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, text_lower):
            logger.warning(f"Suspicious pattern detected: {pattern}")
            return False
    
    if len(text) > 4000:
        logger.warning("Message too long")
        return False
    
    return True

# In handler:
if msg_text and not validate_message_input(msg_text):
    logger.warning(f"Invalid message input from chat {chat_id}")
    return
```

## 6. Database Persistence

### Before (V8):
```python
# Only in-memory storage
trending_topics = defaultdict(lambda: deque(maxlen=20))
user_context = defaultdict(lambda: {...})
```

### After (V9):
```python
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class TrendingTopic(Base):
    __tablename__ = 'trending_topics'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    word = Column(String)
    timestamp = Column(Float)

engine = create_engine('sqlite:///teoembot.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def save_trending_to_db(chat_id, word):
    try:
        db_session = Session()
        topic = TrendingTopic(chat_id=chat_id, word=word, timestamp=time.time())
        db_session.add(topic)
        db_session.commit()
        db_session.close()
    except Exception as e:
        logger.error(f"Failed to save trending topic: {e}")
```

## 7. Security - Whitelist

### Before (V8):
```python
# No whitelist - responds in all chats
if event.is_private:
    return
```

### After (V9):
```python
ALLOWED_CHAT_IDS = {-1001518116463, -1002336255712}

# In handler:
if event.chat_id not in ALLOWED_CHAT_IDS:
    logger.debug(f"Skipped: Chat {event.chat_id} not in whitelist")
    return
```

## 8. Encryption Support

### Before (V8):
```python
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
```

### After (V9):
```python
from cryptography.fernet import Fernet

def get_encryption_key():
    key_file = '.encryption_key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

def decrypt_env_value(encrypted_value, cipher):
    try:
        if encrypted_value and encrypted_value.startswith('ENC:'):
            return cipher.decrypt(encrypted_value[4:].encode()).decode()
        return encrypted_value
    except Exception as e:
        logger.warning(f"Failed to decrypt value, using as-is: {e}")
        return encrypted_value

cipher_suite = Fernet(get_encryption_key())
OPENAI_API_KEY = decrypt_env_value(os.getenv('OPENAI_API_KEY'), cipher_suite)
```

## 9. Context Summarization

### Before (V8):
```python
# No context summarization - just raw history
for h in history[-5:]:
    messages.append({"role": "user", "content": f"{h['name']}: {h['text']}"})
```

### After (V9):
```python
async def summarize_context(history):
    try:
        if len(history) < 3:
            return None
        
        history_text = "\n".join([f"{h['name']}: {h['text']}" for h in history[-5:]])
        
        messages = [{
            "role": "system",
            "content": "Tóm tắt ngắn gọn nội dung cuộc trò chuyện (1-2 câu, tiếng Việt, dùng teencode)."
        }, {
            "role": "user",
            "content": history_text
        }]
        
        summary = await call_openai_with_retry(messages, max_tokens=30, temperature=0.7)
        logger.info(f"Context summary: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Failed to summarize context: {e}")
        return None

# In get_ai_reply_multimodal:
if len(history) >= 3:
    context_summary = await summarize_context(history)
    if context_summary:
        messages.append({
            "role": "system",
            "content": f"Tóm tắt ngữ cảnh: {context_summary}"
        })

for h in history[-10:]:  # Expanded from 5 to 10
    messages.append({"role": "user", "content": f"{h['name']}: {h['text']}"})
```

## 10. Cleanup on Exit

### Before (V8):
```python
# Manual cleanup
if image_path and os.path.exists(image_path):
    try:
        os.remove(image_path)
    except:
        pass
```

### After (V9):
```python
import atexit

temp_files = []

def cleanup_temp_files():
    logger.info("Cleaning up temporary files...")
    for file_path in temp_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed temp file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove {file_path}: {e}")

atexit.register(cleanup_temp_files)

# When creating temp file:
image_path = f"temp_img_{chat_id}_{event.message.id}.jpg"
temp_files.append(image_path)  # Track for cleanup
```

## Summary

The enhancements transform teoembot from a simple bot to an enterprise-grade application with:
- **Professional logging** instead of print statements
- **TTL-based caching** instead of manual expiration
- **Rate limiting** to prevent API abuse
- **Retry logic** for resilient API calls
- **Input validation** for security
- **Database persistence** for scalability
- **Whitelist security** for controlled access
- **Encryption support** for sensitive data
- **Context summarization** for better AI responses
- **Automatic cleanup** for resource management
- **Comprehensive testing** for reliability
