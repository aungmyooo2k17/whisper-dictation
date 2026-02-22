"""
System tray indicator using AppIndicator3 (or AyatanaAppIndicator3).
Opt-in alternative to the floating GIF indicator.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

# Try to import GTK and AppIndicator
try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib

    # Try AyatanaAppIndicator3 first (newer distros), then AppIndicator3
    try:
        gi.require_version('AyatanaAppIndicator3', '0.1')
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    except (ValueError, ImportError):
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3

    HAS_APPINDICATOR = True
except (ImportError, ValueError):
    HAS_APPINDICATOR = False


def get_icons_dir() -> Path:
    """Get the icons directory path."""
    locations = [
        Path.home() / ".config" / "whisper-dictation" / "icons",
        Path(__file__).parent / "icons",
        Path("/usr/local/share/whisper-dictation/icons"),
        Path("/usr/share/whisper-dictation/icons"),
    ]
    for loc in locations:
        if loc.exists():
            return loc
    return locations[1]


# SVG icon content for tray states
IDLE_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <circle cx="12" cy="12" r="10" fill="#888888" opacity="0.8"/>
  <path d="M12 6 L12 14 M9 14 L15 14 M9 14 Q9 18 12 18 Q15 18 15 14" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/>
</svg>"""

RECORDING_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <circle cx="12" cy="12" r="10" fill="#e53935" opacity="0.9"/>
  <path d="M12 6 L12 14 M9 14 L15 14 M9 14 Q9 18 12 18 Q15 18 15 14" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/>
</svg>"""

PROCESSING_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <circle cx="12" cy="12" r="10" fill="#fdd835" opacity="0.9"/>
  <path d="M12 6 L12 14 M9 14 L15 14 M9 14 Q9 18 12 18 Q15 18 15 14" stroke="#333" stroke-width="1.5" fill="none" stroke-linecap="round"/>
</svg>"""


def _ensure_icons(icons_dir: Path) -> dict:
    """Write SVG icons if they don't exist. Returns paths dict."""
    icons_dir.mkdir(parents=True, exist_ok=True)

    icons = {
        "idle": (icons_dir / "idle.svg", IDLE_SVG),
        "recording": (icons_dir / "recording.svg", RECORDING_SVG),
        "processing": (icons_dir / "processing.svg", PROCESSING_SVG),
    }

    paths = {}
    for state, (path, content) in icons.items():
        if not path.exists():
            path.write_text(content)
        paths[state] = str(path)

    return paths


class TrayIndicator:
    """System tray indicator with state management."""

    def __init__(self):
        if not HAS_APPINDICATOR:
            raise RuntimeError(
                "AppIndicator3 not available. "
                "Install gir1.2-ayatanaappindicator3-0.1 or gir1.2-appindicator3-0.1"
            )

        self.icons_dir = get_icons_dir()
        self.icon_paths = _ensure_icons(self.icons_dir)
        self.state = "idle"

        # Create indicator
        self.indicator = AppIndicator3.Indicator.new(
            "whisper-dictation",
            self.icon_paths["idle"],
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Whisper Dictation")

        # Build menu
        self.menu = self._build_menu()
        self.indicator.set_menu(self.menu)

        # Signal handlers for state changes
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR1, self._on_recording)
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR2, self._on_processing)

    def _build_menu(self) -> Gtk.Menu:
        """Build the right-click context menu."""
        menu = Gtk.Menu()

        # Toggle recording
        self.toggle_item = Gtk.MenuItem(label="Toggle Recording")
        self.toggle_item.connect("activate", self._on_toggle)
        menu.append(self.toggle_item)

        # Cancel
        cancel_item = Gtk.MenuItem(label="Cancel")
        cancel_item.connect("activate", self._on_cancel)
        menu.append(cancel_item)

        menu.append(Gtk.SeparatorMenuItem())

        # History
        history_item = Gtk.MenuItem(label="History")
        history_item.connect("activate", self._on_history)
        menu.append(history_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def set_state(self, state: str) -> None:
        """Set the tray icon state.

        Args:
            state: 'idle', 'recording', or 'processing'.
        """
        if state in self.icon_paths:
            self.state = state
            self.indicator.set_icon_full(self.icon_paths[state], state)

    def _on_recording(self) -> bool:
        self.set_state("recording")
        return True  # Keep handler active

    def _on_processing(self) -> bool:
        self.set_state("processing")
        # Return to idle after a delay
        GLib.timeout_add_seconds(5, self._return_to_idle)
        return True

    def _return_to_idle(self) -> bool:
        if self.state == "processing":
            self.set_state("idle")
        return False  # Don't repeat

    def _on_toggle(self, widget) -> None:
        """Toggle recording via whisper-dictation-toggle."""
        try:
            subprocess.Popen(["whisper-dictation-toggle"])
        except FileNotFoundError:
            # Fallback: use begin/end directly
            cookie = Path("/tmp/whisper-dictation.cookie")
            if cookie.exists():
                subprocess.Popen(["whisper-dictation", "end"])
            else:
                subprocess.Popen(["whisper-dictation", "begin"])

    def _on_cancel(self, widget) -> None:
        """Cancel current recording."""
        try:
            subprocess.Popen(["whisper-dictation", "cancel"])
        except FileNotFoundError:
            pass
        self.set_state("idle")

    def _on_history(self, widget) -> None:
        """Show recent history in a notification."""
        try:
            result = subprocess.run(
                ["whisper-dictation", "history", "--last", "5"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip():
                subprocess.run([
                    "notify-send", "Whisper Dictation - History",
                    result.stdout.strip(),
                ], timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def _on_quit(self, widget) -> None:
        Gtk.main_quit()


def main():
    """Entry point for whisper-dictation-tray."""
    if not HAS_APPINDICATOR:
        print(
            "Error: AppIndicator3 not available.\n"
            "Install: sudo apt install gir1.2-ayatanaappindicator3-0.1",
            file=sys.stderr,
        )
        sys.exit(1)

    tray = TrayIndicator()
    Gtk.main()


if __name__ == "__main__":
    main()
