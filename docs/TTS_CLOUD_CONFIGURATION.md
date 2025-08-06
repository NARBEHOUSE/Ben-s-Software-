# Cloud TTS Configuration Guide

## Overview
This guide explains how to configure cloud-based TTS services (Azure, ElevenLabs, OpenAI) with Ben's Accessibility Software using py3-tts-wrapper.

## Configuration Structure

The TTS configuration is stored in `shared/tts_config.json`. Here's how to add cloud TTS services:

### Basic Configuration
```json
{
    "engine_priority": ["sapi", "azure", "elevenlabs", "openai", "googletrans"],
    "preferred_voice_id": null,
    "speech_rate": 200,
    "speech_volume": 0.8,
    "auto_save_settings": true
}
```

## Azure Cognitive Services TTS

### Setup Steps
1. **Get Azure Subscription Key**:
   - Go to [Azure Portal](https://portal.azure.com)
   - Create a "Speech Services" resource
   - Copy the subscription key and region

2. **Add Azure Configuration**:
```json
{
    "azure": {
        "subscription_key": "YOUR_AZURE_KEY_HERE",
        "region": "eastus",
        "voice_name": "en-US-AriaNeural",
        "language": "en-US",
        "output_format": "audio-16khz-32kbitrate-mono-mp3",
        "use_neural_voices": true,
        "prosody": {
            "rate": "medium",
            "pitch": "medium",
            "volume": "medium"
        }
    }
}
```

### Popular Azure Voices
- **English (US)**: `en-US-AriaNeural`, `en-US-JennyNeural`, `en-US-GuyNeural`
- **English (UK)**: `en-GB-SoniaNeural`, `en-GB-RyanNeural`
- **Spanish**: `es-ES-ElviraNeural`, `es-MX-DaliaNeural`
- **French**: `fr-FR-DeniseNeural`, `fr-CA-SylvieNeural`

## ElevenLabs TTS

### Setup Steps
1. **Get ElevenLabs API Key**:
   - Sign up at [ElevenLabs](https://elevenlabs.io)
   - Go to Profile → API Keys
   - Generate and copy your API key

2. **Add ElevenLabs Configuration**:
```json
{
    "elevenlabs": {
        "api_key": "YOUR_ELEVENLABS_KEY_HERE",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "model_id": "eleven_monolingual_v1",
        "stability": 0.5,
        "similarity_boost": 0.5,
        "style": 0.0,
        "use_speaker_boost": true
    }
}
```

### Popular ElevenLabs Voices
- **Rachel**: `21m00Tcm4TlvDq8ikWAM` (default)
- **Drew**: `29vD33N1CtxCmqQRPOHJ`
- **Clyde**: `2EiwWnXFnvU5JabPnv8n`
- **Paul**: `5Q0t7uMcjvnagumLfvZi`

## OpenAI TTS

### Setup Steps
1. **Get OpenAI API Key**:
   - Go to [OpenAI Platform](https://platform.openai.com)
   - Create an API key in your account settings

2. **Add OpenAI Configuration**:
```json
{
    "openai": {
        "api_key": "YOUR_OPENAI_KEY_HERE",
        "model": "tts-1",
        "voice": "alloy",
        "response_format": "mp3",
        "speed": 1.0
    }
}
```

### OpenAI TTS Voices
- **alloy**: Balanced, neutral voice
- **echo**: Male voice
- **fable**: British accent
- **onyx**: Deep male voice
- **nova**: Young female voice
- **shimmer**: Soft female voice

## Engine Priority Configuration

Set the order in which TTS engines are tried:

```json
{
    "engine_priority": [
        "sapi",        // Windows SAPI (local, fast)
        "azure",       // Azure (cloud, high quality)
        "elevenlabs",  // ElevenLabs (cloud, very high quality)
        "openai",      // OpenAI (cloud, good quality)
        "googletrans", // Google Translate (free, online)
        "espeak"       // eSpeak (local, basic)
    ]
}
```

## Usage Examples

### Programmatic Configuration
```python
from shared.utils import set_tts_config, get_tts_manager

# Set Azure as primary engine
set_tts_config("engine_priority", ["azure", "sapi"])

# Configure Azure credentials
set_tts_config("azure", {
    "subscription_key": "your-key-here",
    "region": "eastus",
    "voice_name": "en-US-AriaNeural"
})

# Get new TTS manager with updated config
tts = get_tts_manager()
tts.speak_sync("Hello from Azure TTS!")
```

### Testing Different Engines
```python
from shared.utils import set_tts_config, speak_sync

# Test Azure
set_tts_config("engine_priority", ["azure"])
speak_sync("Testing Azure TTS")

# Test ElevenLabs
set_tts_config("engine_priority", ["elevenlabs"])
speak_sync("Testing ElevenLabs TTS")

# Test OpenAI
set_tts_config("engine_priority", ["openai"])
speak_sync("Testing OpenAI TTS")
```

## Security Notes

1. **Never commit API keys** to version control
2. **Use environment variables** for production:
```python
import os
set_tts_config("azure", {
    "subscription_key": os.getenv("AZURE_TTS_KEY"),
    "region": os.getenv("AZURE_TTS_REGION", "eastus")
})
```

3. **Rotate keys regularly** and monitor usage

## Cost Considerations

- **SAPI/eSpeak**: Free (local)
- **Google Translate**: Free (limited)
- **Azure**: Pay per character (~$4/1M characters)
- **ElevenLabs**: Subscription based (~$5-22/month)
- **OpenAI**: Pay per character (~$15/1M characters)

## Troubleshooting

### Common Issues
1. **"No API key configured"**: Add your API key to the config
2. **"Initialization failed"**: Check internet connection and API key validity
3. **"Rate limit exceeded"**: Wait or upgrade your plan
4. **Poor audio quality**: Try different voice models or output formats

### Debug Mode
Enable debug logging to see detailed TTS information:
```python
set_tts_config("debug_mode", True)
```

## Complete Example Configuration

See `shared/tts_config_example_with_azure.json` for a complete configuration example with all supported cloud TTS services.
