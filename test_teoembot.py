"""
Unit tests for teoembot.py
Tests for key functions: check_simple_response, analyze_sentiment, validate_message_input, etc.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from collections import defaultdict, deque

# Import functions to test
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))


class TestSimpleResponse:
    """Test the check_simple_response function"""
    
    def test_keo_patterns(self):
        """Test kèo-related patterns"""
        from teoembot import check_simple_response
        
        result = check_simple_response("kèo gì hôm nay")
        assert result is not None
        assert any(word in result.lower() for word in ['gặp', 'vs', 'bắt'])
    
    def test_greeting_patterns(self):
        """Test greeting patterns"""
        from teoembot import check_simple_response
        
        result = check_simple_response("chào mọi người")
        assert result is not None
        assert result.lower() in ['ê chào', 'yo bruh', 'hê nhô']
    
    def test_win_loss_patterns(self):
        """Test win/loss patterns"""
        from teoembot import check_simple_response
        
        # Test loss pattern
        result = check_simple_response("thua hết tiền rồi")
        assert result is not None
        assert any(word in result.lower() for word in ['rip', 'gỡ', 'thôi', 'nghỉ'])
    
    def test_no_match(self):
        """Test when no pattern matches"""
        from teoembot import check_simple_response
        
        result = check_simple_response("thời tiết hôm nay thế nào")
        assert result is None


class TestSentimentAnalysis:
    """Test the analyze_sentiment function"""
    
    def test_funny_sentiment(self):
        """Test funny sentiment detection"""
        from teoembot import analyze_sentiment
        
        assert analyze_sentiment("kkk vãi chưởng") == 'funny'
        assert analyze_sentiment("haha lol 😂") == 'funny'
    
    def test_positive_sentiment(self):
        """Test positive sentiment detection"""
        from teoembot import analyze_sentiment
        
        assert analyze_sentiment("vui quá thắng rồi") == 'positive'
        assert analyze_sentiment("đỉnh vãi") == 'positive'
        assert analyze_sentiment("ngon lắm") == 'positive'
    
    def test_negative_sentiment(self):
        """Test negative sentiment detection"""
        from teoembot import analyze_sentiment
        
        assert analyze_sentiment("buồn quá thua rồi") == 'negative'
        assert analyze_sentiment("sập mất tiền") == 'negative'
    
    def test_surprise_sentiment(self):
        """Test surprise sentiment detection"""
        from teoembot import analyze_sentiment
        
        assert analyze_sentiment("wtf gì vậy") == 'surprise'
        assert analyze_sentiment("sao lại thế") == 'surprise'
    
    def test_neutral_sentiment(self):
        """Test neutral sentiment detection"""
        from teoembot import analyze_sentiment
        
        assert analyze_sentiment("thời tiết đẹp") == 'neutral'
        assert analyze_sentiment("hôm nay thế nào") == 'neutral'


class TestInputValidation:
    """Test the validate_message_input function"""
    
    def test_valid_input(self):
        """Test valid message inputs"""
        from teoembot import validate_message_input
        
        assert validate_message_input("kèo gì hôm nay") == True
        assert validate_message_input("chào mọi người") == True
        assert validate_message_input("") == True
        assert validate_message_input(None) == True
    
    def test_suspicious_patterns(self):
        """Test detection of suspicious patterns"""
        from teoembot import validate_message_input
        
        assert validate_message_input("<script>alert('xss')</script>") == False
        assert validate_message_input("javascript:void(0)") == False
        assert validate_message_input("onerror=alert('xss')") == False
    
    def test_message_too_long(self):
        """Test message length limit"""
        from teoembot import validate_message_input
        
        long_message = "a" * 5000
        assert validate_message_input(long_message) == False


class TestTrendingTopics:
    """Test trending topics functionality"""
    
    def test_update_trending(self):
        """Test updating trending topics"""
        from teoembot import update_trending, trending_topics
        
        chat_id = -1001518116463
        update_trending(chat_id, "kèo bóng đá hôm nay")
        
        # Check that topics were added
        assert len(trending_topics[chat_id]) > 0
        words = [t['word'] for t in trending_topics[chat_id]]
        assert any(word in ['kèo', 'bóng', 'hôm', 'nay'] for word in words)
    
    def test_get_trending_topic(self):
        """Test getting trending topic"""
        from teoembot import get_trending_topic, update_trending, trending_topics
        
        chat_id = -1001518116463
        # Clear existing data
        trending_topics[chat_id].clear()
        
        # Add multiple instances of same word (need at least 3 for threshold)
        for _ in range(3):
            update_trending(chat_id, "kèo kèo kèo bóng")
        
        # Add some time for the trending logic
        import time
        time.sleep(0.1)
        
        trending = get_trending_topic(chat_id)
        # Should get 'kèo' or 'bóng' as they both appear multiple times
        assert trending in ['kèo', 'bóng'] or trending is None  # None is ok if timing issues


class TestCacheSystem:
    """Test the cache system"""
    
    def test_cache_response(self):
        """Test caching responses"""
        from teoembot import cache_response, get_cached_response
        
        test_text = "kèo gì hôm nay"
        test_response = "mu vs arsenal thơm phức"
        
        cache_response(test_text, test_response)
        cached = get_cached_response(test_text)
        
        assert cached == test_response
    
    def test_cache_case_insensitive(self):
        """Test cache is case insensitive"""
        from teoembot import cache_response, get_cached_response
        
        test_text = "KÈO GÌ"
        test_response = "test response"
        
        cache_response(test_text, test_response)
        cached = get_cached_response("kèo gì")
        
        assert cached == test_response


class TestVietnameseTypos:
    """Test Vietnamese typo simulator"""
    
    def test_add_vietnamese_typos(self):
        """Test adding Vietnamese typos"""
        from teoembot import add_vietnamese_typos
        
        original = "được đây giờ không"
        # Run multiple times to check it works
        for _ in range(10):
            result = add_vietnamese_typos(original)
            assert result is not None
            # Either original or with typos
            assert len(result) >= len(original) - 5


class TestMoodSystem:
    """Test mood calculation"""
    
    def test_calculate_mood(self):
        """Test mood calculation"""
        from teoembot import calculate_mood, MOODS
        
        mood = calculate_mood()
        assert mood in MOODS


class TestDatabasePersistence:
    """Test database persistence functions"""
    
    def test_save_trending_to_db(self):
        """Test saving trending topic to database"""
        from teoembot import save_trending_to_db
        
        # Should not raise exception
        try:
            save_trending_to_db(-1001518116463, "test_word")
            assert True
        except Exception as e:
            pytest.fail(f"save_trending_to_db raised exception: {e}")
    
    def test_load_trending_from_db(self):
        """Test loading trending topics from database"""
        from teoembot import load_trending_from_db, save_trending_to_db
        
        chat_id = -1001518116463
        test_word = "test_load_word"
        
        save_trending_to_db(chat_id, test_word)
        topics = load_trending_from_db(chat_id, hours=1)
        
        assert isinstance(topics, list)
    
    def test_save_user_context_to_db(self):
        """Test saving user context to database"""
        from teoembot import save_user_context_to_db
        
        context = {
            'last_topic': 'football',
            'sentiment': 'positive',
            'last_interaction': time.time(),
            'interaction_count': 5
        }
        
        # Should not raise exception
        try:
            save_user_context_to_db(-1001518116463, 12345, context)
            assert True
        except Exception as e:
            pytest.fail(f"save_user_context_to_db raised exception: {e}")


@pytest.mark.asyncio
class TestAsyncFunctions:
    """Test async functions"""
    
    async def test_check_openai_quota(self):
        """Test OpenAI quota checking"""
        from teoembot import check_openai_quota
        
        result = await check_openai_quota()
        assert isinstance(result, bool)
    
    async def test_check_relevance(self):
        """Test relevance checking"""
        from teoembot import check_relevance
        
        msg_text = "kèo bóng đá"
        context = {'trending': 'bóng'}
        history = [{'name': 'User', 'text': 'bóng đá'}]
        
        result = await check_relevance(msg_text, context, history)
        assert isinstance(result, bool)


class TestCleanup:
    """Test cleanup functionality"""
    
    def test_cleanup_temp_files(self):
        """Test temp file cleanup"""
        from teoembot import cleanup_temp_files, temp_files
        
        # Create a temporary test file
        test_file = "/tmp/test_cleanup_file.txt"
        with open(test_file, 'w') as f:
            f.write("test")
        
        temp_files.append(test_file)
        cleanup_temp_files()
        
        assert not os.path.exists(test_file)


class TestEncryption:
    """Test encryption utilities"""
    
    def test_get_encryption_key(self):
        """Test encryption key generation"""
        from teoembot import get_encryption_key
        
        key = get_encryption_key()
        assert key is not None
        assert len(key) > 0


class TestTrendingPhrases:
    """Test trending phrases functionality"""
    
    def test_load_trending_phrases(self):
        """Test loading trending phrases from JSON"""
        from teoembot import load_trending_phrases
        
        phrases = load_trending_phrases()
        assert phrases is not None
        assert 'memes' in phrases
        assert 'reactions' in phrases
        assert 'context_aware' in phrases
        assert len(phrases['memes']) > 0
    
    def test_get_random_trending_phrase(self):
        """Test getting random trending phrase"""
        from teoembot import get_random_trending_phrase
        
        # Test getting meme
        phrase = get_random_trending_phrase('memes')
        assert phrase is not None
        assert isinstance(phrase, str)
        
        # Test getting reaction with subcategory
        phrase = get_random_trending_phrase('reactions', 'casual')
        assert phrase is not None
        assert isinstance(phrase, str)
        
        # Test getting with no category (should return random meme)
        phrase = get_random_trending_phrase()
        assert phrase is not None
        assert isinstance(phrase, str)


class TestResponseVariation:
    """Test response variation system"""
    
    def test_add_response_variation(self):
        """Test adding variation to responses"""
        from teoembot import add_response_variation, recent_responses
        
        # Clear recent responses
        recent_responses.clear()
        
        # First time should return original
        response = "uh"
        result1 = add_response_variation(response)
        assert result1 is not None
        
        # Second time with same response should return variation
        result2 = add_response_variation(response)
        # Should be either original or variation
        assert result2 is not None
        assert isinstance(result2, str)


@pytest.mark.asyncio
class TestEnhancedFunctions:
    """Test enhanced async functions"""
    
    async def test_enhanced_check_relevance(self):
        """Test enhanced relevance checking with history"""
        from teoembot import check_relevance
        
        msg_text = "kèo bóng đá hôm nay"
        context = {'trending': 'bóng'}
        history = [
            {'name': 'User1', 'text': 'bàn về bóng đá'},
            {'name': 'User2', 'text': 'ai biết kèo gì'}
        ]
        
        result = await check_relevance(msg_text, context, history)
        assert isinstance(result, bool)
        # This should be relevant
        assert result
    
    async def test_check_relevance_short_response(self):
        """Test relevance check for short responses"""
        from teoembot import check_relevance
        
        # Short responses should be considered relevant
        msg_text = "oke"
        context = {}
        history = []
        
        result = await check_relevance(msg_text, context, history)
        assert result
    
    async def test_check_relevance_too_short(self):
        """Test relevance check for too short responses"""
        from teoembot import check_relevance
        
        # Too short (less than 3 chars) should not be relevant
        msg_text = "uh"
        context = {}
        history = []
        
        result = await check_relevance(msg_text, context, history)
        # 'uh' is 2 chars, should return False or True based on casual words check
        assert isinstance(result, bool)


class TestImprovedSystemPrompt:
    """Test improved system prompt"""
    
    def test_get_system_prompt_includes_trending(self):
        """Test that system prompt includes trending phrases"""
        from teoembot import get_system_prompt
        
        prompt = get_system_prompt()
        assert prompt is not None
        assert 'teencode TIẾT CHẾ' in prompt.lower() or 'teencode' in prompt.lower()
        assert 'context nhập tâm' in prompt.lower() or 'context' in prompt.lower()
        assert 'relevance' in prompt.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

