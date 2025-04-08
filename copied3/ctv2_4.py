#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gio', '2.0')
from gi.repository import Gio, Gtk, Adw, Gdk, GLib, Pango, GObject

    
class TextFormatState:
    """Track active text formatting state for upcoming text"""
    def __init__(self):
        self.bold = False
        self.italic = False
        self.underline = False
        self.alignment = "left"  # default alignment
        self.paragraph_style = "normal"
        self.font_family = None
        self.font_size = None

class RichTextEditor(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.RichTextEditor")
        self.connect('activate', self.on_activate)
        self.current_file = None
        
        # Text formatting state
        self.format_state = TextFormatState()
        
        # CSS Provider
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(b"""
            .toolbar-container { 
                padding: 6px; 
                background-color: rgba(127, 127, 127, 0.2); 
            }
            .toolbar-group { 
                margin: 0 3px; 
            }
            .toolbar-group-container { 
                padding: 2px; 
            }
            button.flat { 
                background: none; 
                border: none;
                padding: 4px;
            }
            button.flat:hover, button.flat:checked { 
                background: rgba(127, 127, 127, 0.25); 
            }
            dropdown.flat > button { 
                background: none; 
                border-radius: 5px; 
                padding: 2px 6px;
            }
            dropdown.flat:hover > button { 
                background: rgba(127, 127, 127, 0.25); 
            }
            .flat-header { 
                background: rgba(127, 127, 127, 0.2); 
                border: none; 
                box-shadow: none; 
                padding: 0; 
            }
            .color-indicator { 
                min-height: 3px; 
                min-width: 16px; 
                margin-top: 1px; 
                border-radius: 2px; 
            }
            .color-box { 
                padding: 0; 
            }
        """)
        # Add provider globally
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(display, self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(800, 600)
        self.win.set_title("Rich Text Editor")

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)
        header = Adw.HeaderBar()
        header.add_css_class("flat-header")
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

        # Content setup
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)

        self.buffer = Gtk.TextBuffer()
        self.buffer.set_max_undo_levels(100)
        self.buffer.connect("changed", self.on_buffer_changed)
        self.buffer.connect("mark-set", self.on_cursor_position_changed)
        
        # Connect to insert-text to apply formatting
        self.buffer.connect("insert-text", self.on_insert_text)
        
        self.textview = Gtk.TextView.new_with_buffer(self.buffer)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_left_margin(20)
        self.textview.set_right_margin(20)
        self.textview.set_top_margin(20)
        self.textview.set_bottom_margin(20)
        
        scrolled_window.set_child(self.textview)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox)
        content_box.append(scrolled_window)
        toolbar_view.set_content(content_box)

        # Populate toolbar groups with flat style
        self.create_file_buttons(file_group)
        self.create_edit_buttons(edit_group)
        self.create_view_buttons(view_group)
        self.create_text_style_buttons(text_style_group)
        self.create_text_format_buttons(text_format_group)
        self.create_list_buttons(list_group)
        self.create_align_buttons(align_group)

        self.setup_text_tags()
        self.modified = False
        self.setup_keyboard_shortcuts()
        
        self.win.set_content(main_box)
        GLib.idle_add(self.textview.grab_focus)
        self.win.present()

    def create_file_buttons(self, container):
        buttons_data = [
            ("New", "document-new-symbolic", self.on_new_clicked),
            ("Open", "document-open-symbolic", self.on_open_clicked),
            ("Save", "document-save-symbolic", self.on_save_clicked),
            ("Save As", "document-save-as-symbolic", self.on_save_as_clicked)
        ]
        for name, icon, callback in buttons_data:
            button = Gtk.Button()
            button.set_tooltip_text(name)
            button.set_icon_name(icon)
            button.connect("clicked", callback)
            button.add_css_class("flat")  # Add flat class to buttons
            container.append(button)

    def create_edit_buttons(self, container):
        buttons_data = [
            ("Cut", "edit-cut-symbolic", self.on_cut_clicked),
            ("Copy", "edit-copy-symbolic", self.on_copy_clicked),
            ("Paste", "edit-paste-symbolic", self.on_paste_clicked),
            ("Undo", "edit-undo-symbolic", self.on_undo_clicked),
            ("Redo", "edit-redo-symbolic", self.on_redo_clicked)
        ]
        for name, icon, callback in buttons_data:
            button = Gtk.Button()
            button.set_tooltip_text(name)
            button.set_icon_name(icon)
            button.connect("clicked", callback)
            button.add_css_class("flat")
            container.append(button)

    def create_view_buttons(self, container):
        pass

    def create_text_style_buttons(self, container):
        para_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        paragraph_styles = ["Normal", "H1", "H2", "H3", "H4", "H5", "H6"]
        self.para_combo = Gtk.DropDown.new_from_strings(paragraph_styles)
        self.para_combo.connect("notify::selected", self.on_paragraph_style_changed)
        self.para_combo.add_css_class("flat")
        para_box.append(self.para_combo)
        container.append(para_box)

        font_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        context = self.win.get_pango_context()
        font_families = context.list_families()
        font_names = [family.get_name() for family in font_families]
        font_names.sort()
        self.font_combo = Gtk.DropDown.new_from_strings(font_names)
        self.font_combo.connect("notify::selected", self.on_font_changed)
        self.font_combo.add_css_class("flat")
        font_box.append(self.font_combo)
        container.append(font_box)

        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        font_sizes = ["6", "8", "10", "12", "14", "16", "18", "20", "24", "28", "32", "36", "42", "48", "56", "64", "72"]
        self.size_combo = Gtk.DropDown.new_from_strings(font_sizes)
        self.size_combo.set_selected(4)  # default to 14pt
        self.format_state.font_size = "14"  # Set initial font size
        self.size_combo.connect("notify::selected", self.on_font_size_changed)
        self.size_combo.add_css_class("flat")
        size_box.append(self.size_combo)
        container.append(size_box)

    def create_text_format_buttons(self, container):
        style_buttons_data = [
            ("Bold", "format-text-bold-symbolic", self.on_bold_clicked, "bold"),
            ("Italic", "format-text-italic-symbolic", self.on_italic_clicked, "italic"),
            ("Underline", "format-text-underline-symbolic", self.on_underline_clicked, "underline")
        ]
        for name, icon, callback, tag in style_buttons_data:
            button = Gtk.ToggleButton()
            button.set_tooltip_text(name)
            button.set_icon_name(icon)
            button.connect("toggled", callback)
            button.add_css_class("flat")
            setattr(self, f"{tag}_button", button)
            container.append(button)

    def create_list_buttons(self, container):
        list_buttons_data = [
            ("Bullet List", "view-list-bullet-symbolic", self.on_bullet_list_clicked),
            ("Numbered List", "view-list-ordered-symbolic", self.on_numbered_list_clicked)
        ]
        for name, icon, callback in list_buttons_data:
            button = Gtk.Button()
            button.set_tooltip_text(name)
            button.set_icon_name(icon)
            button.connect("clicked", callback)
            button.add_css_class("flat")
            container.append(button)

    def create_align_buttons(self, container):
        align_buttons_data = [
            ("Align Left", "format-justify-left-symbolic", self.on_align_left_clicked, "left"),
            ("Align Center", "format-justify-center-symbolic", self.on_align_center_clicked, "center"),
            ("Align Right", "format-justify-right-symbolic", self.on_align_right_clicked, "right"),
            ("Justify", "format-justify-fill-symbolic", self.on_align_justify_clicked, "justify")
        ]
        for name, icon, callback, align in align_buttons_data:
            button = Gtk.ToggleButton()
            button.set_tooltip_text(name)
            button.set_icon_name(icon)
            button.connect("toggled", callback)
            button.add_css_class("flat")
            setattr(self, f"align_{align}_button", button)
            container.append(button)
        
        # Set left alignment as default
        self.align_left_button.set_active(True)

    def setup_text_tags(self):
        # Create all text formatting tags
        self.buffer.create_tag("normal", weight=Pango.Weight.NORMAL, size_points=12)
        self.buffer.create_tag("h1", weight=Pango.Weight.BOLD, size_points=24)
        self.buffer.create_tag("h2", weight=Pango.Weight.BOLD, size_points=20)
        self.buffer.create_tag("h3", weight=Pango.Weight.BOLD, size_points=18)
        self.buffer.create_tag("h4", weight=Pango.Weight.BOLD, size_points=16)
        self.buffer.create_tag("h5", weight=Pango.Weight.BOLD, size_points=14)
        self.buffer.create_tag("h6", weight=Pango.Weight.BOLD, size_points=12)
        self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.buffer.create_tag("underline", underline=Pango.Underline.SINGLE)
        
        # Create alignment tags - make sure these exist
        self.buffer.create_tag("left", justification=Gtk.Justification.LEFT)
        self.buffer.create_tag("center", justification=Gtk.Justification.CENTER)
        self.buffer.create_tag("right", justification=Gtk.Justification.RIGHT)
        self.buffer.create_tag("justify", justification=Gtk.Justification.FILL)
        
        self.buffer.create_tag("bullet-list", left_margin=40)
        self.buffer.create_tag("numbered-list", left_margin=40)

    def setup_keyboard_shortcuts(self):
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_press)
        self.textview.add_controller(key_controller)

    def on_key_press(self, controller, keyval, keycode, state):
        modifiers = state & Gtk.accelerator_get_default_mod_mask()
        ctrl = modifiers == Gdk.ModifierType.CONTROL_MASK
        
        if ctrl:
            if keyval == Gdk.KEY_s:
                self.on_save_clicked(None)
                return True
            elif keyval == Gdk.KEY_o:
                self.on_open_clicked(None)
                return True
            elif keyval == Gdk.KEY_n:
                self.on_new_clicked(None)
                return True
            elif keyval == Gdk.KEY_b:
                self.bold_button.set_active(not self.bold_button.get_active())
                return True
            elif keyval == Gdk.KEY_i:
                self.italic_button.set_active(not self.italic_button.get_active())
                return True
            elif keyval == Gdk.KEY_u:
                self.underline_button.set_active(not self.underline_button.get_active())
                return True
            elif keyval == Gdk.KEY_z:
                self.on_undo_clicked(None)
                return True
            elif keyval == Gdk.KEY_y:
                self.on_redo_clicked(None)
                return True
        return False

    def on_insert_text(self, buffer, location, text, length):
        # This function is called before the text is actually inserted
        # Store insert position for later
        insert_mark = buffer.get_insert()
        cursor_position = buffer.get_iter_at_mark(insert_mark)
        
        # We need to do this in an idle callback to avoid modifying the buffer during signal emission
        def apply_format_to_inserted_text():
            # Get the text range that was just inserted
            end = buffer.get_iter_at_mark(insert_mark)
            start = end.copy()
            start.backward_chars(len(text))
            
            # Apply active formatting to the newly inserted text
            if self.format_state.bold:
                buffer.apply_tag_by_name("bold", start, end)
            
            if self.format_state.italic:
                buffer.apply_tag_by_name("italic", start, end)
            
            if self.format_state.underline:
                buffer.apply_tag_by_name("underline", start, end)
            
            # Apply paragraph style
            if self.format_state.paragraph_style:
                buffer.apply_tag_by_name(self.format_state.paragraph_style, start, end)
            
            # Apply alignment
            if self.format_state.alignment:
                buffer.apply_tag_by_name(self.format_state.alignment, start, end)
            
            # Apply font family if set
            if self.format_state.font_family:
                tag_name = f"font-{self.format_state.font_family}"
                tag = buffer.get_tag_table().lookup(tag_name)
                if tag:
                    buffer.apply_tag(tag, start, end)
            
            # Apply font size if set
            if self.format_state.font_size:
                tag_name = f"size-{self.format_state.font_size}"
                tag = buffer.get_tag_table().lookup(tag_name)
                if tag:
                    buffer.apply_tag(tag, start, end)
            
            return False  # Remove the idle callback
        
        # Schedule the formatting for after the text is inserted
        GLib.idle_add(apply_format_to_inserted_text)
        return False
    def on_new_clicked(self, button):
        if self.modified:
            self.show_save_dialog_before_action(self.create_new_document)
        else:
            self.create_new_document()

    def create_new_document(self):
        self.buffer.set_text("")
        self.current_file = None
        self.modified = False
        self.win.set_title("Rich Text Editor")

    def on_open_clicked(self, button):
        if self.modified:
            self.show_save_dialog_before_action(self.show_open_dialog)
        else:
            self.show_open_dialog()

    def show_open_dialog(self):
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Document")
        filters = Gtk.FileFilter()
        filters.set_name("Text files")
        filters.add_mime_type("text/plain")
        filters.add_pattern("*.txt")
        dialog.open(self.win, None, self.on_open_response)

    def on_open_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.load_file(file)
        except GLib.Error as error:
            print(f"Error opening file: {error.message}")

    def load_file(self, file):
        from gi.repository import Gio
        try:
            [success, contents, etag] = file.load_contents(None)
            if success:
                text = contents.decode('utf-8')
                self.buffer.set_text(text)
                self.current_file = file
                self.modified = False
                self.win.set_title(f"Rich Text Editor - {os.path.basename(file.get_path())}")
        except GLib.Error as error:
            print(f"Error loading file: {error.message}")

    def on_save_clicked(self, button):
        if self.current_file is None:
            self.on_save_as_clicked(button)
        else:
            self.save_to_file(self.current_file)

    def on_save_as_clicked(self, button):
        dialog = Gtk.FileDialog()
        dialog.set_title("Save Document")
        filters = Gtk.FileFilter()
        filters.set_name("Text files")
        filters.add_mime_type("text/plain")
        filters.add_pattern("*.txt")
        dialog.save(self.win, None, self.on_save_response)

    def on_save_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.save_to_file(file)
        except GLib.Error as error:
            print(f"Error saving file: {error.message}")

    def save_to_file(self, file):
        from gi.repository import Gio
        start_iter = self.buffer.get_start_iter()
        end_iter = self.buffer.get_end_iter()
        text = self.buffer.get_text(start_iter, end_iter, True)
        try:
            file.replace_contents(text.encode('utf-8'), None, False, 
                                Gio.FileCreateFlags.REPLACE_DESTINATION, None)
            self.current_file = file
            self.modified = False
            self.win.set_title(f"Rich Text Editor - {os.path.basename(file.get_path())}")
        except GLib.Error as error:
            print(f"Error saving file: {error.message}")

    def show_save_dialog_before_action(self, callback):
        dialog = Adw.MessageDialog.new(self.win, "Save Changes?", 
                                    "The current document has unsaved changes. Would you like to save them?")
        dialog.add_response("discard", "Discard")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda dialog, response: self.on_save_dialog_response(dialog, response, callback))
        dialog.present()

    def on_save_dialog_response(self, dialog, response, callback):
        dialog.destroy()
        if response == "save":
            if self.current_file is not None:
                self.save_to_file(self.current_file)
                callback()
            else:
                save_dialog = Gtk.FileDialog()
                save_dialog.set_title("Save Document")
                filters = Gtk.FileFilter()
                filters.set_name("Text files")
                filters.add_mime_type("text/plain")
                filters.add_pattern("*.txt")
                save_dialog.save(self.win, None, 
                               lambda dialog, result: self.on_save_response_with_callback(dialog, result, callback))
        elif response == "discard":
            callback()

    def on_save_response_with_callback(self, dialog, result, callback):
        try:
            file = dialog.save_finish(result)
            if file:
                self.save_to_file(file)
                callback()
        except GLib.Error as error:
            print(f"Error saving file: {error.message}")

    def on_cut_clicked(self, button):
        clipboard = Gdk.Display.get_default().get_clipboard()
        self.buffer.cut_clipboard(clipboard, True)

    def on_copy_clicked(self, button):
        clipboard = Gdk.Display.get_default().get_clipboard()
        self.buffer.copy_clipboard(clipboard)

    def on_paste_clicked(self, button):
        clipboard = Gdk.Display.get_default().get_clipboard()
        self.buffer.paste_clipboard(clipboard, None, True)

    def on_undo_clicked(self, button):
        self.buffer.undo()
        self.update_button_states()

    def on_redo_clicked(self, button):
        self.buffer.redo()
        self.update_button_states()
        
    def on_bold_clicked(self, button):
        # Update the format state
        self.format_state.bold = button.get_active()
        
        # Apply to selected text if there is a selection
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            if button.get_active():
                self.buffer.apply_tag_by_name("bold", start, end)
            else:
                self.buffer.remove_tag_by_name("bold", start, end)

    def on_italic_clicked(self, button):
        # Update the format state
        self.format_state.italic = button.get_active()
        
        # Apply to selected text if there is a selection
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            if button.get_active():
                self.buffer.apply_tag_by_name("italic", start, end)
            else:
                self.buffer.remove_tag_by_name("italic", start, end)

    def on_underline_clicked(self, button):
        # Update the format state
        self.format_state.underline = button.get_active()
        
        # Apply to selected text if there is a selection
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            if button.get_active():
                self.buffer.apply_tag_by_name("underline", start, end)
            else:
                self.buffer.remove_tag_by_name("underline", start, end)

    def on_bullet_list_clicked(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            start_line = start.get_line()
            end_line = end.get_line()
            for line in range(start_line, end_line + 1):
                # Get line_start iter
                success, line_start = self.buffer.get_iter_at_line(line)
                if not success:
                    continue
                line_end = line_start.copy()
                line_end.forward_chars(2)
                line_text = self.buffer.get_text(line_start, line_end, False)
                if line_text != "• ":
                    self.buffer.insert(line_start, "• ", -1)
                # After insertion, re-fetch line_start and line_end
                success_new, line_start_new = self.buffer.get_iter_at_line(line)
                if not success_new:
                    continue
                line_end_new = line_start_new.copy()
                if not line_end_new.ends_line():
                    line_end_new.forward_to_line_end()
                self.buffer.apply_tag_by_name("bullet-list", line_start_new, line_end_new)


    def on_numbered_list_clicked(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            start_line = start.get_line()
            end_line = end.get_line()
            for line_num, line in enumerate(range(start_line, end_line + 1), 1):
                success, line_start = self.buffer.get_iter_at_line(line)
                if not success:
                    continue
                line_end = line_start.copy()
                line_end.forward_chars(3)
                line_text = self.buffer.get_text(line_start, line_end, False)
                # Fixed line: Added missing closing parenthesis
                if not (line_text.startswith(str(line_num)) and ". " in line_text):
                    self.buffer.insert(line_start, f"{line_num}. ", -1)
                success_new, line_start_new = self.buffer.get_iter_at_line(line)
                if not success_new:
                    continue
                line_end_new = line_start_new.copy()
                if not line_end_new.ends_line():
                    line_end_new.forward_to_line_end()
                self.buffer.apply_tag_by_name("numbered-list", line_start_new, line_end_new)

    def on_align_left_clicked(self, button):
        self.format_state.alignment = "left" if button.get_active() else self.format_state.alignment
        self.handle_alignment_button(button, "left")

    def on_align_center_clicked(self, button):
        self.format_state.alignment = "center" if button.get_active() else self.format_state.alignment
        self.handle_alignment_button(button, "center")

    def on_align_right_clicked(self, button):
        self.format_state.alignment = "right" if button.get_active() else self.format_state.alignment
        self.handle_alignment_button(button, "right")

    def on_align_justify_clicked(self, button):
        self.format_state.alignment = "justify" if button.get_active() else self.format_state.alignment
        self.handle_alignment_button(button, "justify")


    def handle_alignment_button(self, button, align_type):
        if button.get_active():
            # Set the correct format state
            self.format_state.alignment = align_type
            
            # Turn off other alignment buttons
            for align in ["left", "center", "right", "justify"]:
                if align != align_type:
                    getattr(self, f"align_{align}_button").set_active(False)
            
            # Determine the text range to format
            bounds = self.buffer.get_selection_bounds()
            if not bounds:
                # No selection, get current line
                cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
                current_line = cursor.get_line()
                
                # Get line_start and line_end iters - properly handle the tuple return
                success, line_start = self.buffer.get_iter_at_line(current_line)
                if success:
                    line_end = line_start.copy()
                    if not line_end.ends_line():
                        line_end.forward_to_line_end()
                    
                    start, end = line_start, line_end
                else:
                    # Fall back to cursor position if line can't be determined
                    start = cursor
                    end = cursor.copy()
            else:
                start, end = bounds
            
            # Remove existing alignment tags first
            for align in ["left", "center", "right", "justify"]:
                align_tag = self.buffer.get_tag_table().lookup(align)
                if align_tag:  # Only if tag exists
                    self.buffer.remove_tag(align_tag, start, end)
            
            # Apply the new alignment tag
            align_tag = self.buffer.get_tag_table().lookup(align_type)
            if align_tag:  # Only if tag exists
                self.buffer.apply_tag(align_tag, start, end)
        else:
            # If turning off the current alignment, switch to left align
            if self.format_state.alignment == align_type:
                self.format_state.alignment = "left"
                self.align_left_button.set_active(True)

    def on_font_changed(self, dropdown, param):
        context = self.win.get_pango_context()
        font_families = context.list_families()
        font_names = [family.get_name() for family in font_families]
        font_names.sort()
        font_index = dropdown.get_selected()
        if font_index < len(font_names):
            font = font_names[font_index]
            # Update format state for future text
            self.format_state.font_family = font
            
            tag_name = f"font-{font}"
            tag = self.buffer.get_tag_table().lookup(tag_name)
            if tag is None:
                tag = self.buffer.create_tag(tag_name, family=font)
            bounds = self.buffer.get_selection_bounds()
            if bounds:
                start, end = bounds
                for f in font_names:
                    old_tag = self.buffer.get_tag_table().lookup(f"font-{f}")
                    if old_tag:
                        self.buffer.remove_tag(old_tag, start, end)
                self.buffer.apply_tag(tag, start, end)
        GLib.idle_add(self.textview.grab_focus)
        
    def on_font_size_changed(self, dropdown, param):
        font_sizes = ["6", "8", "10", "12", "14", "16", "18", "20", "24", "28", "32", "36", "42", "48", "56", "64", "72"]
        size_index = dropdown.get_selected()
        if size_index < len(font_sizes):
            size = font_sizes[size_index]
            # Update format state for future text
            self.format_state.font_size = size
            
            size_int = int(size)
            tag_name = f"size-{size}"
            tag = self.buffer.get_tag_table().lookup(tag_name)
            if tag is None:
                tag = self.buffer.create_tag(tag_name, size_points=size_int)
            bounds = self.buffer.get_selection_bounds()
            if bounds:
                start, end = bounds
                for s in font_sizes:
                    old_tag = self.buffer.get_tag_table().lookup(f"size-{s}")
                    if old_tag:
                        self.buffer.remove_tag(old_tag, start, end)
                self.buffer.apply_tag(tag, start, end)
        GLib.idle_add(self.textview.grab_focus)

    def on_paragraph_style_changed(self, dropdown, param):
        style_index = dropdown.get_selected()
        styles = ["normal", "h1", "h2", "h3", "h4", "h5", "h6"]
        if style_index < len(styles):
            style = styles[style_index]
            self.format_state.paragraph_style = style
            
            bounds = self.buffer.get_selection_bounds()
            if not bounds:
                cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
                current_line = cursor.get_line()
                
                # Get line_start and line_end iters (unpack tuples)
                success_start, line_start = self.buffer.get_iter_at_line(current_line)
                success_end, line_end = self.buffer.get_iter_at_line(current_line)
                
                # Handle invalid iterators (fallback to buffer start)
                if not success_start or not success_end:
                    line_start = self.buffer.get_start_iter()
                    line_end = self.buffer.get_start_iter()
                else:
                    if not line_end.ends_line():
                        line_end.forward_to_line_end()
                start, end = line_start, line_end
            else:
                start, end = bounds
                
            # Remove existing paragraph tags and apply the new one
            for s in styles:
                self.buffer.remove_tag_by_name(s, start, end)
            self.buffer.apply_tag_by_name(style, start, end)
        GLib.idle_add(self.textview.grab_focus)
            

    def on_buffer_changed(self, buffer):
        self.modified = True
        title = self.win.get_title()
        if not title.endswith(" *"):
            self.win.set_title(f"{title} *")

    def on_cursor_position_changed(self, buffer, location, mark):
        if mark == buffer.get_insert():
            self.update_button_states()

    def update_button_states(self):
        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        
        # Get all tags at cursor position
        tags = cursor.get_tags()
        
        # Check for text style tags
        bold_tag = self.buffer.get_tag_table().lookup("bold")
        self.bold_button.set_active(bold_tag in tags)
        
        italic_tag = self.buffer.get_tag_table().lookup("italic")
        self.italic_button.set_active(italic_tag in tags)
        
        underline_tag = self.buffer.get_tag_table().lookup("underline")
        self.underline_button.set_active(underline_tag in tags)
        
        # Check for alignment tags - defensive lookup with error handling
        for align in ["left", "center", "right", "justify"]:
            align_tag = self.buffer.get_tag_table().lookup(align)
            if align_tag is None:
                # The tag doesn't exist - probably means setup_text_tags hasn't been called
                print(f"Warning: Tag '{align}' not found in tag table")
                continue
                
            getattr(self, f"align_{align}_button").set_active(align_tag in tags)
        
        # Check for paragraph style tags
        styles = ["normal", "h1", "h2", "h3", "h4", "h5", "h6"]
        for i, style in enumerate(styles):
            style_tag = self.buffer.get_tag_table().lookup(style)
            if style_tag in tags:
                self.para_combo.set_selected(i)
                break
        
        # Check for font tags
        context = self.win.get_pango_context()
        font_families = context.list_families()
        font_names = [family.get_name() for family in font_families]
        font_names.sort()
        
        for i, font in enumerate(font_names):
            tag = self.buffer.get_tag_table().lookup(f"font-{font}")
            if tag and tag in tags:
                self.font_combo.set_selected(i)
                break
        
        # Check for size tags
        font_sizes = ["6", "8", "10", "12", "14", "16", "18", "20", "24", "28", "32", "36", "42", "48", "56", "64", "72"]
        for i, size in enumerate(font_sizes):
            tag = self.buffer.get_tag_table().lookup(f"size-{size}")
            if tag and tag in tags:
                self.size_combo.set_selected(i)
                break


##################################
    def update_button_states(self):
        # Get tag references
        bold_tag = self.buffer.get_tag_table().lookup("bold")
        italic_tag = self.buffer.get_tag_table().lookup("italic")
        underline_tag = self.buffer.get_tag_table().lookup("underline")
        bounds = self.buffer.get_selection_bounds()

        def get_full_selection_tag_state(tag):
            """Check if tag exists throughout entire selection"""
            if not bounds:
                return tag in self.buffer.get_iter_at_mark(self.buffer.get_insert()).get_tags()
            
            start, end = bounds
            current = start.copy()
            while current.compare(end) < 0:
                if not current.has_tag(tag):
                    return False
                if not current.forward_char():
                    break
            return True

        # Update style buttons
        self.bold_button.set_active(get_full_selection_tag_state(bold_tag))
        self.italic_button.set_active(get_full_selection_tag_state(italic_tag))
        self.underline_button.set_active(get_full_selection_tag_state(underline_tag))

        # Update alignment buttons
        for align in ["left", "center", "right", "justify"]:
            align_tag = self.buffer.get_tag_table().lookup(align)
            if align_tag:
                btn = getattr(self, f"align_{align}_button")
                btn.set_active(get_full_selection_tag_state(align_tag))

        # Update paragraph style
        styles = ["normal", "h1", "h2", "h3", "h4", "h5", "h6"]
        current_style = "normal"
        if bounds:
            start, end = bounds
            style_tags = set()
            current = start.copy()
            while current.compare(end) < 0:
                for t in current.get_tags():
                    if t.get_property("name") in styles:
                        style_tags.add(t.get_property("name"))
                if not current.forward_char():
                    break
            if len(style_tags) == 1:
                current_style = style_tags.pop()
        else:
            cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            for t in cursor.get_tags():
                if t.get_property("name") in styles:
                    current_style = t.get_property("name")
                    break
        try:
            self.para_combo.set_selected(styles.index(current_style))
        except ValueError:
            self.para_combo.set_selected(0)

        # Update font family
        context = self.win.get_pango_context()
        font_names = sorted([f.get_name() for f in context.list_families()])
        current_font = None
        if bounds:
            start, end = bounds
            fonts = set()
            current = start.copy()
            while current.compare(end) < 0:
                for t in current.get_tags():
                    if font := t.get_property("family"):
                        fonts.add(font)
                if not current.forward_char():
                    break
            if len(fonts) == 1:
                current_font = fonts.pop()
        else:
            cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            for t in cursor.get_tags():
                if font := t.get_property("family"):
                    current_font = font
                    break
        if current_font and current_font in font_names:
            self.font_combo.set_selected(font_names.index(current_font))

        # Update font size
        sizes = ["6", "8", "10", "12", "14", "16", "18", "20", "24", 
                "28", "32", "36", "42", "48", "56", "64", "72"]
        current_size = None
        if bounds:
            start, end = bounds
            size_points = set()
            current = start.copy()
            while current.compare(end) < 0:
                for t in current.get_tags():
                    if size := t.get_property("size_points"):
                        size_points.add(str(int(size)))
                if not current.forward_char():
                    break
            if len(size_points) == 1:
                current_size = size_points.pop()
        else:
            cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            for t in cursor.get_tags():
                if size := t.get_property("size_points"):
                    current_size = str(int(size))
                    break
        if current_size and current_size in sizes:
            self.size_combo.set_selected(sizes.index(current_size))



###################################
if __name__ == "__main__":
    app = RichTextEditor()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
