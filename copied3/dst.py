import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, Pango
import os

class TextEditorWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(800, 600)
        self.set_title("Rich Text Editor")

        # Create text buffer with undo support
        self.buffer = Gtk.TextBuffer(enable_undo=True)
        self.buffer.connect('modified-changed', self.on_modified_changed)
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Create toolbars
        self.create_header_bar()
        self.create_format_toolbar()
        
        main_box.append(self.header_bar)
        main_box.append(self.format_toolbar)

        # Text view
        scrolled_window = Gtk.ScrolledWindow()
        self.text_view = Gtk.TextView(buffer=self.buffer)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled_window.set_child(self.text_view)
        main_box.append(scrolled_window)

        # Initialize tags
        self.create_text_tags()
        self.current_font = "Sans 12"

    def create_header_bar(self):
        self.header_bar = Gtk.HeaderBar()
        
        # File operations
        new_btn = Gtk.Button(icon_name='document-new-symbolic')
        open_btn = Gtk.Button(icon_name='document-open-symbolic')
        save_btn = Gtk.Button(icon_name='document-save-symbolic')

        # Edit operations
        undo_btn = Gtk.Button(icon_name='edit-undo-symbolic')
        redo_btn = Gtk.Button(icon_name='edit-redo-symbolic')
        cut_btn = Gtk.Button(icon_name='edit-cut-symbolic')
        copy_btn = Gtk.Button(icon_name='edit-copy-symbolic')
        paste_btn = Gtk.Button(icon_name='edit-paste-symbolic')

        # Connect actions
        new_btn.connect('clicked', self.on_new)
        open_btn.connect('clicked', self.on_open)
        save_btn.connect('clicked', self.on_save)
        undo_btn.connect('clicked', lambda b: self.buffer.undo())
        redo_btn.connect('clicked', lambda b: self.buffer.redo())
        cut_btn.connect('clicked', self.on_cut)
        copy_btn.connect('clicked', self.on_copy)
        paste_btn.connect('clicked', self.on_paste)

        # Pack buttons
        self.header_bar.pack_start(new_btn)
        self.header_bar.pack_start(open_btn)
        self.header_bar.pack_start(save_btn)
        self.header_bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.header_bar.pack_start(undo_btn)
        self.header_bar.pack_start(redo_btn)
        self.header_bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.header_bar.pack_start(cut_btn)
        self.header_bar.pack_start(copy_btn)
        self.header_bar.pack_start(paste_btn)

    def create_format_toolbar(self):
        self.format_toolbar = Gtk.Box(spacing=5, margin_top=5, margin_bottom=5)

        # Font family
        self.font_btn = Gtk.FontDialogButton.new(Gtk.FontDialog())
        self.font_btn.connect('notify::font', self.on_font_changed)
        
        # Font size
        self.size_btn = Gtk.SpinButton.new_with_range(8, 72, 1)
        self.size_btn.set_value(12)
        self.size_btn.connect('value-changed', self.on_size_changed)

        # Formatting buttons
        bold_btn = Gtk.ToggleButton(icon_name='format-text-bold-symbolic')
        italic_btn = Gtk.ToggleButton(icon_name='format-text-italic-symbolic')
        underline_btn = Gtk.ToggleButton(icon_name='format-text-underline-symbolic')
        strike_btn = Gtk.ToggleButton(icon_name='format-text-strikethrough-symbolic')

        # Paragraph alignment
        align_left = Gtk.Button(icon_name='format-justify-left-symbolic')
        align_center = Gtk.Button(icon_name='format-justify-center-symbolic')
        align_right = Gtk.Button(icon_name='format-justify-right-symbolic')
        align_justify = Gtk.Button(icon_name='format-justify-fill-symbolic')

        # Connect format buttons
        bold_btn.connect('toggled', self.on_format_toggled, 'bold')
        italic_btn.connect('toggled', self.on_format_toggled, 'italic')
        underline_btn.connect('toggled', self.on_format_toggled, 'underline')
        strike_btn.connect('toggled', self.on_format_toggled, 'strikethrough')

        # Connect alignment
        align_left.connect('clicked', self.on_align, Gtk.Justification.LEFT)
        align_center.connect('clicked', self.on_align, Gtk.Justification.CENTER)
        align_right.connect('clicked', self.on_align, Gtk.Justification.RIGHT)
        align_justify.connect('clicked', self.on_align, Gtk.Justification.FILL)

        # Add to toolbar
        self.format_toolbar.append(self.font_btn)
        self.format_toolbar.append(self.size_btn)
        self.format_toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.format_toolbar.append(bold_btn)
        self.format_toolbar.append(italic_btn)
        self.format_toolbar.append(underline_btn)
        self.format_toolbar.append(strike_btn)
        self.format_toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.format_toolbar.append(align_left)
        self.format_toolbar.append(align_center)
        self.format_toolbar.append(align_right)
        self.format_toolbar.append(align_justify)

    def create_text_tags(self):
        # Create text buffer tags
        self.buffer.create_tag('bold', weight=Pango.Weight.BOLD)
        self.buffer.create_tag('italic', style=Pango.Style.ITALIC)
        self.buffer.create_tag('underline', underline=Pango.Underline.SINGLE)
        self.buffer.create_tag('strikethrough', strikethrough=True)
        
        # Paragraph alignment tags
        for justify in [Gtk.Justification.LEFT, Gtk.Justification.CENTER,
                       Gtk.Justification.RIGHT, Gtk.Justification.FILL]:
            self.buffer.create_tag(f'align-{justify.value_nick}', justification=justify)

    def apply_tag_to_selection(self, tag_name):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            self.buffer.apply_tag_by_name(tag_name, start, end)

    def on_format_toggled(self, button, tag_name):
        if button.get_active():
            self.apply_tag_to_selection(tag_name)

    def on_align(self, button, justification):
        iter = self.buffer.get_insert_iter()
        paragraph_start = iter.copy()
        paragraph_start.backward_sentence_start()
        paragraph_end = iter.copy()
        paragraph_end.forward_sentence_end()
        
        # Remove existing alignment tags
        for tag in self.buffer.get_tags():
            if tag.get_property('name') and tag.get_property('name').startswith('align-'):
                self.buffer.remove_tag(tag, paragraph_start, paragraph_end)
        
        # Apply new alignment
        self.buffer.apply_tag_by_name(f'align-{justification.value_nick}', paragraph_start, paragraph_end)

    def on_font_changed(self, button, _):
        font = button.get_font()
        self.current_font = font
        self.apply_font_properties()

    def on_size_changed(self, button):
        self.current_font = self.font_btn.get_font()
        self.apply_font_properties()

    def apply_font_properties(self):
        font_desc = Pango.FontDescription(self.current_font)
        font_desc.set_size(int(self.size_btn.get_value() * Pango.SCALE))
        self.text_view.override_font(font_desc)

    # File operations
    def on_new(self, button):
        self.buffer.set_text('')

    def on_open(self, button):
        dialog = Gtk.FileChooserNative(title="Open File",
                                      transient_for=self,
                                      action=Gtk.FileChooserAction.OPEN)
        dialog.connect('response', self.open_file)
        dialog.show()

    def open_file(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            contents = file.load_contents(None)
            self.buffer.set_text(contents[1].decode())

    def on_save(self, button):
        dialog = Gtk.FileChooserNative(title="Save File",
                                      transient_for=self,
                                      action=Gtk.FileChooserAction.SAVE)
        dialog.connect('response', self.save_file)
        dialog.show()

    def save_file(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            html = self.generate_html()
            file.replace_contents(html.encode(), None, False,
                                Gio.FileCreateFlags.NONE, None)

    def generate_html(self):
        html = ['<html><head><meta charset="UTF-8"></head><body>']
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        
        current_tags = set()
        open_tags = []
        
        iter = start.copy()
        while iter.compare(end) < 0:
            text = iter.get_text(end)
            newline_pos = text.find('\n')
            if newline_pos == -1:
                newline_pos = len(text)
            
            line_end = iter.copy()
            line_end.forward_chars(newline_pos)
            
            tags = iter.get_tags()
            for tag in tags:
                tag_name = tag.get_property('name')
                if tag_name and tag_name not in current_tags:
                    html.append(self.get_html_tag(tag_name, True))
                    open_tags.append(tag_name)
                    current_tags.add(tag_name)
            
            line_text = self.buffer.get_text(iter, line_end, False)
            html.append(line_text.replace('\n', '<br/>'))
            
            iter.forward_chars(newline_pos + 1)
            
            if newline_pos < len(text):
                for tag in reversed(open_tags):
                    html.append(self.get_html_tag(tag, False))
                current_tags.clear()
                open_tags.clear()
                html.append('<br/>')
        
        html.append('</body></html>')
        return ''.join(html)

    def get_html_tag(self, tag_name, open):
        tags = {
            'bold': ('<b>', '</b>'),
            'italic': ('<i>', '</i>'),
            'underline': ('<u>', '</u>'),
            'strikethrough': ('<s>', '</s>')
        }
        return tags.get(tag_name, ('', ''))[0 if open else 1]

    # Clipboard operations
    def on_cut(self, button):
        self.buffer.cut_clipboard(Gdk.Display.get_clipboard(), True)

    def on_copy(self, button):
        self.buffer.copy_clipboard(Gdk.Display.get_clipboard())

    def on_paste(self, button):
        self.buffer.paste_clipboard(Gdk.Display.get_clipboard(), None, True)

    def on_modified_changed(self, buffer):
        self.header_bar.set_title(f"{'*' if buffer.get_modified() else ''}Rich Text Editor")

class TextEditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.TextEditor')
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = TextEditorWindow(application=self)
        self.window.present()

if __name__ == '__main__':
    app = TextEditorApp()
    app.run(None)
