```python
#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
# Use available WebKit2 version; typically "5.0" instead of "6.0".
gi.require_version("WebKit2", "5.0")
from gi.repository import Adw, Gtk, WebKit2, Gio

class MyApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.libadwaita_webkit_editor")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = Gtk.ApplicationWindow(application=app)
        win.set_title("Libadwaita GTK4 WebKit Editor")
        win.set_default_size(800, 600)

        # Create a WebKit editor with pagination CSS for US Letter.
        webview = WebKit2.WebView()
        html = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Editor</title>
<style>
  body {
    margin: 0;
    padding: 1in;
    font-size: 12pt;
    line-height: 1.5;
    column-width: 8.5in;
    column-gap: 0;
    -webkit-column-width: 8.5in;
    -webkit-column-gap: 0;
  }
  @page {
    size: 8.5in 11in;
    margin: 1in;
  }
  div[contenteditable] {
    outline: none;
  }
</style>
</head>
<body contenteditable="true">
  <p>Edit your text here...</p>
</body>
</html>
"""
        webview.load_html(html, "file:///")
        win.set_child(webview)
        win.present()

app = MyApp()
app.run(None)
```
