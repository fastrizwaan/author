import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, Pango, PangoCairo, Gio

class MarkdownEditor(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Markdown Editor")
        
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
        headings = ["Normal", "#", "##", "###"]
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
        self.buffer.set_text("# Welcome to Markdown Editor\n\nType your **markdown** here...")
        self.buffer.connect("changed", self.on_buffer_changed)

        # Text tags for formatting
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

        # Initial markdown rendering
        self.render_markdown()

    def apply_tag_to_selection(self, tag, markdown_syntax):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            text = self.buffer.get_text(start, end, False)
            if tag in [self.bold_tag, self.italic_tag]:
                active = self.bold_btn.get_active() if tag == self.bold_tag else self.italic_btn.get_active()
                if active:
                    self.buffer.delete(start, end)
                    self.buffer.insert(start, f"{markdown_syntax}{text}{markdown_syntax}")
                else:
                    self.buffer.remove_tag(tag, start, end)
            self.render_markdown()

    def on_bold_toggled(self, button):
        self.apply_tag_to_selection(self.bold_tag, "**")

    def on_italic_toggled(self, button):
        self.apply_tag_to_selection(self.italic_tag, "*")

    def on_heading_changed(self, dropdown, _pspec):
        selected = dropdown.get_selected()
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            text = self.buffer.get_text(start, end, False)
            self.buffer.delete(start, end)
            if selected == 0:  # Normal text
                self.buffer.insert(start, text)
            elif selected == 1:  # H1
                self.buffer.insert(start, f"# {text}")
            elif selected == 2:  # H2
                self.buffer.insert(start, f"## {text}")
            elif selected == 3:  # H3
                self.buffer.insert(start, f"### {text}")
            self.render_markdown()

    def on_buffer_changed(self, buffer):
        self.render_markdown()

    def render_markdown(self):
        """Basic real-time Markdown rendering."""
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, False)

        # Remove all tags first
        self.buffer.remove_all_tags(start, end)

        # Apply Markdown formatting
        lines = text.split("\n")
        offset = 0
        for line in lines:
            line_start = self.buffer.get_iter_at_offset(offset)
            line_end = self.buffer.get_iter_at_offset(offset + len(line))

            if line.startswith("### "):
                self.buffer.apply_tag(self.h3_tag, line_start, line_end)
            elif line.startswith("## "):
                self.buffer.apply_tag(self.h2_tag, line_start, line_end)
            elif line.startswith("# "):
                self.buffer.apply_tag(self.h1_tag, line_start, line_end)

            # Bold and italic within the line
            self.apply_inline_formatting(line, offset)

            offset += len(line) + 1  # +1 for newline

    def apply_inline_formatting(self, line, offset):
        """Apply bold and italic formatting within a line."""
        import re
        text = line
        for match in re.finditer(r'\*\*(.*?)\*\*', text):
            start = self.buffer.get_iter_at_offset(offset + match.start())
            end = self.buffer.get_iter_at_offset(offset + match.end())
            self.buffer.apply_tag(self.bold_tag, start, end)
        for match in re.finditer(r'\*(.*?)\*', text):
            start = self.buffer.get_iter_at_offset(offset + match.start())
            end = self.buffer.get_iter_at_offset(offset + match.end())
            self.buffer.apply_tag(self.italic_tag, start, end)

    def on_save_clicked(self, button):
        file_chooser = Gtk.FileChooserNative(
            title="Save Markdown File",
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
            start = self.buffer.get_start_iter()
            end = self.buffer.get_end_iter()
            text = self.buffer.get_text(start, end, False)
            try:
                file.replace_contents(
                    text.encode('utf-8'),
                    None, False, Gio.FileCreateFlags.NONE, None
                )
            except Exception as e:
                print(f"Error saving file: {e}")
        dialog.destroy()

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.MarkdownEditor")
    
    def do_activate(self):
        window = MarkdownEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
