import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, Pango, PangoCairo, GdkPixbuf, Gdk

class ResizableWidget(Gtk.Overlay):
    def __init__(self, child, min_width=50, min_height=50, pixbuf=None):
        super().__init__()
        self.child = child
        self.original_pixbuf = pixbuf
        self.set_size_request(min_width, min_height)
        
        # Set the main child (content)
        self.set_child(child)

        # Handle positions
        self.handles = {}
        positions = [
            ("top-left", 0, 0), ("top", 0.5, 0), ("top-right", 1, 0),
            ("left", 0, 0.5), ("right", 1, 0.5),
            ("bottom-left", 0, 1), ("bottom", 0.5, 1), ("bottom-right", 1, 1)
        ]

        # Create resize handles (initially hidden)
        self.handles_visible = False
        for name, x_align, y_align in positions:
            handle = Gtk.DrawingArea()
            handle.set_size_request(10, 10)
            handle.set_draw_func(self.draw_resize_handle, None)
            handle.add_css_class("resize-handle")
            handle.set_visible(False)  # Start hidden
            self.add_overlay(handle)
            self.set_handle_position(handle, x_align, y_align)
            
            drag = Gtk.GestureDrag()
            drag.connect("drag-begin", self.on_drag_begin, name)
            drag.connect("drag-update", self.on_drag_update, name)
            drag.connect("drag-end", self.on_drag_end)
            handle.add_controller(drag)
            self.handles[name] = handle

        # Toggle handles with mouse button release
        click = Gtk.GestureClick()
        click.connect("released", self.on_release)
        self.child.add_controller(click)

        # Drag state for resizing
        self.resizing = False
        self.start_x = 0
        self.start_y = 0
        self.start_width = 0
        self.start_height = 0
        self.start_x_pos = 0
        self.start_y_pos = 0

        # Drag state for moving
        self.dragging = False
        self.drag_gesture = Gtk.GestureDrag()
        self.drag_gesture.connect("drag-begin", self.on_drag_begin_move)
        self.drag_gesture.connect("drag-update", self.on_drag_update_move)
        self.drag_gesture.connect("drag-end", self.on_drag_end_move)
        self.add_controller(self.drag_gesture)

        # CSS for resize handles
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            .resize-handle {
                background-color: gray;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def set_handle_position(self, handle, x_align, y_align):
        handle.set_halign(Gtk.Align.START if x_align == 0 else Gtk.Align.END if x_align == 1 else Gtk.Align.CENTER)
        handle.set_valign(Gtk.Align.START if y_align == 0 else Gtk.Align.END if y_align == 1 else Gtk.Align.CENTER)
        handle.set_margin_start(-5 if x_align == 0 else 0)
        handle.set_margin_end(-5 if x_align == 1 else 0)
        handle.set_margin_top(-5 if y_align == 0 else 0)
        handle.set_margin_bottom(-5 if y_align == 1 else 0)

    def draw_resize_handle(self, area, cr, width, height, data):
        cr.set_source_rgb(0.5, 0.5, 0.5)  # Gray color
        cr.rectangle(0, 0, width, height)
        cr.fill()

    def on_release(self, gesture, n_press, x, y):
        if not self.dragging and not self.resizing:
            self.handles_visible = not self.handles_visible
            print(f"Toggling handles: {'visible' if self.handles_visible else 'hidden'}")
            for handle in self.handles.values():
                handle.set_visible(self.handles_visible)
            self.drag_gesture.set_state(Gtk.EventSequenceState.DENIED if self.handles_visible else Gtk.EventSequenceState.CLAIMED)

    def on_drag_begin(self, gesture, x, y, handle_name):
        self.resizing = True
        self.start_x = x
        self.start_y = y
        self.start_width = self.get_allocated_width()
        self.start_height = self.get_allocated_height()
        allocation = self.get_allocation()
        self.start_x_pos = allocation.x
        self.start_y_pos = allocation.y
        self.current_handle = handle_name
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        print(f"Resizing started with handle: {handle_name}")

    def on_drag_update(self, gesture, offset_x, offset_y, handle_name):
        if not self.resizing:
            return

        new_width = self.start_width
        new_height = self.start_height
        new_x = self.start_x_pos
        new_y = self.start_y_pos

        if "left" in handle_name:
            new_width = max(50, self.start_width - offset_x)
            new_x = self.start_x_pos + (self.start_width - new_width)
        elif "right" in handle_name:
            new_width = max(50, self.start_width + offset_x)

        if "top" in handle_name:
            new_height = max(50, self.start_height - offset_y)
            new_y = self.start_y_pos + (self.start_height - new_height)
        elif "bottom" in handle_name:
            new_height = max(50, self.start_height + offset_y)

        self.set_size_request(new_width, new_height)
        if "left" in handle_name or "top" in handle_name:
            self.translate_coordinates(self.get_parent(), new_x, new_y)
        print(f"Resizing: width={new_width}, height={new_height}, x={new_x}, y={new_y}")

        if self.original_pixbuf:
            scaled_pixbuf = self.original_pixbuf.scale_simple(
                int(new_width), int(new_height), GdkPixbuf.InterpType.BILINEAR
            )
            self.child.set_from_pixbuf(scaled_pixbuf)

    def on_drag_end(self, gesture, offset_x, offset_y):
        self.resizing = False
        print("Resizing ended")

    def on_drag_begin_move(self, gesture, x, y):
        if self.handles_visible:
            return
        self.dragging = True
        self.start_x = x
        self.start_y = y
        allocation = self.get_allocation()
        self.start_x_pos = allocation.x
        self.start_y_pos = allocation.y
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        print(f"Dragging started at x={x}, y={y}")

    def on_drag_update_move(self, gesture, offset_x, offset_y):
        if not self.dragging or self.handles_visible:
            return
        new_x = self.start_x_pos + offset_x
        new_y = self.start_y_pos + offset_y
        self.translate_coordinates(self.get_parent(), new_x, new_y)
        print(f"Dragging to x={new_x}, y={new_y}")

    def on_drag_end_move(self, gesture, offset_x, offset_y):
        self.dragging = False
        print("Dragging ended")

class TextEditor(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Text Editor")
        
        # Main layout
        self.set_default_size(800, 600)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.box)

        # Toolbar with Adwaita styling
        self.header = Adw.HeaderBar()
        self.box.append(self.header)

        # Text style group
        text_style_group = Gtk.Box(spacing=6)
        self.header.pack_start(text_style_group)

        # Font dropdown
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

        # Size dropdown
        self.size_map = ["6", "8", "10", "12", "14", "16", "18", "24", "36"]
        size_store = Gtk.StringList(strings=self.size_map)
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(3)  # Default to 12
        self.size_dropdown.connect("notify::selected", self.on_font_size_changed)
        self.size_dropdown.add_css_class("flat")
        text_style_group.append(self.size_dropdown)

        # Text format group
        text_format_group = Gtk.Box(spacing=6)
        self.header.pack_start(text_format_group)

        # Formatting buttons
        self.bold_btn = Gtk.ToggleButton(icon_name="format-text-bold-symbolic")
        self.bold_btn.add_css_class("flat")
        self.bold_btn.connect("toggled", self.on_bold_toggled)
        text_format_group.append(self.bold_btn)

        self.italic_btn = Gtk.ToggleButton(icon_name="format-text-italic-symbolic")
        self.italic_btn.add_css_class("flat")
        self.italic_btn.connect("toggled", self.on_italic_toggled)
        text_format_group.append(self.italic_btn)

        self.underline_btn = Gtk.ToggleButton(icon_name="format-text-underline-symbolic")
        self.underline_btn.add_css_class("flat")
        self.underline_btn.connect("toggled", self.on_underline_toggled)
        text_format_group.append(self.underline_btn)

        # Additional feature buttons
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

        self.align_left_btn = Gtk.Button(icon_name="format-justify-left-symbolic")
        self.align_left_btn.add_css_class("flat")
        self.align_left_btn.connect("clicked", self.on_align_left_clicked)
        feature_group.append(self.align_left_btn)

        self.align_right_btn = Gtk.Button(icon_name="format-justify-right-symbolic")
        self.align_right_btn.add_css_class("flat")
        self.align_right_btn.connect("clicked", self.on_align_right_clicked)
        feature_group.append(self.align_right_btn)

        self.list_btn = Gtk.Button(icon_name="view-list-symbolic")
        self.list_btn.add_css_class("flat")
        self.list_btn.connect("clicked", self.on_list_clicked)
        feature_group.append(self.list_btn)

        # TextView setup (main editor)
        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.textview.set_top_margin(10)
        self.textview.set_bottom_margin(10)
        self.buffer = self.textview.get_buffer()
        self.buffer.set_text("Type here...")

        # Create text tags for main editor
        self.bold_tag = self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.italic_tag = self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.underline_tag = self.buffer.create_tag("underline", underline=Pango.Underline.SINGLE)
        self.font_tag = self.buffer.create_tag("font")
        self.left_align_tag = self.buffer.create_tag("left", justification=Gtk.Justification.LEFT)
        self.right_align_tag = self.buffer.create_tag("right", justification=Gtk.Justification.RIGHT)
        self.list_tag = self.buffer.create_tag("list", left_margin=20, indent=-10)

        # Wrap main TextView in a ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.textview)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

    def apply_tag_to_selection(self, tag):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            if tag in [self.bold_tag, self.italic_tag, self.underline_tag]:
                active = (tag == self.bold_tag and self.bold_btn.get_active()) or \
                         (tag == self.italic_tag and self.italic_btn.get_active()) or \
                         (tag == self.underline_tag and self.underline_btn.get_active())
                if active:
                    self.buffer.apply_tag(tag, start, end)
                else:
                    self.buffer.remove_tag(tag, start, end)

    def on_font_family_changed(self, dropdown, _pspec):
        font_name = dropdown.get_selected_item().get_string()
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.remove_tag(self.font_tag, start, end)
            self.font_tag = self.buffer.create_tag(None, family=font_name)
            self.buffer.apply_tag(self.font_tag, start, end)
        else:
            self.font_tag = self.buffer.create_tag(None, family=font_name)

    def on_font_size_changed(self, dropdown, _pspec):
        size = int(dropdown.get_selected_item().get_string())
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.remove_tag(self.font_tag, start, end)
            self.font_tag = self.buffer.create_tag(None, size=size * Pango.SCALE)
            self.buffer.apply_tag(self.font_tag, start, end)
        else:
            self.font_tag = self.buffer.create_tag(None, size=size * Pango.SCALE)

    def on_bold_toggled(self, button):
        self.apply_tag_to_selection(self.bold_tag)

    def on_italic_toggled(self, button):
        self.apply_tag_to_selection(self.italic_tag)

    def on_underline_toggled(self, button):
        self.apply_tag_to_selection(self.underline_tag)

    def on_insert_text_clicked(self, button):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_type=Gtk.MessageType.QUESTION,
            text="Insert Rich Text Box",
            secondary_text="Enter the text for the resizable rich text box:"
        )
        entry = Gtk.Entry()
        dialog.get_content_area().append(entry)
        dialog.connect("response", self.on_insert_text_response, entry)
        dialog.present()

    def on_insert_text_response(self, dialog, response, entry):
        if response == Gtk.ResponseType.OK:
            text = entry.get_text()
            if text:
                # Create a TextView for rich text
                text_view = Gtk.TextView()
                text_view.set_wrap_mode(Gtk.WrapMode.WORD)
                text_view.set_editable(True)
                text_view.set_cursor_visible(True)
                buffer = text_view.get_buffer()
                buffer.set_text(text)

                # Add basic rich text tags
                buffer.create_tag("bold", weight=Pango.Weight.BOLD)
                buffer.create_tag("italic", style=Pango.Style.ITALIC)
                buffer.create_tag("underline", underline=Pango.Underline.SINGLE)

                # Wrap in a ScrolledWindow for scrollable content
                scrolled = Gtk.ScrolledWindow()
                scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
                scrolled.set_child(text_view)
                
                # Insert into ResizableWidget
                resizable_box = ResizableWidget(scrolled, min_width=100, min_height=100)
                anchor = self.buffer.create_child_anchor(self.buffer.get_iter_at_mark(self.buffer.get_insert()))
                self.textview.add_child_at_anchor(resizable_box, anchor)
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
            file_path = dialog.get_file().get_path()
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(file_path, 100, 100)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            resizable_image = ResizableWidget(image, min_width=100, min_height=100, pixbuf=pixbuf)
            anchor = self.buffer.create_child_anchor(self.buffer.get_iter_at_mark(self.buffer.get_insert()))
            self.textview.add_child_at_anchor(resizable_image, anchor)
        dialog.destroy()

    def on_align_left_clicked(self, button):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.apply_tag(self.left_align_tag, start, end)
            self.buffer.remove_tag(self.right_align_tag, start, end)

    def on_align_right_clicked(self, button):
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.apply_tag(self.right_align_tag, start, end)
            self.buffer.remove_tag(self.left_align_tag, start, end)

    def on_list_clicked(self, button):
        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.buffer.insert(cursor, "\n• ")
        if self.buffer.get_has_selection():
            start, end = self.buffer.get_selection_bounds()
            self.buffer.apply_tag(self.list_tag, start, end)

class EditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.TextEditor")
    
    def do_activate(self):
        window = TextEditor(self)
        window.present()

if __name__ == "__main__":
    app = EditorApp()
    app.run()
