#!/usr/bin/env python3

import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango

class Author(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.fastrizwaan.author")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = EditorWindow(application=self)
        win.present()

class EditorWindow(Adw.ApplicationWindow):
    document_counter = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Author")
        self.set_default_size(1000, 700)

        # State tracking
        self.current_file = None
        self.is_new = True
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        scroll.set_child(self.textview)

        buffer = self.textview.get_buffer()
        buffer.connect("changed", self.on_buffer_changed)
        buffer.connect("mark-set", self.on_mark_set)

        # Formatting tags
        self.tag_bold = buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.tag_italic = buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.tag_underline = buffer.create_tag("underline", underline=Pango.Underline.SINGLE)
        self.tag_align_left = buffer.create_tag("align-left", justification=Gtk.Justification.LEFT)
        self.tag_align_center = buffer.create_tag("align-center", justification=Gtk.Justification.CENTER)

        # Toolbar
        file_group = Gtk.Box(spacing=0)
        text_format_group = Gtk.Box(spacing=2)
        align_group = Gtk.Box(spacing=0)

        toolbars_flowbox = Gtk.FlowBox()
        toolbars_flowbox.set_max_children_per_line(100)
        toolbars_flowbox.append(file_group)
        toolbars_flowbox.append(text_format_group)
        toolbars_flowbox.append(align_group)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox)
        content_box.append(scroll)
        toolbar_view.set_content(content_box)

        # File buttons
        for icon, handler in [
            ("document-new", self.on_new_clicked),
            ("document-open", self.on_open_clicked),
            ("document-save", self.on_save_clicked),
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.connect("clicked", handler)
            file_group.append(btn)

        # Text format buttons
        self.bold_btn = Gtk.ToggleButton(label="B")
        self.bold_btn.connect("toggled", self.on_bold_toggled)
        text_format_group.append(self.bold_btn)

        self.italic_btn = Gtk.ToggleButton(label="I")
        self.italic_btn.connect("toggled", self.on_italic_toggled)
        text_format_group.append(self.italic_btn)

        self.underline_btn = Gtk.ToggleButton(label="U")
        self.underline_btn.connect("toggled", self.on_underline_toggled)
        text_format_group.append(self.underline_btn)

        # Align buttons
        self.align_left_btn = Gtk.ToggleButton(label="Left")
        self.align_left_btn.connect("toggled", self.on_align_left)
        align_group.append(self.align_left_btn)

        self.align_center_btn = Gtk.ToggleButton(label="Center")
        self.align_center_btn.connect("toggled", self.on_align_center)
        align_group.append(self.align_center_btn)

        # Key controller
        key_controller = Gtk.EventControllerKey.new()
        self.textview.add_controller(key_controller)
        key_controller.connect("key-pressed", self.on_key_pressed)

    def update_title(self):
        modified_marker = "⃰" if self.is_modified else ""
        title = f"{modified_marker}{self.document_number if self.is_new else self.current_file.get_basename()} – Author"
        self.set_title(title)

    def on_buffer_changed(self, buffer):
        self.is_modified = True
        self.update_title()

    def on_mark_set(self, buffer, iter, mark):
        if mark.get_name() == "insert":
            tags = iter.get_tags()
            self.bold_btn.set_active(self.tag_bold in tags)
            self.italic_btn.set_active(self.tag_italic in tags)
            self.underline_btn.set_active(self.tag_underline in tags)

    def apply_formatting(self, tag, enable):
        buffer = self.textview.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            if enable:
                buffer.apply_tag(tag, start, end)
            else:
                buffer.remove_tag(tag, start, end)
        # Note: For typing after toggle, TextView applies tags automatically if set on insert mark

    def on_bold_toggled(self, btn):
        self.apply_formatting(self.tag_bold, btn.get_active())

    def on_italic_toggled(self, btn):
        self.apply_formatting(self.tag_italic, btn.get_active())

    def on_underline_toggled(self, btn):
        self.apply_formatting(self.tag_underline, btn.get_active())

    def on_align_left(self, btn):
        if btn.get_active():
            self.apply_alignment(self.tag_align_left)
            self.align_center_btn.set_active(False)

    def on_align_center(self, btn):
        if btn.get_active():
            self.apply_alignment(self.tag_align_center)
            self.align_left_btn.set_active(False)

    def apply_alignment(self, tag):
        buffer = self.textview.get_buffer()
        iter = buffer.get_iter_at_mark(buffer.get_insert())
        start = iter.copy()
        start.set_line_offset(0)
        end = iter.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        for other_tag in [self.tag_align_left, self.tag_align_center]:
            if other_tag != tag:
                buffer.remove_tag(other_tag, start, end)
        buffer.apply_tag(tag, start, end)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval == Gdk.KEY_b:
                self.bold_btn.set_active(not self.bold_btn.get_active())
                return True
            elif keyval == Gdk.KEY_i:
                self.italic_btn.set_active(not self.italic_btn.get_active())
                return True
            elif keyval == Gdk.KEY_u:
                self.underline_btn.set_active(not self.underline_btn.get_active())
                return True

    def on_new_clicked(self, btn):
        self.textview.get_buffer().set_text("")
        self.is_new = True
        self.current_file = None
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()

    def on_open_clicked(self, btn):
        dialog = Gtk.FileDialog()
        filter_page = Gtk.FileFilter()
        filter_page.set_name("Page Files (*.page)")
        filter_page.add_pattern("*.page")
        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("Text Files (*.txt)")
        filter_txt.add_pattern("*.txt")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_page)
        filters.append(filter_txt)
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_open_response)

    def on_open_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.current_file = file
                self.is_new = False
                if file.get_path().endswith(".page"):
                    file.load_contents_async(None, self.load_page_callback)
                else:
                    file.load_contents_async(None, self.load_callback)
        except GLib.Error as e:
            print(f"Open error: {e.message}")

    def load_page_callback(self, file, result):
        ok, content, _ = file.load_contents_finish(result)
        if ok:
            buffer = self.textview.get_buffer()
            buffer.set_text("")
            text = content.decode()
            start = buffer.get_start_iter()
            pos = 0
            while pos < len(text):
                if text[pos:pos+3] == "[b]":
                    pos += 3
                    end_pos = text.find("[/b]", pos)
                    if end_pos == -1:
                        break
                    buffer.insert(start, text[pos:end_pos])
                    buffer.apply_tag(self.tag_bold, buffer.get_iter_at_offset(pos - 3), buffer.get_iter_at_offset(end_pos - 3))
                    pos = end_pos + 4
                elif text[pos:pos+3] == "[i]":
                    pos += 3
                    end_pos = text.find("[/i]", pos)
                    if end_pos == -1:
                        break
                    buffer.insert(start, text[pos:end_pos])
                    buffer.apply_tag(self.tag_italic, buffer.get_iter_at_offset(pos - 3), buffer.get_iter_at_offset(end_pos - 3))
                    pos = end_pos + 4
                elif text[pos:pos+3] == "[u]":
                    pos += 3
                    end_pos = text.find("[/u]", pos)
                    if end_pos == -1:
                        break
                    buffer.insert(start, text[pos:end_pos])
                    buffer.apply_tag(self.tag_underline, buffer.get_iter_at_offset(pos - 3), buffer.get_iter_at_offset(end_pos - 3))
                    pos = end_pos + 4
                else:
                    buffer.insert(start, text[pos])
                    pos += 1
            self.is_modified = False
            self.update_title()

    def load_callback(self, file, result):
        ok, content, _ = file.load_contents_finish(result)
        if ok:
            self.textview.get_buffer().set_text(content.decode())
            self.is_modified = False
            self.update_title()

    def on_save_clicked(self, btn):
        if self.current_file and not self.is_new:
            if self.current_file.get_path().endswith(".page"):
                self.save_as_page(self.current_file)
            else:
                self.save_to_file(self.current_file)
        else:
            dialog = Gtk.FileDialog()
            filter_page = Gtk.FileFilter()
            filter_page.set_name("Page Files (*.page)")
            filter_page.add_pattern("*.page")
            filter_txt = Gtk.FileFilter()
            filter_txt.set_name("Text Files (*.txt)")
            filter_txt.add_pattern("*.txt")
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_page)
            filters.append(filter_txt)
            dialog.set_filters(filters)
            dialog.set_initial_name(f"Document {self.document_number}.page")
            dialog.save(self, None, self.save_callback)

    def save_callback(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.current_file = file
                self.is_new = False
                if file.get_path().endswith(".page"):
                    self.save_as_page(file)
                else:
                    self.save_to_file(file)
        except GLib.Error as e:
            print(f"Save error: {e.message}")

    def save_as_page(self, file):
        buffer = self.textview.get_buffer()
        start, end = buffer.get_bounds()
        text = ""
        iter = start.copy()
        while iter.forward_to_tag_toggle(None) and iter.compare(end) <= 0:
            segment_start = iter.copy()
            segment_end = iter.copy()
            if not segment_end.forward_to_tag_toggle(None):
                segment_end = end.copy()
            segment_text = buffer.get_text(segment_start, segment_end, False)
            tags = segment_start.get_tags()
            if self.tag_bold in tags:
                text += f"[b]{segment_text}[/b]"
            elif self.tag_italic in tags:
                text += f"[i]{segment_text}[/i]"
            elif self.tag_underline in tags:
                text += f"[u]{segment_text}[/u]"
            else:
                text += segment_text
            iter = segment_end
        if not text:  # Handle text without tags
            text = buffer.get_text(start, end, False)
        file.replace_contents(text.encode(), None, False, Gio.FileCreateFlags.REPLACE_DESTINATION, None)
        self.is_modified = False
        self.update_title()

    def save_to_file(self, file):
        buffer = self.textview.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, False)
        file.replace_contents(text.encode(), None, False, Gio.FileCreateFlags.REPLACE_DESTINATION, None)
        self.is_modified = False
        self.update_title()

if __name__ == "__main__":
    app = Author()
    app.run()
