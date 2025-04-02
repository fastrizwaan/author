#!/usr/bin/env python3
import gi
import os
import sys
import tempfile
import webbrowser

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Adw, Gio, GLib, Gdk, WebKit
from pathlib import Path

class WYSIWYGTextEditor(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.wysiwygeditor",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        
        self.connect('activate', self.on_activate)
        self.current_file = None
        
    def on_activate(self, app):
        # Create the main window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(800, 600)
        self.win.set_title("WYSIWYG Editor")
        
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
        
        # Create the editor
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
            ('select_all', self.on_select_all_clicked),
            
            # Format actions
            ('bold', self.on_bold_clicked),
            ('italic', self.on_italic_clicked),
            ('underline', self.on_underline_clicked),
            ('heading1', self.on_heading1_clicked),
            ('heading2', self.on_heading2_clicked),
            ('bullet_list', self.on_bullet_list_clicked),
            ('number_list', self.on_number_list_clicked),
            ('align_left', self.on_align_left_clicked),
            ('align_center', self.on_align_center_clicked),
            ('align_right', self.on_align_right_clicked),
            ('insert_image', self.on_insert_image_clicked),
            ('insert_link', self.on_insert_link_clicked),
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
        edit_menu.append("Select All", "app.select_all")
        
        # Format submenu
        format_menu = Gio.Menu.new()
        format_menu.append("Bold", "app.bold")
        format_menu.append("Italic", "app.italic")
        format_menu.append("Underline", "app.underline")
        format_menu.append("Heading 1", "app.heading1")
        format_menu.append("Heading 2", "app.heading2")
        format_menu.append("Bullet List", "app.bullet_list")
        format_menu.append("Numbered List", "app.number_list")
        format_menu.append("Align Left", "app.align_left")
        format_menu.append("Align Center", "app.align_center")
        format_menu.append("Align Right", "app.align_right")
        format_menu.append("Insert Image", "app.insert_image")
        format_menu.append("Insert Link", "app.insert_link")
        
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
        buttons = [
            ("format-text-bold-symbolic", "Bold", self.on_bold_clicked),
            ("format-text-italic-symbolic", "Italic", self.on_italic_clicked),
            ("format-text-underline-symbolic", "Underline", self.on_underline_clicked),
            ("format-text-heading-1-symbolic", "Heading 1", self.on_heading1_clicked),
            ("format-text-heading-2-symbolic", "Heading 2", self.on_heading2_clicked),
            ("format-list-unordered-symbolic", "Bullet List", self.on_bullet_list_clicked),
            ("format-list-ordered-symbolic", "Numbered List", self.on_number_list_clicked),
            ("format-justify-left-symbolic", "Align Left", self.on_align_left_clicked),
            ("format-justify-center-symbolic", "Align Center", self.on_align_center_clicked),
            ("format-justify-right-symbolic", "Align Right", self.on_align_right_clicked),
            ("insert-image-symbolic", "Insert Image", self.on_insert_image_clicked),
            ("insert-link-symbolic", "Insert Link", self.on_insert_link_clicked),
        ]
        
        for icon_name, tooltip, callback in buttons:
            button = Gtk.Button.new_from_icon_name(icon_name)
            button.set_tooltip_text(tooltip)
            button.connect("clicked", callback)
            toolbar.append(button)
        
        # Add toolbar to main box
        self.main_box.append(toolbar)
    
    def create_editor(self):
        # Create a scrolled window for the WebView
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        
        # Create WebView
        self.webview = WebKit.WebView()
        
        # Set WebView settings
        settings = self.webview.get_settings()
        settings.set_javascript_can_access_clipboard(True)
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)
        
        # Load the editor HTML
        self.init_editor_content()
        
        # Add the WebView to the scrolled window
        scrolled_window.set_child(self.webview)
        
        # Add the scrolled window to the main box
        self.main_box.append(scrolled_window)
        
        # Status bar
        self.status_bar = Gtk.Label()
        self.status_bar.set_xalign(0)
        self.status_bar.add_css_class("statusbar")
        self.main_box.append(self.status_bar)
        self.update_status("Ready")
    
    def init_editor_content(self):
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>WYSIWYG Editor</title>
            <style>
                body {
                    font-family: system-ui, -apple-system, sans-serif;
                    margin: 0;
                    padding: 10px;
                    background-color: white;
                    color: black;
                    min-height: 100vh;
                }
                #editor {
                    outline: none;
                    padding: 10px;
                    border: 1px solid #ccc;
                    min-height: 500px;
                    overflow-y: auto;
                }
                @media (prefers-color-scheme: dark) {
                    body {
                        background-color: #333;
                        color: #eee;
                    }
                    #editor {
                        border-color: #555;
                        background-color: #222;
                        color: #eee;
                    }
                }
            </style>
        </head>
        <body>
            <div id="editor" contenteditable="true"></div>
            
            <script>
                // Initialize editor
                const editor = document.getElementById('editor');
                
                // Make the editor focusable
                editor.focus();
                
                // Helper function to get selected HTML
                function getSelectedHtml() {
                    const selection = window.getSelection();
                    if (selection.rangeCount > 0) {
                        const range = selection.getRangeAt(0);
                        const clonedRange = range.cloneContents();
                        const div = document.createElement('div');
                        div.appendChild(clonedRange);
                        return div.innerHTML;
                    }
                    return '';
                }
                
                // Helper function to get editor content
                function getContent() {
                    return editor.innerHTML;
                }
                
                // Helper function to set editor content
                function setContent(html) {
                    editor.innerHTML = html;
                }
                
                // Execute command helper
                function execCommand(command, value=null) {
                    document.execCommand(command, false, value);
                    editor.focus();
                }
            </script>
        </body>
        </html>
        """
        
        self.webview.load_html(html_content, "file:///")
    
    def update_status(self, message):
        self.status_bar.set_text(message)
    
    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)
    
    def get_editor_content(self, callback):
        self.webview.evaluate_javascript("getContent();", -1, None, None, None, self.handle_js_result, callback)
    
    def handle_js_result(self, webview, result, callback):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result is not None:
                value = js_result.get_js_value().to_string()
                callback(value)
        except GLib.Error as error:
            self.show_error_dialog(f"JavaScript error: {error.message}")
    
    # File actions
    def on_new_clicked(self, action, param):
        self.get_editor_content(self.check_modified_for_new)
    
    def check_modified_for_new(self, content):
        if content and content.strip():
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
        self.exec_js("setContent('');")
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
                    # Load content into editor
                    escaped_text = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                    self.exec_js(f"setContent('{escaped_text}');")
                    self.current_file = file
                    self.update_status(f"Loaded {file.get_path()}")
                except UnicodeDecodeError:
                    self.show_error_dialog("File is not in UTF-8 encoding")
        except GLib.Error as error:
            self.show_error_dialog(f"Error loading file: {error.message}")
    
    def on_save_clicked(self, action, param):
        if self.current_file:
            self.get_editor_content(lambda content: self.save_file(self.current_file, content))
        else:
            self.on_save_as_clicked(action, param)
    
    def on_save_as_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Save File")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("text/html")
        dialog.set_default_filter(filters)
        
        dialog.save(self.win, None, self.on_save_file_dialog_response)
    
    def on_save_file_dialog_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.get_editor_content(lambda content: self.save_file(file, content))
        except GLib.Error as error:
            self.show_error_dialog(f"Error saving file: {error.message}")
    
    def save_file(self, file, content):
        try:
            # Ensure the file has .html extension
            path = file.get_path()
            if not path.lower().endswith('.html'):
                path += '.html'
                file = Gio.File.new_for_path(path)
            
            # Create a complete HTML document
            html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Document</title>
</head>
<body>
{content}
</body>
</html>"""
            
            file.replace_contents(html_document.encode('utf-8'), None, 
                                 False, Gio.FileCreateFlags.NONE, 
                                 None)
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
                self.get_editor_content(lambda content: self.export_html(file, content))
        except GLib.Error as error:
            self.show_error_dialog(f"Error exporting HTML: {error.message}")
    
    def export_html(self, file, content):
        try:
            # Ensure the file has .html extension
            path = file.get_path()
            if not path.lower().endswith('.html'):
                path += '.html'
                file = Gio.File.new_for_path(path)
            
            # Create a complete HTML document
            html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Exported Document</title>
