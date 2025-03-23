#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GObject, GLib, Gio, GdkPixbuf
import re
import os
import sys
from PIL import Image
import io

class MarkdownTableCell(Gtk.TextView):
    def __init__(self, table_widget, row_idx, col_idx):
        super().__init__()
        self.table_widget = table_widget
        self.row_idx = row_idx
        self.col_idx = col_idx
        
        self.set_size_request(100, 30)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_accepts_tab(False)
        self.set_hexpand(False)
        self.set_vexpand(False)
        
        self.buffer = self.get_buffer()
        self.is_editing = False
        self.is_resizing = False
        
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        
        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_button(1)
        click_gesture.connect("pressed", self.on_click_pressed)
        self.add_controller(click_gesture)
        
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect("enter", self.on_focus_in)
        self.add_controller(focus_controller)
        
        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("motion", self.on_motion)
        self.add_controller(motion_controller)
        
    def on_focus_in(self, controller):
        self.table_widget.current_cell = (self.row_idx, self.col_idx)
        if not self.is_resizing:
            self.set_cursor_visible(True)
        else:
            self.set_cursor_visible(False)
    
    def on_click_pressed(self, gesture, n_press, x, y):
        if n_press == 3:
            self.buffer.select_range(
                self.buffer.get_start_iter(),
                self.buffer.get_end_iter()
            )
            return True
        elif n_press == 2:
            self.is_editing = True
            self.is_resizing = False
            self.set_cursor_visible(True)
            self.grab_focus()
        return False
    
    def on_motion(self, controller, x, y):
        if x > self.get_allocated_width() - 5:
            self.get_style_context().add_class("resize-col")
            self.is_resizing = True
            self.set_cursor_visible(False)
        elif y > self.get_allocated_height() - 5:
            self.get_style_context().add_class("resize-row")
            self.is_resizing = True
            self.set_cursor_visible(False)
        else:
            self.get_style_context().remove_class("resize-col")
            self.get_style_context().remove_class("resize-row")
            self.is_resizing = False
            if self.is_editing:
                self.set_cursor_visible(True)
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        modifiers = state & Gtk.accelerator_get_default_mod_mask()
        
        if keyval == Gdk.KEY_Escape:
            self.is_editing = not self.is_editing
            self.set_cursor_visible(self.is_editing)
            return True
            
        if self.is_editing and not self.is_resizing:
            if keyval == Gdk.KEY_a and modifiers == Gdk.ModifierType.CONTROL_MASK:
                self.buffer.select_range(
                    self.buffer.get_start_iter(),
                    self.buffer.get_end_iter()
                )
                return True
                
            if keyval == Gdk.KEY_Tab and modifiers == 0:
                self.table_widget.move_to_next_cell()
                return True
                
            if keyval == Gdk.KEY_Tab and modifiers == Gdk.ModifierType.SHIFT_MASK:
                self.table_widget.move_to_previous_cell()
                return True
                
            if keyval == Gdk.KEY_Return and modifiers == 0:
                if self.row_idx == self.table_widget.rows - 1:
                    self.table_widget.add_row()
                self.table_widget.move_to_cell(self.row_idx + 1, self.col_idx)
                return True
        elif not self.is_editing:
            if keyval == Gdk.KEY_Up:
                self.table_widget.move_to_cell(self.row_idx - 1, self.col_idx)
                return True
            elif keyval == Gdk.KEY_Down:
                self.table_widget.move_to_cell(self.row_idx + 1, self.col_idx)
                return True
            elif keyval == Gdk.KEY_Left:
                self.table_widget.move_to_cell(self.row_idx, self.col_idx - 1)
                return True
            elif keyval == Gdk.KEY_Right:
                self.table_widget.move_to_cell(self.row_idx, self.col_idx + 1)
                return True
                
        return False
    
    def get_text(self):
        return self.buffer.get_text(
            self.buffer.get_start_iter(),
            self.buffer.get_end_iter(),
            False
        )
    
    def set_text(self, text):
        self.buffer.set_text(text)

