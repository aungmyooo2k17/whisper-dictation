#!/bin/bash
# Install whisper-dictation without pip
# For users who prefer manual installation

set -e

echo "Installing whisper-dictation..."

# Create directories
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/whisper-dictation/icons
mkdir -p ~/.config/whisper-dictation/icons

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv ~/.local/share/whisper-dictation/venv
source ~/.local/share/whisper-dictation/venv/bin/activate

# Install faster-whisper
echo "Installing faster-whisper..."
pip install --upgrade pip
pip install faster-whisper

# Copy icons
echo "Copying icons..."
cp "$SCRIPT_DIR/whisper_dictation/icons/"*.gif ~/.local/share/whisper-dictation/icons/
cp "$SCRIPT_DIR/whisper_dictation/icons/"*.gif ~/.config/whisper-dictation/icons/

# Copy main script
cp "$SCRIPT_DIR/whisper_dictation/dictation.py" ~/.local/share/whisper-dictation/
cp "$SCRIPT_DIR/whisper_dictation/indicator.py" ~/.local/share/whisper-dictation/

# Create wrapper scripts
cat > ~/.local/bin/whisper-dictation << 'EOF'
#!/bin/bash
source ~/.local/share/whisper-dictation/venv/bin/activate
exec python3 ~/.local/share/whisper-dictation/dictation.py "$@"
EOF

cat > ~/.local/bin/whisper-dictation-indicator << 'EOF'
#!/bin/bash
exec python3 ~/.local/share/whisper-dictation/indicator.py "$@"
EOF

# Copy toggle script
cp "$SCRIPT_DIR/scripts/whisper-dictation-toggle" ~/.local/bin/

# Make executable
chmod +x ~/.local/bin/whisper-dictation
chmod +x ~/.local/bin/whisper-dictation-indicator
chmod +x ~/.local/bin/whisper-dictation-toggle

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Add ~/.local/bin to your PATH (if not already):"
echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "2. Set up keyboard shortcut:"
echo "   $SCRIPT_DIR/scripts/setup-shortcut.sh"
echo ""
echo "3. Or manually: Settings → Keyboard → Custom Shortcuts"
echo "   Command: ~/.local/bin/whisper-dictation-toggle"
echo "   Shortcut: Ctrl+Shift+Space"
