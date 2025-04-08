#!/usr/bin/env python3

import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, Gio, GLib, Pango, PangoCairo, Gdk

class UndoRedoStack:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def save_state(self, state):
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            state = self.undo_stack.pop()
            self.redo_stack.append(state)
            return state
        return None

    def redo(self):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(state)
            return state
        return None

class Writer(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.fastrizwaan.writer")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = EditorWindow(application=self)
        win.present()

class EditorWindow(Adw.ApplicationWindow):
    document_counter = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Writer")
        self.set_default_size(1000, 700)

        # State tracking
        self.current_bold = False
        self.current_italic = False
        self.current_underline = False
        self.current_strikethrough = False
        self.current_bullet_list = False
        self.current_number_list = False
        self.current_font = "Sans"
        self.current_size = "12"
        self.current_file = None
        self.is_new = True
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()

        # Undo/Redo stack
        self.undo_redo_stack = UndoRedoStack()
        self.last_saved_state = ""

        # TextView and TextBuffer setup
        self.textview = Gtk.TextView(editable=True, wrap_mode=Gtk.WrapMode.WORD)
        self.textbuffer = self.textview.get_buffer()
        self.textbuffer.connect("changed", self.on_buffer_changed)
        self.textbuffer.connect("mark-set", self.on_mark_set)
        self.textbuffer.connect_after("insert-text", self.on_after_insert_text)
        self.textbuffer.connect_after("delete-range", self.on_after_delete_range)

        # Define text tags
        self.bold_tag = Gtk.TextTag.new("bold")
        self.bold_tag.set_property("weight", Pango.Weight.BOLD)
        self.textbuffer.get_tag_table().add(self.bold_tag)

        self.italic_tag = Gtk.TextTag.new("italic")
        self.italic_tag.set_property("style", Pango.Style.ITALIC)
        self.textbuffer.get_tag_table().add(self.italic_tag)

        self.underline_tag = Gtk.TextTag.new("underline")
        self.underline_tag.set_property("underline", Pango.Underline.SINGLE)
        self.textbuffer.get_tag_table().add(self.underline_tag)

        self.strikethrough_tag = Gtk.TextTag.new("strikethrough")
        self.strikethrough_tag.set_property("strikethrough", True)
        self.textbuffer.get_tag_table().add(self.strikethrough_tag)

        self.left_tag = Gtk.TextTag.new("left")
        self.left_tag.set_property("justification", Gtk.Justification.LEFT)
        self.textbuffer.get_tag_table().add(self.left_tag)

        self.center_tag = Gtk.TextTag.new("center")
        self.center_tag.set_property("justification", Gtk.Justification.CENTER)
        self.textbuffer.get_tag_table().add(self.center_tag)

        self.right_tag = Gtk.TextTag.new("right")
        self.right_tag.set_property("justification", Gtk.Justification.RIGHT)
        self.textbuffer.get_tag_table().add(self.right_tag)

        self.justify_tag = Gtk.TextTag.new("justify")
        self.justify_tag.set_property("justification", Gtk.Justification.FILL)
        self.textbuffer.get_tag_table().add(self.justify_tag)

        self.font_tags = {}
        self.size_tags = {}
        self.heading_tags = {}
        for level in range(1, 7):
            tag = Gtk.TextTag.new(f"h{level}")
            size = 24 - (level * 2)  # h1=24pt, h2=22pt, ..., h6=14pt
            tag.set_property("size-points", size)
            tag.set_property("weight", Pango.Weight.BOLD)
            self.textbuffer.get_tag_table().add(tag)
            self.heading_tags[f"h{level}"] = tag

        # CSS Providers
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(b"""
            .toolbar-container { padding: 6px; background-color: rgba(127, 127, 127, 0.2); }
            .flat { background: none; }
            .flat:hover, .flat:checked { background: rgba(127, 127, 127, 0.25); }
            dropdown.flat, dropdown.flat button { background: none; border-radius: 5px; }
            dropdown.flat:hover { background: rgba(127, 127, 127, 0.25); }
            .flat-header { background: rgba(127, 127, 127, 0.2); border: none; box-shadow: none; padding: 0; }
            .toolbar-group { margin: 0 3px; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.dark_css = Gtk.CssProvider()
        self.dark_css.load_from_data(b"""
            textview {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
        """)

        # Main layout
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.textview)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)
        header = Adw.HeaderBar()
        header.add_css_class("flat-header")
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        toolbar_view.add_top_bar(header)

        # Toolbar groups
        file_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        file_group.add_css_class("toolbar-group")
        edit_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        edit_group.add_css_class("toolbar-group")
        view_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        view_group.add_css_class("toolbar-group")
        text_style_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        text_style_group.add_css_class("toolbar-group")
        text_format_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        text_format_group.add_css_class("toolbar-group")
        list_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        list_group.add_css_class("toolbar-group")
        align_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        align_group.add_css_class("toolbar-group")

        file_toolbar_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        file_toolbar_group.add_css_class("toolbar-group-container")
        file_toolbar_group.append(file_group)
        file_toolbar_group.append(edit_group)
        file_toolbar_group.append(view_group)

        formatting_toolbar_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        formatting_toolbar_group.add_css_class("toolbar-group-container")
        formatting_toolbar_group.append(text_style_group)
        formatting_toolbar_group.append(text_format_group)
        formatting_toolbar_group.append(list_group)
        formatting_toolbar_group.append(align_group)

        toolbars_flowbox = Gtk.FlowBox()
        toolbars_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        toolbars_flowbox.set_max_children_per_line(100)
        toolbars_flowbox.add_css_class("toolbar-container")
        toolbars_flowbox.insert(file_toolbar_group, -1)
        toolbars_flowbox.insert(formatting_toolbar_group, -1)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox)
        content_box.append(scroll)
        toolbar_view.set_content(content_box)

        # Populate toolbar groups
        for icon, handler in [
            ("document-new", self.on_new_clicked), ("document-open", self.on_open_clicked),
            ("document-save", self.on_save_clicked), ("document-save-as", self.on_save_as_clicked),
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.add_css_class("flat")
            btn.connect("clicked", handler)
            file_group.append(btn)

        for icon, handler in [
            ("edit-cut", self.on_cut_clicked), ("edit-copy", self.on_copy_clicked),
            ("edit-paste", self.on_paste_clicked), ("edit-undo", self.on_undo_clicked),
            ("edit-redo", self.on_redo_clicked),
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.add_css_class("flat")
            btn.connect("clicked", handler)
            edit_group.append(btn)

        self.dark_mode_btn = Gtk.ToggleButton(icon_name="display-brightness")
        self.dark_mode_btn.connect("toggled", self.on_dark_mode_toggled)
        self.dark_mode_btn.add_css_class("flat")
        view_group.append(self.dark_mode_btn)

        heading_store = Gtk.StringList()
        for h in ["Normal", "H1", "H2", "H3", "H4", "H5", "H6"]:
            heading_store.append(h)
        self.heading_dropdown = Gtk.DropDown(model=heading_store)
        self.heading_dropdown.connect("notify::selected", self.on_heading_changed)
        self.heading_dropdown.add_css_class("flat")
        text_style_group.append(self.heading_dropdown)

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

        size_store = Gtk.StringList(strings=["6", "8", "10", "12", "24", "36"])
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(3)  # Default to 12
        self.size_dropdown.connect("notify::selected", self.on_font_size_changed)
        self.size_dropdown.add_css_class("flat")
        text_style_group.append(self.size_dropdown)

        self.bold_btn = Gtk.ToggleButton(icon_name="format-text-bold")
        self.bold_btn.add_css_class("flat")
        self.bold_btn.connect("toggled", self.on_bold_toggled)
        text_format_group.append(self.bold_btn)

        self.italic_btn = Gtk.ToggleButton(icon_name="format-text-italic")
        self.italic_btn.add_css_class("flat")
        self.italic_btn.connect("toggled", self.on_italic_toggled)
        text_format_group.append(self.italic_btn)

        self.underline_btn = Gtk.ToggleButton(icon_name="format-text-underline")
        self.underline_btn.add_css_class("flat")
        self.underline_btn.connect("toggled", self.on_underline_toggled)
        text_format_group.append(self.underline_btn)

        self.strikethrough_btn = Gtk.ToggleButton(icon_name="format-text-strikethrough")
        self.strikethrough_btn.add_css_class("flat")
        self.strikethrough_btn.connect("toggled", self.on_strikethrough_toggled)
        text_format_group.append(self.strikethrough_btn)

        self.align_left_btn = Gtk.ToggleButton(icon_name="format-justify-left")
        self.align_left_btn.add_css_class("flat")
        self.align_left_btn.connect("toggled", self.on_align_left)
        align_group.append(self.align_left_btn)

        self.align_center_btn = Gtk.ToggleButton(icon_name="format-justify-center")
        self.align_center_btn.add_css_class("flat")
        self.align_center_btn.connect("toggled", self.on_align_center)
        align_group.append(self.align_center_btn)

        self.align_right_btn = Gtk.ToggleButton(icon_name="format-justify-right")
        self.align_right_btn.add_css_class("flat")
        self.align_right_btn.connect("toggled", self.on_align_right)
        align_group.append(self.align_right_btn)

        self.align_justify_btn = Gtk.ToggleButton(icon_name="format-justify-fill")
        self.align_justify_btn.add_css_class("flat")
        self.align_justify_btn.connect("toggled", self.on_align_justify)
        align_group.append(self.align_justify_btn)

        self.align_left_btn.set_active(True)

        self.bullet_btn = Gtk.ToggleButton(icon_name="view-list-bullet")
        self.bullet_btn.connect("toggled", self.on_bullet_list_toggled)
        self.bullet_btn.add_css_class("flat")
        list_group.append(self.bullet_btn)

        self.number_btn = Gtk.ToggleButton(icon_name="view-list-ordered")
        self.number_btn.connect("toggled", self.on_number_list_toggled)
        self.number_btn.add_css_class("flat")
        list_group.append(self.number_btn)

        for icon, handler in [
            ("format-indent-more", self.on_indent_more), ("format-indent-less", self.on_indent_less)
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.connect("clicked", handler)
            btn.add_css_class("flat")
            list_group.append(btn)

        key_controller = Gtk.EventControllerKey.new()
        self.textview.add_controller(key_controller)
        key_controller.connect("key-pressed", self.on_key_pressed)

        self.connect("close-request", self.on_close_request)

    def on_after_insert_text(self, buffer, iter, text, length):
        end = iter.copy()
        start = end.copy()
        if start.backward_chars(length):
            if self.current_bold:
                buffer.apply_tag(self.bold_tag, start, end)
            if self.current_italic:
                buffer.apply_tag(self.italic_tag, start, end)
            if self.current_underline:
                buffer.apply_tag(self.underline_tag, start, end)
            if self.current_strikethrough:
                buffer.apply_tag(self.strikethrough_tag, start, end)
            if self.current_font in self.font_tags:
                buffer.apply_tag(self.font_tags[self.current_font], start, end)
            if self.current_size in self.size_tags:
                buffer.apply_tag(self.size_tags[self.current_size], start, end)
        self.undo_redo_stack.save_state(self.last_saved_state)
        self.last_saved_state = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def on_after_delete_range(self, buffer, start, end):
        self.undo_redo_stack.save_state(self.last_saved_state)
        self.last_saved_state = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def on_mark_set(self, buffer, iter, mark):
        if mark.get_name() == "insert":
            tags = iter.get_tags()
            self.bold_btn.set_active(self.bold_tag in tags)
            self.italic_btn.set_active(self.italic_tag in tags)
            self.underline_btn.set_active(self.underline_tag in tags)
            self.strikethrough_btn.set_active(self.strikethrough_tag in tags)

            font_tag = next((tag for tag in tags if tag.get_property("family")), None)
            if font_tag:
                font_family = font_tag.get_property("family")
                model = self.font_dropdown.get_model()
                for i in range(model.get_n_items()):
                    if model.get_string(i) == font_family:
                        self.font_dropdown.set_selected(i)
                        break
            else:
                self.font_dropdown.set_selected(0)

            size_tag = next((tag for tag in tags if tag.get_property("size-points")), None)
            if size_tag:
                size_points = str(int(size_tag.get_property("size-points")))
                model = self.size_dropdown.get_model()
                for i in range(model.get_n_items()):
                    if model.get_string(i) == size_points:
                        self.size_dropdown.set_selected(i)
                        break
            else:
                self.size_dropdown.set_selected(3)

            if self.left_tag in tags:
                self.align_left_btn.set_active(True)
                self.align_center_btn.set_active(False)
                self.align_right_btn.set_active(False)
                self.align_justify_btn.set_active(False)
            elif self.center_tag in tags:
                self.align_center_btn.set_active(True)
                self.align_left_btn.set_active(False)
                self.align_right_btn.set_active(False)
                self.align_justify_btn.set_active(False)
            elif self.right_tag in tags:
                self.align_right_btn.set_active(True)
                self.align_left_btn.set_active(False)
                self.align_center_btn.set_active(False)
                self.align_justify_btn.set_active(False)
            elif self.justify_tag in tags:
                self.align_justify_btn.set_active(True)
                self.align_left_btn.set_active(False)
                self.align_center_btn.set_active(False)
                self.align_right_btn.set_active(False)

            heading_tag = None
            for level in range(1, 7):
                h_tag = self.heading_tags[f"h{level}"]
                if h_tag in tags:
                    heading_tag = h_tag
                    self.heading_dropdown.set_selected(level)
                    break
            if not heading_tag:
                self.heading_dropdown.set_selected(0)

            start = iter.copy()
            if not start.starts_line():
                start.backward_line()
            end = start.copy()
            end.forward_to_line_end()
            text = buffer.get_text(start, end, False)
            self.bullet_btn.set_active(text.startswith("• "))
            self.number_btn.set_active(text.strip().startswith(tuple(f"{i}. " for i in range(1, 100))))

    def update_title(self):
        modified_marker = "⃰" if self.is_modified else ""
        if self.current_file and not self.is_new:
            base_name = os.path.splitext(self.current_file.get_basename())[0]
            title = f"{modified_marker}{base_name} – Writer"
        else:
            title = f"{modified_marker}Document {self.document_number} – Writer"
        self.set_title(title)

    def on_new_clicked(self, btn):
        if not self.check_save_before_new():
            self.textbuffer.set_text("")
            self.current_file = None
            self.is_new = True
            self.is_modified = False
            self.document_number = EditorWindow.document_counter
            EditorWindow.document_counter += 1
            self.undo_redo_stack = UndoRedoStack()  # Reset undo/redo history
            self.last_saved_state = ""
            self.update_title()

    def on_open_clicked(self, btn):
        dialog = Gtk.FileDialog()
        filter = Gtk.FileFilter()
        filter.set_name("Text Files (*.txt)")
        filter.add_pattern("*.txt")
        dialog.set_default_filter(filter)
        dialog.open(self, None, self.on_open_file_dialog_response)

    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.current_file = file
                self.is_new = False
                file.load_contents_async(None, self.load_text_callback)
        except GLib.Error as e:
            print("Open error:", e.message)

    def load_text_callback(self, file, result):
        try:
            ok, content, _ = file.load_contents_finish(result)
            if ok:
                self.textbuffer.set_text(content.decode())
                self.is_modified = False
                self.undo_redo_stack = UndoRedoStack()  # Reset undo/redo history
                self.last_saved_state = content.decode()
                self.update_title()
        except GLib.Error as e:
            print("Load error:", e.message)

    def on_save_clicked(self, btn):
        if self.current_file and not self.is_new:
            self.save_as_text(self.current_file)
        else:
            self.show_save_dialog()

    def on_save_as_clicked(self, btn):
        self.show_save_dialog()

    def show_save_dialog(self):
        dialog = Gtk.FileDialog()
        dialog.set_title("Save As")
        if self.current_file and not self.is_new:
            dialog.set_initial_file(self.current_file)
        else:
            dialog.set_initial_name(f"Document {self.document_number}.txt")
        filter = Gtk.FileFilter()
        filter.set_name("Text Files (*.txt)")
        filter.add_pattern("*.txt")
        dialog.set_default_filter(filter)
        dialog.save(self, None, self.save_callback)

    def save_callback(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.save_as_text(file)
                self.current_file = file
                self.is_new = False
                self.update_title()
        except GLib.Error as e:
            print("Save error:", e.message)

    def save_as_text(self, file):
        text = self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
        file.replace_contents_bytes_async(
            GLib.Bytes.new(text.encode()),
            None, False, Gio.FileCreateFlags.REPLACE_DESTINATION,
            None, self.final_save_callback
        )

    def final_save_callback(self, file, result):
        try:
            file.replace_contents_finish(result)
            self.is_modified = False
            self.update_title()
        except GLib.Error as e:
            print("Final save error:", e.message)

    def on_cut_clicked(self, btn):
        if self.textbuffer.get_has_selection():
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            self.textbuffer.cut_clipboard(Gdk.Display.get_default().get_clipboard(), True)
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_copy_clicked(self, btn):
        self.textbuffer.copy_clipboard(Gdk.Display.get_default().get_clipboard())

    def on_paste_clicked(self, btn):
        self.undo_redo_stack.save_state(
            self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
        )
        self.textbuffer.paste_clipboard(Gdk.Display.get_default().get_clipboard(), None, True)
        self.last_saved_state = self.textbuffer.get_text(
            self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
        )

    def on_undo_clicked(self, btn):
        state = self.undo_redo_stack.undo()
        if state is not None:
            self.textbuffer.set_text(state)
            self.last_saved_state = state
            self.is_modified = True
            self.update_title()

    def on_redo_clicked(self, btn):
        state = self.undo_redo_stack.redo()
        if state is not None:
            self.textbuffer.set_text(state)
            self.last_saved_state = state
            self.is_modified = True
            self.update_title()

    def on_dark_mode_toggled(self, btn):
        style_context = self.textview.get_style_context()
        if btn.get_active():
            btn.set_icon_name("weather-clear-night")
            style_context.add_provider(self.dark_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        else:
            btn.set_icon_name("display-brightness")
            style_context.remove_provider(self.dark_css)

    def on_bold_toggled(self, btn):
        self.current_bold = btn.get_active()
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            if self.current_bold:
                self.textbuffer.apply_tag(self.bold_tag, start, end)
            else:
                self.textbuffer.remove_tag(self.bold_tag, start, end)
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_italic_toggled(self, btn):
        self.current_italic = btn.get_active()
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            if self.current_italic:
                self.textbuffer.apply_tag(self.italic_tag, start, end)
            else:
                self.textbuffer.remove_tag(self.italic_tag, start, end)
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_underline_toggled(self, btn):
        self.current_underline = btn.get_active()
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            if self.current_underline:
                self.textbuffer.apply_tag(self.underline_tag, start, end)
            else:
                self.textbuffer.remove_tag(self.underline_tag, start, end)
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_strikethrough_toggled(self, btn):
        self.current_strikethrough = btn.get_active()
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            if self.current_strikethrough:
                self.textbuffer.apply_tag(self.strikethrough_tag, start, end)
            else:
                self.textbuffer.remove_tag(self.strikethrough_tag, start, end)
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def apply_alignment(self, tag):
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            if not start.starts_line():
                start.backward_line()
            if not end.ends_line():
                end.forward_to_line_end()
        else:
            iter = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
            start = iter.copy()
            if not start.starts_line():
                start.backward_line()
            end = start.copy()
            end.forward_to_line_end()
        self.undo_redo_stack.save_state(
            self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
        )
        for align_tag in [self.left_tag, self.center_tag, self.right_tag, self.justify_tag]:
            self.textbuffer.remove_tag(align_tag, start, end)
        self.textbuffer.apply_tag(tag, start, end)
        self.last_saved_state = self.textbuffer.get_text(
            self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
        )

    def on_align_left(self, btn):
        if btn.get_active():
            self.align_center_btn.set_active(False)
            self.align_right_btn.set_active(False)
            self.align_justify_btn.set_active(False)
            self.apply_alignment(self.left_tag)

    def on_align_center(self, btn):
        if btn.get_active():
            self.align_left_btn.set_active(False)
            self.align_right_btn.set_active(False)
            self.align_justify_btn.set_active(False)
            self.apply_alignment(self.center_tag)

    def on_align_right(self, btn):
        if btn.get_active():
            self.align_left_btn.set_active(False)
            self.align_center_btn.set_active(False)
            self.align_justify_btn.set_active(False)
            self.apply_alignment(self.right_tag)

    def on_align_justify(self, btn):
        if btn.get_active():
            self.align_left_btn.set_active(False)
            self.align_center_btn.set_active(False)
            self.align_right_btn.set_active(False)
            self.apply_alignment(self.justify_tag)

    def on_bullet_list_toggled(self, btn):
        self.current_bullet_list = btn.get_active()
        if self.current_bullet_list:
            self.current_number_list = False
            self.number_btn.set_active(False)
            if self.textbuffer.get_has_selection():
                start, end = self.textbuffer.get_selection_bounds()
                if not start.starts_line():
                    start.backward_line()
                if not end.ends_line():
                    end.forward_to_line_end()
                self.undo_redo_stack.save_state(
                    self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
                )
                iter = start.copy()
                while iter.compare(end) < 0:
                    line_start = iter.copy()
                    if not line_start.starts_line():
                        line_start.forward_to_line_start()
                    self.textbuffer.insert(line_start, "• ")
                    iter.forward_line()
                self.last_saved_state = self.textbuffer.get_text(
                    self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
                )
        else:
            if self.textbuffer.get_has_selection():
                start, end = self.textbuffer.get_selection_bounds()
                if not start.starts_line():
                    start.backward_line()
                if not end.ends_line():
                    end.forward_to_line_end()
                self.undo_redo_stack.save_state(
                    self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
                )
                iter = start.copy()
                while iter.compare(end) < 0:
                    line_start = iter.copy()
                    if not line_start.starts_line():
                        line_start.forward_to_line_start()
                    line_end = line_start.copy()
                    line_end.forward_chars(2)
                    text = self.textbuffer.get_text(line_start, line_end, False)
                    if text == "• ":
                        self.textbuffer.delete(line_start, line_end)
                    iter.forward_line()
                self.last_saved_state = self.textbuffer.get_text(
                    self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
                )

    def on_number_list_toggled(self, btn):
        self.current_number_list = btn.get_active()
        if self.current_number_list:
            self.current_bullet_list = False
            self.bullet_btn.set_active(False)
            if self.textbuffer.get_has_selection():
                start, end = self.textbuffer.get_selection_bounds()
                if not start.starts_line():
                    start.backward_line()
                if not end.ends_line():
                    end.forward_to_line_end()
                self.undo_redo_stack.save_state(
                    self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
                )
                iter = start.copy()
                number = 1
                while iter.compare(end) < 0:
                    line_start = iter.copy()
                    if not line_start.starts_line():
                        line_start.forward_to_line_start()
                    self.textbuffer.insert(line_start, f"{number}. ")
                    number += 1
                    iter.forward_line()
                self.last_saved_state = self.textbuffer.get_text(
                    self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
                )
        else:
            if self.textbuffer.get_has_selection():
                start, end = self.textbuffer.get_selection_bounds()
                if not start.starts_line():
                    start.backward_line()
                if not end.ends_line():
                    end.forward_to_line_end()
                self.undo_redo_stack.save_state(
                    self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
                )
                iter = start.copy()
                while iter.compare(end) < 0:
                    line_start = iter.copy()
                    if not line_start.starts_line():
                        line_start.forward_to_line_start()
                    line_end = line_start.copy()
                    while line_end.get_char().isdigit() or line_end.get_char() == '.':
                        line_end.forward_char()
                    text = self.textbuffer.get_text(line_start, line_end, False)
                    if text.endswith(". "):
                        self.textbuffer.delete(line_start, line_end)
                    iter.forward_line()
                self.last_saved_state = self.textbuffer.get_text(
                    self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
                )

    def on_indent_more(self, btn):
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            if not start.starts_line():
                start.backward_line()
            if not end.ends_line():
                end.forward_to_line_end()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            iter = start.copy()
            while iter.compare(end) < 0:
                line_start = iter.copy()
                if not line_start.starts_line():
                    line_start.forward_to_line_start()
                self.textbuffer.insert(line_start, "\t")
                iter.forward_line()
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_indent_less(self, btn):
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            if not start.starts_line():
                start.backward_line()
            if not end.ends_line():
                end.forward_to_line_end()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            iter = start.copy()
            while iter.compare(end) < 0:
                line_start = iter.copy()
                if not line_start.starts_line():
                    line_start.forward_to_line_start()
                line_end = line_start.copy()
                line_end.forward_char()
                if self.textbuffer.get_text(line_start, line_end, False) == "\t":
                    self.textbuffer.delete(line_start, line_end)
                iter.forward_line()
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_heading_changed(self, dropdown, *args):
        selected = dropdown.get_selected()
        if selected == 0:
            tag = None
        else:
            tag = self.heading_tags[f"h{selected}"]
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            if not start.starts_line():
                start.backward_line()
            if not end.ends_line():
                end.forward_to_line_end()
        else:
            iter = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
            start = iter.copy()
            if not start.starts_line():
                start.backward_line()
            end = start.copy()
            end.forward_to_line_end()
        self.undo_redo_stack.save_state(
            self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
        )
        for h_tag in self.heading_tags.values():
            self.textbuffer.remove_tag(h_tag, start, end)
        if tag:
            self.textbuffer.apply_tag(tag, start, end)
        self.last_saved_state = self.textbuffer.get_text(
            self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
        )

    def on_font_family_changed(self, dropdown, *args):
        selected_font = dropdown.get_selected_item().get_string()
        if selected_font not in self.font_tags:
            tag = Gtk.TextTag.new(f"font-{selected_font}")
            tag.set_property("family", selected_font)
            self.textbuffer.get_tag_table().add(tag)
            self.font_tags[selected_font] = tag
        self.current_font = selected_font
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            for tag in self.font_tags.values():
                self.textbuffer.remove_tag(tag, start, end)
            self.textbuffer.apply_tag(self.font_tags[selected_font], start, end)
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_font_size_changed(self, dropdown, *args):
        selected_size = dropdown.get_selected_item().get_string()
        if selected_size not in self.size_tags:
            tag = Gtk.TextTag.new(f"size-{selected_size}")
            tag.set_property("size-points", float(selected_size))
            self.textbuffer.get_tag_table().add(tag)
            self.size_tags[selected_size] = tag
        self.current_size = selected_size
        if self.textbuffer.get_has_selection():
            start, end = self.textbuffer.get_selection_bounds()
            self.undo_redo_stack.save_state(
                self.textbuffer.get_text(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False)
            )
            for tag in self.size_tags.values():
                self.textbuffer.remove_tag(tag, start, end)
            self.textbuffer.apply_tag(self.size_tags[selected_size], start, end)
            self.last_saved_state = self.textbuffer.get_text(
                self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter(), False
            )

    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        shift = (state & Gdk.ModifierType.SHIFT_MASK) != 0

        if ctrl and not shift:
            if keyval == Gdk.KEY_b:
                self.bold_btn.set_active(not self.bold_btn.get_active())
                return True
            elif keyval == Gdk.KEY_i:
                self.italic_btn.set_active(not self.italic_btn.get_active())
                return True
            elif keyval == Gdk.KEY_u:
                self.underline_btn.set_active(not self.underline_btn.get_active())
                return True
            elif keyval == Gdk.KEY_s:
                self.on_save_clicked(None)
                return True
            elif keyval == Gdk.KEY_w:
                self.on_close_request()
                return True
            elif keyval == Gdk.KEY_n:
                self.on_new_clicked(None)
                return True
            elif keyval == Gdk.KEY_o:
                self.on_open_clicked(None)
                return True
            elif keyval == Gdk.KEY_x:
                self.on_cut_clicked(None)
                return True
            elif keyval == Gdk.KEY_c:
                self.on_copy_clicked(None)
                return True
            elif keyval == Gdk.KEY_v:
                self.on_paste_clicked(None)
                return True
            elif keyval == Gdk.KEY_z:
                self.on_undo_clicked(None)
                return True
            elif keyval == Gdk.KEY_y:
                self.on_redo_clicked(None)
                return True
            elif keyval == Gdk.KEY_l:
                self.on_align_left(self.align_left_btn)
                return True
            elif keyval == Gdk.KEY_e:
                self.on_align_center(self.align_center_btn)
                return True
            elif keyval == Gdk.KEY_r:
                self.on_align_right(self.align_right_btn)
                return True
            elif keyval == Gdk.KEY_j:
                self.on_align_justify(self.align_justify_btn)
                return True
            elif keyval in (Gdk.KEY_M, Gdk.KEY_m):
                self.on_indent_more(None)
                return True
            elif keyval == Gdk.KEY_0:
                self.heading_dropdown.set_selected(0)
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval in range(Gdk.KEY_1, Gdk.KEY_7):
                self.heading_dropdown.set_selected(keyval - Gdk.KEY_0)
                self.on_heading_changed(self.heading_dropdown)
                return True
        elif ctrl and shift:
            if keyval == Gdk.KEY_S:
                self.on_save_as_clicked(None)
                return True
            elif keyval == Gdk.KEY_X:
                self.strikethrough_btn.set_active(not self.strikethrough_btn.get_active())
                return True
            elif keyval == Gdk.KEY_L or keyval == Gdk.KEY_asterisk:
                self.on_bullet_list_toggled(self.bullet_btn)
                return True
            elif keyval == Gdk.KEY_ampersand:
                self.on_number_list_toggled(self.number_btn)
                return True
            elif keyval == Gdk.KEY_M:
                self.on_indent_less(None)
                return True
        elif not ctrl:
            if keyval == Gdk.KEY_F12:
                if shift:
                    self.on_bullet_list_toggled(self.bullet_btn)
                else:
                    self.on_number_list_toggled(self.number_btn)
                return True
            elif keyval == Gdk.KEY_Return and (self.current_bullet_list or self.current_number_list):
                iter = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
                if self.current_bullet_list:
                    self.textbuffer.insert(iter, "\n• ")
                elif self.current_number_list:
                    start = iter.copy()
                    if not start.starts_line():
                        start.backward_line()
                    line_text = self.textbuffer.get_text(start, iter, False)
                    import re
                    match = re.match(r"(\d+)\. ", line_text)
                    number = int(match.group(1)) + 1 if match else 1
                    self.textbuffer.insert(iter, f"\n{number}. ")
                return True
        return False

    def on_buffer_changed(self, buffer):
        self.is_modified = True
        self.update_title()

    def check_save_before_new(self):
        if self.is_modified:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Save changes?",
                body="Do you want to save changes before starting a new document?",
                modal=True
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)

            def on_response(dialog, response):
                if response == "save":
                    self.on_save_clicked(None)
                elif response == "discard":
                    self.on_new_clicked(None)
                dialog.destroy()

            dialog.connect("response", on_response)
            dialog.present()
            return True
        return False

    def on_close_request(self, *args):
        if self.is_modified:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Save changes?",
                body="Do you want to save changes before closing?",
                modal=True
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)

            def on_response(dialog, response):
                if response == "save":
                    self.on_save_clicked(None)
                    self.get_application().quit()
                elif response == "discard":
                    self.get_application().quit()
                dialog.destroy()

            dialog.connect("response", on_response)
            dialog.present()
            return True
        self.get_application().quit()
        return False

if __name__ == "__main__":
    app = Writer()
    app.run()
