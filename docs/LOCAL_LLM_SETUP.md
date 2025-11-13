# Local Uncensored LLM Setup

This guide explains how to set up and use local uncensored LLM models (like Drummer's models from HuggingFace) with WompBot.

## Overview

The `/uncensored` command allows you to route specific prompts through a **local** LLM server instead of OpenRouter. This is useful for:

- **Uncensored responses** - Models like Drummer's dolphin series are trained to be less filtered
- **Privacy** - Keep sensitive queries on your local machine
- **Cost savings** - No API costs for using local models
- **Custom models** - Use any HuggingFace model you want

## Quick Start with Ollama (Recommended)

### 1. Install Ollama

**Windows/Mac/Linux:**
```bash
# Visit https://ollama.com/download and install for your OS
# Or on Linux:
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull a Drummer's Uncensored Model

```bash
# Dolphin Llama3 (recommended - good balance of quality and speed)
ollama pull dolphin-llama3

# Or other popular uncensored models:
ollama pull dolphin-mixtral        # Larger, more capable
ollama pull wizardlm-uncensored    # Alternative uncensored model
ollama pull llama3.1:8b            # Base Llama 3.1 (less censored than GPT models)
```

**More Drummer models on HuggingFace:**
- [cognitivecomputations/dolphin-2.9-llama3-8b](https://huggingface.co/cognitivecomputations/dolphin-2.9-llama3-8b)
- [cognitivecomputations/dolphin-2.9.1-mixtral-8x22b](https://huggingface.co/cognitivecomputations/dolphin-2.9.1-mixtral-8x22b)

### 3. Configure WompBot

Edit your `.env` file:

```bash
# Enable local LLM
LOCAL_LLM_ENABLED=true

# Ollama's default endpoint (no changes needed if using defaults)
LOCAL_LLM_URL=http://localhost:11434/v1

# Model name (must match what you pulled)
LOCAL_LLM_MODEL=dolphin-llama3:latest

# Timeout (increase if model is slow)
LOCAL_LLM_TIMEOUT=60
```

### 4. Restart the Bot

```bash
docker-compose restart bot
```

### 5. Test It

In Discord, run:
```
/uncensored What are some controversial topics in AI ethics?
```

## Alternative Setup Options

### Option 1: LM Studio

1. Download [LM Studio](https://lmstudio.ai/)
2. Load a Drummer model (search for "dolphin" or "wizard")
3. Start the local server (Tools → Local Server)
4. Configure `.env`:
   ```bash
   LOCAL_LLM_ENABLED=true
   LOCAL_LLM_URL=http://localhost:1234/v1
   LOCAL_LLM_MODEL=dolphin-2.9-llama3-8b
   ```

### Option 2: vLLM (For GPU servers)

```bash
# Install vLLM
pip install vllm

# Serve a model
python -m vllm.entrypoints.openai.api_server \
    --model cognitivecomputations/dolphin-2.9-llama3-8b \
    --host 0.0.0.0 --port 8000

# Configure .env
LOCAL_LLM_ENABLED=true
LOCAL_LLM_URL=http://localhost:8000/v1
LOCAL_LLM_MODEL=cognitivecomputations/dolphin-2.9-llama3-8b
```

### Option 3: Text Generation WebUI

1. Install [oobabooga's text-generation-webui](https://github.com/oobabooga/text-generation-webui)
2. Load a Drummer model
3. Enable OpenAI API extension
4. Configure `.env`:
   ```bash
   LOCAL_LLM_ENABLED=true
   LOCAL_LLM_URL=http://localhost:5000/v1
   LOCAL_LLM_MODEL=your_model_name
   ```

## Docker Configuration

If running the bot in Docker but Ollama on the host:

```bash
# In .env, use host.docker.internal instead of localhost
LOCAL_LLM_URL=http://host.docker.internal:11434/v1
```

Or if Ollama is on a different machine:
```bash
LOCAL_LLM_URL=http://192.168.1.100:11434/v1
```

## Recommended Drummer Models

### For General Use:
- **dolphin-llama3** (8B params) - Best balance of speed/quality
- **dolphin-mixtral** (8x7B params) - Better quality, slower

### For Specific Tasks:
- **wizardlm-uncensored** - Alternative uncensored option
- **nous-hermes** - Good instruction following

### Finding More Models:
- Browse [HuggingFace](https://huggingface.co/cognitivecomputations)
- Check [Ollama Library](https://ollama.com/library)
- Search for "uncensored" or "dolphin"

## Usage Tips

### Basic Usage
```
/uncensored Tell me about controversial AI alignment theories
```

### The command will:
- Send your prompt to the local LLM
- Use an uncensored system prompt
- Return the response in Discord
- Automatically split long responses into multiple messages

### Performance Tips

1. **First run is slower** - Models need to load into memory
2. **Subsequent requests are faster** - Model stays loaded
3. **Adjust timeout** if responses are slow:
   ```bash
   LOCAL_LLM_TIMEOUT=120  # 2 minutes
   ```
4. **Use smaller models** on low-end hardware:
   - 7B-8B models: Most consumer hardware
   - 13B models: Need 16GB+ RAM
   - 70B+ models: Need GPU or high-end CPU

## Troubleshooting

### "Local LLM not enabled"
- Check `LOCAL_LLM_ENABLED=true` in `.env`
- Restart the bot after changing `.env`

### "Cannot connect to local LLM"
- Verify Ollama/LM Studio is running
- Check the URL is correct (localhost vs host.docker.internal)
- Test the endpoint: `curl http://localhost:11434/api/tags`

### "Request timed out"
- Increase `LOCAL_LLM_TIMEOUT` in `.env`
- Use a smaller/faster model
- Check system resources (CPU/RAM)

### Empty/Invalid responses
- Check logs: `docker-compose logs bot`
- Verify model name matches: `ollama list`
- Try a different model

## Security Notes

- Local LLMs bypass OpenRouter's safety filters
- Use responsibly and follow Discord's Terms of Service
- Consider using `/uncensored` in private channels
- Responses from uncensored models may contain:
  - Profanity
  - Controversial opinions
  - Unfiltered information
- **You** are responsible for how you use these models

## Cost Comparison

| Method | Cost per 1M tokens | Speed | Quality |
|--------|-------------------|-------|---------|
| OpenRouter (Claude) | ~$3-15 | Fast | Excellent |
| Local (dolphin-llama3) | $0 (electricity) | Moderate | Good |
| Local (dolphin-mixtral) | $0 (electricity) | Slow | Very Good |

## Command Reference

```
/uncensored <prompt>        - Query the local uncensored LLM
```

**Parameters:**
- `prompt` (required) - Your question or prompt

**Example:**
```
/uncensored What are the arguments for and against AI regulation?
```

## FAQ

**Q: Can I use this for normal conversation?**
A: Currently, `/uncensored` is for one-off prompts. For full conversations, you'd need to extend the implementation to support history.

**Q: Does this replace OpenRouter?**
A: No, it supplements it. The bot still uses OpenRouter for normal mentions/chat. `/uncensored` is for specific queries.

**Q: Can I use GPT-4 locally?**
A: No, GPT-4 is not open source. But models like dolphin-mixtral approach GPT-3.5 quality.

**Q: How much RAM do I need?**
A:
- 7B-8B models: 8-16GB RAM
- 13B models: 16-32GB RAM
- 70B models: 64GB+ RAM or GPU

**Q: Does this cost money?**
A: No API costs, just electricity. Local inference is free.

**Q: Is this slower than OpenRouter?**
A: Usually yes, especially on CPU. But there's no network latency or API limits.

## Support

For issues or questions:
1. Check Docker logs: `docker-compose logs bot`
2. Verify Ollama is running: `ollama list`
3. Test the API: `curl http://localhost:11434/v1/models`
4. Report issues with full error messages
