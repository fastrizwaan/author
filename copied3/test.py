import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw

class RadioButtonApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Create a new window
        self.window = Gtk.ApplicationWindow(application=app, title="Radio Button Example")
        self.window.set_default_size(300, 200)

        # Create a box to hold the radio buttons
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        # Create the first radio button
        radio1 = Gtk.CheckButton(label="Option 1")
        radio1.connect("toggled", self.on_radio_toggled, "Option 1")
        box.append(radio1)

        # Create the second radio button, grouped with the first
        radio2 = Gtk.CheckButton(label="Option 2", group=radio1)
        radio2.connect("toggled", self.on_radio_toggled, "Option 2")
        box.append(radio2)

        # Add the box to the window
        self.window.set_child(box)
        self.window.present()

    def on_radio_toggled(self, button, option):
        if button.get_active():
            print(f"{option} selected")

# Create and run the application
app = RadioButtonApp(application_id='com.example.RadioButtonApp')
app.run(None)
