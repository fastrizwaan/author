import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

class EditorWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_ui()

    def setup_ui(self):
        self.set_title("Basic Editor")
        self.set_default_size(800, 600)

        # Create a box layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)

        # Create a navigation bar
        header_bar = Gtk.HeaderBar()
        box.append(header_bar)

        # Create a new button
        new_button = Gtk.Button(label="New")
        new_button.connect("clicked", self.new_file)
        header_bar.pack_start(new_button)

        # Create an open button
        open_button = Gtk.Button(label="Open")
        open_button.connect("clicked", self.open_file)
        header_bar.pack_start(open_button)

        # Create a save button
        save_button = Gtk.Button(label="Save")
        save_button.connect("clicked", self.save_file)
        header_bar.pack_start(save_button)

        # Create a text view
        self.text_view = Gtk.TextView()
        box.append(self.text_view)

        # Create a text buffer
        self.text_buffer = self.text_view.get_buffer()

    def new_file(self, button):
        # Clear the text buffer
        self.text_buffer.set_text("")

    def open_file(self, button):
        # Create a file chooser dialog
        dialog = Gtk.FileChooserDialog(
            title="Open File",
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Open", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self.open_file_response)
        dialog.present()

    def open_file_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            # Get the selected file
            file = dialog.get_file()
            try:
                # Read the contents of the file into the text buffer
                with open(file.get_path(), "r") as f:
                    self.text_buffer.set_text(f.read())
            except Exception as e:
                print(f"Error opening file: {e}")
        dialog.destroy()

    def save_file(self, button):
        # Create a file chooser dialog
        dialog = Gtk.FileChooserDialog(
            title="Save File",
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self.save_file_response)
        dialog.present()

    def save_file_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            # Get the selected file
            file = dialog.get_file()
            try:
                # Write the contents of the text buffer to the file
                with open(file.get_path(), "w") as f:
                    f.write(self.text_buffer.get_text(self.text_buffer.get_start_iter(), self.text_buffer.get_end_iter(), True))
            except Exception as e:
                print(f"Error saving file: {e}")
        dialog.destroy()

class EditorApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.Editor")

    def do_activate(self):
        window = EditorWindow(application=self)
        window.present()

if __name__ == "__main__":
    app = EditorApplication()
    app.run()
