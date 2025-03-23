import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

class RadioButtonWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(300, 200)

        # Create a box to hold the radio buttons
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_content(box)

        # Create two radio buttons using Gtk.CheckButton
        radio_button1 = Gtk.CheckButton(label="Option 1")
        radio_button2 = Gtk.CheckButton(label="Option 2")

        # Set the group property to make them radio buttons
        radio_button2.set_group(radio_button1)

        # Add radio buttons to the box
        box.append(radio_button1)
        box.append(radio_button2)

        # Create a box for the OK and Cancel buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(button_box)

        # Create OK and Cancel buttons
        ok_button = Gtk.Button(label="OK")
        cancel_button = Gtk.Button(label="Cancel")

        # Connect signals to buttons
        ok_button.connect("clicked", self.on_ok_clicked)
        cancel_button.connect("clicked", self.on_cancel_clicked)

        # Add buttons to the button box
        button_box.append(ok_button)
        button_box.append(cancel_button)

    def on_ok_clicked(self, button):
        print("OK button clicked")

    def on_cancel_clicked(self, button):
        print("Cancel button clicked")
        self.close()

def main():
    app = Adw.Application(application_id="com.example.GtkApplication")
    app.connect("activate", on_activate)
    app.run()

def on_activate(app):
    win = RadioButtonWindow(application=app)
    win.present()

if __name__ == "__main__":
    main()
