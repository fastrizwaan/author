#!/usr/bin/env python3

import base64
import mimetypes

import os
import gi, json
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, WebKit, Gio, GLib, Pango, PangoCairo, Gdk
from datetime import datetime

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
        self.is_bold = False
        self.is_italic = False
        self.is_underline = False
        self.is_strikethrough = False
        self.is_bullet_list = False
        self.is_number_list = False
        self.is_align_left = True
        self.is_align_center = False
        self.is_align_right = False
        self.is_align_justify = False
        self.current_font = "Sans"
        self.current_font_size = "12"
        
        # Document state
        self.current_file = None
        self.is_new = True
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()

        # CSS Provider
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(b"""
            .toolbar-container { padding: 6px; background-color: rgba(127, 127, 127, 0.2); }
            .flat { background: none; }
            .flat:hover, .flat:checked { background: rgba(127, 127, 127, 0.25); }
            colorbutton.flat, colorbutton.flat button { background: none; }
            colorbutton.flat:hover, colorbutton.flat button:hover { background: rgba(127, 127, 127, 0.25); }
            dropdown.flat, dropdown.flat button { background: none; border-radius: 5px; }
            dropdown.flat:hover { background: rgba(127, 127, 127, 0.25); }
            .flat-header { background: rgba(127, 127, 127, 0.2); border: none; box-shadow: none; padding: 0; }
            .toolbar-group { margin: 0 3px; }
            .color-indicator { min-height: 3px; min-width: 16px; margin-top: 1px; border-radius: 2px; }
            .color-box { padding: 0; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Main layout
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.webview = WebKit.WebView(editable=True)

        user_content = self.webview.get_user_content_manager()
        user_content.register_script_message_handler('contentChanged')
        user_content.connect('script-message-received::contentChanged', self.on_content_changed_js)
        user_content.register_script_message_handler('selectionChanged')
        user_content.connect('script-message-received::selectionChanged', self.on_selection_changed)
        self.webview.connect('load-changed', self.on_webview_load)

        self.initial_html = """
<!DOCTYPE html>
<head>
    <style>
        body {
            font-family: serif;
            font-size: 12pt;
            margin: 0;
            padding: 0;
            line-height: 1.5;
        }
        @media (prefers-color-scheme: dark) {
            body { background-color: #1e1e1e; color: #e0e0e0; }
            editor { background-color: #1e1e1e; color: #e0e0e0; }
            img.selected { outline-color: #5e97f6; box-shadow: 0 0 10px rgba(94, 151, 246, 0.5); }
            .context-menu { background-color: #333; border-color: #555; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5); }
            .context-menu-item:hover { background-color: #444; }
            .context-menu-separator { background-color: #555; }
            .context-menu-submenu-content { background-color: #333; border-color: #555; }
            .textbox { color: #e0e0e0; border-color: #555; background-color: transparent; }
        }
        @media (prefers-color-scheme: light) {
            body { background-color: #ffffff; color: #000000; }
            editor { background-color: #ffffff; color: #000000; }
            img.selected { outline: 2px solid #4285f4; box-shadow: 0 0 10px rgba(66, 133, 244, 0.5); }
            .context-menu { background-color: white; border-color: #ccc; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2); }
            .context-menu-item:hover { background-color: #f0f0f0; }
            .context-menu-separator { background-color: #e0e0e0; }
            .context-menu-submenu-content { background-color: white; border-color: #ccc; }
            .textbox { color: #000000; border-color: #000; background-color: transparent; } 
        }
        #editor {
            outline: none;
            margin: 0px;
            padding: 20px;
            border: none;
            min-height: 1000px;
            overflow-y: auto;
        }
        img {
            display: inline-block;
            max-width: 50%;
            cursor: move;
            box-sizing: border-box;
            height: auto;
        }
        img.selected {
            outline: 2px solid #4285f4;
            box-shadow: 0 0 10px rgba(66, 133, 244, 0.5);
        }
        img.resizing {
            outline: 2px dashed #4285f4;
        }
        img.align-left {
            float: left;
            margin: 0 15px 10px 0;
            shape-outside: margin-box;
        }
        img.align-right {
            float: right;
            margin: 0 0 10px 15px;
            shape-outside: margin-box;
        }
        img.align-center {
            display: block;
            margin: 10px auto;
            float: none;
        }
        img.align-none {
            float: none;
            margin: 10px 0;
            display: block;
        }
        .text-wrap-none {
            clear: both;
        }
        .resize-handle {
            position: absolute;
            width: 10px;
            height: 10px;
            background-color: #4285f4;
            border: 1px solid white;
            border-radius: 50%;
            z-index: 999;
        }
        .tl-handle { top: -5px; left: -5px; cursor: nw-resize; }
        .tr-handle { top: -5px; right: -5px; cursor: ne-resize; }
        .bl-handle { bottom: -5px; left: -5px; cursor: sw-resize; }
        .br-handle { bottom: -5px; right: -5px; cursor: se-resize; }
        .context-menu {
            position: absolute;
            border: 1px solid;
            border-radius: 4px;
            padding: 5px 0;
            z-index: 1000;
            min-width: 150px;
        }
        .context-menu-item {
            padding: 8px 15px;
            cursor: pointer;
            user-select: none;
        }
        .context-menu-separator {
            height: 1px;
            margin: 5px 0;
        }
        .context-menu-submenu {
            position: relative;
        }
        .context-menu-submenu::after {
            content: '▶';
            position: absolute;
            right: 10px;
            top: 8px;
            font-size: 10px;
        }
        .context-menu-submenu-content {
            display: none;
            position: absolute;
            left: 100%;
            top: 0;
            border: 1px solid;
            border-radius: 4px;
            padding: 5px 0;
            min-width: 150px;
        }
        .context-menu-submenu:hover .context-menu-submenu-content {
            display: block;
        }
    </style>
</head>
<body>
    <div id="editor" contenteditable="true"><p>\u200B</p></div>
</body>
</html>"""

        # Main layout
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


        # In the toolbar groups section (where other buttons are added)
        image_btn = Gtk.Button(icon_name="insert-image-symbolic")
        image_btn.add_css_class("flat")
        image_btn.set_tooltip_text("Insert Image")
        image_btn.connect("clicked", self.on_insert_image_clicked)
        text_format_group.append(image_btn)

        # Insert Textbox button
        textbox_btn = Gtk.Button(icon_name="insert-text-symbolic")  # You might need a custom icon
        textbox_btn.add_css_class("flat")
        textbox_btn.set_tooltip_text("Insert Textbox")
        textbox_btn.connect("clicked", self.on_insert_textbox_clicked)
        text_format_group.append(textbox_btn)
        
        table_btn = Gtk.Button(icon_name="table-symbolic")  # You might need to adjust icon name based on availability
        table_btn.add_css_class("flat")
        table_btn.set_tooltip_text("Insert Table")
        table_btn.connect("clicked", self.on_insert_table_clicked)
        text_format_group.append(table_btn)

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

        scroll.set_child(self.webview)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox)
        content_box.append(scroll)
        toolbar_view.set_content(content_box)

        self.webview.load_html(self.initial_html, "file:///")

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
            ("edit-redo", self.on_redo_clicked)
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
        self.heading_dropdown_handler = self.heading_dropdown.connect("notify::selected", self.on_heading_changed)
        self.heading_dropdown.add_css_class("flat")
        text_style_group.append(self.heading_dropdown)

        # Font dropdown using PangoCairo
        font_map = PangoCairo.FontMap.get_default()
        families = font_map.list_families()
        font_names = sorted([family.get_name() for family in families])
        font_store = Gtk.StringList(strings=font_names)
        self.font_dropdown = Gtk.DropDown(model=font_store)
        default_font_index = font_names.index("Sans") if "Sans" in font_names else 0
        self.font_dropdown.set_selected(default_font_index)
        self.font_dropdown_handler = self.font_dropdown.connect("notify::selected", self.on_font_family_changed)
        self.font_dropdown.add_css_class("flat")
        text_style_group.append(self.font_dropdown)

        # Size dropdown - using point sizes from 6pt to 96pt
        self.size_range = [str(size) for size in [6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72, 96]]
        size_range = [str(i) for i in range(6, 97)]  # 6 to 96 inclusive
        size_store = Gtk.StringList(strings=size_range)
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(6)  # Default to 12pt (index 6 is 12pt: 6,7,8,9,10,11,12)
        self.size_dropdown_handler = self.size_dropdown.connect("notify::selected", self.on_font_size_changed)
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
        self.webview.add_controller(key_controller)
        key_controller.connect("key-pressed", self.on_key_pressed)

        self.connect("close-request", self.on_close_request)

    def on_content_changed_js(self, manager, js_result):
        if getattr(self, 'ignore_changes', False):
            return
        self.is_modified = True
        self.update_title()

    def on_insert_textbox_clicked(self, btn):
        default_text = "Enter text here"
        self.exec_js(
            f"document.execCommand('insertHTML', false, "
            f"'<div class=\"textbox\" contenteditable=\"false\" draggable=\"true\" "
            f"style=\"display: inline-block; padding: 5px; border: 1px solid #000; min-width: 100px;\">{default_text}</div>');"
        )
        self.webview.grab_focus()
        
    def on_insert_image_clicked(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Insert Image")
        filter = Gtk.FileFilter()
        filter.add_mime_type("image/png")
        filter.add_mime_type("image/jpeg")
        filter.add_mime_type("image/gif")
        dialog.set_default_filter(filter)
        dialog.open(self, None, self.on_insert_image_dialog_response)

    def on_insert_image_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.insert_image(file)
        except GLib.Error as e:
            self.show_error_dialog(f"Error opening image: {e.message}")

    def insert_image(self, file):
        try:
            success, contents, _ = file.load_contents()
            if success:
                mime_type, _ = mimetypes.guess_type(file.get_path())
                if not mime_type:
                    mime_type = 'image/png'
                base64_data = base64.b64encode(contents).decode('utf-8')
                data_url = f"data:{mime_type};base64,{base64_data}"
                data_url_escaped = data_url.replace("'", "\\'")
                self.exec_js(
                    f"document.execCommand('insertHTML', false, "
                    f"'<img src=\"{data_url_escaped}\" contenteditable=\"false\" draggable=\"true\">');"
                )
                self.webview.grab_focus()
        except GLib.Error as e:
            self.show_error_dialog(f"Error inserting image: {e.message}")

    def show_error_dialog(self, message):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Error",
            body=message,
            modal=True
        )
        dialog.add_response("ok", "OK")
        dialog.present()
            
    def on_webview_load(self, webview, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            # Initialize cursor position
            self.initialize_cursor_position()
            
            # Setup image handling
            self.setup_image_and_textbox_handling()
            
            # Setup content change notification
            self.setup_content_change_notification()
            
            # Setup selection change notification
            self.setup_selection_change_notification()
            
            # Focus the webview after loading
            GLib.idle_add(self.webview.grab_focus)

    def initialize_cursor_position(self):
        script = """
        (function() {
            const editor = document.getElementById('editor');
            if (!editor) {
                console.error('Editor element not found');
                return;
            }

            // Initialize cursor position
            let p = editor.querySelector('p');
            if (p) {
                let range = document.createRange();
                range.setStart(p, 0);
                range.setEnd(p, 0);
                let sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            }
        })();
        """
        self.exec_js(script)


    def setup_image_and_textbox_handling(self):
        script = """
        (function() {
            const editor = document.getElementById('editor');
            if (!editor) {
                console.error('Editor element not found');
                return;
            }

            // Handling variables
            let selectedElement = null;
            let resizeHandles = [];
            let isDragging = false;
            let isResizing = false;
            let lastX, lastY;
            let resizeStartWidth, resizeStartHeight;
            let currentResizeHandle = null;
            let contextMenu = null;
            let savedRange = null;  // To store caret position/selection
            
            // Current element properties
            let currentBorderWidth = '0';
            let currentBorderStyle = 'solid';
            let currentBorderColor = '#000000';
            let currentBackgroundColor = 'transparent';
            
            // Add additional CSS dynamically
            const style = document.createElement('style');
            style.textContent = `
                img, .textbox {
                    max-width: 100%;
                    box-sizing: border-box;
                    background-color: transparent;
                    cursor: move;
                }
                .textbox {
                    padding: 5px;
                    min-width: 100px;
                    min-height: 20px;
                    overflow-wrap: break-word;
                }
                img.floating, .textbox.floating {
                    position: absolute;
                    z-index: 10;
                }
                img.align-left, .textbox.align-left {
                    float: left;
                    margin: 0 15px 10px 0;
                }
                img.align-right, .textbox.align-right {
                    float: right;
                    margin: 0 0 10px 15px;
                }
                img.align-center, .textbox.align-center {
                    display: block;
                    margin: 10px auto;
                    float: none;
                }
                .resize-handle {
                    position: absolute;
                    width: 10px;
                    height: 10px;
                    background-color: #4285f4;
                    border: 1px solid white;
                    border-radius: 50%;
                    z-index: 999;
                }
                .tl-handle { top: -5px; left: -5px; cursor: nw-resize; }
                .tr-handle { top: -5px; right: -5px; cursor: ne-resize; }
                .bl-handle { bottom: -5px; left: -5px; cursor: sw-resize; }
                .br-handle { bottom: -5px; right: -5px; cursor: se-resize; }
                img.selected, .textbox.selected {
                    outline: 2px solid #4285f4;
                    box-shadow: 0 0 10px rgba(66, 133, 244, 0.5);
                }
                img.resizing, .textbox.resizing {
                    outline: 2px dashed #4285f4;
                }
                .context-menu {
                    position: absolute;
                    border: 1px solid;
                    border-radius: 4px;
                    padding: 5px 0;
                    z-index: 1000;
                    min-width: 150px;
                }
                .context-menu-item {
                    padding: 8px 15px;
                    cursor: pointer;
                    user-select: none;
                }
                .context-menu-separator {
                    height: 1px;
                    margin: 5px 0;
                }
                .context-menu-submenu {
                    position: relative;
                }
                .context-menu-submenu::after {
                    content: '▶';
                    position: absolute;
                    right: 10px;
                    top: 8px;
                    font-size: 10px;
                }
                .context-menu-submenu-content {
                    display: none;
                    position: absolute;
                    left: 100%;
                    top: 0;
                    border: 1px solid;
                    border-radius: 4px;
                    padding: 5px 0;
                    min-width: 150px;
                }
                .context-menu-submenu:hover .context-menu-submenu-content {
                    display: block;
                }
                .color-preview {
                    display: inline-block;
                    width: 15px;
                    height: 15px;
                    border: 1px solid #ccc;
                    margin-right: 5px;
                    vertical-align: middle;
                }
                .transparent-color {
                    background-image: linear-gradient(45deg, #ccc 25%, transparent 25%), 
                                    linear-gradient(-45deg, #ccc 25%, transparent 25%), 
                                    linear-gradient(45deg, transparent 75%, #ccc 75%), 
                                    linear-gradient(-45deg, transparent 75%, #ccc 75%);
                    background-size: 10px 10px;
                    background-position: 0 0, 0 5px, 5px -5px, -5px 0px;
                }
            `;
            document.head.appendChild(style);

            // Save current selection
            function saveSelection() {
                const sel = window.getSelection();
                if (sel.rangeCount > 0) {
                    savedRange = sel.getRangeAt(0).cloneRange();
                }
            }

            // Restore saved selection
            function restoreSelection() {
                if (savedRange) {
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(savedRange);
                    editor.focus();
                }
            }

            // Create resize handles
            function createResizeHandles(element) {
                removeResizeHandles();
                const container = document.createElement('div');
                container.style.position = 'absolute';
                
                if (element.classList.contains('floating')) {
                    container.style.left = element.style.left;
                    container.style.top = element.style.top;
                } else {
                    const rect = element.getBoundingClientRect();
                    const editorRect = editor.getBoundingClientRect();
                    container.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                    container.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                }
                container.style.width = element.offsetWidth + 'px';
                container.style.height = element.offsetHeight + 'px';
                
                container.style.pointerEvents = 'none';
                container.className = 'resize-container';

                const positions = ['tl', 'tr', 'bl', 'br'];
                positions.forEach(pos => {
                    const handle = document.createElement('div');
                    handle.className = `resize-handle ${pos}-handle`;
                    handle.style.pointerEvents = 'all';
                    handle.dataset.position = pos;
                    
                    handle.addEventListener('mousedown', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        startResize(e, handle);
                    });
                    
                    container.appendChild(handle);
                    resizeHandles.push(handle);
                });

                editor.appendChild(container);
            }

            // Remove resize handles
            function removeResizeHandles() {
                const container = editor.querySelector('.resize-container');
                if (container) container.remove();
                resizeHandles = [];
            }

            // Update resize handles position
            function updateResizeHandles() {
                if (!selectedElement) return;
                
                const container = editor.querySelector('.resize-container');
                if (container) {
                    if (selectedElement.classList.contains('floating')) {
                        container.style.left = selectedElement.style.left;
                        container.style.top = selectedElement.style.top;
                    } else {
                        const rect = selectedElement.getBoundingClientRect();
                        const editorRect = editor.getBoundingClientRect();
                        container.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                        container.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                    }
                    container.style.width = selectedElement.offsetWidth + 'px';
                    container.style.height = selectedElement.offsetHeight + 'px';
                }
            }

            // Start resizing
            function startResize(e, handle) {
                if (!selectedElement) return;
                isResizing = true;
                currentResizeHandle = handle;
                lastX = e.clientX;
                lastY = e.clientY;
                resizeStartWidth = selectedElement.offsetWidth;
                resizeStartHeight = selectedElement.offsetHeight;
                selectedElement.classList.add('resizing');
                
                saveSelection();  // Save selection before resizing
                document.addEventListener('mousemove', handleResize);
                document.addEventListener('mouseup', stopResize);
            }

            // Handle resize
            function handleResize(e) {
                if (!isResizing || !selectedElement || !currentResizeHandle) return;
                
                const deltaX = e.clientX - lastX;
                const deltaY = e.clientY - lastY;
                const position = currentResizeHandle.dataset.position;
                
                let newWidth = resizeStartWidth;
                let newHeight = resizeStartHeight;
                
                if (position.includes('r')) newWidth += deltaX;
                if (position.includes('l')) newWidth -= deltaX;
                if (position.includes('b')) newHeight += deltaY;
                if (position.includes('t')) newHeight -= deltaY;
                
                if (e.shiftKey) {
                    const aspectRatio = resizeStartWidth / resizeStartHeight;
                    if (Math.abs(deltaX) > Math.abs(deltaY)) {
                        newHeight = newWidth / aspectRatio;
                    } else {
                        newWidth = newHeight * aspectRatio;
                    }
                }
                
                newWidth = Math.max(20, newWidth);
                newHeight = Math.max(20, newHeight);
                
                selectedElement.style.width = newWidth + 'px';
                selectedElement.style.height = newHeight + 'px';
                
                updateResizeHandles();
            }

            // Stop resizing
            function stopResize() {
                isResizing = false;
                currentResizeHandle = null;
                if (selectedElement) selectedElement.classList.remove('resizing');
                document.removeEventListener('mousemove', handleResize);
                document.removeEventListener('mouseup', stopResize);
                restoreSelection();  // Restore selection after resizing
            }

            // Set border properties
            function setBorder(element, width, style, color) {
                if (!element) return;
                
                if (width) currentBorderWidth = width;
                if (style) currentBorderStyle = style;
                if (color) currentBorderColor = color;
                
                if (currentBorderWidth === '0') {
                    element.style.border = 'none';
                } else {
                    element.style.border = `${currentBorderWidth}px ${currentBorderStyle} ${currentBorderColor}`;
                }
            }

            // Set background color
            function setBackgroundColor(element, color) {
                if (!element) return;
                
                currentBackgroundColor = color;
                element.style.backgroundColor = color;
            }

            // Select element
            function selectElement(element) {
                if (selectedElement) selectedElement.classList.remove('selected');
                selectedElement = element;
                selectedElement.classList.add('selected');
                
                const computedStyle = window.getComputedStyle(element);
                currentBorderWidth = element.style.borderWidth ? parseInt(element.style.borderWidth) + '' : '0';
                currentBorderStyle = element.style.borderStyle || computedStyle.borderStyle || 'solid';
                currentBorderColor = element.style.borderColor || computedStyle.borderColor || '#000000';
                currentBackgroundColor = element.style.backgroundColor || computedStyle.backgroundColor || 'transparent';
                
                createResizeHandles(element);
            }

            // Create color picker dialog
            function createColorPickerDialog(title, initialColor, callback) {
                const overlay = document.createElement('div');
                overlay.style.position = 'fixed';
                overlay.style.top = '0';
                overlay.style.left = '0';
                overlay.style.width = '100%';
                overlay.style.height = '100%';
                overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
                overlay.style.zIndex = '10000';
                overlay.style.display = 'flex';
                overlay.style.justifyContent = 'center';
                overlay.style.alignItems = 'center';
                
                const dialog = document.createElement('div');
                dialog.style.backgroundColor = 'white';
                dialog.style.borderRadius = '5px';
                dialog.style.padding = '20px';
                dialog.style.boxShadow = '0 0 10px rgba(0, 0, 0, 0.3)';
                dialog.style.maxWidth = '300px';
                dialog.style.width = '100%';
                
                const titleElem = document.createElement('h3');
                titleElem.textContent = title;
                titleElem.style.margin = '0 0 15px 0';
                
                const colorInput = document.createElement('input');
                colorInput.type = 'color';
                colorInput.value = initialColor !== 'transparent' && initialColor !== 'rgba(0, 0, 0, 0)' ? 
                                initialColor : '#000000';
                colorInput.style.width = '100%';
                colorInput.style.height = '40px';
                colorInput.style.marginBottom = '15px';
                
                const transparentContainer = document.createElement('div');
                transparentContainer.style.marginBottom = '15px';
                
                const transparentCheckbox = document.createElement('input');
                transparentCheckbox.type = 'checkbox';
                transparentCheckbox.id = 'transparent-checkbox';
                transparentCheckbox.checked = initialColor === 'transparent' || initialColor === 'rgba(0, 0, 0, 0)';
                
                const transparentLabel = document.createElement('label');
                transparentLabel.htmlFor = 'transparent-checkbox';
                transparentLabel.textContent = 'Transparent';
                transparentLabel.style.marginLeft = '5px';
                
                transparentContainer.appendChild(transparentCheckbox);
                transparentContainer.appendChild(transparentLabel);
                
                transparentCheckbox.addEventListener('change', () => {
                    colorInput.disabled = transparentCheckbox.checked;
                });
                colorInput.disabled = transparentCheckbox.checked;
                
                const buttonContainer = document.createElement('div');
                buttonContainer.style.display = 'flex';
                buttonContainer.style.justifyContent = 'flex-end';
                
                const cancelButton = document.createElement('button');
                cancelButton.textContent = 'Cancel';
                cancelButton.style.padding = '5px 10px';
                cancelButton.style.marginRight = '10px';
                
                const okButton = document.createElement('button');
                okButton.textContent = 'OK';
                okButton.style.padding = '5px 10px';
                
                cancelButton.addEventListener('click', () => {
                    document.body.removeChild(overlay);
                    restoreSelection();
                });
                
                okButton.addEventListener('click', () => {
                    const finalColor = transparentCheckbox.checked ? 'transparent' : colorInput.value;
                    callback(finalColor);
                    document.body.removeChild(overlay);
                    restoreSelection();
                });
                
                buttonContainer.appendChild(cancelButton);
                buttonContainer.appendChild(okButton);
                
                dialog.appendChild(titleElem);
                dialog.appendChild(colorInput);
                dialog.appendChild(transparentContainer);
                dialog.appendChild(buttonContainer);
                
                overlay.appendChild(dialog);
                document.body.appendChild(overlay);
            }

            // Create context menu
            function createContextMenu(x, y) {
                removeContextMenu();
                saveSelection();  // Save selection before showing menu
                contextMenu = document.createElement('div');
                contextMenu.className = 'context-menu';
                contextMenu.style.left = x + 'px';
                contextMenu.style.top = y + 'px';
                
                const isTextbox = selectedElement.classList.contains('textbox');
                const menuItems = [
                    ...(isTextbox ? [{ label: 'Edit Text', action: 'edit-text' }] : []),
                    { label: 'Position', submenu: [
                        { label: 'Float', action: 'float' },
                        { label: 'Inline Left', action: 'inline-left' },
                        { label: 'Inline Right', action: 'inline-right' },
                    ]},
                    { label: 'Layer', submenu: [
                        { label: 'Bring Forward', action: 'bring-forward' },
                        { label: 'Send Backward', action: 'send-backward' }
                    ]},
                    { label: 'Border Width', submenu: [
                        { label: 'None', action: 'border-width-0' },
                        { label: '1px', action: 'border-width-1' },
                        { label: '2px', action: 'border-width-2' },
                        { label: '3px', action: 'border-width-3' },
                        { label: '4px', action: 'border-width-4' },
                        { label: '5px', action: 'border-width-5' },
                        { label: '6px', action: 'border-width-6' }
                    ]},
                    { label: 'Border Style', submenu: [
                        { label: 'Solid', action: 'border-style-solid' },
                        { label: 'Dotted', action: 'border-style-dotted' },
                        { label: 'Dashed', action: 'border-style-dashed' },
                        { label: 'Double', action: 'border-style-double' }
                    ]},
                    { label: 'Border Color...', action: 'border-color' },
                    { label: 'Background Color...', action: 'bg-color' },
                    { type: 'separator' },
                    { label: 'Delete', action: 'delete' }
                ];
                
                createMenuItems(contextMenu, menuItems);
                document.body.appendChild(contextMenu);
                setTimeout(() => {
                    document.addEventListener('click', closeContextMenuOnClickOutside);
                }, 0);
            }

            // Create menu items
            function createMenuItems(parent, items) {
                items.forEach(item => {
                    if (item.type === 'separator') {
                        const separator = document.createElement('div');
                        separator.className = 'context-menu-separator';
                        parent.appendChild(separator);
                    } else if (item.submenu) {
                        const submenuItem = document.createElement('div');
                        submenuItem.className = 'context-menu-item context-menu-submenu';
                        submenuItem.textContent = item.label;
                        
                        const submenuContent = document.createElement('div');
                        submenuContent.className = 'context-menu-submenu-content';
                        createMenuItems(submenuContent, item.submenu);
                        
                        submenuItem.appendChild(submenuContent);
                        parent.appendChild(submenuItem);
                    } else {
                        const menuItem = document.createElement('div');
                        menuItem.className = 'context-menu-item';
                        
                        if (item.action === 'border-color') {
                            const colorPreview = document.createElement('span');
                            colorPreview.className = 'color-preview';
                            if (currentBorderColor === 'transparent' || currentBorderColor === 'rgba(0, 0, 0, 0)') {
                                colorPreview.classList.add('transparent-color');
                            } else {
                                colorPreview.style.backgroundColor = currentBorderColor;
                            }
                            menuItem.appendChild(colorPreview);
                        } else if (item.action === 'bg-color') {
                            const colorPreview = document.createElement('span');
                            colorPreview.className = 'color-preview';
                            if (currentBackgroundColor === 'transparent' || currentBackgroundColor === 'rgba(0, 0, 0, 0)') {
                                colorPreview.classList.add('transparent-color');
                            } else {
                                colorPreview.style.backgroundColor = currentBackgroundColor;
                            }
                            menuItem.appendChild(colorPreview);
                        }
                        
                        menuItem.appendChild(document.createTextNode(item.label));
                        
                        if (item.action === 'float' && selectedElement.classList.contains('floating')) {
                            menuItem.style.fontWeight = 'bold';
                        }
                        if (item.action === 'inline-left' && selectedElement.classList.contains('align-left')) {
                            menuItem.style.fontWeight = 'bold';
                        }
                        if (item.action === 'inline-right' && selectedElement.classList.contains('align-right')) {
                            menuItem.style.fontWeight = 'bold';
                        }
                        if (item.action === 'center' && selectedElement.classList.contains('align-center')) {
                            menuItem.style.fontWeight = 'bold';
                        }
                        
                        if (item.action.startsWith('border-width-')) {
                            const width = item.action.replace('border-width-', '');
                            if (selectedElement && width === currentBorderWidth) {
                                menuItem.style.fontWeight = 'bold';
                            }
                        }
                        
                        if (item.action.startsWith('border-style-')) {
                            const style = item.action.replace('border-style-', '');
                            if (selectedElement && style === currentBorderStyle) {
                                menuItem.style.fontWeight = 'bold';
                            }
                        }
                        
                        menuItem.addEventListener('click', (e) => {
                            e.stopPropagation();
                            handleContextMenuAction(item.action);
                            removeContextMenu();
                            restoreSelection();  // Restore selection after action
                        });
                        parent.appendChild(menuItem);
                    }
                });
            }

            // Handle context menu action
            function handleContextMenuAction(action) {
                if (!selectedElement) return;
                
                if (action === 'edit-text') {
                    editor.contentEditable = false;
                    selectedElement.contentEditable = true;
                    selectedElement.focus();
                    
                    const range = document.createRange();
                    const sel = window.getSelection();
                    range.selectNodeContents(selectedElement);
                    range.collapse(false);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    
                    const finishEditing = () => {
                        selectedElement.contentEditable = false;
                        editor.contentEditable = true;
                        selectElement(selectedElement);
                        restoreSelection();  // Restore editor selection after editing
                    };
                    
                    selectedElement.addEventListener('blur', finishEditing, { once: true });
                    selectedElement.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            selectedElement.blur();
                        }
                    });
                } else if (action === 'float') {
                    selectedElement.classList.add('floating');
                    selectedElement.style.position = 'absolute';
                    if (!selectedElement.style.left) selectedElement.style.left = '50px';
                    if (!selectedElement.style.top) selectedElement.style.top = '50px';
                    selectedElement.style.float = '';
                    selectedElement.style.display = 'block';
                    selectedElement.style.margin = '0';
                    selectedElement.classList.remove('align-left', 'align-right', 'align-center');
                    updateResizeHandles();
                } else if (action === 'inline-left') {
                    selectedElement.classList.remove('floating');
                    selectedElement.style.position = '';
                    selectedElement.style.left = '';
                    selectedElement.style.top = '';
                    selectedElement.style.zIndex = '';
                    setAlignment(selectedElement, 'left');
                } else if (action === 'inline-right') {
                    selectedElement.classList.remove('floating');
                    selectedElement.style.position = '';
                    selectedElement.style.left = '';
                    selectedElement.style.top = '';
                    selectedElement.style.zIndex = '';
                    setAlignment(selectedElement, 'right');
                } else if (action === 'center') {
                    selectedElement.classList.remove('floating');
                    selectedElement.style.position = '';
                    selectedElement.style.left = '';
                    selectedElement.style.top = '';
                    selectedElement.style.zIndex = '';
                    setAlignment(selectedElement, 'center');
                } else if (action === 'bring-forward') {
                    let currentZ = parseInt(selectedElement.style.zIndex) || 10;
                    selectedElement.style.zIndex = currentZ + 1;
                } else if (action === 'send-backward') {
                    let currentZ = parseInt(selectedElement.style.zIndex) || 10;
                    selectedElement.style.zIndex = Math.max(0, currentZ - 1);
                } else if (action.startsWith('border-width-')) {
                    const width = action.replace('border-width-', '');
                    setBorder(selectedElement, width, null, null);
                } else if (action.startsWith('border-style-')) {
                    const style = action.replace('border-style-', '');
                    setBorder(selectedElement, null, style, null);
                } else if (action === 'border-color') {
                    saveSelection();  // Save selection before showing dialog
                    createColorPickerDialog('Choose Border Color', currentBorderColor, (color) => {
                        setBorder(selectedElement, null, null, color);
                    });
                } else if (action === 'bg-color') {
                    saveSelection();  // Save selection before showing dialog
                    createColorPickerDialog('Choose Background Color', currentBackgroundColor, (color) => {
                        setBackgroundColor(selectedElement, color);
                    });
                } else if (action === 'delete') {
                    deleteElement(selectedElement);
                }
            }

            // Start dragging
            function startDrag(e, element) {
                if (isResizing) return;
                isDragging = true;
                lastX = e.clientX;
                lastY = e.clientY;
                
                saveSelection();  // Save selection before dragging
                document.addEventListener('mousemove', handleDrag);
                document.addEventListener('mouseup', stopDrag);
            }

            // Handle drag
            function handleDrag(e) {
                if (!isDragging || !selectedElement) return;
                
                if (selectedElement.classList.contains('floating')) {
                    const deltaX = e.clientX - lastX;
                    const deltaY = e.clientY - lastY;
                    let currentLeft = parseInt(selectedElement.style.left) || 0;
                    let currentTop = parseInt(selectedElement.style.top) || 0;
                    
                    selectedElement.style.left = (currentLeft + deltaX) + 'px';
                    selectedElement.style.top = (currentTop + deltaY) + 'px';
                    
                    lastX = e.clientX;
                    lastY = e.clientY;
                    
                    updateResizeHandles();
                } else {
                    const temp = document.createElement('span');
                    temp.style.display = 'inline-block';
                    temp.style.width = '1px';
                    temp.style.height = '1px';
                    
                    const range = document.caretRangeFromPoint(e.clientX, e.clientY);
                    if (range) {
                        range.insertNode(temp);
                        temp.parentNode.insertBefore(selectedElement, temp);
                        temp.remove();
                        updateResizeHandles();
                    }
                }
            }

            // Stop dragging
            function stopDrag() {
                isDragging = false;
                document.removeEventListener('mousemove', handleDrag);
                document.removeEventListener('mouseup', stopDrag);
                restoreSelection();  // Restore selection after dragging
            }

            // Get current alignment
            function getCurrentAlignment(element) {
                if (element.classList.contains('align-left')) return 'left';
                if (element.classList.contains('align-right')) return 'right';
                if (element.classList.contains('align-center')) return 'center';
                return 'left'; // Default
            }

            // Clear alignment classes
            function clearAlignmentClasses(element) {
                element.classList.remove('align-left', 'align-right', 'align-center');
            }

            // Set alignment
            function setAlignment(element, alignment) {
                clearAlignmentClasses(element);
                
                element.style.float = '';
                element.style.display = '';
                element.style.margin = '';
                
                switch (alignment) {
                    case 'left':
                        element.classList.add('align-left');
                        element.style.float = 'left';
                        element.style.margin = '0 15px 10px 0';
                        break;
                    case 'right':
                        element.classList.add('align-right');
                        element.style.float = 'right';
                        element.style.margin = '0 0 10px 15px';
                        break;
                    case 'center':
                        element.classList.add('align-center');
                        element.style.display = 'block';
                        element.style.margin = '10px auto';
                        break;
                }
                
                if (selectedElement === element) {
                    updateResizeHandles();
                }
            }

            // Deselect element
            function deselectElement() {
                if (selectedElement) {
                    selectedElement.classList.remove('selected');
                    selectedElement = null;
                }
                removeResizeHandles();
                restoreSelection();  // Restore selection when deselecting
            }

            // Delete element
            function deleteElement(element) {
                deselectElement();
                element.remove();
            }

            // Remove context menu
            function removeContextMenu() {
                if (contextMenu) {
                    document.removeEventListener('click', closeContextMenuOnClickOutside);
                    contextMenu.remove();
                    contextMenu = null;
                }
            }

            // Close context menu on click outside
            function closeContextMenuOnClickOutside(e) {
                if (contextMenu && !contextMenu.contains(e.target)) {
                    removeContextMenu();
                    restoreSelection();  // Restore selection when closing menu
                }
            }

            // Event listeners
            editor.addEventListener('click', (e) => {
                removeContextMenu();
                if (e.target.tagName === 'IMG' || e.target.classList.contains('textbox')) {
                    e.preventDefault();
                    selectElement(e.target);
                } else {
                    deselectElement();
                }
            });

            editor.addEventListener('contextmenu', (e) => {
                if (e.target.tagName === 'IMG' || e.target.classList.contains('textbox')) {
                    e.preventDefault();
                    selectElement(e.target);
                    createContextMenu(e.clientX, e.clientY);
                }
            });

            editor.addEventListener('mousedown', (e) => {
                if ((e.target.tagName === 'IMG' || e.target.classList.contains('textbox')) && e.button === 0) {
                    e.preventDefault();
                    if (selectedElement !== e.target) {
                        selectElement(e.target);
                    }
                    startDrag(e, e.target);
                }
            });

            window.addEventListener('scroll', () => {
                if (selectedElement) updateResizeHandles();
            });

            editor.addEventListener('scroll', () => {
                if (selectedElement) updateResizeHandles();
            });

            // Initialize existing elements
            editor.querySelectorAll('img, .textbox').forEach(element => {
                element.contentEditable = false;
                element.draggable = true;
                if (!element.classList.contains('floating')) {
                    setAlignment(element, 'left');
                }
            });

            // Mutation observer for new elements
            const observer = new MutationObserver(mutations => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.tagName === 'IMG' || (node.classList && node.classList.contains('textbox'))) {
                            node.contentEditable = false;
                            node.draggable = true;
                            if (!node.classList.contains('floating')) {
                                setAlignment(node, 'left');
                            }
                        }
                    });
                });
            });
            observer.observe(editor, { childList: true, subtree: true });

            // Function to insert and select textbox
            window.insertAndSelectTextbox = function(text) {
                saveSelection();  // Save selection before insertion
                document.execCommand('insertHTML', false, 
                    '<div class="textbox" contenteditable="false" draggable="true" ' +
                    'style="display: inline-block; padding: 5px; border: 1px solid #000; min-width: 100px;">' + 
                    text + '</div>');
                const textboxes = editor.querySelectorAll('.textbox');
                const lastTextbox = textboxes[textboxes.length - 1];
                if (lastTextbox) {
                    selectElement(lastTextbox);
                    setAlignment(lastTextbox, 'left');
                }
                restoreSelection();  // Restore selection after insertion
            };
        })();
        """
        self.exec_js(script)


    def setup_content_change_notification(self):
        script = """
        (function() {
            const editor = document.getElementById('editor');
            if (!editor) {
                console.error('Editor element not found');
                return;
            }
            
            // Content change notification
            function debounce(func, wait) {
                let timeout;
                return function(...args) {
                    clearTimeout(timeout);
                    timeout = setTimeout(() => func(...args), wait);
                };
            }

            let lastContent = editor.innerHTML;
            const notifyChange = debounce(function() {
                let currentContent = editor.innerHTML;
                if (currentContent !== lastContent) {
                    window.webkit.messageHandlers.contentChanged.postMessage('changed');
                    lastContent = currentContent;
                }
            }, 250);

            editor.addEventListener('input', notifyChange);
            editor.addEventListener('paste', notifyChange);
            editor.addEventListener('cut', notifyChange);
        })();
        """
        self.exec_js(script)

    def setup_selection_change_notification(self):
        script = """
        (function() {
            const editor = document.getElementById('editor');
            if (!editor) {
                console.error('Editor element not found');
                return;
            }
            
            // Selection change notification
            function debounce(func, wait) {
                let timeout;
                return function(...args) {
                    clearTimeout(timeout);
                    timeout = setTimeout(() => func(...args), wait);
                };
            }
            
            const notifySelectionChange = debounce(function() {
                const sel = window.getSelection();
                if (sel.rangeCount > 0) {
                    const range = sel.getRangeAt(0);
                    let element = range.startContainer;
                    if (element.nodeType === Node.TEXT_NODE) {
                        element = element.parentElement;
                    }
                    const style = window.getComputedStyle(element);
                    const state = {
                        bold: document.queryCommandState('bold'),
                        italic: document.queryCommandState('italic'),
                        underline: document.queryCommandState('underline'),
                        // Add other states as needed
                    };
                    window.webkit.messageHandlers.selectionChanged.postMessage(JSON.stringify(state));
                }
            }, 100);

            document.addEventListener('selectionchange', notifySelectionChange);
            notifySelectionChange(); // Call once to initialize
        })();
        """
        self.exec_js(script)            
    def on_selection_changed(self, user_content, message):
        if message.is_string():
            state_str = message.to_string()
            state = json.loads(state_str)
            self.update_formatting_ui(state)
        else:
            print("Error: Expected a string message, got something else")

    def update_formatting_ui(self, state=None):
        if state:
            # Toggle buttons
            self.bold_btn.handler_block_by_func(self.on_bold_toggled)
            self.bold_btn.set_active(state.get('bold', False))
            self.bold_btn.handler_unblock_by_func(self.on_bold_toggled)

            self.italic_btn.handler_block_by_func(self.on_italic_toggled)
            self.italic_btn.set_active(state.get('italic', False))
            self.italic_btn.handler_unblock_by_func(self.on_italic_toggled)

            self.underline_btn.handler_block_by_func(self.on_underline_toggled)
            self.underline_btn.set_active(state.get('underline', False))
            self.underline_btn.handler_unblock_by_func(self.on_underline_toggled)

            self.strikethrough_btn.handler_block_by_func(self.on_strikethrough_toggled)
            self.strikethrough_btn.set_active(state.get('strikethrough', False))
            self.strikethrough_btn.handler_unblock_by_func(self.on_strikethrough_toggled)

            # List buttons
            self.bullet_btn.handler_block_by_func(self.on_bullet_list_toggled)
            self.bullet_btn.set_active(state.get('insertUnorderedList', False))
            self.bullet_btn.handler_unblock_by_func(self.on_bullet_list_toggled)

            self.number_btn.handler_block_by_func(self.on_number_list_toggled)
            self.number_btn.set_active(state.get('insertOrderedList', False))
            self.number_btn.handler_unblock_by_func(self.on_number_list_toggled)

            # Alignment buttons
            align_states = {
                'justifyLeft': (self.align_left_btn, self.on_align_left),
                'justifyCenter': (self.align_center_btn, self.on_align_center),
                'justifyRight': (self.align_right_btn, self.on_align_right),
                'justifyFull': (self.align_justify_btn, self.on_align_justify)
            }
            for align, (btn, handler) in align_states.items():
                btn.handler_block_by_func(handler)
                btn.set_active(state.get(align, False))
                btn.handler_unblock_by_func(handler)

            # Paragraph style
            format_block = state.get('formatBlock', 'p').lower()
            headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
            index = 0 if format_block not in headings else headings.index(format_block)
            self.heading_dropdown.handler_block(self.heading_dropdown_handler)
            self.heading_dropdown.set_selected(index)
            self.heading_dropdown.handler_unblock(self.heading_dropdown_handler)

            # Font family detection
            detected_font = state.get('fontName', self.current_font).lower()
            font_store = self.font_dropdown.get_model()
            selected_font_index = 0
            for i in range(font_store.get_n_items()):
                if font_store.get_string(i).lower() in detected_font:
                    selected_font_index = i
                    self.current_font = font_store.get_string(i)
                    break
            self.font_dropdown.handler_block(self.font_dropdown_handler)
            self.font_dropdown.set_selected(selected_font_index)
            self.font_dropdown.handler_unblock(self.font_dropdown_handler)

            # Font size detection
            font_size_str = state.get('fontSize', '12pt')
            if font_size_str.endswith('px'):
                font_size_pt = str(int(float(font_size_str[:-2]) / 1.333))  # Convert px to pt
            elif font_size_str.endswith('pt'):
                font_size_pt = font_size_str[:-2]
            else:
                font_size_pt = '12'  # Default

            size_store = self.size_dropdown.get_model()
            available_sizes = [size_store.get_string(i) for i in range(size_store.get_n_items())]
            selected_size_index = 6  # Default to 12pt
            if font_size_pt in available_sizes:
                selected_size_index = available_sizes.index(font_size_pt)
            self.current_font_size = available_sizes[selected_size_index]
            self.size_dropdown.handler_block(self.size_dropdown_handler)
            self.size_dropdown.set_selected(selected_size_index)
            self.size_dropdown.handler_unblock(self.size_dropdown_handler)
        else:
            # When called without state, update dropdowns with current values
            font_store = self.font_dropdown.get_model()
            selected_font_index = 0
            for i in range(font_store.get_n_items()):
                if font_store.get_string(i).lower() == self.current_font.lower():
                    selected_font_index = i
                    break
            self.font_dropdown.handler_block(self.font_dropdown_handler)
            self.font_dropdown.set_selected(selected_font_index)
            self.font_dropdown.handler_unblock(self.font_dropdown_handler)

            size_store = self.size_dropdown.get_model()
            selected_size_index = 3  # Default to 12
            for i in range(size_store.get_n_items()):
                if size_store.get_string(i) == self.current_font_size:
                    selected_size_index = i
                    break
            self.size_dropdown.handler_block(self.size_dropdown_handler)
            self.size_dropdown.set_selected(selected_size_index)
            self.size_dropdown.handler_unblock(self.size_dropdown_handler)

    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

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
            self.ignore_changes = True
            self.webview.load_html(self.initial_html, "file:///")
            self.current_file = None
            self.is_new = True
            self.is_modified = False
            self.document_number = EditorWindow.document_counter
            EditorWindow.document_counter += 1
            self.update_title()
            GLib.timeout_add(500, self.clear_ignore_changes)

    def on_open_clicked(self, btn):
        dialog = Gtk.FileDialog()
        filter = Gtk.FileFilter()
        filter.set_name("HTML Files (*.html, *.htm)")
        filter.add_pattern("*.html")
        filter.add_pattern("*.htm")
        dialog.set_default_filter(filter)
        dialog.open(self, None, self.on_open_file_dialog_response)

    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.current_file = file
                self.is_new = False
                self.update_title()
                file.load_contents_async(None, self.load_html_callback)
        except GLib.Error as e:
            print("Open error:", e.message)

    def load_html_callback(self, file, result):
        try:
            ok, content, _ = file.load_contents_finish(result)
            if ok:
                self.ignore_changes = True
                self.webview.load_html(content.decode(), file.get_uri())
                GLib.timeout_add(500, self.clear_ignore_changes)
                self.is_modified = False
                self.update_title()
        except GLib.Error as e:
            print("Load error:", e.message)

    def on_save_clicked(self, btn):
        if self.current_file and not self.is_new:
            self.save_as_html(self.current_file)
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
            dialog.set_initial_name(f"Document {self.document_number}.html")
        filter = Gtk.FileFilter()
        filter.set_name("HTML Files (*.html)")
        filter.add_pattern("*.html")
        dialog.set_default_filter(filter)
        dialog.save(self, None, self.save_callback)

    def save_callback(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.save_as_html(file)
                self.current_file = file
                self.is_new = False
                self.update_title()
        except GLib.Error as e:
            print("Save error:", e.message)

    def save_as_html(self, file):
        self.webview.evaluate_javascript(
            "document.documentElement.outerHTML",
            -1, None, None, None, self.save_html_callback, file
        )

    def save_html_callback(self, webview, result, file):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                html = js_value.to_string()
                file.replace_contents_bytes_async(
                    GLib.Bytes.new(html.encode()),
                    None, False, Gio.FileCreateFlags.REPLACE_DESTINATION,
                    None, self.final_save_callback
                )
        except GLib.Error as e:
            print("HTML save error:", e.message)

    def final_save_callback(self, file, result):
        try:
            file.replace_contents_finish(result)
            self.is_modified = False
            self.update_title()
        except GLib.Error as e:
            print("Final save error:", e.message)

    def on_cut_clicked(self, btn):
        self.exec_js("document.execCommand('cut')")

    def on_copy_clicked(self, btn):
        self.exec_js("document.execCommand('copy')")

    def on_paste_clicked(self, btn):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, self.on_text_received, None)

    def on_text_received(self, clipboard, result, user_data):
        try:
            text = clipboard.read_text_finish(result)
            if text:
                import json
                text_json = json.dumps(text)
                self.exec_js(f"document.execCommand('insertText', false, {text_json})")
        except GLib.Error as e:
            print("Paste error:", e.message)

    def on_undo_clicked(self, btn):
        self.exec_js("document.execCommand('undo')")

    def on_redo_clicked(self, btn):
        self.exec_js("document.execCommand('redo')")

    def on_dark_mode_toggled(self, btn):
        if btn.get_active():
            btn.set_icon_name("weather-clear-night")
            script = """
            document.body.style.backgroundColor = '#1e1e1e';
            document.body.style.color = '#e0e0e0';
            document.querySelectorAll('.textbox').forEach(tb => {
                tb.style.color = '#e0e0e0';
                tb.style.borderColor = '#555';
                tb.style.backgroundColor = 'transparent';
            });
            document.querySelectorAll('img.selected').forEach(img => {
                img.style.color = '#e0e0e0';
                img.style.borderColor = '#555';
                img.style.backgroundColor = 'transparent';
            });
            """
        else:
            btn.set_icon_name("display-brightness")
            script = """
            document.body.style.backgroundColor = '#ffffff';
            document.body.style.color = '#000000';
            document.querySelectorAll('.textbox').forEach(tb => {
                tb.style.color = '#000000';
                tb.style.borderColor = '#000';
                tb.style.backgroundColor = 'transparent';
            });
                document.querySelectorAll('img.selected').forEach(img => {
                img.style.color = '#000000';
                img.style.borderColor = '#000';
                img.style.backgroundColor = 'transparent';
            });

            """
        self.exec_js(script)

    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        shift = (state & Gdk.ModifierType.SHIFT_MASK) != 0

        if ctrl and not shift:
            if keyval == Gdk.KEY_b:
                self.on_bold_toggled(self.bold_btn)
                return True
            elif keyval == Gdk.KEY_i:
                self.on_italic_toggled(self.italic_btn)
                return True
            elif keyval == Gdk.KEY_u:
                self.on_underline_toggled(self.underline_btn)
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
                self.heading_dropdown.set_selected(0)  # Normal
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_1:
                self.heading_dropdown.set_selected(1)  # H1
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_2:
                self.heading_dropdown.set_selected(2)  # H2
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_3:
                self.heading_dropdown.set_selected(3)  # H3
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_4:
                self.heading_dropdown.set_selected(4)  # H4
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_5:
                self.heading_dropdown.set_selected(5)  # H5
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_6:
                self.heading_dropdown.set_selected(6)  # H6
                self.on_heading_changed(self.heading_dropdown)
                return True
        elif ctrl and shift:
            if keyval == Gdk.KEY_S:
                self.on_save_as_clicked(None)
                return True
            elif keyval == Gdk.KEY_Z:
                self.on_redo_clicked(None)
                return True
            elif keyval == Gdk.KEY_X:
                self.on_strikethrough_toggled(self.strikethrough_btn)
                return True
            elif keyval == Gdk.KEY_L:
                self.on_bullet_list_toggled(self.bullet_btn)
                return True
            elif keyval == Gdk.KEY_asterisk:
                self.on_bullet_list_toggled(self.bullet_btn)
                return True
            elif keyval == Gdk.KEY_ampersand:
                self.on_number_list_toggled(self.number_btn)
                return True
            elif keyval == Gdk.KEY_M:
                self.on_indent_less(None)
                return True
        elif not ctrl:
            if keyval == Gdk.KEY_F12 and not shift:
                self.on_number_list_toggled(self.number_btn)
                return True
            elif keyval == Gdk.KEY_F12 and shift:
                self.on_bullet_list_toggled(self.bullet_btn)
                return True
        return False

    def exec_js_with_result(self, js_code, callback):
        if hasattr(self.webview, 'run_javascript'):
            self.webview.run_javascript(js_code, None, callback, None)
        else:
            callback(self.webview, None, None)

    def on_bold_toggled(self, btn):
        if hasattr(self, '_processing_bold_toggle') and self._processing_bold_toggle:
            return
            
        self._processing_bold_toggle = True
        
        def get_bold_state(webview, result, user_data):
            try:
                if result is not None and hasattr(result, 'get_js_value'):
                    bold_state = webview.run_javascript_finish(result).get_js_value().to_boolean()
                else:
                    bold_state = not self.is_bold if hasattr(self, 'is_bold') else btn.get_active()
                    
                self.is_bold = bold_state
                self.bold_btn.handler_block_by_func(self.on_bold_toggled)
                self.bold_btn.set_active(self.is_bold)
                self.bold_btn.handler_unblock_by_func(self.on_bold_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in bold state callback: {e}")
                self.is_bold = not self.is_bold if hasattr(self, 'is_bold') else btn.get_active()
                self.bold_btn.handler_block_by_func(self.on_bold_toggled)
                self.bold_btn.set_active(self.is_bold)
                self.bold_btn.handler_unblock_by_func(self.on_bold_toggled)
            finally:
                self._processing_bold_toggle = False
        
        self.exec_js("document.execCommand('bold')")
        self.exec_js_with_result("document.queryCommandState('bold')", get_bold_state)
                
    def on_italic_toggled(self, btn):
        if hasattr(self, '_processing_italic_toggle') and self._processing_italic_toggle:
            return
            
        self._processing_italic_toggle = True
        
        def get_italic_state(webview, result, user_data):
            try:
                if result is not None and hasattr(result, 'get_js_value'):
                    italic_state = webview.run_javascript_finish(result).get_js_value().to_boolean()
                else:
                    italic_state = not self.is_italic if hasattr(self, 'is_italic') else btn.get_active()
                    
                self.is_italic = italic_state
                self.italic_btn.handler_block_by_func(self.on_italic_toggled)
                self.italic_btn.set_active(self.is_italic)
                self.italic_btn.handler_unblock_by_func(self.on_italic_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in italic state callback: {e}")
                self.is_italic = not self.is_italic if hasattr(self, 'is_italic') else btn.get_active()
                self.italic_btn.handler_block_by_func(self.on_italic_toggled)
                self.italic_btn.set_active(self.is_italic)
                self.italic_btn.handler_unblock_by_func(self.on_italic_toggled)
            finally:
                self._processing_italic_toggle = False
        
        self.exec_js("document.execCommand('italic')")
        self.exec_js_with_result("document.queryCommandState('italic')", get_italic_state)

    def on_underline_toggled(self, btn):
        if hasattr(self, '_processing_underline_toggle') and self._processing_underline_toggle:
            return
            
        self._processing_underline_toggle = True
        
        def get_underline_state(webview, result, user_data):
            try:
                if result is not None and hasattr(result, 'get_js_value'):
                    underline_state = webview.run_javascript_finish(result).get_js_value().to_boolean()
                else:
                    underline_state = not self.is_underline if hasattr(self, 'is_underline') else btn.get_active()
                    
                self.is_underline = underline_state
                self.underline_btn.handler_block_by_func(self.on_underline_toggled)
                self.underline_btn.set_active(self.is_underline)
                self.underline_btn.handler_unblock_by_func(self.on_underline_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in underline state callback: {e}")
                self.is_underline = not self.is_underline if hasattr(self, 'is_underline') else btn.get_active()
                self.underline_btn.handler_block_by_func(self.on_underline_toggled)
                self.underline_btn.set_active(self.is_underline)
                self.underline_btn.handler_unblock_by_func(self.on_underline_toggled)
            finally:
                self._processing_underline_toggle = False
        
        self.exec_js("document.execCommand('underline')")
        self.exec_js_with_result("document.queryCommandState('underline')", get_underline_state)

    def on_strikethrough_toggled(self, btn):
        if hasattr(self, '_processing_strikethrough_toggle') and self._processing_strikethrough_toggle:
            return
            
        self._processing_strikethrough_toggle = True
        
        def get_strikethrough_state(webview, result, user_data):
            try:
                if result is not None and hasattr(result, 'get_js_value'):
                    strikethrough_state = webview.run_javascript_finish(result).get_js_value().to_boolean()
                else:
                    strikethrough_state = not self.is_strikethrough if hasattr(self, 'is_strikethrough') else btn.get_active()
                    
                self.is_strikethrough = strikethrough_state
                self.strikethrough_btn.handler_block_by_func(self.on_strikethrough_toggled)
                self.strikethrough_btn.set_active(self.is_strikethrough)
                self.strikethrough_btn.handler_unblock_by_func(self.on_strikethrough_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in strikethrough state callback: {e}")
                self.is_strikethrough = not self.is_strikethrough if hasattr(self, 'is_strikethrough') else btn.get_active()
                self.strikethrough_btn.handler_block_by_func(self.on_strikethrough_toggled)
                self.strikethrough_btn.set_active(self.is_strikethrough)
                self.strikethrough_btn.handler_unblock_by_func(self.on_strikethrough_toggled)
            finally:
                self._processing_strikethrough_toggle = False
        
        self.exec_js("document.execCommand('strikethrough')")
        self.exec_js_with_result("document.queryCommandState('strikethrough')", get_strikethrough_state)
        
    def on_bullet_list_toggled(self, btn):
        if hasattr(self, '_processing_bullet_toggle') and self._processing_bullet_toggle:
            return
        
        self._processing_bullet_toggle = True
        
        def get_bullet_state(webview, result, user_data):
            try:
                if result is not None:
                    bullet_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    bullet_state = not self.is_bullet_list if hasattr(self, 'is_bullet_list') else btn.get_active()
                    
                self.is_bullet_list = bullet_state
                self.bullet_btn.handler_block_by_func(self.on_bullet_list_toggled)
                self.bullet_btn.set_active(self.is_bullet_list)
                self.bullet_btn.handler_unblock_by_func(self.on_bullet_list_toggled)
                
                if self.is_bullet_list:
                    self.is_number_list = False
                    self.number_btn.handler_block_by_func(self.on_number_list_toggled)
                    self.number_btn.set_active(False)
                    self.number_btn.handler_unblock_by_func(self.on_number_list_toggled)
                    
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in bullet list state callback: {e}")
                self.is_bullet_list = not self.is_bullet_list if hasattr(self, 'is_bullet_list') else btn.get_active()
                self.bullet_btn.handler_block_by_func(self.on_bullet_list_toggled)
                self.bullet_btn.set_active(self.is_bullet_list)
                self.bullet_btn.handler_unblock_by_func(self.on_bullet_list_toggled)
            finally:
                self._processing_bullet_toggle = False
        
        self.exec_js("document.execCommand('insertUnorderedList')")
        self.exec_js_with_result("document.queryCommandState('insertUnorderedList')", get_bullet_state)

    def on_number_list_toggled(self, btn):
        if hasattr(self, '_processing_number_toggle') and self._processing_number_toggle:
            return
        
        self._processing_number_toggle = True
        
        def get_number_state(webview, result, user_data):
            try:
                if result is not None:
                    number_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    number_state = not self.is_number_list if hasattr(self, 'is_number_list') else btn.get_active()
                    
                self.is_number_list = number_state
                self.number_btn.handler_block_by_func(self.on_number_list_toggled)
                self.number_btn.set_active(self.is_number_list)
                self.number_btn.handler_unblock_by_func(self.on_number_list_toggled)
                
                if self.is_number_list:
                    self.is_bullet_list = False
                    self.bullet_btn.handler_block_by_func(self.on_bullet_list_toggled)
                    self.bullet_btn.set_active(False)
                    self.bullet_btn.handler_unblock_by_func(self.on_bullet_list_toggled)
                    
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in number list state callback: {e}")
                self.is_number_list = not self.is_number_list if hasattr(self, 'is_number_list') else btn.get_active()
                self.number_btn.handler_block_by_func(self.on_number_list_toggled)
                self.number_btn.set_active(self.is_number_list)
                self.number_btn.handler_unblock_by_func(self.on_number_list_toggled)
            finally:
                self._processing_number_toggle = False
        
        self.exec_js("document.execCommand('insertOrderedList')")
        self.exec_js_with_result("document.queryCommandState('insertOrderedList')", get_number_state)

    def on_indent_more(self, btn):
        self.exec_js("document.execCommand('indent')")

    def on_indent_less(self, btn):
        self.exec_js("document.execCommand('outdent')")

    def on_heading_changed(self, dropdown, *args):
        headings = ["div", "h1", "h2", "h3", "h4", "h5", "h6"]
        selected = dropdown.get_selected()
        if 0 <= selected < len(headings):
            self.exec_js(f"document.execCommand('formatBlock', false, '{headings[selected]}')")

    def on_font_family_changed(self, dropdown, *args):
        if item := dropdown.get_selected_item():
            self.current_font = item.get_string()
            self.exec_js(f"document.execCommand('fontName', false, '{self.current_font}')")
            self.update_formatting_ui()

    def on_font_size_changed(self, dropdown, *args):
        if item := dropdown.get_selected_item():
            size_pt = item.get_string()
            self.current_font_size = size_pt
            script = f"""
            (function() {{
                const selection = window.getSelection();
                if (selection.rangeCount > 0) {{
                    const range = selection.getRangeAt(0);
                    // Map pt size to closest WebKit size (1-7) for execCommand
                    let webkitSize;
                    if ({size_pt} <= 9) webkitSize = '1';
                    else if ({size_pt} <= 11) webkitSize = '2';
                    else if ({size_pt} <= 14) webkitSize = '3';
                    else if ({size_pt} <= 18) webkitSize = '4';
                    else if ({size_pt} <= 24) webkitSize = '5';
                    else if ({size_pt} <= 36) webkitSize = '6';
                    else webkitSize = '7';
                    
                    if (range.collapsed) {{
                        // For cursor position (apply to future typing)
                        // Clear any existing formatting
                        document.execCommand('removeFormat', false, null);
                        // Apply base size
                        document.execCommand('fontSize', false, webkitSize);
                        
                        // Ensure cursor is in a font tag with exact size
                        let font = selection.focusNode.parentElement;
                        if (!font || font.tagName !== 'FONT' || 
                            font.getAttribute('size') !== webkitSize || 
                            font.style.fontSize !== '{size_pt}pt') {{
                            // Create new font tag if needed
                            font = document.createElement('font');
                            font.setAttribute('size', webkitSize);
                            font.style.fontSize = '{size_pt}pt';
                            range.insertNode(font);
                        }}
                        
                        // Insert a zero-width space to anchor the style
                        const zwsp = document.createTextNode('\u200B');
                        font.appendChild(zwsp);
                        
                        // Position cursor after zero-width space
                        range.setStartAfter(zwsp);
                        range.setEndAfter(zwsp);
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }} else {{
                        // For selected text
                        document.execCommand('fontSize', false, webkitSize);
                        const fonts = document.querySelectorAll('font[size="' + webkitSize + '"]');
                        fonts.forEach(font => {{
                            if (!font.style.fontSize) {{  // Only if not already set
                                font.style.fontSize = '{size_pt}pt';
                            }}
                        }});
                    }}
                }}
            }})();
            """
            self.exec_js(script)
            self.update_formatting_ui()
    def on_align_left(self, btn):
        if hasattr(self, '_processing_align_left') and self._processing_align_left:
            return
        
        self._processing_align_left = True
        
        def get_align_state(webview, result, user_data):
            try:
                if result is not None:
                    align_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    align_state = not self.is_align_left if hasattr(self, 'is_align_left') else btn.get_active()
                    
                self.is_align_left = align_state
                self.align_left_btn.handler_block_by_func(self.on_align_left)
                self.align_left_btn.set_active(self.is_align_left)
                self.align_left_btn.handler_unblock_by_func(self.on_align_left)
                
                if self.is_align_left:
                    self.is_align_center = False
                    self.align_center_btn.handler_block_by_func(self.on_align_center)
                    self.align_center_btn.set_active(False)
                    self.align_center_btn.handler_unblock_by_func(self.on_align_center)
                    
                    self.is_align_right = False
                    self.align_right_btn.handler_block_by_func(self.on_align_right)
                    self.align_right_btn.set_active(False)
                    self.align_right_btn.handler_unblock_by_func(self.on_align_right)
                    
                    self.is_align_justify = False
                    self.align_justify_btn.handler_block_by_func(self.on_align_justify)
                    self.align_justify_btn.set_active(False)
                    self.align_justify_btn.handler_unblock_by_func(self.on_align_justify)
                    
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in align left state callback: {e}")
                self.is_align_left = not self.is_align_left if hasattr(self, 'is_align_left') else btn.get_active()
                self.align_left_btn.handler_block_by_func(self.on_align_left)
                self.align_left_btn.set_active(self.is_align_left)
                self.align_left_btn.handler_unblock_by_func(self.on_align_left)
            finally:
                self._processing_align_left = False
        
        self.exec_js("document.execCommand('justifyLeft')")
        self.exec_js_with_result("document.queryCommandState('justifyLeft')", get_align_state)

    def on_align_center(self, btn):
        if hasattr(self, '_processing_align_center') and self._processing_align_center:
            return
        
        self._processing_align_center = True
        
        def get_align_state(webview, result, user_data):
            try:
                if result is not None:
                    align_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    align_state = not self.is_align_center if hasattr(self, 'is_align_center') else btn.get_active()
                    
                self.is_align_center = align_state
                self.align_center_btn.handler_block_by_func(self.on_align_center)
                self.align_center_btn.set_active(self.is_align_center)
                self.align_center_btn.handler_unblock_by_func(self.on_align_center)
                
                if self.is_align_center:
                    self.is_align_left = False
                    self.align_left_btn.handler_block_by_func(self.on_align_left)
                    self.align_left_btn.set_active(False)
                    self.align_left_btn.handler_unblock_by_func(self.on_align_left)
                    
                    self.is_align_right = False
                    self.align_right_btn.handler_block_by_func(self.on_align_right)
                    self.align_right_btn.set_active(False)
                    self.align_right_btn.handler_unblock_by_func(self.on_align_right)
                    
                    self.is_align_justify = False
                    self.align_justify_btn.handler_block_by_func(self.on_align_justify)
                    self.align_justify_btn.set_active(False)
                    self.align_justify_btn.handler_unblock_by_func(self.on_align_justify)
                    
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in align center state callback: {e}")
                self.is_align_center = not self.is_align_center if hasattr(self, 'is_align_center') else btn.get_active()
                self.align_center_btn.handler_block_by_func(self.on_align_center)
                self.align_center_btn.set_active(self.is_align_center)
                self.align_center_btn.handler_unblock_by_func(self.on_align_center)
            finally:
                self._processing_align_center = False
        
        self.exec_js("document.execCommand('justifyCenter')")
        self.exec_js_with_result("document.queryCommandState('justifyCenter')", get_align_state)

    def on_align_right(self, btn):
        if hasattr(self, '_processing_align_right') and self._processing_align_right:
            return
        
        self._processing_align_right = True
        
        def get_align_state(webview, result, user_data):
            try:
                if result is not None:
                    align_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    align_state = not self.is_align_right if hasattr(self, 'is_align_right') else btn.get_active()
                    
                self.is_align_right = align_state
                self.align_right_btn.handler_block_by_func(self.on_align_right)
                self.align_right_btn.set_active(self.is_align_right)
                self.align_right_btn.handler_unblock_by_func(self.on_align_right)
                
                if self.is_align_right:
                    self.is_align_left = False
                    self.align_left_btn.handler_block_by_func(self.on_align_left)
                    self.align_left_btn.set_active(False)
                    self.align_left_btn.handler_unblock_by_func(self.on_align_left)
                    
                    self.is_align_center = False
                    self.align_center_btn.handler_block_by_func(self.on_align_center)
                    self.align_center_btn.set_active(False)
                    self.align_center_btn.handler_unblock_by_func(self.on_align_center)
                    
                    self.is_align_justify = False
                    self.align_justify_btn.handler_block_by_func(self.on_align_justify)
                    self.align_justify_btn.set_active(False)
                    self.align_justify_btn.handler_unblock_by_func(self.on_align_justify)
                    
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in align right state callback: {e}")
                self.is_align_right = not self.is_align_right if hasattr(self, 'is_align_right') else btn.get_active()
                self.align_right_btn.handler_block_by_func(self.on_align_right)
                self.align_right_btn.set_active(self.is_align_right)
                self.align_right_btn.handler_unblock_by_func(self.on_align_right)
            finally:
                self._processing_align_right = False
        
        self.exec_js("document.execCommand('justifyRight')")
        self.exec_js_with_result("document.queryCommandState('justifyRight')", get_align_state)

    def on_align_justify(self, btn):
        if hasattr(self, '_processing_align_justify') and self._processing_align_justify:
            return
        
        self._processing_align_justify = True
        
        def get_align_state(webview, result, user_data):
            try:
                if result is not None:
                    align_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    align_state = not self.is_align_justify if hasattr(self, 'is_align_justify') else btn.get_active()
                    
                self.is_align_justify = align_state
                self.align_justify_btn.handler_block_by_func(self.on_align_justify)
                self.align_justify_btn.set_active(self.is_align_justify)
                self.align_justify_btn.handler_unblock_by_func(self.on_align_justify)
                
                if self.is_align_justify:
                    self.is_align_left = False
                    self.align_left_btn.handler_block_by_func(self.on_align_left)
                    self.align_left_btn.set_active(False)
                    self.align_left_btn.handler_unblock_by_func(self.on_align_left)
                    
                    self.is_align_center = False
                    self.align_center_btn.handler_block_by_func(self.on_align_center)
                    self.align_center_btn.set_active(False)
                    self.align_center_btn.handler_unblock_by_func(self.on_align_center)
                    
                    self.is_align_right = False
                    self.align_right_btn.handler_block_by_func(self.on_align_right)
                    self.align_right_btn.set_active(False)
                    self.align_right_btn.handler_unblock_by_func(self.on_align_right)
                    
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in align justify state callback: {e}")
                self.is_align_justify = not self.is_align_justify if hasattr(self, 'is_align_justify') else btn.get_active()
                self.align_justify_btn.handler_block_by_func(self.on_align_justify)
                self.align_justify_btn.set_active(self.is_align_justify)
                self.align_justify_btn.handler_unblock_by_func(self.on_align_justify)
            finally:
                self._processing_align_justify = False
        
        self.exec_js("document.execCommand('justifyFull')")
        self.exec_js_with_result("document.queryCommandState('justifyFull')", get_align_state)

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

    def clear_ignore_changes(self):
        self.ignore_changes = False
        return False


    def on_insert_textbox_clicked(self, btn):
        default_text = "Enter text here"
        script = f"""
        (function() {{
            const editor = document.getElementById('editor');
            const textbox = document.createElement('div');
            textbox.className = 'textbox';
            textbox.contentEditable = false;
            textbox.draggable = true;
            textbox.style.display = 'inline-block';
            textbox.style.padding = '5px';
            textbox.style.border = '1px dashed';
            textbox.style.minWidth = '100px';
            textbox.innerHTML = '{default_text}';
            
            const range = window.getSelection().getRangeAt(0);
            range.insertNode(textbox);
            
            // Trigger selection
            const event = new Event('click', {{ bubbles: true }});
            textbox.dispatchEvent(event);
        }})();
        """
        self.exec_js(script)
        self.webview.grab_focus()
######################################################

# Now, add the table insertion method to the EditorWindow class:

    def on_insert_table_clicked(self, btn):
        # Create a dialog to get table dimensions
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Insert Table",
            body="Select the number of rows and columns for your table",
            modal=True
        )
        
        # Create content area with spin buttons for rows and columns
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)
        
        # Rows
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row_label = Gtk.Label(label="Rows:")
        row_label.set_xalign(0)
        row_box.append(row_label)
        
        row_adjustment = Gtk.Adjustment(value=3, lower=1, upper=50, step_increment=1)
        row_spin = Gtk.SpinButton(adjustment=row_adjustment, climb_rate=1, digits=0)
        row_box.append(row_spin)
        content_box.append(row_box)
        
        # Columns
        col_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        col_label = Gtk.Label(label="Columns:")
        col_label.set_xalign(0)
        col_box.append(col_label)
        
        col_adjustment = Gtk.Adjustment(value=3, lower=1, upper=20, step_increment=1)
        col_spin = Gtk.SpinButton(adjustment=col_adjustment, climb_rate=1, digits=0)
        col_box.append(col_spin)
        content_box.append(col_box)
        
        # Add header row checkbox
        header_check = Gtk.CheckButton(label="Add header row")
        header_check.set_active(True)
        content_box.append(header_check)
        
        # Border width
        border_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        border_label = Gtk.Label(label="Border width:")
        border_label.set_xalign(0)
        border_box.append(border_label)
        
        border_adjustment = Gtk.Adjustment(value=1, lower=0, upper=10, step_increment=1)
        border_spin = Gtk.SpinButton(adjustment=border_adjustment, climb_rate=1, digits=0)
        border_box.append(border_spin)
        content_box.append(border_box)
        
        dialog.set_extra_child(content_box)
        
        # Add buttons
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("insert", "Insert")
        dialog.set_response_appearance("insert", Adw.ResponseAppearance.SUGGESTED)
        
        dialog.connect("response", self.on_table_dialog_response, 
                      {"rows": row_spin, "cols": col_spin, 
                       "header": header_check, "border": border_spin})
        dialog.present()

    def on_table_dialog_response(self, dialog, response, data):
        if response == "insert":
            rows = data["rows"].get_value_as_int()
            cols = data["cols"].get_value_as_int()
            has_header = data["header"].get_active()
            border_width = data["border"].get_value_as_int()
            self.insert_table(rows, cols, has_header, border_width)
        dialog.destroy()

    def insert_table(self, rows, cols, has_header=True, border_width=1):
        # Create table HTML
        table_html = f'<table border="{border_width}" style="border-collapse: collapse; width: 100%;">'
        
        for row in range(rows):
            table_html += '<tr>'
            for col in range(cols):
                cell_tag = 'th' if row == 0 and has_header else 'td'
                table_html += f'<{cell_tag} style="border: {border_width}px solid black; padding: 8px;">&nbsp;</{cell_tag}>'
            table_html += '</tr>'
        
        table_html += '</table><p></p>'  # Add paragraph after table for easier editing
        
        # Insert table into editor
        self.exec_js(f'document.execCommand("insertHTML", false, {json.dumps(table_html)});')
        
        # Now add JavaScript to handle table functionality
        self.setup_table_handlers()

    def setup_table_handlers(self):
        script = """
        (function() {
            const editor = document.getElementById('editor');
            if (!editor) return;
            
            // Context menu for tables
            let tableContextMenu = null;
            let currentCell = null;
            let currentTable = null;
            let resizingColumn = false;
            let resizingRow = false;
            let lastX, lastY;
            let columnResizeHandles = [];
            let rowResizeHandles = [];
            
            // Clean up any existing handlers to prevent duplicates
            document.querySelectorAll('.table-resize-handle').forEach(handle => handle.remove());
            
            // Initialize existing tables
            initializeExistingTables();
            
            function initializeExistingTables() {
                editor.querySelectorAll('table').forEach(table => {
                    table.addEventListener('click', handleTableClick);
                    table.contentEditable = true;
                    
                    // Make all cells focusable
                    table.querySelectorAll('td, th').forEach(cell => {
                        cell.tabIndex = -1;
                        setupCellEvents(cell);
                    });
                });
            }
            
            // Set up events for table cells
            function setupCellEvents(cell) {
                // Handle key navigation
                cell.addEventListener('keydown', handleCellKeyDown);
                
                // Context menu on right-click
                cell.addEventListener('contextmenu', handleCellContextMenu);
                
                // Handle cell selection
                cell.addEventListener('click', function(e) {
                    if (e.target === cell) {
                        selectCell(cell);
                    }
                });
            }
            
            // Handle table clicks
            function handleTableClick(e) {
                if (e.target.tagName === 'TD' || e.target.tagName === 'TH') {
                    selectCell(e.target);
                    e.stopPropagation();
                }
            }
            
            // Select a cell
            function selectCell(cell) {
                // Remove any previous selection styling
                editor.querySelectorAll('td.selected, th.selected').forEach(selectedCell => {
                    selectedCell.classList.remove('selected');
                });
                
                // Add selection style
                cell.classList.add('selected');
                currentCell = cell;
                currentTable = cell.closest('table');
                
                // Create resize handles if they don't exist
                showTableResizeHandles(currentTable);
            }
            
            // Handle keyboard navigation in cells
            function handleCellKeyDown(e) {
                if (!currentCell) return;
                
                const table = currentCell.closest('table');
                if (!table) return;
                
                const rows = Array.from(table.rows);
                const currentRow = currentCell.parentElement;
                const rowIndex = rows.indexOf(currentRow);
                const colIndex = Array.from(currentRow.cells).indexOf(currentCell);
                
                let newCell;
                
                // Navigation keys
                if (e.key === 'Tab') {
                    e.preventDefault();
                    
                    if (e.shiftKey) {
                        // Move to previous cell
                        if (colIndex > 0) {
                            newCell = currentRow.cells[colIndex - 1];
                        } else if (rowIndex > 0) {
                            // Move to last cell of previous row
                            const prevRow = rows[rowIndex - 1];
                            newCell = prevRow.cells[prevRow.cells.length - 1];
                        }
                    } else {
                        // Move to next cell
                        if (colIndex < currentRow.cells.length - 1) {
                            newCell = currentRow.cells[colIndex + 1];
                        } else if (rowIndex < rows.length - 1) {
                            // Move to first cell of next row
                            newCell = rows[rowIndex + 1].cells[0];
                        } else {
                            // Add a new row if at last cell
                            const newRow = table.insertRow();
                            for (let i = 0; i < currentRow.cells.length; i++) {
                                const newCell = newRow.insertCell();
                                newCell.innerHTML = '&nbsp;';
                                setupCellEvents(newCell);
                            }
                            newCell = newRow.cells[0];
                        }
                    }
                    
                    if (newCell) {
                        selectCell(newCell);
                        newCell.focus();
                    }
                    return;
                }
                
                // Arrow key navigation
                if (e.key.startsWith('Arrow') && !e.shiftKey && !e.ctrlKey && !e.altKey) {
                    e.preventDefault();
                    
                    switch (e.key) {
                        case 'ArrowUp':
                            if (rowIndex > 0) {
                                newCell = rows[rowIndex - 1].cells[Math.min(colIndex, rows[rowIndex - 1].cells.length - 1)];
                            }
                            break;
                        case 'ArrowDown':
                            if (rowIndex < rows.length - 1) {
                                newCell = rows[rowIndex + 1].cells[Math.min(colIndex, rows[rowIndex + 1].cells.length - 1)];
                            }
                            break;
                        case 'ArrowLeft':
                            if (colIndex > 0) {
                                newCell = currentRow.cells[colIndex - 1];
                            } else if (rowIndex > 0) {
                                // Go to end of previous row
                                const prevRow = rows[rowIndex - 1];
                                newCell = prevRow.cells[prevRow.cells.length - 1];
                            }
                            break;
                        case 'ArrowRight':
                            if (colIndex < currentRow.cells.length - 1) {
                                newCell = currentRow.cells[colIndex + 1];
                            } else if (rowIndex < rows.length - 1) {
                                // Go to start of next row
                                newCell = rows[rowIndex + 1].cells[0];
                            }
                            break;
                    }
                    
                    if (newCell) {
                        selectCell(newCell);
                        newCell.focus();
                    }
                    return;
                }
                
                // Enter to go to next row or add a new row
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    
                    if (rowIndex < rows.length - 1) {
                        newCell = rows[rowIndex + 1].cells[colIndex];
                    } else {
                        // Add a new row
                        const newRow = table.insertRow();
                        for (let i = 0; i < currentRow.cells.length; i++) {
                            const newCell = newRow.insertCell();
                            newCell.innerHTML = '&nbsp;';
                            setupCellEvents(newCell);
                        }
                        newCell = newRow.cells[colIndex];
                    }
                    
                    if (newCell) {
                        selectCell(newCell);
                        newCell.focus();
                    }
                    return;
                }
                
                // Allow Shift+Enter for line breaks within cells
                if (e.key === 'Enter' && e.shiftKey) {
                    // Don't prevent default to allow line break
                    return;
                }
                
                // Prevent Enter from creating paragraphs outside the table
                if (e.key === 'Enter') {
                    e.preventDefault();
                }
            }
            
            // Handle right-click context menu
            function handleCellContextMenu(e) {
                e.preventDefault();
                
                // Select the cell that was right-clicked
                selectCell(e.target);
                
                // Create context menu
                removeTableContextMenu();
                createTableContextMenu(e.clientX, e.clientY);
            }
            
            // Create table context menu
            function createTableContextMenu(x, y) {
                if (!currentCell || !currentTable) return;
                
                tableContextMenu = document.createElement('div');
                tableContextMenu.className = 'context-menu';
                tableContextMenu.style.left = x + 'px';
                tableContextMenu.style.top = y + 'px';
                
                const menuItems = [
                    { label: 'Insert Row Above', action: 'insert-row-above' },
                    { label: 'Insert Row Below', action: 'insert-row-below' },
                    { label: 'Insert Column Left', action: 'insert-col-left' },
                    { label: 'Insert Column Right', action: 'insert-col-right' },
                    { type: 'separator' },
                    { label: 'Delete Row', action: 'delete-row' },
                    { label: 'Delete Column', action: 'delete-col' },
                    { type: 'separator' },
                    { label: 'Merge Cells', action: 'merge-cells' },
                    { label: 'Split Cell', action: 'split-cell' },
                    { type: 'separator' },
                    { label: 'Table Properties', action: 'table-properties' },
                    { label: 'Cell Properties', action: 'cell-properties' },
                    { type: 'separator' },
                    { label: 'Delete Table', action: 'delete-table' }
                ];
                
                menuItems.forEach(item => {
                    if (item.type === 'separator') {
                        const separator = document.createElement('div');
                        separator.className = 'context-menu-separator';
                        tableContextMenu.appendChild(separator);
                    } else {
                        const menuItem = document.createElement('div');
                        menuItem.className = 'context-menu-item';
                        menuItem.textContent = item.label;
                        
                        menuItem.addEventListener('click', () => {
                            handleTableContextMenuAction(item.action);
                            removeTableContextMenu();
                        });
                        
                        tableContextMenu.appendChild(menuItem);
                    }
                });
                
                document.body.appendChild(tableContextMenu);
                
                setTimeout(() => {
                    document.addEventListener('click', closeTableContextMenuOnClickOutside);
                }, 0);
            }
            
            // Remove context menu
            function removeTableContextMenu() {
                if (tableContextMenu) {
                    document.removeEventListener('click', closeTableContextMenuOnClickOutside);
                    tableContextMenu.remove();
                    tableContextMenu = null;
                }
            }
            
            // Close context menu when clicking outside
            function closeTableContextMenuOnClickOutside(e) {
                if (tableContextMenu && !tableContextMenu.contains(e.target)) {
                    removeTableContextMenu();
                }
            }
            
            // Handle context menu actions
            function handleTableContextMenuAction(action) {
                if (!currentCell || !currentTable) return;
                
                const table = currentTable;
                const cell = currentCell;
                const row = cell.parentElement;
                const rows = Array.from(table.rows);
                const rowIndex = rows.indexOf(row);
                const colIndex = Array.from(row.cells).indexOf(cell);
                
                switch (action) {
                    case 'insert-row-above':
                        insertRow(table, rowIndex);
                        break;
                    case 'insert-row-below':
                        insertRow(table, rowIndex + 1);
                        break;
                    case 'insert-col-left':
                        insertColumn(table, colIndex);
                        break;
                    case 'insert-col-right':
                        insertColumn(table, colIndex + 1);
                        break;
                    case 'delete-row':
                        deleteRow(table, rowIndex);
                        break;
                    case 'delete-col':
                        deleteColumn(table, colIndex);
                        break;
                    case 'merge-cells':
                        openMergeCellsDialog();
                        break;
                    case 'split-cell':
                        openSplitCellDialog();
                        break;
                    case 'table-properties':
                        openTablePropertiesDialog();
                        break;
                    case 'cell-properties':
                        openCellPropertiesDialog();
                        break;
                    case 'delete-table':
                        deleteTable(table);
                        break;
                }
                
                // Update table resize handles
                if (currentTable) {
                    showTableResizeHandles(currentTable);
                }
            }
            
            // Insert row
            function insertRow(table, rowIndex) {
                const newRow = table.insertRow(rowIndex);
                const refRow = table.rows[rowIndex === table.rows.length - 1 ? rowIndex - 1 : rowIndex];
                
                for (let i = 0; i < refRow.cells.length; i++) {
                    const refCell = refRow.cells[i];
                    const newCell = newRow.insertCell();
                    
                    // Copy the cell type (th or td)
                    if (refCell.tagName === 'TH') {
                        const th = document.createElement('th');
                        th.innerHTML = '&nbsp;';
                        newRow.replaceChild(th, newCell);
                        setupCellEvents(th);
                    } else {
                        newCell.innerHTML = '&nbsp;';
                        setupCellEvents(newCell);
                    }
                }
                
                // Select first cell in the new row
                if (newRow.cells.length > 0) {
                    selectCell(newRow.cells[0]);
                }
            }
            
            // Insert column
            function insertColumn(table, colIndex) {
                for (let i = 0; i < table.rows.length; i++) {
                    const row = table.rows[i];
                    const refCell = row.cells[colIndex === row.cells.length ? colIndex - 1 : colIndex];
                    
                    // Create new cell based on reference cell type
                    if (refCell.tagName === 'TH') {
                        const th = document.createElement('th');
                        th.innerHTML = '&nbsp;';
                        row.insertBefore(th, refCell.nextSibling);
                        setupCellEvents(th);
                    } else {
                        const td = row.insertCell(colIndex);
                        td.innerHTML = '&nbsp;';
                        setupCellEvents(td);
                    }
                }
                
                // Select first cell in the new column
                if (table.rows.length > 0 && colIndex < table.rows[0].cells.length) {
                    selectCell(table.rows[0].cells[colIndex]);
                }
            }
            
            // Delete row
            function deleteRow(table, rowIndex) {
                if (table.rows.length <= 1) {
                    // Don't delete the last row, delete the table instead
                    deleteTable(table);
                    return;
                }
                
                table.deleteRow(rowIndex);
                
                // Select a cell in the table
                if (table.rows.length > 0) {
                    const newRowIndex = Math.min(rowIndex, table.rows.length - 1);
                    if (table.rows[newRowIndex].cells.length > 0) {
                        selectCell(table.rows[newRowIndex].cells[0]);
                    }
                }
            }
            
            // Delete column
            function deleteColumn(table, colIndex) {
                // Check if this is the last column
                let isLastColumn = true;
                for (let i = 0; i < table.rows.length; i++) {
                    if (table.rows[i].cells.length > 1) {
                        isLastColumn = false;
                        break;
                    }
                }
                
                if (isLastColumn) {
                    // Don't delete the last column, delete the table instead
                    deleteTable(table);
                    return;
                }
                
                for (let i = 0; i < table.rows.length; i++) {
                    const row = table.rows[i];
                    if (colIndex < row.cells.length) {
                        row.deleteCell(colIndex);
                    }
                }
                
                // Select a cell in the table
                if (table.rows.length > 0) {
                    const row = table.rows[0];
                    if (row.cells.length > 0) {
                        const newColIndex = Math.min(colIndex, row.cells.length - 1);
                        selectCell(row.cells[newColIndex]);
                    }
                }
            }
            
            // Delete table
            function deleteTable(table) {
                table.remove();
                currentTable = null;
                currentCell = null;
                removeTableResizeHandles();
            }
            
            // Open merge cells dialog
            function openMergeCellsDialog() {
                // This would display a UI dialog for merging cells
                // For now, we'll implement a simple version
                alert('Merge cells functionality coming soon');
            }
            
            // Open split cell dialog
            function openSplitCellDialog() {
                // This would display a UI dialog for splitting cells
                // For now, we'll implement a simple version
                alert('Split cell functionality coming soon');
            }
            
            // Open table properties dialog
            function openTablePropertiesDialog() {
                // This would display a UI dialog for table properties
                // For now, we'll implement a simple version
                alert('Table properties dialog coming soon');
            }
            
            // Open cell properties dialog
            function openCellPropertiesDialog() {
                // This would display a UI dialog for cell properties
                // For now, we'll implement a simple version
                alert('Cell properties dialog coming soon');
            }
            
            // Show table resize handles
            function showTableResizeHandles(table) {
                removeTableResizeHandles();
                
                if (!table) return;
                
                // Position for the table
                const tableRect = table.getBoundingClientRect();
                const editorRect = editor.getBoundingClientRect();
                
                // Create column resize handles
                if (table.rows.length > 0) {
                    const firstRow = table.rows[0];
                    let totalWidth = 0;
                    
                    for (let i = 0; i < firstRow.cells.length - 1; i++) {
                        const cell = firstRow.cells[i];
                        const cellRect = cell.getBoundingClientRect();
                        totalWidth += cellRect.width;
                        
                        // Create column resize handle
                        const handle = document.createElement('div');
                        handle.className = 'table-resize-handle column-resize-handle';
                        handle.style.position = 'absolute';
                        handle.style.top = (tableRect.top - editorRect.top + editor.scrollTop) + 'px';
                        handle.style.left = (tableRect.left - editorRect.left + totalWidth + editor.scrollLeft) + 'px';
                        handle.style.width = '5px';
                        handle.style.height = tableRect.height + 'px';
                        handle.style.cursor = 'col-resize';
                        handle.style.backgroundColor = 'transparent';
                        handle.style.zIndex = '999';
                        
                        handle.dataset.index = i;
                        handle.addEventListener('mousedown', startColumnResize);
                        
                        editor.appendChild(handle);
                        columnResizeHandles.push(handle);
                    }
                }
                
                // Create row resize handles
                for (let i = 0; i < table.rows.length - 1; i++) {
                    const row = table.rows[i];
                    const rowRect = row.getBoundingClientRect();
                    
                    // Create row resize handle
                    const handle = document.createElement('div');
                    handle.className = 'table-resize-handle row-resize-handle';
                    handle.style.position = 'absolute';
                    handle.style.top = (tableRect.top - editorRect.top + rowRect.height + (i * rowRect.height) + editor.scrollTop) + 'px';
                    handle.style.left = (tableRect.left - editorRect.left + editor.scrollLeft) + 'px';
                    handle.style.width = tableRect.width + 'px';
                    handle.style.height = '5px';
                    handle.style.cursor = 'row-resize';
                    handle.style.backgroundColor = 'transparent';
                    handle.style.zIndex = '999';
                    
                    handle.dataset.index = i;
                    handle.addEventListener('mousedown', startRowResize);
                    
                    editor.appendChild(handle);
                    rowResizeHandles.push(handle);
                }
            }
            
            // Start column resize
            function startColumnResize(e) {
                if (!currentTable) return;
                
                resizingColumn = true;
                const columnIndex = parseInt(e.target.dataset.index);
                lastX = e.clientX;
                
                // Store original widths
                const cells = [];
                for (let i = 0; i < currentTable.rows.length; i++) {
                    const row = currentTable.rows[i];
                    if (columnIndex < row.cells.length) {
                        const cell = row.cells[columnIndex];
                        cells.push({
                            element: cell,
                            width: cell.offsetWidth
                        });
                    }
                }
                
                function handleColumnResize(e) {
                    if (!resizingColumn) return;
                    
                    const deltaX = e.clientX - lastX;
                    
                    // Apply new widths
                    cells.forEach(cell => {
                        const newWidth = Math.max(20, cell.width + deltaX);
                        cell.element.style.width = newWidth + 'px';
                    });
                    
                    // Update position of column resize handles
                    showTableResizeHandles(currentTable);
                }
                
                function stopColumnResize() {
                    resizingColumn = false;
                    document.removeEventListener('mousemove', handleColumnResize);
                    document.removeEventListener('mouseup', stopColumnResize);
                }
                
                document.addEventListener('mousemove', handleColumnResize);
                document.addEventListener('mouseup', stopColumnResize);
                
                e.preventDefault();
            }
            
            // Start row resize
            function startRowResize(e) {
                if (!currentTable) return;
                
                resizingRow = true;
                const rowIndex = parseInt(e.target.dataset.index);
                lastY = e.clientY;
                
                // Store original height
                const row = currentTable.rows[rowIndex];
                const originalHeight = row.offsetHeight;
                
                function handleRowResize(e) {
                    if (!resizingRow) return;
                    
                    const deltaY = e.clientY - lastY;
                    const newHeight = Math.max(20, originalHeight + deltaY);
                    
                    // Apply new height
                    row.style.height = newHeight + 'px';
                    
                    // Update position of row resize handles
                    showTableResizeHandles(currentTable);
                }
                
                function stopRowResize() {
                    resizingRow = false;
                    document.removeEventListener('mousemove', handleRowResize);
                    document.removeEventListener('mouseup', stopRowResize);
                }
                
                document.addEventListener('mousemove', handleRowResize);
                document.addEventListener('mouseup', stopRowResize);
                
                e.preventDefault();
            }
            
            // Remove table resize handles
            function removeTableResizeHandles() {
                columnResizeHandles.forEach(handle => handle.remove());
                rowResizeHandles.forEach(handle => handle.remove());
                columnResizeHandles = [];
                rowResizeHandles = [];
            }
            
            // Add additional styles for tables
            const tableStyles = document.createElement('style');
            tableStyles.textContent = `
                table {
                    border-collapse: collapse;
                    table-layout: fixed;
                    width: 100%;
                    margin: 10px 0;
                }
                
                th, td {
                    border: 1px solid black;
                    padding: 8px;
                    position: relative;
                    min-width: 30px;
                    word-wrap: break-word;
                }
                
                th.selected, td.selected {
                    background-color: rgba(66, 133, 244, 0.2);
                    outline: 2px solid #4285f4;
                }
                
                .column-resize-handle:hover {
                    background-color: #4285f4 !important;
                }
                
                .row-resize-handle:hover {
                    background-color: #4285f4 !important;
                }
                
                @media (prefers-color-scheme: dark) {
                    th, td {
                        border-color: #555;
                    }
                    
                    th.selected, td.selected {
                        background-color: rgba(94, 151, 246, 0.25);
                        outline-color: #5e97f6;
                    }
                }
            `;
            document.head.appendChild(tableStyles);
            
            // Watch for mutations to handle dynamically added tables
            const observer = new MutationObserver(mutations => {
                let tableAdded = false;
                
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.tagName === 'TABLE') {
                            node.addEventListener('click', handleTableClick);
                            node.querySelectorAll('td, th').forEach(cell => {
                                cell.tabIndex = -1;
                                setupCellEvents(cell);
                            });
                            tableAdded = true;
                        } else if (node.nodeType === 1) {
                            const tables = node.querySelectorAll('table');
                            if (tables.length > 0) {
                                tables.forEach(table => {
                                    table.addEventListener('click', handleTableClick);
                                    table.querySelectorAll('td, th').forEach(cell => {
                                        cell.tabIndex = -1;
                                        setupCellEvents(cell);
                                    });
                                });
                                tableAdded = true;
                            }
                        }
                    });
                });
                
                if (tableAdded && currentTable) {
                    showTableResizeHandles(currentTable);
                }
            });
            
            observer.observe(editor, { childList: true, subtree: true });
        })();
        """
        self.exec_js(script)
        self.webview.grab_focus()
if __name__ == "__main__":
    app = Writer()
    app.run()
