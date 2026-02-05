# TeleCode: Remote Control for OpenCode

**TeleCode** is a lightweight Python wrapper that connects your local **OpenCode CLI** to a private **Telegram Bot**. It allows you to monitor your AI agent's progress and remotely approve sensitive actions directly from your phone.

---

## **Quick Setup**

This tool is designed to live in `tools/telecode` inside your project root.

```bash
# 1. Clone into your tools directory
mkdir -p tools
git clone https://github.com/azavibe/telecode tools/telecode

# 2. Run from your project root
./tools/telecode/start.sh
```

---

## **Collaborations**

Welcome to the TeleCode community! We love collaborations. Whether it's fixing bugs, adding new safety patterns, or improving the streaming experience, feel free to open a Pull Request or an Issue. Let's build the best remote terminal for AI agents together!

## **License**

This project is licensed under the [MIT License](LICENSE).


---

## Directory Structure

```
/home/maza/dev/telecode/   # Your project root
├── tools/
│   └── telecode/          # TeleCode tool location
│       ├── telecode.py
│       ├── start.sh
│       └── ...
├── .agent                 # Root files
└── hello.html             # Files created by TeleCode
```

---

## Prerequisites

1. **Python 3.12+** (Installed on your system)
2. **OpenCode CLI** installed and authenticated.
3. **Telegram Account** with a bot created via [@BotFather](https://t.me/botfather)

---

## Installation

1. **Navigate to your tools folder:**
```bash
cd ~/tools/telecode  # or wherever you placed it
```

2. **Configure credentials:**
```bash
# Edit telecode.py and set your tokens
nano telecode.py
```

3. **Run the bot:**
```bash
chmod +x start.sh
./start.sh
```

---

## Configuration

Edit `telecode.py` and set your credentials:

```python
# --- CONFIGURATION ---
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"  # Get from @BotFather
YOUR_USER_ID = 123456789           # Get from @userinfobot
# ---------------------
```

**Get your credentials:**
- **Bot Token**: Message [@BotFather](https://t.me/botfather), create a new bot, and copy the token
- **User ID**: Message [@userinfobot](https://t.me/userinfobot) and copy your ID

---

## Telegram Commands

### Session Management

| Command | Description |
|---------|-------------|
| `/s` or `/sessions` | List all available opencode sessions |
| `/s <number>` | Switch to a specific session (e.g., `/s 1`) |
| `/new` | Create a new session with random ID |

### Control Commands

| Command | Description |
|---------|-------------|
| `/stop` or `stop` | Kill the currently running opencode process |
| `/model <name>` | Change the AI model (e.g., `/model opencode/gpt-4o`) |

### How to Use

1. **Start the bot** and send any message to create a session
2. **List sessions**: Send `/s` to see available sessions
3. **Switch session**: Send `/s 1` to use the first session
4. **Send commands**: Just type your request (e.g., "create a React app")

**Example workflow:**
```
You: create hello.html with title Hello
Bot: > build · kimi-k2.5-free
     ← Write hello.html
     Wrote file successfully.
     Created hello.html

You: /s
Bot: 📋 Available Sessions:
     • ses_abc123
     • ses_xyz789
     
     Using: Default (continuing last session)
     Use `/s <number>` to switch

You: /s 1
Bot: ✅ Switched to session: ses_abc123
```

---

## Features

### Session Persistence
- By default, continues the last opencode session
- Switch between multiple active sessions
- Each session maintains its own conversation context

### Smart Notifications
- Get notified when OpenCode needs approval `(y/n)`
- Reply directly in Telegram to approve/deny
- Full output capture - see everything OpenCode does

### Portable Setup
- Place in `~/tools/telecode/` or any directory
- Run from any project folder
- Automatically creates virtual environment on first run

---

## Directory Structure

```
~/tools/telecode/          # TeleCode installation
├── telecode.py           # Main bot script
├── start.sh              # Launch script
├── requirements.txt      # Python dependencies
└── venv/                 # Virtual environment (auto-created)

~/my-project/             # Your working directory
├── (your files here)     # Files OpenCode will work with
└── (run bot from here)   # cd here, then ~/tools/telecode/start.sh
```

---

## Troubleshooting

**Issue: "externally-managed-environment"**
* The `start.sh` script handles virtual environment automatically. Just use `./start.sh`

**Issue: "Conflict - Another instance is running"**
* Another bot instance is already running. Kill it with:
  ```bash
  pkill -f "python telecode.py"
  ```

**Issue: "Resource not found ... ses_xxx.json"**
* This happens when switching to a non-existent session. Use `/s` to list valid sessions.

**Issue: "All Antigravity endpoints failed"**
* Check your internet connection or `opencode` authentication status.

**Issue: Bot not responding**
* Make sure `TELEGRAM_TOKEN` and `YOUR_USER_ID` are set correctly in `telecode.py`
* Check that the bot is started: `ps aux | grep telecode`

---

## Tips

1. **Run from project root**: Always start the bot from the directory where you want OpenCode to work
2. **Session isolation**: Use `/s` to switch sessions when working on different projects
3. **Clean output**: The bot captures stderr/stdout and sends clean final responses
4. **Quote handling**: You can use quotes in messages - they're escaped automatically

---

## Security Notes

- Never commit your `telecode.py` with real tokens to git
- Keep your bot token private - anyone with it can control your bot
- The bot only responds to your `YOUR_USER_ID` - others are ignored
