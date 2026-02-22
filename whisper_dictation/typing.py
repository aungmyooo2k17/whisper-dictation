"""
Text typing abstraction for xdotool, ydotool, and clipboard methods.
"""

import os
import shutil
import subprocess


def is_wayland() -> bool:
    """Check if running under Wayland."""
    return os.environ.get("XDG_SESSION_TYPE") == "wayland"


def type_via_keyboard(text: str) -> None:
    """Type text using xdotool (X11) or ydotool (Wayland).

    Args:
        text: Text to type.
    """
    if is_wayland():
        subprocess.run(["ydotool", "type", "--", text], check=True)
    else:
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--", text], check=True)


def _detect_clipboard_tool(wayland: bool) -> str:
    """Detect available clipboard tool.

    Returns:
        Tool name: 'wl-copy', 'xclip', or 'xsel'.
    """
    if wayland and shutil.which("wl-copy"):
        return "wl-copy"
    if shutil.which("xclip"):
        return "xclip"
    if shutil.which("xsel"):
        return "xsel"
    if shutil.which("wl-copy"):
        return "wl-copy"
    return "xclip"  # will fail with a clear error


def type_via_clipboard(text: str, tool: str = "auto") -> None:
    """Copy text to clipboard and paste with Ctrl+V.

    Args:
        text: Text to paste.
        tool: Clipboard tool ('auto', 'xclip', 'xsel', 'wl-copy').
    """
    wayland = is_wayland()

    if tool == "auto":
        tool = _detect_clipboard_tool(wayland)

    # Copy to clipboard
    if tool == "wl-copy":
        subprocess.run(["wl-copy", "--", text], check=True)
    elif tool == "xclip":
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(input=text.encode("utf-8"))
    elif tool == "xsel":
        proc = subprocess.Popen(
            ["xsel", "--clipboard", "--input"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(input=text.encode("utf-8"))

    # Paste with Ctrl+V
    import time
    time.sleep(0.05)
    if wayland:
        subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True)
    else:
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=True)


def type_text(text: str, method: str = "auto", clipboard_tool: str = "auto") -> None:
    """Type text using the configured method.

    Args:
        text: Text to type/paste.
        method: Typing method ('auto', 'xdotool', 'ydotool', 'clipboard').
        clipboard_tool: Clipboard tool for clipboard method.
    """
    if not text:
        return

    if method == "clipboard":
        try:
            type_via_clipboard(text, clipboard_tool)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            import sys
            print(f"Clipboard typing failed ({e}), falling back to keyboard", file=sys.stderr)
            type_via_keyboard(text)
        return
    elif method == "xdotool":
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--", text], check=True)
    elif method == "ydotool":
        subprocess.run(["ydotool", "type", "--", text], check=True)
    else:
        # auto — keyboard typing with environment detection
        type_via_keyboard(text)
