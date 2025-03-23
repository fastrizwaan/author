#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GObject, GLib, Gio
import re
import os
import sys

class MarkdownTableCell(Gtk.TextView):
    def __init__(self, table_widget, row_idx, col_idx):
        super().__init__()
        self.table_widget = table_widget
        self.row_idx = row_idx
        self.col_idx = col_idx
        
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_accepts_tab(False)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        self.buffer = self.get_buffer()
        
        # Set up key controller for navigation and selection
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        
        # Set up gesture for triple click
        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_button(1)  # Left mouse button
        click_gesture.connect("pressed", self.on_click_pressed)
        self.add_controller(click_gesture)
        
        # Focus handling using EventControllerFocus
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect("enter", self.on_focus_in)
        self.add_controller(focus_controller)
        
    def on_focus_in(self, controller):
        self.table_widget.current_cell = (self.row_idx, self.col_idx)
    
    def on_click_pressed(self, gesture, n_press, x, y):
        if n_press == 3:  # Triple click
            self.buffer.select_range(
                self.buffer.get_start_iter(),
                self.buffer.get_end_iter()
            )
            return True
        return False
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        modifiers = state & Gtk.accelerator_get_default_mod_mask()
        
        # Ctrl+A to select all text in cell
        if keyval == Gdk.KEY_a and modifiers == Gdk.ModifierType.CONTROL_MASK:
            self.buffer.select_range(
                self.buffer.get_start_iter(),
                self.buffer.get_end_iter()
            )
            return True
            
        # Tab navigation
        if keyval == Gdk.KEY_Tab and modifiers == 0:
            self.table_widget.move_to_next_cell()
            return True
            
        # Shift+Tab navigation
        if keyval == Gdk.KEY_Tab and modifiers == Gdk.ModifierType.SHIFT_MASK:
            self.table_widget.move_to_previous_cell()
            return True
            
        # Enter creates new row or moves down
        if keyval == Gdk.KEY_Return and modifiers == 0:
            if self.row_idx == self.table_widget.rows - 1:
                self.table_widget.add_row()
            self.table_widget.move_to_cell(self.row_idx + 1, self.col_idx)
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

