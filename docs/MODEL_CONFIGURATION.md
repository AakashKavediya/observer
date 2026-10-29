# Track 2 — Task Sequencer: Model Configuration Guide

## 1. Centralized Configuration
All LLM and RAG parameters are centralized in `observer/engine/observer_engine/sequencer/config.py`:

| Parameter | Default | Environment Variable | Description |
| :--- | :--- | :--- | :--- |
| `llm_provider` | `ollama` | — | Primary local inference runtime |
| `ollama_endpoint` | `http://localhost:11434` | `OLLAMA_HOST` | Local HTTP API host |
| `model_name` | `llama3.2:latest` | `OBSERVER_LLM_MODEL` | Target local model |
| `request_timeout` | `20.0s` | — | HTTP connection timeout |
| `generation_timeout` | `45.0s` | — | Maximum response generation duration |
| `max_input_length` | `4000` chars | — | User prompt length cap |
| `max_generated_tokens`| `1024` tokens | — | Token budget per response |
| `embedding_model` | `local_tfidf_minilm` | — | 256-dim subword vectorizer |
| `retrieval_top_k` | `4` | — | Number of RAG chunks passed to LLM |
| `min_retrieval_relevance` | `0.20` | — | Cosine similarity cutoff |
| `history_limits` | `10` turns | — | Context memory window |

---

## 2. Supported Local Models
Tested and verified with Ollama:
- `llama3.2:latest` (Default, recommended: ~2.0 GB, fast CPU inference, strict JSON adherence)
- `llama3.2:1b` (Ultra-lightweight: ~1.3 GB, low-RAM laptops)
- `mistral:latest` (7B parameter model, high precision)

---

## 3. External API Disclosure & Non-Automatic Activation
Per project ethics rules:
- External API providers (e.g. OpenAI/Anthropic) are **disabled by default**.
- They can only be enabled by explicit user configuration in settings.
- If enabled, the UI prominently displays that queries will be transmitted over the network.
- The default installation works 100% locally with zero internet access when Ollama and models are present.
