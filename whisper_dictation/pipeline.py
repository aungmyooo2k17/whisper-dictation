"""
Post-processing pipeline framework for transcribed text.
Steps are applied in order: voice commands → capitalize → custom replacements → LLM cleanup.
"""

import json
import re
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineContext:
    """Context passed through pipeline steps."""
    text: str
    original_text: str = ""
    model_used: str = ""
    duration: float = 0.0
    window_class: str = ""

    def __post_init__(self):
        if not self.original_text:
            self.original_text = self.text


class PipelineStep(ABC):
    """Abstract base class for pipeline steps."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable step name."""
        ...

    @abstractmethod
    def process(self, ctx: PipelineContext) -> PipelineContext:
        """Process the context and return it (possibly modified)."""
        ...


class VoiceCommandStep(PipelineStep):
    """Apply spoken punctuation and voice commands."""

    def __init__(self, custom_commands: list = None):
        self.custom_commands = custom_commands or []

    @property
    def name(self) -> str:
        return "Voice Commands"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        from .voice_commands import apply_voice_commands
        ctx.text = apply_voice_commands(ctx.text, self.custom_commands)
        return ctx


class AutoCapitalizeStep(PipelineStep):
    """Capitalize first character and after sentence enders."""

    @property
    def name(self) -> str:
        return "Auto Capitalize"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        text = ctx.text
        if not text:
            return ctx

        # Capitalize first character
        text = text[0].upper() + text[1:]

        # Capitalize after sentence enders (. ! ?)
        text = re.sub(
            r'([.!?]\s+)([a-z])',
            lambda m: m.group(1) + m.group(2).upper(),
            text,
        )

        # Capitalize after newlines
        text = re.sub(
            r'(\n\s*)([a-z])',
            lambda m: m.group(1) + m.group(2).upper(),
            text,
        )

        ctx.text = text
        return ctx


class CustomReplacementStep(PipelineStep):
    """Apply user-defined regex replacements."""

    def __init__(self, replacements: list):
        """
        Args:
            replacements: List of {"pattern": str, "replacement": str} dicts.
        """
        self.replacements = replacements

    @property
    def name(self) -> str:
        return "Custom Replacements"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        for rule in self.replacements:
            pattern = rule.get("pattern", "")
            replacement = rule.get("replacement", "")
            if pattern:
                try:
                    ctx.text = re.sub(pattern, replacement, ctx.text)
                except re.error:
                    continue
        return ctx


class LLMCleanupStep(PipelineStep):
    """Optional text cleanup via local Ollama API."""

    def __init__(self, endpoint: str, model: str, prompt: str):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.prompt = prompt

    @property
    def name(self) -> str:
        return "LLM Cleanup"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        if not self.model:
            return ctx

        try:
            url = f"{self.endpoint}/api/generate"
            payload = json.dumps({
                "model": self.model,
                "prompt": f"{self.prompt}\n\n{ctx.text}",
                "stream": False,
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                cleaned = result.get("response", "").strip()
                if cleaned:
                    ctx.text = cleaned
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            # Silently fall back to original text on any error
            pass

        return ctx


class Pipeline:
    """Ordered list of processing steps."""

    def __init__(self, steps: list = None):
        self.steps = steps or []

    def process(self, ctx: PipelineContext) -> PipelineContext:
        """Run all steps in order."""
        for step in self.steps:
            ctx = step.process(ctx)
        return ctx


def build_pipeline(config, profile_overrides: dict = None) -> Pipeline:
    """Build a pipeline from config and optional profile overrides.

    Args:
        config: Config dataclass instance.
        profile_overrides: Optional dict of per-app overrides.

    Returns:
        Configured Pipeline instance.
    """
    overrides = profile_overrides or {}
    steps = []

    # Voice commands
    voice_enabled = overrides.get(
        "voice_commands",
        config.pipeline.voice_commands and config.voice_commands.enabled,
    )
    if voice_enabled:
        steps.append(VoiceCommandStep(config.voice_commands.custom))

    # Auto capitalize
    auto_cap = overrides.get("auto_capitalize", config.pipeline.auto_capitalize)
    if auto_cap:
        steps.append(AutoCapitalizeStep())

    # Custom replacements
    if config.pipeline.custom_replacements:
        steps.append(CustomReplacementStep(config.pipeline.custom_replacements))

    # LLM cleanup (optional)
    if config.pipeline.llm.enabled:
        steps.append(LLMCleanupStep(
            endpoint=config.pipeline.llm.endpoint,
            model=config.pipeline.llm.model,
            prompt=config.pipeline.llm.prompt,
        ))

    return Pipeline(steps)
