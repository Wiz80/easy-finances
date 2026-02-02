"""
Unit tests for WhatsApp message_parser.py.

Tests:
- Twilio webhook payload parsing
- Message type detection (text, image, audio, etc.)
- Media extraction
- Location extraction
- Phone number extraction
- Country code detection
- Timezone inference
- Special messages (join, sandbox)
"""

from datetime import datetime

import pytest

from app.integrations.whatsapp.message_parser import (
    MessageType,
    MediaContent,
    LocationContent,
    ParsedMessage,
    parse_twilio_webhook,
    extract_country_code,
    infer_timezone_from_phone,
    is_join_message,
    extract_join_code,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def basic_text_payload():
    """Create a basic text message payload from Twilio."""
    return {
        "MessageSid": "SM1234567890abcdef",
        "From": "whatsapp:+573115084628",
        "To": "whatsapp:+14155238886",
        "Body": "Gasté 50000 pesos en almuerzo",
        "NumMedia": "0",
        "ProfileName": "Harrison",
        "NumSegments": "1",
    }


@pytest.fixture
def image_message_payload():
    """Create an image message payload from Twilio."""
    return {
        "MessageSid": "SM9876543210fedcba",
        "From": "whatsapp:+573115084628",
        "To": "whatsapp:+14155238886",
        "Body": "Aquí está el recibo",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/media/12345",
        "MediaContentType0": "image/jpeg",
        "MediaId0": "ME12345",
        "ProfileName": "Harrison",
    }


@pytest.fixture
def audio_message_payload():
    """Create an audio message payload from Twilio."""
    return {
        "MessageSid": "SMAudio123",
        "From": "whatsapp:+573115084628",
        "To": "whatsapp:+14155238886",
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/media/audio123",
        "MediaContentType0": "audio/ogg; codecs=opus",
        "ProfileName": "Harrison",
    }


@pytest.fixture
def location_message_payload():
    """Create a location message payload from Twilio."""
    return {
        "MessageSid": "SMLocation123",
        "From": "whatsapp:+573115084628",
        "To": "whatsapp:+14155238886",
        "Body": "",
        "NumMedia": "0",
        "Latitude": "4.7110",
        "Longitude": "-74.0721",
        "Label": "Mi Casa",
        "Address": "Calle 123, Bogotá",
        "ProfileName": "Harrison",
    }


@pytest.fixture
def button_reply_payload():
    """Create a button reply payload from Twilio."""
    return {
        "MessageSid": "SMButton123",
        "From": "whatsapp:+573115084628",
        "To": "whatsapp:+14155238886",
        "Body": "Sí, confirmar",
        "NumMedia": "0",
        "ButtonPayload": "confirm_yes",
        "ButtonText": "Sí, confirmar",
        "ProfileName": "Harrison",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Basic Parsing Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBasicParsing:
    """Tests for basic webhook payload parsing."""

    def test_parse_text_message(self, basic_text_payload):
        """Should correctly parse a basic text message."""
        result = parse_twilio_webhook(basic_text_payload)
        
        assert result.message_sid == "SM1234567890abcdef"
        assert result.phone_number == "+573115084628"
        assert result.phone_number_raw == "whatsapp:+573115084628"
        assert result.body == "Gasté 50000 pesos en almuerzo"
        assert result.message_type == MessageType.TEXT
        assert result.profile_name == "Harrison"
        assert result.num_media == 0
        assert result.num_segments == 1

    def test_parse_empty_body(self):
        """Should handle empty message body."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "",
            "NumMedia": "0",
        }
        
        result = parse_twilio_webhook(payload)
        
        assert result.body == ""
        assert result.message_type == MessageType.UNKNOWN

    def test_parse_missing_fields_use_defaults(self):
        """Should use default values for missing optional fields."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "Test message",
        }
        
        result = parse_twilio_webhook(payload)
        
        assert result.num_media == 0
        assert result.num_segments == 1
        assert result.profile_name is None

    def test_parse_alternative_message_id(self):
        """Should use SmsSid if MessageSid is not present."""
        payload = {
            "SmsSid": "SMSMS123",
            "From": "whatsapp:+573115084628",
            "Body": "Test",
            "NumMedia": "0",
        }
        
        result = parse_twilio_webhook(payload)
        
        assert result.message_sid == "SMSMS123"


# ─────────────────────────────────────────────────────────────────────────────
# Message Type Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMessageTypeDetection:
    """Tests for message type detection."""

    def test_detect_text_message(self, basic_text_payload):
        """Should detect text message type."""
        result = parse_twilio_webhook(basic_text_payload)
        assert result.message_type == MessageType.TEXT

    def test_detect_image_message(self, image_message_payload):
        """Should detect image message type."""
        result = parse_twilio_webhook(image_message_payload)
        assert result.message_type == MessageType.IMAGE

    def test_detect_audio_message(self, audio_message_payload):
        """Should detect audio message type."""
        result = parse_twilio_webhook(audio_message_payload)
        assert result.message_type == MessageType.AUDIO

    def test_detect_video_message(self):
        """Should detect video message type."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "",
            "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/media/video",
            "MediaContentType0": "video/mp4",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.message_type == MessageType.VIDEO

    def test_detect_document_message(self):
        """Should detect document/PDF message type."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "",
            "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/media/doc",
            "MediaContentType0": "application/pdf",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.message_type == MessageType.DOCUMENT

    def test_detect_location_message(self, location_message_payload):
        """Should detect location message type."""
        result = parse_twilio_webhook(location_message_payload)
        assert result.message_type == MessageType.LOCATION

    def test_detect_button_reply(self, button_reply_payload):
        """Should detect button reply message type."""
        result = parse_twilio_webhook(button_reply_payload)
        assert result.message_type == MessageType.BUTTON_REPLY

    def test_detect_list_reply(self):
        """Should detect list reply message type."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "Option 1",
            "NumMedia": "0",
            "ListId": "list_123",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.message_type == MessageType.LIST_REPLY


# ─────────────────────────────────────────────────────────────────────────────
# Media Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMediaExtraction:
    """Tests for media extraction from payloads."""

    def test_extract_single_image(self, image_message_payload):
        """Should extract single image media."""
        result = parse_twilio_webhook(image_message_payload)
        
        assert len(result.media) == 1
        assert result.media[0].url == "https://api.twilio.com/media/12345"
        assert result.media[0].content_type == "image/jpeg"
        assert result.media[0].media_id == "ME12345"

    def test_extract_multiple_media(self):
        """Should extract multiple media attachments."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "Two receipts",
            "NumMedia": "2",
            "MediaUrl0": "https://api.twilio.com/media/1",
            "MediaContentType0": "image/jpeg",
            "MediaUrl1": "https://api.twilio.com/media/2",
            "MediaContentType1": "image/png",
        }
        
        result = parse_twilio_webhook(payload)
        
        assert len(result.media) == 2
        assert result.media[0].url == "https://api.twilio.com/media/1"
        assert result.media[1].url == "https://api.twilio.com/media/2"

    def test_has_media_property(self, image_message_payload):
        """Should correctly report has_media property."""
        result = parse_twilio_webhook(image_message_payload)
        assert result.has_media is True
        
    def test_has_media_false_for_text(self, basic_text_payload):
        """Should report has_media as False for text messages."""
        result = parse_twilio_webhook(basic_text_payload)
        assert result.has_media is False

    def test_is_text_only_property(self, basic_text_payload):
        """Should correctly report is_text_only property."""
        result = parse_twilio_webhook(basic_text_payload)
        assert result.is_text_only is True


