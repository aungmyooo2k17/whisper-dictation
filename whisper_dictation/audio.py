"""
Audio recording abstraction for PulseAudio and PipeWire.
"""

import shutil
import subprocess
from pathlib import Path


def detect_audio_backend() -> str:
    """Detect the available audio backend.

    Checks for PipeWire first (preferred), then PulseAudio.

    Returns:
        'pipewire' or 'pulseaudio'.
    """
    # Check if PipeWire is running
    if shutil.which("pw-cli"):
        try:
            result = subprocess.run(
                ["pw-cli", "info", "0"],
                capture_output=True, timeout=3
            )
            if result.returncode == 0:
                return "pipewire"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if shutil.which("pactl"):
        return "pulseaudio"

    # Fallback — parecord is usually available
    return "pulseaudio"


def record_audio(output_file: Path, backend: str = "auto") -> subprocess.Popen:
    """Start recording audio to a WAV file.

    Args:
        output_file: Path for the output WAV file.
        backend: 'auto', 'pipewire', or 'pulseaudio'.

    Returns:
        Popen process handle for the recording.
    """
    if backend == "auto":
        backend = detect_audio_backend()

    if backend == "pipewire":
        cmd = [
            "pw-record",
            "--format=s16",
            "--rate=16000",
            "--channels=1",
            str(output_file),
        ]
    else:
        cmd = [
            "parecord",
            "--file-format=wav",
            "--rate=16000",
            "--channels=1",
            str(output_file),
        ]

    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def is_mic_muted(backend: str = "auto") -> bool:
    """Check if the default microphone is muted.

    Args:
        backend: 'auto', 'pipewire', or 'pulseaudio'.

    Returns:
        True if muted, False otherwise.
    """
    if backend == "auto":
        backend = detect_audio_backend()

    try:
        if backend == "pipewire":
            result = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"],
                capture_output=True, text=True, timeout=5,
            )
            return "[MUTED]" in result.stdout
        else:
            result = subprocess.run(
                ["pactl", "get-source-mute", "@DEFAULT_SOURCE@"],
                capture_output=True, text=True, timeout=5,
            )
            return "yes" in result.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
