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
        }
        @media (prefers-color-scheme: light) {
            body { background-color: #ffffff; color: #000000; }
            editor { background-color: #ffffff; color: #000000; }
            img.selected { outline: 2px solid #4285f4; box-shadow: 0 0 10px rgba(66, 133, 244, 0.5); }
            .context-menu { background-color: white; border-color: #ccc; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2); }
            .context-menu-item:hover { background-color: #f0f0f0; }
            .context-menu-separator { background-color: #e0e0e0; }
            .context-menu-submenu-content { background-color: white; border-color: #ccc; }
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
            self.setup_image_handling()
            
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


    def setup_image_handling(self):
        script = """
        (function() {
            const editor = document.getElementById('editor');
            if (!editor) {
                console.error('Editor element not found');
                return;
            }

            // Image handling variables
            let selectedImage = null;
            let resizeHandles = [];
            let isDragging = false;
            let isResizing = false;
            let lastX, lastY;
            let resizeStartWidth, resizeStartHeight;
            let currentResizeHandle = null;
            let contextMenu = null;
            
            // Current text wrap mode for the selected image
            let currentWrapMode = 'parallel'; // Default wrap mode
            
            // Add additional CSS dynamically for advanced wrapping
            const style = document.createElement('style');
            style.textContent = `
                img {
                    max-width: 100%;
                    height: auto;
                    box-sizing: border-box;
                }
                
                img.wrap-inline {
                    display: inline;
                    vertical-align: middle;
                    margin: 0 5px;
                }
                
                img.wrap-float-left {
                    float: left;
                    margin: 0 15px 10px 0;
                    shape-outside: margin-box;
                }
                
                img.wrap-float-right {
                    float: right;
                    margin: 0 0 10px 15px;
                    shape-outside: margin-box;
                }
                
                img.wrap-tight-left {
                    float: left;
                    margin: 0 8px 5px 0;
                    shape-outside: margin-box;
                }
                
                img.wrap-tight-right {
                    float: right;
                    margin: 0 0 5px 8px;
                    shape-outside: margin-box;
                }
                
                img.wrap-parallel {
                    display: block;
                    margin: 0 auto;
                    max-width: 80%;
                }
                
                .parallel-wrap-container {
                    position: relative;
                    display: table;
                    margin: 10px auto;
                    clear: both;
                    width: 100%;
                }
                
                .parallel-text-column {
                    display: table-cell;
                    width: 30%;
                    vertical-align: middle;
                    padding: 0 10px;
                    text-align: justify;
                }
                
                .parallel-image-column {
                    display: table-cell;
                    width: 40%;
                    vertical-align: middle;
                    text-align: center;
                }
                
                img.wrap-top-bottom {
                    display: block;
                    margin: 10px auto;
                    clear: both;
                }
                
                img.wrap-center {
                    display: block;
                    margin: 10px auto;
                    float: none;
                }
                
                .text-wrap-none {
                    clear: both;
                    height: 0;
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
                
                img.selected {
                    outline: 2px solid #4285f4;
                    box-shadow: 0 0 10px rgba(66, 133, 244, 0.5);
                }
                
                img.resizing {
                    outline: 2px dashed #4285f4;
                }
            `;
            document.head.appendChild(style);

            // Create resize handles
            function createResizeHandles(image) {
                removeResizeHandles();
                const container = document.createElement('div');
                container.style.position = 'absolute';
                
                // Get position relative to editor
                const rect = image.getBoundingClientRect();
                const editorRect = editor.getBoundingClientRect();
                container.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                container.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                container.style.width = image.offsetWidth + 'px';
                container.style.height = image.offsetHeight + 'px';
                
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
                if (!selectedImage) return;
                
                const container = editor.querySelector('.resize-container');
                if (container) {
                    const rect = selectedImage.getBoundingClientRect();
                    const editorRect = editor.getBoundingClientRect();
                    
                    container.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                    container.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                    container.style.width = selectedImage.offsetWidth + 'px';
                    container.style.height = selectedImage.offsetHeight + 'px';
                }
            }

            // Start resizing
            function startResize(e, handle) {
                if (!selectedImage) return;
                isResizing = true;
                currentResizeHandle = handle;
                lastX = e.clientX;
                lastY = e.clientY;
                resizeStartWidth = selectedImage.offsetWidth;
                resizeStartHeight = selectedImage.offsetHeight;
                selectedImage.classList.add('resizing');
                
                document.addEventListener('mousemove', handleResize);
                document.addEventListener('mouseup', stopResize);
            }

            // Handle resize
            function handleResize(e) {
                if (!isResizing || !selectedImage || !currentResizeHandle) return;
                
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
                
                selectedImage.style.width = newWidth + 'px';
                selectedImage.style.height = newHeight + 'px';
                
                updateResizeHandles();
            }

            // Stop resizing
            function stopResize() {
                isResizing = false;
                currentResizeHandle = null;
                if (selectedImage) selectedImage.classList.remove('resizing');
                document.removeEventListener('mousemove', handleResize);
                document.removeEventListener('mouseup', stopResize);
            }

            // Check if the image is in a parallel wrap container
            function isInParallelContainer(image) {
                return image.parentNode && 
                       image.parentNode.classList && 
                       image.parentNode.classList.contains('parallel-image-column') &&
                       image.parentNode.parentNode &&
                       image.parentNode.parentNode.classList &&
                       image.parentNode.parentNode.classList.contains('parallel-wrap-container');
            }

            // Extract text content from a parallel wrap container
            function getParallelContainerText(container) {
                const leftColumn = container.querySelector('.parallel-text-column:first-child');
                const rightColumn = container.querySelector('.parallel-text-column:last-child');
                
                return {
                    leftText: leftColumn ? leftColumn.innerHTML : '',
                    rightText: rightColumn ? rightColumn.innerHTML : ''
                };
            }

            // Start dragging
            function startDrag(e, image) {
                if (isResizing) return;
                isDragging = true;
                lastX = e.clientX;
                lastY = e.clientY;
                
                // Check if the image is in a parallel container
                if (isInParallelContainer(image)) {
                    // Store the parallel container text
                    const container = image.parentNode.parentNode;
                    const textContent = getParallelContainerText(container);
                    image.dataset.leftText = textContent.leftText;
                    image.dataset.rightText = textContent.rightText;
                }
                
                // Store the current wrap mode
                const wrapMode = getCurrentWrapMode(image);
                image.dataset.wrapMode = wrapMode;
                
                document.addEventListener('mousemove', handleDrag);
                document.addEventListener('mouseup', stopDrag);
            }

            // Handle drag
            function handleDrag(e) {
                if (!isDragging || !selectedImage) return;
                
                // Create a temporary marker for insertion
                const temp = document.createElement('span');
                temp.style.display = 'inline-block';
                temp.style.width = '1px';
                temp.style.height = '1px';
                
                // Find insertion point from cursor position
                const range = document.caretRangeFromPoint(e.clientX, e.clientY);
                if (range) {
                    // Insert temporary marker
                    range.insertNode(temp);
                    
                    // Get the stored wrap mode
                    const wrapMode = selectedImage.dataset.wrapMode || 'parallel';
                    
                    // Check if the image is in a parallel container
                    if (isInParallelContainer(selectedImage)) {
                        // Remove the image from the container
                        const container = selectedImage.parentNode.parentNode;
                        container.parentNode.insertBefore(selectedImage, container);
                        container.remove();
                    }
                    
                    // Remove any text-wrap-none elements if they follow the image
                    const siblings = [];
                    let nextSibling = selectedImage.nextSibling;
                    while (nextSibling) {
                        siblings.push(nextSibling);
                        nextSibling = nextSibling.nextSibling;
                    }
                    
                    siblings.forEach(sibling => {
                        if (sibling.nodeType === Node.ELEMENT_NODE && 
                            sibling.classList && 
                            sibling.classList.contains('text-wrap-none')) {
                            sibling.remove();
                        }
                    });
                    
                    // Move the image to the new position
                    temp.parentNode.insertBefore(selectedImage, temp);
                    temp.remove();
                    
                    // Re-apply wrapping based on stored left/right text if it was parallel
                    if (wrapMode === 'parallel' && 
                        selectedImage.dataset.leftText && 
                        selectedImage.dataset.rightText) {
                        createParallelWrap(
                            selectedImage, 
                            selectedImage.dataset.leftText, 
                            selectedImage.dataset.rightText
                        );
                    } else {
                        // Apply regular wrapping
                        setTextWrap(selectedImage, wrapMode);
                    }
                    
                    // Update the resize handles
                    updateResizeHandles();
                }
            }

            // Stop dragging
            function stopDrag() {
                isDragging = false;
                document.removeEventListener('mousemove', handleDrag);
                document.removeEventListener('mouseup', stopDrag);
                
                // Re-apply text wrap
                if (selectedImage) {
                    const wrapMode = selectedImage.dataset.wrapMode || getCurrentWrapMode(selectedImage);
                    setTextWrap(selectedImage, wrapMode);
                }
            }

            // Get current wrap mode from image classes
            function getCurrentWrapMode(image) {
                if (image.classList.contains('wrap-inline')) return 'inline';
                if (image.classList.contains('wrap-float-left')) return 'float-left';
                if (image.classList.contains('wrap-float-right')) return 'float-right';
                if (image.classList.contains('wrap-tight-left')) return 'tight-left';
                if (image.classList.contains('wrap-tight-right')) return 'tight-right';
                if (image.classList.contains('wrap-top-bottom')) return 'top-bottom';
                if (image.classList.contains('wrap-center')) return 'center';
                if (image.classList.contains('wrap-parallel')) return 'parallel';
                
                // Check if it's in a parallel container
                if (isInParallelContainer(image)) {
                    return 'parallel';
                }
                
                return 'parallel'; // Default
            }

            // Clear all wrap classes
            function clearWrapClasses(image) {
                image.classList.remove(
                    'wrap-inline', 'wrap-float-left', 'wrap-float-right',
                    'wrap-tight-left', 'wrap-tight-right', 'wrap-top-bottom',
                    'wrap-center', 'wrap-parallel'
                );
            }

            // Create parallel wrap container with text on both sides
            function createParallelWrap(image, leftText = '', rightText = '') {
                // Check if already in a parallel container
                if (isInParallelContainer(image)) {
                    return;
                }
                
                // Create parallel wrap container structure
                const container = document.createElement('div');
                container.className = 'parallel-wrap-container';
                
                const leftColumn = document.createElement('div');
                leftColumn.className = 'parallel-text-column';
                leftColumn.innerHTML = leftText || '<p>&nbsp;</p>';
                leftColumn.contentEditable = true;
                
                const imageColumn = document.createElement('div');
                imageColumn.className = 'parallel-image-column';
                
                const rightColumn = document.createElement('div');
                rightColumn.className = 'parallel-text-column';
                rightColumn.innerHTML = rightText || '<p>&nbsp;</p>';
                rightColumn.contentEditable = true;
                
                // Replace the image with the container
                const parent = image.parentNode;
                parent.insertBefore(container, image);
                
                // Add all elements to the container
                container.appendChild(leftColumn);
                container.appendChild(imageColumn);
                container.appendChild(rightColumn);
                imageColumn.appendChild(image);
                
                // Apply parallel styling to the image
                clearWrapClasses(image);
                image.classList.add('wrap-parallel');
                image.style.float = '';
                image.style.margin = '0 auto';
                image.style.display = 'block';
                
                // Update resize handles if needed
                if (selectedImage === image) {
                    updateResizeHandles();
                }
            }

            // Extract surrounding text for parallel wrapping
            function extractSurroundingText(image) {
                // Look for text nodes before and after the image
                let leftText = '';
                let rightText = '';
                
                // Get a paragraph or two before the image
                let prevSibling = image.previousSibling;
                let leftParagraphCount = 0;
                const maxParagraphs = 1;
                
                // First, collect all previous nodes that we might consider
                const prevNodes = [];
                while (prevSibling && leftParagraphCount < maxParagraphs) {
                    prevNodes.push(prevSibling);
                    
                    // Count paragraphs
                    if (prevSibling.nodeType === Node.ELEMENT_NODE && 
                        (prevSibling.tagName === 'P' || prevSibling.tagName === 'DIV')) {
                        leftParagraphCount++;
                    }
                    
                    prevSibling = prevSibling.previousSibling;
                }
                
                // Process the collected nodes in reverse (to get correct order)
                for (let i = prevNodes.length - 1; i >= 0; i--) {
                    const node = prevNodes[i];
                    if (node.nodeType === Node.TEXT_NODE) {
                        if (node.textContent.trim()) {
                            leftText += node.textContent;
                        }
                    } else if (node.nodeType === Node.ELEMENT_NODE) {
                        if (node.tagName === 'BR') {
                            leftText += '<br>';
                        } else if (node.innerHTML && node.innerHTML.trim()) {
                            leftText += node.outerHTML;
                        }
                    }
                }
                
                // Get a paragraph or two after the image
                let nextSibling = image.nextSibling;
                let rightParagraphCount = 0;
                
                // Process all following nodes
                while (nextSibling && rightParagraphCount < maxParagraphs) {
                    if (nextSibling.nodeType === Node.TEXT_NODE) {
                        if (nextSibling.textContent.trim()) {
                            rightText += nextSibling.textContent;
                        }
                    } else if (nextSibling.nodeType === Node.ELEMENT_NODE) {
                        if (nextSibling.tagName === 'BR') {
                            rightText += '<br>';
                        } else if (nextSibling.innerHTML && nextSibling.innerHTML.trim() && 
                                   !nextSibling.classList.contains('text-wrap-none')) {
                            rightText += nextSibling.outerHTML;
                            
                            // Count paragraphs
                            if (nextSibling.tagName === 'P' || nextSibling.tagName === 'DIV') {
                                rightParagraphCount++;
                            }
                        }
                    }
                    
                    nextSibling = nextSibling.nextSibling;
                }
                
                // Ensure content is wrapped in paragraphs
                if (leftText && !(/<p>/i.test(leftText) || /<div>/i.test(leftText))) {
                    leftText = '<p>' + leftText + '</p>';
                }
                
                if (rightText && !(/<p>/i.test(rightText) || /<div>/i.test(rightText))) {
                    rightText = '<p>' + rightText + '</p>';
                }
                
                return { leftText, rightText };
            }

            // Set text wrap
            function setTextWrap(image, wrapMode) {
                // Update current wrap mode
                currentWrapMode = wrapMode;
                
                // Check if currently in a parallel container
                const inParallelContainer = isInParallelContainer(image);
                
                // For parallel mode, we need to extract the text first if not already in parallel
                let textContent = { leftText: '', rightText: '' };
                if (wrapMode === 'parallel' && !inParallelContainer) {
                    textContent = extractSurroundingText(image);
                } else if (inParallelContainer) {
                    const container = image.parentNode.parentNode;
                    textContent = getParallelContainerText(container);
                }
                
                // Remove from parallel container if needed
                if (inParallelContainer && wrapMode !== 'parallel') {
                    const container = image.parentNode.parentNode;
                    container.parentNode.insertBefore(image, container);
                    container.remove();
                }
                
                // Remove any text-wrap-none elements
                const siblings = [];
                let nextSibling = image.nextSibling;
                while (nextSibling) {
                    siblings.push(nextSibling);
                    nextSibling = nextSibling.nextSibling;
                }
                
                siblings.forEach(sibling => {
                    if (sibling.nodeType === Node.ELEMENT_NODE && 
                        sibling.classList && 
                        sibling.classList.contains('text-wrap-none')) {
                        sibling.remove();
                    }
                });
                
                // Clear all styles and classes
                clearWrapClasses(image);
                image.style.float = '';
                image.style.margin = '';
                image.style.display = '';
                image.style.clear = '';
                
                // Apply the requested wrap mode
                switch (wrapMode) {
                    case 'parallel':
                        // Special parallel wrapping with text on both sides
                        if (!inParallelContainer) {
                            // Remove nearby text nodes to be used in the columns
                            const nodesToRemove = [];
                            
                            let prevSibling = image.previousSibling;
                            let leftParagraphCount = 0;
                            const maxParagraphs = 1;
                            
                            while (prevSibling && leftParagraphCount < maxParagraphs) {
                                nodesToRemove.push(prevSibling);
                                
                                // Count paragraphs
                                if (prevSibling.nodeType === Node.ELEMENT_NODE && 
                                    (prevSibling.tagName === 'P' || prevSibling.tagName === 'DIV')) {
                                    leftParagraphCount++;
                                }
                                
                                prevSibling = prevSibling.previousSibling;
                            }
                            
                            let nextSibling = image.nextSibling;
                            let rightParagraphCount = 0;
                            
                            while (nextSibling && rightParagraphCount < maxParagraphs) {
                                nodesToRemove.push(nextSibling);
                                
                                // Count paragraphs
                                if (nextSibling.nodeType === Node.ELEMENT_NODE && 
                                    (nextSibling.tagName === 'P' || nextSibling.tagName === 'DIV')) {
                                    rightParagraphCount++;
                                }
                                
                                nextSibling = nextSibling.nextSibling;
                            }
                            
                            // Create the parallel container
                            createParallelWrap(image, textContent.leftText, textContent.rightText);
                            
                            // Remove the original text nodes
                            nodesToRemove.forEach(node => {
                                if (node.parentNode) {
                                    node.parentNode.removeChild(node);
                                }
                            });
                        }
                        break;
                    
                    case 'inline':
                        // Basic inline mode (like a character)
                        image.classList.add('wrap-inline');
                        break;
                        
                    case 'float-left':
                        // Square wrapping with image on left
                        image.classList.add('wrap-float-left');
                        image.style.float = 'left';
                        image.style.margin = '0 15px 10px 0';
                        break;
                        
                    case 'float-right':
                        // Square wrapping with image on right
                        image.classList.add('wrap-float-right');
                        image.style.float = 'right';
                        image.style.margin = '0 0 10px 15px';
                        break;
                        
                    case 'tight-left':
                        // Tight wrapping with image on left
                        image.classList.add('wrap-tight-left');
                        image.style.float = 'left';
                        image.style.margin = '0 8px 5px 0';
                        break;
                        
                    case 'tight-right':
                        // Tight wrapping with image on right
                        image.classList.add('wrap-tight-right');
                        image.style.float = 'right';
                        image.style.margin = '0 0 5px 8px';
                        break;
                        
                    case 'top-bottom':
                        // No wrapping - text above and below only
                        image.classList.add('wrap-top-bottom');
                        image.style.display = 'block';
                        image.style.margin = '10px auto';
                        
                        // Add a clear div to prevent text wrapping
                        const clearDiv = document.createElement('div');
                        clearDiv.className = 'text-wrap-none';
                        clearDiv.style.clear = 'both';
                        
                        if (image.nextSibling) {
                            image.parentNode.insertBefore(clearDiv, image.nextSibling);
                        } else {
                            image.parentNode.appendChild(clearDiv);
                        }
                        break;
                        
                    case 'center':
                        // Image is centered with text above and below
                        image.classList.add('wrap-center');
                        image.style.display = 'block';
                        image.style.margin = '10px auto';
                        
                        // Add a clear div to prevent text wrapping
                        const clearDiv2 = document.createElement('div');
                        clearDiv2.className = 'text-wrap-none';
                        clearDiv2.style.clear = 'both';
                        
                        if (image.nextSibling) {
                            image.parentNode.insertBefore(clearDiv2, image.nextSibling);
                        } else {
                            image.parentNode.appendChild(clearDiv2);
                        }
                        break;
                }
                
                // Update resize handles if image is selected
                if (selectedImage === image) {
                    updateResizeHandles();
                }
            }

            // Select image
            function selectImage(image) {
                if (selectedImage) selectedImage.classList.remove('selected');
                selectedImage = image;
                selectedImage.classList.add('selected');
                
                // Store the current wrap mode in dataset for potential drag operations
                image.dataset.wrapMode = getCurrentWrapMode(image);
                
                // If it's in a parallel container, store the text
                if (isInParallelContainer(image)) {
                    const container = image.parentNode.parentNode;
                    const textContent = getParallelContainerText(container);
                    image.dataset.leftText = textContent.leftText;
                    image.dataset.rightText = textContent.rightText;
                }
                
                createResizeHandles(image);
            }

            // Deselect image
            function deselectImage() {
                if (selectedImage) {
                    selectedImage.classList.remove('selected');
                    selectedImage = null;
                }
                removeResizeHandles();
            }

            // Create context menu
            function createContextMenu(x, y) {
                removeContextMenu();
                contextMenu = document.createElement('div');
                contextMenu.className = 'context-menu';
                contextMenu.style.left = x + 'px';
                contextMenu.style.top = y + 'px';
                
                const menuItems = [
                    { label: 'Text Wrapping', submenu: [
                        { label: 'Parallel (Text on Both Sides)', action: 'wrap-parallel' },
                        { label: 'In Line with Text', action: 'wrap-inline' },
                        { label: 'Square Left', action: 'wrap-float-left' },
                        { label: 'Square Right', action: 'wrap-float-right' },
                        { label: 'Tight Left', action: 'wrap-tight-left' },
                        { label: 'Tight Right', action: 'wrap-tight-right' },
                        { label: 'Top and Bottom', action: 'wrap-top-bottom' },
                        { label: 'Centered', action: 'wrap-center' }
                    ]},
                    { type: 'separator' },
                    { label: 'Copy Image', action: 'copy' },
                    { label: 'Delete Image', action: 'delete' }
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
                        menuItem.textContent = item.label;
                        
                        // Highlight the active wrap mode
                        if (item.action.startsWith('wrap-')) {
                            const wrapType = item.action.replace('wrap-', '');
                            if (selectedImage && wrapType === getCurrentWrapMode(selectedImage)) {
                                menuItem.style.fontWeight = 'bold';
                            }
                        }
                        
                        menuItem.addEventListener('click', (e) => {
                            e.stopPropagation();
                            handleContextMenuAction(item.action);
                            removeContextMenu();
                        });
                        parent.appendChild(menuItem);
                    }
                });
            }

            // Handle context menu action
            function handleContextMenuAction(action) {
                if (!selectedImage) return;
                
                if (action.startsWith('wrap-')) {
                    const wrapMode = action.replace('wrap-', '');
                    setTextWrap(selectedImage, wrapMode);
                    // Store the wrap mode for potential drag operations
                    selectedImage.dataset.wrapMode = wrapMode;
                } else if (action === 'copy') {
                    copyImageToClipboard(selectedImage);
                } else if (action === 'delete') {
                    deleteImage(selectedImage);
                }
            }

            // Copy image to clipboard
            function copyImageToClipboard(image) {
                const canvas = document.createElement('canvas');
                canvas.width = image.naturalWidth;
                canvas.height = image.naturalHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(image, 0, 0);
                canvas.toBlob(blob => {
                    const item = new ClipboardItem({ 'image/png': blob });
                    navigator.clipboard.write([item]).then(
                        () => console.log('Image copied to clipboard'),
                        err => console.error('Error copying image: ', err)
                    );
                });
            }

            // Delete image
            function deleteImage(image) {
                // Check if the image is in a parallel container
                if (isInParallelContainer(image)) {
                    const container = image.parentNode.parentNode;
                    container.remove();
                    deselectImage();
                    return;
                }
                
                // Remove any clearing elements
                const siblings = [];
                let nextSibling = image.nextSibling;
                while (nextSibling) {
                    siblings.push(nextSibling);
                    nextSibling = nextSibling.nextSibling;
                }
                
                siblings.forEach(sibling => {
                    if (sibling.nodeType === Node.ELEMENT_NODE && 
                        sibling.classList && 
                        sibling.classList.contains('text-wrap-none')) {
                        sibling.remove();
                    }
                });
                
                // Deselect the image
                deselectImage();
                
                // Remove the image
                image.remove();
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
                }
            }

            // Event listeners
            editor.addEventListener('click', (e) => {
                removeContextMenu();
                if (e.target.tagName === 'IMG') {
                    e.preventDefault();
                    selectImage(e.target);
                } else {
                    deselectImage();
                }
            });

            editor.addEventListener('contextmenu', (e) => {
                if (e.target.tagName === 'IMG') {
                    e.preventDefault();
                    selectImage(e.target);
                    createContextMenu(e.clientX, e.clientY);
                }
            });

            editor.addEventListener('mousedown', (e) => {
                if (e.target.tagName === 'IMG' && e.button === 0) {
                    e.preventDefault();
                    if (selectedImage !== e.target) {
                        selectImage(e.target);
                    }
                    startDrag(e, e.target);
                }
            });

            // Window scroll event to update resize handles
            window.addEventListener('scroll', () => {
                if (selectedImage) {
                    updateResizeHandles();
                }
            });

            // Editor scroll event to update resize handles
            editor.addEventListener('scroll', () => {
                if (selectedImage) {
                    updateResizeHandles();
                }
            });

            // Initialize existing images
            editor.querySelectorAll('img').forEach(img => {
                img.contentEditable = false;
                img.draggable = true;
                
                // If no special class, set default wrapping
                if (!img.classList.contains('wrap-inline') && 
                    !img.classList.contains('wrap-float-left') &&
                    !img.classList.contains('wrap-float-right') &&
                    !img.classList.contains('wrap-tight-left') &&
                    !img.classList.contains('wrap-tight-right') &&
                    !img.classList.contains('wrap-top-bottom') &&
                    !img.classList.contains('wrap-center') &&
                    !img.classList.contains('wrap-parallel') &&
                    !isInParallelContainer(img)) {
                    setTextWrap(img, 'parallel');
                }
            });

            // Mutation observer for new images
            const observer = new MutationObserver(mutations => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.tagName === 'IMG') {
                            node.contentEditable = false;
                            node.draggable = true;
                            
                            // Apply default wrapping if no wrap class is present
                            const hasWrapClass = node.classList && 
                                (node.classList.contains('wrap-inline') || 
                                 node.classList.contains('wrap-float-left') ||
                                 node.classList.contains('wrap-float-right') ||
                                 node.classList.contains('wrap-tight-left') ||
                                 node.classList.contains('wrap-tight-right') ||
                                 node.classList.contains('wrap-top-bottom') ||
                                 node.classList.contains('wrap-center') ||
                                 node.classList.contains('wrap-parallel'));
                            
                            const inParallel = isInParallelContainer(node);
                            
                            if (!hasWrapClass && !inParallel) {
                                setTextWrap(node, 'parallel');
                            }
                        }
                    });
                });
            });
            observer.observe(editor, { childList: true, subtree: true });

            // Function to insert and select image
            window.insertAndSelectImage = function(src) {
                document.execCommand('insertHTML', false, '<img src="' + src + '">');
                const images = editor.querySelectorAll('img');
                const lastImage = images[images.length - 1];
                if (lastImage) {
                    lastImage.contentEditable = false;
                    lastImage.draggable = true;
                    selectImage(lastImage);
                    setTextWrap(lastImage, 'parallel'); // Default to parallel for new images
                }
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
            script = "document.body.style.backgroundColor = '#1e1e1e'; document.body.style.color = '#e0e0e0';"
        else:
            btn.set_icon_name("display-brightness")
            script = "document.body.style.backgroundColor = '#ffffff'; document.body.style.color = '#000000';"
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

if __name__ == "__main__":
    app = Writer()
    app.run()
