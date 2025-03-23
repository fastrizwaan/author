import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, Pango, PangoCairo

class TextEditor(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Text Editor")
        
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

        # Size dropdown - pixel sizes directly applied via Pango
        self.size_map = ["6", "8", "10", "12", "14", "16", "18", "24", "36"]
        size_store = Gtk.StringList(strings=self.size_map)
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

        # TextView setup
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.textview.set_top_margin(10)
        self.textview.set_bottom_margin(10)
        self.buffer = self.textview.get_buffer()
        self.buffer.set_text("Type here...")

        # Create text tags for formatting
        self.bold_tag = self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.italic_tag = self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.underline_tag = self.buffer.create_tag("underline", underline=Pango.Underline.SINGLE)
        self.font_tag = self.buffer.create_tag("font")  # Updated dynamically

        # Wrap TextView in a ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.textview)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

    def apply_tag_to_selection(self, tag):
        """Apply or remove a tag to/from the current selection."""
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            if tag.get_property("weight") == Pango.Weight.BOLD:  # Example for bold
                active = self.bold_btn.get_active()
                if active:
                    self.buffer.apply_tag(tag, start, end)
                else:
                    self.buffer.remove_tag(tag, start, end)
            elif tag.get_property("style") == Pango.Style.ITALIC:  # Example for italic
                active = self.italic_btn.get_active()
                if active:
                    self.buffer.apply_tag(tag, start, end)
                else:
                    self.buffer.remove_tag(tag, start, end)
            elif tag.get_property("underline") == Pango.Underline.SINGLE:  # Example for underline
                active = self.underline_btn.get_active()
                if active:
                    self.buffer.apply_tag(tag, start, end)
                else:
                    self.buffer.remove_tag(tag, start, end)

    def on_font_family_changed(self, dropdown, _pspec):
        font_name = dropdown.get_selected_item().get_string()
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.remove_tag(self.font_tag, start, end)
            self.font_tag = self.buffer.create_tag(None, family=font_name)
            self.buffer.apply_tag(self.font_tag, start, end)
        else:
            self.font_tag = self.buffer.create_tag(None, family=font_name)

    def on_font_size_changed(self, dropdown, _pspec):
        size = int(dropdown.get_selected_item().get_string())
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.remove_tag(self.font_tag, start, end)
            self.font_tag = self.buffer.create_tag(None, size=size * Pango.SCALE)
            self.buffer.apply_tag(self.font_tag, start, end)
        else:
            self.font_tag = self.buffer.create_tag(None, size=size * Pango.SCALE)

    def on_bold_toggled(self, button):
        self.apply_tag_to_selection(self.bold_tag)

    def on_italic_toggled(self, button):
        self.apply_tag_to_selection(self.italic_tag)

    def on_underline_toggled(self, button):
        self.apply_tag_to_selection(self.underline_tag)

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.TextEditor")
    
    def do_activate(self):
        window = TextEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
