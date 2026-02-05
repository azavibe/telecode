import asyncio
import time
import pexpect
import sys
import os
import signal

try:
    from telegram import Bot, Update
    from telegram.ext import Application, MessageHandler, filters, Defaults
    from telegram.error import Conflict
except ImportError:
    print("\n❌ ERROR: Could not import 'telegram'.")
    print("👉 Please run this script using the provided start script:")
    print("   ./start.sh")
    print("\nOr activate your virtual environment manually:")
    print("   source venv/bin/activate\n")
    sys.exit(1)


def session_exists(session_id: str) -> bool:
    """Check if an opencode session file exists."""
    session_path = os.path.expanduser(
        f"~/.local/share/opencode/storage/session/global/{session_id}.json"
    )
    return os.path.exists(session_path)


def list_sessions() -> list:
    """List all available opencode sessions with metadata."""
    import json

    sessions_dir = os.path.expanduser("~/.local/share/opencode/storage/session/global/")
    sessions = []
    if os.path.exists(sessions_dir):
        for filename in os.listdir(sessions_dir):
            if filename.endswith(".json"):
                session_id = filename[:-5]  # Remove .json
                try:
                    with open(os.path.join(sessions_dir, filename), "r") as f:
                        data = json.load(f)
                        title = data.get("title", "Untitled")
                        # Extract short name from title (e.g., "create hello html" from "create hello html - 2026-01-20...")
                        if " - " in title:
                            short_title = title.split(" - ")[0]
                        else:
                            short_title = title
                        # Limit title length
                        if len(short_title) > 40:
                            short_title = short_title[:37] + "..."
                        sessions.append(
                            {
                                "id": session_id,
                                "title": short_title,
                                "full_title": title,
                            }
                        )
                except:
                    sessions.append(
                        {
                            "id": session_id,
                            "title": session_id[:20] + "...",
                            "full_title": session_id,
                        }
                    )
    return sessions


# --- CONFIGURATION ---
# Load secrets from environment or .env file
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
YOUR_USER_ID = int(os.environ.get("YOUR_USER_ID", 0))

if not TELEGRAM_TOKEN or not YOUR_USER_ID:
    print("❌ ERROR: TELEGRAM_TOKEN or YOUR_USER_ID not found in environment.")
    print("Please create a .env file in the same directory as telecode.py")
    sys.exit(1)
# ---------------------
# Session will be auto-created by opencode on first message
# Safety modes: "ask" (default - ask for dangerous operations), "auto" (allow everything)
state = {
    "session_id": None,
    "current_model": "opencode/kimi-k2.5-free",
    "safety_mode": "ask",  # "ask" or "auto"
    "pending_command": None,  # Store command waiting for approval
}

# Dangerous command patterns that require approval in "ask" mode
DANGEROUS_PATTERNS = [
    "rm ",
    "remove",
    "delete",
    "del ",
    "unlink",
    "rmdir",
    "rm -rf",
    "rm -r ",
    "> ",
    ">> ",  # File overwrite
    "chmod ",
    "chown ",
    "sudo ",
    "su ",
    "dd ",
    "mkfs",
    "fdisk",
]


def is_dangerous_command(text: str) -> bool:
    """Check if a command contains dangerous operations."""
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in DANGEROUS_PATTERNS)


# ---------------------

child_process = None


# 1. TELEGRAM SENDER (Streamer)
async def send_to_telegram(bot, text):
    if not text or not text.strip():
        return
    clean = text.strip()
    # Filter out ANSI codes (colors) for Telegram readability
    import re

    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    clean = ansi_escape.sub("", clean)

    if len(clean) > 0:
        try:
            # Send without Markdown parsing to avoid issues with special characters
            await bot.send_message(
                chat_id=YOUR_USER_ID,
                text=clean[:4000],  # Telegram limit
            )
        except:
            pass


