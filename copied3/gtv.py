wwimport gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, Gio, Pango, Adw
import sys

class RichTextEditor(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Rich Text Editor")
        self.set_default_size(800, 600)

        # Text buffer and view
        self.text_buffer = Gtk.TextBuffer()
        self.text_view = Gtk.TextView.new_with_buffer(self.text_buffer)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_vexpand(True)

        # Track current formatting
        self.current_tags = {}
        self.current_font = "Sans"
        self.current_size = 12

        # Create formatting tags
        self.create_formatting_tags()

        # Connect signals for continuous formatting
        self.text_buffer.connect("insert-text", self.on_text_inserted)
        self.text_buffer.connect("changed", self.update_toggle_states)

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # HeaderBar with first toolbar
        header = Adw.HeaderBar()
        toolbar1 = self.create_toolbar1()
        header.pack_start(toolbar1)
        main_box.append(header)

        # Second toolbar
        toolbar2 = self.create_toolbar2()
        toolbar2.get_style_context().add_class("toolbar")
        main_box.append(toolbar2)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.text_view)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

        self.set_content(main_box)
        self.current_file = None

    def create_formatting_tags(self):
        self.tags = {}
        tag_table = self.text_buffer.get_tag_table()
        
        for name, props in {
            "bold": {"weight": Pango.Weight.BOLD},
            "italic": {"style": Pango.Style.ITALIC},
            "underline": {"underline": Pango.Underline.SINGLE},
            "strike": {"strikethrough": True},
            "left": {"justification": Gtk.Justification.LEFT},
            "center": {"justification": Gtk.Justification.CENTER},
            "right": {"justification": Gtk.Justification.RIGHT},
            "justify": {"justification": Gtk.Justification.FILL},
            "bullet": {"left-margin": 20, "indent": -20},
            "numbered": {"left-margin": 20, "indent": -20}
        }.items():
            tag = Gtk.TextTag.new(name)
            for prop, value in props.items():
                tag.set_property(prop, value)
            tag_table.add(tag)
            self.tags[name] = tag

    def create_toolbar1(self):
        toolbar = Gtk.Box(spacing=6)
        
        for icon, callback in [
            ("document-new", self.on_new_clicked),
            ("document-open", self.on_open_clicked),
            ("document-save", self.on_save_clicked),
            ("edit-cut", self.on_cut_clicked),
            ("edit-copy", self.on_copy_clicked),
            ("edit-paste", self.on_paste_clicked),
            ("edit-undo", self.on_undo_clicked),
            ("edit-redo", self.on_redo_clicked)
        ]:
            btn = Gtk.Button.new_from_icon_name(icon)
            btn.connect("clicked", callback)
            toolbar.append(btn)
        
        return toolbar

    def create_toolbar2(self):
        toolbar = Gtk.Box(spacing=6)
        
        # Paragraph style
        self.style_combo = Gtk.ComboBoxText()
        for style in ["Normal", "Heading 1", "Heading 2"]:
            self.style_combo.append_text(style)
        self.style_combo.set_active(0)
        self.style_combo.connect("changed", self.on_style_changed)
        toolbar.append(self.style_combo)

        # Font face
        self.font_combo = Gtk.ComboBoxText()
        for font in ["Sans", "Serif", "Monospace"]:
            self.font_combo.append_text(font)
        self.font_combo.set_active(0)
        self.font_combo.connect("changed", self.on_font_changed)
        toolbar.append(self.font_combo)

        # Font size
        self.size_combo = Gtk.ComboBoxText()
        for size in ["8", "10", "12", "14", "18", "24"]:
            self.size_combo.append_text(size)
        self.size_combo.set_active(2)  # Default 12
        self.size_combo.connect("changed", self.on_size_changed)
        toolbar.append(self.size_combo)

        # Formatting buttons
        self.bold_btn = Gtk.ToggleButton(label="B")
        self.bold_btn.connect("toggled", self.on_format_toggled, "bold")
        toolbar.append(self.bold_btn)

        self.italic_btn = Gtk.ToggleButton(label="I")
        self.italic_btn.connect("toggled", self.on_format_toggled, "italic")
        toolbar.append(self.italic_btn)

        self.underline_btn = Gtk.ToggleButton(label="U")
        self.underline_btn.connect("toggled", self.on_format_toggled, "underline")
        toolbar.append(self.underline_btn)

        self.strike_btn = Gtk.ToggleButton(label="S")
        self.strike_btn.connect("toggled", self.on_format_toggled, "strike")
        toolbar.append(self.strike_btn)

        self.bullet_btn = Gtk.ToggleButton(label="•")
        self.bullet_btn.connect("toggled", self.on_format_toggled, "bullet")
        toolbar.append(self.bullet_btn)

        self.numbered_btn = Gtk.ToggleButton(label="1.")
        self.numbered_btn.connect("toggled", self.on_format_toggled, "numbered")
        toolbar.append(self.numbered_btn)

        # Alignment buttons
        align_group = None
        for icon, tag in [
            ("format-justify-left", "left"),
            ("format-justify-center", "center"),
            ("format-justify-right", "right"),
            ("format-justify-fill", "justify")
        ]:
            btn = Gtk.ToggleButton()
            btn.set_child(Gtk.Image.new_from_icon_name(icon))
            btn.connect("toggled", self.on_format_toggled, tag)
            if not align_group:
                align_group = btn
            else:
                btn.set_group(align_group)
            toolbar.append(btn)
        
        return toolbar

    # Toolbar 1 handlers
    def on_new_clicked(self, button):
        self.text_buffer.set_text("")
        self.current_file = None

    def on_open_clicked(self, button):
        dialog = Gtk.FileChooserNative(
            title="Open File",
            action=Gtk.FileChooserAction.OPEN,
            accept_label="Open",
            cancel_label="Cancel"
        )
        dialog.set_transient_for(self)
        dialog.connect("response", self.on_open_response)
        dialog.show()

    def on_open_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                content = file.load_contents(None)[1].decode()
                self.text_buffer.set_text(self.html_to_text(content))
                self.current_file = file
        dialog.destroy()

    def on_save_clicked(self, button):
        if not self.current_file:
            dialog = Gtk.FileChooserNative(
                title="Save File",
                action=Gtk.FileChooserAction.SAVE,
                accept_label="Save",
                cancel_label="Cancel"
            )
            dialog.set_transient_for(self)
            dialog.connect("response", self.on_save_response)
            dialog.show()
        else:
            self.save_to_file(self.current_file)

    def on_save_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self.save_to_file(file)
                self.current_file = file
        dialog.destroy()

    def save_to_file(self, file):
        start, end = self.text_buffer.get_bounds()
        text = self.text_to_html(start, end)
        file.replace_contents(text.encode(), None, False, Gio.FileCreateFlags.NONE, None)

    def on_cut_clicked(self, button):
        clipboard = self.get_clipboard()
        self.text_buffer.cut_clipboard(clipboard, True)

    def on_copy_clicked(self, button):
        clipboard = self.get_clipboard()
        self.text_buffer.copy_clipboard(clipboard)

    def on_paste_clicked(self, button):
        clipboard = self.get_clipboard()
        self.text_buffer.paste_clipboard(clipboard, None, True)

    def on_undo_clicked(self, button):
        self.text_buffer.undo()

    def on_redo_clicked(self, button):
        self.text_buffer.redo()

    # Toolbar 2 handlers
    def on_style_changed(self, combo):
        style = combo.get_active_text()
        size = {"Normal": 12, "Heading 1": 24, "Heading 2": 18}[style]
        self.current_size = size
        self.apply_current_formatting()

    def on_font_changed(self, combo):
        self.current_font = combo.get_active_text()
        self.apply_current_formatting()

    def on_size_changed(self, combo):
        self.current_size = int(combo.get_active_text())
        self.apply_current_formatting()

    def on_format_toggled(self, button, tag_name):
        if button.get_active():
            self.current_tags[tag_name] = self.tags[tag_name]
        elif tag_name in self.current_tags:
            del self.current_tags[tag_name]
        self.apply_current_formatting()

    # Formatting helpers
    def on_text_inserted(self, buffer, location, text, length):
        start = buffer.get_iter_at_offset(location.get_offset() - length)
        end = location
        for tag in self.current_tags.values():
            buffer.apply_tag(tag, start, end)
        font_tag = buffer.create_tag(None, 
                                   family=self.current_font,
                                   size_points=self.current_size)
        buffer.apply_tag(font_tag, start, end)
        
        # Add bullet/numbered list markers
        if "bullet" in self.current_tags and text == "\n":
            buffer.insert(location, "• ")
        elif "numbered" in self.current_tags and text == "\n":
            buffer.insert(location, "1. ")

    def apply_current_formatting(self):
        if self.text_buffer.get_has_selection():
            start, end = self.text_buffer.get_selection_bounds()
            # Remove existing tags
            for tag in self.tags.values():
                self.text_buffer.remove_tag(tag, start, end)
            self.text_buffer.remove_all_tags(start, end)
            # Apply current tags
            for tag in self.current_tags.values():
                self.text_buffer.apply_tag(tag, start, end)
            font_tag = self.text_buffer.create_tag(None,
                                                 family=self.current_font,
                                                 size_points=self.current_size)
            self.text_buffer.apply_tag(font_tag, start, end)

    def update_toggle_states(self, buffer):
        if not self.text_buffer.get_has_selection():
            return
        start, end = self.text_buffer.get_selection_bounds()
        for btn, tag_name in [
            (self.bold_btn, "bold"),
            (self.italic_btn, "italic"),
            (self.underline_btn, "underline"),
            (self.strike_btn, "strike"),
            (self.bullet_btn, "bullet"),
            (self.numbered_btn, "numbered")
        ]:
            btn.set_active(self.text_buffer.get_iter_has_tag(start, self.tags[tag_name]))

    # HTML conversion
    def text_to_html(self, start, end):
        text = "<html><body>"
        iter = start.copy()
        while iter.compare(end) < 0:
            tags = iter.get_tags()
            tag_names = [tag.get_property("name") for tag in tags if tag.get_property("name")]
            
            # Open tags
            if "bold" in tag_names: text += "<b>"
            if "italic" in tag_names: text += "<i>"
            if "underline" in tag_names: text += "<u>"
            if "strike" in tag_names: text += "<s>"
            if "bullet" in tag_names: text += "<ul><li>"
            if "numbered" in tag_names: text += "<ol><li>"
            
            # Get text and font properties
            char = iter.get_char()
            text += char.replace("\n", "<br>")
            
            # Close tags
            if "numbered" in tag_names: text += "</li></ol>"
            if "bullet" in tag_names: text += "</li></ul>"
            if "strike" in tag_names: text += "</s>"
            if "underline" in tag_names: text += "</u>"
            if "italic" in tag_names: text += "</i>"
            if "bold" in tag_names: text += "</b>"
            
            iter.forward_char()
        
        text += "</body></html>"
        return text

    def html_to_text(self, html):
        # Simple HTML to text conversion (for loading)
        return html.replace("<html>", "").replace("</html>", "").replace("<body>", "").replace("</body>", "") \
                   .replace("<br>", "\n").replace("<b>", "").replace("</b>", "") \
                   .replace("<i>", "").replace("</i>", "").replace("<u>", "").replace("</u>", "") \
                   .replace("<s>", "").replace("</s>", "").replace("<ul><li>", "• ").replace("</li></ul>", "") \
                   .replace("<ol><li>", "1. ").replace("</li></ol>", "")

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.RichTextEditor")
        
    def do_activate(self):
        window = RichTextEditor(self)
        window.present()

def main():
    app = EditorApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()
