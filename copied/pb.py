import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

class ProgressButtonApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.ProgressButtonApp')
        self.progress = 0.0

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_default_size(300, 200)
        self.win.set_title("Progress Button")

        # Create overlay container
        overlay = Gtk.Overlay()

        # Create main button
        self.button = Gtk.Button(label="Click to Start Progress")
        self.button.set_vexpand(True)
        self.button.set_hexpand(True)
        self.button.connect("clicked", self.on_button_clicked)
        overlay.set_child(self.button)

        # Create progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_halign(Gtk.Align.FILL)
        self.progress_bar.set_valign(Gtk.Align.END)
        self.progress_bar.set_margin_bottom(0)
        self.progress_bar.set_margin_start(5)
        self.progress_bar.set_margin_end(5)

        # Add progress bar to overlay
        overlay.add_overlay(self.progress_bar)

        # Load custom CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            progressbar {
                min-height: 2px;
                background: none;
                border: none;
                padding: 0;
                margin: 0;
            }
            progressbar trough {
                min-height: 2px;
                background-color: alpha(0, 0);
                border: none;
                padding: 0;
                margin: 0;
            }
            progressbar progress {
                min-height: 2px;
                background-color: @success_color;
                border-radius: 1px;
                margin: 0;
            }
            button {
                padding-bottom: 6px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            self.win.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.win.set_content(overlay)
        self.win.present()

    def on_button_clicked(self, button):
        self.progress = 0.0
        GLib.timeout_add(50, self.update_progress)

    def update_progress(self):
        self.progress += 0.01
        if self.progress > 1.0:
            self.progress = 0.0
            return False  # Stop animation
        self.progress_bar.set_fraction(self.progress)
        return True  # Continue animation

if __name__ == "__main__":
    app = ProgressButtonApp()
    app.run(None)
