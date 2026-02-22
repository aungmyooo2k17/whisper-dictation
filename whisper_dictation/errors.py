"""
Validation and error messaging for whisper-dictation.
Checks environment, model names, and tool availability.
"""

import shutil
import subprocess
from difflib import get_close_matches

VALID_MODELS = [
    "tiny", "tiny.en",
    "base", "base.en",
    "small", "small.en",
    "medium", "medium.en",
    "large-v1", "large-v2", "large-v3",
    "distil-large-v2", "distil-large-v3",
    "distil-medium.en", "distil-small.en",
]


def validate_model_name(name: str) -> tuple:
    """Validate a Whisper model name.

    Returns:
        (is_valid, message) tuple.
    """
    if name in VALID_MODELS:
        return True, ""

    # Check for close matches
    matches = get_close_matches(name, VALID_MODELS, n=3, cutoff=0.5)
    if matches:
        suggestions = ", ".join(matches)
        return False, f"Unknown model '{name}'. Did you mean: {suggestions}?"
    return False, f"Unknown model '{name}'. Available: {', '.join(VALID_MODELS)}"


def check_typing_tool(method: str, is_wayland: bool) -> tuple:
    """Check if the required typing tool is available.

    Returns:
        (is_ok, message) tuple.
    """
    if method == "clipboard":
        if is_wayland:
            tools = ["wl-copy", "xclip", "xsel"]
        else:
            tools = ["xclip", "xsel"]
        for tool in tools:
            if shutil.which(tool):
                return True, ""
        return False, f"Clipboard mode requires one of: {', '.join(tools)}"

    if method == "auto" or method == "ydotool":
        if is_wayland:
            if shutil.which("ydotool"):
                return True, ""
            if method == "ydotool":
                return False, "ydotool not found. Install it for Wayland typing support."
            # Auto mode on Wayland: warn but don't fail
            if shutil.which("xdotool"):
                return True, "Warning: Wayland detected but only xdotool found. ydotool recommended."
            return False, "No typing tool found. Install ydotool (Wayland) or xdotool (X11)."

    if method == "auto" or method == "xdotool":
        if shutil.which("xdotool"):
            return True, ""
        if method == "xdotool":
            return False, "xdotool not found. Install it: sudo apt install xdotool"
        if shutil.which("ydotool"):
            return True, ""
        return False, "No typing tool found. Install xdotool or ydotool."

    return True, ""


def check_audio_backend(backend: str) -> tuple:
    """Check if the audio recording backend is available.

    Returns:
        (is_ok, message) tuple.
    """
    if backend == "pipewire":
        if shutil.which("pw-record"):
            return True, ""
        return False, "PipeWire backend requested but pw-record not found."

    if backend == "pulseaudio":
        if shutil.which("parecord"):
            return True, ""
        return False, "PulseAudio backend requested but parecord not found."

    # auto mode
    if shutil.which("pw-record") or shutil.which("parecord"):
        return True, ""
    return False, "No audio recording tool found. Install PipeWire or PulseAudio."


def check_cuda_available(device: str) -> tuple:
    """Check CUDA availability when CUDA device is requested.

    Returns:
        (is_ok, message) tuple.
    """
    if device != "cuda":
        return True, ""

    try:
        import torch
        if torch.cuda.is_available():
            return True, ""
        return False, "CUDA device requested but no GPU detected. Use --device cpu or auto."
    except ImportError:
        return False, "CUDA device requested but torch not installed. Install with: pip install torch"


def validate_environment(config) -> list:
    """Run all environment checks against the config.

    Args:
        config: Config dataclass instance.

    Returns:
        List of warning/error message strings. Empty if all OK.
    """
    import os
    messages = []

    # Model name
    valid, msg = validate_model_name(config.model.name)
    if not valid:
        messages.append(f"Error: {msg}")

    # CUDA
    valid, msg = check_cuda_available(config.model.device)
    if not valid:
        messages.append(f"Error: {msg}")

    # Audio backend
    valid, msg = check_audio_backend(config.audio.backend)
    if not valid:
        messages.append(f"Error: {msg}")

    # Typing tool
    wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland"
    valid, msg = check_typing_tool(config.typing.method, wayland)
    if not valid:
        messages.append(f"Error: {msg}")
    elif msg:
        messages.append(msg)

    return messages
