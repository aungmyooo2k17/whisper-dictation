#!/bin/bash
# Set up GNOME keyboard shortcut for whisper-dictation
# Run this script once after installation

set -e

SHORTCUT="${1:-<Control><Shift>space}"
TOGGLE_SCRIPT=$(which whisper-dictation-toggle 2>/dev/null || echo "$HOME/.local/bin/whisper-dictation-toggle")

echo "Setting up whisper-dictation keyboard shortcut..."
echo "Shortcut: $SHORTCUT"
echo "Command: $TOGGLE_SCRIPT"

# Get existing custom keybindings
EXISTING=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "[]")

# Find next available slot
SLOT=0
while [[ "$EXISTING" == *"custom$SLOT"* ]]; do
    ((SLOT++))
done

KEYBINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom$SLOT/"

# Add to list of custom keybindings
if [ "$EXISTING" = "@as []" ] || [ "$EXISTING" = "[]" ]; then
    NEW_LIST="['$KEYBINDING_PATH']"
else
    # Remove trailing ] and add new entry
    NEW_LIST="${EXISTING%]*}, '$KEYBINDING_PATH']"
fi

gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_LIST"

# Configure the keybinding
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEYBINDING_PATH name 'Whisper Dictation'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEYBINDING_PATH command "$TOGGLE_SCRIPT"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEYBINDING_PATH binding "$SHORTCUT"

echo ""
echo "Done! Whisper dictation is now bound to $SHORTCUT"
echo ""
echo "Usage:"
echo "  Press $SHORTCUT to start recording"
echo "  Press $SHORTCUT again to stop and transcribe"
