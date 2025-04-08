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
        /* Remaining styles for images, context menu, etc., remain unchanged */
        img {
            display: inline-block;
            max-width: 50%;
            cursor: move;
        }
        img.selected {
            outline: 2px solid #4285f4;
            box-shadow: 0 0 10px rgba(66, 133, 244, 0.5);
        }
        img.resizing {
            outline: 2px dashed #4285f4;
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
        img.align-left {
            float: left;
            margin: 0 15px 10px 0;
        }
        img.align-right {
            float: right;
            margin: 0 0 10px 15px;
        }
        img.align-center {
            display: block;
            margin: 10px auto;
            float: none;
        }
        img.align-none {
            float: none;
            margin: 10px 0;
        }
        .text-wrap-none {
            clear: both;
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

        textbox_btn = Gtk.Button(icon_name="text-editor-symbolic")
        textbox_btn.add_css_class("flat")
        textbox_btn.set_tooltip_text("Insert Text Box")
        textbox_btn.connect("clicked", self.on_insert_textbox_clicked)
        text_format_group.append(textbox_btn)

        textbox_with_header_btn = Gtk.Button(icon_name="insert-text-symbolic")
        textbox_with_header_btn.add_css_class("flat")
        textbox_with_header_btn.set_tooltip_text("Insert Text Box with Title")
        textbox_with_header_btn.connect("clicked", self.on_insert_textbox_with_header_clicked)
        text_format_group.append(textbox_with_header_btn)

        # Inside the __init__ method, after other toolbar buttons in text_format_group
        wrap_indicators_btn = Gtk.Button(icon_name="view-grid-symbolic")  # You can choose a better icon
        wrap_indicators_btn.add_css_class("flat")
        wrap_indicators_btn.set_tooltip_text("Toggle Wrap Indicators")
        wrap_indicators_btn.connect("clicked", self.on_toggle_wrap_indicators)
        text_format_group.append(wrap_indicators_btn)

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
            
            # Setup Textbox handling
            self.setup_textbox_handling()

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

            // Create resize handles
            function createResizeHandles(image) {
                removeResizeHandles();
                const container = document.createElement('div');
                container.style.position = 'absolute';
                container.style.left = image.offsetLeft + 'px';
                container.style.top = image.offsetTop + 'px';
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

            // Start dragging
            function startDrag(e, image) {
                if (isResizing) return;
                isDragging = true;
                lastX = e.clientX;
                lastY = e.clientY;
                document.addEventListener('mousemove', handleDrag);
                document.addEventListener('mouseup', stopDrag);
            }

            // Handle drag
            function handleDrag(e) {
                if (!isDragging || !selectedImage) return;
                
                const temp = document.createElement('span');
                temp.style.display = 'inline-block';
                temp.style.width = '1px';
                temp.style.height = '1px';
                
                const range = document.caretRangeFromPoint(e.clientX, e.clientY);
                if (range) {
                    range.insertNode(temp);
                    
                    temp.parentNode.insertBefore(selectedImage, temp);
                    temp.remove();
                    
                    updateResizeHandles();
                }
            }

            // Stop dragging
            function stopDrag() {
                isDragging = false;
                document.removeEventListener('mousemove', handleDrag);
                document.removeEventListener('mouseup', stopDrag);
            }

            // Select image
            function selectImage(image) {
                if (selectedImage) selectedImage.classList.remove('selected');
                selectedImage = image;
                selectedImage.classList.add('selected');
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
                    { label: 'Resize Image', action: 'resize' },
                    { label: 'Alignment', submenu: [
                        { label: 'Left', action: 'align-left' },
                        { label: 'Center', action: 'align-center' },
                        { label: 'Right', action: 'align-right' },
                        { label: 'None', action: 'align-none' }
                    ]},
                    { label: 'Text Wrap', submenu: [
                        { label: 'Around', action: 'wrap-around' },
                        { label: 'None', action: 'wrap-none' }
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
                switch (action) {
                    case 'resize':
                        // Already selected
                        break;
                    case 'align-left':
                        setImageAlignment(selectedImage, 'left');
                        break;
                    case 'align-center':
                        setImageAlignment(selectedImage, 'center');
                        break;
                    case 'align-right':
                        setImageAlignment(selectedImage, 'right');
                        break;
                    case 'align-none':
                        setImageAlignment(selectedImage, 'none');
                        break;
                    case 'wrap-around':
                        setTextWrap(selectedImage, 'around');
                        break;
                    case 'wrap-none':
                        setTextWrap(selectedImage, 'none');
                        break;
                    case 'copy':
                        copyImageToClipboard(selectedImage);
                        break;
                    case 'delete':
                        deleteImage(selectedImage);
                        break;
                }
            }

            // Set image alignment
            function setImageAlignment(image, alignment) {
                image.classList.remove('align-left', 'align-right', 'align-center', 'align-none');
                image.classList.add(`align-${alignment}`);
                updateResizeHandles();
            }

            // Set text wrap
            function setTextWrap(image, wrap) {
                if (wrap === 'none') {
                    image.style.float = 'none';
                    const clearDiv = document.createElement('div');
                    clearDiv.className = 'text-wrap-none';
                    clearDiv.style.clear = 'both';
                    if (image.nextSibling) {
                        image.parentNode.insertBefore(clearDiv, image.nextSibling);
                    } else {
                        image.parentNode.appendChild(clearDiv);
                    }
                } else if (wrap === 'around') {
                    if (!image.classList.contains('align-left') && !image.classList.contains('align-right')) {
                        setImageAlignment(image, 'left');
                    }
                    const nextSibling = image.nextSibling;
                    if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                        nextSibling.remove();
                    }
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
                const nextSibling = image.nextSibling;
                if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                    nextSibling.remove();
                }
                deselectImage();
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

            // Initialize existing images
            editor.querySelectorAll('img').forEach(img => {
                img.contentEditable = false;
                img.draggable = true;
            });

            // Mutation observer for new images
            const observer = new MutationObserver(mutations => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.tagName === 'IMG') {
                            node.contentEditable = false;
                            node.draggable = true;
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
                    setImageAlignment(lastImage, 'left');
                    setTextWrap(lastImage, 'around');
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


#############
    def on_toggle_wrap_indicators(self, action=None, parameter=None):
        """Toggle the display of text wrap indicators"""
        self.exec_js("window.toggleWrapIndicators();")
        
    # First, define these class-level methods for button connections

    def on_insert_textbox_clicked(self, btn):
        """Handle click on the Insert Text Box button"""
        self.exec_js("window.createTextBox(false);")
        
    def on_insert_textbox_with_header_clicked(self, btn):
        """Handle click on the Insert Text Box with Header button"""
        self.exec_js("window.createTextBox(true);")

        # Then implement the textbox handling setup method
    def setup_textbox_handling(self):
        """Set up JavaScript code for textbox handling with advanced text wrapping in the webview"""
        # First load the base textbox functionality
        base_script = """
        (function() {
            const editor = document.getElementById('editor');
            if (!editor) {
                console.error('Editor element not found');
                return;
            }

            // CSS for textboxes
            const styleElement = document.createElement('style');
            styleElement.textContent = `
                .textbox {
                    position: relative;
                    border: 1px dashed #999;
                    padding: 10px;
                    min-width: 100px;
                    min-height: 50px;
                    max-width: 100%;
                    box-sizing: border-box;
                    overflow: visible;
                    cursor: default;
                    display: inline-block;
                    margin: 5px;
                    background-color: rgba(250, 250, 250, 0.7);
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    transition: border-color 0.2s, box-shadow 0.2s;
                }
                @media (prefers-color-scheme: dark) {
                    .textbox {
                        border-color: #777;
                        background-color: rgba(60, 60, 60, 0.7);
                    }
                    .textbox.selected {
                        outline: 2px solid #5e97f6;
                        box-shadow: 0 0 10px rgba(94, 151, 246, 0.5);
                    }
                }
                @media (prefers-color-scheme: light) {
                    .textbox {
                        border-color: #999;
                        background-color: rgba(250, 250, 250, 0.7);
                    }
                    .textbox.selected {
                        outline: 2px solid #4285f4;
                        box-shadow: 0 0 10px rgba(66, 133, 244, 0.5);
                    }
                }
                .textbox.selected {
                    z-index: 2;
                }
                .textbox.resizing {
                    outline-style: dashed;
                }
                .textbox-content {
                    width: 100%;
                    height: 100%;
                    outline: none;
                    overflow: visible;
                    text-align: left;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    min-height: 100%;
                    font-family: inherit;
                    font-size: inherit;
                    color: inherit;
                }
                .textbox-header {
                    padding: 5px 10px;
                    background-color: rgba(0, 0, 0, 0.05);
                    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
                    font-weight: bold;
                    margin: -10px -10px 10px -10px;
                    cursor: move;
                }
                @media (prefers-color-scheme: dark) {
                    .textbox-header {
                        background-color: rgba(255, 255, 255, 0.1);
                        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                    }
                }

                /* Resize handles */
                .resize-container {
                    z-index: 1000;
                }
                .resize-handle {
                    position: absolute;
                    width: 10px;
                    height: 10px;
                    background-color: #4285f4;
                    border: 1px solid white;
                    border-radius: 50%;
                    z-index: 999;
                    transition: transform 0.1s;
                }
                .resize-handle:hover {
                    transform: scale(1.2);
                }
                .tl-handle { top: -5px; left: -5px; cursor: nw-resize; }
                .tr-handle { top: -5px; right: -5px; cursor: ne-resize; }
                .bl-handle { bottom: -5px; left: -5px; cursor: sw-resize; }
                .br-handle { bottom: -5px; right: -5px; cursor: se-resize; }

                /* Context menu */
                .context-menu {
                    position: absolute;
                    background: white;
                    border: 1px solid #ccc;
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
                    z-index: 1001;
                    width: 180px;
                    border-radius: 4px;
                    padding: 4px 0;
                }
                @media (prefers-color-scheme: dark) {
                    .context-menu {
                        background: #333;
                        border-color: #555;
                        color: #eee;
                        box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
                    }
                    .context-menu-item:hover {
                        background-color: #444;
                    }
                    .context-menu-separator {
                        background-color: #555;
                    }
                    .context-menu-submenu-content {
                        background: #333;
                        border-color: #555;
                    }
                }
                .context-menu-item {
                    padding: 8px 12px;
                    cursor: pointer;
                    user-select: none;
                }
                .context-menu-item:hover {
                    background-color: #f0f0f0;
                }
                .context-menu-separator {
                    height: 1px;
                    background-color: #ddd;
                    margin: 4px 0;
                }
                .context-menu-submenu {
                    position: relative;
                }
                .context-menu-submenu:after {
                    content: '▶';
                    position: absolute;
                    right: 8px;
                    top: 8px;
                    font-size: 10px;
                    opacity: 0.7;
                }
                .context-menu-submenu-content {
                    display: none;
                    position: absolute;
                    left: 100%;
                    top: 0;
                    background: white;
                    border: 1px solid #ccc;
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
                    width: 180px;
                    border-radius: 4px;
                    padding: 4px 0;
                }
                .context-menu-submenu:hover .context-menu-submenu-content {
                    display: block;
                }
            `;
            document.head.appendChild(styleElement);

            // Textbox variables
            let selectedTextBox = null;
            let resizeHandles = [];
            let isDragging = false;
            let isResizing = false;
            let lastX, lastY;
            let dragOffsetX, dragOffsetY;
            let resizeStartWidth, resizeStartHeight;
            let currentResizeHandle = null;
            let contextMenu = null;
            
            // Create a new textbox
            function createTextBox(withHeader = false) {
                const textBox = document.createElement('div');
                textBox.className = 'textbox';
                textBox.style.width = '200px';
                textBox.style.height = 'auto';
                textBox.contentEditable = false;
                textBox.draggable = false;
                
                if (withHeader) {
                    const header = document.createElement('div');
                    header.className = 'textbox-header';
                    header.contentEditable = true;
                    header.textContent = 'Title';
                    header.addEventListener('mousedown', e => {
                        e.stopPropagation();
                        selectTextBox(textBox);
                        startDrag(e, textBox);
                    });
                    header.addEventListener('blur', () => {
                        if (header.textContent.trim() === '') {
                            header.textContent = 'Title';
                        }
                    });
                    header.addEventListener('focus', () => {
                        if (header.textContent === 'Title') {
                            header.textContent = '';
                        }
                    });
                    textBox.appendChild(header);
                }
                
                const content = document.createElement('div');
                content.className = 'textbox-content';
                content.contentEditable = true;
                content.textContent = 'Enter text here...';
                
                content.addEventListener('focus', () => {
                    if (content.textContent === 'Enter text here...') {
                        content.textContent = '';
                    }
                    // Prevent dragging when editing content
                    if (selectedTextBox === textBox) {
                        removeResizeHandles();
                    }
                });
                
                content.addEventListener('blur', () => {
                    if (content.textContent.trim() === '') {
                        content.textContent = 'Enter text here...';
                    }
                    // Re-enable selection and resize handles after editing
                    if (selectedTextBox === textBox) {
                        createResizeHandles(textBox);
                    }
                });
                
                content.addEventListener('mousedown', e => {
                    e.stopPropagation(); // Allow selection inside content area
                    selectTextBox(textBox);
                });
                
                content.addEventListener('keydown', e => {
                    if (e.key === 'Escape') {
                        content.blur();
                        textBox.focus();
                        e.preventDefault();
                    }
                });
                
                textBox.appendChild(content);
                
                // Insert at current selection
                const sel = window.getSelection();
                if (sel.rangeCount > 0) {
                    const range = sel.getRangeAt(0);
                    range.deleteContents();
                    range.insertNode(textBox);
                    // Create an empty paragraph after the textbox if needed
                    if (!textBox.nextSibling || (textBox.nextSibling.nodeType !== 1 && !textBox.nextSibling.textContent.trim())) {
                        const paragraph = document.createElement('p');
                        paragraph.innerHTML = '<br>';
                        textBox.parentNode.insertBefore(paragraph, textBox.nextSibling);
                    }
                } else {
                    editor.appendChild(textBox);
                }

                // Add event listeners for selection and drag
                setupTextBoxEvents(textBox);
                selectTextBox(textBox);
                
                // Focus the content for immediate editing
                content.focus();
                
                return textBox;
            }
            
            // Setup event listeners for a text box
            function setupTextBoxEvents(textBox) {
                textBox.addEventListener('mousedown', e => {
                    // Ignore mousedown on the content (handled separately)
                    if (e.target.classList.contains('textbox-content') || 
                        e.target.classList.contains('textbox-header')) {
                        return;
                    }
                    
                    e.preventDefault();
                    selectTextBox(textBox);
                    startDrag(e, textBox);
                });
                
                textBox.addEventListener('contextmenu', e => {
                    e.preventDefault();
                    selectTextBox(textBox);
                    showContextMenu(e.clientX, e.clientY);
                });
                
                textBox.addEventListener('keydown', e => {
                    // Delete key to delete textbox (when not editing content)
                    if ((e.key === 'Delete' || e.key === 'Backspace') && 
                        document.activeElement === textBox) {
                        e.preventDefault();
                        deleteTextBox(textBox);
                    }
                    
                    // Keyboard shortcuts for alignment
                    if (document.activeElement === textBox && e.ctrlKey) {
                        switch (e.key) {
                            case 'l': // Ctrl+L - Align left
                                e.preventDefault();
                                setTextBoxAlignment(textBox, 'left');
                                break;
                            case 'e': // Ctrl+E - Align center
                            case 'c': // Some users expect Ctrl+C for center
                                if (e.key === 'e' || (e.key === 'c' && e.shiftKey)) {
                                    e.preventDefault();
                                    setTextBoxAlignment(textBox, 'center');
                                }
                                break;
                            case 'r': // Ctrl+R - Align right
                                e.preventDefault();
                                setTextBoxAlignment(textBox, 'right');
                                break;
                            case 'j': // Ctrl+J - Align justify/none
                                e.preventDefault();
                                setTextBoxAlignment(textBox, 'none');
                                break;
                            case 'd': // Ctrl+D - Duplicate
                                e.preventDefault();
                                duplicateTextBox(textBox);
                                break;
                        }
                    }
                    
                    // Arrow keys to move textbox when not editing content
                    if (document.activeElement === textBox && 
                        !textBox.querySelector('.textbox-content:focus') &&
                        !textBox.querySelector('.textbox-header:focus')) {
                        
                        if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
                            e.preventDefault();
                            const moveStep = e.shiftKey ? 10 : 1;
                            
                            // Make position absolute if it's not already
                            if (window.getComputedStyle(textBox).position !== 'absolute') {
                                const rect = textBox.getBoundingClientRect();
                                const editorRect = editor.getBoundingClientRect();
                                textBox.style.position = 'absolute';
                                textBox.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                                textBox.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                                
                                // Remove any alignment classes
                                textBox.classList.remove('align-left', 'align-right', 'align-center', 'align-none');
                            }
                            
                            const currentLeft = parseInt(textBox.style.left) || 0;
                            const currentTop = parseInt(textBox.style.top) || 0;
                            
                            switch (e.key) {
                                case 'ArrowLeft':
                                    textBox.style.left = (currentLeft - moveStep) + 'px';
                                    break;
                                case 'ArrowRight':
                                    textBox.style.left = (currentLeft + moveStep) + 'px';
                                    break;
                                case 'ArrowUp':
                                    textBox.style.top = (currentTop - moveStep) + 'px';
                                    break;
                                case 'ArrowDown':
                                    textBox.style.top = (currentTop + moveStep) + 'px';
                                    break;
                            }
                            
                            updateResizeHandles();
                        }
                    }
                });
            }
            
            // Select a textbox
            function selectTextBox(textBox) {
                if (selectedTextBox) {
                    selectedTextBox.classList.remove('selected');
                }
                
                selectedTextBox = textBox;
                textBox.classList.add('selected');
                createResizeHandles(textBox);
                
                // Make the textbox focusable but not editable
                textBox.tabIndex = 0;
                
                // Handle click outside to deselect
                function handleClickOutside(e) {
                    if (!textBox.contains(e.target) && 
                        !e.target.closest('.resize-container') && 
                        !e.target.closest('.context-menu')) {
                        deselectTextBox();
                        document.removeEventListener('mousedown', handleClickOutside);
                    }
                }
                
                // Remove any existing listener before adding a new one
                document.removeEventListener('mousedown', handleClickOutside);
                document.addEventListener('mousedown', handleClickOutside);
            }
            
            // Deselect the current textbox
            function deselectTextBox() {
                if (selectedTextBox) {
                    selectedTextBox.classList.remove('selected');
                    selectedTextBox = null;
                    removeResizeHandles();
                }
            }
            
            // Create resize handles for the selected textbox
            function createResizeHandles(textBox) {
                removeResizeHandles();
                const container = document.createElement('div');
                container.className = 'resize-container';
                container.style.position = 'absolute';
                
                updateHandleContainerPosition(container, textBox);
                
                const positions = [
                    { className: 'tl-handle', position: 'tl' },
                    { className: 'tr-handle', position: 'tr' },
                    { className: 'bl-handle', position: 'bl' },
                    { className: 'br-handle', position: 'br' }
                ];
                
                positions.forEach(pos => {
                    const handle = document.createElement('div');
                    handle.className = `resize-handle ${pos.className}`;
                    handle.dataset.position = pos.position;
                    
                    handle.addEventListener('mousedown', e => {
                        e.preventDefault();
                        e.stopPropagation();
                        startResize(e, handle);
                    });
                    
                    container.appendChild(handle);
                    resizeHandles.push(handle);
                });
                
                editor.appendChild(container);
            }
            
            // Update the position of the resize handle container
            function updateHandleContainerPosition(container, textBox) {
                if (!container) {
                    container = document.querySelector('.resize-container');
                    if (!container) return;
                }
                
                if (!textBox) {
                    textBox = selectedTextBox;
                    if (!textBox) return;
                }
                
                const rect = textBox.getBoundingClientRect();
                const editorRect = editor.getBoundingClientRect();
                
                container.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                container.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                container.style.width = rect.width + 'px';
                container.style.height = rect.height + 'px';
            }
            
            // Remove resize handles
            function removeResizeHandles() {
                const container = document.querySelector('.resize-container');
                if (container) {
                    container.remove();
                }
                resizeHandles = [];
            }
            
            // Update resize handles position
            function updateResizeHandles() {
                updateHandleContainerPosition();
            }
            
            // Start dragging
            function startDrag(e, textBox) {
                if (isResizing) return;
                if (!textBox) return;
                
                isDragging = true;
                
                const rect = textBox.getBoundingClientRect();
                const editorRect = editor.getBoundingClientRect();
                
                // Calculate offset relative to the textbox
                dragOffsetX = e.clientX - rect.left;
                dragOffsetY = e.clientY - rect.top;
                
                // Make position absolute if it's not already
                if (window.getComputedStyle(textBox).position !== 'absolute') {
                    textBox.style.position = 'absolute';
                    textBox.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                    textBox.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                    
                    // Remove any alignment classes
                    textBox.classList.remove('align-left', 'align-right', 'align-center', 'align-none');
                }
                
                document.addEventListener('mousemove', handleDrag);
                document.addEventListener('mouseup', stopDrag);
            }
            
            // Handle drag movement
            function handleDrag(e) {
                if (!isDragging || !selectedTextBox) return;
                
                const editorRect = editor.getBoundingClientRect();
                const newLeft = e.clientX - editorRect.left - dragOffsetX + editor.scrollLeft;
                const newTop = e.clientY - editorRect.top - dragOffsetY + editor.scrollTop;
                
                // Calculate boundaries to keep textbox inside editor
                const maxLeft = editor.clientWidth - selectedTextBox.offsetWidth;
                const maxTop = editor.clientHeight - selectedTextBox.offsetHeight;
                
                selectedTextBox.style.left = Math.max(0, Math.min(newLeft, maxLeft)) + 'px';
                selectedTextBox.style.top = Math.max(0, Math.min(newTop, maxTop)) + 'px';
                
                updateResizeHandles();
            }
            
            // Stop dragging
            function stopDrag() {
                isDragging = false;
                document.removeEventListener('mousemove', handleDrag);
                document.removeEventListener('mouseup', stopDrag);
            }
            
            // Start resizing
            function startResize(e, handle) {
                if (!selectedTextBox) return;
                
                isResizing = true;
                currentResizeHandle = handle;
                
                lastX = e.clientX;
                lastY = e.clientY;
                
                resizeStartWidth = selectedTextBox.offsetWidth;
                resizeStartHeight = selectedTextBox.offsetHeight;
                
                selectedTextBox.classList.add('resizing');
                
                document.addEventListener('mousemove', handleResize);
                document.addEventListener('mouseup', stopResize);
            }
            
            // Handle resize movement
            function handleResize(e) {
                if (!isResizing || !selectedTextBox || !currentResizeHandle) return;
                
                const deltaX = e.clientX - lastX;
                const deltaY = e.clientY - lastY;
                const position = currentResizeHandle.dataset.position;
                
                let newWidth = resizeStartWidth;
                let newHeight = resizeStartHeight;
                
                // Adjust dimensions based on which handle is being dragged
                if (position.includes('r')) newWidth += deltaX;
                if (position.includes('l')) newWidth -= deltaX;
                if (position.includes('b')) newHeight += deltaY;
                if (position.includes('t')) newHeight -= deltaY;
                
                // Maintain aspect ratio if Shift key is pressed
                if (e.shiftKey) {
                    const aspectRatio = resizeStartWidth / resizeStartHeight;
                    if (Math.abs(deltaX) > Math.abs(deltaY)) {
                        newHeight = newWidth / aspectRatio;
                    } else {
                        newWidth = newHeight * aspectRatio;
                    }
                }
                
                // Apply minimum dimensions
                newWidth = Math.max(100, newWidth);
                newHeight = Math.max(50, newHeight);
                
                // If resizing from top or left, we need to adjust position as well
                if (position.includes('t') || position.includes('l')) {
                    // Calculate positional adjustment
                    let leftAdjust = 0;
                    let topAdjust = 0;
                    
                    if (position.includes('l')) {
                        leftAdjust = resizeStartWidth - newWidth;
                    }
                    
                    if (position.includes('t')) {
                        topAdjust = resizeStartHeight - newHeight;
                    }
                    
                    // Make sure position is absolute before adjusting
                    if (window.getComputedStyle(selectedTextBox).position !== 'absolute') {
                        const rect = selectedTextBox.getBoundingClientRect();
                        const editorRect = editor.getBoundingClientRect();
                        selectedTextBox.style.position = 'absolute';
                        selectedTextBox.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                        selectedTextBox.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                    }
                    
                    const currentLeft = parseInt(selectedTextBox.style.left) || 0;
                    const currentTop = parseInt(selectedTextBox.style.top) || 0;
                    
                    selectedTextBox.style.left = (currentLeft - leftAdjust) + 'px';
                    selectedTextBox.style.top = (currentTop - topAdjust) + 'px';
                }
                
                // Apply new dimensions
                selectedTextBox.style.width = newWidth + 'px';
                selectedTextBox.style.height = newHeight + 'px';
                
                // Update handles
                updateResizeHandles();
            }
            
            // Stop resizing
            function stopResize() {
                isResizing = false;
                currentResizeHandle = null;
                
                if (selectedTextBox) {
                    selectedTextBox.classList.remove('resizing');
                }
                
                document.removeEventListener('mousemove', handleResize);
                document.removeEventListener('mouseup', stopResize);
            }
            
            // Show context menu
            function showContextMenu(x, y) {
                removeContextMenu();
                
                if (!selectedTextBox) return;
                
                contextMenu = document.createElement('div');
                contextMenu.className = 'context-menu';
                
                // Position menu within viewport
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;
                const menuWidth = 180;
                const menuHeightEstimate = 300;
                
                const editorRect = editor.getBoundingClientRect();
                
                // Keep menu inside editor bounds
                let adjustedX = Math.min(x, editorRect.right - menuWidth);
                let adjustedY = Math.min(y, editorRect.bottom - menuHeightEstimate);
                adjustedX = Math.max(adjustedX, editorRect.left);
                adjustedY = Math.max(adjustedY, editorRect.top);
                
                // Convert to editor-relative coordinates
                contextMenu.style.left = (adjustedX - editorRect.left + editor.scrollLeft) + 'px';
                contextMenu.style.top = (adjustedY - editorRect.top + editor.scrollTop) + 'px';
                
                // Define menu items
                const menuItems = [
                    { label: 'Edit Text', action: 'edit-text' },
                    { label: 'Edit Title', action: 'edit-title', condition: () => !!selectedTextBox.querySelector('.textbox-header') },
                    { label: 'Add Title', action: 'add-title', condition: () => !selectedTextBox.querySelector('.textbox-header') },
                    { type: 'separator' },
                    { label: 'Style', submenu: [
                        { label: 'Background Color', submenu: [
                            { label: 'None', action: 'bg-none' },
                            { label: 'Light Gray', action: 'bg-lightgray' },
                            { label: 'Light Blue', action: 'bg-lightblue' },
                            { label: 'Light Green', action: 'bg-lightgreen' },
                            { label: 'Light Yellow', action: 'bg-lightyellow' }
                        ]},
                        { label: 'Border Style', submenu: [
                            { label: 'None', action: 'border-none' },
                            { label: 'Thin', action: 'border-thin' },
                            { label: 'Medium', action: 'border-medium' },
                            { label: 'Thick', action: 'border-thick' },
                            { label: 'Dashed', action: 'border-dashed' },
                            { label: 'Dotted', action: 'border-dotted' },
                            { label: 'Double', action: 'border-double' }
                        ]}
                    ]},
                    { label: 'Text Wrap', submenu: [
                        { label: 'Around', action: 'wrap-around' },
                        { label: 'None', action: 'wrap-none' }
                    ]},
                    { label: 'Alignment', submenu: [
                        { label: 'Left (Ctrl+L)', action: 'align-left' },
                        { label: 'Center (Ctrl+E)', action: 'align-center' },
                        { label: 'Right (Ctrl+R)', action: 'align-right' },
                        { label: 'None (Ctrl+J)', action: 'align-none' }
                    ]},
                    { type: 'separator' },
                    { label: 'Duplicate (Ctrl+D)', action: 'duplicate' },
                    { label: 'Delete', action: 'delete' }
                ];
                
                // Create menu items
                createMenuItems(contextMenu, menuItems);
                
                // Add to editor
                editor.appendChild(contextMenu);
                
                // Add click outside handler
                setTimeout(() => {
                    document.addEventListener('mousedown', handleContextMenuClickOutside);
                }, 0);
            }
            
            // Create menu items from configuration
            function createMenuItems(parent, items) {
                items.forEach(item => {
                    // Skip conditional items that fail their condition
                    if (item.condition && !item.condition()) {
                        return;
                    }
                    
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
                        menuItem.addEventListener('click', e => {
                            e.stopPropagation();
                            handleContextMenuAction(item.action);
                            removeContextMenu();
                        });
                        parent.appendChild(menuItem);
                    }
                });
            }
            
            // Handle context menu click outside
            function handleContextMenuClickOutside(e) {
                if (contextMenu && !contextMenu.contains(e.target)) {
                    removeContextMenu();
                }
            }
            
            // Remove context menu
            function removeContextMenu() {
                if (contextMenu) {
                    contextMenu.remove();
                    contextMenu = null;
                    document.removeEventListener('mousedown', handleContextMenuClickOutside);
                }
            }
            
            // Handle context menu actions
            function handleContextMenuAction(action) {
                if (!selectedTextBox) return;
                
                switch (action) {
                    case 'edit-text':
                        const content = selectedTextBox.querySelector('.textbox-content');
                        if (content) {
                            content.focus();
                            if (content.textContent === 'Enter text here...') {
                                // Select all when it's the placeholder text
                                const range = document.createRange();
                                range.selectNodeContents(content);
                                const selection = window.getSelection();
                                selection.removeAllRanges();
                                selection.addRange(range);
                            }
                        }
                        break;
                        
                    case 'edit-title':
                        const header = selectedTextBox.querySelector('.textbox-header');
                        if (header) {
                            header.focus();
                            if (header.textContent === 'Title') {
                                // Select all when it's the placeholder text
                                const range = document.createRange();
                                range.selectNodeContents(header);
                                const selection = window.getSelection();
                                selection.removeAllRanges();
                                selection.addRange(range);
                            }
                        }
                        break;
                        
                    case 'add-title':
                        const newHeader = document.createElement('div');
                        newHeader.className = 'textbox-header';
                        newHeader.contentEditable = true;
                        newHeader.textContent = 'Title';
                        
                        newHeader.addEventListener('mousedown', e => {
                            e.stopPropagation();
                            selectTextBox(selectedTextBox);
                            startDrag(e, selectedTextBox);
                        });
                        
                        newHeader.addEventListener('blur', () => {
                            if (newHeader.textContent.trim() === '') {
                                newHeader.textContent = 'Title';
                            }
                        });
                        
                        newHeader.addEventListener('focus', () => {
                            if (newHeader.textContent === 'Title') {
                                newHeader.textContent = '';
                            }
                        });
                        
                        selectedTextBox.insertBefore(newHeader, selectedTextBox.firstChild);
                        newHeader.focus();
                        break;
                        
                    case 'bg-none':
                        selectedTextBox.style.backgroundColor = 'transparent';
                        break;
                    case 'bg-lightgray':
                        selectedTextBox.style.backgroundColor = 'rgba(220, 220, 220, 0.7)';
                        break;
                    case 'bg-lightblue':
                        selectedTextBox.style.backgroundColor = 'rgba(173, 216, 230, 0.7)';
                        break;
                    case 'bg-lightgreen':
                        selectedTextBox.style.backgroundColor = 'rgba(144, 238, 144, 0.7)';
                        break;
                    case 'bg-lightyellow':
                        selectedTextBox.style.backgroundColor = 'rgba(255, 255, 224, 0.7)';
                        break;
                        
                    case 'border-none':
                        selectedTextBox.style.border = 'none';
                        break;
                    case 'border-thin':
                        selectedTextBox.style.border = '1px solid currentColor';
                        break;
                    case 'border-medium':
                        selectedTextBox.style.border = '2px solid currentColor';
                        break;
                    case 'border-thick':
                        selectedTextBox.style.border = '3px solid currentColor';
                        break;
                    case 'border-dashed':
                        selectedTextBox.style.border = '2px dashed currentColor';
                        break;
                    case 'border-dotted':
                        selectedTextBox.style.border = '2px dotted currentColor';
                        break;
                    case 'border-double':
                        selectedTextBox.style.border = '3px double currentColor';
                        break;
                        
                    case 'align-left':
                        setTextBoxAlignment(selectedTextBox, 'left');
                        break;
                    case 'align-center':
                        setTextBoxAlignment(selectedTextBox, 'center');
                        break;
                    case 'align-right':
                        setTextBoxAlignment(selectedTextBox, 'right');
                        break;
                    case 'align-none':
                        setTextBoxAlignment(selectedTextBox, 'none');
                        break;
                        
                    case 'wrap-around':
                        setTextWrap(selectedTextBox, 'around');
                        break;
                    case 'wrap-none':
                        setTextWrap(selectedTextBox, 'none');
                        break;
                        
                    case 'duplicate':
                        duplicateTextBox(selectedTextBox);
                        break;
                        
                    case 'delete':
                        deleteTextBox(selectedTextBox);
                        break;
                }
            }
            
            // Set textbox alignment
            function setTextBoxAlignment(textBox, alignment) {
                // Remove absolute positioning and reset positioning
                textBox.style.position = '';
                textBox.style.left = '';
                textBox.style.top = '';
                
                // Remove all alignment classes
                textBox.classList.remove('align-left', 'align-right', 'align-center', 'align-none');
                
                // Add the new alignment class
                textBox.classList.add(`align-${alignment}`);
                
                // Update resize handles
                updateResizeHandles();
            }
            
            // Set text wrap
            function setTextWrap(textBox, wrap) {
                // Remove any existing clear div
                const nextSibling = textBox.nextSibling;
                if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                    nextSibling.remove();
                }
                
                if (wrap === 'none') {
                    setTextBoxAlignment(textBox, 'none');
                    
                    // Add clear div after the textbox
                    const clearDiv = document.createElement('div');
                    clearDiv.className = 'text-wrap-none';
                    
                    if (textBox.nextSibling) {
                        textBox.parentNode.insertBefore(clearDiv, textBox.nextSibling);
                    } else {
                        textBox.parentNode.appendChild(clearDiv);
                    }
                } else if (wrap === 'around') {
                    // Default to left align if not already aligned
                    if (!textBox.classList.contains('align-left') && 
                        !textBox.classList.contains('align-right') && 
                        !textBox.classList.contains('align-center')) {
                        setTextBoxAlignment(textBox, 'left');
                    }
                }
            }
            
            // Duplicate textbox
            function duplicateTextBox(textBox) {
                // Clone the textbox
                const clone = textBox.cloneNode(true);
                
                // Set unique IDs for any elements that might have them
                const elementsWithId = clone.querySelectorAll('[id]');
                elementsWithId.forEach(el => {
                    el.id = el.id + '-clone-' + Date.now();
                });
                
                // Position slightly offset from original if absolute
                if (window.getComputedStyle(textBox).position === 'absolute') {
                    const left = parseInt(textBox.style.left) || 0;
                    const top = parseInt(textBox.style.top) || 0;
                    clone.style.left = (left + 20) + 'px';
                    clone.style.top = (top + 20) + 'px';
                }
                
                // Insert after original
                if (textBox.nextSibling) {
                    textBox.parentNode.insertBefore(clone, textBox.nextSibling);
                } else {
                    textBox.parentNode.appendChild(clone);
                }
                
                // Setup event handlers
                setupTextBoxEvents(clone);
                
                // Select the new textbox
                selectTextBox(clone);
                
                return clone;
            }
            
            // Delete textbox
            function deleteTextBox(textBox) {
                // Remove any clear div that follows
                const nextSibling = textBox.nextSibling;
                if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                    nextSibling.remove();
                }
                
                // Deselect before removing
                if (selectedTextBox === textBox) {
                    deselectTextBox();
                }
                
                // Remove the textbox
                textBox.remove();
            }
            
            // Expose createTextBox function to be called from Python
            window.createTextBox = function(withHeader = false) {
                return createTextBox(withHeader);
            };

            // Expose core functions for text wrap extension
            window.textboxAPI = {
                selectTextBox,
                deselectTextBox,
                createResizeHandles,
                removeResizeHandles,
                updateResizeHandles,
                showContextMenu,
                removeContextMenu,
                handleContextMenuAction,
                setTextBoxAlignment,
                setTextWrap,
                duplicateTextBox,
                deleteTextBox,
                startDrag,
                stopDrag,
                handleDrag,
                startResize,
                stopResize,
                handleResize,
                
                // State variables
                get selectedTextBox() { return selectedTextBox; },
                get isDragging() { return isDragging; },
                get isResizing() { return isResizing; }
            };
            
            // Update resize handles when window is resized or scrolled
            window.addEventListener('resize', updateResizeHandles);
            editor.addEventListener('scroll', updateResizeHandles);
            
            // Clean up event listeners when leaving the page
            window.addEventListener('beforeunload', () => {
                window.removeEventListener('resize', updateResizeHandles);
                editor.removeEventListener('scroll', updateResizeHandles);
            });
        })();
        """
        self.exec_js(base_script)
        
        # Now inject the advanced text wrapping functionality
        wrap_script = """
        (function() {
            // Wait for the base textbox functionality to be available
            function waitForTextboxAPI() {
                if (window.textboxAPI) {
                    enhanceTextWrapHandling();
                } else {
                    setTimeout(waitForTextboxAPI, 50);
                }
            }
            
            waitForTextboxAPI();
            
            function enhanceTextWrapHandling() {
                const editor = document.getElementById('editor');
                if (!editor) {
                    console.error('Editor element not found');
                    return;
                }

                // Get references to the textbox API functions
                const {
                    selectedTextBox, isDragging, isResizing,
                    showContextMenu: originalShowContextMenu,
                    handleContextMenuAction: originalHandleContextMenuAction,
                    startDrag: originalStartDrag,
                    stopDrag: originalStopDrag, 
                    duplicateTextBox: originalDuplicateTextBox
                } = window.textboxAPI;
                
                // Add enhanced CSS for text wrapping
                const wrapStyles = document.createElement('style');
                wrapStyles.textContent = `
                    /* Basic wrap modes */
                    .textbox {
                        /* Default style for all textboxes */
                        position: relative;
                        z-index: 1;
                    }
                    
                    /* Standard float-based wrapping */
                    .textbox.wrap-left {
                        float: left;
                        margin: 0 15px 10px 0;
                        clear: left;
                    }
                    
                    .textbox.wrap-right {
                        float: right;
                        margin: 0 0 10px 15px;
                        clear: right;
                    }
                    
                    /* Center with no wrapping */
                    .textbox.wrap-center {
                        display: block;
                        margin: 10px auto;
                        float: none;
                        clear: both;
                    }
                    
                    /* No wrapping at all */
                    .textbox.wrap-none {
                        float: none;
                        margin: 10px 0;
                        clear: both;
                        display: block;
                    }
                    
                    /* Tight wrapping with less margin */
                    .textbox.wrap-tight-left {
                        float: left;
                        margin: 0 5px 5px 0;
                        clear: left;
                    }
                    
                    .textbox.wrap-tight-right {
                        float: right;
                        margin: 0 0 5px 5px;
                        clear: right;
                    }
                    
                    /* Clear markers */
                    .wrap-clear {
                        clear: both;
                        display: block;
                        visibility: hidden;
                        height: 0;
                        font-size: 0;
                        line-height: 0;
                    }
                    
                    .wrap-clear-left {
                        clear: left;
                        display: block;
                        visibility: hidden;
                        height: 0;
                        font-size: 0;
                        line-height: 0;
                    }
                    
                    .wrap-clear-right {
                        clear: right;
                        display: block;
                        visibility: hidden;
                        height: 0;
                        font-size: 0;
                        line-height: 0;
                    }
                    
                    /* Visual indicators when in edit mode */
                    .editor-show-wrapping .textbox {
                        outline: 1px dashed rgba(0, 0, 255, 0.3);
                    }
                    
                    .editor-show-wrapping .textbox.wrap-left::before,
                    .editor-show-wrapping .textbox.wrap-tight-left::before {
                        content: "";
                        position: absolute;
                        left: -3px;
                        top: 0;
                        bottom: 0;
                        width: 3px;
                        background: linear-gradient(90deg, 
                            rgba(0, 100, 255, 0.5) 0%, 
                            rgba(0, 100, 255, 0) 100%);
                    }
                    
                    .editor-show-wrapping .textbox.wrap-right::before,
                    .editor-show-wrapping .textbox.wrap-tight-right::before {
                        content: "";
                        position: absolute;
                        right: -3px;
                        top: 0;
                        bottom: 0;
                        width: 3px;
                        background: linear-gradient(270deg, 
                            rgba(0, 100, 255, 0.5) 0%, 
                            rgba(0, 100, 255, 0) 100%);
                    }
                    
                    .editor-show-wrapping .textbox.wrap-tight-left::before,
                    .editor-show-wrapping .textbox.wrap-tight-right::before {
                        background-color: rgba(255, 165, 0, 0.5);
                    }
                    
                    .editor-show-wrapping .textbox.wrap-center::before {
                        content: "";
                        position: absolute;
                        left: 0;
                        right: 0;
                        top: -3px;
                        height: 3px;
                        background: linear-gradient(180deg, 
                            rgba(0, 100, 255, 0.5) 0%, 
                            rgba(0, 100, 255, 0) 100%);
                    }
                    
                    .editor-show-wrapping .textbox.wrap-none::before {
                        content: "";
                        position: absolute;
                        left: 0;
                        right: 0;
                        bottom: -3px;
                        height: 3px;
                        background: linear-gradient(0deg, 
                            rgba(255, 0, 0, 0.5) 0%, 
                            rgba(255, 0, 0, 0) 100%);
                    }
                    
                    /* Wrap preview overlay */
                    .wrap-preview {
                        position: absolute;
                        pointer-events: none;
                        z-index: 1000;
                        border-radius: 3px;
                        opacity: 0.2;
                        transition: opacity 0.2s;
                    }
                    
                    .wrap-preview.wrap-preview-left {
                        background-color: blue;
                    }
                    
                    .wrap-preview.wrap-preview-right {
                        background-color: green;
                    }
                    
                    .wrap-preview.wrap-preview-center,
                    .wrap-preview.wrap-preview-none {
                        background-color: red;
                    }
                    
                    .wrap-preview.wrap-preview-tight-left,
                    .wrap-preview.wrap-preview-tight-right {
                        background-color: orange;
                    }
                `;
                document.head.appendChild(wrapStyles);
                
                // Toggle to show wrap indicators
                let showWrapIndicators = false;
                
                // Function to toggle wrap indicators
                window.toggleWrapIndicators = function() {
                    showWrapIndicators = !showWrapIndicators;
                    if (showWrapIndicators) {
                        editor.classList.add('editor-show-wrapping');
                    } else {
                        editor.classList.remove('editor-show-wrapping');
                    }
                    return showWrapIndicators;
                };
                
                // Function to apply text wrap style to a textbox
                function applyTextWrap(textBox, wrapStyle) {
                    // Remove all existing wrap classes
                    textBox.classList.remove(
                        'wrap-left', 'wrap-right', 'wrap-center', 'wrap-none',
                        'wrap-tight-left', 'wrap-tight-right'
                    );
                    
                    // Remove any wrap-specific alignment classes
                    textBox.classList.remove(
                        'align-left', 'align-right', 'align-center', 'align-none'
                    );
                    
                    // If in absolute position, reset it
                    if (wrapStyle !== 'custom') {
                        textBox.style.position = '';
                        textBox.style.left = '';
                        textBox.style.top = '';
                    }
                    
                    // Remove any existing clear elements
                    const clearDiv = getAdjacentClearElement(textBox);
                    if (clearDiv) {
                        clearDiv.remove();
                    }
                    
                    // Apply the new wrap style
                    if (wrapStyle === 'left' || wrapStyle === 'right' || 
                        wrapStyle === 'center' || wrapStyle === 'none' ||
                        wrapStyle === 'tight-left' || wrapStyle === 'tight-right') {
                        
                        textBox.classList.add('wrap-' + wrapStyle);
                        
                        // Add corresponding clear element if needed
                        if (wrapStyle === 'none') {
                            addClearElement(textBox, 'both');
                        } else if (wrapStyle === 'left' || wrapStyle === 'tight-left') {
                            // For left floating elements, we may want to optionally add clear
                            // Only add if the element is the last in a series of left floats
                            const nextElement = textBox.nextElementSibling;
                            if (!nextElement || 
                                !nextElement.classList.contains('textbox') || 
                                !(nextElement.classList.contains('wrap-left') || 
                                  nextElement.classList.contains('wrap-tight-left'))) {
                                addClearElement(textBox, 'left');
                            }
                        } else if (wrapStyle === 'right' || wrapStyle === 'tight-right') {
                            // Same for right floating elements
                            const nextElement = textBox.nextElementSibling;
                            if (!nextElement || 
                                !nextElement.classList.contains('textbox') || 
                                !(nextElement.classList.contains('wrap-right') || 
                                  nextElement.classList.contains('wrap-tight-right'))) {
                                addClearElement(textBox, 'right');
                            }
                        }
                    } else if (wrapStyle === 'custom') {
                        // Custom positioning - this is handled by the dragging functionality
                        // We don't add any wrap classes, but ensure it's positioned absolutely
                        textBox.style.position = 'absolute';
                    }
                }
                
                // Helper function to get any existing clear element after a textbox
                function getAdjacentClearElement(textBox) {
                    const nextSibling = textBox.nextSibling;
                    if (nextSibling && 
                        nextSibling.nodeType === Node.ELEMENT_NODE && 
                        (nextSibling.classList.contains('wrap-clear') ||
                         nextSibling.classList.contains('wrap-clear-left') ||
                         nextSibling.classList.contains('wrap-clear-right'))) {
                        return nextSibling;
                    }
                    return null;
                }
                
                // Helper function to add a clear element after a textbox
                function addClearElement(textBox, clearType) {
                    const clearDiv = document.createElement('div');
                    clearDiv.className = clearType === 'both' ? 'wrap-clear' : 
                                        (clearType === 'left' ? 'wrap-clear-left' : 'wrap-clear-right');
                    
                    if (textBox.nextSibling) {
                        textBox.parentNode.insertBefore(clearDiv, textBox.nextSibling);
                    } else {
                        textBox.parentNode.appendChild(clearDiv);
                    }
                    return clearDiv;
                }
                
                // Override the original showContextMenu function
                window.textboxAPI.showContextMenu = function(x, y) {
                    const contextMenu = document.querySelector('.context-menu');
                    if (contextMenu) contextMenu.remove();
                    
                    if (!window.textboxAPI.selectedTextBox) return;
                    
                    const newContextMenu = document.createElement('div');
                    newContextMenu.className = 'context-menu';
                    
                    // Calculate position
                    const editorRect = editor.getBoundingClientRect();
                    const menuWidth = 180;
                    const menuHeightEstimate = 300;
                    
                    let adjustedX = Math.min(x, editorRect.right - menuWidth);
                    let adjustedY = Math.min(y, editorRect.bottom - menuHeightEstimate);
                    adjustedX = Math.max(adjustedX, editorRect.left);
                    adjustedY = Math.max(adjustedY, editorRect.top);
                    
                    newContextMenu.style.left = (adjustedX - editorRect.left + editor.scrollLeft) + 'px';
                    newContextMenu.style.top = (adjustedY - editorRect.top + editor.scrollTop) + 'px';
                    
                    // Define enhanced menu items with expanded text wrap submenu
                    const menuItems = [
                        { label: 'Edit Text', action: 'edit-text' },
                        { label: 'Edit Title', action: 'edit-title', condition: () => !!window.textboxAPI.selectedTextBox.querySelector('.textbox-header') },
                        { label: 'Add Title', action: 'add-title', condition: () => !window.textboxAPI.selectedTextBox.querySelector('.textbox-header') },
                        { type: 'separator' },
                        { label: 'Style', submenu: [
                            { label: 'Background Color', submenu: [
                                { label: 'None', action: 'bg-none' },
                                { label: 'Light Gray', action: 'bg-lightgray' },
                                { label: 'Light Blue', action: 'bg-lightblue' },
                                { label: 'Light Green', action: 'bg-lightgreen' },
                                { label: 'Light Yellow', action: 'bg-lightyellow' }
                            ]},
                            { label: 'Border Style', submenu: [
                                { label: 'None', action: 'border-none' },
                                { label: 'Thin', action: 'border-thin' },
                                { label: 'Medium', action: 'border-medium' },
                                { label: 'Thick', action: 'border-thick' },
                                { label: 'Dashed', action: 'border-dashed' },
                                { label: 'Dotted', action: 'border-dotted' },
                                { label: 'Double', action: 'border-double' }
                            ]}
                        ]},
                        { label: 'Text Wrap', submenu: [
                            { label: 'Left Standard', action: 'wrap-left' },
                            { label: 'Right Standard', action: 'wrap-right' },
                            { label: 'Left Tight', action: 'wrap-tight-left' },
                            { label: 'Right Tight', action: 'wrap-tight-right' },
                            { label: 'Center (No Wrap)', action: 'wrap-center' },
                            { label: 'No Wrap', action: 'wrap-none' },
                            { label: 'Custom Position', action: 'wrap-custom' },
                            { type: 'separator' },
                            { label: 'Show Wrap Indicators', action: 'wrap-show-indicators' }
                        ]},
                        { label: 'Alignment', submenu: [
                            { label: 'Left (Ctrl+L)', action: 'align-left' },
                            { label: 'Center (Ctrl+E)', action: 'align-center' },
                            { label: 'Right (Ctrl+R)', action: 'align-right' },
                            { label: 'None (Ctrl+J)', action: 'align-none' }
                        ]},
                        { type: 'separator' },
                        { label: 'Duplicate (Ctrl+D)', action: 'duplicate' },
                        { label: 'Delete', action: 'delete' }
                    ];
                    
                    // Create menu items using the original function
                    window.createMenuItems(newContextMenu, menuItems);
                    
                    // Add to editor
                    editor.appendChild(newContextMenu);
                    
                    // Add click outside handler
                    setTimeout(() => {
                        document.addEventListener('mousedown', handleContextMenuClickOutside);
                    }, 0);
                    
                    // Store in global context menu reference
                    window.contextMenu = newContextMenu;
                };
                
                function handleContextMenuClickOutside(e) {
                    if (window.contextMenu && !window.contextMenu.contains(e.target)) {
                        window.contextMenu.remove();
                        window.contextMenu = null;
                        document.removeEventListener('mousedown', handleContextMenuClickOutside);
                    }
                }
                
                // Override the original handleContextMenuAction function
                const originalHandleContextMenuAction = window.textboxAPI.handleContextMenuAction;
                
                window.textboxAPI.handleContextMenuAction = function(action) {
                    if (!window.textboxAPI.selectedTextBox) return;
                    
                    // Handle wrap-specific actions
                    if (action.startsWith('wrap-')) {
                        if (action === 'wrap-show-indicators') {
                            // Toggle wrap indicators
                            window.toggleWrapIndicators();
                        } else if (action === 'wrap-custom') {
                            // Make the textbox absolutely positioned for custom placement
                            const textBox = window.textboxAPI.selectedTextBox;
                            const rect = textBox.getBoundingClientRect();
                            const editorRect = editor.getBoundingClientRect();
                            
                            textBox.style.position = 'absolute';
                            textBox.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                            textBox.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                            
                            // Remove any wrap classes
                            textBox.classList.remove(
                                'wrap-left', 'wrap-right', 'wrap-center', 'wrap-none',
                                'wrap-tight-left', 'wrap-tight-right'
                            );
                            
                            // Remove any clear element
                            const clearDiv = getAdjacentClearElement(textBox);
                            if (clearDiv) {
                                clearDiv.remove();
                            }
                            
                            // Update resize handles
                            window.textboxAPI.updateResizeHandles();
                        } else {
                            // Apply the specified wrap style
                            const wrapStyle = action.replace('wrap-', '');
                            applyTextWrap(window.textboxAPI.selectedTextBox, wrapStyle);
                            window.textboxAPI.updateResizeHandles();
                        }
                        return;
                    }
                    
                    // For alignment actions, we want to apply appropriate wrap styles as well
                    if (action.startsWith('align-')) {
                        const alignment = action.replace('align-', '');
                        
                        // Map alignments to wrap styles
                        let wrapStyle;
                        switch (alignment) {
                            case 'left':
                                wrapStyle = 'left';
                                break;
                            case 'right':
                                wrapStyle = 'right';
                                break;
                            case 'center':
                                wrapStyle = 'center';
                                break;
                            case 'none':
                                wrapStyle = 'none';
                                break;
                            default:
                                wrapStyle = 'left'; // Default
                        }
                        
                        // Apply the wrap style along with the alignment
                        applyTextWrap(window.textboxAPI.selectedTextBox, wrapStyle);
                        
                        // Call the original alignment handler (modified to not interfere with our wrapping)
                        setTextBoxAlignment_WithoutWrapChange(window.textboxAPI.selectedTextBox, alignment);
                        return;
                    }
                    
                    // For all other actions, call the original handler
                    originalHandleContextMenuAction(action);
                };
                
                // Modified version of setTextBoxAlignment that doesn't touch wrapping
                function setTextBoxAlignment_WithoutWrapChange(textBox, alignment) {
                    // Add the alignment class but preserve wrapping classes
                    textBox.classList.remove('align-left', 'align-right', 'align-center', 'align-none');
                    textBox.classList.add(`align-${alignment}`);
                    window.textboxAPI.updateResizeHandles();
                }
                
                // Enhance the startDrag function to show wrap preview
                const originalStartDrag = window.textboxAPI.startDrag;
                
                window.textboxAPI.startDrag = function(e, textBox) {
                    // Clean up any existing preview
                    removeWrapPreview();
                    
                    // Save the original wrapping style so we can restore it if canceled
                    textBox.dataset.originalWrapStyle = Array.from(textBox.classList)
                        .filter(cls => cls.startsWith('wrap-'))
                        .join(' ');
                    
                    // Call the original startDrag
                    originalStartDrag(e, textBox);
                    
                    // When dragging starts, show wrap preview and change wrap mode to custom
                    if (textBox === window.textboxAPI.selectedTextBox) {
                        applyTextWrap(textBox, 'custom');
                    }
                };
                
                // Function to remove wrap preview overlay
                function removeWrapPreview() {
                    const preview = document.querySelector('.wrap-preview');
                    if (preview) {
                        preview.remove();
                    }
                }
                
                // Add drag end behavior
                const originalStopDrag = window.textboxAPI.stopDrag;
                
                window.textboxAPI.stopDrag = function() {
                    // Call original stop drag
                    originalStopDrag();
                    
                    // Clean up
                    removeWrapPreview();
                    
                    // If elements are now in absolute position, they're using custom wrapping
                    if (window.textboxAPI.selectedTextBox && 
                        window.textboxAPI.selectedTextBox.style.position === 'absolute') {
                        // Remove any legacy wrap classes that might remain
                        window.textboxAPI.selectedTextBox.classList.remove(
                            'wrap-left', 'wrap-right', 'wrap-center', 'wrap-none',
                            'wrap-tight-left', 'wrap-tight-right'
                        );
                    }
                };
                
                // Add visual indicators for textbox positions
                editor.addEventListener('mousemove', function(e) {
                    // Show position hints when element is being dragged
                    if (window.textboxAPI.isDragging && window.textboxAPI.selectedTextBox) {
                        const editorRect = editor.getBoundingClientRect();
                        const mouseX = e.clientX - editorRect.left + editor.scrollLeft;
                        const mouseY = e.clientY - editorRect.top + editor.scrollTop;
                        
                        // Add visual hints based on position
                        // Here we just highlight regions where special alignment would apply
                        const editorWidth = editor.clientWidth;
                        
                        // Determine where in the editor we are (left third, middle third, right third)
                        const zone = mouseX < editorWidth / 3 ? 'left' : 
                                   (mouseX > (editorWidth * 2) / 3 ? 'right' : 'center');
                        
                        // Update the dragged element's style to give a visual hint
                        // This is just for feedback - we'll apply the actual style on drop
                        
                        // Remove any existing preview
                        removeWrapPreview();
                        
                        // Show hint based on position and holding shift/alt
                        let previewType = 'custom';
                        
                        if (e.shiftKey) {
                            // Shift for tight wrapping
                            if (zone === 'left') previewType = 'tight-left';
                            else if (zone === 'right') previewType = 'tight-right';
                            else previewType = 'center';
                        } else if (e.altKey) {
                            // Alt for no wrapping
                            previewType = 'none';
                        } else {
                            // Normal wrapping
                            if (zone === 'left') previewType = 'left';
                            else if (zone === 'right') previewType = 'right';
                            else previewType = 'center';
                        }
                        
                        // Create preview overlay
                        if (previewType !== 'custom') {
                            const preview = document.createElement('div');
                            preview.className = `wrap-preview wrap-preview-${previewType}`;
                            
                            // Set the position and size based on the type
                            if (previewType === 'left' || previewType === 'tight-left') {
                                preview.style.left = '0';
                                preview.style.top = '0';
                                preview.style.width = editorWidth / 3 + 'px';
                                preview.style.height = '100%';
                            } else if (previewType === 'right' || previewType === 'tight-right') {
                                preview.style.right = '0';
                                preview.style.top = '0';
                                preview.style.width = editorWidth / 3 + 'px';
                                preview.style.height = '100%';
                            } else if (previewType === 'center') {
                                preview.style.left = editorWidth / 3 + 'px';
                                preview.style.top = '0';
                                preview.style.width = editorWidth / 3 + 'px';
                                preview.style.height = '100%';
                            } else if (previewType === 'none') {
                                preview.style.left = '0';
                                preview.style.top = '0';
                                preview.style.width = '100%';
                                preview.style.height = '100%';
                            }
                            
                            // Add to editor
                            editor.appendChild(preview);
                            
                            // Fade out after a moment
                            setTimeout(() => {
                                if (preview.parentNode) {
                                    preview.style.opacity = '0.1';
                                }
                            }, 500);
                        }
                    }
                });
                
                // Add key handler for preview styles
                editor.addEventListener('keydown', function(e) {
                    if (window.textboxAPI.isDragging && window.textboxAPI.selectedTextBox) {
                        // Force preview update when modifier keys are pressed or released
                        const evt = new MouseEvent('mousemove', {
                            clientX: e.clientX,
                            clientY: e.clientY,
                            bubbles: true,
                            cancelable: true,
                            shiftKey: e.shiftKey,
                            altKey: e.altKey,
                            ctrlKey: e.ctrlKey
                        });
                        
                        editor.dispatchEvent(evt);
                    }
                });
                
                // Add drop behavior to apply wrap style
                editor.addEventListener('mouseup', function(e) {
                    if (window.textboxAPI.isDragging && window.textboxAPI.selectedTextBox) {
                        // Check what kind of wrapping to apply based on drop position
                        const editorRect = editor.getBoundingClientRect();
                        const mouseX = e.clientX - editorRect.left + editor.scrollLeft;
                        
                        // Get editor dimensions
                        const editorWidth = editor.clientWidth;
                        
                        // Determine where in the editor we are (left third, middle third, right third)
                        const zone = mouseX < editorWidth / 3 ? 'left' : 
                                   (mouseX > (editorWidth * 2) / 3 ? 'right' : 'center');
                        
                        // Apply wrapping based on position and modifier keys
                        let wrapStyle;
                        
                        if (e.shiftKey) {
                            // Shift for tight wrapping
                            if (zone === 'left') wrapStyle = 'tight-left';
                            else if (zone === 'right') wrapStyle = 'tight-right';
                            else wrapStyle = 'center';
                        } else if (e.altKey) {
                            // Alt for no wrapping
                            wrapStyle = 'none';
                        } else {
                            // Normal wrapping
                            if (zone === 'left') wrapStyle = 'left';
                            else if (zone === 'right') wrapStyle = 'right';
                            else wrapStyle = 'center';
                        }
                        
                        // If Ctrl is pressed, keep the custom positioning
                        if (e.ctrlKey) {
                            wrapStyle = 'custom';
                        }
                        
                        // Apply the wrap style
                        applyTextWrap(window.textboxAPI.selectedTextBox, wrapStyle);
                        window.textboxAPI.updateResizeHandles();
                    }
                });
                
                // Override duplicate to preserve wrapping style
                const originalDuplicateTextBox = window.textboxAPI.duplicateTextBox;
                
                window.textboxAPI.duplicateTextBox = function(textBox) {
                    const clone = originalDuplicateTextBox(textBox);
                    
                    // Copy wrap classes
                    const wrapClasses = Array.from(textBox.classList)
                        .filter(cls => cls.startsWith('wrap-'));
                        
                    if (wrapClasses.length > 0) {
                        // If the original had absolute positioning, the clone should maintain similar wrapping
                        if (window.getComputedStyle(textBox).position === 'absolute') {
                            applyTextWrap(clone, 'custom');
                        } else {
                            // Otherwise copy the wrap classes
                            wrapClasses.forEach(cls => {
                                clone.classList.add(cls);
                            });
                            
                            // Add appropriate clear element if needed
                            if (clone.classList.contains('wrap-none')) {
                                addClearElement(clone, 'both');
                            } else if (clone.classList.contains('wrap-left') || 
                                       clone.classList.contains('wrap-tight-left')) {
                                addClearElement(clone, 'left');
                            } else if (clone.classList.contains('wrap-right') || 
                                       clone.classList.contains('wrap-tight-right')) {
                                addClearElement(clone, 'right');
                            }
                        }
                    }
                    
                    return clone;
                };
                
                // Initialize existing textboxes
                editor.querySelectorAll('.textbox').forEach(textBox => {
                    // Apply default wrapping if none exists
                    if (!Array.from(textBox.classList).some(cls => cls.startsWith('wrap-'))) {
                        applyTextWrap(textBox, 'left');
                    }
                });
                
                // Add help info for users
                console.log('Text wrapping enhancement loaded:');
                console.log('- Drag textboxes to different areas for auto-wrapping');
                console.log('- Hold Shift while dragging for tight margins');
                console.log('- Hold Alt while dragging for no wrapping');
                console.log('- Hold Ctrl while dragging to maintain custom positioning');
            }
        })();
        """
        self.exec_js(wrap_script)
        
        # Define class-level method to add button for header
        def on_insert_textbox_clicked(self, btn):
            """Handle click on the Insert Text Box button"""
            self.exec_js("window.createTextBox(false);")
        
        def on_insert_textbox_with_header_clicked(self, btn):
            """Handle click on the Insert Text Box with Header button"""
            self.exec_js("window.createTextBox(true);")
            
        # Optionally, add a method to toggle wrap indicators (you could connect this to a menu item)
        def on_toggle_wrap_indicators(self, action=None, parameter=None):
            """Toggle the display of text wrap indicators"""
            self.exec_js("window.toggleWrapIndicators();")
        
        # When initializing the app, you could add a button for textbox with header:
        # textbox_with_header_btn = Gtk.Button(icon_name="insert-text-symbolic") 
        # textbox_with_header_btn.add_css_class("flat")
        # textbox_with_header_btn.set_tooltip_text("Insert Text Box with Title")
        # textbox_with_header_btn.connect("clicked", self.on_insert_textbox_with_header_clicked)
        # text_format_group.append(textbox_with_header_btn)
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
