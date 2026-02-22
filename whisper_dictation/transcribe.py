"""
Transcription logic extracted from dictation.py.
Handles Whisper model loading and audio transcription.
"""

from pathlib import Path


def transcribe_audio(
    audio_file: Path,
    model_size: str = "base.en",
    device: str = "auto",
    compute_type: str = "auto",
) -> str:
    """Transcribe audio file using faster-whisper.

    Args:
        audio_file: Path to the WAV file.
        model_size: Whisper model name (e.g. 'base.en', 'small.en').
        device: Inference device ('auto', 'cuda', 'cpu').
        compute_type: Compute type ('auto', 'float16', 'int8').

    Returns:
        Transcribed text string.
    """
    from faster_whisper import WhisperModel

    # Resolve device and compute type
    if device == "auto":
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                if compute_type == "auto":
                    compute_type = "float16"
            else:
                device = "cpu"
                if compute_type == "auto":
                    compute_type = "int8"
        except ImportError:
            device = "cpu"
            if compute_type == "auto":
                compute_type = "int8"
    else:
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(str(audio_file), beam_size=5)

    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)

    return " ".join(text_parts).strip()