# ─────────────────────────────────────────────────────────────────────────────
# Location Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLocationExtraction:
    """Tests for location extraction from payloads."""

    def test_extract_location(self, location_message_payload):
        """Should extract location data."""
        result = parse_twilio_webhook(location_message_payload)
        
        assert result.location is not None
        assert result.location.latitude == 4.7110
        assert result.location.longitude == -74.0721
        assert result.location.label == "Mi Casa"
        assert result.location.address == "Calle 123, Bogotá"

    def test_no_location_for_text(self, basic_text_payload):
        """Should return None location for text messages."""
        result = parse_twilio_webhook(basic_text_payload)
        assert result.location is None

    def test_location_with_invalid_coords(self):
        """Should handle invalid location coordinates gracefully."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "",
            "NumMedia": "0",
            "Latitude": "invalid",
            "Longitude": "also_invalid",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.location is None


# ─────────────────────────────────────────────────────────────────────────────
# Phone Number Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPhoneNumberExtraction:
    """Tests for phone number extraction and formatting."""

    def test_extract_phone_removes_whatsapp_prefix(self, basic_text_payload):
        """Should remove 'whatsapp:' prefix from phone number."""
        result = parse_twilio_webhook(basic_text_payload)
        
        assert result.phone_number == "+573115084628"
        assert "whatsapp:" not in result.phone_number

    def test_preserve_raw_phone_number(self, basic_text_payload):
        """Should preserve raw phone number with prefix."""
        result = parse_twilio_webhook(basic_text_payload)
        
        assert result.phone_number_raw == "whatsapp:+573115084628"

    def test_extract_phone_without_prefix(self):
        """Should handle phone number without whatsapp prefix."""
        payload = {
            "MessageSid": "SM123",
            "From": "+573115084628",  # No whatsapp: prefix
            "Body": "Test",
            "NumMedia": "0",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.phone_number == "+573115084628"


# ─────────────────────────────────────────────────────────────────────────────
# Country Code Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCountryCodeDetection:
    """Tests for country code detection from phone numbers."""

    @pytest.mark.parametrize(
        "phone,expected_code",
        [
            ("+573115084628", "57"),   # Colombia
            ("+5215512345678", "52"),  # Mexico
            ("+51999888777", "51"),    # Peru
            ("+593999888777", "593"),  # Ecuador
            ("+5491112345678", "54"),  # Argentina
            ("+5511999888777", "55"),  # Brazil
            ("+14155238886", "1"),     # USA
            ("+34612345678", "34"),    # Spain
            ("+56912345678", "56"),    # Chile
        ],
    )
    def test_extract_country_code(self, phone, expected_code):
        """Should correctly extract country code from various phone numbers."""
        result = extract_country_code(phone)
        assert result == expected_code

    def test_extract_country_code_unknown(self):
        """Should return None for unknown country codes."""
        result = extract_country_code("+9991234567")
        assert result is None

    def test_extract_country_code_without_plus(self):
        """Should handle phone numbers without + prefix."""
        result = extract_country_code("573115084628")
        assert result == "57"


# ─────────────────────────────────────────────────────────────────────────────
# Timezone Inference Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTimezoneInference:
    """Tests for timezone inference from phone numbers."""

    @pytest.mark.parametrize(
        "phone,expected_tz",
        [
            ("+573115084628", "America/Bogota"),      # Colombia
            ("+5215512345678", "America/Mexico_City"), # Mexico
            ("+51999888777", "America/Lima"),          # Peru
            ("+593999888777", "America/Guayaquil"),    # Ecuador
            ("+5491112345678", "America/Buenos_Aires"), # Argentina
            ("+5511999888777", "America/Sao_Paulo"),   # Brazil
            ("+14155238886", "America/New_York"),      # USA
            ("+34612345678", "Europe/Madrid"),         # Spain
        ],
    )
    def test_infer_timezone(self, phone, expected_tz):
        """Should correctly infer timezone from phone number."""
        result = infer_timezone_from_phone(phone)
        assert result == expected_tz

    def test_infer_timezone_unknown(self):
        """Should return None for unknown country codes."""
        result = infer_timezone_from_phone("+9991234567")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox Join Message Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestJoinMessages:
    """Tests for Twilio sandbox join message detection."""

    @pytest.mark.parametrize(
        "body,expected",
        [
            ("join happy-elephant", True),
            ("Join HAPPY-ELEPHANT", True),
            ("JOIN test-code", True),
            ("join ", False),  # No code
            ("joinhappy", False),  # No space
            ("Hello join", False),  # Not at start
            ("Hola", False),
        ],
    )
    def test_is_join_message(self, body, expected):
        """Should correctly identify join messages."""
        result = is_join_message(body)
        assert result == expected

    @pytest.mark.parametrize(
        "body,expected_code",
        [
            ("join happy-elephant", "happy-elephant"),
            ("Join HAPPY-ELEPHANT", "HAPPY-ELEPHANT"),
            ("join test-sandbox-code", "test-sandbox-code"),
        ],
    )
    def test_extract_join_code(self, body, expected_code):
        """Should extract join code from message."""
        result = extract_join_code(body)
        assert result == expected_code

    def test_extract_join_code_none_for_non_join(self):
        """Should return None for non-join messages."""
        result = extract_join_code("Hello world")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# ParsedMessage Properties Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestParsedMessageProperties:
    """Tests for ParsedMessage dataclass properties."""

    def test_display_phone(self, basic_text_payload):
        """Should format phone number for display."""
        result = parse_twilio_webhook(basic_text_payload)
        
        # Currently just returns the phone number
        assert result.display_phone == "+573115084628"

    def test_timestamp_is_set(self, basic_text_payload):
        """Should set timestamp to current time."""
        result = parse_twilio_webhook(basic_text_payload)
        
        assert isinstance(result.timestamp, datetime)
        # Timestamp should be recent (within last minute)
        time_diff = (datetime.utcnow() - result.timestamp).total_seconds()
        assert time_diff < 60

    def test_raw_payload_preserved(self, basic_text_payload):
        """Should preserve raw payload."""
        result = parse_twilio_webhook(basic_text_payload)
        
        assert result.raw_payload == basic_text_payload


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and unusual payloads."""

    def test_invalid_num_media(self):
        """Should handle invalid NumMedia value."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "Test",
            "NumMedia": "invalid",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.num_media == 0

    def test_invalid_num_segments(self):
        """Should handle invalid NumSegments value."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "Test",
            "NumMedia": "0",
            "NumSegments": "not_a_number",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.num_segments == 1

    def test_body_with_whitespace(self):
        """Should trim whitespace from body."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "  Test message  ",
            "NumMedia": "0",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.body == "Test message"

    def test_unicode_in_body(self):
        """Should handle unicode characters in body."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "Gasté 50€ en café ☕",
            "NumMedia": "0",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.body == "Gasté 50€ en café ☕"

    def test_emoji_only_body(self):
        """Should handle emoji-only body."""
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": "👍",
            "NumMedia": "0",
        }
        
        result = parse_twilio_webhook(payload)
        assert result.body == "👍"
        assert result.message_type == MessageType.TEXT

    def test_very_long_body(self):
        """Should handle very long message body."""
        long_text = "A" * 10000
        payload = {
            "MessageSid": "SM123",
            "From": "whatsapp:+573115084628",
            "Body": long_text,
            "NumMedia": "0",
        }
        
        result = parse_twilio_webhook(payload)
        assert len(result.body) == 10000


