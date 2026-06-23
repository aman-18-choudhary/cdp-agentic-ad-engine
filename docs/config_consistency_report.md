# Configuration Consistency Report

## Scope
Verify that `OLLAMA_CHAT_MODEL` is consistent across all configuration files and actual usage.

## Settings

| Setting | File | Value | Status |
|---------|------|-------|:------:|
| `ollama_chat_model` | `common/settings.py` (default) | `qwen2.5:3b` | VERIFIED — line 6 |
| `OLLAMA_CHAT_MODEL` | `.env.example` | `qwen2.5:3b` | **CORRECTED** — was `tinyllama`, updated 2026-06-23 |
| `OLLAMA_CHAT_MODEL` default | `docker-compose.yml` entrypoint | `qwen2.5:3b` | **CORRECTED** — was `tinyllama`, updated 2026-06-23 |
| `OLLAMA_CHAT_MODEL` (runtime) | `agents/intent_profiler.py` line 58 | `settings.ollama_chat_model` (fallback) | VERIFIED |
| `OLLAMA_CHAT_MODEL` (runtime) | `agents/ad_creative.py` line 50 | `settings.ollama_chat_model` (fallback) | VERIFIED |
| `OLLAMA_CHAT_MODEL` (actual) | Ollama server (localhost:11434) | `qwen2.5:3b` | VERIFIED — model present |
| `OLLAMA_CHAT_MODEL` (override) | `.env` (active config) | Not set (uses settings.py) | VERIFIED — no env override |

## Embed Model

| Setting | File | Value | Status |
|---------|------|-------|:------:|
| `ollama_embed_model` | `common/settings.py` (default) | `nomic-embed-text` | VERIFIED — line 7 |
| `OLLAMA_EMBED_MODEL` | `.env.example` | `nomic-embed-text` | VERIFIED |
| `OLLAMA_EMBED_MODEL` default | `docker-compose.yml` entrypoint | `nomic-embed-text` | VERIFIED |

## Resolution
- **Root cause**: `.env.example` and `docker-compose.yml` defaulted to `tinyllama` while `settings.py` and actual usage used `qwen2.5:3b`
- **Fix applied**: Both files updated to `qwen2.5:3b` on 2026-06-23
- **All files now agree**: `qwen2.5:3b` is the consistent default across all configuration layers
