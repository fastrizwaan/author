import gi
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, WebKit2, Gio

class HTMLEditor(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.example.htmleditor")

    def do_activate(self):
        win = EditorWindow(application=self)
        win.present()

class EditorWindow(Gtk.Window):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("HTML Editor")
        self.set_default_size(800, 600)

        # Header bar setup
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        # WebKit WebView for editing
        self.webview = WebKit2.WebView()
        self.webview.set_editable(True)
        self.set_child(self.webview)

        # Initial HTML content
        initial_html = """
        <html>
        <head>
        <title>Untitled</title>
        </head>
        <body>
        <p>Start editing here...</p>
        </body>
        </html>
        """
        self.webview.load_html(initial_html, None)

        # Formatting buttons
        bold_button = Gtk.Button(icon_name="format-text-bold-symbolic")
        bold_button.connect("clicked", self.on_bold_clicked)
        header.pack_start(bold_button)

        italic_button = Gtk.Button(icon_name="format-text-italic-symbolic")
        italic_button.connect("clicked", self.on_italic_clicked)
        header.pack_start(italic_button)

        # Insert buttons
        image_button = Gtk.Button(label="Insert Image")
        image_button.connect("clicked", self.on_insert_image_clicked)
        header.pack_start(image_button)

        link_button = Gtk.Button(label="Insert Link")
        link_button.connect("clicked", self.on_insert_link_clicked)
        header.pack_start(link_button)

        # File and preview buttons
        open_button = Gtk.Button(label="Open")
        open_button.connect("clicked", self.on_open_clicked)
        header.pack_start(open_button)

        save_button = Gtk.Button(label="Save")
        save_button.connect("clicked", self.on_save_clicked)
        header.pack_end(save_button)

        preview_button = Gtk.Button(label="Preview")
        preview_button.connect("clicked", self.on_preview_clicked)
        header.pack_end(preview_button)

    # Formatting handlers
    def on_bold_clicked(self, button):
        self.webview.execute_editing_command("Bold")

    def on_italic_clicked(self, button):
        self.webview.execute_editing_command("Italic")

    # Insert image
    def on_insert_image_clicked(self, button):
        dialog = Gtk.Dialog(title="Insert Image", parent=self, modal=True)
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Insert", Gtk.ResponseType.ACCEPT)
        content_area = dialog.get_content_area()
        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("Enter image URL")
        content_area.append(url_entry)
        dialog.connect("response", self.on_insert_image_response, url_entry)
        dialog.show()

    def on_insert_image_response(self, dialog, response, url_entry):
        if response == Gtk.ResponseType.ACCEPT:
            url = url_entry.get_text()
            if url:
                self.webview.execute_editing_command_with_argument("InsertImage", url)
        dialog.destroy()

    # Insert link
    def on_insert_link_clicked(self, button):
        dialog = Gtk.Dialog(title="Insert Link", parent=self, modal=True)
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Insert", Gtk.ResponseType.ACCEPT)
        content_area = dialog.get_content_area()
        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("Enter link URL")
        content_area.append(url_entry)
        dialog.connect("response", self.on_insert_link_response, url_entry)
        dialog.show()

    def on_insert_link_response(self, dialog, response, url_entry):
        if response == Gtk.ResponseType.ACCEPT:
            url = url_entry.get_text()
            if url:
                self.webview.execute_editing_command_with_argument("CreateLink", url)
        dialog.destroy()

    # Open file
    def on_open_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Open HTML File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self.on_open_response)
        dialog.show()

    def on_open_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                content = file.load_contents(None)[1].decode('utf-8')
                self.webview.load_html(content, None)
        dialog.destroy()

    # Save file
    def on_save_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Save HTML File",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Save", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self.on_save_response)
        dialog.show()

    def on_save_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self.webview.run_javascript(
                    "document.documentElement.outerHTML",
                    None,
                    self.on_get_html_for_save,
                    file
                )
        else:
            dialog.destroy()

    def on_get_html_for_save(self, webview, result, file):
        js_result = webview.run_javascript_finish(result)
        if js_result:
            html = js_result.get_js_value().to_string()
            file.replace_contents(html.encode('utf-8'), None, False, Gio.FileCreateFlags.NONE, None)

    # Preview
    def on_preview_clicked(self, button):
        preview_window = Gtk.Window(title="Preview")
        preview_window.set_default_size(600, 400)
        preview_webview = WebKit2.WebView()
        preview_window.set_child(preview_webview)
        self.webview.run_javascript(
            "document.documentElement.outerHTML",
            None,
            self.on_get_html_for_preview,
            preview_webview
        )
        preview_window.present()

    def on_get_html_for_preview(self, webview, result, preview_webview):
        js_result = webview.run_javascript_finish(result)
        if js_result:
            html = js_result.get_js_value().to_string()
            preview_webview.load_html(html, None)

if __name__ == "__main__":
    app = HTMLEditor()
    app.run()
