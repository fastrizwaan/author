import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio

class CheckboxesApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.example.Checkboxes',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect('activate', self.on_activate)

    def on_activate(self):
        # Create the main window
        self.window = Gtk.ApplicationWindow(
            application=self,
            title="Adwaita Checkboxes Example",
            default_width=300,
            default_height=200
        )

        # Create a vertical box container with spacing and margins
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(18)
        vbox.set_margin_bottom(18)
        vbox.set_margin_start(18)
        vbox.set_margin_end(18)

        # Create four check buttons
        check_buttons = [
            Gtk.CheckButton(label="Option 1"),
            Gtk.CheckButton(label="Option 2"),
            Gtk.CheckButton(label="Option 3"),
            Gtk.CheckButton(label="Option 4")
        ]

        # Add all check buttons to the box
        for btn in check_buttons:
            vbox.append(btn)

        # Set the box as the window's content
        self.window.set_child(vbox)

        # Show the window
        self.window.present()

if __name__ == "__main__":
    app = CheckboxesApp()
    app.run(None)
