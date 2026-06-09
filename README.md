# 🤖 Agent-7: Advanced AI System Automation

Agent-7 is an autonomous AI agent that controls your Mac system. Powered by Google Gemini (or local Ollama models), it allows you to plan and execute system actions—such as web browsing, messaging, file management, and even screen analysis—using plain English.

---

## 🚀 Getting Started

Follow these steps to set up and run Agent-7 locally.

### 📋 Prerequisites

Ensure you have Python 3.10+ installed on your Mac. You can check this by running:
```bash
python3 --version
```

### 1. Set Up a Virtual Environment (Recommended)

Navigate to the project directory and create a virtual environment to manage dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

Install all the required python packages and install the Playwright browser dependencies:
```bash
pip install -r requirements.txt
playwright install
```

### 3. Configure Environment Variables

1. Copy the example environment file to create your `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` in a text editor and add your **Gemini API Key**:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   *Note: If you don't have a Gemini API key, you can get one for free at [Google AI Studio](https://aistudio.google.com).*

---

## 🏃 Running Agent-7

With your virtual environment active and `.env` configured, you can run Agent-7 in several modes:

### A. Interactive Command Line Mode (Default)
This starts an interactive prompt where you can give multiple commands:
```bash
python3 main.py
```

### B. Single Command Mode
Execute a single instruction immediately and exit:
```bash
python3 main.py "Open Google Chrome and search for local weather"
```

### C. Run with Web Dashboard
Start the dashboard to monitor the agent's actions and screen state visually at `http://localhost:7777`:
```bash
python3 main.py --dashboard
```

### D. Lightweight MCQ-only Mode
Runs a background listener specifically for solving MCQs on your screen:
```bash
python3 main.py --mcq
```
*Hotkeys for MCQ mode:*
- `Control + Command`: Solve & auto-click.
- `Control + Option`: Show answer in an overlay/notification.

---

## 🛡️ Safety & Controls

- **Confirmation Levels**: You can set `CONFIRMATION_LEVEL` in `.env` to:
  - `CONFIRM_ALL`: Asks you before taking any mouse, keyboard, or system action.
  - `CONFIRM_DANGEROUS`: Asks before executing actions like deleting files, sending messages, or posting.
  - `NO_CONFIRM`: Runs on autopilot (use with caution).
- **Emergency Stop / Kill Switch**: Move your mouse cursor quickly to any of the four corners of your monitor to trigger Python's FailSafe and abort execution.
