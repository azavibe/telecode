#!/bin/bash
# TeleCode Launcher - Portable version
# This script can be run from any directory

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Save the current directory (where user ran the command)
WORKING_DIR="$(pwd)"

# If user is running this from inside the tools/telecode directory,
# we should probably set the root to one level above 'tools'
if [[ "$WORKING_DIR" == *"/tools/telecode" ]]; then
    # Go up two levels from tools/telecode to reach the root
    PARENT_DIR="$(dirname "$(dirname "$WORKING_DIR")")"
    echo "⚠️  Detected running from tool folder. Switching root to: $PARENT_DIR"
    WORKING_DIR="$PARENT_DIR"
fi

echo "🚀 Starting TeleCode..."
echo "📁 Project root: $WORKING_DIR"
echo "🔧 Tool location: $SCRIPT_DIR"

# Change to script directory to access venv
cd "$SCRIPT_DIR"

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run the bot, staying in the working directory
echo "🤖 Bot is starting..."
echo "📂 Files will be created in: $WORKING_DIR"
echo ""

# Pass working directory to Python so it can cd there
export TELECODE_WORKING_DIR="$WORKING_DIR"
python telecode.py
