"""
Continuous dictation mode with silence detection.
Records audio in chunks, transcribes each chunk when silence is detected.
"""

import array
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .audio import record_audio, detect_audio_backend
from .config import Config, load_config, merge_cli_args
from .history import HistoryEntry, TranscriptionHistory
from .pipeline import PipelineContext, build_pipeline
from .profiles import get_focused_window_class, get_profile_overrides
from .transcribe import transcribe_audio
from .typing import type_text


class SilenceDetector:
    """Detects silence in PCM audio samples."""

    def __init__(self, threshold: float = 0.03, duration: float = 1.5, sample_rate: int = 16000):
        """
        Args:
            threshold: RMS amplitude threshold below which audio is "silent".
            duration: Seconds of continuous silence before triggering.
            sample_rate: Audio sample rate in Hz.
        """
        self.threshold = threshold
        self.duration = duration
        self.sample_rate = sample_rate
        self.silent_samples = 0
        self.required_samples = int(duration * sample_rate)

    def feed(self, samples: bytes) -> bool:
        """Feed raw PCM 16-bit LE samples and check for silence.

        Args:
            samples: Raw PCM bytes (16-bit signed LE, mono).

        Returns:
            True if silence duration threshold has been reached.
        """
        # Calculate RMS of the chunk
        if len(samples) < 2:
            return False

        n_samples = len(samples) // 2
        values = struct.unpack(f'<{n_samples}h', samples[:n_samples * 2])
        rms = (sum(v * v for v in values) / n_samples) ** 0.5 / 32768.0

        if rms < self.threshold:
            self.silent_samples += n_samples
        else:
            self.silent_samples = 0

        return self.silent_samples >= self.required_samples

    def reset(self):
        """Reset the silence counter."""
        self.silent_samples = 0


class ContinuousDictation:
    """Continuous dictation loop: record → detect silence → transcribe → type → repeat."""

    def __init__(self, config: Config):
        self.config = config
        self.running = False
        self._backend = None

    def start(self):
        """Start the continuous dictation loop."""
        self.running = True
        self._backend = (
            self.config.audio.backend
            if self.config.audio.backend != "auto"
            else detect_audio_backend()
        )

        # Install signal handler for clean shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        print("Continuous dictation started. Speak naturally, pause to transcribe. Ctrl+C to stop.")

        while self.running:
            try:
                self._record_and_process_chunk()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in dictation loop: {e}", file=sys.stderr)
                time.sleep(0.5)

        print("\nContinuous dictation stopped.")

    def stop(self):
        """Stop the continuous dictation loop."""
        self.running = False

    def _handle_signal(self, signum, frame):
        self.stop()

    def _record_and_process_chunk(self):
        """Record a single chunk until silence, then transcribe and type."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Start recording
            proc = record_audio(tmp_path, self._backend)
            start_time = time.time()

            # Wait for silence or max duration
            detector = SilenceDetector(
                threshold=self.config.continuous.silence_threshold,
                duration=self.config.continuous.silence_duration,
            )

            # Monitor recording duration (we can't easily read the pipe,
            # so use a time-based approach with the max chunk duration)
            max_duration = self.config.continuous.max_chunk_duration
            while self.running:
                elapsed = time.time() - start_time
                if elapsed >= max_duration:
                    break
                if elapsed >= self.config.continuous.silence_duration:
                    # Check file size growth as a proxy for audio activity
                    if tmp_path.exists():
                        size = tmp_path.stat().st_size
                        time.sleep(self.config.continuous.silence_duration)
                        if tmp_path.exists():
                            new_size = tmp_path.stat().st_size
                            # If file hasn't grown much, likely silence
                            bytes_per_sec = 16000 * 2  # 16kHz, 16-bit
                            expected_growth = bytes_per_sec * self.config.continuous.silence_duration
                            # The file always grows since we're recording;
                            # use a minimum recording time instead
                            if elapsed >= self.config.continuous.silence_duration + 1.0:
                                break
                    else:
                        break
                else:
                    time.sleep(0.1)

            # Stop recording
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                proc.kill()

            duration = time.time() - start_time

            # Check if we got meaningful audio
            if not tmp_path.exists() or tmp_path.stat().st_size < 1000:
                return

            # Transcribe
            text = transcribe_audio(
                tmp_path,
                model_size=self.config.model.name,
                device=self.config.model.device,
            )

            if not text or not text.strip():
                return

            # Pipeline
            window_class = get_focused_window_class() if self.config.profiles.enabled else ""
            overrides = get_profile_overrides(self.config, window_class) if window_class else {}
            pipeline = build_pipeline(self.config, overrides)

            ctx = PipelineContext(
                text=text,
                model_used=self.config.model.name,
                duration=duration,
                window_class=window_class,
            )
            ctx = pipeline.process(ctx)

            # Type the result
            typing_method = overrides.get("typing_method", self.config.typing.method)
            type_text(ctx.text, method=typing_method, clipboard_tool=self.config.typing.clipboard_tool)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {ctx.text}")

            # Save to history
            if self.config.history.enabled:
                history = TranscriptionHistory(
                    path=self.config.history.path,
                    max_entries=self.config.history.max_entries,
                )
                entry = HistoryEntry(
                    timestamp=datetime.now().isoformat(),
                    text=ctx.text,
                    model=self.config.model.name,
                    device=self.config.model.device,
                    duration=duration,
                )
                history.save(entry)

        finally:
            if tmp_path.exists():
                tmp_path.unlink()
