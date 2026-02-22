"""
Configuration loading and dataclasses for whisper-dictation.
Supports TOML config files with CLI override merging.
"""

import os
import re
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Optional

# TOML support: tomllib in 3.11+, tomli fallback for 3.10
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

CONFIG_DIR = Path.home() / ".config" / "whisper-dictation"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.toml"


@dataclass
class ModelConfig:
    name: str = "base.en"
    device: str = "auto"


@dataclass
class AudioConfig:
    backend: str = "auto"


@dataclass
class TypingConfig:
    method: str = "auto"
    clipboard_tool: str = "auto"


@dataclass
class HistoryConfig:
    enabled: bool = True
    path: str = "~/.local/share/whisper-dictation/history.jsonl"
    max_entries: int = 10000


@dataclass
class LLMConfig:
    enabled: bool = False
    endpoint: str = "http://localhost:11434"
    model: str = ""
    prompt: str = "Clean up this dictated text, fixing grammar while preserving meaning:"


@dataclass
class PipelineConfig:
    auto_capitalize: bool = True
    voice_commands: bool = True
    custom_replacements: list = field(default_factory=list)
    llm: LLMConfig = field(default_factory=LLMConfig)


@dataclass
class VoiceCommandsConfig:
    enabled: bool = True
    custom: list = field(default_factory=list)


@dataclass
class ContinuousConfig:
    enabled: bool = False
    silence_threshold: float = 0.03
    silence_duration: float = 1.5
    max_chunk_duration: float = 30.0


@dataclass
class TrayConfig:
    enabled: bool = False
    show_notifications: bool = True


@dataclass
class WakeWordConfig:
    enabled: bool = False
    phrase: str = "alexa"
    sensitivity: float = 0.5


@dataclass
class ProfileRule:
    window_class: str = ""
    typing_method: Optional[str] = None
    auto_capitalize: Optional[bool] = None


@dataclass
class ProfilesConfig:
    enabled: bool = False
    rules: list = field(default_factory=list)


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    typing: TypingConfig = field(default_factory=TypingConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    voice_commands: VoiceCommandsConfig = field(default_factory=VoiceCommandsConfig)
    continuous: ContinuousConfig = field(default_factory=ContinuousConfig)
    tray: TrayConfig = field(default_factory=TrayConfig)
    wakeword: WakeWordConfig = field(default_factory=WakeWordConfig)
    profiles: ProfilesConfig = field(default_factory=ProfilesConfig)


def _merge_dict_into_dataclass(dc, data: dict):
    """Recursively merge a dict into a dataclass instance."""
    for key, value in data.items():
        if not hasattr(dc, key):
            continue
        current = getattr(dc, key)
        if isinstance(value, dict) and hasattr(current, '__dataclass_fields__'):
            _merge_dict_into_dataclass(current, value)
        else:
            setattr(dc, key, value)


def _parse_profile_rules(rules_list: list) -> list:
    """Parse profile rules from TOML list of dicts into ProfileRule objects."""
    result = []
    for rule_dict in rules_list:
        rule = ProfileRule()
        for key, value in rule_dict.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        result.append(rule)
    return result


def load_config(path: Optional[str] = None) -> Config:
    """Load config from TOML file, falling back to defaults.

    Args:
        path: Explicit config file path. If None, uses default location.

    Returns:
        Config dataclass with merged values.
    """
    config = Config()

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return config

    if tomllib is None:
        return config

    with open(config_path, "rb") as f:
        data = f.read()

    try:
        toml_data = tomllib.loads(data.decode("utf-8"))
    except Exception:
        return config

    # Handle nested sections
    for section_name, section_data in toml_data.items():
        if not isinstance(section_data, dict):
            continue

        if section_name == "profiles":
            if "enabled" in section_data:
                config.profiles.enabled = section_data["enabled"]
            if "rules" in section_data:
                config.profiles.rules = _parse_profile_rules(section_data["rules"])
        elif section_name == "pipeline":
            # Handle pipeline.llm nested section
            llm_data = section_data.pop("llm", None)
            _merge_dict_into_dataclass(config.pipeline, section_data)
            if llm_data:
                _merge_dict_into_dataclass(config.pipeline.llm, llm_data)
        elif hasattr(config, section_name):
            sub = getattr(config, section_name)
            if hasattr(sub, '__dataclass_fields__'):
                _merge_dict_into_dataclass(sub, section_data)

    return config


def merge_cli_args(config: Config, args) -> Config:
    """Override config values with CLI arguments.

    Args:
        config: Existing Config instance.
        args: argparse Namespace with CLI flags.

    Returns:
        Modified Config instance.
    """
    if hasattr(args, 'model') and args.model is not None:
        config.model.name = args.model
    if hasattr(args, 'device') and args.device is not None:
        config.model.device = args.device
    if hasattr(args, 'typing_method') and args.typing_method is not None:
        config.typing.method = args.typing_method
    if hasattr(args, 'no_pipeline') and args.no_pipeline:
        config.pipeline.auto_capitalize = False
        config.pipeline.voice_commands = False
        config.pipeline.llm.enabled = False
    return config


def generate_default_config() -> str:
    """Generate a default config.toml string with comments."""
    return """\
# Whisper Dictation Configuration
# Place this file at ~/.config/whisper-dictation/config.toml

[model]
name = "base.en"
device = "auto"              # auto | cuda | cpu

[audio]
backend = "auto"             # auto | pulseaudio | pipewire

[typing]
method = "auto"              # auto | xdotool | ydotool | clipboard
clipboard_tool = "auto"      # auto | xclip | xsel | wl-copy

[history]
enabled = true
path = "~/.local/share/whisper-dictation/history.jsonl"
max_entries = 10000

[pipeline]
auto_capitalize = true
voice_commands = true
custom_replacements = []

[pipeline.llm]
enabled = false
endpoint = "http://localhost:11434"   # Ollama only (local)
model = ""                            # e.g. "llama3.2"
prompt = "Clean up this dictated text, fixing grammar while preserving meaning:"

[voice_commands]
enabled = true
custom = []

[continuous]
enabled = false
silence_threshold = 0.03
silence_duration = 1.5
max_chunk_duration = 30.0

[tray]
enabled = false
show_notifications = true

[wakeword]
enabled = false
phrase = "hey alien"
sensitivity = 0.5

[profiles]
enabled = false

[[profiles.rules]]
window_class = "gnome-terminal|kitty|alacritty"
typing_method = "clipboard"
auto_capitalize = false

[[profiles.rules]]
window_class = "code|Code"
auto_capitalize = false
"""
