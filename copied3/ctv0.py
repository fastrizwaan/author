#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Pango, GObject

class RichTextEditor(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.RichTextEditor")
        self.connect('activate', self.on_activate)
        self.current_file = None

    def on_activate(self, app):
        # Create main window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(800, 600)
        self.win.set_title("Rich Text Editor")

        # Create main layout box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.set_content(self.main_box)

        # Create headerbar
        self.header = Adw.HeaderBar()
        self.main_box.append(self.header)

        # Create flowboxes for toolbar items
        self.toolbar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toolbar_box.add_css_class("toolbar")
        self.main_box.append(self.toolbar_box)

        # First FlowBox Group (File Operations and Edit)
        self.file_operations_flow = Gtk.FlowBox()
        self.file_operations_flow.set_valign(Gtk.Align.START)
        self.file_operations_flow.set_max_children_per_line(10)
        self.file_operations_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.file_operations_flow.set_homogeneous(False)
        self.toolbar_box.append(self.file_operations_flow)

        # Add separator between flowboxes
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.toolbar_box.append(separator)

        # Second FlowBox Group (Formatting)
        self.formatting_flow = Gtk.FlowBox()
        self.formatting_flow.set_valign(Gtk.Align.START)
        self.formatting_flow.set_max_children_per_line(12)
        self.formatting_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.formatting_flow.set_homogeneous(False)
        self.toolbar_box.append(self.formatting_flow)

        # Add buttons to first FlowBox
        self.create_file_operations_buttons()
        
        # Add buttons to second FlowBox
        self.create_formatting_buttons()

        # Scrolled window for text view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        self.main_box.append(scrolled_window)

        # Create TextBuffer and TextView
        self.buffer = Gtk.TextBuffer()
        self.buffer.connect("changed", self.on_buffer_changed)
        self.buffer.connect("mark-set", self.on_cursor_position_changed)
        
        self.textview = Gtk.TextView.new_with_buffer(self.buffer)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_left_margin(20)
        self.textview.set_right_margin(20)
        self.textview.set_top_margin(20)
        self.textview.set_bottom_margin(20)
        
        scrolled_window.set_child(self.textview)
        
        # Setup various tag tables for formatting
        self.setup_text_tags()
        
        # Initialize state
        self.modified = False
        
        # Set up keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        # Show window
        self.win.present()

    def create_file_operations_buttons(self):
        # Create file operation buttons
        buttons_data = [
            ("New", "document-new-symbolic", self.on_new_clicked),
            ("Open", "document-open-symbolic", self.on_open_clicked),
            ("Save", "document-save-symbolic", self.on_save_clicked),
            ("Save As", "document-save-as-symbolic", self.on_save_as_clicked),
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
            self.file_operations_flow.append(button)

    def create_formatting_buttons(self):
        # Create paragraph style dropdown
        para_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        #para_label = Gtk.Label(label="Paragraph:")
        #para_box.append(para_label)
        
        paragraph_styles = ["Normal", "H1", "H2", "H3", "H4", "H5", "H6"]
        self.para_combo = Gtk.DropDown.new_from_strings(paragraph_styles)
        self.para_combo.connect("notify::selected", self.on_paragraph_style_changed)
        para_box.append(self.para_combo)
        
        self.formatting_flow.append(para_box)
        
        # Create font family dropdown
        font_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        #font_label = Gtk.Label(label="Font:")
        #font_box.append(font_label)
        
        # Get system fonts using Pango context
        context = self.win.get_pango_context()
        font_families = context.list_families()
        font_names = [family.get_name() for family in font_families]
        font_names.sort()
        
        self.font_combo = Gtk.DropDown.new_from_strings(font_names)
        self.font_combo.connect("notify::selected", self.on_font_changed)
        font_box.append(self.font_combo)
        
        self.formatting_flow.append(font_box)
        
        # Create font size dropdown
        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        size_label = Gtk.Label(label="Size:")
        size_box.append(size_label)
        
        font_sizes = ["6", "8", "10", "12", "14", "16", "18", "20", "24", "28", "32", "36", "42", "48", "56", "64", "72"]
        self.size_combo = Gtk.DropDown.new_from_strings(font_sizes)
        # Set default to 12pt
        self.size_combo.set_selected(4)  # 12 is at index 4
        self.size_combo.connect("notify::selected", self.on_font_size_changed)
        size_box.append(self.size_combo)
        
        self.formatting_flow.append(size_box)
        
        # Create style buttons (bold, italic, underline)
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
            setattr(self, f"{tag}_button", button)
            self.formatting_flow.append(button)
        
        # Create list buttons
        list_buttons_data = [
            ("Bullet List", "format-list-bulleted-symbolic", self.on_bullet_list_clicked),
            ("Numbered List", "format-list-numbered-symbolic", self.on_numbered_list_clicked)
        ]
        
        for name, icon, callback in list_buttons_data:
            button = Gtk.Button()
            button.set_tooltip_text(name)
            button.set_icon_name(icon)
            button.connect("clicked", callback)
            self.formatting_flow.append(button)
        
        # Create alignment buttons
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
            setattr(self, f"align_{align}_button", button)
            self.formatting_flow.append(button)

    def setup_text_tags(self):
        # Create paragraph style tags
        self.buffer.create_tag("normal", weight=Pango.Weight.NORMAL, size_points=12)
        self.buffer.create_tag("h1", weight=Pango.Weight.BOLD, size_points=24)
        self.buffer.create_tag("h2", weight=Pango.Weight.BOLD, size_points=20)
        self.buffer.create_tag("h3", weight=Pango.Weight.BOLD, size_points=18)
        self.buffer.create_tag("h4", weight=Pango.Weight.BOLD, size_points=16)
        self.buffer.create_tag("h5", weight=Pango.Weight.BOLD, size_points=14)
        self.buffer.create_tag("h6", weight=Pango.Weight.BOLD, size_points=12)
        
        # Create formatting tags
        self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.buffer.create_tag("underline", underline=Pango.Underline.SINGLE)
        
        # Create alignment tags
        self.buffer.create_tag("left", justification=Gtk.Justification.LEFT)
        self.buffer.create_tag("center", justification=Gtk.Justification.CENTER)
        self.buffer.create_tag("right", justification=Gtk.Justification.RIGHT)
        self.buffer.create_tag("justify", justification=Gtk.Justification.FILL)
        
        # Create list tags (will be used for line indentation)
        self.buffer.create_tag("bullet-list", left_margin=40)
        self.buffer.create_tag("numbered-list", left_margin=40)

    def setup_keyboard_shortcuts(self):
        # Create key event controller
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_press)
        self.textview.add_controller(key_controller)

    def on_key_press(self, controller, keyval, keycode, state):
        # Handle key shortcuts
        modifiers = state & Gtk.accelerator_get_default_mod_mask()
        ctrl = modifiers == Gdk.ModifierType.CONTROL_MASK
        
        if ctrl:
            if keyval == Gdk.KEY_s:  # Ctrl+S for save
                self.on_save_clicked(None)
                return True
            elif keyval == Gdk.KEY_o:  # Ctrl+O for open
                self.on_open_clicked(None)
                return True
            elif keyval == Gdk.KEY_n:  # Ctrl+N for new
                self.on_new_clicked(None)
                return True
            elif keyval == Gdk.KEY_b:  # Ctrl+B for bold
                self.bold_button.set_active(not self.bold_button.get_active())
                return True
            elif keyval == Gdk.KEY_i:  # Ctrl+I for italic
                self.italic_button.set_active(not self.italic_button.get_active())
                return True
            elif keyval == Gdk.KEY_u:  # Ctrl+U for underline
                self.underline_button.set_active(not self.underline_button.get_active())
                return True
            elif keyval == Gdk.KEY_z:  # Ctrl+Z for undo
                self.on_undo_clicked(None)
                return True
            elif keyval == Gdk.KEY_y:  # Ctrl+Y for redo
                self.on_redo_clicked(None)
                return True
        
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
        # Import Gio for file operations
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
        # Import Gio for file operations
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
            # If we have a current file, save to it, otherwise show save dialog
            if self.current_file is not None:
                self.save_to_file(self.current_file)
                callback()
            else:
                # Create a special save dialog that will call the callback after saving
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
        # "cancel" or dialog closed, do nothing

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
        if self.buffer.can_undo():
            self.buffer.undo()
            self.update_button_states()

    def on_redo_clicked(self, button):
        if self.buffer.can_redo():
            self.buffer.redo()
            self.update_button_states()

    def on_bold_clicked(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            if button.get_active():
                self.buffer.apply_tag_by_name("bold", start, end)
            else:
                self.buffer.remove_tag_by_name("bold", start, end)

    def on_italic_clicked(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            if button.get_active():
                self.buffer.apply_tag_by_name("italic", start, end)
            else:
                self.buffer.remove_tag_by_name("italic", start, end)

    def on_underline_clicked(self, button):
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
                line_start = self.buffer.get_iter_at_line(line)
                
                # Check if already has a bullet
                line_end = line_start.copy()
                line_end.forward_chars(2)
                line_text = self.buffer.get_text(line_start, line_end, False)
                if line_text != "• ":
                    # Insert bullet point at start of line
                    self.buffer.insert(line_start, "• ", -1)
                
                # Apply indentation
                line_start = self.buffer.get_iter_at_line(line)
                line_end = self.buffer.get_iter_at_line(line)
                if not line_end.ends_line():
                    line_end.forward_to_line_end()
                
                self.buffer.apply_tag_by_name("bullet-list", line_start, line_end)

    def on_numbered_list_clicked(self, button):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            start_line = start.get_line()
            end_line = end.get_line()
            
            for line_num, line in enumerate(range(start_line, end_line + 1), 1):
                line_start = self.buffer.get_iter_at_line(line)
                
                # Check if already has a number
                line_end = line_start.copy()
                line_end.forward_chars(3)
                line_text = self.buffer.get_text(line_start, line_end, False)
                if not (line_text.startswith(str(line_num)) and ". " in line_text):
                    # Insert number at start of line
                    self.buffer.insert(line_start, f"{line_num}. ", -1)
                
                # Apply indentation
                line_start = self.buffer.get_iter_at_line(line)
                line_end = self.buffer.get_iter_at_line(line)
                if not line_end.ends_line():
                    line_end.forward_to_line_end()
                
                self.buffer.apply_tag_by_name("numbered-list", line_start, line_end)

    def on_align_left_clicked(self, button):
        self.handle_alignment_button(button, "left")

    def on_align_center_clicked(self, button):
        self.handle_alignment_button(button, "center")

    def on_align_right_clicked(self, button):
        self.handle_alignment_button(button, "right")

    def on_align_justify_clicked(self, button):
        self.handle_alignment_button(button, "justify")

    def handle_alignment_button(self, button, align_type):
        # Unselect other alignment buttons
        if button.get_active():
            for align in ["left", "center", "right", "justify"]:
                if align != align_type:
                    getattr(self, f"align_{align}_button").set_active(False)
            
            # Apply the alignment
            bounds = self.buffer.get_selection_bounds()
            if not bounds:
                # If no selection, get the current line
                cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
                line_start = self.buffer.get_iter_at_line(cursor.get_line())
                line_end = line_start.copy()
                if not line_end.ends_line():
                    line_end.forward_to_line_end()
                bounds = (line_start, line_end)
            
            start, end = bounds
            
            # Remove other alignment tags
            for align in ["left", "center", "right", "justify"]:
                self.buffer.remove_tag_by_name(align, start, end)
            
            # Apply new alignment
            self.buffer.apply_tag_by_name(align_type, start, end)

    def on_paragraph_style_changed(self, dropdown, param):
        style_index = dropdown.get_selected()
        styles = ["normal", "h1", "h2", "h3", "h4", "h5", "h6"]
        if style_index < len(styles):
            style = styles[style_index]
            
            bounds = self.buffer.get_selection_bounds()
            if not bounds:
                # If no selection, get the current line
                cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
                line_start = self.buffer.get_iter_at_line(cursor.get_line())
                line_end = line_start.copy()
                if not line_end.ends_line():
                    line_end.forward_to_line_end()
                bounds = (line_start, line_end)
            
            start, end = bounds
            
            # Remove other paragraph style tags
            for s in styles:
                self.buffer.remove_tag_by_name(s, start, end)
            
            # Apply new style
            self.buffer.apply_tag_by_name(style, start, end)

    def on_font_changed(self, dropdown, param):
        # Get font names from context
        context = self.win.get_pango_context()
        font_families = context.list_families()
        font_names = [family.get_name() for family in font_families]
        font_names.sort()
        
        font_index = dropdown.get_selected()
        if font_index < len(font_names):
            font = font_names[font_index]
            
            # Create or get font tag
            tag_name = f"font-{font}"
            tag = self.buffer.get_tag_table().lookup(tag_name)
            
            if tag is None:
                tag = self.buffer.create_tag(tag_name, family=font)
            
            bounds = self.buffer.get_selection_bounds()
            if bounds:
                start, end = bounds
                
                # Remove other font tags
                for f in font_names:
                    old_tag = self.buffer.get_tag_table().lookup(f"font-{f}")
                    if old_tag:
                        self.buffer.remove_tag(old_tag, start, end)
                
                # Apply new font
                self.buffer.apply_tag(tag, start, end)

    def on_font_size_changed(self, dropdown, param):
        font_sizes = ["6", "8", "10", "12", "14", "16", "18", "20", "24", "28", "32", "36", "42", "48", "56", "64", "72"]
        size_index = dropdown.get_selected()
        if size_index < len(font_sizes):
            size = int(font_sizes[size_index])
            
            # Create or get size tag
            tag_name = f"size-{size}"
            tag = self.buffer.get_tag_table().lookup(tag_name)
            
            if tag is None:
                tag = self.buffer.create_tag(tag_name, size_points=size)
            
            bounds = self.buffer.get_selection_bounds()
            if bounds:
                start, end = bounds
                
                # Remove other size tags
                for s in font_sizes:
                    old_tag = self.buffer.get_tag_table().lookup(f"size-{s}")
                    if old_tag:
                        self.buffer.remove_tag(old_tag, start, end)
                
                # Apply new size
                self.buffer.apply_tag(tag, start, end)

    def on_buffer_changed(self, buffer):
        self.modified = True
        
        # Update window title to show modified status
        title = self.win.get_title()
        if not title.endswith(" *"):
            self.win.set_title(f"{title} *")

    def on_cursor_position_changed(self, buffer, location, mark):
        if mark == buffer.get_insert():
            self.update_button_states()

    def update_button_states(self):
        # Update formatting button states based on current cursor position
        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        
        # Check for bold
        bold_tag = self.buffer.get_tag_table().lookup("bold")
        self.bold_button.set_active(bold_tag in cursor.get_tags())
        
        # Check for italic
        italic_tag = self.buffer.get_tag_table().lookup("italic")
        self.italic_button.set_active(italic_tag in cursor.get_tags())
        
        # Check for underline
        underline_tag = self.buffer.get_tag_table().lookup("underline")
        self.underline_button.set_active(underline_tag in cursor.get_tags())
        
        # Check for alignment
        for align in ["left", "center", "right", "justify"]:
            align_tag = self.buffer.get_tag_table().lookup(align)
            if align_tag in cursor.get_tags():
                getattr(self, f"align_{align}_button").set_active(True)
            else:
                getattr(self, f"align_{align}_button").set_active(False)
        
        # Check for paragraph style
        styles = ["normal", "h1", "h2", "h3", "h4", "h5", "h6"]
        for i, style in enumerate(styles):
            style_tag = self.buffer.get_tag_table().lookup(style)
            if style_tag in cursor.get_tags():
                self.para_combo.set_selected(i)
                break
        
        # Check for font
        context = self.win.get_pango_context()
        font_families = context.list_families()
        font_names = [family.get_name() for family in font_families]
        font_names.sort()
        
        for i, font in enumerate(font_names):
            tag = self.buffer.get_tag_table().lookup(f"font-{font}")
            if tag and tag in cursor.get_tags():
                self.font_combo.set_selected(i)
                break
        

        # Check for font size
        font_sizes = ["6", "8", "10", "12", "14", "16", "18", "20", "24", "28", "32", "36", "42", "48", "56", "64", "72"]
        for i, size in enumerate(font_sizes):
            tag = self.buffer.get_tag_table().lookup(f"size-{size}")
                        
            if tag and tag in cursor.get_tags():
                self.size_combo.set_selected(i)
                break

if __name__ == "__main__":
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio
    
    app = RichTextEditor()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
