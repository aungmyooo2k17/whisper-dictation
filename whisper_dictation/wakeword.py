"""
Wake word listener using openwakeword.
Say the wake word to start recording, say it again to stop and transcribe.

Flow: listen → wake word → record → wake word again → transcribe → type → listen
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .config import Config


class WakeWordListener:
    """Listens for a wake word to toggle dictation."""

    def __init__(self, config: Config):
        self.config = config
        self.running = False
        self.phrase = config.wakeword.phrase
        self.sensitivity = config.wakeword.sensitivity

    def start(self):
        """Start the wake word listener loop."""
        try:
            import numpy as np
            import pyaudio
            from openwakeword.model import Model as OWWModel
        except ImportError as e:
            print(
                f"Missing dependency: {e}\n"
                "Install wake word support: pip install 'whisper-dictation[wakeword]'",
                file=sys.stderr,
            )
            sys.exit(1)

        from .audio import record_audio, detect_audio_backend
        from .history import HistoryEntry, TranscriptionHistory
        from .pipeline import PipelineContext, build_pipeline
        from .profiles import get_focused_window_class, get_profile_overrides
        from .transcribe import transcribe_audio
        from .typing import type_text

        self.running = True
        self._recording = False
        self._rec_proc = None
        self._audio_path = None
        self._rec_start = None
        self._indicator_proc = None

        backend = (
            self.config.audio.backend
            if self.config.audio.backend != "auto"
            else detect_audio_backend()
        )

        oww_model = OWWModel()

        available = list(oww_model.models.keys())
        if self.phrase not in available:
            print(f"Wake word '{self.phrase}' not found.", file=sys.stderr)
            print(f"Available: {', '.join(available)}", file=sys.stderr)
            sys.exit(1)

        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=16000,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=1280,
        )

        signal.signal(signal.SIGINT, lambda s, f: self.stop())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop())

        print(f'Say "{self.phrase}" to start recording, say it again to stop. Ctrl+C to quit.')

        try:
            while self.running:
                audio_data = stream.read(1280, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)

                prediction = oww_model.predict(audio_array)
                score = prediction.get(self.phrase, 0.0)

                if score > self.sensitivity:
                    oww_model.reset()

                    if not self._recording:
                        # --- START recording ---
                        print(f'\n"{self.phrase}" → Recording started. Speak now.')
                        self._start_recording(backend, record_audio)
                    else:
                        # --- STOP recording, transcribe, type ---
                        print(f'"{self.phrase}" → Stopping...')
                        self._stop_and_transcribe(
                            transcribe_audio, build_pipeline, type_text,
                            get_focused_window_class, get_profile_overrides,
                            TranscriptionHistory, HistoryEntry, PipelineContext,
                        )
                        print(f'\nSay "{self.phrase}" to record again.')

                    # Drain 2 seconds of audio to avoid re-triggering
                    oww_model.reset()
                    for _ in range(25):
                        try:
                            stream.read(1280, exception_on_overflow=False)
                        except OSError:
                            break
                        time.sleep(0.08)
                    oww_model.reset()

        except KeyboardInterrupt:
            pass
        finally:
            # Clean up if still recording
            if self._recording:
                self._cancel_recording()
            self.running = False
            stream.stop_stream()
            stream.close()
            pa.terminate()
            print("\nWake word listener stopped.")

    def stop(self):
        self.running = False

    def _start_recording(self, backend, record_audio):
        """Begin recording audio to a temp file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._audio_path = Path(tmp.name)
        tmp.close()

        self._indicator_proc = self._launch_indicator()
        self._rec_proc = record_audio(self._audio_path, backend)
        self._rec_start = time.time()
        self._recording = True

    def _stop_and_transcribe(
        self, transcribe_audio, build_pipeline, type_text,
        get_focused_window_class, get_profile_overrides,
        TranscriptionHistory, HistoryEntry, PipelineContext,
    ):
        """Stop recording, transcribe, run pipeline, type result."""
        self._recording = False
        duration = time.time() - self._rec_start

        # Stop recorder
        if self._rec_proc:
            try:
                self._rec_proc.terminate()
                self._rec_proc.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    self._rec_proc.kill()
                except ProcessLookupError:
                    pass
            self._rec_proc = None

        # Switch indicator to processing
        if self._indicator_proc:
            try:
                os.kill(self._indicator_proc.pid, signal.SIGUSR1)
            except (ProcessLookupError, OSError):
                pass

        audio_path = self._audio_path
        self._audio_path = None

        try:
            if not audio_path or not audio_path.exists() or audio_path.stat().st_size < 1000:
                print("No audio captured.")
                return

            print(f"Transcribing ({duration:.1f}s)...")
            text = transcribe_audio(
                audio_path,
                model_size=self.config.model.name,
                device=self.config.model.device,
            )

            if not text or not text.strip():
                print("(empty transcription)")
                return

            # Pipeline
            window_class = ""
            overrides = {}
            if self.config.profiles.enabled:
                window_class = get_focused_window_class()
                overrides = get_profile_overrides(self.config, window_class)

            pipeline = build_pipeline(self.config, overrides)
            ctx = PipelineContext(
                text=text,
                model_used=self.config.model.name,
                duration=duration,
                window_class=window_class,
            )
            ctx = pipeline.process(ctx)

            # Type at cursor
            typing_method = overrides.get("typing_method", self.config.typing.method)
            type_text(
                ctx.text,
                method=typing_method,
                clipboard_tool=self.config.typing.clipboard_tool,
            )
            print(f"Typed: {ctx.text}")

            # History
            if self.config.history.enabled:
                history = TranscriptionHistory(
                    path=self.config.history.path,
                    max_entries=self.config.history.max_entries,
                )
                history.save(HistoryEntry(
                    timestamp=datetime.now().isoformat(),
                    text=ctx.text,
                    model=self.config.model.name,
                    device=self.config.model.device,
                    duration=duration,
                ))

        finally:
            if audio_path and audio_path.exists():
                audio_path.unlink()
            self._kill_indicator()

    def _cancel_recording(self):
        """Cancel an in-progress recording without transcribing."""
        self._recording = False
        if self._rec_proc:
            try:
                self._rec_proc.terminate()
            except ProcessLookupError:
                pass
            self._rec_proc = None
        if self._audio_path and self._audio_path.exists():
            self._audio_path.unlink()
        self._audio_path = None
        self._kill_indicator()

    def _launch_indicator(self):
        """Start the floating indicator."""
        try:
            return subprocess.Popen(
                ["/usr/bin/python3", os.path.expanduser("~/.local/bin/dictation-indicator")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return None

    def _kill_indicator(self):
        """Kill any running indicator."""
        try:
            subprocess.run(
                ["pkill", "-f", "dictation-indicator"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass
        self._indicator_proc = None
