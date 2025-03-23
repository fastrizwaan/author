import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, Pango, PangoCairo, Gio

class RichTextEditor(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Rich Text Editor")
        
        self.set_default_size(800, 600)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.box.append(self.header)

        # Save button
        save_btn = Gtk.Button(icon_name="document-save-symbolic")
        save_btn.add_css_class("flat")
        save_btn.connect("clicked", self.on_save_clicked)
        self.header.pack_end(save_btn)

        # Toolbar
        toolbar = Gtk.Box(spacing=6)
        self.header.pack_start(toolbar)

        # Bold button
        self.bold_btn = Gtk.ToggleButton(icon_name="format-text-bold-symbolic")
        self.bold_btn.add_css_class("flat")
        self.bold_btn.connect("toggled", self.on_bold_toggled)
        toolbar.append(self.bold_btn)

        # Italic button
        self.italic_btn = Gtk.ToggleButton(icon_name="format-text-italic-symbolic")
        self.italic_btn.add_css_class("flat")
        self.italic_btn.connect("toggled", self.on_italic_toggled)
        toolbar.append(self.italic_btn)

        # Heading dropdown
        headings = ["Normal", "Heading 1", "Heading 2", "Heading 3"]
        heading_store = Gtk.StringList(strings=headings)
        self.heading_dropdown = Gtk.DropDown(model=heading_store)
        self.heading_dropdown.set_selected(0)
        self.heading_dropdown.connect("notify::selected", self.on_heading_changed)
        self.heading_dropdown.add_css_class("flat")
        toolbar.append(self.heading_dropdown)

        # TextView setup
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.textview.set_top_margin(10)
        self.textview.set_bottom_margin(10)
        self.buffer = self.textview.get_buffer()
        self.buffer.set_text("Welcome to Rich Text Editor\n\nType your text here...")

        # Text tags for rich text display
        self.bold_tag = self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.italic_tag = self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.h1_tag = self.buffer.create_tag("h1", size=24 * Pango.SCALE)
        self.h2_tag = self.buffer.create_tag("h2", size=18 * Pango.SCALE)
        self.h3_tag = self.buffer.create_tag("h3", size=14 * Pango.SCALE)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.textview)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

    def apply_tag_to_selection(self, tag):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            if tag == self.bold_tag:
                active = self.bold_btn.get_active()
                if active:
                    self.buffer.apply_tag(tag, start, end)
                else:
                    self.buffer.remove_tag(tag, start, end)
            elif tag == self.italic_tag:
                active = self.italic_btn.get_active()
                if active:
                    self.buffer.apply_tag(tag, start, end)
                else:
                    self.buffer.remove_tag(tag, start, end)

    def on_bold_toggled(self, button):
        self.apply_tag_to_selection(self.bold_tag)

    def on_italic_toggled(self, button):
        self.apply_tag_to_selection(self.italic_tag)

    def on_heading_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected()
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            # Remove existing heading tags
            for tag in [self.h1_tag, self.h2_tag, self.h3_tag]:
                self.buffer.remove_tag(tag, start, end)
            # Apply new heading tag
            if selected == 1:  # Heading 1
                self.buffer.apply_tag(self.h1_tag, start, end)
            elif selected == 2:  # Heading 2
                self.buffer.apply_tag(self.h2_tag, start, end)
            elif selected == 3:  # Heading 3
                self.buffer.apply_tag(self.h3_tag, start, end)

    def on_save_clicked(self, button):
        file_chooser = Gtk.FileChooserNative(
            title="Save as Markdown",
            action=Gtk.FileChooserAction.SAVE,
            accept_label="_Save",
            cancel_label="_Cancel",
            transient_for=self,
        )
        file_chooser.set_current_name("document.md")
        file_chooser.connect("response", self.on_save_response)
        file_chooser.show()

    def on_save_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            markdown_text = self.convert_to_markdown()
            try:
                file.replace_contents(
                    markdown_text.encode('utf-8'),
                    None, False, Gio.FileCreateFlags.NONE, None
                )
            except Exception as e:
                print(f"Error saving file: {e}")
        dialog.destroy()

    def convert_to_markdown(self):
        """Convert rich text buffer to Markdown."""
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, False)
        markdown = []
        current_line = ""
        offset = 0

        while start.forward_to_tag_toggle(None) and start.compare(end) < 0:
            segment_end = start.copy()
            if not segment_end.forward_to_tag_toggle(None):
                segment_end = end.copy()
            
            segment_text = self.buffer.get_text(start, segment_end, False)
            tags = start.get_tags()

            # Handle headings
            if self.h1_tag in tags:
                if current_line:
                    markdown.append(current_line)
                markdown.append(f"# {segment_text}")
                current_line = ""
            elif self.h2_tag in tags:
                if current_line:
                    markdown.append(current_line)
                markdown.append(f"## {segment_text}")
                current_line = ""
            elif self.h3_tag in tags:
                if current_line:
                    markdown.append(current_line)
                markdown.append(f"### {segment_text}")
                current_line = ""
            else:
                # Handle inline formatting
                if self.bold_tag in tags and self.italic_tag in tags:
                    current_line += f"***{segment_text}***"
                elif self.bold_tag in tags:
                    current_line += f"**{segment_text}**"
                elif self.italic_tag in tags:
                    current_line += f"*{segment_text}*"
                else:
                    current_line += segment_text

            # Check for line breaks
            if segment_text.endswith("\n"):
                markdown.append(current_line)
                current_line = ""
            
            start = segment_end

        if current_line:
            markdown.append(current_line)
        
        return "\n".join(markdown)

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.RichTextEditor")
    
    def do_activate(self):
        window = RichTextEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
