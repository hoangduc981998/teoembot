import os
import random
import asyncio
import re
import datetime
import base64
import time
import hashlib
from collections import defaultdict, deque
from telethon import TelegramClient, events, functions, types
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CẤU HÌNH TỪ .ENV ---
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SESSION_NAME = os.getenv('SESSION_NAME', 'teocakhia')

# Cấu hình hành vi - ĐIỀU CHỈNH ĐỂ DEBUG
RATE_LIMIT_SECONDS = 10  # Giảm xuống 10s để test
TRIGGER_PROBABILITY = 0.5  # Tăng lên 50% để dễ test
SLEEP_START_HOUR = 25  # Tắt tính năng ngủ (>24h)
SLEEP_END_HOUR = 26

# DEBUG MODE
DEBUG = True  # Bật debug log

# Dữ liệu templates
CLUBS = ["MU", "Man City", "Arsenal", "Liverpool", "Real", "Barca", "Chelsea", "Bayern", "PSG", "Việt Nam"]
KEOS = ["tài 2.5", "xỉu 2.5", "tài 3 hòa", "chấp nửa trái", "đồng banh", "rung tài 0.5"]
COMMENTS = ["sáng cửa", "thơm phức", "hơi bịp nhưng vẫn ngon", "tín vl", "nhồi mạnh", "xa bờ thì bám vào"]

# AI Client
ai_client = OpenAI(api_key=OPENAI_API_KEY)
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Memory systems
last_chat_time = {}
user_context = defaultdict(lambda: {
    'last_topic': None,
    'sentiment': 'neutral',
    'last_interaction': 0,
    'interaction_count': 0
})
trending_topics = defaultdict(lambda: deque(maxlen=20))
message_cache = {}

# Moods system
MOODS = ['hype', 'chill', 'mệt', 'tỉnh', 'say nhẹ']
current_mood = {'state': 'chill', 'changed_at': time.time()}

def debug_log(msg):
    """Print debug messages"""
    if DEBUG:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] 🐛 {msg}")

# --- MOOD SYSTEM ---
def calculate_mood():
    global current_mood
    now = time.time()
    
    if now - current_mood['changed_at'] > random.randint(1800, 3600):
        hour = datetime.datetime.now().hour
        
        if 22 <= hour or hour < 1:
            current_mood['state'] = random.choice(['say nhẹ', 'mệt', 'chill'])
        elif 7 <= hour < 12:
            current_mood['state'] = random.choice(['tỉnh', 'chill', 'hype'])
        elif 18 <= hour < 22:
            current_mood['state'] = random.choice(['hype', 'chill'])
        else:
            current_mood['state'] = 'chill'
        
        current_mood['changed_at'] = now
    
    return current_mood['state']

# --- TRENDING TOPICS ---
def update_trending(chat_id, text):
    words = re.findall(r'\w+', text.lower())
    important_words = [w for w in words if len(w) > 3 and w not in ['đang', 'này', 'thôi', 'nhỉ']]
    
    for word in important_words:
        trending_topics[chat_id].append({
            'word': word,
            'time': time.time()
        })

def get_trending_topic(chat_id):
    now = time.time()
    recent = [t['word'] for t in trending_topics[chat_id] if now - t['time'] < 300]
    
    if not recent:
        return None
    
    word_count = defaultdict(int)
    for word in recent:
        word_count[word] += 1
    
    top_word = max(word_count.items(), key=lambda x: x[1])
    return top_word[0] if top_word[1] >= 3 else None

