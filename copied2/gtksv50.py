#!/usr/bin/env python3
import gi
import os
import sys
import tempfile
import webbrowser

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GtkSource', '5')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Adw, Gio, GtkSource, GLib, Gdk, WebKit
from pathlib import Path

class RichTextEditor(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.richtexteditor",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        
        self.connect('activate', self.on_activate)
        self.current_file = None
        
    def on_activate(self, app):
        # Create the main window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(800, 600)
        self.win.set_title("Rich Text Editor")
        
        # Create a header bar
        self.header = Adw.HeaderBar()
        
        # Create a box for the main content
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Add the header to the main box
        self.main_box.append(self.header)
        
        # Create actions
        self.create_actions()
        
        # Create menus
        self.create_menus()
        
        # Create the source view for rich text editing
        self.create_editor()
        
        # Add the main box to the window
        self.win.set_content(self.main_box)
        
        # Show the window
        self.win.present()
    
    def create_actions(self):
        # File actions
        actions = [
            ('new', self.on_new_clicked),
            ('open', self.on_open_clicked),
            ('save', self.on_save_clicked),
            ('save_as', self.on_save_as_clicked),
            ('export_html', self.on_export_html_clicked),
            ('preview', self.on_preview_clicked),
            ('quit', self.on_quit_clicked),
            
            # Edit actions
            ('cut', self.on_cut_clicked),
            ('copy', self.on_copy_clicked),
            ('paste', self.on_paste_clicked),
            ('paste_html', self.on_paste_html_clicked),
            ('select_all', self.on_select_all_clicked),
            
            # Format actions
            ('bold', self.on_bold_clicked),
            ('italic', self.on_italic_clicked),
            ('underline', self.on_underline_clicked),
        ]
        
        for action_name, callback in actions:
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", callback)
            self.add_action(action)
    
    def create_menus(self):
        # Create menu button for the header bar
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        
        # Create menu model
        menu = Gio.Menu.new()
        
        # File submenu
        file_menu = Gio.Menu.new()
        file_menu.append("New", "app.new")
        file_menu.append("Open", "app.open")
        file_menu.append("Save", "app.save")
        file_menu.append("Save As", "app.save_as")
        file_menu.append("Export HTML", "app.export_html")
        file_menu.append("Preview in Browser", "app.preview")
        file_menu.append("Quit", "app.quit")
        
        # Edit submenu
        edit_menu = Gio.Menu.new()
        edit_menu.append("Cut", "app.cut")
        edit_menu.append("Copy", "app.copy")
        edit_menu.append("Paste", "app.paste")
        edit_menu.append("Paste HTML", "app.paste_html")
        edit_menu.append("Select All", "app.select_all")
        
        # Format submenu
        format_menu = Gio.Menu.new()
        format_menu.append("Bold", "app.bold")
        format_menu.append("Italic", "app.italic")
        format_menu.append("Underline", "app.underline")
        
        # Add submenus to main menu
        menu.append_submenu("File", file_menu)
        menu.append_submenu("Edit", edit_menu)
        menu.append_submenu("Format", format_menu)
        
        # Connect menu to button
        menu_button.set_menu_model(menu)
        
        # Add menu button to header bar
        self.header.pack_end(menu_button)
        
        # Create toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.add_css_class("toolbar")
        
        # Add formatting buttons to toolbar
        bold_button = Gtk.Button.new_from_icon_name("format-text-bold-symbolic")
        bold_button.set_tooltip_text("Bold")
        bold_button.connect("clicked", self.on_bold_clicked)
        
        italic_button = Gtk.Button.new_from_icon_name("format-text-italic-symbolic")
        italic_button.set_tooltip_text("Italic")
        italic_button.connect("clicked", self.on_italic_clicked)
        
        underline_button = Gtk.Button.new_from_icon_name("format-text-underline-symbolic")
        underline_button.set_tooltip_text("Underline")
        underline_button.connect("clicked", self.on_underline_clicked)
        
        toolbar.append(bold_button)
        toolbar.append(italic_button)
        toolbar.append(underline_button)
        
        # Add toolbar to main box
        self.main_box.append(toolbar)
    
    def create_editor(self):
        # Create a scrolled window for the source view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        
        # Create the source view for rich text editing
        self.buffer = GtkSource.Buffer()
        self.buffer.set_highlight_syntax(True)
        
        # Create a source language manager
        language_manager = GtkSource.LanguageManager.get_default()
        html_language = language_manager.get_language("html")
        
        if html_language:
            self.buffer.set_language(html_language)
        
        # Create the source view with the buffer
        self.source_view = GtkSource.View(buffer=self.buffer)
        self.source_view.set_show_line_numbers(True)
        self.source_view.set_tab_width(4)
        self.source_view.set_auto_indent(True)
        self.source_view.set_indent_width(4)
        self.source_view.set_insert_spaces_instead_of_tabs(True)
        self.source_view.set_smart_backspace(True)
        self.source_view.set_monospace(True)
        
        # Add the source view to the scrolled window
        scrolled_window.set_child(self.source_view)
        
        # Add the scrolled window to the main box
        self.main_box.append(scrolled_window)
        
        # Status bar
        self.status_bar = Gtk.Label()
        self.status_bar.set_xalign(0)
        self.status_bar.add_css_class("statusbar")
        self.main_box.append(self.status_bar)
        self.update_status("Ready")
    
    def update_status(self, message):
        self.status_bar.set_text(message)
    
    # File actions
    def on_new_clicked(self, action, param):
        if self.buffer.get_modified():
            dialog = Adw.MessageDialog.new(self.win, "Unsaved Changes", 
                                          "Do you want to save the changes?")
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_default_response("save")
            dialog.connect("response", self.on_new_file_response)
            dialog.present()
        else:
            self.new_file()
    
    def on_new_file_response(self, dialog, response):
        if response == "save":
            self.on_save_clicked(None, None)
            self.new_file()
        elif response == "discard":
            self.new_file()
    
    def new_file(self):
        self.buffer.set_text("")
        self.buffer.set_modified(False)
        self.current_file = None
        self.update_status("New file created")
    
    def on_open_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open File")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("text/html")
        filters.add_mime_type("text/plain")
        dialog.set_default_filter(filters)
        
        dialog.open(self.win, None, self.on_open_file_dialog_response)
    
    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.load_file(file)
        except GLib.Error as error:
            self.show_error_dialog(f"Error opening file: {error.message}")
    
    def load_file(self, file):
        try:
            success, contents, _ = file.load_contents()
            if success:
                try:
                    text = contents.decode('utf-8')
                    self.buffer.set_text(text)
                    self.buffer.set_modified(False)
                    self.current_file = file
                    self.update_status(f"Loaded {file.get_path()}")
                except UnicodeDecodeError:
                    self.show_error_dialog("File is not in UTF-8 encoding")
        except GLib.Error as error:
            self.show_error_dialog(f"Error loading file: {error.message}")
    
    def on_save_clicked(self, action, param):
        if self.current_file:
            self.save_file(self.current_file)
        else:
            self.on_save_as_clicked(action, param)
    
    def on_save_as_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Save File")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("text/html")
        filters.add_mime_type("text/plain")
        dialog.set_default_filter(filters)
        
        dialog.save(self.win, None, self.on_save_file_dialog_response)
    
    def on_save_file_dialog_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.save_file(file)
        except GLib.Error as error:
            self.show_error_dialog(f"Error saving file: {error.message}")
    
    def save_file(self, file):
        try:
            text = self.buffer.get_text(self.buffer.get_start_iter(), 
                                        self.buffer.get_end_iter(), 
                                        include_hidden_chars=True)
            file.replace_contents(text.encode('utf-8'), None, 
                                 False, Gio.FileCreateFlags.NONE, 
                                 None)
            self.buffer.set_modified(False)
            self.current_file = file
            self.update_status(f"Saved to {file.get_path()}")
        except GLib.Error as error:
            self.show_error_dialog(f"Error saving file: {error.message}")
    
    def on_export_html_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Export HTML")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("text/html")
        dialog.set_default_filter(filters)
        
        dialog.save(self.win, None, self.on_export_html_dialog_response)
    
    def on_export_html_dialog_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.export_html(file)
        except GLib.Error as error:
            self.show_error_dialog(f"Error exporting HTML: {error.message}")
    
    def export_html(self, file):
        try:
            text = self.buffer.get_text(self.buffer.get_start_iter(), 
                                       self.buffer.get_end_iter(), 
                                       include_hidden_chars=True)
            
            # Ensure basic HTML structure if it doesn't exist
            if "<html" not in text:
                text = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Exported Document</title>
</head>
<body>
{text}
</body>
</html>"""
            
            file.replace_contents(text.encode('utf-8'), None, 
                                 False, Gio.FileCreateFlags.NONE, 
                                 None)
            self.update_status(f"Exported HTML to {file.get_path()}")
        except GLib.Error as error:
            self.show_error_dialog(f"Error exporting HTML: {error.message}")
    
    def on_preview_clicked(self, action, param):
        text = self.buffer.get_text(self.buffer.get_start_iter(), 
                                   self.buffer.get_end_iter(), 
                                   include_hidden_chars=True)
        
        # Ensure basic HTML structure if it doesn't exist
        if "<html" not in text:
            text = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Preview</title>
</head>
<body>
{text}
</body>
</html>"""
        
        # Create a temporary file for preview
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f:
            f.write(text.encode('utf-8'))
            temp_path = f.name
        
        # Open the file in the default web browser
        webbrowser.open('file://' + temp_path)
        self.update_status("Previewing in browser")
    
    def on_quit_clicked(self, action, param):
        if self.buffer.get_modified():
            dialog = Adw.MessageDialog.new(self.win, "Unsaved Changes", 
                                          "Do you want to save the changes before quitting?")
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_default_response("save")
            dialog.connect("response", self.on_quit_response)
            dialog.present()
        else:
            self.quit()
    
    def on_quit_response(self, dialog, response):
        if response == "save":
            self.on_save_clicked(None, None)
            self.quit()
        elif response == "discard":
            self.quit()
    
    # Edit actions
    def on_cut_clicked(self, action, param):
        self.buffer.cut_clipboard(self.get_clipboard(), True)
    
    def on_copy_clicked(self, action, param):
        self.buffer.copy_clipboard(self.get_clipboard())
    
    def on_paste_clicked(self, action, param):
        self.buffer.paste_clipboard(self.get_clipboard(), None, True)
    
    def on_paste_html_clicked(self, action, param):
        clipboard = self.get_clipboard()
        
        # Request HTML content from clipboard
        clipboard.read_text_async(None, self.on_clipboard_html_received)
    
    def on_clipboard_html_received(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            if text:
                # Insert at cursor position
                self.buffer.insert_at_cursor(text, len(text))
        except GLib.Error as error:
            self.show_error_dialog(f"Error pasting HTML: {error.message}")
    
    def on_select_all_clicked(self, action, param):
        bounds = self.buffer.get_bounds()
        if bounds:
            start, end = bounds
            self.buffer.select_range(start, end)
    
    # Format actions
    def on_bold_clicked(self, action=None, param=None):
        self.insert_html_tag("<strong>", "</strong>")
    
    def on_italic_clicked(self, action=None, param=None):
        self.insert_html_tag("<em>", "</em>")
    
    def on_underline_clicked(self, action=None, param=None):
        self.insert_html_tag("<u>", "</u>")
    
    def insert_html_tag(self, opening_tag, closing_tag):
        # Get current selection bounds
        bounds = self.buffer.get_selection_bounds()
        
        if bounds:
            # There is a selection, wrap it with tags
            start, end = bounds
            text = self.buffer.get_text(start, end, False)
            
            with self.buffer.new_edit():
                self.buffer.delete(start, end)
                self.buffer.insert(start, opening_tag + text + closing_tag, -1)
        else:
            # No selection, just insert tags at cursor
            cursor = self.buffer.get_insert()
            iter = self.buffer.get_iter_at_mark(cursor)
            self.buffer.insert(iter, opening_tag + closing_tag, -1)
            
            # Position cursor between tags
            cursor_pos = iter.get_offset() - len(closing_tag)
            iter_between = self.buffer.get_iter_at_offset(cursor_pos)
            self.buffer.place_cursor(iter_between)
    
    # Helper methods
    def get_clipboard(self):
        return Gdk.Display.get_default().get_clipboard()
    
    def show_error_dialog(self, message):
        dialog = Adw.MessageDialog.new(self.win, "Error", message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present()

if __name__ == "__main__":
    app = RichTextEditor()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
