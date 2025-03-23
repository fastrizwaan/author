import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, Pango, PangoCairo, GdkPixbuf

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

        # Font dropdown
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

        # Size dropdown
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

        # Formatting buttons
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

        # Additional feature buttons
        feature_group = Gtk.Box(spacing=6)
        self.header.pack_end(feature_group)

        self.insert_text_btn = Gtk.Button(icon_name="insert-text-symbolic")
        self.insert_text_btn.add_css_class("flat")
        self.insert_text_btn.connect("clicked", self.on_insert_text_clicked)
        feature_group.append(self.insert_text_btn)

        self.insert_image_btn = Gtk.Button(icon_name="insert-image-symbolic")
        self.insert_image_btn.add_css_class("flat")
        self.insert_image_btn.connect("clicked", self.on_insert_image_clicked)
        feature_group.append(self.insert_image_btn)

        self.align_left_btn = Gtk.Button(icon_name="format-justify-left-symbolic")
        self.align_left_btn.add_css_class("flat")
        self.align_left_btn.connect("clicked", self.on_align_left_clicked)
        feature_group.append(self.align_left_btn)

        self.align_right_btn = Gtk.Button(icon_name="format-justify-right-symbolic")
        self.align_right_btn.add_css_class("flat")
        self.align_right_btn.connect("clicked", self.on_align_right_clicked)
        feature_group.append(self.align_right_btn)

        self.list_btn = Gtk.Button(icon_name="view-list-symbolic")
        self.list_btn.add_css_class("flat")
        self.list_btn.connect("clicked", self.on_list_clicked)
        feature_group.append(self.list_btn)

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
        self.font_tag = self.buffer.create_tag("font")
        self.left_align_tag = self.buffer.create_tag("left", justification=Gtk.Justification.LEFT)
        self.right_align_tag = self.buffer.create_tag("right", justification=Gtk.Justification.RIGHT)
        self.list_tag = self.buffer.create_tag("list", left_margin=20, indent=-10)

        # Wrap TextView in a ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.textview)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

    def apply_tag_to_selection(self, tag):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            if tag in [self.bold_tag, self.italic_tag, self.underline_tag]:
                active = (tag == self.bold_tag and self.bold_btn.get_active()) or \
                         (tag == self.italic_tag and self.italic_btn.get_active()) or \
                         (tag == self.underline_tag and self.underline_btn.get_active())
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

    def on_insert_text_clicked(self, button):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_type=Gtk.MessageType.QUESTION,
            text="Insert Text",
            secondary_text="Enter the text to insert:"
        )
        entry = Gtk.Entry()
        dialog.get_content_area().append(entry)
        dialog.connect("response", self.on_insert_text_response, entry)
        dialog.present()

    def on_insert_text_response(self, dialog, response, entry):
        if response == Gtk.ResponseType.OK:
            text = entry.get_text()
            if text:
                cursor = self.buffer.get_insert()
                self.buffer.insert_at_cursor(text, len(text))
        dialog.destroy()

    def on_insert_image_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select an Image",
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Open", Gtk.ResponseType.ACCEPT
        )
        dialog.connect("response", self.on_insert_image_response)
        dialog.present()

    def on_insert_image_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(file_path, 100, 100)  # Scale image
            anchor = self.buffer.create_child_anchor(self.buffer.get_iter_at_mark(self.buffer.get_insert()))
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            self.textview.add_child_at_anchor(image, anchor)
        dialog.destroy()

    def on_align_left_clicked(self, button):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.apply_tag(self.left_align_tag, start, end)
            self.buffer.remove_tag(self.right_align_tag, start, end)

    def on_align_right_clicked(self, button):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.apply_tag(self.right_align_tag, start, end)
            self.buffer.remove_tag(self.left_align_tag, start, end)

    def on_list_clicked(self, button):
        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.buffer.insert(cursor, "\n• ")  # Simple bullet
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.apply_tag(self.list_tag, start, end)

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.TextEditor")
    
    def do_activate(self):
        window = TextEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