class MarkdownTableObject(Gtk.Grid):
    def __init__(self, rows=3, cols=3):
        super().__init__()
        self.rows = 0
        self.cols = 0
        self.cells = []
        self.current_cell = (0, 0)
        
        self.set_row_spacing(1)
        self.set_column_spacing(1)
        self.set_column_homogeneous(False)
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        grid {
            border: 1px solid #ccc;
            background-color: #eee;
        }
        textview {
            border: 1px solid #bbb;
            border-radius: 2px;
            padding: 2px;
            background-color: white;
            font-size: 12px;
        }
        textview:focus {
            border-color: #3584e4;
        }
        .resize-col {
            cursor: ew-resize;
        }
        .resize-row {
            cursor: ns-resize;
        }
        """)
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        drag_gesture = Gtk.GestureDrag.new()
        drag_gesture.connect("drag-update", self.on_drag_update)
        drag_gesture.connect("drag-end", self.on_drag_end)
        self.add_controller(drag_gesture)
        
        self.create_table(rows, cols)
        
    def create_table(self, rows, cols):
        for r in range(self.rows):
            for c in range(self.cols):
                child = self.get_child_at(c, r)
                if child:
                    self.remove(child)
        
        self.rows = rows
        self.cols = cols
        self.cells = []
        
        for r in range(rows):
            row = []
            for c in range(cols):
                cell = MarkdownTableCell(self, r, c)
                self.attach(cell, c, r, 1, 1)
                row.append(cell)
            self.cells.append(row)
        
        self.queue_draw()
        self.move_to_cell(0, 0)
    
    def on_drag_update(self, gesture, offset_x, offset_y):
        success, start_x, start_y = gesture.get_start_point()
        if not success:
            return
        
        col = int(start_x / 100)
        row = int(start_y / 30)
        if col < self.cols and row < self.rows:
            cell = self.cells[row][col]
            if cell.get_style_context().has_class("resize-col"):
                new_width = max(50, cell.get_allocated_width() + int(offset_x))
                cell.set_size_request(new_width, -1)
            elif cell.get_style_context().has_class("resize-row"):
                new_height = max(20, cell.get_allocated_height() + int(offset_y))
                cell.set_size_request(-1, new_height)
    
    def on_drag_end(self, gesture, offset_x, offset_y):
        col = int(gesture.get_start_point()[1] / 100)
        row = int(gesture.get_start_point()[2] / 30)
        if col < self.cols and row < self.rows:
            cell = self.cells[row][col]
            cell.is_resizing = False
            if cell.is_editing:
                cell.set_cursor_visible(True)
    
    def add_row(self):
        r = self.rows
        self.rows += 1
        row = []
        
        for c in range(self.cols):
            cell = MarkdownTableCell(self, r, c)
            self.attach(cell, c, r, 1, 1)
            row.append(cell)
        
        self.cells.append(row)
        self.queue_draw()
    
    def add_column(self):
        c = self.cols
        self.cols += 1
        
        for r in range(self.rows):
            cell = MarkdownTableCell(self, r, c)
            self.attach(cell, c, r, 1, 1)
            self.cells[r].append(cell)
        
        self.queue_draw()
    
    def remove_row(self, row_idx):
        if self.rows <= 1:
            return
            
        for c in range(self.cols):
            child = self.get_child_at(c, row_idx)
            if child:
                self.remove(child)
        
        del self.cells[row_idx]
        self.rows -= 1
        
        for r in range(row_idx, self.rows):
            for c in range(self.cols):
                self.cells[r][c].row_idx = r
        
        self.queue_draw()
        
        if self.current_cell[0] >= self.rows:
            self.move_to_cell(self.rows - 1, self.current_cell[1])
    
    def remove_column(self, col_idx):
        if self.cols <= 1:
            return
            
        for r in range(self.rows):
            child = self.get_child_at(col_idx, r)
            if child:
                self.remove(child)
            del self.cells[r][col_idx]
            
            for c in range(col_idx, len(self.cells[r])):
                self.cells[r][c].col_idx = c
        
        self.cols -= 1
        self.queue_draw()
        
        if self.current_cell[1] >= self.cols:
            self.move_to_cell(self.current_cell[0], self.cols - 1)
    
    def move_to_cell(self, row, col):
        row = max(0, min(row, self.rows - 1))
        col = max(0, min(col, self.cols - 1))
        
        self.current_cell = (row, col)
        self.cells[row][col].grab_focus()
    
    def move_to_next_cell(self):
        row, col = self.current_cell
        col += 1
        
        if col >= self.cols:
            col = 0
            row += 1
            
        if row >= self.rows:
            row = 0
            
        self.move_to_cell(row, col)
    
    def move_to_previous_cell(self):
        row, col = self.current_cell
        col -= 1
        
        if col < 0:
            col = self.cols - 1
            row -= 1
            
        if row < 0:
            row = self.rows - 1
            
        self.move_to_cell(row, col)
    
    def to_markdown(self):
        result = []
        col_widths = [0] * self.cols
        for r in range(self.rows):
            for c in range(self.cols):
                text = self.cells[r][c].get_text()
                col_widths[c] = max(col_widths[c], len(text))
        
        row_text = []
        for c in range(self.cols):
            text = self.cells[0][c].get_text()
            row_text.append(text.ljust(col_widths[c]))
        result.append("| " + " | ".join(row_text) + " |")
        
        sep_row = []
        for c in range(self.cols):
            sep_row.append("-" * max(3, col_widths[c]))
        result.append("| " + " | ".join(sep_row) + " |")
        
        for r in range(1, self.rows):
            row_text = []
            for c in range(self.cols):
                text = self.cells[r][c].get_text()
                row_text.append(text.ljust(col_widths[c]))
            result.append("| " + " | ".join(row_text) + " |")
        
        return "\n".join(result)
    
    def from_markdown(self, markdown_text):
        lines = markdown_text.strip().split("\n")
        
        if len(lines) < 3:
            return False
            
        for line in lines:
            if not line.startswith("|") or not line.endswith("|"):
                return False
                
        data_rows = [lines[0]] + lines[2:]
        cols = len(re.findall(r"\|", lines[0])) - 1
        rows = len(data_rows)
        
        self.create_table(rows, cols)
        
        for r, line in enumerate(data_rows):
            cells = line.strip("|").split("|")
            for c, cell_text in enumerate(cells):
                if c < self.cols:
                    self.cells[r][c].set_text(cell_text.strip())
        
        return True

class MarkdownImageObject(Gtk.Image):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file_path, 200, -1, True)
        self.set_from_pixbuf(pixbuf)
        self.set_size_request(200, -1)
    
    def to_markdown(self):
        return f"![Image]({self.file_path})"

class UndoRedoManager:
    def __init__(self, text_buffer, text_view):
        self.text_buffer = text_buffer
        self.text_view = text_view
        self.undo_stack = []
        self.redo_stack = []
        self.is_modifying = False
        self.anchor_widgets = {}  # Store anchor-to-widget mapping
        
        text_buffer.connect("insert-text", self.on_insert_text)
        text_buffer.connect("delete-range", self.on_delete_range)
    
    def add_widget(self, anchor, widget):
        self.anchor_widgets[anchor] = widget
    
    def on_insert_text(self, buffer, location, text, length):
        if self.is_modifying:
            return
        self.undo_stack.append(("insert", location.get_offset(), text))
        self.redo_stack.clear()
    
    def on_delete_range(self, buffer, start, end):
        if self.is_modifying:
            return
        deleted_text = buffer.get_text(start, end, False)
        anchors = []
        iter_start = start.copy()
        while iter_start.get_offset() < end.get_offset():
            anchor = iter_start.get_child_anchor()
            if anchor and anchor in self.anchor_widgets:
                widget = self.anchor_widgets[anchor]
                if isinstance(widget, (MarkdownTableObject, MarkdownImageObject)):
                    anchors.append((iter_start.get_offset(), widget.to_markdown()))
            iter_start.forward_char()
        self.undo_stack.append(("delete", start.get_offset(), end.get_offset() - start.get_offset(), deleted_text, anchors))
        self.redo_stack.clear()
    
    def undo(self):
        if not self.undo_stack:
            return
        self.is_modifying = True
        action = self.undo_stack.pop()
        if action[0] == "insert":
            offset, text = action[1], action[2]
            start = self.text_buffer.get_iter_at_offset(offset)
            end = self.text_buffer.get_iter_at_offset(offset + len(text))
            self.text_buffer.delete(start, end)
            self.redo_stack.append(("delete", offset, len(text), text, []))
        elif action[0] == "delete":
            offset, length, text, anchors = action[1], action[2], action[3], action[4]
            start = self.text_buffer.get_iter_at_offset(offset)
            self.text_buffer.insert(start, text)
            for anchor_offset, markdown in anchors:
                iter_at = self.text_buffer.get_iter_at_offset(anchor_offset)
                if "![Image](" in markdown:
                    file_path = markdown.split("(")[1].rstrip(")")
                    obj = MarkdownImageObject(file_path)
                else:
                    obj = MarkdownTableObject()
                    obj.from_markdown(markdown)
                anchor = self.text_buffer.create_child_anchor(iter_at)
                self.text_view.add_child_at_anchor(obj, anchor)
                self.anchor_widgets[anchor] = obj
            self.redo_stack.append(action)
        self.is_modifying = False
    
    def redo(self):
        if not self.redo_stack:
            return
        self.is_modifying = True
        action = self.redo_stack.pop()
        if action[0] == "insert":
            offset, text = action[1], action[2]
            start = self.text_buffer.get_iter_at_offset(offset)
            self.text_buffer.insert(start, text)
            self.undo_stack.append(action)
        elif action[0] == "delete":
            offset, length, text, anchors = action[1], action[2], action[3], action[4]
            start = self.text_buffer.get_iter_at_offset(offset)
            end = self.text_buffer.get_iter_at_offset(offset + length)
            self.text_buffer.delete(start, end)
            self.undo_stack.append(action)
        self.is_modifying = False

class MarkdownTableEditor(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_title("Markdown Table Editor")
        self.set_default_size(800, 600)
        
        self.current_file = None
        self.unsaved_changes = False
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.box)
        
        self.create_toolbar()
        
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_buffer = self.text_view.get_buffer()
        
        self.undo_redo = UndoRedoManager(self.text_buffer, self.text_view)
        
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_child(self.text_view)
        self.box.append(self.scrolled)
    
    def create_toolbar(self):
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toolbar.add_css_class("toolbar")
        toolbar.set_spacing(6)
        toolbar.set_margin_start(6)
        toolbar.set_margin_end(6)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        
        insert_table_button = Gtk.Button()
        insert_table_button.set_icon_name("table-symbolic")
        insert_table_button.set_tooltip_text("Insert Table")
        insert_table_button.connect("clicked", self.on_insert_table)
        toolbar.append(insert_table_button)
        
        insert_image_button = Gtk.Button()
        insert_image_button.set_icon_name("image-x-generic-symbolic")
        insert_image_button.set_tooltip_text("Insert Image")
        insert_image_button.connect("clicked", self.on_insert_image)
        toolbar.append(insert_image_button)
        
        self.box.append(toolbar)
    
    def on_insert_table(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Insert New Table",
            body="Choose table dimensions:"
        )
        
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("insert", "Insert")
        dialog.set_default_response("insert")
        dialog.set_response_appearance("insert", Adw.ResponseAppearance.SUGGESTED)
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_spacing(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        rows_label = Gtk.Label(label="Rows:")
        box.append(rows_label)
        
        rows_spin = Gtk.SpinButton.new_with_range(1, 50, 1)
        rows_spin.set_value(3)
        box.append(rows_spin)
        
        cols_label = Gtk.Label(label="Columns:")
        box.append(cols_label)
        
        cols_spin = Gtk.SpinButton.new_with_range(1, 20, 1)
        cols_spin.set_value(3)
        box.append(cols_spin)
        
        dialog.set_extra_child(box)
        
        dialog.connect("response", self.on_insert_table_response, rows_spin, cols_spin)
        dialog.present()
    
    def on_insert_table_response(self, dialog, response, rows_spin, cols_spin):
        if response == "insert":
            rows = rows_spin.get_value_as_int()
            cols = cols_spin.get_value_as_int()
            
            table = MarkdownTableObject(rows, cols)
            cursor_iter = self.text_buffer.get_iter_at_mark(
                self.text_buffer.get_insert()
            )
            if not cursor_iter.starts_line():
                self.text_buffer.insert(cursor_iter, "\n")
            anchor = self.text_buffer.create_child_anchor(cursor_iter)
            self.text_view.add_child_at_anchor(table, anchor)
            self.undo_redo.add_widget(anchor, table)
            self.text_buffer.insert(cursor_iter, "\n")
            self.unsaved_changes = True
            self.undo_redo.undo_stack.append(("insert", cursor_iter.get_offset(), table.to_markdown()))
        
        dialog.destroy()
    
    def on_insert_image(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select Image",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN
        )
        
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Open", Gtk.ResponseType.ACCEPT
        )
        
        filter_image = Gtk.FileFilter()
        filter_image.set_name("Image files")
        filter_image.add_mime_type("image/png")
        filter_image.add_mime_type("image/jpeg")
        filter_image.add_mime_type("image/gif")
        dialog.add_filter(filter_image)
        
        dialog.connect("response", self.on_insert_image_response)
        dialog.present()
    
    def on_insert_image_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            image = MarkdownImageObject(file_path)
            cursor_iter = self.text_buffer.get_iter_at_mark(
                self.text_buffer.get_insert()
            )
            if not cursor_iter.starts_line():
                self.text_buffer.insert(cursor_iter, "\n")
            anchor = self.text_buffer.create_child_anchor(cursor_iter)
            self.text_view.add_child_at_anchor(image, anchor)
            self.undo_redo.add_widget(anchor, image)
            self.text_buffer.insert(cursor_iter, "\n")
            self.unsaved_changes = True
            self.undo_redo.undo_stack.append(("insert", cursor_iter.get_offset(), image.to_markdown()))
        
        dialog.destroy()
    
    def save_file(self, file_path=None):
        path = file_path or self.current_file
        
        if not path:
            return False
            
        try:
            start, end = self.text_buffer.get_bounds()
            text = self.text_buffer.get_text(start, end, False)
            
            iter_start = start.copy()
            while iter_start.forward_to_tag_toggle(None):
                anchor = iter_start.get_child_anchor()
                if anchor and anchor in self.undo_redo.anchor_widgets:
                    widget = self.undo_redo.anchor_widgets[anchor]
                    if isinstance(widget, (MarkdownTableObject, MarkdownImageObject)):
                        markdown = widget.to_markdown()
                        anchor_start = self.text_buffer.get_iter_at_child(anchor)
                        text = (text[:anchor_start.get_offset()] + 
                               markdown + 
                               text[anchor_start.get_offset():])
                if not iter_start.forward_char():
                    break
            
            with open(path, 'w') as f:
                f.write(text)
                
            self.current_file = path
            self.unsaved_changes = False
            self.set_title(f"Markdown Table Editor - {os.path.basename(path)}")
            return True
        except Exception as e:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Save Error",
                body=f"Could not save the file: {str(e)}"
            )
            dialog.add_response("ok", "OK")
            dialog.present()
            return False
    
    def open_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            self.text_buffer.set_text("")
            
            pos = 0
            table_pattern = r'\|.*?\n(?:\|[-:| ]*\n)+(?:\|.*?\n)*'
            image_pattern = r'!\[.*?\]\(.*?\)'
            
            for match in re.finditer(f"{table_pattern}|{image_pattern}", content, re.MULTILINE):
                if match.start() > pos:
                    self.text_buffer.insert_at_cursor(content[pos:match.start()])
                
                cursor_iter = self.text_buffer.get_iter_at_mark(
                    self.text_buffer.get_insert()
                )
                if match.group().startswith("|"):
                    table = MarkdownTableObject()
                    if table.from_markdown(match.group()):
                        anchor = self.text_buffer.create_child_anchor(cursor_iter)
                        self.text_view.add_child_at_anchor(table, anchor)
                        self.undo_redo.add_widget(anchor, table)
                        self.text_buffer.insert(cursor_iter, "\n")
                elif match.group().startswith("!["):
                    file_path = match.group().split("(")[1].rstrip(")")
                    if os.path.exists(file_path):
                        image = MarkdownImageObject(file_path)
                        anchor = self.text_buffer.create_child_anchor(cursor_iter)
                        self.text_view.add_child_at_anchor(image, anchor)
                        self.undo_redo.add_widget(anchor, image)
                        self.text_buffer.insert(cursor_iter, "\n")
                
                pos = match.end()
            
            if pos < len(content):
                self.text_buffer.insert_at_cursor(content[pos:])
            
            self.current_file = file_path
            self.unsaved_changes = False
            self.set_title(f"Markdown Table Editor - {os.path.basename(file_path)}")
            return True
        except Exception as e:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Open Error",
                body=f"Could not open the file: {str(e)}"
            )
            dialog.add_response("ok", "OK")
            dialog.present()
            return False
    
    def check_unsaved_changes(self):
        if not self.unsaved_changes:
            return True
            
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Unsaved Changes",
            body="Do you want to save your changes?"
        )
        
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.add_response("save", "Save")
        
        dialog.set_default_response("save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        
        response = dialog.choose()
        
        if response == "cancel":
            return False
        elif response == "save":
            return self.save_file()
        else:
            return True

class MarkdownTableApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.markdown_table_editor")
        self.connect('activate', self.on_activate)
    
    def on_activate(self, app):
        win = MarkdownTableEditor(app)
        win.present()
        
        actions = [
            Gio.SimpleAction.new("new", None),
            Gio.SimpleAction.new("open", None),
            Gio.SimpleAction.new("save", None),
            Gio.SimpleAction.new("save_as", None),
            Gio.SimpleAction.new("about", None),
            Gio.SimpleAction.new("undo", None),
            Gio.SimpleAction.new("redo", None)
        ]
        
        actions[0].connect("activate", self.on_new)
        actions[1].connect("activate", self.on_open)
        actions[2].connect("activate", self.on_save)
        actions[3].connect("activate", self.on_save_as)
        actions[4].connect("activate", self.on_about)
        actions[5].connect("activate", self.on_undo)
        actions[6].connect("activate", self.on_redo)
        
        for action in actions:
            self.add_action(action)
    
    def on_new(self, action, param):
        win = self.get_active_window()
        
        if win.check_unsaved_changes():
            win.text_buffer.set_text("")
            win.current_file = None
            win.unsaved_changes = False
            win.set_title("Markdown Table Editor")
            win.undo_redo.undo_stack.clear()
            win.undo_redo.redo_stack.clear()
    
    def on_open(self, action, param):
        win = self.get_active_window()
        
        if not win.check_unsaved_changes():
            return
            
        dialog = Gtk.FileChooserDialog(
            title="Open File",
            transient_for=win,
            action=Gtk.FileChooserAction.OPEN
        )
        
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Open", Gtk.ResponseType.ACCEPT
        )
        
        filter_md = Gtk.FileFilter()
        filter_md.set_name("Markdown files")
        filter_md.add_mime_type("text/markdown")
        filter_md.add_pattern("*.md")
        dialog.add_filter(filter_md)
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        dialog.connect("response", self.on_open_response)
        dialog.present()
    
    def on_open_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            win = self.get_active_window()
            win.open_file(file_path)
            win.undo_redo.undo_stack.clear()
            win.undo_redo.redo_stack.clear()
        
        dialog.destroy()
    
    def on_save(self, action, param):
        win = self.get_active_window()
        
        if win.current_file:
            win.save_file()
        else:
            self.on_save_as(action, param)
    
    def on_save_as(self, action, param):
        win = self.get_active_window()
        
        dialog = Gtk.FileChooserDialog(
            title="Save File",
            transient_for=win,
            action=Gtk.FileChooserAction.SAVE
        )
        
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Save", Gtk.ResponseType.ACCEPT
        )
        
        dialog.set_do_overwrite_confirmation(True)
        
        filter_md = Gtk.FileFilter()
        filter_md.set_name("Markdown files")
        filter_md.add_mime_type("text/markdown")
        filter_md.add_pattern("*.md")
        dialog.add_filter(filter_md)
        
        if win.current_file:
            dialog.set_file(Gio.File.new_for_path(win.current_file))
        else:
            dialog.set_current_name("table.md")
        
        dialog.connect("response", self.on_save_response)
        dialog.present()
    
    def on_save_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            win = self.get_active_window()
            
            if not file_path.endswith(".md"):
                file_path += ".md"
                
            win.save_file(file_path)
        
        dialog.destroy()
    
    def on_undo(self, action, param):
        win = self.get_active_window()
        win.undo_redo.undo()
    
    def on_redo(self, action, param):
        win = self.get_active_window()
        win.undo_redo.redo()
    
    def on_about(self, action, param):
        win = self.get_active_window()
        
        about = Adw.AboutWindow(
            transient_for=win,
            application_name="Markdown Table Editor",
            application_icon="text-editor-symbolic",
            developer_name="WYSIWYG Markdown Table Editor",
            version="1.0",
            developers=["Markdown Table Editor Team"],
            copyright="© 2025"
        )
        
        about.present()

def main(args):
    app = MarkdownTableApp()
    return app.run(args)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
