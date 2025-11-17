# Audio Extractor - Usage Guide

## Overview

The Audio Extractor uses OpenAI's Whisper API to transcribe audio files and then extracts structured expense information using the Text Extractor. It supports multiple languages and audio formats.

## Features

- **OpenAI Whisper API**: State-of-the-art speech recognition
- **Multi-language support**: Automatic language detection
- **Audio format support**: MP3, OGG, WAV, M4A, and more
- **Combined confidence**: ASR quality + extraction confidence
- **Metadata preservation**: Stores transcription in expense notes
- **Structured logging**: Full traceability

## Architecture

```
Audio Input (file or bytes)
       ↓
  OpenAI Whisper API
       ↓
  Transcription (text)
       ↓
  Text Extractor
       ↓
  ExtractedExpense
  (with audio metadata)
```

## Installation

Already included in project dependencies. Requires:

```bash
# OpenAI SDK
uv pip install openai

# Or full project
uv pip install -e .
```

## Configuration

Set your OpenAI API key in `.env`:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...

# Whisper Configuration
WHISPER_PROVIDER=api  # Use API (not local)
WHISPER_MODEL=whisper-1  # OpenAI's production model
```

## Usage

### Basic Usage

```python
from app.tools.extraction.audio_extractor import extract_expense_from_audio

# Extract from audio file
expense = extract_expense_from_audio("voice_note.ogg")

print(f"Amount: {expense.amount} {expense.currency}")
print(f"Category: {expense.category_candidate}")
print(f"Transcription: {expense.notes}")
```

### From Audio Bytes

```python
# If you have audio as bytes (e.g., from WhatsApp webhook)
with open("audio.ogg", "rb") as f:
    audio_bytes = f.read()

expense = extract_expense_from_audio(audio_bytes)
```

### With Language Hint

```python
# Provide language hint for better accuracy
expense = extract_expense_from_audio(
    "voice_note.ogg",
    language="es"  # Spanish
)
```

### Transcription Only

```python
from app.tools.extraction.audio_extractor import transcribe_audio

# Just transcribe, don't extract
result = transcribe_audio("audio.ogg")

print(f"Text: {result['text']}")
print(f"Language: {result['language']}")
print(f"Duration: {result['duration']}s")
```

### With Context (for logging)

```python
expense = extract_expense_from_audio(
    "audio.ogg",
    user_id="user123",
    request_id="req456",
    source="whatsapp"
)
```

## Supported Audio Formats

OpenAI Whisper API supports:

- **MP3** (recommended for storage)
- **OGG** (WhatsApp voice notes)
- **WAV** (uncompressed)
- **M4A** (Apple audio)
- **FLAC** (lossless)
- **WebM** (web audio)

**File size limit**: 25 MB per file

## Pipeline Details

### Step 1: Transcription

```python
# Audio file → OpenAI Whisper API → Text
{
    "text": "Gasté veinte soles en taxi, pagué en efectivo",
    "language": "es",
    "duration": 3.5
}
```

### Step 2: Extraction

```python
# Text → Text Extractor → Structured data
ExtractedExpense(
    amount=20.00,
    currency="PEN",
    description="taxi",
    category_candidate="transport",
    method="cash",
    confidence=0.89  # Combined ASR + extraction
)
```

### Step 3: Metadata Storage

```python
# Original transcription stored in notes
expense.notes = "Transcription: Gasté veinte soles en taxi, pagué en efectivo"
expense.raw_input = "[AUDIO] Gasté veinte soles en taxi, pagué en efectivo"
```

## Confidence Scoring

The audio extractor combines two confidence scores:

### Formula

```
combined_confidence = (whisper_confidence × 0.3) + (extraction_confidence × 0.7)
```

- **Whisper confidence**: 0.95 (high, Whisper is very accurate)
- **Extraction confidence**: From Text Extractor (0.0-1.0)
- **Weight**: 30% ASR, 70% extraction

### Example

```
Whisper: 0.95 (confident transcription)
Text Extractor: 0.92 (good extraction)
Combined: (0.95 × 0.3) + (0.92 × 0.7) = 0.929
```

## Testing

### Generate Test Audio

```bash
# Create synthetic audio files for testing
python tests-manual/generate_test_audio.py
```

This generates:
- `spanish_taxi.mp3`
- `english_restaurant.mp3`
- `spanish_delivery.mp3`
- `spanish_groceries.mp3`
- `english_hotel.mp3`

### Run Manual Tests

```bash
# Test with generated files
python tests-manual/test_audio_extractor.py

# Test with your own file
python tests-manual/test_audio_extractor.py path/to/audio.ogg
```

### Unit Testing (when implemented)

```bash
pytest tests/unit/test_audio_extractor.py -v
```

## Examples

### Example 1: Spanish Voice Note

```python
# Audio content: "Gasté veinte soles en taxi, pagué en efectivo"
expense = extract_expense_from_audio("spanish_taxi.mp3")

# Result:
# amount: 20.00
# currency: PEN
# description: taxi
# category: transport
# method: cash
# confidence: ~0.89
# notes: "Transcription: Gasté veinte soles en taxi, pagué en efectivo"
```

### Example 2: English Restaurant

```python
# Audio: "Dinner at Italian restaurant, eighty five dollars with my Visa card"
expense = extract_expense_from_audio("english_restaurant.mp3")

