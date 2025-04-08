#!/usr/bin/env python3

import base64
import mimetypes
import os
import gi
import json
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

        # State tracking (unchanged)
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
        
        # Document state (unchanged)
        self.current_file = None
        self.is_new = True
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()

        # CSS Provider (unchanged)
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

        # Main layout (unchanged)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.webview = WebKit.WebView(editable=True)
        settings = self.webview.get_settings()
        settings.set_property('enable-javascript', True)
        settings.set_property('javascript-can-open-windows-automatically', True)
        
        user_content = self.webview.get_user_content_manager()
        user_content.register_script_message_handler('contentChanged')
        user_content.connect('script-message-received::contentChanged', self.on_content_changed_js)
        user_content.register_script_message_handler('selectionChanged')
        user_content.connect('script-message-received::selectionChanged', self.on_selection_changed)
        self.webview.connect('load-changed', self.on_webview_load)

        # Initial HTML (unchanged)
        self.initial_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
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
            img.selected { outline-color: #5e97f6; box-shadow: 0 0 10px rgba(94, 151, 246, 0.5); }
            .context-menu { background-color: #333; border-color: #555; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5); }
            .context-menu-item:hover { background-color: #444; }
            .context-menu-separator { background-color: #555; }
            .context-menu-submenu-content { background-color: #333; border-color: #555; }
            .textbox { border: 1px dotted #aaa; background-color: #2a2a2a; }
            .textbox.selected { outline: 2px dotted #5e97f6; box-shadow: 0 0 10px rgba(94, 151, 246, 0.5); }
        }
        
        @media (prefers-color-scheme: light) {
            body { background-color: #ffffff; color: #000000; }
            img.selected { outline: 2px solid #4285f4; box-shadow: 0 0 10px rgba(66, 133, 244, 0.5); }
            .context-menu { background-color: white; border-color: #ccc; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2); }
            .context-menu-item:hover { background-color: #f0f0f0; }
            .context-menu-separator { background-color: #e0e0e0; }
            .context-menu-submenu-content { background-color: white; border-color: #ccc; }
            .textbox { border: 1px dotted #666; background-color: #f8f8f8; }
            .textbox.selected { outline: 2px dotted #4285f4; box-shadow: 0 0 10px rgba(66, 133, 244, 0.5); }
        }

        #editor {
            outline: none;
            margin: 0;
            padding: 20px;
            min-height: 1000px;
            overflow-y: auto;
        }

        img {
            display: inline-block;
            max-width: 50%;
            cursor: move;
            transition: outline 0.1s ease;
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

        .textbox {
            display: inline-block;
            padding: 5px;
            min-width: 100px;
            min-height: 20px;
            cursor: move;
            position: relative;
            margin: 10px 0;
        }

        .textbox[contenteditable="true"] {
            cursor: text;
            outline: none;
            box-shadow: none;
        }

        .textbox p {
            margin: 0;
        }

        .align-left {
            float: left;
            margin: 0 15px 10px 0;
        }

        .align-right {
            float: right;
            margin: 0 0 10px 15px;
        }

        .align-center {
            display: block;
            margin: 10px auto;
            float: none;
        }

        .align-none {
            float: none;
            margin: 10px 0;
        }

        .text-wrap-none {
            clear: both;
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
    </style>
</head>
<body>
    <div id="editor" contenteditable="true"><p>​</p></div>
</body>
</html>
"""
        # Main layout (unchanged)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)
        header = Adw.HeaderBar()
        header.add_css_class("flat-header")
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        toolbar_view.add_top_bar(header)

        # Toolbar groups (unchanged)
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

        # Toolbar buttons (unchanged)
        image_btn = Gtk.Button(icon_name="insert-image-symbolic")
        image_btn.add_css_class("flat")
        image_btn.set_tooltip_text("Insert Image")
        image_btn.connect("clicked", self.on_insert_image_clicked)
        text_format_group.append(image_btn)

        text_box_btn = Gtk.Button(icon_name="insert-text-symbolic")
        text_box_btn.add_css_class("flat")
        text_box_btn.set_tooltip_text("Insert Text Box")
        text_box_btn.connect("clicked", self.on_insert_text_box_clicked)
        text_format_group.append(text_box_btn)

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

        # Populate toolbar groups (unchanged)
        for icon, handler in [
            ("document-new", self.on_new_clicked),
            ("document-open", self.on_open_clicked),
            ("document-save", self.on_save_clicked),
            ("document-save-as", self.on_save_as_clicked),
            ("document-print", self.on_print_clicked),
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

        self.size_range = [str(size) for size in [6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72, 96]]
        size_store = Gtk.StringList(strings=self.size_range)
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(5)  # Default to 12pt
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

    def on_insert_text_box_clicked(self, btn):
        """Insert a textbox, make it editable, and select its content."""
        script = """
        (function() {
            const selection = window.getSelection();
            if (selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                let textbox = document.createElement('div');
                textbox.contentEditable = true;  // Editable on insertion
                textbox.className = 'textbox';
                textbox.innerHTML = '<p>Type here...</p>';
                textbox.draggable = true;
                
                range.insertNode(textbox);
                
                textbox.focus();
                const p = textbox.querySelector('p');
                if (p) {
                    const range = document.createRange();
                    range.selectNodeContents(p);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                }
                
                window.webkit.messageHandlers.contentChanged.postMessage('changed');
            }
        })();
        """
        self.exec_js(script)
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
                self.exec_js(f"window.insertAndSelectImage('{data_url_escaped}')")
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
            script = """
            (function() {
                const editor = document.getElementById('editor');
                if (!editor) {
                    console.error('Editor element not found');
                    return;
                }

                let p = editor.querySelector('p');
                if (p) {
                    let range = document.createRange();
                    range.setStart(p, 0);
                    range.setEnd(p, 0);
                    let sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                }

                let selectedElement = null;
                let resizeHandles = [];
                let isDragging = false;
                let isResizing = false;
                let lastX, lastY;
                let resizeStartWidth, resizeStartHeight;
                let currentResizeHandle = null;
                let contextMenu = null;

                function isSelectableElement(el) {
                    return el.tagName === 'IMG' || el.classList.contains('textbox');
                }

                function createResizeHandles(element) {
                    removeResizeHandles();
                    const container = document.createElement('div');
                    container.style.position = 'absolute';
                    container.style.left = element.offsetLeft + 'px';
                    container.style.top = element.offsetTop + 'px';
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

                function removeResizeHandles() {
                    const container = editor.querySelector('.resize-container');
                    if (container) container.remove();
                    resizeHandles = [];
                }

                function updateResizeHandles() {
                    if (!selectedElement) return;
                    const container = editor.querySelector('.resize-container');
                    if (container) {
                        const rect = selectedElement.getBoundingClientRect();
                        const editorRect = editor.getBoundingClientRect();
                        container.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                        container.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                        container.style.width = selectedElement.offsetWidth + 'px';
                        container.style.height = selectedElement.offsetHeight + 'px';
                    }
                }

                function startResize(e, handle) {
                    if (!selectedElement) return;
                    isResizing = true;
                    currentResizeHandle = handle;
                    lastX = e.clientX;
                    lastY = e.clientY;
                    resizeStartWidth = selectedElement.offsetWidth;
                    resizeStartHeight = selectedElement.offsetHeight;
                    selectedElement.classList.add('resizing');
                    document.addEventListener('mousemove', handleResize);
                    document.addEventListener('mouseup', stopResize);
                }

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
                    newWidth = Math.max(20, newWidth);
                    newHeight = Math.max(20, newHeight);
                    selectedElement.style.width = newWidth + 'px';
                    selectedElement.style.height = newHeight + 'px';
                    updateResizeHandles();
                }

                function stopResize() {
                    isResizing = false;
                    currentResizeHandle = null;
                    if (selectedElement) selectedElement.classList.remove('resizing');
                    document.removeEventListener('mousemove', handleResize);
                    document.removeEventListener('mouseup', stopResize);
                }

                function startDrag(e, element) {
                    if (isResizing) return;
                    isDragging = true;
                    lastX = e.clientX;
                    lastY = e.clientY;
                    document.addEventListener('mousemove', handleDrag);
                    document.addEventListener('mouseup', stopDrag);
                }

                function handleDrag(e) {
                    if (!isDragging || !selectedElement) return;
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

                function stopDrag() {
                    isDragging = false;
                    document.removeEventListener('mousemove', handleDrag);
                    document.removeEventListener('mouseup', stopDrag);
                }

                function selectElement(element) {
                    if (selectedElement) selectedElement.classList.remove('selected');
                    selectedElement = element;
                    selectedElement.classList.add('selected');
                    if (element.classList.contains('textbox')) {
                        createResizeHandles(element);
                    } else {
                        removeResizeHandles();
                    }
                }

                function deselectElement() {
                    if (selectedElement) {
                        selectedElement.classList.remove('selected');
                        selectedElement = null;
                    }
                    removeResizeHandles();
                }

                function createContextMenu(x, y) {
                    removeContextMenu();
                    contextMenu = document.createElement('div');
                    contextMenu.className = 'context-menu';
                    const editorRect = editor.getBoundingClientRect();
                    const menuWidth = 150;
                    const menuHeightEstimate = 200;
                    let adjustedX = Math.min(x, editorRect.right - menuWidth);
                    let adjustedY = Math.min(y, editorRect.bottom - menuHeightEstimate);
                    adjustedX = Math.max(adjustedX, editorRect.left);
                    adjustedY = Math.max(adjustedY, editorRect.top);
                    contextMenu.style.left = adjustedX + 'px';
                    contextMenu.style.top = adjustedY + 'px';
                    
                    let menuItems = [];
                    const borderStyles = [
                        { label: 'None', action: 'border-none' },
                        { label: 'Solid', action: 'border-solid' },
                        { label: 'Dotted', action: 'border-dotted' },
                        { label: 'Dashed', action: 'border-dashed' },
                        { label: 'Double', action: 'border-double' }
                    ];
                    if (selectedElement.tagName === 'IMG') {
                        menuItems = [
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
                            { label: 'Border Style', submenu: borderStyles },
                            { type: 'separator' },
                            { label: 'Copy Image', action: 'copy' },
                            { label: 'Delete Image', action: 'delete' }
                        ];
                    } else if (selectedElement.classList.contains('textbox')) {
                        menuItems = [
                            { label: 'Edit Textbox', action: 'edit' },
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
                            { label: 'Border Style', submenu: borderStyles },
                            { type: 'separator' },
                            { label: 'Delete Textbox', action: 'delete' }
                        ];
                    }
                    createMenuItems(contextMenu, menuItems);
                    document.body.appendChild(contextMenu);
                    setTimeout(() => {
                        document.addEventListener('click', closeContextMenuOnClickOutside);
                    }, 0);
                }

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

                function handleContextMenuAction(action) {
                    if (!selectedElement) return;
                    switch (action) {
                        case 'edit':
                            if (selectedElement.classList.contains('textbox')) {
                                selectedElement.contentEditable = true;
                                selectedElement.focus();
                                const p = selectedElement.querySelector('p');
                                if (p) {
                                    const range = document.createRange();
                                    range.selectNodeContents(p);
                                    const sel = window.getSelection();
                                    sel.removeAllRanges();
                                    sel.addRange(range);
                                }
                            }
                            break;
                        case 'align-left':
                            setElementAlignment(selectedElement, 'left');
                            break;
                        case 'align-center':
                            setElementAlignment(selectedElement, 'center');
                            break;
                        case 'align-right':
                            setElementAlignment(selectedElement, 'right');
                            break;
                        case 'align-none':
                            setElementAlignment(selectedElement, 'none');
                            break;
                        case 'wrap-around':
                            setTextWrap(selectedElement, 'around');
                            break;
                        case 'wrap-none':
                            setTextWrap(selectedElement, 'none');
                            break;
                        case 'border-none':
                            selectedElement.style.border = 'none';
                            break;
                        case 'border-solid':
                            selectedElement.style.border = '1px solid currentColor';
                            break;
                        case 'border-dotted':
                            selectedElement.style.border = '1px dotted currentColor';
                            break;
                        case 'border-dashed':
                            selectedElement.style.border = '1px dashed currentColor';
                            break;
                        case 'border-double':
                            selectedElement.style.border = '3px double currentColor';
                            break;
                        case 'copy':
                            if (selectedElement.tagName === 'IMG') {
                                copyImageToClipboard(selectedElement);
                            }
                            break;
                        case 'delete':
                            deleteElement(selectedElement);
                            break;
                    }
                }

                function setElementAlignment(element, alignment) {
                    element.classList.remove('align-left', 'align-right', 'align-center', 'align-none');
                    element.classList.add(`align-${alignment}`);
                    updateResizeHandles();
                }

                function setTextWrap(element, wrap) {
                    if (wrap === 'none') {
                        element.style.float = 'none';
                        const clearDiv = document.createElement('div');
                        clearDiv.className = 'text-wrap-none';
                        clearDiv.style.clear = 'both';
                        if (element.nextSibling) {
                            element.parentNode.insertBefore(clearDiv, element.nextSibling);
                        } else {
                            element.parentNode.appendChild(clearDiv);
                        }
                    } else if (wrap === 'around') {
                        if (!element.classList.contains('align-left') && !element.classList.contains('align-right')) {
                            setElementAlignment(element, 'left');
                        }
                        const nextSibling = element.nextSibling;
                        if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                            nextSibling.remove();
                        }
                    }
                }

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

                function deleteElement(element) {
                    const nextSibling = element.nextSibling;
                    if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                        nextSibling.remove();
                    }
                    deselectElement();
                    element.remove();
                }

                function removeContextMenu() {
                    if (contextMenu) {
                        document.removeEventListener('click', closeContextMenuOnClickOutside);
                        contextMenu.remove();
                        contextMenu = null;
                    }
                }

                function closeContextMenuOnClickOutside(e) {
                    if (contextMenu && !contextMenu.contains(e.target)) {
                        removeContextMenu();
                    }
                }

                editor.addEventListener('click', (e) => {
                    removeContextMenu();
                    let target = e.target;
                    while (target && target !== editor && !isSelectableElement(target)) {
                        target = target.parentElement;
                    }
                    if (target && isSelectableElement(target)) {
                        e.preventDefault();
                        selectElement(target);
                    } else {
                        deselectElement();
                    }
                });

                editor.addEventListener('contextmenu', (e) => {
                    let target = e.target;
                    while (target && target !== editor && !isSelectableElement(target)) {
                        target = target.parentElement;
                    }
                    if (target && isSelectableElement(target)) {
                        e.preventDefault();
                        selectElement(target);
                        createContextMenu(e.clientX, e.clientY);
                    }
                });

                editor.addEventListener('mousedown', (e) => {
                    let target = e.target;
                    while (target && target !== editor && !isSelectableElement(target)) {
                        target = target.parentElement;
                    }
                    if (target && isSelectableElement(target) && e.button === 0) {
                        e.preventDefault();
                        if (selectedElement !== target) {
                            selectElement(target);
                        }
                        startDrag(e, target);
                    }
                });

                function handleTextboxEvents(textbox) {
                    textbox.addEventListener('dblclick', (e) => {
                        if (selectedElement === textbox) {
                            textbox.contentEditable = true;
                            textbox.focus();
                            removeResizeHandles();
                            const range = document.createRange();
                            range.selectNodeContents(textbox);
                            range.collapse(false);
                            const sel = window.getSelection();
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }
                    });

                    textbox.addEventListener('blur', () => {
                        textbox.contentEditable = false;
                        if (selectedElement === textbox) {
                            createResizeHandles(textbox);
                        }
                    });

                    textbox.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            textbox.contentEditable = false;
                            if (selectedElement === textbox) {
                                createResizeHandles(textbox);
                            }
                        }
                    });
                }

                editor.querySelectorAll('img, .textbox').forEach(el => {
                    el.contentEditable = false;
                    el.draggable = true;
                    if (el.classList.contains('textbox')) {
                        handleTextboxEvents(el);
                    }
                });

                const observer = new MutationObserver(mutations => {
                    mutations.forEach(mutation => {
                        mutation.addedNodes.forEach(node => {
                            if (isSelectableElement(node)) {
                                node.contentEditable = false;
                                node.draggable = true;
                                if (node.classList.contains('textbox')) {
                                    handleTextboxEvents(node);
                                }
                            }
                        });
                    });
                });
                observer.observe(editor, { childList: true, subtree: true });

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
                            strikethrough: document.queryCommandState('strikethrough'),
                            insertUnorderedList: document.queryCommandState('insertUnorderedList'),
                            insertOrderedList: document.queryCommandState('insertOrderedList'),
                            justifyLeft: document.queryCommandState('justifyLeft'),
                            justifyCenter: document.queryCommandState('justifyCenter'),
                            justifyRight: document.queryCommandState('justifyRight'),
                            justifyFull: document.queryCommandState('justifyFull'),
                            formatBlock: document.queryCommandValue('formatBlock'),
                            fontName: style.fontFamily,
                            fontSize: style.fontSize
                        };
                        window.webkit.messageHandlers.selectionChanged.postMessage(JSON.stringify(state));
                    }
                }, 100);

                document.addEventListener('selectionchange', notifySelectionChange);
                notifySelectionChange();

                window.insertAndSelectImage = function(src) {
                    document.execCommand('insertHTML', false, '<img src="' + src + '">');
                    const images = editor.querySelectorAll('img');
                    const lastImage = images[images.length - 1];
                    if (lastImage) {
                        lastImage.contentEditable = false;
                        lastImage.draggable = true;
                        selectElement(lastImage);
                        setElementAlignment(lastImage, 'left');
                        setTextWrap(lastImage, 'around');
                    }
                };

                window.insertAndSelectTextbox = function() {
                    const textbox = document.createElement('div');
                    textbox.className = 'textbox';
                    textbox.contentEditable = true;
                    textbox.draggable = true;
                    textbox.innerHTML = '<p>Type here...</p>';
                    document.execCommand('insertHTML', false, textbox.outerHTML);
                    const textboxes = editor.querySelectorAll('.textbox');
                    const lastTextbox = textboxes[textboxes.length - 1];
                    if (lastTextbox) {
                        handleTextboxEvents(lastTextbox);
                        lastTextbox.focus();
                        const p = lastTextbox.querySelector('p');
                        if (p) {
                            const range = document.createRange();
                            range.selectNodeContents(p);
                            const sel = window.getSelection();
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }
                    }
                };
            })();
            """
            self.webview.evaluate_javascript(script, -1, None, None, None, None, None)
            GLib.idle_add(self.webview.grab_focus)

    # Remaining methods (unchanged)
    def on_selection_changed(self, user_content, message):
        if message.is_string():
            state_str = message.to_string()
            state = json.loads(state_str)
            self.update_formatting_ui(state)
        else:
            print("Error: Expected a string message, got something else")

    def update_formatting_ui(self, state=None):
        if state:
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

            self.bullet_btn.handler_block_by_func(self.on_bullet_list_toggled)
            self.bullet_btn.set_active(state.get('insertUnorderedList', False))
            self.bullet_btn.handler_unblock_by_func(self.on_bullet_list_toggled)

            self.number_btn.handler_block_by_func(self.on_number_list_toggled)
            self.number_btn.set_active(state.get('insertOrderedList', False))
            self.number_btn.handler_unblock_by_func(self.on_number_list_toggled)

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

            format_block = state.get('formatBlock', 'p').lower()
            headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
            index = 0 if format_block not in headings else headings.index(format_block)
            self.heading_dropdown.handler_block(self.heading_dropdown_handler)
            self.heading_dropdown.set_selected(index)
            self.heading_dropdown.handler_unblock(self.heading_dropdown_handler)

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

            font_size_str = state.get('fontSize', '12pt')
            if font_size_str.endswith('px'):
                font_size_pt = str(int(float(font_size_str[:-2]) / 1.333))
            elif font_size_str.endswith('pt'):
                font_size_pt = font_size_str[:-2]
            else:
                font_size_pt = '12'
            size_store = self.size_dropdown.get_model()
            available_sizes = [size_store.get_string(i) for i in range(size_store.get_n_items())]
            selected_size_index = 5  # Default to 12pt
            if font_size_pt in available_sizes:
                selected_size_index = available_sizes.index(font_size_pt)
            self.current_font_size = available_sizes[selected_size_index]
            self.size_dropdown.handler_block(self.size_dropdown_handler)
            self.size_dropdown.set_selected(selected_size_index)
            self.size_dropdown.handler_unblock(self.size_dropdown_handler)
        else:
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
            selected_size_index = 5  # Default to 12
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
        self.webview.paste()


    def on_print_clicked(self, btn):
        print_operation = WebKit.PrintOperation.new(self.webview)
        print_operation.run_dialog(self)

    def on_text_received(self, clipboard, result, user_data):
        try:
            text = clipboard.read_text_finish(result)
            if text:
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
                self.heading_dropdown.set_selected(0)
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_1:
                self.heading_dropdown.set_selected(1)
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_2:
                self.heading_dropdown.set_selected(2)
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_3:
                self.heading_dropdown.set_selected(3)
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_4:
                self.heading_dropdown.set_selected(4)
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_5:
                self.heading_dropdown.set_selected(5)
                self.on_heading_changed(self.heading_dropdown)
                return True
            elif keyval == Gdk.KEY_6:
                self.heading_dropdown.set_selected(6)
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
                if result and hasattr(result, 'get_js_value'):
                    bold_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    bold_state = not self.is_bold if hasattr(self, 'is_bold') else btn.get_active()
                self.is_bold = bold_state
                self.bold_btn.handler_block_by_func(self.on_bold_toggled)
                self.bold_btn.set_active(self.is_bold)
                self.bold_btn.handler_unblock_by_func(self.on_bold_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in bold state callback: {e}")
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
                if result and hasattr(result, 'get_js_value'):
                    italic_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    italic_state = not self.is_italic if hasattr(self, 'is_italic') else btn.get_active()
                self.is_italic = italic_state
                self.italic_btn.handler_block_by_func(self.on_italic_toggled)
                self.italic_btn.set_active(self.is_italic)
                self.italic_btn.handler_unblock_by_func(self.on_italic_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in italic state callback: {e}")
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
                if result and hasattr(result, 'get_js_value'):
                    underline_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    underline_state = not self.is_underline if hasattr(self, 'is_underline') else btn.get_active()
                self.is_underline = underline_state
                self.underline_btn.handler_block_by_func(self.on_underline_toggled)
                self.underline_btn.set_active(self.is_underline)
                self.underline_btn.handler_unblock_by_func(self.on_underline_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in underline state callback: {e}")
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
                if result and hasattr(result, 'get_js_value'):
                    strikethrough_state = webview.evaluate_javascript_finish(result).to_boolean()
                else:
                    strikethrough_state = not self.is_strikethrough if hasattr(self, 'is_strikethrough') else btn.get_active()
                self.is_strikethrough = strikethrough_state
                self.strikethrough_btn.handler_block_by_func(self.on_strikethrough_toggled)
                self.strikethrough_btn.set_active(self.is_strikethrough)
                self.strikethrough_btn.handler_unblock_by_func(self.on_strikethrough_toggled)
                self.webview.grab_focus()
            except Exception as e:
                print(f"Error in strikethrough state callback: {e}")
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
                if result:
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
                if result:
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
                    let webkitSize;
                    if ({size_pt} <= 9) webkitSize = '1';
                    else if ({size_pt} <= 11) webkitSize = '2';
                    else if ({size_pt} <= 14) webkitSize = '3';
                    else if ({size_pt} <= 18) webkitSize = '4';
                    else if ({size_pt} <= 24) webkitSize = '5';
                    else if ({size_pt} <= 36) webkitSize = '6';
                    else webkitSize = '7';
                    if (range.collapsed) {{
                        document.execCommand('removeFormat', false, null);
                        document.execCommand('fontSize', false, webkitSize);
                        let font = selection.focusNode.parentElement;
                        if (!font || font.tagName !== 'FONT' || font.getAttribute('size') !== webkitSize || font.style.fontSize !== '{size_pt}pt') {{
                            font = document.createElement('font');
                            font.setAttribute('size', webkitSize);
                            font.style.fontSize = '{size_pt}pt';
                            range.insertNode(font);
                        }}
                        const zwsp = document.createTextNode('\u200B');
                        font.appendChild(zwsp);
                        range.setStartAfter(zwsp);
                        range.setEndAfter(zwsp);
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }} else {{
                        document.execCommand('fontSize', false, webkitSize);
                        const fonts = document.querySelectorAll('font[size="' + webkitSize + '"]');
                        fonts.forEach(font => {{
                            if (!font.style.fontSize) {{
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
                if result:
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
                if result:
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
                if result:
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
                if result:
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
