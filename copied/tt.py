import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, Pango, PangoCairo, GdkPixbuf, Gdk

# US Letter size in pixels (96 DPI)
PAGE_WIDTH = 816   # 8.5 inches * 96
PAGE_HEIGHT = 1056 # 11 inches * 96

class BoxedWidget(Gtk.Frame):
    def __init__(self, content, textview, anchor, pixbuf=None):
        super().__init__()
        self.content = content
        self.textview = textview
        self.anchor = anchor
        self.pixbuf = pixbuf
        self.set_child(content)

        # Drag gesture
        self.drag_gesture = Gtk.GestureDrag()
        self.drag_gesture.set_button(1)
        self.drag_gesture.connect("drag-begin", self.on_drag_begin)
        self.drag_gesture.connect("drag-update", self.on_drag_update)
        self.drag_gesture.connect("drag-end", self.on_drag_end)
        self.add_controller(self.drag_gesture)

        # Double-click gesture
        self.click_gesture = Gtk.GestureClick()
        self.click_gesture.set_button(1)
        self.click_gesture.connect("pressed", self.on_click, None)
        self.add_controller(self.click_gesture)

        # Right-click for table context menu
        if isinstance(content, Gtk.Grid):
            self.right_click_gesture = Gtk.GestureClick()
            self.right_click_gesture.set_button(3)
            self.right_click_gesture.connect("pressed", self.on_right_click)
            self.add_controller(self.right_click_gesture)

        self.start_x = 0
        self.start_y = 0
        self.start_x_pos = 0
        self.start_y_pos = 0
        self.new_iter = None

    def on_drag_begin(self, gesture, x, y):
        self.start_x = x
        self.start_y = y
        allocation = self.get_allocation()
        self.start_x_pos = allocation.x
        self.start_y_pos = allocation.y
        self.add_css_class("dragging")
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        print(f"Drag started at x={x}, y={y}")

    def on_drag_update(self, gesture, offset_x, offset_y):
        new_x = self.start_x_pos + offset_x
        new_y = self.start_y_pos + offset_y
        buffer_x, buffer_y = self.textview.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(new_x), int(new_y))
        self.new_iter = self.textview.get_iter_at_location(buffer_x, buffer_y)
        print(f"Dragging to x={new_x}, y={new_y}, iter offset={self.new_iter.get_offset() if self.new_iter else 'None'}")

    def on_drag_end(self, gesture, offset_x, offset_y):
        if self.new_iter:
            buffer = self.textview.get_buffer()
            start_iter = buffer.get_iter_at_child_anchor(self.anchor)
            if start_iter:
                end_iter = start_iter.copy()
                if end_iter.forward_char():
                    buffer.begin_user_action()
                    buffer.delete(start_iter, end_iter)
                    buffer.insert_child_anchor(self.new_iter, self.anchor)
                    buffer.end_user_action()
                    print(f"Dropped at offset: {self.new_iter.get_offset()}")
                else:
                    print("No next character to delete")
            else:
                print("Anchor not found")
        self.remove_css_class("dragging")
        self.new_iter = None
        print("Drag ended")

    def on_click(self, gesture, n_press, x, y, data):
        if n_press == 2:
            if isinstance(self.content, Gtk.TextView):
                self.content.set_editable(True)
                self.content.grab_focus()
                print("Text box set to editable")
            elif isinstance(self.content, Gtk.Picture) and self.pixbuf:
                print("Double-click on image - edit not implemented")
            elif isinstance(self.content, Gtk.Grid):
                print("Double-click on table - select a cell to edit")

    def on_right_click(self, gesture, n_press, x, y):
        if n_press == 1 and isinstance(self.content, Gtk.Grid):
            menu = Gtk.PopoverMenu()
            menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            menu.set_child(menu_box)
            items = [
                ("Insert Row Above", self.insert_row_above),
                ("Insert Row Below", self.insert_row_below),
                ("Insert Column Left", self.insert_column_left),
                ("Insert Column Right", self.insert_column_right),
                ("Delete Row", self.delete_row),
                ("Delete Column", self.delete_column),
                ("Merge Cells", self.merge_cells),
                ("Split Cell", self.split_cell)
            ]
            for label, callback in items:
                item = Gtk.Button(label=label)
                item.connect("clicked", lambda btn: callback(x, y))
                menu_box.append(item)
            menu.set_parent(self)
            menu.set_position(Gtk.PositionType.BOTTOM)
            menu.set_pointing_to(Gdk.Rectangle(x=x, y=y, width=1, height=1))
            menu.popup()

    def get_cell_at_position(self, x, y):
        for i in range(self.content.get_n_rows()):
            for j in range(self.content.get_n_columns()):
                child = self.content.get_child_at(j, i)
                if child and child.get_allocation().contains(x, y):
                    return i, j
        return None, None

    def insert_row_above(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if row is not None:
            self.content.insert_row(row)
            entry = Gtk.Entry()
            entry.set_size_request(50, 30)
            self.content.attach(entry, 0, row, self.content.get_n_columns(), 1)
            print(f"Inserted row above {row}")

    def insert_row_below(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if row is not None:
            self.content.insert_row(row + 1)
            entry = Gtk.Entry()
            entry.set_size_request(50, 30)
            self.content.attach(entry, 0, row + 1, self.content.get_n_columns(), 1)
            print(f"Inserted row below {row}")

    def insert_column_left(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if col is not None:
            self.content.insert_column(col)
            entry = Gtk.Entry()
            entry.set_size_request(50, 30)
            self.content.attach(entry, col, 0, 1, self.content.get_n_rows())
            print(f"Inserted column left of {col}")

    def insert_column_right(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if col is not None:
            self.content.insert_column(col + 1)
            entry = Gtk.Entry()
            entry.set_size_request(50, 30)
            self.content.attach(entry, col + 1, 0, 1, self.content.get_n_rows())
            print(f"Inserted column right of {col}")

    def delete_row(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if row is not None:
            self.content.remove_row(row)
            print(f"Deleted row {row}")

    def delete_column(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if col is not None:
            self.content.remove_column(col)
            print(f"Deleted column {col}")

    def merge_cells(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if row is not None and col is not None and col + 1 < self.content.get_n_columns():
            child = self.content.get_child_at(col, row)
            if isinstance(child, Gtk.Entry):
                next_child = self.content.get_child_at(col + 1, row)
                if next_child:
                    text = child.get_text() + " " + next_child.get_text()
                    self.content.remove_column(col + 1)
                    child.set_text(text)
                    print(f"Merged cells at ({row}, {col}) with ({row}, {col+1})")

    def split_cell(self, x, y):
        row, col = self.get_cell_at_position(x, y)
        if row is not None and col is not None:
            child = self.content.get_child_at(col, row)
            if isinstance(child, Gtk.Entry):
                self.content.insert_column(col + 1)
                new_entry = Gtk.Entry()
                new_entry.set_size_request(50, 30)
                self.content.attach(new_entry, col + 1, row, 1, 1)
                print(f"Split cell at ({row}, {col})")

class Page(Gtk.TextView):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.set_size_request(PAGE_WIDTH, PAGE_HEIGHT)
        self.set_wrap_mode(Gtk.WrapMode.WORD)
        self.set_left_margin(20)
        self.set_right_margin(20)
        self.set_top_margin(20)
        self.set_bottom_margin(20)
        self.buffer = self.get_buffer()
        self.buffer.connect("changed", self.on_buffer_changed)

    def on_buffer_changed(self, buffer):
        self.editor.check_overflow(self)

class TextEditor(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Text Editor")
        
        self.set_default_size(900, 600)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.box)

        self.header = Adw.HeaderBar()
        self.box.append(self.header)

        feature_group = Gtk.Box(spacing=6)
        self.header.pack_end(feature_group)

        self.insert_text_btn = Gtk.Button(icon_name="insert-text-symbolic")
        self.insert_text_btn.add_css_class("flat")
        self.insert_text_btn.connect("clicked", self.on_insert_text_clicked)
        feature_group.append(self.insert_text_btn)

        self.insert_image_btn = Gtk.Button(icon_name="insert-image-symbolic")
        self.insert_image_btn.add_css_class("flat")
        self.insert_image_btn.connect("clicked", self.on_insert_image_clicked)
        feature_group.append(self.insert_image_btn)

        self.insert_table_btn = Gtk.Button(icon_name="view-grid-symbolic")
        self.insert_table_btn.add_css_class("flat")
        self.insert_table_btn.connect("clicked", self.on_insert_table_clicked)
        feature_group.append(self.insert_table_btn)

        # Pages container
        self.pages_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.pages = []
        self.add_page()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.pages_box)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

        # CSS
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            frame {
                border: 1px solid black;
            }
            .dragging {
                border: 2px dashed blue;
            }
            entry {
                min-width: 50px;
                min-height: 30px;
            }
            textview {
                background-color: white;
                border: 1px solid #ccc;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def add_page(self):
        page = Page(self)
        self.pages.append(page)
        self.pages_box.append(page)
        if len(self.pages) == 1:
            page.buffer.set_text("Type here...")
        return page

    def check_overflow(self, page):
        buffer = page.get_buffer()
        bounds = buffer.get_bounds()
        text = buffer.get_text(bounds[0], bounds[1], True)
        
        # Estimate height using Pango layout (simplified)
        layout = page.create_pango_layout(text)
        layout.set_width(PAGE_WIDTH * Pango.SCALE)
        _, height = layout.get_pixel_size()

        if height > PAGE_HEIGHT:
            # Overflow detected, move excess to next page
            iter_at_end = buffer.get_end_iter()
            while layout.get_pixel_size()[1] > PAGE_HEIGHT and iter_at_end.backward_line():
                layout = page.create_pango_layout(buffer.get_text(buffer.get_start_iter(), iter_at_end, True))
            
            if iter_at_end.get_offset() > 0:
                excess_text = buffer.get_text(iter_at_end, buffer.get_end_iter(), True)
                buffer.delete(iter_at_end, buffer.get_end_iter())
                
                next_page = None
                current_idx = self.pages.index(page)
                if current_idx + 1 < len(self.pages):
                    next_page = self.pages[current_idx + 1]
                else:
                    next_page = self.add_page()
                
                next_buffer = next_page.get_buffer()
                next_buffer.insert_at_cursor(excess_text)
                print(f"Text flowed from page {current_idx + 1} to page {current_idx + 2}")

    def on_insert_text_clicked(self, button):
        dialog = Gtk.Window(transient_for=self, modal=True, title="Insert Text")
        dialog.set_default_size(300, 100)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dialog.set_child(box)
        
        label = Gtk.Label(label="Enter the text:")
        box.append(label)
        
        entry = Gtk.Entry()
        box.append(entry)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(button_box)
        
        ok_button = Gtk.Button(label="OK")
        ok_button.connect("clicked", lambda btn: self.on_insert_text_response(dialog, entry))
        button_box.append(ok_button)
        
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda btn: dialog.destroy())
        button_box.append(cancel_button)
        
        dialog.present()

    def on_insert_text_response(self, dialog, entry):
        text = entry.get_text()
        if text:
            text_view = Gtk.TextView()
            text_view.set_wrap_mode(Gtk.WrapMode.WORD)
            text_view.set_editable(False)
            buffer = text_view.get_buffer()
            buffer.set_text(text)
            
            current_page = self.pages[-1]  # Insert on last page
            anchor = current_page.buffer.create_child_anchor(current_page.buffer.get_iter_at_mark(current_page.buffer.get_insert()))
            boxed_widget = BoxedWidget(text_view, current_page, anchor)
            current_page.add_child_at_anchor(boxed_widget, anchor)
            self.check_overflow(current_page)
        dialog.destroy()

    def on_insert_image_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select an Image",
            transient_for=self,
            modal=True,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Open", Gtk.ResponseType.ACCEPT
        )
        dialog.connect("response", self.on_insert_image_response)
        dialog.present()

    def on_insert_image_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            files = dialog.get_files()
            if files:
                file_path = files[0].get_path()
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(file_path, 100, 100)
                image = Gtk.Picture.new_for_pixbuf(pixbuf)
                current_page = self.pages[-1]
                anchor = current_page.buffer.create_child_anchor(current_page.buffer.get_iter_at_mark(current_page.buffer.get_insert()))
                boxed_widget = BoxedWidget(image, current_page, anchor, pixbuf=pixbuf)
                current_page.add_child_at_anchor(boxed_widget, anchor)
                self.check_overflow(current_page)
        dialog.destroy()

    def on_insert_table_clicked(self, button):
        dialog = Gtk.Window(transient_for=self, modal=True, title="Insert Table")
        dialog.set_default_size(300, 150)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dialog.set_child(box)

        rows_label = Gtk.Label(label="Rows:")
        rows_spin = Gtk.SpinButton.new_with_range(1, 10, 1)
        rows_spin.set_value(2)
        box.append(rows_label)
        box.append(rows_spin)

        cols_label = Gtk.Label(label="Columns:")
        cols_spin = Gtk.SpinButton.new_with_range(1, 10, 1)
        cols_spin.set_value(2)
        box.append(cols_label)
        box.append(cols_spin)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(button_box)
        
        ok_button = Gtk.Button(label="OK")
        ok_button.connect("clicked", lambda btn: self.on_insert_table_response(dialog, rows_spin, cols_spin))
        button_box.append(ok_button)
        
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda btn: dialog.destroy())
        button_box.append(cancel_button)
        
        dialog.present()

    def on_insert_table_response(self, dialog, rows_spin, cols_spin):
        rows = int(rows_spin.get_value())
        cols = int(cols_spin.get_value())
        
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)
        
        for i in range(rows):
            for j in range(cols):
                entry = Gtk.Entry()
                entry.set_size_request(50, 30)
                entry.set_placeholder_text(f"Cell {i},{j}")
                grid.attach(entry, j, i, 1, 1)

        current_page = self.pages[-1]
        anchor = current_page.buffer.create_child_anchor(current_page.buffer.get_iter_at_mark(current_page.buffer.get_insert()))
        boxed_widget = BoxedWidget(grid, current_page, anchor)
        current_page.add_child_at_anchor(boxed_widget, anchor)
        self.check_overflow(current_page)
        dialog.destroy()

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.TextEditor")
    
    def do_activate(self):
        window = TextEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