# Result:
# amount: 85.00
# currency: USD
# description: Dinner at Italian restaurant
# category: out_house_food
# method: card
# card_hint: Visa
# confidence: ~0.93
```

### Example 3: From WhatsApp Bytes

```python
# Simulate WhatsApp webhook audio
from pathlib import Path

audio_bytes = Path("whatsapp_voice.ogg").read_bytes()
expense = extract_expense_from_audio(
    audio_bytes,
    user_id="whatsapp_user_123",
    source="whatsapp_webhook"
)
```

## Error Handling

Common errors and solutions:

### Empty Transcription

```python
try:
    expense = extract_expense_from_audio("audio.ogg")
except ValueError as e:
    print(f"Empty transcription: {e}")
    # Audio might be silence or noise
```

### File Not Found

```python
from pathlib import Path

audio_path = Path("audio.ogg")
if not audio_path.exists():
    print("File not found")
else:
    expense = extract_expense_from_audio(audio_path)
```

### API Errors

```python
try:
    expense = extract_expense_from_audio("audio.ogg")
except Exception as e:
    logger.error("API call failed", error=str(e))
    # Retry or fallback logic
```

## Performance

- **Whisper API Latency**: ~2-5 seconds (depends on audio length)
- **Text Extraction**: ~1-2 seconds
- **Total**: ~3-7 seconds per audio file
- **Cost**: ~$0.006 per minute of audio

### Optimization Tips

1. **Compress audio**: Use MP3 at 64kbps for voice notes
2. **Trim silence**: Remove leading/trailing silence
3. **Batch processing**: Process multiple files in parallel
4. **Cache transcriptions**: Store text to avoid re-transcribing

## Language Support

Whisper supports 99+ languages. Common ones:

| Language | Code | Example |
|----------|------|---------|
| Spanish | `es` | "Gasté veinte soles en taxi" |
| English | `en` | "Twenty dollars for groceries" |
| Portuguese | `pt` | "Comprei comida por trinta reais" |
| French | `fr` | "Vingt euros pour le taxi" |
| German | `de` | "Zwanzig Euro für Essen" |

**Auto-detection**: Leave `language=None` for automatic detection.

## Logging

All operations are logged with structured data:

```json
{
  "event": "audio_transcribed_successfully",
  "text_length": 45,
  "language": "es",
  "duration": 3.5,
  "user_id": "user123"
}

{
  "event": "expense_extracted_from_audio_successfully",
  "amount": 20.0,
  "currency": "PEN",
  "category": "transport",
  "confidence": 0.89,
  "transcription_length": 45,
  "detected_language": "es"
}
```

## Integration Example

### WhatsApp Webhook Handler

```python
from fastapi import FastAPI, UploadFile
from app.tools.extraction.audio_extractor import extract_expense_from_audio

app = FastAPI()

@app.post("/webhook/whatsapp/audio")
async def handle_audio(audio: UploadFile, user_id: str):
    """Handle audio message from WhatsApp."""
    
    # Read audio bytes
    audio_bytes = await audio.read()
    
    # Extract expense
    expense = extract_expense_from_audio(
        audio_bytes,
        user_id=user_id,
        source="whatsapp"
    )
    
    # Store in database (Phase 1C)
    # expense_id = store_expense(expense, user_id)
    
    return {
        "expense_id": "...",
        "amount": float(expense.amount),
        "currency": expense.currency,
        "confidence": expense.confidence
    }
```

## Comparison: API vs Local

| Feature | OpenAI Whisper API | Local (faster-whisper) |
|---------|-------------------|------------------------|
| **Accuracy** | Excellent (99%+) | Excellent (98%+) |
| **Speed** | 2-5 seconds | 5-15 seconds |
| **Setup** | API key only | Model download (~1GB) |
| **Cost** | $0.006/min | Free (compute cost) |
| **Offline** | ❌ No | ✅ Yes |
| **Languages** | 99+ | 99+ |
| **Current** | ✅ Implemented | 🚧 Future |

**Recommendation**: Use API for MVP. Add local fallback in Phase 2 if needed.

## Troubleshooting

### Issue: "OPENAI_API_KEY not configured"

**Solution**: Add to `.env`:
```bash
OPENAI_API_KEY=sk-...
```

### Issue: "File too large" (>25MB)

**Solution**: Compress audio before sending:
```bash
ffmpeg -i large_audio.wav -b:a 64k compressed.mp3
```

### Issue: Low confidence scores

**Solution**:
- Improve audio quality (reduce background noise)
- Speak clearly and at moderate pace
- Provide language hint if auto-detect fails

### Issue: Wrong language detected

**Solution**: Specify language explicitly:
```python
expense = extract_expense_from_audio("audio.ogg", language="es")
```

## Next Steps

- Add batch processing support
- Implement transcription caching
- Add audio quality checks
- Support for longer audio (chunking)
- Add speaker diarization (Phase 2+)

## References

- [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text)
- [Text Extractor Documentation](./text-extractor-usage.md)
- [Phase 1 Plan](../plans/phase-1-ie-agent-and-storage.md)
- [Whisper Model Card](https://github.com/openai/whisper/blob/main/model-card.md)


