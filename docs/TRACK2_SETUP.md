# Track 2 — Task Sequencer: Setup & Installation Guide

## 1. Prerequisites
- **Python 3.10+** (existing environment)
- **Node.js 18+** & npm
- **Rust Toolchain** (cargo, stable)
- **Ollama** (for local offline LLM inference)

---

## 2. Ollama Installation & Model Configuration

The Task Sequencer uses Ollama for 100% private, local inference.

### Step 1: Install Ollama
- **macOS**: `brew install ollama` or download from [ollama.com](https://ollama.com)
- **Windows**: Download Windows installer from [ollama.com/download/windows](https://ollama.com/download/windows)
- **Linux**: `curl -fsSL https://ollama.ai/install.sh | sh`

### Step 2: Start the Ollama Service
```bash
ollama serve
```
By default, Ollama listens on `http://localhost:11434`.

### Step 3: Pull the Recommended Model
The default model is `llama3.2:latest` (or `mistral:latest`):
```bash
ollama pull llama3.2
```

---

## 3. Environment Variables (Optional)
You can customize the LLM endpoint or model via environment variables:
```bash
export OLLAMA_HOST="http://localhost:11434"
export OBSERVER_LLM_MODEL="llama3.2:latest"
```

---

## 4. Running the Complete Application

```bash
# 1. Start Ollama in background
ollama serve &

# 2. Build or start the Tauri app
cd observer
npm install
cd src-tauri && cargo build && cd ..

# Launch debug binary
./src-tauri/target/debug/observer
```

If Ollama is not running, the application opens normally and displays a clear setup banner with a **Retry** button—it never crashes or silently mocks data.
