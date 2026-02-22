"""
Per-application configuration profiles.
Detects the focused window and applies matching overrides.
"""

import json
import os
import re
import subprocess


def get_focused_window_class() -> str:
    """Get the WM_CLASS of the currently focused window.

    Supports X11 (xdotool+xprop) and Wayland (swaymsg, gdbus for GNOME).

    Returns:
        Window class string, or empty string if detection fails.
    """
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return _get_wayland_window_class()
    return _get_x11_window_class()


def _get_x11_window_class() -> str:
    """Get focused window class on X11."""
    try:
        # Get focused window ID
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return ""
        window_id = result.stdout.strip()

        # Get WM_CLASS via xprop
        result = subprocess.run(
            ["xprop", "-id", window_id, "WM_CLASS"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return ""

        # Parse: WM_CLASS(STRING) = "instance", "class"
        match = re.search(r'"([^"]*)",\s*"([^"]*)"', result.stdout)
        if match:
            return match.group(2)  # Return the class name
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_wayland_window_class() -> str:
    """Get focused window class on Wayland."""
    # Try swaymsg (sway/i3-compatible compositors)
    wclass = _try_swaymsg()
    if wclass:
        return wclass

    # Try gdbus for GNOME Shell
    wclass = _try_gnome_gdbus()
    if wclass:
        return wclass

    return ""


def _try_swaymsg() -> str:
    """Try getting focused window via swaymsg."""
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return ""

        tree = json.loads(result.stdout)
        focused = _find_focused_node(tree)
        if focused:
            return focused.get("app_id", "") or focused.get("window_properties", {}).get("class", "")
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return ""


def _find_focused_node(node: dict) -> dict:
    """Recursively find the focused node in a sway tree."""
    if node.get("focused"):
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        result = _find_focused_node(child)
        if result:
            return result
    return {}


def _try_gnome_gdbus() -> str:
    """Try getting focused window via GNOME Shell eval."""
    try:
        result = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell",
                "--object-path", "/org/gnome/Shell",
                "--method", "org.gnome.Shell.Eval",
                "global.display.focus_window ? global.display.focus_window.get_wm_class() : ''",
            ],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return ""

        # Parse gdbus output: (true, 'ClassName')
        match = re.search(r"'([^']*)'", result.stdout)
        if match:
            return match.group(1)
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_profile_overrides(config, window_class: str) -> dict:
    """Match window class against profile rules and return overrides.

    Args:
        config: Config dataclass instance.
        window_class: The focused window's WM_CLASS.

    Returns:
        Dict of override values (e.g. {'typing_method': 'clipboard', 'auto_capitalize': False}).
        Empty dict if no match.
    """
    if not config.profiles.enabled or not window_class:
        return {}

    for rule in config.profiles.rules:
        pattern = rule.window_class
        if not pattern:
            continue

        try:
            if re.search(pattern, window_class, re.IGNORECASE):
                overrides = {}
                if rule.typing_method is not None:
                    overrides["typing_method"] = rule.typing_method
                if rule.auto_capitalize is not None:
                    overrides["auto_capitalize"] = rule.auto_capitalize
                return overrides
        except re.error:
            continue

    return {}
