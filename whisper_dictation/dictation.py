#!/usr/bin/env python3
"""
Whisper-based dictation for Linux using faster-whisper.
Records audio, transcribes with Whisper, types result into any application.
"""

import argparse
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from .audio import record_audio, is_mic_muted, detect_audio_backend
from .config import (
    Config, load_config, merge_cli_args, generate_default_config,
    CONFIG_DIR, DEFAULT_CONFIG_PATH,
)
from .errors import validate_environment, validate_model_name
from .history import HistoryEntry, TranscriptionHistory
from .pipeline import PipelineContext, build_pipeline
from .profiles import get_focused_window_class, get_profile_overrides
from .transcribe import transcribe_audio
from .typing import type_text

# Cookie file to track running state
COOKIE_FILE = Path("/tmp/whisper-dictation.cookie")
AUDIO_FILE = Path("/tmp/whisper-dictation-audio.wav")


def notify(message: str, urgency: str = "normal"):
    """Show a desktop notification."""
    import subprocess
    try:
        subprocess.run(
            ["notify-send", "--urgency", urgency, "Whisper Dictation", message],
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def begin(config: Config):
    """Start recording."""
    if COOKIE_FILE.exists():
        print("Dictation already running", file=sys.stderr)
        sys.exit(1)

    # Validate environment
    messages = validate_environment(config)
    errors = [m for m in messages if m.startswith("Error:")]
    warnings = [m for m in messages if not m.startswith("Error:")]

    for w in warnings:
        print(w, file=sys.stderr)

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        notify(errors[0].removeprefix("Error: "), urgency="critical")
        sys.exit(1)

    # Check if microphone is muted
    backend = config.audio.backend
    if is_mic_muted(backend):
        msg = "Microphone is muted. Please unmute and try again."
        print(f"Error: {msg}", file=sys.stderr)
        notify(msg, urgency="critical")
        sys.exit(1)

    # Remove old audio file
    if AUDIO_FILE.exists():
        AUDIO_FILE.unlink()

    # Start recording
    proc = record_audio(AUDIO_FILE, backend)

    # Save PID, model, and config path to cookie file
    COOKIE_FILE.write_text(f"{proc.pid}\n{config.model.name}\n{config.model.device}")

    print(f"Recording started (PID: {proc.pid})")


def end(config: Config):
    """Stop recording, transcribe, process, and type."""
    if not COOKIE_FILE.exists():
        print("Dictation not running", file=sys.stderr)
        sys.exit(1)

    # Read PID and model from cookie
    content = COOKIE_FILE.read_text().strip().split("\n")
    pid = int(content[0])
    model_size = content[1] if len(content) > 1 else config.model.name
    device = content[2] if len(content) > 2 else config.model.device

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
    start_time = time.time()

    try:
        text = transcribe_audio(AUDIO_FILE, model_size, device)
        duration = time.time() - start_time
        print(f"Transcribed: {text}")

        if text:
            # Get profile overrides
            window_class = ""
            overrides = {}
            if config.profiles.enabled:
                window_class = get_focused_window_class()
                overrides = get_profile_overrides(config, window_class)

            # Build and run pipeline
            pipeline = build_pipeline(config, overrides)
            ctx = PipelineContext(
                text=text,
                model_used=model_size,
                duration=duration,
                window_class=window_class,
            )
            ctx = pipeline.process(ctx)

            # Type the result
            typing_method = overrides.get("typing_method", config.typing.method)
            type_text(
                ctx.text,
                method=typing_method,
                clipboard_tool=config.typing.clipboard_tool,
            )

            # Save to history
            if config.history.enabled:
                history = TranscriptionHistory(
                    path=config.history.path,
                    max_entries=config.history.max_entries,
                )
                entry = HistoryEntry(
                    timestamp=datetime.now().isoformat(),
                    text=ctx.text,
                    model=model_size,
                    device=device,
                    duration=duration,
                )
                history.save(entry)

    except Exception as e:
        print(f"Transcription error: {e}", file=sys.stderr)
    finally:
        if AUDIO_FILE.exists():
            AUDIO_FILE.unlink()


def cancel():
    """Cancel recording without transcribing."""
    if not COOKIE_FILE.exists():
        print("Dictation not running", file=sys.stderr)
        return

    content = COOKIE_FILE.read_text().strip().split("\n")
    pid = int(content[0])

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    COOKIE_FILE.unlink()

    if AUDIO_FILE.exists():
        AUDIO_FILE.unlink()

    print("Dictation cancelled")


def cmd_history(args, config: Config):
    """Handle the 'history' subcommand."""
    history = TranscriptionHistory(
        path=config.history.path,
        max_entries=config.history.max_entries,
    )

    if args.search:
        entries = history.search(args.search)
        if not entries:
            print("No matching entries found.")
            return
        for entry in entries[:args.last]:
            print(f"[{entry.timestamp}] {entry.text}")
    else:
        entries = history.get_recent(args.last)
        if not entries:
            print("No history entries yet.")
            return
        for entry in entries:
            print(f"[{entry.timestamp}] {entry.text}")


def cmd_config(args):
    """Handle the 'config' subcommand."""
    if args.init:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if DEFAULT_CONFIG_PATH.exists():
            print(f"Config already exists: {DEFAULT_CONFIG_PATH}")
            print("Remove it first to regenerate.")
            return
        DEFAULT_CONFIG_PATH.write_text(generate_default_config())
        print(f"Config created: {DEFAULT_CONFIG_PATH}")
    elif args.show:
        config = load_config()
        if DEFAULT_CONFIG_PATH.exists():
            print(DEFAULT_CONFIG_PATH.read_text())
        else:
            print(generate_default_config())
    elif args.path:
        print(DEFAULT_CONFIG_PATH)
    else:
        print(f"Config path: {DEFAULT_CONFIG_PATH}")
        print(f"Exists: {DEFAULT_CONFIG_PATH.exists()}")


def cmd_continuous(args, config: Config):
    """Handle the 'continuous' subcommand."""
    from .continuous import ContinuousDictation

    config.continuous.enabled = True
    dictation = ContinuousDictation(config)
    dictation.start()


def cmd_listen(args, config: Config):
    """Handle the 'listen' subcommand."""
    from .wakeword import WakeWordListener

    listener = WakeWordListener(config)
    listener.start()


def main():
    parser = argparse.ArgumentParser(
        description="Whisper-based speech-to-text dictation for Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  whisper-dictation begin                    # Start recording
  whisper-dictation begin --model small.en   # Start with specific model
  whisper-dictation end                      # Stop and transcribe
  whisper-dictation cancel                   # Cancel without transcribing
  whisper-dictation continuous               # Continuous dictation mode
  whisper-dictation listen                   # Wake word listener
  whisper-dictation history --last 5         # Show recent transcriptions
  whisper-dictation config --init            # Create default config file

Available models: tiny.en, base.en, small.en, medium.en, large-v3
""",
    )

    # Global flags
    parser.add_argument("--config", dest="config_path", default=None,
                        help="Path to config file")
    parser.add_argument("--typing-method", default=None,
                        choices=["xdotool", "ydotool", "clipboard"],
                        help="Override typing method")
    parser.add_argument("--no-pipeline", action="store_true", default=False,
                        help="Skip post-processing pipeline")

    subparsers = parser.add_subparsers(dest="command")

    # begin
    begin_parser = subparsers.add_parser("begin", help="Start recording")
    begin_parser.add_argument("--model", default=None,
                              help="Whisper model size (default: base.en)")

    # end
    end_parser = subparsers.add_parser("end", help="Stop recording and transcribe")
    end_parser.add_argument("--device", default=None, choices=["auto", "cuda", "cpu"],
                            help="Device for inference (default: auto)")

    # cancel
    subparsers.add_parser("cancel", help="Cancel recording")

    # continuous
    cont_parser = subparsers.add_parser("continuous", help="Continuous dictation mode")
    cont_parser.add_argument("--model", default=None,
                             help="Whisper model size")
    cont_parser.add_argument("--device", default=None, choices=["auto", "cuda", "cpu"],
                             help="Device for inference")

    # listen
    subparsers.add_parser("listen", help="Wake word listener")

    # history
    hist_parser = subparsers.add_parser("history", help="View transcription history")
    hist_parser.add_argument("--last", type=int, default=10,
                             help="Number of recent entries (default: 10)")
    hist_parser.add_argument("--search", default=None,
                             help="Search history text")

    # config
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_group = config_parser.add_mutually_exclusive_group()
    config_group.add_argument("--init", action="store_true",
                              help="Create default config file")
    config_group.add_argument("--show", action="store_true",
                              help="Show current configuration")
    config_group.add_argument("--path", action="store_true",
                              help="Print config file path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Handle config command early (doesn't need full config loading)
    if args.command == "config":
        cmd_config(args)
        return

    # Load config
    config = load_config(args.config_path)
    config = merge_cli_args(config, args)

    # Dispatch commands
    if args.command == "begin":
        begin(config)
    elif args.command == "end":
        end(config)
    elif args.command == "cancel":
        cancel()
    elif args.command == "continuous":
        cmd_continuous(args, config)
    elif args.command == "listen":
        cmd_listen(args, config)
    elif args.command == "history":
        cmd_history(args, config)


if __name__ == "__main__":
    main()
