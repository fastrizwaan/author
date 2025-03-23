#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")  # WebKit 6.0
from gi.repository import Gtk, Adw, WebKit, GLib

class EditorWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Simple Web Editor")
        self.set_default_size(600, 400)

        # Create main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Create Adwaita header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Create toolbar box
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        toolbar.set_margin_start(6)
        toolbar.set_margin_end(6)
        header.set_title_widget(toolbar)

        # Underline button
        underline_btn = Gtk.Button(label="Underline")
        underline_btn.connect("clicked", self.on_underline_clicked)
        toolbar.append(underline_btn)

        # Strikeout button
        strikeout_btn = Gtk.Button(label="Strikeout")
        strikeout_btn.connect("clicked", self.on_strikeout_clicked)
        toolbar.append(strikeout_btn)

        # WebView setup with WebKit 6.0
        self.webview = WebKit.WebView()
        self.webview.set_editable(True)

        # Initial HTML content
        html_content = """
        <!DOCTYPE html>
        <html>
        <body contenteditable="true">
            <p>Type your text here...</p>
        </body>
        </html>
        """
        self.webview.load_html(html_content, "file:///")

        # Add WebView to scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.webview)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

    def on_underline_clicked(self, button):
        # Use evaluate_javascript for WebKit 6.0
        self.webview.evaluate_javascript(
            "document.execCommand('underline', false, null);",
            -1,  # Length of the script (-1 for null-terminated string)
            None,  # World name (None for default)
            None,  # Callback (None since we don't need the result)
            None,  # User data
            None  # Error callback
        )

    def on_strikeout_clicked(self, button):
        # Use evaluate_javascript for WebKit 6.0
        self.webview.evaluate_javascript(
            "document.execCommand('strikeThrough', false, null);",
            -1,  # Length of the script
            None,  # World name
            None,  # Callback
            None,  # User data
            None  # Error callback
        )

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.WebEditor")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = EditorWindow(application=app)
        win.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
