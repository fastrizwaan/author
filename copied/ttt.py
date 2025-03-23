import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Adw, Pango

class TextEditor(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Text Editor")
        
        self.set_default_size(800, 600)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.box)

        # Toolbar
        self.header = Adw.HeaderBar()
        self.box.append(self.header)

        # Text style group
        text_style_group = Gtk.Box(spacing=6)
        self.header.pack_start(text_style_group)

        # Font dropdown
        context = self.get_pango_context()
        font_map = context.get_font_map()
        families = font_map.list_families()
        font_names = sorted([family.get_name() for family in families])
        font_store = Gtk.StringList(strings=font_names)
        self.font_dropdown = Gtk.DropDown(model=font_store)
        self.font_dropdown.set_selected(font_names.index("Sans") if "Sans" in font_names else 0)
        self.font_dropdown.connect("notify::selected", self.on_font_changed)
        text_style_group.append(self.font_dropdown)

        # Size dropdown
        self.size_map = {"6": 6, "8": 8, "10": 10, "12": 12, "14": 14, "16": 16, "18": 18, "24": 24, "36": 36}
        size_store = Gtk.StringList(strings=list(self.size_map.keys()))
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(3)  # Default to 12
        self.size_dropdown.connect("notify::selected", self.on_size_changed)
        text_style_group.append(self.size_dropdown)

        # Formatting buttons
        text_format_group = Gtk.Box(spacing=6)
        self.header.pack_start(text_format_group)

        self.bold_btn = Gtk.ToggleButton(icon_name="format-text-bold-symbolic")
        self.bold_btn.connect("toggled", self.on_bold_toggled)
        text_format_group.append(self.bold_btn)

        self.italic_btn = Gtk.ToggleButton(icon_name="format-text-italic-symbolic")
        self.italic_btn.connect("toggled", self.on_italic_toggled)
        text_format_group.append(self.italic_btn)

        self.underline_btn = Gtk.ToggleButton(icon_name="format-text-underline-symbolic")
        self.underline_btn.connect("toggled", self.on_underline_toggled)
        text_format_group.append(self.underline_btn)

        # Text view
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.buffer = self.textview.get_buffer()
        self.buffer.set_text("Type here...")

        # Tag table and predefined tags
        self.tag_table = self.buffer.get_tag_table()
        self.font_tags = {}
        self.size_tags = {}

        self.tag_bold = Gtk.TextTag.new("bold")
        self.tag_bold.set_property("weight", Pango.Weight.BOLD)
        self.tag_table.add(self.tag_bold)

        self.tag_italic = Gtk.TextTag.new("italic")
        self.tag_italic.set_property("style", Pango.Style.ITALIC)
        self.tag_table.add(self.tag_italic)

        self.tag_underline = Gtk.TextTag.new("underline")
        self.tag_underline.set_property("underline", Pango.Underline.SINGLE)
        self.tag_table.add(self.tag_underline)

        # Populate font and size tags
        for font_name in font_names:
            tag = Gtk.TextTag.new(f"font-{font_name}")
            tag.set_property("family", font_name)
            self.tag_table.add(tag)
            self.font_tags[font_name] = tag

        for size in self.size_map.values():
            tag = Gtk.TextTag.new(f"size-{size}")
            tag.set_property("size", size * Pango.SCALE)
            self.tag_table.add(tag)
            self.size_tags[size] = tag

        # Scrolled window for text view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.textview)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

        # Connect signals
        self.buffer.connect("mark-set", self.update_button_states)

    def apply_or_remove_tag(self, tag, apply):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            # Apply or remove tag to selected text
            start, end = bounds
            if apply:
                self.buffer.apply_tag(tag, start, end)
            else:
                self.buffer.remove_tag(tag, start, end)
        else:
            # Apply tag at cursor position for new text
            cursor_mark = self.buffer.get_insert()
            cursor_iter = self.buffer.get_iter_at_mark(cursor_mark)
            if apply:
                self.buffer.apply_tag(tag, cursor_iter, cursor_iter)
            else:
                self.buffer.remove_tag(tag, cursor_iter, cursor_iter)

    def on_font_changed(self, dropdown, _pspec):
        font_name = dropdown.get_selected_item().get_string()
        tag = self.font_tags[font_name]
        self.apply_or_remove_tag(tag, True)

    def on_size_changed(self, dropdown, _pspec):
        size = self.size_map[dropdown.get_selected_item().get_string()]
        tag = self.size_tags[size]
        self.apply_or_remove_tag(tag, True)

    def on_bold_toggled(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            all_bold = all(self.buffer.get_iter_at_offset(i).has_tag(self.tag_bold) for i in range(start.get_offset(), end.get_offset()))
            self.apply_or_remove_tag(self.tag_bold, not all_bold)
        else:
            self.apply_or_remove_tag(self.tag_bold, button.get_active())

    def on_italic_toggled(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            all_italic = all(self.buffer.get_iter_at_offset(i).has_tag(self.tag_italic) for i in range(start.get_offset(), end.get_offset()))
            self.apply_or_remove_tag(self.tag_italic, not all_italic)
        else:
            self.apply_or_remove_tag(self.tag_italic, button.get_active())

    def on_underline_toggled(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            all_underline = all(self.buffer.get_iter_at_offset(i).has_tag(self.tag_underline) for i in range(start.get_offset(), end.get_offset()))
            self.apply_or_remove_tag(self.tag_underline, not all_underline)
        else:
            self.apply_or_remove_tag(self.tag_underline, button.get_active())

    def update_button_states(self, buffer, iter, mark):
        bounds = buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            # Check if formatting is uniform across the selection
            bold_states = [buffer.get_iter_at_offset(i).has_tag(self.tag_bold) for i in range(start.get_offset(), end.get_offset())]
            italic_states = [buffer.get_iter_at_offset(i).has_tag(self.tag_italic) for i in range(start.get_offset(), end.get_offset())]
            underline_states = [buffer.get_iter_at_offset(i).has_tag(self.tag_underline) for i in range(start.get_offset(), end.get_offset())]

            # Set button states: active if all true, inactive if mixed or all false
            self.bold_btn.set_active(all(bold_states) and any(bold_states))
            self.italic_btn.set_active(all(italic_states) and any(italic_states))
            self.underline_btn.set_active(all(underline_states) and any(underline_states))
        else:
            # No selection, check tags at cursor position
            cursor_mark = buffer.get_insert()
            cursor_iter = buffer.get_iter_at_mark(cursor_mark)
            self.bold_btn.set_active(cursor_iter.has_tag(self.tag_bold))
            self.italic_btn.set_active(cursor_iter.has_tag(self.tag_italic))
            self.underline_btn.set_active(cursor_iter.has_tag(self.tag_underline))

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.TextEditor")

    def do_activate(self):
        window = TextEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
