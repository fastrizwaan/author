#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango, Gio

class WordPadApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.WordPad", flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.text_buffer = None
        self.window = None

    def do_activate(self):
        # Create the main window
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("WordPad (GTK4)")
        self.window.set_default_size(800, 600)

        # Main layout: vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.window.set_child(main_box)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        main_box.append(toolbar)

        # Bold button
        bold_button = Gtk.Button(label="Bold")
        bold_button.connect("clicked", self.on_bold_clicked)
        toolbar.append(bold_button)

        # Italic button
        italic_button = Gtk.Button(label="Italic")
        italic_button.connect("clicked", self.on_italic_clicked)
        toolbar.append(italic_button)

        # Font chooser button
        font_button = Gtk.FontButton()
        font_button.connect("font-set", self.on_font_set)
        toolbar.append(font_button)

        # Undo/Redo buttons
        undo_button = Gtk.Button(label="Undo")
        undo_button.connect("clicked", self.on_undo_clicked)
        toolbar.append(undo_button)
        redo_button = Gtk.Button(label="Redo")
        redo_button.connect("clicked", self.on_redo_clicked)
        toolbar.append(redo_button)

        # File menu using Gio.Menu and Gtk.MenuButton
        file_menu = Gio.Menu()
        file_menu.append("New", "app.new")
        file_menu.append("Open", "app.open")
        file_menu.append("Save", "app.save")

        menu_button = Gtk.MenuButton(label="File")
        menu_button.set_menu_model(file_menu)
        toolbar.append(menu_button)

        # Define actions for the menu
        new_action = Gio.SimpleAction.new("new", None)
        new_action.connect("activate", self.on_new_file)
        self.add_action(new_action)

        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", self.on_open_file)
        self.add_action(open_action)

        save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", self.on_save_file)
        self.add_action(save_action)

        # Text view with scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)  # Make it expand vertically
        self.text_view = Gtk.TextView()
        self.text_buffer = self.text_view.get_buffer()
        self.text_buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.text_buffer.create_tag("italic", style=Pango.Style.ITALIC)
        scrolled_window.set_child(self.text_view)
        main_box.append(scrolled_window)

        # Enable undo/redo tracking
        self.text_buffer.connect("changed", self.on_text_changed)
        self.text_buffer.set_enable_undo(True)

        self.window.present()

    def on_bold_clicked(self, button):
        bounds = self.text_buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            # Use the TextIter directly instead of get_iter_at_offset
            if self.text_buffer.get_tag_table().lookup("bold") in start.get_tags():
                self.text_buffer.remove_tag_by_name("bold", start, end)
            else:
                self.text_buffer.apply_tag_by_name("bold", start, end)

    def on_italic_clicked(self, button):
        bounds = self.text_buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            # Use the TextIter directly instead of get_iter_at_offset
            if self.text_buffer.get_tag_table().lookup("italic") in start.get_tags():
                self.text_buffer.remove_tag_by_name("italic", start, end)
            else:
                self.text_buffer.apply_tag_by_name("italic", start, end)

    def on_font_set(self, font_button):
        # Use get_font_desc() instead of deprecated get_font()
        font_desc = font_button.get_font_desc()
        bounds = self.text_buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            # Create a tag and set the font-desc property
            font_tag = Gtk.TextTag.new("font")
            font_tag.set_property("font-desc", font_desc)
            self.text_buffer.apply_tag(font_tag, start, end)

    def on_undo_clicked(self, button):
        self.text_buffer.undo()  # No can_undo() check; GTK4 ignores if nothing to undo

    def on_redo_clicked(self, button):
        self.text_buffer.redo()  # No can_redo() check; GTK4 ignores if nothing to redo

    def on_text_changed(self, buffer):
        pass  # Could update UI (e.g., enable/disable undo/redo buttons)

    def on_new_file(self, action, param):
        self.text_buffer.set_text("")

    def on_open_file(self, action, param):
        dialog = Gtk.FileChooserDialog(
            title="Open File", parent=self.window, action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self.on_open_response)
        dialog.present()

    def on_open_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                with open(file.get_path(), "r") as f:
                    self.text_buffer.set_text(f.read())
        dialog.destroy()

    def on_save_file(self, action, param):
        dialog = Gtk.FileChooserDialog(
            title="Save File", parent=self.window, action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Save", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self.on_save_response)
        dialog.present()

    def on_save_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                start, end = self.text_buffer.get_bounds()
                text = self.text_buffer.get_text(start, end, True)
                with open(file.get_path(), "w") as f:
                    f.write(text)
        dialog.destroy()

def main():
    app = WordPadApp()
    app.run()

if __name__ == "__main__":
    main()
