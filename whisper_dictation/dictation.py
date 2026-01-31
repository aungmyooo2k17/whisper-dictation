#!/usr/bin/env python3
"""
Whisper-based dictation for Linux using faster-whisper.
Records audio, transcribes with Whisper, types result with xdotool.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Cookie file to track running state
COOKIE_FILE = Path("/tmp/whisper-dictation.cookie")
AUDIO_FILE = Path("/tmp/whisper-dictation-audio.wav")


def record_audio(output_file: Path):
    """Record audio using parec until stopped."""
    cmd = [
        "parecord",
        "--file-format=wav",
        "--rate=16000",
        "--channels=1",
        str(output_file)
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def transcribe_audio(audio_file: Path, model_size: str = "base.en", device: str = "auto"):
    """Transcribe audio file using faster-whisper."""
    from faster_whisper import WhisperModel

    # Determine device and compute type
    if device == "auto":
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
            else:
                device = "cpu"
                compute_type = "int8"
        except ImportError:
            device = "cpu"
            compute_type = "int8"
    elif device == "cuda":
        compute_type = "float16"
    else:
        compute_type = "int8"

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(str(audio_file), beam_size=5)

    # Collect all text
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)

    return " ".join(text_parts).strip()


def type_text(text: str):
    """Type text using xdotool."""
    if not text:
        return
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--", text], check=True)


def begin(model_size: str = "base.en"):
    """Start recording."""
    if COOKIE_FILE.exists():
        print("Dictation already running", file=sys.stderr)
        sys.exit(1)

    # Remove old audio file
    if AUDIO_FILE.exists():
        AUDIO_FILE.unlink()

    # Start recording
    proc = record_audio(AUDIO_FILE)

    # Save PID to cookie file
    COOKIE_FILE.write_text(f"{proc.pid}\n{model_size}")

    print(f"Recording started (PID: {proc.pid})")


def end(device: str = "auto"):
    """Stop recording and transcribe."""
    if not COOKIE_FILE.exists():
        print("Dictation not running", file=sys.stderr)
        sys.exit(1)

    # Read PID and model from cookie
    content = COOKIE_FILE.read_text().strip().split("\n")
    pid = int(content[0])
    model_size = content[1] if len(content) > 1 else "base.en"

    # Stop recording
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.2)  # Give it time to flush
    except ProcessLookupError:
        pass

    COOKIE_FILE.unlink()

    # Check if audio file exists and has content
    if not AUDIO_FILE.exists() or AUDIO_FILE.stat().st_size < 1000:
        print("No audio recorded", file=sys.stderr)
        return

    print("Transcribing...")

    # Transcribe
    try:
        text = transcribe_audio(AUDIO_FILE, model_size, device)
        print(f"Transcribed: {text}")

        if text:
            type_text(text)
    except Exception as e:
        print(f"Transcription error: {e}", file=sys.stderr)
    finally:
        # Cleanup
        if AUDIO_FILE.exists():
            AUDIO_FILE.unlink()


def cancel():
    """Cancel recording without transcribing."""
    if not COOKIE_FILE.exists():
        print("Dictation not running", file=sys.stderr)
        return

    # Read PID from cookie
    content = COOKIE_FILE.read_text().strip().split("\n")
    pid = int(content[0])

    # Stop recording
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    COOKIE_FILE.unlink()

    # Cleanup audio
    if AUDIO_FILE.exists():
        AUDIO_FILE.unlink()

    print("Dictation cancelled")


def main():
    parser = argparse.ArgumentParser(
        description="Whisper-based speech-to-text dictation for Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  whisper-dictation begin                  # Start recording
  whisper-dictation begin --model small.en # Start with specific model
  whisper-dictation end                    # Stop and transcribe
  whisper-dictation cancel                 # Cancel without transcribing

Available models: tiny.en, base.en, small.en, medium.en, large-v3
        """
    )
    parser.add_argument("command", choices=["begin", "end", "cancel"],
                        help="Command to execute")
    parser.add_argument("--model", default="base.en",
                        help="Whisper model size (default: base.en)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"],
                        help="Device to use for inference (default: auto)")

    args = parser.parse_args()

    if args.command == "begin":
        begin(args.model)
    elif args.command == "end":
        end(args.device)
    elif args.command == "cancel":
        cancel()


if __name__ == "__main__":
    main()