# 2. THE PTY ENGINE (The Linux Magic)
async def run_process_listener(app):
    global child_process

    # Check if a command was queued
    if not hasattr(app, "queued_command"):
        return
    cmd = app.queued_command

    print(f"🚀 Launching PTY for: {cmd}")

    # SPAWN WITH PTY (Simulates real human terminal)
    # encoding='utf-8' ensures we handle text correctly
    # Use working directory from environment (set by start.sh) or current directory
    cwd = os.environ.get("TELECODE_WORKING_DIR", os.getcwd())
    child_process = pexpect.spawn(
        f"bash -c 'cd {cwd} && {cmd}'",
        encoding="utf-8",
        timeout=None,
    )

    output_buffer = ""

    # Read output loop - collect everything, send only at end
    full_output = ""
    while True:
        try:
            # Read chunks of text
            output = child_process.read_nonblocking(size=1024, timeout=0.1)
            if output:
                sys.stdout.write(output)
                sys.stdout.flush()
                full_output += output
                output_buffer += output

                # Check for prompts to auto-notify immediately
                if "(y/n)" in output.lower():
                    await send_to_telegram(app.bot, output_buffer)
                    output_buffer = ""
                    await send_to_telegram(app.bot, "⚠️ **Action Required: (y/n)**")

        except pexpect.TIMEOUT:
            pass  # No new data, continue
        except pexpect.EOF:
            break

        await asyncio.sleep(0.05)

    # Send complete output at the end (only the final response)
    if full_output:
        # Extract the meaningful part (after the model header)
        lines = full_output.split("\n")
        meaningful_lines = []
        found_content = False
        for line in lines:
            if found_content or ("·" in line and "kimi" in line.lower()):
                found_content = True
            if found_content and line.strip():
                meaningful_lines.append(line)

        if meaningful_lines:
            final_text = "\n".join(meaningful_lines)
            await send_to_telegram(app.bot, final_text)

    await send_to_telegram(app.bot, "🏁 Process Finished.")
    child_process = None
    app.queued_command = None


