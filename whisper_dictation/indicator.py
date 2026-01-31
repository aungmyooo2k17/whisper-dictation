#!/usr/bin/env python3
"""
Dictation indicator - shows animated GIF near cursor.
States: recording (sound wave) → processing (spinner)
Send SIGUSR1 to switch to processing state.
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
import signal
import subprocess
import os
from pathlib import Path


def get_icons_dir():
    """Get the icons directory path."""
    # Check in order: user config, package data, current dir
    locations = [
        Path.home() / ".config" / "whisper-dictation" / "icons",
        Path(__file__).parent / "icons",
        Path("/usr/local/share/whisper-dictation/icons"),
        Path("/usr/share/whisper-dictation/icons"),
    ]
    for loc in locations:
        if loc.exists():
            return loc
    return locations[1]  # Default to package dir


ICONS_DIR = get_icons_dir()
RECORDING_GIF = ICONS_DIR / "recording.gif"
PROCESSING_GIF = ICONS_DIR / "processing.gif"


class DictationIndicator(Gtk.Window):
    def __init__(self):
        super().__init__(title="")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_resizable(False)

        # Enable RGBA visual for transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        # Make window background transparent via CSS
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window, window * {
                background-color: rgba(0,0,0,0);
                background: transparent;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Image widget for GIF
        self.image = Gtk.Image()
        self.add(self.image)

        # Start with recording GIF
        self.load_gif(RECORDING_GIF)

        # Position near cursor
        self.position_near_cursor()

        # Handle SIGUSR1 to switch to processing
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR1, self.switch_to_processing)

    def load_gif(self, path):
        if path.exists():
            animation = GdkPixbuf.PixbufAnimation.new_from_file(str(path))
            self.image.set_from_animation(animation)
            # Resize window to fit GIF
            self.set_default_size(animation.get_width(), animation.get_height())
            self.resize(animation.get_width(), animation.get_height())

    def position_near_cursor(self):
        # Get cursor position using xdotool
        try:
            result = subprocess.run(
                ["xdotool", "getmouselocation", "--shell"],
                capture_output=True, text=True
            )
            x, y = 100, 100
            for line in result.stdout.strip().split('\n'):
                if line.startswith('X='):
                    x = int(line.split('=')[1])
                elif line.startswith('Y='):
                    y = int(line.split('=')[1])
            # Offset slightly from cursor
            self.move(x + 20, y + 20)
        except Exception:
            # Fallback to top center if xdotool fails
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor()
            geometry = monitor.get_geometry()
            self.move(geometry.x + geometry.width // 2 - 30, geometry.y + 30)

    def switch_to_processing(self):
        self.load_gif(PROCESSING_GIF)
        return False  # Remove signal handler


def main():
    win = DictationIndicator()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
