import os
import random
import asyncio
import re
import datetime
import base64
import time
import hashlib
import logging
import atexit
import json
from collections import defaultdict, deque
from telethon import TelegramClient, events, functions, types
from openai import OpenAI
from dotenv import load_dotenv
from aiolimiter import AsyncLimiter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('teoembot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- ENCRYPTION UTILITIES ---
def get_encryption_key():
    """Get or create encryption key for API keys"""
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
    """Decrypt environment value if it's encrypted"""
    try:
        if encrypted_value and encrypted_value.startswith('ENC:'):
            return cipher.decrypt(encrypted_value[4:].encode()).decode()
        return encrypted_value
    except Exception as e:
        logger.warning(f"Failed to decrypt value, using as-is: {e}")
        return encrypted_value

# Initialize encryption
cipher_suite = Fernet(get_encryption_key())

# --- CẤU HÌNH TỪ .ENV ---
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
OPENAI_API_KEY = decrypt_env_value(os.getenv('OPENAI_API_KEY'), cipher_suite)
SESSION_NAME = os.getenv('SESSION_NAME', 'teocakhia')

# --- WHITELIST CHAT IDs ---
ALLOWED_CHAT_IDS = {-1001518116463, -1002336255712}

# Cấu hình hành vi - ĐIỀU CHỈNH ĐỂ DEBUG
RATE_LIMIT_SECONDS = 10  # Giảm xuống 10s để test
TRIGGER_PROBABILITY = 0.5  # Tăng lên 50% để dễ test
SLEEP_START_HOUR = 25  # Tắt tính năng ngủ (>24h)
SLEEP_END_HOUR = 26

# DEBUG MODE
DEBUG = True  # Bật debug log

# Response quality constants
MIN_MEANINGFUL_LENGTH = 3  # Minimum character length for meaningful responses
MAX_HISTORY_TEXT_LENGTH = 50  # Maximum length for history text in context
RECENT_TOPICS_COUNT = 3  # Number of recent topics to consider for relevance

# Rate limiters
telegram_limiter = AsyncLimiter(max_rate=20, time_period=60)  # 20 messages per minute
openai_limiter = AsyncLimiter(max_rate=10, time_period=60)  # 10 API calls per minute

# Dữ liệu templates
CLUBS = ["MU", "Man City", "Arsenal", "Liverpool", "Real", "Barca", "Chelsea", "Bayern", "PSG", "Việt Nam"]
KEOS = ["tài 2.5", "xỉu 2.5", "tài 3 hòa", "chấp nửa trái", "đồng banh", "rung tài 0.5"]
COMMENTS = ["sáng cửa", "thơm phức", "hơi bịp nhưng vẫn ngon", "tín vl", "nhồi mạnh", "xa bờ thì bám vào"]

# Load trending phrases from JSON
def load_trending_phrases():
    """Load trending phrases from JSON config file"""
    try:
        phrases_file = os.path.join(os.path.dirname(__file__), 'trending_phrases.json')
        with open(phrases_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load trending phrases: {e}")
        return {
            "memes": ["cái gì vậy trời", "ngon nghẻ", "sợ anh em lắm"],
            "reactions": {
                "win": ["đỉnh của đỉnh"],
                "loss": ["gg wp"],
                "football": ["trận này căng"],
                "betting": ["kèo ngon lắm"],
                "casual": ["oke nha"]
            },
            "context_aware": {
                "agree": ["ừ đúng rồi"],
                "disagree": ["chưa chắc đâu"],
                "surprise": ["trời ơi"],
                "laugh": ["chết cười"]
            }
        }

TRENDING_PHRASES = load_trending_phrases()

def get_random_trending_phrase(category=None, subcategory=None):
    """Get a random trending phrase based on category"""
    try:
        if category and subcategory:
            phrases = TRENDING_PHRASES.get(category, {}).get(subcategory, [])
            if phrases:
                return random.choice(phrases)
        elif category:
            phrases = TRENDING_PHRASES.get(category, [])
            if phrases:
                return random.choice(phrases)
        # Return random meme as fallback
        memes = TRENDING_PHRASES.get('memes', [])
        if memes:
            return random.choice(memes)
        return 'oke'  # Final fallback
    except Exception as e:
        logger.error(f"Error getting trending phrase: {e}")
        return None

# AI Client - lazy initialization
ai_client = None
client = None

def get_ai_client():
    """Lazy initialization of OpenAI client"""
    global ai_client
    if ai_client is None:
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not set, using mock client")
            return None
        ai_client = OpenAI(api_key=OPENAI_API_KEY)
    return ai_client

def get_telegram_client():
    """Lazy initialization of Telegram client"""
    global client
    if client is None:
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    return client

# --- DATABASE SETUP ---
Base = declarative_base()

class TrendingTopic(Base):
    __tablename__ = 'trending_topics'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    word = Column(String)
    timestamp = Column(Float)

class UserContext(Base):
    __tablename__ = 'user_contexts'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    user_id = Column(Integer)
    last_topic = Column(String)
    sentiment = Column(String)
    last_interaction = Column(Float)
    interaction_count = Column(Integer)
    context_data = Column(JSON)

# Initialize database
engine = create_engine('sqlite:///teoembot.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Memory systems
last_chat_time = {}
user_context = defaultdict(lambda: {
    'last_topic': None,
    'sentiment': 'neutral',
    'last_interaction': 0,
    'interaction_count': 0
})
trending_topics = defaultdict(lambda: deque(maxlen=20))

# Replace MD5 cache with TTLCache
message_cache = TTLCache(maxsize=100, ttl=600)  # 100 items, 10 min TTL

# Moods system with emotional states
MOODS = ['hype', 'chill', 'mệt', 'tỉnh', 'say nhẹ']
EMOTIONAL_STATES = ['excited', 'skeptical', 'thoughtful', 'playful', 'confident', 'worried']
current_mood = {'state': 'chill', 'changed_at': time.time(), 'emotion': 'playful'}

# Track temporary files for cleanup
temp_files = []

# Topic memory for conversation continuity
topic_memory = defaultdict(lambda: {'last_topic': None, 'timestamp': 0, 'questions_asked': 0})

def cleanup_temp_files():
    """Clean up temporary files on exit"""
    logger.info("Cleaning up temporary files...")
    for file_path in temp_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed temp file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove {file_path}: {e}")

# Register cleanup function
atexit.register(cleanup_temp_files)

# Database persistence functions
def save_trending_to_db(chat_id, word):
    """Save trending topic to database"""
    try:
        db_session = Session()
        topic = TrendingTopic(chat_id=chat_id, word=word, timestamp=time.time())
        db_session.add(topic)
        db_session.commit()
        db_session.close()
    except Exception as e:
        logger.error(f"Failed to save trending topic: {e}")

def load_trending_from_db(chat_id, hours=1):
    """Load recent trending topics from database"""
    try:
        db_session = Session()
        cutoff = time.time() - (hours * 3600)
        topics = db_session.query(TrendingTopic).filter(
            TrendingTopic.chat_id == chat_id,
            TrendingTopic.timestamp > cutoff
        ).all()
        db_session.close()
        return [t.word for t in topics]
    except Exception as e:
        logger.error(f"Failed to load trending topics: {e}")
        return []

def save_user_context_to_db(chat_id, user_id, context):
    """Save user context to database"""
    try:
        db_session = Session()
        user_ctx = db_session.query(UserContext).filter_by(
            chat_id=chat_id, user_id=user_id
        ).first()
        
        if user_ctx:
            user_ctx.last_topic = context.get('last_topic')
            user_ctx.sentiment = context.get('sentiment')
            user_ctx.last_interaction = context.get('last_interaction')
            user_ctx.interaction_count = context.get('interaction_count')
            user_ctx.context_data = context
        else:
            user_ctx = UserContext(
                chat_id=chat_id,
                user_id=user_id,
                last_topic=context.get('last_topic'),
                sentiment=context.get('sentiment'),
                last_interaction=context.get('last_interaction'),
                interaction_count=context.get('interaction_count'),
                context_data=context
            )
            db_session.add(user_ctx)
        
        db_session.commit()
        db_session.close()
    except Exception as e:
        logger.error(f"Failed to save user context: {e}")

def validate_message_input(text):
    """Validate message input to prevent injection"""
    if not text:
        return True
    
    # Check for suspicious patterns
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
    
    # Check message length
    if len(text) > 4000:
        logger.warning("Message too long")
        return False
    
    return True

def debug_log(msg):
    """Print debug messages"""
    if DEBUG:
        logger.debug(msg)

# --- MOOD SYSTEM ---
def calculate_mood():
    global current_mood
    now = time.time()
    
    if now - current_mood['changed_at'] > random.randint(1800, 3600):
        hour = datetime.datetime.now().hour
        
        if 22 <= hour or hour < 1:
            current_mood['state'] = random.choice(['say nhẹ', 'mệt', 'chill'])
            current_mood['emotion'] = random.choice(['playful', 'thoughtful'])
        elif 7 <= hour < 12:
            current_mood['state'] = random.choice(['tỉnh', 'chill', 'hype'])
            current_mood['emotion'] = random.choice(['excited', 'confident'])
        elif 18 <= hour < 22:
            current_mood['state'] = random.choice(['hype', 'chill'])
            current_mood['emotion'] = random.choice(['excited', 'playful', 'confident'])
        else:
            current_mood['state'] = 'chill'
            current_mood['emotion'] = random.choice(['thoughtful', 'playful'])
        
        current_mood['changed_at'] = now
    
    return current_mood['state'], current_mood.get('emotion', 'playful')

def get_emotional_context(text, history):
    """Analyze conversation context to determine appropriate emotion"""
    text_lower = text.lower() if text else ""
    
    # Check for winning/losing context
    if any(w in text_lower for w in ['thắng', 'lãi', 'ăn', 'đỉnh', 'ngon']):
        return 'excited'
    elif any(w in text_lower for w in ['thua', 'sập', 'cháy', 'mất']):
        return 'worried'
    elif any(w in text_lower for w in ['kèo', 'tỷ lệ', 'phân tích', 'nghiên cứu']):
        return 'thoughtful'
    # Check skeptical before confident (to catch "không chắc" before "chắc")
    elif any(w in text_lower for w in ['không chắc', 'rủi ro', 'nghi ngờ']):
        return 'skeptical'
    elif any(w in text_lower for w in ['chắc', 'ez', 'dễ', 'ăn chắc']):
        return 'confident'
    
    # Check history sentiment
    if history and len(history) >= 3:
        recent_text = ' '.join([h.get('text', '')[:50].lower() for h in history[-3:]])
        if 'haha' in recent_text or 'lol' in recent_text or 'kkk' in recent_text:
            return 'playful'
    
    return 'playful'

# --- TRENDING TOPICS ---
def update_trending(chat_id, text):
    """Update trending topics with database persistence"""
    try:
        words = re.findall(r'\w+', text.lower())
        important_words = [w for w in words if len(w) > 3 and w not in ['đang', 'này', 'thôi', 'nhỉ']]
        
        for word in important_words:
            trending_topics[chat_id].append({
                'word': word,
                'time': time.time()
            })
            # Save to database
            save_trending_to_db(chat_id, word)
    except Exception as e:
        logger.error(f"Error updating trending topics: {e}")

def get_trending_topic(chat_id):
    """Get trending topic with database fallback"""
    try:
        now = time.time()
        recent = [t['word'] for t in trending_topics[chat_id] if now - t['time'] < 300]
        
        # Also load from database
        db_topics = load_trending_from_db(chat_id, hours=1)
        recent.extend(db_topics)
        
        if not recent:
            return None
        
        word_count = defaultdict(int)
        for word in recent:
            word_count[word] += 1
        
        top_word = max(word_count.items(), key=lambda x: x[1])
        return top_word[0] if top_word[1] >= 3 else None
    except Exception as e:
        logger.error(f"Error getting trending topic: {e}")
        return None

def get_sample_trending_phrases(count=3):
    """Get sample trending phrases for prompt"""
    memes = TRENDING_PHRASES.get('memes', [])
    if not memes:
        fallback = get_random_trending_phrase()
        return fallback if fallback else "cái gì vậy trời, ngon nghẻ"
    
    # Ensure we don't sample more than available
    available_memes = memes[:10]
    sample_count = min(count, len(available_memes))
    sample_memes = random.sample(available_memes, sample_count)
    return ", ".join(sample_memes)

# --- PROMPT AI ---
def get_system_prompt(emotion='playful'):
    mood, _ = calculate_mood()
    
    mood_traits = {
        'hype': 'Đang phê, năng lượng cao, hào hứng nhưng KHÔNG lặp lại "kkk", "vl" quá nhiều',
        'chill': 'Bình thường, thoải mái, không quá nhiệt tình',
        'mệt': 'Hơi lười, trả lời ngắn gọn, thỉnh thoảng "ừ", "ok"',
        'tỉnh': 'Tỉnh táo, sáng sớm, trả lời lịch sự hơn một chút',
        'say nhẹ': 'Hơi loạn, đánh máy sai chính tả nhiều hơn'
    }
    
    emotion_traits = {
        'excited': 'Hào hứng, phấn khích, tích cực',
        'skeptical': 'Nghi ngờ, thận trọng, cẩn thận',
        'thoughtful': 'Suy nghĩ sâu, phân tích kỹ, đưa ra lý do',
        'playful': 'Vui vẻ, thoải mái, dễ chịu',
        'confident': 'Tự tin, chắc chắn, quyết đoán',
        'worried': 'Lo lắng, bất an, thận trọng'
    }
    
    # Get some trending phrases to include in prompt
    memes_text = get_sample_trending_phrases(count=3)
    
    # Get emotional responses for this emotion
    emotional_responses = TRENDING_PHRASES.get('emotional_responses', {}).get(emotion, [])
    emotion_examples = ', '.join(emotional_responses[:3]) if emotional_responses else ''
    
    return (
        f"Bạn là Tèo, dân chơi cá độ bóng đá thật. Mood: {mood} ({mood_traits[mood]}). "
        f"Cảm xúc hiện tại: {emotion} ({emotion_traits.get(emotion, 'bình thường')}). "
        "QUY TẮC VÀNG - ĐỌC KỸ: "
        "1. Chat CỰC NGẮN (3-8 từ), không viết hoa, không dấu câu nhiều. "
        "2. Teencode TIẾT CHẾ: Dùng 'kkk', 'vl', 'r', 'đù' nhưng KHÔNG lặp lại liên tục. Mỗi từ chỉ 1 lần/câu. "
        f"3. Câu hot trend: Thỉnh thoảng dùng '{memes_text}' hoặc tương tự để tự nhiên. "
        f"4. [EMOTION] Thể hiện cảm xúc {emotion}: Dùng '{emotion_examples}' khi phù hợp. "
        "5. [VISION] Có ảnh: Bình luận ngắn gọn (khen/chê/hỏi han). "
        "6. [REPLY] Bị trả lời: Đáp lại súc tích, đúng trọng tâm, PHẢI liên quan tin nhắn trước. "
        "7. [BÓNG ĐÁ] Nói rõ tên đội, VD: 'mu vs arsenal', KHÔNG nói 'trận này'. Biết các đội bóng phổ biến. "
        "8. [DEEP THINKING] Đôi khi suy nghĩ sâu: Phân tích kèo chi tiết, đưa lý do cụ thể (vd: 'mu hàng thủ yếu, tài 2.5 ngon'). "
        "9. [FOLLOW UP] Thỉnh thoảng hỏi ngược: 'sao lại thế?', 'anh nghĩ sao?', 'chắc không?' để tiếp tục cuộc trò chuyện. "
        "10. [STICKER] Tình huống chỉ cần cười: Thêm [sticker] cuối câu. "
        "11. [EMOTION TAG] Cuối câu text: Thêm [vui], [buon], [hai], [like], [wow] nếu phù hợp. "
        "12. Đôi khi chỉ cần rep bằng 'uh', 'oke r', 'được' là đủ. ĐỪNG cố gắng quá. "
        "13. [CONTEXT NHẬP TÂM] ĐỌC KỸ lịch sử chat, hiểu chủ đề đang bàn (bóng đá/cá độ/vui vẻ), "
        "tham chiếu tin nhắn trước, KHÔNG lan man hoặc đổi chủ đề tự nhiên. "
        "14. [RELEVANCE] CHỈ trả lời nếu có liên quan đến ngữ cảnh nhóm. Nếu không chắc, dùng phản ứng ngắn ('uh', 'oke'). "
        "15. [BIẾN THỂ] Tránh lặp lại cùng một cách trả lời. Sử dụng nhiều cách diễn đạt khác nhau cho ý nghĩa tương tự. "
        "16. [TỰ NHIÊN] Nói như người thật, có cảm xúc, không ngáo ngơ, không robot. Hiểu bóng đá, cá độ, meme Việt. "
        "17. [INNER THOUGHT] Trước khi trả lời về chủ đề quan trọng, suy nghĩ bên trong (vd: 'để xem... arsenal phong độ cao...'). "
    )


# --- RULE-BASED RESPONSES ---
SIMPLE_PATTERNS = {
    r'\b(kèo gì|kèo nào|kèo j)\b': lambda: get_random_match_text(),
    r'\b(ăn|thắng|lãi)\b.*\b(bao nhiêu|bn|mấy)\b': lambda: random.choice([
        f"ăn {random.randint(2,8)}tr kkk",
        "lãi vài ba củ thôi",
        "hòa vốn vl"
    ]),
    r'\b(thua|cháy|sập)\b': lambda: random.choice([
        "rip bro",
        "gỡ lại đi",
        "thôi nghỉ đi kkk"
    ]),
    r'\b(chào|hi|hello|yo)\b': lambda: random.choice([
        "ê chào",
        "yo bruh",
        "hê nhô"
    ]),
    r'\b(ai|mày|bot)\s+(đang|có|ở)\b': lambda: random.choice([
        "tao đây",
        "uh có j",
        "hm"
    ])
}

def check_simple_response(text):
    text_lower = text.lower()
    
    for pattern, response_func in SIMPLE_PATTERNS.items():
        if re.search(pattern, text_lower):
            return response_func()
    
    return None

# --- CACHE SYSTEM (TTLCache replaces MD5) ---
# Track recent responses to avoid repetition
recent_responses = deque(maxlen=10)

def get_cached_response(text):
    """Get cached response using TTLCache"""
    try:
        text_key = text.lower().strip()
        return message_cache.get(text_key)
    except Exception as e:
        logger.error(f"Cache retrieval error: {e}")
        return None

def cache_response(text, response):
    """Cache response using TTLCache with automatic eviction"""
    try:
        text_key = text.lower().strip()
        message_cache[text_key] = response
    except Exception as e:
        logger.error(f"Cache storage error: {e}")

def add_response_variation(response):
    """Add variation to response to avoid repetition with synonym replacement"""
    try:
        # Check if this response was recently used
        if response in recent_responses:
            # Get synonyms from trending phrases
            synonyms = TRENDING_PHRASES.get('synonyms', {})
            
            # Try to replace common words with synonyms
            for key, alts in synonyms.items():
                if key in response.lower():
                    variation = response.lower().replace(key, random.choice(alts))
                    recent_responses.append(variation)
                    return variation
            
            # If no synonym found, return as is
            recent_responses.append(response)
            return response
        
        # Track this response
        recent_responses.append(response)
        return response
    except Exception as e:
        logger.error(f"Error adding variation: {e}")
        return response

def should_ask_follow_up_question(history, context):
    """Determine if bot should ask a follow-up question"""
    try:
        # Don't ask too many questions
        chat_id = context.get('chat_id', 0)
        if topic_memory[chat_id]['questions_asked'] >= 2:
            # Reset counter occasionally
            if random.random() < 0.3:
                topic_memory[chat_id]['questions_asked'] = 0
            return False
        
        # Ask questions when:
        # 1. Conversation is active (3+ messages)
        # 2. Random chance (20%)
        # 3. Topic is interesting (football, betting)
        if len(history) >= 3 and random.random() < 0.2:
            return True
        
        # Ask if recent messages mention interesting topics
        if history and len(history) >= 2:
            recent_text = ' '.join([h.get('text', '')[:50].lower() for h in history[-2:]])
            interesting_topics = ['kèo', 'bóng', 'trận', 'đội', 'cược', 'thắng', 'thua']
            if any(topic in recent_text for topic in interesting_topics):
                if random.random() < 0.15:
                    return True
        
        return False
    except Exception as e:
        logger.error(f"Error in should_ask_follow_up_question: {e}")
        return False

def get_follow_up_question():
    """Get a random follow-up question"""
    questions = TRENDING_PHRASES.get('follow_up_questions', ['sao lại thế?', 'anh nghĩ sao?'])
    return random.choice(questions)

def add_thinking_depth(response, emotion, context):
    """Add thinking depth to response based on emotion and context"""
    try:
        # Only add depth sometimes (30% chance)
        if random.random() > 0.3:
            return response
        
        thinking_prefixes = TRENDING_PHRASES.get('thinking_prefixes', ['hmm', 'để tao nghĩ'])
        
        # For thoughtful or analytical contexts, add reasoning
        if emotion in ['thoughtful', 'skeptical']:
            prefix = random.choice(thinking_prefixes)
            # Add reasoning hint
            return f"{prefix}... {response}"
        
        return response
    except Exception as e:
        logger.error(f"Error adding thinking depth: {e}")
        return response

# --- RANDOM MATCH ---
def get_random_match_text():
    t1, t2 = random.sample(CLUBS, 2)
    return f"{t1} gặp {t2} bắt {random.choice(KEOS)} {random.choice(COMMENTS)} nha"

# --- VIETNAMESE TYPO SIMULATOR ---
def add_vietnamese_typos(text):
    if random.random() > 0.3:
        return text
    
    typo_rules = [
        (r'\bđ\b', 'd'),
        (r'ư', 'u'),
        (r'ơ', 'o'),
        (r'giờ', 'gio'),
        (r'được', 'duoc'),
        (r'không', 'ko'),
        (r'vậy', 'vay'),
        (r'thế', 'the'),
    ]
    
    rule = random.choice(typo_rules)
    return re.sub(rule[0], rule[1], text, count=1)

# --- IMAGE HANDLING ---
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'[^\w\sđĐ]', '', text.lower().strip())

# --- AI CALL WITH RETRY LOGIC ---
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)
async def call_openai_with_retry(messages, max_tokens=50, temperature=0.9):
    """Call OpenAI API with retry logic"""
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

async def check_openai_quota():
    """Check if we should make OpenAI call (basic quota check)"""
    # Simple check: limit calls per hour
    current_hour = datetime.datetime.now().hour
    quota_key = f"quota_{current_hour}"
    
    if not hasattr(check_openai_quota, 'hourly_calls'):
        check_openai_quota.hourly_calls = {}
    
    if quota_key not in check_openai_quota.hourly_calls:
        check_openai_quota.hourly_calls = {quota_key: 0}
    
    # Limit to 100 calls per hour
    if check_openai_quota.hourly_calls[quota_key] >= 100:
        logger.warning("OpenAI quota limit reached for this hour")
        return False
    
    check_openai_quota.hourly_calls[quota_key] += 1
    return True

async def summarize_context(history):
    """Summarize conversation context using OpenAI with more detail"""
    try:
        if len(history) < 3:
            return None
        
        # Expand summary to include more history (last 10 messages instead of 5)
        history_text = "\n".join([f"{h['name']}: {h['text']}" for h in history[-10:]])
        
        messages = [{
            "role": "system",
            "content": (
                "Tóm tắt ngắn gọn cuộc trò chuyện này (2-3 câu, tiếng Việt). "
                "Xác định chủ đề chính (bóng đá, cá độ, vui vẻ), tâm trạng nhóm, "
                "và điểm nổi bật cần nhớ. Dùng teencode tự nhiên."
            )
        }, {
            "role": "user",
            "content": history_text
        }]
        
        # Increase max_tokens from 30 to 60 for more detailed summary
        summary = await call_openai_with_retry(messages, max_tokens=60, temperature=0.7)
        logger.info(f"Context summary: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Failed to summarize context: {e}")
        return None

async def check_relevance(msg_text, context, history):
    """Check if response would be relevant to current context with improved logic"""
    try:
        if not msg_text or len(msg_text.strip()) < MIN_MEANINGFUL_LENGTH:
            return False  # Too short to be meaningful
        
        # If message is very short (3-8 words), it's likely relevant
        word_count = len(msg_text.split())
        if word_count <= 8:
            return True
        
        # Check if message relates to trending topic
        if context and context.get('trending'):
            trending = context.get('trending', '').lower()
            msg_lower = msg_text.lower()
            if trending in msg_lower:
                return True
        
        # Check if message relates to recent conversation topics
        if history and len(history) >= 2:
            recent_topics = ' '.join([h.get('text', '')[:MAX_HISTORY_TEXT_LENGTH] for h in history[-RECENT_TOPICS_COUNT:]])
            msg_lower = msg_text.lower()
            # Extract key words from message
            msg_words = set(re.findall(r'\w+', msg_lower))
            topic_words = set(re.findall(r'\w+', recent_topics.lower()))
            # Check for word overlap (at least 1 common word)
            if msg_words & topic_words:
                return True
        
        # Check for specific keywords that indicate it's a casual/relevant response
        casual_words = ['uh', 'oke', 'vl', 'kkk', 'haha', 'lol', 'đồng ý', 'chuẩn', 'phải', 'ừ']
        if any(word in msg_text.lower() for word in casual_words):
            return True
        
        return True  # Default to relevant to avoid over-filtering
    except Exception as e:
        logger.error(f"Relevance check error: {e}")
        return True

async def get_ai_reply_multimodal(msg_text, history, image_path=None, my_previous_msg=None, context=None):
    """Get AI reply with emotional intelligence, deeper thinking, and follow-up questions"""
    try:
        # Check quota before making call
        if not await check_openai_quota():
            logger.warning("Quota exceeded, using fallback")
            trending_fallback = get_random_trending_phrase('reactions', 'casual')
            return trending_fallback if trending_fallback else random.choice(["uh", "oke r", "vl"])
        
        # Determine emotional context
        emotion = get_emotional_context(msg_text or '', history)
        
        messages = [{"role": "system", "content": get_system_prompt(emotion)}]
        
        # Add context summary if available (for conversations with 5+ messages)
        if len(history) >= 5:
            context_summary = await summarize_context(history)
            if context_summary:
                messages.append({
                    "role": "system",
                    "content": f"Tóm tắt ngữ cảnh trước đó: {context_summary}"
                })
        
        if context and context.get('trending'):
            messages.append({
                "role": "system",
                "content": f"Chủ đề đang hot: '{context['trending']}'. Liên quan đến chủ đề này nếu có thể."
            })
        
        # Add emotional guidance
        emotional_guidance = TRENDING_PHRASES.get('emotional_responses', {}).get(emotion, [])
        if emotional_guidance:
            messages.append({
                "role": "system",
                "content": f"Cảm xúc {emotion}: Có thể dùng '{random.choice(emotional_guidance)}' hoặc tương tự."
            })
        
        # Add some trending phrases as examples
        sample_phrase = get_random_trending_phrase()
        if sample_phrase:
            messages.append({
                "role": "system",
                "content": f"Ví dụ câu hot trend: '{sample_phrase}' - dùng tự nhiên khi phù hợp."
            })
        
        # Expand history to 25 messages for better context (gets ~20-24 excluding bot)
        for h in history[-25:]:
            messages.append({"role": "user", "content": f"{h['name']}: {h['text']}"})
        
        user_content = []
        context_intro = ""
        
        if my_previous_msg:
            context_intro = f"(Đang rep lại tin nhắn: '{my_previous_msg[:50]}...'). "
        
        if msg_text:
            user_content.append({"type": "text", "text": f"{context_intro}{msg_text}"})
        else:
            user_content.append({"type": "text", "text": "User gửi ảnh."})
        
        if image_path:
            base64_image = encode_image(image_path)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
            user_content.append({"type": "text", "text": "Nhận xét ảnh này (ngắn gọn)."})
        
        messages.append({"role": "user", "content": user_content})
        
        debug_log(f"Calling OpenAI API with {len(history)} messages, emotion={emotion}...")
        
        # Increase max_tokens from 50 to 80 for deeper responses with reasoning
        result = await call_openai_with_retry(messages, max_tokens=80, temperature=1.0)
        
        debug_log(f"AI Response: {result}")
        
        # Add thinking depth if appropriate
        result = add_thinking_depth(result, emotion, context)
        
        # Possibly add a follow-up question
        if context and should_ask_follow_up_question(history, context):
            follow_up = get_follow_up_question()
            result = f"{result} {follow_up}"
            # Track that we asked a question
            chat_id = context.get('chat_id', 0)
            topic_memory[chat_id]['questions_asked'] += 1
            debug_log(f"Added follow-up question: {follow_up}")
        
        # Check relevance with history
        if not await check_relevance(result, context, history):
            logger.info("Response deemed irrelevant, using contextual fallback")
            # Use emotional phrase as fallback
            emotional_fallback = get_random_trending_phrase('emotional_responses', emotion)
            if emotional_fallback:
                return emotional_fallback
            # Otherwise use casual fallback
            trending_fallback = get_random_trending_phrase('reactions', 'casual')
            return trending_fallback if trending_fallback else random.choice(["uh", "oke", "hmm"])
        
        return result
    
    except Exception as e:
        logger.error(f"❌ AI error: {e}", exc_info=True)
        # Use emotional phrase for errors too
        emotion = context.get('emotion', 'playful') if context else 'playful'
        emotional_fallback = get_random_trending_phrase('emotional_responses', emotion)
        if emotional_fallback:
            return emotional_fallback
        trending_fallback = get_random_trending_phrase('reactions', 'casual')
        return trending_fallback if trending_fallback else random.choice(["uh", "oke r", "vl"])

# --- TYPING SIMULATION ---
async def simulate_human_typing(chat_id, text, reply_to=None):
    """Simulate human typing with rate limiting"""
    try:
        tg_client = get_telegram_client()
        if tg_client is None:
            logger.warning("Telegram client not initialized")
            return
            
        async with telegram_limiter:
            if random.random() < 0.05:
                async with tg_client.action(chat_id, 'typing'):
                    await asyncio.sleep(random.randint(2, 5))
                return
            
            async with tg_client.action(chat_id, 'typing'):
                typing_time = len(text) * random.uniform(0.08, 0.15)
                
                if random.random() < 0.25 and len(text) > 8:
                    mistake_pos = random.randint(-3, -1)
                    fake_text = text[:mistake_pos]
                    
                    await asyncio.sleep(typing_time * 0.6)
                    
                    try:
                        if reply_to:
                            m = await tg_client.send_message(chat_id, fake_text, reply_to=reply_to)
                        else:
                            m = await tg_client.send_message(chat_id, fake_text)
                        
                        await asyncio.sleep(random.uniform(1, 2))
                        
                        final_text = add_vietnamese_typos(text)
                        await tg_client.edit_message(chat_id, m.id, final_text)
                        
                    except Exception as e:
                        logger.error(f"Typing sim error: {e}")
                else:
                    await asyncio.sleep(typing_time)
                    final_text = add_vietnamese_typos(text)
                    
                    try:
                        if reply_to:
                            await tg_client.send_message(chat_id, final_text, reply_to=reply_to)
                        else:
                            await tg_client.send_message(chat_id, final_text)
                    except Exception as e:
                        logger.error(f"Send error: {e}")
    except Exception as e:
        logger.error(f"Typing simulation failed: {e}", exc_info=True)

# --- SMART REACTION ---
async def send_smart_reaction(chat_id, msg_id, sentiment):
    """Send smart reaction with rate limiting"""
    try:
        tg_client = get_telegram_client()
        if tg_client is None:
            return
            
        async with telegram_limiter:
            reaction_map = {
                'positive': ['❤', '🔥', '👍', '💯'],
                'negative': ['😢', '💀', '😭'],
                'funny': ['😂', '🤣', '💀'],
                'surprise': ['😮', '🤯', '👀'],
                'neutral': ['👍', '👀', '🙂']
            }
            
            emo = random.choice(reaction_map.get(sentiment, reaction_map['neutral']))
            
            await asyncio.sleep(random.uniform(0.5, 2))
            await tg_client.send_reaction(chat_id, msg_id, emo)
            debug_log(f"Sent reaction: {emo}")
    except Exception as e:
        logger.error(f"Reaction error: {e}")

# --- SENTIMENT ANALYSIS ---
def analyze_sentiment(text):
    text_lower = text.lower()
    
    if any(w in text_lower for w in ['kkk', 'haha', 'lol', 'lmao', '😂', '🤣']):
        return 'funny'
    elif any(w in text_lower for w in ['vui', 'vãi', 'đỉnh', 'ngon', 'thắng', 'ăn']):
        return 'positive'
    elif any(w in text_lower for w in ['buồn', 'thua', 'sập', 'cháy', 'rip']):
        return 'negative'
    elif any(w in text_lower for w in ['wtf', 'wut', 'sao', 'gì vậy']):
        return 'surprise'
    
    return 'neutral'

# --- MAIN HANDLER ---
async def handler(event):
    try:
        tg_client = get_telegram_client()
        if tg_client is None:
            return
            
        me = await tg_client.get_me()
        
        debug_log(f"📩 New message from chat_id={event.chat_id}")
        
        # --- WHITELIST CHECK ---
        if event.chat_id not in ALLOWED_CHAT_IDS:
            debug_log(f"⏭️ Skipped: Chat {event.chat_id} not in whitelist")
            return
        
        if event.is_private:
            debug_log("⏭️  Skipped: Private chat")
            return
        
        if event.sender_id == me.id:
            debug_log("⏭️  Skipped: Own message")
            return
        
        current_hour = datetime.datetime.now().hour
        if SLEEP_START_HOUR <= current_hour < SLEEP_END_HOUR:
            debug_log(f"😴 Skipped: Sleep time ({current_hour}h)")
            return
        
        chat_id = event.chat_id
        topic_id = event.message.reply_to_msg_id if event.message.reply_to else None
        msg_text = event.raw_text.lower() if event.raw_text else ""
        unique_key = f"{chat_id}_{topic_id}"
        
        # --- INPUT VALIDATION ---
        if msg_text and not validate_message_input(msg_text):
            logger.warning(f"Invalid message input from chat {chat_id}")
            return
        
        debug_log(f"📝 Message text: '{msg_text[:50]}...'")
        
        if msg_text:
            update_trending(chat_id, msg_text)
        
        is_targeted = False
        my_previous_content = None
        
        if event.is_reply:
            try:
                reply = await event.get_reply_message()
                if reply and reply.sender_id == me.id:
                    is_targeted = True
                    my_previous_content = reply.message
                    debug_log("🎯 Targeted: Reply to my message")
            except:
                pass
        
        if any(n in msg_text for n in ['tèo', 'teo', 'bot', '@']):
            is_targeted = True
            debug_log("🎯 Targeted: Mentioned in message")
        
        has_photo = event.message.photo is not None
        if has_photo:
            debug_log("📷 Photo detected")
        
        dangerous = ['scam', 'lừa đảo', 'sập', 'bùng', 'công an', 'bắt']
        if any(w in msg_text for w in dangerous) and not is_targeted:
            debug_log("⚠️  Skipped: Dangerous content")
            return
        
        now = time.time()
        trigger_words = ['kèo', 'bóng', 'húp', 'lãi', 'thua', 'gỡ', 'đá', 'trận']
        
        has_trigger = any(w in msg_text for w in trigger_words)
        random_trigger = random.random() < TRIGGER_PROBABILITY
        
        should_reply = is_targeted or has_photo or has_trigger or random_trigger
        
        debug_log(f"Decision: targeted={is_targeted}, photo={has_photo}, trigger={has_trigger}, random={random_trigger}")
        debug_log(f"Should reply: {should_reply}")
        
        if not is_targeted and not has_photo:
            if unique_key in last_chat_time:
                time_diff = now - last_chat_time[unique_key]
                if time_diff < RATE_LIMIT_SECONDS:
                    debug_log(f"⏱️  Rate limited: {time_diff:.1f}s < {RATE_LIMIT_SECONDS}s")
                    return
        
        if not should_reply:
            if random.random() < 0.2:
                sentiment = analyze_sentiment(msg_text)
                await send_smart_reaction(chat_id, event.message.id, sentiment)
                debug_log("👍 Sent reaction only")
            else:
                debug_log("⏭️  Skipped: No reply needed")
            return
        
        # BẮT ĐẦU XỬ LÝ
        debug_log("✅ Processing message...")
        last_chat_time[unique_key] = now
        
        image_path = None
        if has_photo:
            try:
                image_path = f"temp_img_{chat_id}_{event.message.id}.jpg"
                temp_files.append(image_path)  # Track for cleanup
                await tg_client.download_media(event.message.photo, file=image_path)
                debug_log(f"📥 Downloaded image: {image_path}")
                await asyncio.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.error(f"Image download error: {e}", exc_info=True)
                image_path = None
        
        if is_targeted:
            wait_time = random.uniform(2, 5)
        else:
            wait_time = random.uniform(4, 10)
        
        debug_log(f"⏳ Waiting {wait_time:.1f}s...")
        await asyncio.sleep(wait_time)
        
        if not has_photo and not is_targeted:
            simple = check_simple_response(msg_text)
            if simple:
                debug_log(f"✅ Rule-based: {simple}")
                await simulate_human_typing(chat_id, simple, reply_to=topic_id)
                return
        
        if not has_photo and not is_targeted:
            cached = get_cached_response(msg_text)
            if cached:
                debug_log(f"💾 Cache hit: {cached}")
                await simulate_human_typing(chat_id, cached, reply_to=topic_id)
                return
        
        history = []
        try:
            # Expand history from 21 to 31 messages (to get up to 25-30 excluding bot's own)
            async for m in tg_client.iter_messages(chat_id, limit=31, reply_to=topic_id):
                if m.text and not getattr(m.sender, 'bot', False):
                    history.append({
                        'name': getattr(m.sender, 'first_name', 'U'),
                        'text': m.text[:100]
                    })
            debug_log(f"📜 Got {len(history)} history messages")
        except Exception as e:
            logger.error(f"Failed to fetch history: {e}")
        
        history.reverse()
        
        # Get emotional context
        emotion = get_emotional_context(msg_text, history)
        
        context = {
            'trending': get_trending_topic(chat_id),
            'mood': current_mood['state'],
            'emotion': emotion,
            'chat_id': chat_id
        }
        
        debug_log(f"🧠 Context: mood={context['mood']}, emotion={emotion}, trending={context['trending']}")
        
        ai_reply = await get_ai_reply_multimodal(
            msg_text, 
            history, 
            image_path, 
            my_previous_content,
            context
        )
        
        # Cleanup image file immediately after use
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                if image_path in temp_files:
                    temp_files.remove(image_path)
                debug_log(f"🗑️  Removed image: {image_path}")
            except Exception as e:
                logger.error(f"Failed to remove image: {e}")
        
        if ai_reply:
            if not has_photo:
                cache_response(msg_text, ai_reply)
            
            if '[sticker]' in ai_reply:
                sticker_emo = random.choice(['😂', '👍', '🔥', '👀'])
                try:
                    async with telegram_limiter:
                        if topic_id:
                            await tg_client.send_message(chat_id, file=types.InputMediaDice(sticker_emo), reply_to=topic_id)
                        else:
                            await tg_client.send_message(chat_id, file=types.InputMediaDice(sticker_emo))
                        debug_log(f"🎲 Sticker: {sticker_emo}")
                except Exception as e:
                    logger.error(f"Sticker send error: {e}")
                
                clean_reply = re.sub(r'\[.*?\]', '', ai_reply).strip()
                if clean_reply and len(clean_reply) > 2:
                    # Add variation to avoid repetition
                    clean_reply = add_response_variation(clean_reply)
                    await simulate_human_typing(chat_id, clean_reply, reply_to=topic_id)
            else:
                final = clean_text(re.sub(r'\[.*?\]', '', ai_reply))
                
                if not final or len(final) < 2:
                    # Use trending phrases for fallback
                    trending_fallback = get_random_trending_phrase('reactions', 'casual')
                    final = trending_fallback if trending_fallback else random.choice(['uh', 'oke', 'vl'])
                
                # Add variation to avoid repetition
                final = add_response_variation(final)
                
                target_msg_id = event.message.id if is_targeted else topic_id
                
                await simulate_human_typing(chat_id, final, reply_to=target_msg_id)
                debug_log(f"💬 Reply: {final}")
                
                sentiment_map = {
                    '[vui]': 'positive',
                    '[hai]': 'funny', 
                    '[like]': 'positive',
                    '[buon]': 'negative',
                    '[wow]': 'surprise'
                }
                
                for tag, sent in sentiment_map.items():
                    if tag in ai_reply and random.random() < 0.5:
                        await send_smart_reaction(chat_id, event.message.id, sent)
                        break
    
    except Exception as e:
        logger.error(f"❌ Handler error: {e}", exc_info=True)

# --- START BOT ---
def main():
    """Main function to start the bot"""
    logger.info("=" * 50)
    logger.info("🤖 Tèo Bot V9 - ENHANCED VERSION")
    logger.info("=" * 50)
    logger.info("⚙️  DEBUG MODE: ON")
    logger.info(f"⏰ Sleep hours: {SLEEP_START_HOUR}h - {SLEEP_END_HOUR}h")
    logger.info(f"🎲 Trigger probability: {TRIGGER_PROBABILITY*100}%")
    logger.info(f"⏱️  Rate limit: {RATE_LIMIT_SECONDS}s")
    logger.info(f"🔐 Allowed chats: {ALLOWED_CHAT_IDS}")
    logger.info("=" * 50)
    
    try:
        tg_client = get_telegram_client()
        if tg_client is None:
            logger.error("Failed to initialize Telegram client")
            return
        
        # Register the event handler
        tg_client.add_event_handler(handler, events.NewMessage())
        
        tg_client.start()
        logger.info("🟢 Bot is online!")
        logger.info("📊 Waiting for messages...")
        logger.info("💡 Tip: Send 'kèo gì' to test quickly")
        tg_client.run_until_disconnected()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Startup error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