# --- PROMPT AI ---
def get_system_prompt():
    mood = calculate_mood()
    
    mood_traits = {
        'hype': 'Đang phê, năng lượng cao, hào hứng, dùng nhiều "vl", "kkk"',
        'chill': 'Bình thường, thoải mái, không quá nhiệt tình',
        'mệt': 'Hơi lười, trả lời ngắn gọn, thỉnh thoảng "ừ", "ok"',
        'tỉnh': 'Tỉnh táo, sáng sớm, trả lời lịch sự hơn một chút',
        'say nhẹ': 'Hơi loạn, đánh máy sai chính tả nhiều hơn'
    }
    
    return (
        f"Bạn là Tèo, dân chơi cá độ bóng đá. Mood hiện tại: {mood} ({mood_traits[mood]}). "
        "QUY TẮC VÀNG: "
        "1. Chat CỰC NGẮN (3-8 từ), không viết hoa, không dấu câu nhiều. "
        "2. Dùng teencode: kkk, vl, r, đù, bruh, oke. "
        "3. [VISION] Có ảnh: Bình luận ngắn gọn (khen/chê/hỏi han). "
        "4. [REPLY] Bị trả lời: Đáp lại súc tích, đúng trọng tâm. "
        "5. [BÓNG ĐÁ] Nói rõ tên đội, VD: 'mu vs arsenal', KHÔNG nói 'trận này'. "
        "6. [STICKER] Tình huống chỉ cần cười: Thêm [sticker] cuối câu. "
        "7. [EMOTION] Cuối câu text: Thêm [vui], [buon], [hai], [like], [wow]. "
        "8. Đôi khi chỉ cần rep bằng 'uh', 'oke r', 'vl' là đủ."
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

# --- CACHE SYSTEM ---
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

# --- AI CALL ---
async def get_ai_reply_multimodal(msg_text, history, image_path=None, my_previous_msg=None, context=None):
    try:
        messages = [{"role": "system", "content": get_system_prompt()}]
        
        if context and context.get('trending'):
            messages.append({
                "role": "system",
                "content": f"Lưu ý: Chủ đề đang hot trong nhóm: '{context['trending']}'"
            })
        
        for h in history[-5:]:
            messages.append({"role": "user", "content": f"{h['name']}: {h['text']}"})
        
        user_content = []
        context_intro = ""
        
        if my_previous_msg:
            context_intro = f"(User đang rep lại: '{my_previous_msg[:50]}...'). "
        
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
        
        debug_log(f"Calling OpenAI API...")
        
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=80,
            temperature=0.9
        )
        
        result = response.choices[0].message.content
        debug_log(f"AI Response: {result}")
        return result
    
    except Exception as e:
        print(f"❌ Lỗi AI: {e}")
        return random.choice(["uh", "oke r", "vl", "kkk"])

# --- TYPING SIMULATION ---
async def simulate_human_typing(chat_id, text, reply_to=None):
    if random.random() < 0.05:
        async with client.action(chat_id, 'typing'):
            await asyncio.sleep(random.randint(2, 5))
        return
    
    async with client.action(chat_id, 'typing'):
        typing_time = len(text) * random.uniform(0.08, 0.15)
        
        if random.random() < 0.25 and len(text) > 8:
            mistake_pos = random.randint(-3, -1)
            fake_text = text[:mistake_pos]
            
            await asyncio.sleep(typing_time * 0.6)
            
            try:
                if reply_to:
                    m = await client.send_message(chat_id, fake_text, reply_to=reply_to)
                else:
                    m = await client.send_message(chat_id, fake_text)
                
                await asyncio.sleep(random.uniform(1, 2))
                
                final_text = add_vietnamese_typos(text)
                await client.edit_message(chat_id, m.id, final_text)
                
            except Exception as e:
                debug_log(f"Lỗi typing sim: {e}")
        else:
            await asyncio.sleep(typing_time)
            final_text = add_vietnamese_typos(text)
            
            try:
                if reply_to:
                    await client.send_message(chat_id, final_text, reply_to=reply_to)
                else:
                    await client.send_message(chat_id, final_text)
            except Exception as e:
                debug_log(f"Lỗi send: {e}")

