# Whisper Dictation

<p align="center">
  <img src="https://img.shields.io/badge/platform-Linux-blue" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
</p>

**Speech-to-text dictation for Linux** using [OpenAI Whisper](https://github.com/openai/whisper) via [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

Press a keyboard shortcut to start recording, press again to transcribe and type the text at your cursor. Works in any application.

## Features

- **Offline** - Runs completely locally, no internet required
- **Fast** - Uses faster-whisper (CTranslate2) for 4x faster inference
- **Accurate** - Powered by OpenAI Whisper models
- **Visual feedback** - Animated indicator shows recording/processing state
- **GPU support** - CUDA acceleration for faster transcription
- **Simple** - One shortcut to toggle recording

## Demo

| Recording | Processing | Done |
|-----------|------------|------|
| Sound wave animation near cursor | Loading spinner | Text typed at cursor |

## Installation

### Prerequisites

Install system dependencies:

```bash
# Ubuntu/Debian
sudo apt install python3-pip python3-venv pulseaudio-utils xdotool python3-gi gir1.2-gtk-3.0

# Fedora
sudo dnf install python3-pip pulseaudio-utils xdotool python3-gobject gtk3

# Arch
sudo pacman -S python-pip pulseaudio xdotool python-gobject gtk3
```

### Option 1: Install with pip (Recommended)

```bash
pip install whisper-dictation
```

For GPU acceleration (NVIDIA):

```bash
pip install whisper-dictation[gpu]
```

Then copy the toggle script and set up the shortcut:

```bash
# Download toggle script
curl -o ~/.local/bin/whisper-dictation-toggle https://raw.githubusercontent.com/aungmyooo2k17/whisper-dictation/main/scripts/whisper-dictation-toggle
chmod +x ~/.local/bin/whisper-dictation-toggle

# Set up keyboard shortcut (GNOME)
curl -s https://raw.githubusercontent.com/aungmyooo2k17/whisper-dictation/main/scripts/setup-shortcut.sh | bash
```

### Option 2: Install from source

```bash
git clone https://github.com/aungmyooo2k17/whisper-dictation.git
cd whisper-dictation
./install.sh
./scripts/setup-shortcut.sh
```

### Option 3: Manual installation

```bash
git clone https://github.com/aungmyooo2k17/whisper-dictation.git
cd whisper-dictation
pip install -e .

# Copy toggle script
cp scripts/whisper-dictation-toggle ~/.local/bin/
chmod +x ~/.local/bin/whisper-dictation-toggle

# Set up shortcut manually in Settings → Keyboard → Custom Shortcuts
# Command: ~/.local/bin/whisper-dictation-toggle
# Shortcut: Ctrl+Shift+Space
```

## Usage

| Action | Shortcut |
|--------|----------|
| Start/Stop dictation | `Ctrl+Shift+Space` |

1. Press `Ctrl+Shift+Space` - Recording starts, sound wave indicator appears
2. Speak your text
3. Press `Ctrl+Shift+Space` again - Recording stops, loading indicator shows
4. Text is typed at your cursor position

### Command Line

```bash
# Start recording
whisper-dictation begin

# Stop recording and transcribe
whisper-dictation end

# Cancel recording (no transcription)
whisper-dictation cancel

# Use a specific model
whisper-dictation begin --model medium.en
```

## Configuration

### Changing the Whisper Model

Edit `~/.local/bin/whisper-dictation-toggle` and change the `MODEL` variable:

```bash
MODEL="${WHISPER_MODEL:-base.en}"  # Change to small.en, medium.en, etc.
```

Or set an environment variable:

```bash
export WHISPER_MODEL=medium.en
```

### Available Models

| Model | Size | Speed | Accuracy | Best For |
|-------|------|-------|----------|----------|
| `tiny.en` | ~40 MB | Fastest | Lower | Quick drafts |
| `base.en` | ~140 MB | Fast | Good | **Default** - balanced |
| `small.en` | ~460 MB | Medium | Better | General use |
| `medium.en` | ~1.5 GB | Slow | High | Accuracy priority |
| `large-v3` | ~3 GB | Slowest | Highest | Best accuracy, multilingual |

### Changing the Keyboard Shortcut

```bash
# View current shortcut
gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ binding

# Change to Super+D
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ binding '<Super>d'
```

### Custom Indicator Icons

Replace the GIF files in `~/.config/whisper-dictation/icons/`:

```
~/.config/whisper-dictation/icons/
├── recording.gif    # Shown while recording
└── processing.gif   # Shown while transcribing
```

Recommended: Use small (64-128px) transparent GIFs from:
- [Pixabay GIFs](https://pixabay.com/gifs/) (royalty-free)
- [Loading.io](https://loading.io/) (customizable)

## Troubleshooting

### Indicator stuck on screen

```bash
pkill -f whisper-dictation-indicator
```

### No audio recording

```bash
# Check PulseAudio
parecord --list-sources

# Test recording
parecord --file-format=wav --rate=16000 test.wav
```

### Slow transcription

- Use a smaller model (`tiny.en` or `base.en`)
- Install GPU support: `pip install whisper-dictation[gpu]`
- First run downloads the model; subsequent runs are faster

### Text not typing

```bash
# Check xdotool
xdotool type "test"
```

Note: xdotool requires X11. For Wayland, you may need `ydotool` (not yet supported).

## How It Works

1. **Toggle script** receives keyboard shortcut
2. **parecord** captures audio from PulseAudio
3. **faster-whisper** transcribes audio using Whisper model
4. **xdotool** types the transcribed text at cursor

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

```bash
# Development setup
git clone https://github.com/aungmyooo2k17/whisper-dictation.git
cd whisper-dictation
pip install -e ".[dev]"
```

## License

[MIT License](LICENSE) - feel free to use this project however you like.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - The speech recognition model
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Fast Whisper implementation
- [Pixabay](https://pixabay.com/) - Indicator GIF icons

## Related Projects

- [nerd-dictation](https://github.com/ideasman42/nerd-dictation) - VOSK-based dictation (real-time, less accurate)
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) - C++ Whisper implementation