# 3. HANDLER
async def telegram_reply_handler(update: Update, context):
    if update.message.chat_id != YOUR_USER_ID:
        return
    user_text = update.message.text.strip()
    global child_process

    print(f"[Remote]: {user_text}")

    # --- 1. SPECIAL BOT COMMANDS ---
    cmd_lower = user_text.lower().strip()

    # /new - New Session
    if cmd_lower == "/new":
        state["session_id"] = "ses_" + str(int(time.time()))
        state["current_session"] = None  # Clear specific session
        await update.message.reply_text(
            f"🆕 **New Session Started**\nID: `{state['session_id']}`"
        )
        return

    # /model or /m - Change Model
    if cmd_lower.startswith("/model ") or cmd_lower.startswith("/m "):
        # Support both "/model <name>" and "/m <name>"
        prefix_len = 7 if cmd_lower.startswith("/model ") else 3
        new_model = user_text[prefix_len:].strip()
        if new_model:
            state["current_model"] = new_model
            await update.message.reply_text(
                f"🤖 **Model Updated**\nNow using: `{state['current_model']}`"
            )
        return

    # /models - List available models
    if cmd_lower == "/models":
        try:
            import subprocess

            result = subprocess.run(
                ["opencode", "models"], capture_output=True, text=True, timeout=10
            )
            models_output = result.stdout.strip()
            if models_output:
                # Send exactly as opencode outputs it (raw format)
                if len(models_output) > 4000:
                    await update.message.reply_text(
                        models_output[:4000] + "\n... (truncated)"
                    )
                else:
                    await update.message.reply_text(models_output)
            else:
                await update.message.reply_text("❌ Could not fetch models list.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error fetching models: {str(e)}")
        return

    # /sessions or /s - List available sessions
    if cmd_lower in ["/sessions", "/s"]:
        sessions = list_sessions()
        if sessions:
            # Format as numbered list with titles
            session_list = "\n".join(
                [f"{i + 1}. {s['title']}" for i, s in enumerate(sessions[:10])]
            )
            current_id = state.get("current_session")
            current = ""
            if current_id:
                # Find the title of current session
                current_session = next(
                    (s for s in sessions if s["id"] == current_id), None
                )
                if current_session:
                    current = f"\n\n**Current:** {current_session['title']}"
                else:
                    current = f"\n\n**Current:** {current_id[:30]}..."
            else:
                current = "\n\n**Current:** Continuing last session"
            await update.message.reply_text(
                f"📋 **Available Sessions:**\n{session_list}{current}\n\nUse `/s <number>` to switch (e.g., `/s 1`)"
            )
        else:
            await update.message.reply_text(
                "📭 No sessions found. Send any message to create one."
            )
        return

    # /s <n> - Switch to session by index
    if cmd_lower.startswith("/s "):
        try:
            idx = int(cmd_lower[3:].strip()) - 1  # Convert to 0-based index
            sessions = list_sessions()
            if 0 <= idx < len(sessions):
                session = sessions[idx]
                state["current_session"] = session["id"]
                await update.message.reply_text(
                    f"✅ **Switched to:** {session['title']}\n\nNext message will use this session."
                )
            else:
                await update.message.reply_text(
                    f"❌ Invalid session number. Use `/s` to see available sessions."
                )
        except ValueError:
            await update.message.reply_text("❌ Usage: `/s <number>` (e.g., `/s 1`)")
        return

    # /safety - Show or change safety mode
    if cmd_lower.startswith("/safety"):
        if cmd_lower == "/safety":
            mode = state.get("safety_mode", "ask")
            mode_desc = (
                "ask before dangerous operations"
                if mode == "ask"
                else "allow all operations automatically"
            )
            await update.message.reply_text(
                f"🛡️ **Safety Mode Settings**\n"
                f"Current: `{mode}`\n"
                f"({mode_desc})\n\n"
                f"Choose mode:\n"
                f"🔒 /safety_ask - Ask for confirmation\n"
                f"🚀 /safety_auto - Allow everything"
            )
        else:
            # Handle /safety_ask and /safety_auto
            new_mode = (
                cmd_lower.replace("/safety_", "")
                .replace("ask", "ask")
                .replace("auto", "auto")
                .strip()
            )
            if new_mode in ["ask", "auto"]:
                state["safety_mode"] = new_mode
                await update.message.reply_text(
                    f"🛡️ **Safety mode changed to:** `{new_mode}`\n\n"
                    f"{'Will ask before dangerous operations' if new_mode == 'ask' else 'Will allow all operations automatically'}"
                )
        return

    # Direct aliases for safety modes
    if cmd_lower == "/safety_ask":
        state["safety_mode"] = "ask"
        await update.message.reply_text(
            "🛡️ **Safety Mode:** `ask` (will confirm deletes)"
        )
        return
    if cmd_lower == "/safety_auto":
        state["safety_mode"] = "auto"
        await update.message.reply_text("🛡️ **Safety Mode:** `auto` (allow everything)")
        return

    # /info - Show current bot status
    if cmd_lower in ["/info", "/status"]:
        session_name = "Continuing last session"
        if state.get("current_session"):
            sessions = list_sessions()
            curr = next(
                (s for s in sessions if s["id"] == state["current_session"]), None
            )
            session_name = curr["title"] if curr else state["current_session"]

        await update.message.reply_text(
            f"ℹ️ **TeleCode Status**\n\n"
            f"🤖 **Model:** `{state['current_model']}`\n"
            f"📁 **Session:** `{session_name}`\n"
            f"🛡️ **Safety:** `{state['safety_mode']}`\n"
            f"📍 **Working Dir:** `{os.environ.get('TELECODE_WORKING_DIR', os.getcwd())}`\n\n"
            f"Settings: /safety | /models | /s"
        )
        return

    # Catch-all for unknown bot commands (anything starting with /)
    if user_text.startswith("/") and cmd_lower not in ["/yes", "/no", "/y", "/n"]:
        await update.message.reply_text(
            f"❓ **Unknown command:** `{user_text}`\n"
            f"Available: `/s`, `/models`, `/m <name>`, `/safety`, `/info`, `/new`, `/stop`"
        )
        return

    # --- 2. PENDING APPROVALS ---
    # Handle pending command approval (yes/no response)
    if state.get("pending_command"):
        if cmd_lower in ["yes", "y", "да", "ye", "yeah", "sure", "ok", "/yes", "/y"]:
            cmd = state["pending_command"]
            state["pending_command"] = None
            await update.message.reply_text(f"✅ **Approved. Executing...**")

            # Execute the approved command
            context.application.queued_command = cmd
            asyncio.create_task(run_process_listener(context.application))
            return

        if cmd_lower in [
            "no",
            "n",
            "нет",
            "nah",
            "cancel",
            "abort",
            "stop",
            "/no",
            "/n",
        ]:
            state["pending_command"] = None
            await update.message.reply_text("❌ **Operation cancelled.**")
            return

        # If user sends something else while waiting for approval
        await update.message.reply_text(
            "⚠️ **Waiting for approval!**\nPlease tap /yes or /no below."
        )
        return

    # --- 3. OPENCODE EXECUTION ---
    # /stop or "stop"
    if cmd_lower in ["stop", "/stop"]:
        if child_process:
            child_process.terminate(force=True)
            child_process = None
        context.application.queued_command = None
        await update.message.reply_text("🛑 **Killed.**")
        return

    # B. INPUT (If running, type into it)
    if child_process and child_process.isalive():
        child_process.sendline(user_text)
        await update.message.reply_text("✅ Sent.")
        return

    # C. START NEW COMMAND
    if user_text.lower().startswith("opencode"):
        final_cmd = user_text
    else:
        # Inject Model flag
        model_flag = (
            f"--model {state['current_model']}" if state["current_model"] else ""
        )
        # Use specific session if selected, otherwise continue last session
        # Escape quotes in user text to prevent bash errors
        escaped_text = user_text.replace('"', '\\"')
        if state.get("current_session"):
            # Use specific session
            session_flag = f"--session {state['current_session']}"
            final_cmd = f'opencode run {session_flag} {model_flag} "{escaped_text}"'
        else:
            # Continue last session (default behavior)
            final_cmd = f'opencode run --continue {model_flag} "{escaped_text}"'

    # Check for dangerous commands if in "ask" mode
    if state.get("safety_mode", "ask") == "ask" and is_dangerous_command(final_cmd):
        state["pending_command"] = final_cmd
        await update.message.reply_text(
            f"⚠️ **Dangerous operation detected:**\n"
            f"`{final_cmd[:200]}...`\n\n"
            f"Allow execution?\n"
            f"✅ /yes  |  ❌ /no\n\n"
            f"_Mode: {state['safety_mode']} (change: /safety)_"
        )
        return

    await update.message.reply_text(f"🚀 Queueing: {final_cmd}")

    # Pass command to the loop
    context.application.queued_command = final_cmd
    # Start the listener task
    asyncio.create_task(run_process_listener(context.application))


async def error_handler(update: object, context):
    """Log errors and handle specific exceptions."""
    error = context.error
    if isinstance(error, Conflict):
        print("⚠️  Warning: Bot conflict detected. Another instance is running.")
        print("🛑 Stopping this instance...")
        sys.exit(0)
    else:
        print(f"⚠️  Error: {error}")


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .build()
    )

    app.add_handler(MessageHandler(filters.TEXT, telegram_reply_handler))
    app.add_error_handler(error_handler)

    print("🚀 TeleCode (Linux/WSL Mode) Active.")

    # run_polling handles the event loop, signals (Ctrl+C), and updates automatically.
    # It defaults to poll_interval=1.0 if not specified (default is actually 0.0 but we can tune if needed).
    app.run_polling(poll_interval=1.0)


if __name__ == "__main__":
    main()