# --- SMART REACTION ---
async def send_smart_reaction(chat_id, msg_id, sentiment):
    reaction_map = {
        'positive': ['❤', '🔥', '👍', '💯'],
        'negative': ['😢', '💀', '😭'],
        'funny': ['😂', '🤣', '💀'],
        'surprise': ['😮', '🤯', '👀'],
        'neutral': ['👍', '👀', '🙂']
    }
    
    emo = random.choice(reaction_map.get(sentiment, reaction_map['neutral']))
    
    try:
        await asyncio.sleep(random.uniform(0.5, 2))
        await client.send_reaction(chat_id, msg_id, emo)
        debug_log(f"Sent reaction: {emo}")
    except Exception as e:
        debug_log(f"Lỗi reaction: {e}")

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
@client.on(events.NewMessage)
async def handler(event):
    try:
        me = await client.get_me()
        
        debug_log(f"📩 New message from chat_id={event.chat_id}")
        
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
                await client.download_media(event.message.photo, file=image_path)
                debug_log(f"📥 Downloaded image: {image_path}")
                await asyncio.sleep(random.uniform(2, 4))
            except Exception as e:
                debug_log(f"❌ Image download error: {e}")
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
            async for m in client.iter_messages(chat_id, limit=6, reply_to=topic_id):
                if m.text and not getattr(m.sender, 'bot', False):
                    history.append({
                        'name': getattr(m.sender, 'first_name', 'U'),
                        'text': m.text[:100]
                    })
            debug_log(f"📜 Got {len(history)} history messages")
        except:
            pass
        
        history.reverse()
        
        context = {
            'trending': get_trending_topic(chat_id),
            'mood': current_mood['state']
        }
        
        debug_log(f"🧠 Context: mood={context['mood']}, trending={context['trending']}")
        
        ai_reply = await get_ai_reply_multimodal(
            msg_text, 
            history, 
            image_path, 
            my_previous_content,
            context
        )
        
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                debug_log(f"🗑️  Removed image: {image_path}")
            except:
                pass
        
        if ai_reply:
            if not has_photo:
                cache_response(msg_text, ai_reply)
            
            if '[sticker]' in ai_reply:
                sticker_emo = random.choice(['😂', '👍', '🔥', '👀'])
                try:
                    if topic_id:
                        await client.send_message(chat_id, file=types.InputMediaDice(sticker_emo), reply_to=topic_id)
                    else:
                        await client.send_message(chat_id, file=types.InputMediaDice(sticker_emo))
                    debug_log(f"🎲 Sticker: {sticker_emo}")
                except:
                    pass
                
                clean_reply = re.sub(r'\[.*?\]', '', ai_reply).strip()
                if clean_reply and len(clean_reply) > 2:
                    await simulate_human_typing(chat_id, clean_reply, reply_to=topic_id)
            else:
                final = clean_text(re.sub(r'\[.*?\]', '', ai_reply))
                
                if not final or len(final) < 2:
                    final = random.choice(['uh', 'oke', 'vl'])
                
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
        print(f"❌ Handler error: {e}")
        import traceback
        traceback.print_exc()

# --- START BOT ---
print("=" * 50)
print("🤖 Tèo Bot V8 - DEBUG VERSION")
print("=" * 50)
print("⚙️  DEBUG MODE: ON")
print(f"⏰ Sleep hours: {SLEEP_START_HOUR}h - {SLEEP_END_HOUR}h")
print(f"🎲 Trigger probability: {TRIGGER_PROBABILITY*100}%")
print(f"⏱️  Rate limit: {RATE_LIMIT_SECONDS}s")
print("=" * 50)

try:
    client.start()
    print("🟢 Bot đã online!")
    print("📊 Đang chờ tin nhắn...")
    print("💡 Tip: Gửi 'kèo gì' để test nhanh")
    client.run_until_disconnected()
except KeyboardInterrupt:
    print("\n⏹️  Bot stopped by user")
except Exception as e:
    print(f"❌ Lỗi khởi động: {e}")
    import traceback
    traceback.print_exc()
