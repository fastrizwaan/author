import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw

class CheckboxesApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='org.example.Checkboxes',
                        flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect('activate', self.on_activate)

    def on_activate(self, user_data):
        # Create the main window
        self.window = Adw.PreferencesWindow(
            application=self,
            title="Adwaita Checkboxes Example",
            default_width=300,
            default_height=200
        )

        # Create a preferences page
        page = Adw.PreferencesPage()

        # Create a group for checkboxes
        group = Adw.PreferencesGroup(
            title="Options",
            description="Select your preferences"
        )

        # Create four check buttons
        check_buttons = [
            Gtk.CheckButton(label="Option 1"),
            Gtk.CheckButton(label="Option 2"),
            Gtk.CheckButton(label="Option 3"),
            Gtk.CheckButton(label="Option 4")
        ]

        # Add check buttons to the group
        for btn in check_buttons:
            group.add(btn)

        # Add group to page and page to window
        page.add(group)
        self.window.set_content(page)

        # Show the window
        self.window.present()

if __name__ == "__main__":
    app = CheckboxesApp()
    app.run(None)
