#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
from gi.repository import Gtk, Adw, WebKit, GLib, Gio
import os
import sys
import tempfile

class EditorWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.set_default_size(800, 850)
        self.set_title("Editor")
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header bar with buttons
        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton()
        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu_button.set_menu_model(menu)
        menu_button.set_icon_name("open-menu-symbolic")
        header.pack_end(menu_button)
        
        save_button = Gtk.Button(icon_name="document-save-symbolic")
        save_button.set_tooltip_text("Save as Text")
        save_button.connect("clicked", self.on_save_clicked)
        header.pack_start(save_button)
        
        save_html_button = Gtk.Button(icon_name="text-html-symbolic")
        save_html_button.set_tooltip_text("Save as HTML")
        save_html_button.connect("clicked", self.on_save_html_clicked)
        header.pack_start(save_html_button)
        
        self.main_box.append(header)
        
        self.create_editor()
        self.set_content(self.main_box)
        
        self.temp_dir = tempfile.TemporaryDirectory()
        self.html_path = os.path.join(self.temp_dir.name, "editor.html")
        self.create_editor_html()
        
        self.webview.load_uri(f"file://{self.html_path}")
    
    def create_editor(self):
        self.webview = WebKit.WebView()
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)
        
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_javascript_can_access_clipboard(True)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.webview)
        self.main_box.append(scrolled)
    
    def create_editor_html(self):
        html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Editor</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: white;
            font-family: sans-serif;
        }
        .content {
            min-height: 100vh;
            padding: 20px;
            outline: none;
            box-sizing: border-box;
        }
    </style>
</head>
<body>
    <div class="content" contenteditable="true"></div>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const content = document.querySelector('.content');
            content.focus();
            
            content.addEventListener('click', () => content.focus());
            
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    document.execCommand('insertHTML', false, '<br>');
                }
            });
        });
        
        window.getEditorContent = () => document.querySelector('.content').innerText;
        window.getEditorHTML = () => document.querySelector('.content').innerHTML;
        window.setEditorContent = (html) => document.querySelector('.content').innerHTML = html;
    </script>
</body>
</html>"""
        
        with open(self.html_path, 'w') as f:
            f.write(html_content)
    
    def on_save_clicked(self, button):
        self.webview.evaluate_javascript(
            "getEditorContent();",
            -1,
            None,
            None,
            None,
            self.on_get_content_finished,
            None
        )
    
    def on_save_html_clicked(self, button):
        self.webview.evaluate_javascript(
            "getEditorHTML();",
            -1,
            None,
            None,
            None,
            self.on_get_html_finished,
            None
        )
    
    def on_get_content_finished(self, webview, result, data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                js_value = js_result.get_js_value()
                content = js_value.to_string()
                self.show_save_dialog(content, "txt")
        except Exception as e:
            self.show_error(f"Failed to get content: {str(e)}")
    
    def on_get_html_finished(self, webview, result, data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                js_value = js_result.get_js_value()
                content = js_value.to_string()
                self.show_save_dialog(content, "html")
        except Exception as e:
            self.show_error(f"Failed to get HTML: {str(e)}")
    
    def show_save_dialog(self, content, file_type):
        dialog = Gtk.FileChooserDialog(
            title=f"Save as {file_type.upper()}",
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Save", Gtk.ResponseType.ACCEPT
        )
        dialog.set_current_name(f"Untitled.{file_type}")

        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                gfile = dialog.get_file()
                self.save_content(gfile, content, file_type)
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.present()  # Changed from show() to present()

    def save_content(self, gfile, content, file_type):
        try:
            path = gfile.get_path()
            if file_type == "html":
                content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
</head>
<body>
{content}
</body>
</html>"""
            with open(path, 'w') as f:
                f.write(content)
            self.show_toast(f"Saved successfully as {os.path.basename(path)}")
        except Exception as e:
            self.show_error(f"Save failed: {str(e)}")
    
    def show_toast(self, msg):
        toast = Adw.Toast.new(msg)
        # Get existing toast overlay or create new
        current_content = self.get_content()
        if isinstance(current_content, Adw.ToastOverlay):
            current_content.add_toast(toast)
        else:
            toast_overlay = Adw.ToastOverlay.new(child=current_content)
            self.set_content(toast_overlay)
            toast_overlay.add_toast(toast)
    
    def show_error(self, error):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Error",
            body=error
        )
        dialog.add_response("ok", "_OK")
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

class EditorApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.editor")
        self.connect("activate", self.on_activate)
    
    def on_activate(self, app):
        self.win = EditorWindow(application=app)
        self.win.present()
        
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.show_about)
        self.add_action(about_action)
    
    def show_about(self, *args):
        about = Adw.AboutWindow(
            transient_for=self.win,
            application_name="Text Editor",
            application_icon="text-editor-symbolic",
            version="1.0",
            developers=["Your Name"],
            copyright="© 2024"
        )
        about.present()

if __name__ == "__main__":
    app = EditorApplication()
    app.run(sys.argv)
