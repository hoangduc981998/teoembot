# TeoEmBot - Intelligent Vietnamese Betting Chat Bot

TeoEmBot is an advanced AI-powered Telegram bot designed to participate naturally in Vietnamese betting and football discussion groups. The bot uses emotional intelligence, deep conversation capabilities, and natural language understanding to engage like a real person.

## 🌟 Key Features

### Emotional Intelligence
- **Dynamic Emotional States**: Bot adapts emotions based on conversation context
  - `excited` - When discussing wins, profits, exciting matches
  - `worried` - When discussing losses or risky situations
  - `thoughtful` - When analyzing betting odds or making predictions
  - `confident` - When giving certain recommendations
  - `skeptical` - When expressing doubt or caution
  - `playful` - Default casual, fun interactions

### Deep Conversation Capabilities
- **Extended Context**: Maintains 25-30 message history for better context understanding
- **Follow-up Questions**: Naturally asks questions like "Sao lại thế?", "Anh nghĩ sao?" to continue conversations
- **Thinking Depth**: Adds analytical depth with phrases like "để tao nghĩ...", "phân tích thử..."
- **Topic Memory**: Remembers recent conversation topics to maintain continuity

### Natural Language
- **Reduced Teencode Spam**: Smart synonym replacement prevents repetitive responses
  - `oke` → ok, được, nhận, oke r, rõ
  - `vl` → vãi, ghê, kinh, trời, ối
  - `kkk` → haha, hehe, lol, hì
- **Response Variation**: Tracks recent responses to avoid repetition
- **Mood System**: Time-based mood changes (hype, chill, mệt, tỉnh, say nhẹ)

### Advanced Features
- **Multimodal**: Can view and comment on images
- **Context-Aware**: Understands betting terminology, football teams, and Vietnamese slang
- **Smart Reactions**: Sends appropriate emoji reactions based on sentiment
- **Rate Limited**: Respects Telegram and OpenAI API limits
- **Secure**: Encrypted API key storage, input validation

## 📊 Emotional Responses by Context

| Context | Emotion | Example Response |
|---------|---------|------------------|
| Win/Profit | Excited | "phê quá", "đỉnh của đỉnh" |
| Loss | Worried | "lo lo", "hơi sợ" |
| Analysis | Thoughtful | "để nghĩ kỹ", "phân tích thử" |
| Certain | Confident | "chắc chắn", "ez game" |
| Doubt | Skeptical | "không chắc lắm", "cẩn thận" |
| Casual | Playful | "chill đi", "vui vui" |

## 🚀 Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
OPENAI_API_KEY=your_openai_api_key
SESSION_NAME=teocakhia
```

3. Run the bot:
```bash
python teoembot.py
```

## 🧪 Testing

Run unit tests:
```bash
pytest test_teoembot.py -v
```

All 51+ tests cover:
- Emotional context detection
- Response variation
- Follow-up questions
- Thinking depth
- Sentiment analysis
- Input validation
- Cache system
- Database persistence

## 📝 Configuration

Key parameters in `teoembot.py`:
- `RATE_LIMIT_SECONDS = 10` - Minimum seconds between responses
- `TRIGGER_PROBABILITY = 0.5` - Chance to respond to random messages
- `ALLOWED_CHAT_IDS` - Whitelist of allowed chat groups
- `MAX_HISTORY_TEXT_LENGTH = 50` - Characters to keep from each history message

## 🎯 Usage Tips

The bot responds to:
- Direct mentions (@bot, "tèo", "teo")
- Replies to bot's messages
- Photos/images
- Football/betting keywords (kèo, bóng, húp, trận)
- Random messages (50% probability)

## 🔒 Security

- API keys encrypted using Fernet
- Input validation against XSS/injection
- Message length limits
- Suspicious pattern detection

## 📈 Performance

- Response time: < 5 seconds
- OpenAI quota: 100 calls/hour
- Telegram rate limit: 20 messages/minute
- Cache TTL: 10 minutes

## 🛠️ Technical Stack

- **Telethon**: Telegram client
- **OpenAI GPT-4o-mini**: AI responses
- **SQLAlchemy**: Database persistence
- **Tenacity**: Retry logic
- **AIOLimiter**: Rate limiting
- **Cryptography**: API key encryption

## 📚 Recent Updates

### v10 - Emotional Intelligence & Deep Conversations
- ✅ Enhanced mood system with 6 emotional states
- ✅ Synonym-based response variation (reduces spam)
- ✅ Follow-up question system (10+ questions)
- ✅ Thinking depth with analytical prefixes
- ✅ Extended history to 25-30 messages
- ✅ Temperature increased to 1.0 for more variety
- ✅ 200+ new unit tests

## 👨‍💻 Author

hoangduc981998

## 📄 License

Private project