class MarkdownTableWidget(Gtk.Grid):
    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor
        self.rows = 0
        self.cols = 0
        self.cells = []
        self.current_cell = (0, 0)
        
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_row_spacing(1)
        self.set_column_spacing(1)
        self.set_column_homogeneous(True)
        
        # Add border and styling using CSS provider
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        grid {
            border: 1px solid #ccc;
            background-color: #eee;
        }
        textview {
            border: 1px solid #bbb;
            border-radius: 2px;
            padding: 4px;
            background-color: white;
        }
        textview:focus {
            border-color: #3584e4;
        }
        """)
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
    def create_table(self, rows, cols):
        # Clear any existing cells
        for r in range(self.rows):
            for c in range(self.cols):
                child = self.get_child_at(c, r)
                if child:
                    self.remove(child)
        
        self.rows = rows
        self.cols = cols
        self.cells = []
        
        # Create cells
        for r in range(rows):
            row = []
            for c in range(cols):
                cell = MarkdownTableCell(self, r, c)
                self.attach(cell, c, r, 1, 1)
                row.append(cell)
            self.cells.append(row)
        
        self.queue_draw()
        self.move_to_cell(0, 0)
    
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
        
        # Update row indices for cells below the removed row
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

class MarkdownTableEditor(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_title("Markdown Table Editor")
        self.set_default_size(800, 600)
        
        self.current_file = None
        self.unsaved_changes = False
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.box)
        
        self.create_header_bar()
        self.create_toolbar()
        
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.box.append(self.scrolled)
        
        self.table_widget = MarkdownTableWidget(self)
        self.scrolled.set_child(self.table_widget)
        
        self.table_widget.create_table(3, 3)
    
    def create_header_bar(self):
        header = Adw.HeaderBar()
        self.header_bar = header
        
        file_menu = Gio.Menu.new()
        file_menu.append("New", "app.new")
        file_menu.append("Open", "app.open")
        file_menu.append("Save", "app.save")
        file_menu.append("Save As", "app.save_as")
        
        file_button = Gtk.MenuButton()
        file_button.set_icon_name("document-new-symbolic")
        file_button.set_menu_model(file_menu)
        header.pack_start(file_button)
        
        app_menu = Gio.Menu.new()
        app_menu.append("About", "app.about")
        
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(app_menu)
        header.pack_end(menu_button)
        
        self.box.append(header)
    
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
        insert_table_button.set_tooltip_text("Insert New Table")
        insert_table_button.connect("clicked", self.on_insert_table)
        toolbar.append(insert_table_button)
        
        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        
        add_row_button = Gtk.Button()
        add_row_button.set_icon_name("list-add-symbolic")
        add_row_button.set_tooltip_text("Add Row")
        add_row_button.connect("clicked", self.on_add_row)
        toolbar.append(add_row_button)
        
        remove_row_button = Gtk.Button()
        remove_row_button.set_icon_name("list-remove-symbolic")
        remove_row_button.set_tooltip_text("Remove Row")
        remove_row_button.connect("clicked", self.on_remove_row)
        toolbar.append(remove_row_button)
        
        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        
        add_col_button = Gtk.Button()
        add_col_button.set_icon_name("view-column-add-symbolic")
        add_col_button.set_tooltip_text("Add Column")
        add_col_button.connect("clicked", self.on_add_column)
        toolbar.append(add_col_button)
        
        remove_col_button = Gtk.Button()
        remove_col_button.set_icon_name("view-column-remove-symbolic")
        remove_col_button.set_tooltip_text("Remove Column")
        remove_col_button.connect("clicked", self.on_remove_column)
        toolbar.append(remove_col_button)
        
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
        
        content_area = dialog.get_content_area()
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
        
        content_area.append(box)
        
        dialog.connect("response", self.on_insert_table_response, rows_spin, cols_spin)
        dialog.present()
    
    def on_insert_table_response(self, dialog, response, rows_spin, cols_spin):
        if response == "insert":
            rows = rows_spin.get_value_as_int()
            cols = cols_spin.get_value_as_int()
            self.table_widget.create_table(rows, cols)
            self.unsaved_changes = True
        
        dialog.destroy()
    
    def on_add_row(self, button):
        self.table_widget.add_row()
        self.unsaved_changes = True
    
    def on_remove_row(self, button):
        row, _ = self.table_widget.current_cell
        self.table_widget.remove_row(row)
        self.unsaved_changes = True
    
    def on_add_column(self, button):
        self.table_widget.add_column()
        self.unsaved_changes = True
    
    def on_remove_column(self, button):
        _, col = self.table_widget.current_cell
        self.table_widget.remove_column(col)
        self.unsaved_changes = True
    
    def save_file(self, file_path=None):
        path = file_path or self.current_file
        
        if not path:
            return False
            
        try:
            markdown = self.table_widget.to_markdown()
            with open(path, 'w') as f:
                f.write(markdown)
                
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
                markdown = f.read()
            
            if self.table_widget.from_markdown(markdown):
                self.current_file = file_path
                self.unsaved_changes = False
                self.set_title(f"Markdown Table Editor - {os.path.basename(file_path)}")
                return True
            else:
                dialog = Adw.MessageDialog(
                    transient_for=self,
                    heading="Invalid Format",
                    body="The file does not contain a valid markdown table."
                )
                dialog.add_response("ok", "OK")
                dialog.present()
                return False
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
        
        self.add_action_entries([
            ('new', self.on_new),
            ('open', self.on_open),
            ('save', self.on_save),
            ('save_as', self.on_save_as),
            ('about', self.on_about)
        ])
    
    def on_new(self, action, param):
        win = self.get_active_window()
        
        if win.check_unsaved_changes():
            win.table_widget.create_table(3, 3)
            win.current_file = None
            win.unsaved_changes = False
            win.set_title("Markdown Table Editor")
    
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