# ─────────────────────────────────────────────────────────────────────────────
# MediaContent and LocationContent Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDataclasses:
    """Tests for MediaContent and LocationContent dataclasses."""

    def test_media_content_creation(self):
        """Should create MediaContent with all fields."""
        media = MediaContent(
            url="https://example.com/media",
            content_type="image/jpeg",
            media_id="ME123",
            filename="photo.jpg",
            size_bytes=1024,
        )
        
        assert media.url == "https://example.com/media"
        assert media.content_type == "image/jpeg"
        assert media.media_id == "ME123"
        assert media.filename == "photo.jpg"
        assert media.size_bytes == 1024

    def test_media_content_optional_fields(self):
        """Should create MediaContent with optional fields as None."""
        media = MediaContent(
            url="https://example.com/media",
            content_type="audio/ogg",
        )
        
        assert media.media_id is None
        assert media.filename is None
        assert media.size_bytes is None

    def test_location_content_creation(self):
        """Should create LocationContent with all fields."""
        location = LocationContent(
            latitude=4.7110,
            longitude=-74.0721,
            label="Home",
            address="123 Main St",
        )
        
        assert location.latitude == 4.7110
        assert location.longitude == -74.0721
        assert location.label == "Home"
        assert location.address == "123 Main St"

    def test_location_content_optional_fields(self):
        """Should create LocationContent with optional fields as None."""
        location = LocationContent(
            latitude=4.7110,
            longitude=-74.0721,
        )
        
        assert location.label is None
        assert location.address is None
