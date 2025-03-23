import gi
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit', '6.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, WebKit, Pango, PangoCairo

class WebEditor(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="WebKit Editor")
        
        # Main layout
        self.set_default_size(800, 600)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.box)

        # Toolbar with Adwaita styling
        self.header = Adw.HeaderBar()
        self.box.append(self.header)

        # Text style group
        text_style_group = Gtk.Box(spacing=6)
        self.header.pack_start(text_style_group)

        # Font dropdown using PangoCairo
        font_map = PangoCairo.FontMap.get_default()
        families = font_map.list_families()
        font_names = sorted([family.get_name() for family in families])
        font_store = Gtk.StringList(strings=font_names)
        self.font_dropdown = Gtk.DropDown(model=font_store)
        default_font_index = font_names.index("Sans") if "Sans" in font_names else 0
        self.font_dropdown.set_selected(default_font_index)
        self.font_dropdown.connect("notify::selected", self.on_font_family_changed)
        self.font_dropdown.add_css_class("flat")
        text_style_group.append(self.font_dropdown)

        # Size dropdown - using WebKit-compatible size indices mapped to pixels
        self.size_map = {
            "6": "1",   # xx-small
            "8": "1",
            "10": "2",  # small
            "12": "3",  # medium
            "14": "3",
            "16": "4",  # large
            "18": "4",
            "24": "5",  # x-large
            "36": "6"   # xx-large
            # Note: WebKit uses 1-7 scale, 7 would be xxx-large
        }
        size_store = Gtk.StringList(strings=list(self.size_map.keys()))
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(3)  # Default to 12
        self.size_dropdown.connect("notify::selected", self.on_font_size_changed)
        self.size_dropdown.add_css_class("flat")
        text_style_group.append(self.size_dropdown)

        # Text format group
        text_format_group = Gtk.Box(spacing=6)
        self.header.pack_start(text_format_group)

        # Formatting buttons with Adwaita icons
        self.bold_btn = Gtk.ToggleButton(icon_name="format-text-bold-symbolic")
        self.bold_btn.add_css_class("flat")
        self.bold_btn.connect("toggled", self.on_bold_toggled)
        text_format_group.append(self.bold_btn)

        self.italic_btn = Gtk.ToggleButton(icon_name="format-text-italic-symbolic")
        self.italic_btn.add_css_class("flat")
        self.italic_btn.connect("toggled", self.on_italic_toggled)
        text_format_group.append(self.italic_btn)

        self.underline_btn = Gtk.ToggleButton(icon_name="format-text-underline-symbolic")
        self.underline_btn.add_css_class("flat")
        self.underline_btn.connect("toggled", self.on_underline_toggled)
        text_format_group.append(self.underline_btn)

        # Source button
        self.source_btn = Gtk.Button(label="Source")
        self.source_btn.add_css_class("flat")
        self.source_btn.connect("clicked", self.on_source_clicked)
        self.header.pack_end(self.source_btn)

        # WebKit editor
        self.webview = WebKit.WebView()
        settings = self.webview.get_settings()
        settings.set_enable_developer_extras(True)
        self.webview.set_settings(settings)
        self.webview.set_editable(True)
        
        # Wrap WebView in a ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.webview)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

        # Initial HTML
        initial_html = """
        <html>
            <head>
                <style>
                    body { 
                        padding: 10px; 
                        margin: 0; 
                        min-height: 100vh;
                    }
                </style>
            </head>
            <body contenteditable="true">
                <p>Type here...</p>
            </body>
        </html>
        """
        self.webview.load_html(initial_html, "")

    def on_font_family_changed(self, dropdown, _pspec):
        font_name = dropdown.get_selected_item().get_string()
        js = f"document.execCommand('fontName', false, '{font_name}');"
        self.webview.evaluate_javascript(js, -1, None, None, None, None)

    def on_font_size_changed(self, dropdown, _pspec):
        pixel_size = dropdown.get_selected_item().get_string()
        webkit_size = self.size_map[pixel_size]  # Convert to WebKit size index
        js = f"document.execCommand('fontSize', false, '{webkit_size}');"
        self.webview.evaluate_javascript(js, -1, None, None, None, None)

    def on_bold_toggled(self, button):
        js = "document.execCommand('bold', false, null);"
        self.webview.evaluate_javascript(js, -1, None, None, None, None)

    def on_italic_toggled(self, button):
        js = "document.execCommand('italic', false, null);"
        self.webview.evaluate_javascript(js, -1, None, None, None, None)

    def on_underline_toggled(self, button):
        js = "document.execCommand('underline', false, null);"
        self.webview.evaluate_javascript(js, -1, None, None, None, None)

    def on_source_clicked(self, button):
        def js_finished(webview, result, user_data=None):
            value = webview.evaluate_javascript_finish(result)
            html = value.to_string()
            source_window = Adw.Window(title="HTML Source")
            source_window.set_default_size(600, 400)
            
            text_view = Gtk.TextView()
            text_view.set_editable(True)
            text_view.set_monospace(True)
            text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            buffer = text_view.get_buffer()
            buffer.set_text(html)
            
            source_header = Adw.HeaderBar()
            source_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            source_box.append(source_header)
            
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_child(text_view)
            scrolled.set_vexpand(True)
            source_box.append(scrolled)
            
            source_window.set_content(source_box)
            source_window.present()

        self.webview.evaluate_javascript("document.documentElement.outerHTML", -1, None, None, None, js_finished)

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.WebEditor")
    
    def do_activate(self):
        window = WebEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