</head>
<body>
{content}
</body>
</html>"""
            
            file.replace_contents(html_document.encode('utf-8'), None, 
                                 False, Gio.FileCreateFlags.NONE, 
                                 None)
            self.update_status(f"Exported HTML to {file.get_path()}")
        except GLib.Error as error:
            self.show_error_dialog(f"Error exporting HTML: {error.message}")
    
    def on_preview_clicked(self, action, param):
        self.get_editor_content(self.preview_content)
    
    def preview_content(self, content):
        # Create a complete HTML document
        html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Preview</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; padding: 20px; }}
    </style>
</head>
<body>
{content}
</body>
</html>"""
        
        # Create a temporary file for preview
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f:
            f.write(html_document.encode('utf-8'))
            temp_path = f.name
        
        # Open the file in the default web browser
        webbrowser.open('file://' + temp_path)
        self.update_status("Previewing in browser")
    
    def on_quit_clicked(self, action, param):
        self.get_editor_content(self.check_modified_for_quit)
    
    def check_modified_for_quit(self, content):
        if content and content.strip():
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
        self.exec_js("execCommand('cut');")
    
    def on_copy_clicked(self, action, param):
        self.exec_js("execCommand('copy');")
    
    def on_paste_clicked(self, action, param):
        self.exec_js("execCommand('paste');")
    
    def on_select_all_clicked(self, action, param):
        self.exec_js("execCommand('selectAll');")
    
    # Format actions
    def on_bold_clicked(self, action=None, param=None):
        self.exec_js("execCommand('bold');")
    
    def on_italic_clicked(self, action=None, param=None):
        self.exec_js("execCommand('italic');")
    
    def on_underline_clicked(self, action=None, param=None):
        self.exec_js("execCommand('underline');")
    
    def on_heading1_clicked(self, action=None, param=None):
        self.exec_js("execCommand('formatBlock', 'h1');")
    
    def on_heading2_clicked(self, action=None, param=None):
        self.exec_js("execCommand('formatBlock', 'h2');")
    
    def on_bullet_list_clicked(self, action=None, param=None):
        self.exec_js("execCommand('insertUnorderedList');")
    
    def on_number_list_clicked(self, action=None, param=None):
        self.exec_js("execCommand('insertOrderedList');")
    
    def on_align_left_clicked(self, action=None, param=None):
        self.exec_js("execCommand('justifyLeft');")
    
    def on_align_center_clicked(self, action=None, param=None):
        self.exec_js("execCommand('justifyCenter');")
    
    def on_align_right_clicked(self, action=None, param=None):
        self.exec_js("execCommand('justifyRight');")
    
    def on_insert_image_clicked(self, action=None, param=None):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select Image")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("image/*")
        dialog.set_default_filter(filters)
        
        dialog.open(self.win, None, self.on_image_selected)
    
    def on_image_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                # Convert to data URL
                success, contents, _ = file.load_contents()
                if success:
                    import base64
                    import mimetypes
                    
                    # Get mime type
                    mime_type, _ = mimetypes.guess_type(file.get_path())
                    if mime_type is None:
                        mime_type = 'image/png'  # Default to PNG
                    
                    # Create data URL
                    encoded = base64.b64encode(contents).decode('utf-8')
                    data_url = f"data:{mime_type};base64,{encoded}"
                    
                    # Insert image
                    self.exec_js(f"execCommand('insertImage', '{data_url}');")
        except GLib.Error as error:
            self.show_error_dialog(f"Error selecting image: {error.message}")
    
    def on_insert_link_clicked(self, action=None, param=None):
        dialog = Adw.MessageDialog.new(self.win, "Insert Link", "Enter URL:")
        
        # Add URL entry
        entry = Gtk.Entry()
        entry.set_margin_start(20)
        entry.set_margin_end(20)
        entry.set_margin_bottom(20)
        entry.set_text("https://")
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)
        
        # Add dialog buttons
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_response_enabled("ok", True)
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        
        # Connect response signal
        dialog.connect("response", self.on_link_dialog_response, entry)
        dialog.present()
    
    def on_link_dialog_response(self, dialog, response, entry):
        if response == "ok":
            url = entry.get_text()
            if url:
                self.exec_js(f"execCommand('createLink', '{url}');")
    
    # Helper methods
    def show_error_dialog(self, message):
        dialog = Adw.MessageDialog.new(self.win, "Error", message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present()

if __name__ == "__main__":
    app = WYSIWYGTextEditor()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
