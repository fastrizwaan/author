#!/usr/bin/env python3

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
        self.current_line_spacing = "1.5"
        self.search_matches = []
        self.current_search_match = 0
        
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
            .toolbar-container { padding: 6px; background-color: rgba(127, 127, 127, 0.05); }
            .flat { background: none; }
            .flat:hover, .flat:checked { background: rgba(127, 127, 127, 0.25); }
            colorbutton.flat, colorbutton.flat button { background: none; }
            colorbutton.flat:hover, colorbutton.flat button:hover { background: rgba(127, 127, 127, 0.25); }
            dropdown.flat, dropdown.flat button { background: none; border-radius: 5px; }
            dropdown.flat:hover { background: rgba(127, 127, 127, 0.25); }
            .flat-header { background: rgba(127, 127, 127, 0.05); border: none; box-shadow: none; padding: 0; }
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

        self.initial_html = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: serif; font-size: 12pt; margin: 20px; line-height: 1.5; }
        @media (prefers-color-scheme: dark) { body { background-color: #121212; color: #e0e0e0; } }
        @media (prefers-color-scheme: light) { body { background-color: #ffffff; color: #000000; } }
    </style>
</head>
<body><p></p></body>
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
            ("edit-redo", self.on_redo_clicked),
            ("edit-find", self.on_search_clicked),  # Search icon
            ("edit-find-replace", self.on_replace_clicked),  # Replace icon
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

        self.size_map = {
            "6": "1", "8": "1", "10": "2", "12": "3", "14": "3",
            "16": "4", "18": "4", "24": "5", "36": "6"
        }
        size_store = Gtk.StringList(strings=list(self.size_map.keys()))
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(3)  # Default to 12
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

        line_spacing_options = ["1.0", "1.15", "1.5", "2.0", "2.5", "3.0"]
        line_spacing_store = Gtk.StringList(strings=line_spacing_options)
        self.line_spacing_dropdown = Gtk.DropDown(model=line_spacing_store)
        self.line_spacing_dropdown.set_selected(2)  # Default to 1.5
        self.line_spacing_handler = self.line_spacing_dropdown.connect("notify::selected", self.on_line_spacing_changed)
        self.line_spacing_dropdown.add_css_class("flat")
        text_format_group.append(self.line_spacing_dropdown)
        
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

    def on_webview_load(self, webview, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            self.webview.evaluate_javascript("""
                (function() {
                    let p = document.querySelector('p');
                    if (p) {
                        let range = document.createRange();
                        range.setStart(p, 0);
                        range.setEnd(p, 0);
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                    }
                    function debounce(func, wait) {
                        let timeout;
                        return function(...args) {
                            clearTimeout(timeout);
                            timeout = setTimeout(() => func(...args), wait);
                        };
                    }
                    let lastContent = document.body.innerHTML;
                    const notifyChange = debounce(function() {
                        let currentContent = document.body.innerHTML;
                        if (currentContent !== lastContent) {
                            window.webkit.messageHandlers.contentChanged.postMessage('changed');
                            lastContent = currentContent;
                        }
                    }, 250);
                    document.addEventListener('input', notifyChange);
                    document.addEventListener('paste', notifyChange);
                    document.addEventListener('cut', notifyChange);

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
                                formatBlock: document.queryCommandValue('formatBlock') || 'p',
                                fontName: style.fontFamily.split(',')[0].replace(/['"]/g, ''),
                                fontSize: style.fontSize,
                                insertUnorderedList: document.queryCommandState('insertUnorderedList'),
                                insertOrderedList: document.queryCommandState('insertOrderedList'),
                                justifyLeft: document.queryCommandState('justifyLeft'),
                                justifyCenter: document.queryCommandState('justifyCenter'),
                                justifyRight: document.queryCommandState('justifyRight'),
                                justifyFull: document.queryCommandState('justifyFull'),
                                lineHeight: style.lineHeight === 'normal' ? '1.0' : (parseFloat(style.lineHeight) / parseFloat(style.fontSize)).toFixed(2)
                            };
                            window.webkit.messageHandlers.selectionChanged.postMessage(JSON.stringify(state));
                        }
                    }, 100);
                    document.addEventListener('selectionchange', notifySelectionChange);
                    notifySelectionChange();
                })();
            """, -1, None, None, None, None, None)
            GLib.idle_add(self.webview.grab_focus)

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
                font_size_px = float(font_size_str[:-2])
                font_size_pt = str(int(font_size_px / 1.333))
            elif font_size_str.endswith('pt'):
                font_size_pt = font_size_str[:-2]
            else:
                font_size_pt = '12'
            size_store = self.size_dropdown.get_model()
            available_sizes = [size_store.get_string(i) for i in range(size_store.get_n_items())]
            selected_size_index = 3
            if font_size_pt in available_sizes:
                selected_size_index = available_sizes.index(font_size_pt)
            self.current_font_size = available_sizes[selected_size_index]
            self.size_dropdown.handler_block(self.size_dropdown_handler)
            self.size_dropdown.set_selected(selected_size_index)
            self.size_dropdown.handler_unblock(self.size_dropdown_handler)

            detected_line_spacing = state.get('lineHeight', '1.5')
            line_spacing_store = self.line_spacing_dropdown.get_model()
            available_spacings = [line_spacing_store.get_string(i) for i in range(line_spacing_store.get_n_items())]
            selected_spacing_index = 2
            detected_float = float(detected_line_spacing)
            min_diff = float('inf')
            for i, spacing in enumerate(available_spacings):
                diff = abs(float(spacing) - detected_float)
                if diff < min_diff:
                    min_diff = diff
                    selected_spacing_index = i
            self.current_line_spacing = available_spacings[selected_spacing_index]
            self.line_spacing_dropdown.handler_block(self.line_spacing_handler)
            self.line_spacing_dropdown.set_selected(selected_spacing_index)
            self.line_spacing_dropdown.handler_unblock(self.line_spacing_handler)
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
            selected_size_index = 3
            for i in range(size_store.get_n_items()):
                if size_store.get_string(i) == self.current_font_size:
                    selected_size_index = i
                    break
            self.size_dropdown.handler_block(self.size_dropdown_handler)
            self.size_dropdown.set_selected(selected_size_index)
            self.size_dropdown.handler_unblock(self.size_dropdown_handler)

            line_spacing_store = self.line_spacing_dropdown.get_model()
            selected_spacing_index = 2
            for i in range(line_spacing_store.get_n_items()):
                if line_spacing_store.get_string(i) == self.current_line_spacing:
                    selected_spacing_index = i
                    break
            self.line_spacing_dropdown.handler_block(self.line_spacing_handler)
            self.line_spacing_dropdown.set_selected(selected_spacing_index)
            self.line_spacing_dropdown.handler_unblock(self.line_spacing_handler)

    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def exec_js_with_result(self, js_code, callback):
        self.webview.evaluate_javascript(js_code, -1, None, None, None, callback, None)

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
            script = "document.body.style.backgroundColor = '#242424'; document.body.style.color = '#e0e0e0';"
        else:
            btn.set_icon_name("display-brightness")
            script = "document.body.style.backgroundColor = '#ffffff'; document.body.style.color = '#000000';"
        self.exec_js(script)

    def on_search_clicked(self, btn):
        self.webview.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, self.show_search_dialog, None)

    def show_search_dialog(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            selected_text = js_value.to_string() if js_value else ""
        except Exception as e:
            print(f"Error getting selection: {e}")
            selected_text = ""

        self.search_dialog = Adw.MessageDialog(transient_for=self, heading="Find", modal=False)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_text(selected_text)
        self.search_entry.connect("activate", self.on_find_next_clicked)
        content_box.append(self.search_entry)

        self.highlight_check = Gtk.CheckButton(label="Highlight All")
        self.highlight_check.connect("toggled", self.on_highlight_toggled)
        content_box.append(self.highlight_check)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        back_btn = Gtk.Button(label="Back")
        back_btn.connect("clicked", self.on_find_prev_clicked)
        button_box.append(back_btn)

        next_btn = Gtk.Button(label="Next")
        next_btn.connect("clicked", self.on_find_next_clicked)
        button_box.append(next_btn)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self.on_search_close_clicked)
        button_box.append(close_btn)

        content_box.append(button_box)
        self.search_dialog.set_extra_child(content_box)
        self.search_dialog.present()

        if selected_text:
            self.find_text(selected_text)

    def find_text(self, search_text):
        script = f"""
            (function() {{
                let highlights = document.querySelectorAll('.search-highlight');
                highlights.forEach(h => {{
                    let parent = h.parentNode;
                    parent.replaceChild(document.createTextNode(h.textContent), h);
                    parent.normalize();
                }});

                let matches = [];
                let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                let searchText = {json.dumps(search_text)};
                let regex = new RegExp(searchText, 'gi');

                while (node = walker.nextNode()) {{
                    let text = node.textContent;
                    let match;
                    while ((match = regex.exec(text)) !== null) {{
                        matches.push({{
                            node: node,
                            start: match.index,
                            end: match.index + match[0].length
                        }});
                    }}
                }}

                window.searchMatches = matches;
                return JSON.stringify(matches);
            }})();
        """
        self.exec_js_with_result(script, self.on_matches_found)

    def on_matches_found(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                self.search_matches = json.loads(js_value.to_string())
                self.current_search_match = 0
                if self.search_matches and not self.highlight_check.get_active():
                    self.highlight_current_match()
                elif self.search_matches and self.highlight_check.get_active():
                    self.highlight_all()
        except Exception as e:
            print(f"Error finding matches: {e}")
            self.search_matches = []

    def highlight_all(self):
        script = """
            (function() {
                let matches = window.searchMatches || [];
                matches.forEach((match, index) => {
                    let range = document.createRange();
                    range.setStart(match.node, match.start);
                    range.setEnd(match.node, match.end);
                    let span = document.createElement('span');
                    span.className = 'search-highlight';
                    span.style.backgroundColor = 'yellow';
                    range.surroundContents(span);
                });
            })();
        """
        self.exec_js(script)

    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
        script = f"""
            (function() {{
                let matches = window.searchMatches || [];
                let index = {self.current_search_match};
                if (index >= 0 && index < matches.length) {{
                    let match = matches[index];
                    let range = document.createRange();
                    range.setStart(match.node, match.start);
                    range.setEnd(match.node, match.end);
                    let sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                    match.node.parentElement.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }})();
        """
        self.exec_js(script)

    def on_highlight_toggled(self, check):
        if check.get_active():
            self.highlight_all()
        else:
            self.clear_search_highlights()
            if self.search_matches:
                self.highlight_current_match()

    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or self.search_entry.get_text() != self.last_search_text:
            self.last_search_text = search_text
            self.find_text(search_text)
        elif self.search_matches:
            self.current_search_match = (self.current_search_match + 1) % len(self.search_matches)
            self.highlight_current_match()

    def on_find_prev_clicked(self, btn):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or self.search_entry.get_text() != self.last_search_text:
            self.last_search_text = search_text
            self.find_text(search_text)
        elif self.search_matches:
            self.current_search_match = (self.current_search_match - 1) if self.current_search_match > 0 else len(self.search_matches) - 1
            self.highlight_current_match()

    def on_search_close_clicked(self, btn):
        self.clear_search_highlights()
        self.search_matches = []
        self.current_search_match = 0
        self.search_dialog.destroy()

    def clear_search_highlights(self):
        script = """
            (function() {
                let highlights = document.querySelectorAll('.search-highlight');
                highlights.forEach(h => {
                    let parent = h.parentNode;
                    parent.replaceChild(document.createTextNode(h.textContent), h);
                    parent.normalize();
                });
            })();
        """
        self.exec_js(script)

    def on_replace_clicked(self, btn):
        self.webview.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, self.show_replace_dialog, None)

    def show_replace_dialog(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            selected_text = js_value.to_string() if js_value else ""
        except Exception as e:
            print(f"Error getting selection: {e}")
            selected_text = ""

        self.replace_dialog = Adw.MessageDialog(transient_for=self, heading="Replace", modal=True)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        self.find_entry = Gtk.Entry()
        self.find_entry.set_text(selected_text)
        self.find_entry.connect("activate", self.on_replace_clicked_handler)
        content_box.append(Gtk.Label(label="Find:"))
        content_box.append(self.find_entry)

        self.replace_entry = Gtk.Entry()
        self.replace_entry.connect("activate", self.on_replace_clicked_handler)
        content_box.append(Gtk.Label(label="Replace with:"))
        content_box.append(self.replace_entry)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        replace_btn = Gtk.Button(label="Replace")
        replace_btn.connect("clicked", self.on_replace_clicked_handler)
        button_box.append(replace_btn)

        replace_all_btn = Gtk.Button(label="Replace All")
        replace_all_btn.connect("clicked", self.on_replace_all_clicked)
        button_box.append(replace_all_btn)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self.on_replace_close_clicked)
        button_box.append(close_btn)

        content_box.append(button_box)
        self.replace_dialog.set_extra_child(content_box)
        self.replace_dialog.present()

    def on_replace_clicked_handler(self, btn_or_entry):
        find_text = self.find_entry.get_text()
        replace_text = self.replace_entry.get_text()
        script = f"""
            (function() {{
                let sel = window.getSelection();
                if (sel.rangeCount > 0 && sel.toString() === {json.dumps(find_text)}) {{
                    let range = sel.getRangeAt(0);
                    range.deleteContents();
                    range.insertNode(document.createTextNode({json.dumps(replace_text)}));
                    window.webkit.messageHandlers.contentChanged.postMessage('changed');
                }}
            }})();
        """
        self.exec_js(script)

    def on_replace_all_clicked(self, btn):
        find_text = self.find_entry.get_text()
        replace_text = self.replace_entry.get_text()
        script = f"""
            (function() {{
                let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                let regex = new RegExp({json.dumps(find_text)}, 'g');
                let changes = false;

                while (node = walker.nextNode()) {{
                    let text = node.textContent;
                    if (regex.test(text)) {{
                        node.textContent = text.replace(regex, {json.dumps(replace_text)});
                        changes = true;
                    }}
                }}

                if (changes) {{
                    window.webkit.messageHandlers.contentChanged.postMessage('changed');
                }}
            }})();
        """
        self.exec_js(script)

    def on_replace_close_clicked(self, btn):
        self.replace_dialog.destroy()

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
            elif keyval == Gdk.KEY_f:  # Ctrl+F for Search
                self.on_search_clicked(None)
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
            elif keyval == Gdk.KEY_H:
                current_index = self.line_spacing_dropdown.get_selected()
                next_index = (current_index + 1) % self.line_spacing_dropdown.get_model().get_n_items()
                self.line_spacing_dropdown.set_selected(next_index)
                self.on_line_spacing_changed(self.line_spacing_dropdown)
                return True
        elif not ctrl:
            if keyval == Gdk.KEY_F12 and not shift:
                self.on_number_list_toggled(self.number_btn)
                return True
            elif keyval == Gdk.KEY_F12 and shift:
                self.on_bullet_list_toggled(self.bullet_btn)
                return True
        return False

    def on_line_spacing_changed(self, dropdown, *args):
        if item := dropdown.get_selected_item():
            self.current_line_spacing = item.get_string()
            script = f"""
                (function() {{
                    let sel = window.getSelection();
                    let range = sel.rangeCount > 0 ? sel.getRangeAt(0) : document.createRange();
                    let node = range.startContainer || document.body;
                    let cursorNode = range.startContainer;
                    let cursorOffset = range.startOffset;

                    if (node.nodeType === Node.TEXT_NODE) {{
                        node = node.parentElement;
                    }}

                    let block = node.closest('p, div, h1, h2, h3, h4, h5, h6');

                    if (!block || block === document.body) {{
                        let newParagraph = document.createElement('p');
                        newParagraph.style.lineHeight = '{self.current_line_spacing}';

                        if (node === document.body && sel.rangeCount > 0) {{
                            let textNode = range.startContainer;
                            if (textNode.nodeType === Node.TEXT_NODE) {{
                                range.selectNode(textNode);
                                range.surroundContents(newParagraph);
                                range.setStart(cursorNode, cursorOffset);
                                range.setEnd(cursorNode, cursorOffset);
                                sel.removeAllRanges();
                                sel.addRange(range);
                            }} else {{
                                range.insertNode(newParagraph);
                                range.setStart(newParagraph, 0);
                                range.setEnd(newParagraph, 0);
                                sel.removeAllRanges();
                                sel.addRange(range);
                            }}
                        }} else if (node === document.body) {{
                            range.insertNode(newParagraph);
                            range.setStart(newParagraph, 0);
                            range.setEnd(newParagraph, 0);
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }}
                    }} else {{
                        block.style.lineHeight = '{self.current_line_spacing}';
                        if (sel.rangeCount > 0) {{
                            range.setStart(cursorNode, cursorOffset);
                            range.setEnd(cursorNode, cursorOffset);
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }}
                    }}

                    if (!block && sel.isCollapsed && range.startContainer === document.body) {{
                        let previousSibling = range.startContainer.childNodes[range.startOffset - 1];
                        if (previousSibling && previousSibling.nodeName.match(/^(P|DIV|H[1-6])$/i)) {{
                            previousSibling.style.lineHeight = '{self.current_line_spacing}';
                            range.setStart(cursorNode, cursorOffset);
                            range.setEnd(cursorNode, cursorOffset);
                            sel.removeAllRanges();
                            sel.addRange(range);
                        }}
                    }}

                    window.webkit.messageHandlers.contentChanged.postMessage('changed');
                }})();
            """
            self.exec_js(script)
            self.update_formatting_ui()

    def on_bold_toggled(self, btn):
        if hasattr(self, '_processing_bold_toggle') and self._processing_bold_toggle:
            return
        self._processing_bold_toggle = True
        def get_bold_state(webview, result, user_data):
            try:
                if result is not None:
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
                if result is not None:
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
                if result is not None:
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
                if result is not None:
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
            size_key = item.get_string()
            webkit_size = self.size_map[size_key]
            self.current_font_size = size_key
            script = f"document.execCommand('fontSize', false, '{webkit_size}')"
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
########################################################
    def find_text(self, search_text):
        script = f"""
            (function() {{
                let highlights = document.querySelectorAll('.search-highlight');
                highlights.forEach(h => {{
                    let parent = h.parentNode;
                    parent.replaceChild(document.createTextNode(h.textContent), h);
                    parent.normalize();
                }});

                let matches = [];
                let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                let searchText = {json.dumps(search_text)};
                let regex = new RegExp(searchText, 'gi');

                while (node = walker.nextNode()) {{
                    let text = node.textContent;
                    let match;
                    while ((match = regex.exec(text)) !== null) {{
                        matches.push({{
                            node: node,
                            start: match.index,
                            end: match.index + match[0].length
                        }});
                    }}
                }}

                window.searchMatches = matches;
                return JSON.stringify(matches);
            }})();
        """
        self.last_search_text = search_text  # Store the search text immediately
        self.exec_js_with_result(script, self.on_matches_found)

    def on_matches_found(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                self.search_matches = json.loads(js_value.to_string())
                self.current_search_match = 0  # Reset to first match
                if self.search_matches:
                    if self.highlight_check.get_active():
                        self.highlight_all()
                    else:
                        self.highlight_current_match()  # Highlight first match immediately
                else:
                    print("No matches found")
        except Exception as e:
            print(f"Error finding matches: {e}")
            self.search_matches = []
            self.current_search_match = 0

    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
        script = f"""
            (function() {{
                let matches = window.searchMatches || [];
                let index = {self.current_search_match};
                if (index >= 0 && index < matches.length) {{
                    let match = matches[index];
                    let range = document.createRange();
                    range.setStart(match.node, match.start);
                    range.setEnd(match.node, match.end);
                    let sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                    match.node.parentElement.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }})();
        """
        self.exec_js(script)

    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)  # Trigger new search if text changed
        elif self.search_matches:
            self.current_search_match = (self.current_search_match + 1) % len(self.search_matches)
            if not self.highlight_check.get_active():  # Only highlight current if not all highlighted
                self.clear_search_highlights()  # Clear previous highlights
                self.highlight_current_match()

    def on_find_prev_clicked(self, btn):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)  # Trigger new search if text changed
        elif self.search_matches:
            self.current_search_match = (self.current_search_match - 1) if self.current_search_match > 0 else len(self.search_matches) - 1
            if not self.highlight_check.get_active():  # Only highlight current if not all highlighted
                self.clear_search_highlights()  # Clear previous highlights
                self.highlight_current_match()

    def on_replace_clicked_handler(self, btn_or_entry):
        find_text = self.find_entry.get_text()
        replace_text = self.replace_entry.get_text()
        script = f"""
            (function() {{
                let sel = window.getSelection();
                if (sel.rangeCount > 0 && sel.toString() === {json.dumps(find_text)}) {{
                    let range = sel.getRangeAt(0);
                    range.deleteContents();
                    range.insertNode(document.createTextNode({json.dumps(replace_text)}));
                    window.webkit.messageHandlers.contentChanged.postMessage('changed');
                }}
            }})();
        """
        self.exec_js(script)
        # After replace, update matches and move to next
        if self.search_matches and find_text == self.last_search_text:
            self.find_text(find_text)  # Refresh matches after replacement
            if self.search_matches:
                self.current_search_match = min(self.current_search_match, len(self.search_matches) - 1)
                if not self.highlight_check.get_active():
                    self.clear_search_highlights()
                    self.highlight_current_match()
        else:
            self.find_text(find_text)  # Trigger search if no prior matches

######################## find improvemnet
    def on_search_clicked(self, btn):
        self.webview.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, self.show_search_dialog, None)

    def show_search_dialog(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            selected_text = js_value.to_string() if js_value else ""
        except Exception as e:
            print(f"Error getting selection: {e}")
            selected_text = ""

        self.search_dialog = Adw.MessageDialog(transient_for=self, heading="Find", modal=False)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.set_text(selected_text)
        self.search_entry.connect("activate", self.on_find_next_clicked)
        content_box.append(Gtk.Label(label="Find:"))
        content_box.append(self.search_entry)

        # Options
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.match_case_check = Gtk.CheckButton(label="Match Case")
        self.match_entire_word_check = Gtk.CheckButton(label="Match Entire Word")
        self.highlight_all_check = Gtk.CheckButton(label="Highlight All")
        self.search_backwards_check = Gtk.CheckButton(label="Search Backwards")
        self.wrap_around_check = Gtk.CheckButton(label="Wrap Around")
        self.highlight_all_check.connect("toggled", self.on_highlight_all_toggled)
        options_box.append(self.match_case_check)
        options_box.append(self.match_entire_word_check)
        options_box.append(self.highlight_all_check)
        options_box.append(self.search_backwards_check)
        options_box.append(self.wrap_around_check)
        content_box.append(options_box)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        self.back_btn = Gtk.Button(label="Back")
        self.back_btn.connect("clicked", self.on_find_back_clicked)
        button_box.append(self.back_btn)

        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.connect("clicked", self.on_find_next_clicked)
        button_box.append(self.next_btn)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self.on_search_close_clicked)
        button_box.append(close_btn)

        content_box.append(button_box)
        self.search_dialog.set_extra_child(content_box)
        self.search_dialog.present()

        if selected_text:
            self.find_text(selected_text)

    def find_text(self, search_text):
        # Clear existing highlights
        self.clear_search_highlights()
        flags = 'g'  # Global search
        if self.match_case_check.get_active():
            flags += 'i'  # Remove 'i' for case-sensitive (default is case-insensitive with 'i')
        else:
            flags = 'gi'
        word_boundary = r'\b' if self.match_entire_word_check.get_active() else ''
        script = f"""
            (function() {{
                let matches = [];
                let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                let searchText = {json.dumps(search_text)};
                let regex = new RegExp('{word_boundary}' + searchText + '{word_boundary}', '{flags}');

                while (node = walker.nextNode()) {{
                    let text = node.textContent;
                    let match;
                    while ((match = regex.exec(text)) !== null) {{
                        matches.push({{
                            node: node,
                            start: match.index,
                            end: match.index + match[0].length
                        }});
                    }}
                }}

                window.searchMatches = matches;
                return JSON.stringify(matches);
            }})();
        """
        self.last_search_text = search_text
        self.exec_js_with_result(script, self.on_matches_found)

    def on_matches_found(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                self.search_matches = json.loads(js_value.to_string())
                self.current_search_match = 0 if not self.search_backwards_check.get_active() else len(self.search_matches) - 1
                if self.search_matches:
                    if self.highlight_all_check.get_active():
                        self.highlight_all()
                    else:
                        self.highlight_current_match()
                else:
                    print("No matches found")
            else:
                self.search_matches = []
                self.current_search_match = 0
        except Exception as e:
            print(f"Error finding matches: {e}")
            self.search_matches = []
            self.current_search_match = 0

    def highlight_all(self):
        script = """
            (function() {
                let matches = window.searchMatches || [];
                matches.forEach((match, index) => {
                    let range = document.createRange();
                    range.setStart(match.node, match.start);
                    range.setEnd(match.node, match.end);
                    let span = document.createElement('span');
                    span.className = 'search-highlight';
                    span.style.backgroundColor = 'yellow';
                    range.surroundContents(span);
                });
            })();
        """
        self.exec_js(script)

    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
        script = f"""
            (function() {{
                let matches = window.searchMatches || [];
                let index = {self.current_search_match};
                if (index >= 0 && index < matches.length) {{
                    let match = matches[index];
                    let range = document.createRange();
                    range.setStart(match.node, match.start);
                    range.setEnd(match.node, match.end);
                    let sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                    match.node.parentElement.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }})();
        """
        self.exec_js(script)

    def on_highlight_all_toggled(self, check):
        if check.get_active():
            self.highlight_all()
        else:
            self.clear_search_highlights()
            if self.search_matches:
                self.highlight_current_match()

    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            else:
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            if not self.highlight_all_check.get_active():
                self.clear_search_highlights()
                self.highlight_current_match()

    def on_find_back_clicked(self, btn):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            else:
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            if not self.highlight_all_check.get_active():
                self.clear_search_highlights()
                self.highlight_current_match()

    def on_search_close_clicked(self, btn):
        self.clear_search_highlights()
        self.search_matches = []
        self.current_search_match = 0
        self.search_dialog.destroy()

    def clear_search_highlights(self):
        script = """
            (function() {
                let highlights = document.querySelectorAll('.search-highlight');
                highlights.forEach(h => {
                    let parent = h.parentNode;
                    parent.replaceChild(document.createTextNode(h.textContent), h);
                    parent.normalize();
                });
            })();
        """
        self.exec_js(script)
#######################################################
########### Working search but highlighting whole page/editor

    def on_search_clicked(self, btn):
        self.webview.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, self.show_search_dialog, None)

    def show_search_dialog(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            selected_text = js_value.to_string() if js_value else ""
        except Exception as e:
            print(f"Error getting selection: {e}")
            selected_text = ""

        self.search_dialog = Adw.MessageDialog(transient_for=self, heading="Find", modal=True)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.set_text(selected_text)
        self.search_entry.connect("activate", self.on_find_next_clicked)
        content_box.append(Gtk.Label(label="Find:"))
        content_box.append(self.search_entry)

        # Options
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.match_case_check = Gtk.CheckButton(label="Match Case")
        self.match_entire_word_check = Gtk.CheckButton(label="Match Entire Word")
        self.highlight_all_check = Gtk.CheckButton(label="Highlight All")
        self.search_backwards_check = Gtk.CheckButton(label="Search Backwards")
        self.wrap_around_check = Gtk.CheckButton(label="Wrap Around")
        self.wrap_around_check.set_active(True)  # Default to wrap around
        self.highlight_all_check.connect("toggled", self.on_highlight_all_toggled)
        options_box.append(self.match_case_check)
        options_box.append(self.match_entire_word_check)
        options_box.append(self.highlight_all_check)
        options_box.append(self.search_backwards_check)
        options_box.append(self.wrap_around_check)
        content_box.append(options_box)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        self.back_btn = Gtk.Button(label="Back")
        self.back_btn.connect("clicked", self.on_find_back_clicked)
        button_box.append(self.back_btn)

        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.connect("clicked", self.on_find_next_clicked)
        button_box.append(self.next_btn)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self.on_search_close_clicked)
        button_box.append(close_btn)

        content_box.append(button_box)
        self.search_dialog.set_extra_child(content_box)
        self.search_dialog.present()

        if selected_text:
            self.find_text(selected_text)

    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def exec_js_with_result(self, script, callback):
        self.webview.evaluate_javascript(script, -1, None, None, None, callback, None)

    def find_text(self, search_text):
        # Clear existing highlights
        self.clear_search_highlights()
        
        # Set correct flags for case sensitivity
        flags = 'g'  # Global search
        if not self.match_case_check.get_active():
            flags += 'i'  # 'i' for case-insensitive
        
        # Escape special regex characters in search_text
        escaped_search_text = search_text.replace('\\', '\\\\').replace('/', '\\/').replace('.', '\\.') \
                                     .replace('*', '\\*').replace('+', '\\+').replace('?', '\\?') \
                                     .replace('(', '\\(').replace(')', '\\)').replace('[', '\\[') \
                                     .replace(']', '\\]').replace('{', '\\{').replace('}', '\\}') \
                                     .replace('^', '\\^').replace('$', '\\$')
        
        word_boundary = r'\b' if self.match_entire_word_check.get_active() else ''
        
        script = f"""
            (function() {{
                let matches = [];
                let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                let searchText = {json.dumps(escaped_search_text)};
                let regex = new RegExp('{word_boundary}' + searchText + '{word_boundary}', '{flags}');
                
                let index = 0;
                while (node = walker.nextNode()) {{
                    let text = node.textContent;
                    let match;
                    let lastIndex = 0;
                    
                    // Reset regex for each node
                    regex.lastIndex = 0;
                    
                    while ((match = regex.exec(text)) !== null) {{
                        matches.push({{
                            node: node,
                            start: match.index,
                            end: match.index + match[0].length,
                            text: match[0]
                        }});
                        
                        // Prevent infinite loops for zero-length matches
                        if (regex.lastIndex === match.index) {{
                            regex.lastIndex++;
                        }}
                        
                        lastIndex = regex.lastIndex;
                    }}
                }}

                window.searchMatches = matches;
                return JSON.stringify(matches.length > 0 ? 
                    matches.map(m => ({{ start: m.start, end: m.end, text: m.text }})) : []);
            }})();
        """
        self.last_search_text = search_text
        self.exec_js_with_result(script, self.on_matches_found)

    def on_matches_found(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                matches_info = json.loads(js_value.to_string())
                self.search_matches = matches_info
                
                if self.search_matches:
                    if self.search_backwards_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        
                    if self.highlight_all_check.get_active():
                        self.highlight_all()
                    else:
                        self.highlight_current_match()
                        
                    # Update dialog title with match count
                    self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
                else:
                    print("No matches found")
                    self.search_dialog.set_heading("Find (No matches)")
            else:
                self.search_matches = []
                self.current_search_match = 0
                self.search_dialog.set_heading("Find (No matches)")
        except Exception as e:
            print(f"Error finding matches: {e}")
            self.search_matches = []
            self.current_search_match = 0
            self.search_dialog.set_heading("Find (Error)")

    def highlight_all(self):
        script = """
            (function() {
                // First clean any existing highlights
                let highlights = document.querySelectorAll('.search-highlight');
                highlights.forEach(h => {
                    let parent = h.parentNode;
                    parent.replaceChild(document.createTextNode(h.textContent), h);
                    parent.normalize();
                });
                
                // Don't proceed if we don't have matches
                if (!window.searchMatches || window.searchMatches.length === 0) {
                    return;
                }
                
                // Create a document fragment to minimize reflows
                let highlightedNodes = new Map();
                
                for (let i = 0; i < window.searchMatches.length; i++) {
                    let match = window.searchMatches[i];
                    let node = match.node;
                    
                    // If we've already highlighted a node, we need to get its new reference
                    if (highlightedNodes.has(node)) {
                        node = highlightedNodes.get(node);
                        
                        // Adjust indices for previously added spans in this node
                        // This will make later matches work with the modified DOM
                        match.node = node;
                    }
                    
                    let range = document.createRange();
                    range.setStart(node, match.start);
                    range.setEnd(node, match.end);
                    
                    let span = document.createElement('span');
                    span.className = 'search-highlight';
                    span.style.backgroundColor = 'yellow';
                    
                    try {
                        range.surroundContents(span);
                        
                        // Store reference to the node after the span
                        if (node.nextSibling) {
                            highlightedNodes.set(node, node.nextSibling);
                        }
                    } catch(e) {
                        console.error('Error highlighting:', e);
                    }
                }
                
                // Scroll to current match
                let currentMatch = window.searchMatches[window.currentSearchMatch];
                if (currentMatch) {
                    let elements = document.querySelectorAll('.search-highlight');
                    if (elements[window.currentSearchMatch]) {
                        elements[window.currentSearchMatch].scrollIntoView({
                            behavior: 'smooth',
                            block: 'center'
                        });
                    }
                }
            })();
        """
        self.exec_js(script)

    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
            
        script = f"""
            (function() {{
                let matches = window.searchMatches || [];
                let index = {self.current_search_match};
                
                if (index >= 0 && index < matches.length) {{
                    let match = matches[index];
                    
                    try {{
                        let range = document.createRange();
                        range.setStart(match.node, match.start);
                        range.setEnd(match.node, match.end);
                        
                        // Clear selection and add new range
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        
                        // Scroll the match into view
                        let element = match.node.parentElement;
                        element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        
                        // Flash the match to make it more visible
                        let originalBg = element.style.backgroundColor;
                        element.style.backgroundColor = 'yellow';
                        
                        setTimeout(() => {{
                            element.style.backgroundColor = originalBg;
                        }}, 1000);
                        
                        window.currentSearchMatch = index;
                    }} catch(e) {{
                        console.error('Error highlighting current match:', e);
                    }}
                }}
            }})();
        """
        self.exec_js(script)
        
        # Update dialog title with match count
        if self.search_matches:
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")

    def on_highlight_all_toggled(self, check):
        if check.get_active():
            self.highlight_all()
        else:
            self.clear_search_highlights()
            if self.search_matches:
                self.highlight_current_match()

    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            else:
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            
            # Update dialog title with match count
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            if not self.highlight_all_check.get_active():
                self.clear_search_highlights()
                self.highlight_current_match()
            else:
                # Just scroll to the current match
                script = f"""
                    (function() {{
                        let elements = document.querySelectorAll('.search-highlight');
                        if (elements[{self.current_search_match}]) {{
                            elements[{self.current_search_match}].scrollIntoView({{
                                behavior: 'smooth',
                                block: 'center'
                            }});
                        }}
                    }})();
                """
                self.exec_js(script)

    def on_find_back_clicked(self, btn):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            # Save current direction
            backward = self.search_backwards_check.get_active()
            # Temporarily flip direction for initial search
            self.search_backwards_check.set_active(not backward)
            self.find_text(search_text)
            # Restore direction
            self.search_backwards_check.set_active(backward)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            else:
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            
            # Update dialog title with match count
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            if not self.highlight_all_check.get_active():
                self.clear_search_highlights()
                self.highlight_current_match()
            else:
                # Just scroll to the current match
                script = f"""
                    (function() {{
                        let elements = document.querySelectorAll('.search-highlight');
                        if (elements[{self.current_search_match}]) {{
                            elements[{self.current_search_match}].scrollIntoView({{
                                behavior: 'smooth',
                                block: 'center'
                            }});
                        }}
                    }})();
                """
                self.exec_js(script)

    def on_search_close_clicked(self, btn):
        self.clear_search_highlights()
        self.search_matches = []
        self.current_search_match = 0
        self.search_dialog.destroy()

    def clear_search_highlights(self):
        script = """
            (function() {
                let highlights = document.querySelectorAll('.search-highlight');
                highlights.forEach(h => {
                    let parent = h.parentNode;
                    parent.replaceChild(document.createTextNode(h.textContent), h);
                    parent.normalize();
                });
                
                // Clear selection
                window.getSelection().removeAllRanges();
            })();
        """
        self.exec_js(script)



###################################################################### highligh fix?


    def on_search_clicked(self, btn):
        self.webview.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, self.show_search_dialog, None)

    def show_search_dialog(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            selected_text = js_value.to_string() if js_value else ""
        except Exception as e:
            print(f"Error getting selection: {e}")
            selected_text = ""

        self.search_dialog = Adw.MessageDialog(transient_for=self, heading="Find", modal=True)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.set_text(selected_text)
        self.search_entry.connect("activate", self.on_find_next_clicked)
        content_box.append(Gtk.Label(label="Find:"))
        content_box.append(self.search_entry)

        # Options
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.match_case_check = Gtk.CheckButton(label="Match Case")
        self.match_entire_word_check = Gtk.CheckButton(label="Match Entire Word")
        self.highlight_all_check = Gtk.CheckButton(label="Highlight All")
        self.search_backwards_check = Gtk.CheckButton(label="Search Backwards")
        self.wrap_around_check = Gtk.CheckButton(label="Wrap Around")
        self.wrap_around_check.set_active(True)  # Default to wrap around
        self.highlight_all_check.connect("toggled", self.on_highlight_all_toggled)
        options_box.append(self.match_case_check)
        options_box.append(self.match_entire_word_check)
        options_box.append(self.highlight_all_check)
        options_box.append(self.search_backwards_check)
        options_box.append(self.wrap_around_check)
        content_box.append(options_box)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        self.back_btn = Gtk.Button(label="Back")
        self.back_btn.connect("clicked", self.on_find_back_clicked)
        button_box.append(self.back_btn)

        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.connect("clicked", self.on_find_next_clicked)
        button_box.append(self.next_btn)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self.on_search_close_clicked)
        button_box.append(close_btn)

        content_box.append(button_box)
        self.search_dialog.set_extra_child(content_box)
        self.search_dialog.present()

        if selected_text:
            self.find_text(selected_text)

    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def exec_js_with_result(self, script, callback):
        self.webview.evaluate_javascript(script, -1, None, None, None, callback, None)

    def find_text(self, search_text):
        # Clear existing highlights
        self.clear_search_highlights()
        
        # Set correct flags for case sensitivity
        flags = 'g'  # Global search
        if not self.match_case_check.get_active():
            flags += 'i'  # 'i' for case-insensitive
        
        # Escape special regex characters in search_text
        escaped_search_text = search_text.replace('\\', '\\\\').replace('/', '\\/').replace('.', '\\.') \
                                     .replace('*', '\\*').replace('+', '\\+').replace('?', '\\?') \
                                     .replace('(', '\\(').replace(')', '\\)').replace('[', '\\[') \
                                     .replace(']', '\\]').replace('{', '\\{').replace('}', '\\}') \
                                     .replace('^', '\\^').replace('$', '\\$')
        
        word_boundary = r'\b' if self.match_entire_word_check.get_active() else ''
        
        script = f"""
            (function() {{
                try {{
                    let matches = [];
                    let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                    let node;
                    let searchText = {json.dumps(escaped_search_text)};
                    let regex = new RegExp('{word_boundary}' + searchText + '{word_boundary}', '{flags}');
                    
                    while (node = walker.nextNode()) {{
                        let text = node.textContent;
                        regex.lastIndex = 0;  // Reset regex for each node
                        
                        let match;
                        while ((match = regex.exec(text)) !== null) {{
                            matches.push({{
                                node: node,
                                start: match.index,
                                end: match.index + match[0].length,
                                text: match[0]
                            }});
                            
                            // Prevent infinite loops for zero-length matches
                            if (regex.lastIndex === match.index) {{
                                regex.lastIndex++;
                            }}
                        }}
                    }}

                    window.searchMatches = matches;
                    return JSON.stringify({{
                        count: matches.length, 
                        matches: matches.map(m => ({{ start: m.start, end: m.end, text: m.text }}))
                    }});
                }} catch (e) {{
                    console.error("Search error:", e);
                    return JSON.stringify({{ count: 0, matches: [], error: e.toString() }});
                }}
            }})();
        """
        self.last_search_text = search_text
        self.exec_js_with_result(script, self.on_matches_found)

    def on_matches_found(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                result_obj = json.loads(js_value.to_string())
                self.search_matches = result_obj.get('matches', [])
                match_count = result_obj.get('count', 0)
                
                if match_count > 0:
                    if self.search_backwards_check.get_active():
                        self.current_search_match = match_count - 1
                    else:
                        self.current_search_match = 0
                        
                    if self.highlight_all_check.get_active():
                        self.highlight_all()
                    else:
                        self.highlight_current_match()
                        
                    # Update dialog title with match count
                    self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {match_count})")
                else:
                    print("No matches found")
                    self.search_dialog.set_heading("Find (No matches)")
            else:
                self.search_matches = []
                self.current_search_match = 0
                self.search_dialog.set_heading("Find (No matches)")
        except Exception as e:
            print(f"Error finding matches: {e}")
            self.search_matches = []
            self.current_search_match = 0
            self.search_dialog.set_heading("Find (Error)")

    def highlight_all(self):
        # First clear any existing highlights
        self.clear_search_highlights()
        
        script = """
            (function() {
                try {
                    if (!window.searchMatches || window.searchMatches.length === 0) {
                        return;
                    }
                    
                    // We need to keep track of offset changes as we add spans
                    let nodeOffsets = new Map();
                    
                    for (let i = 0; i < window.searchMatches.length; i++) {
                        let match = window.searchMatches[i];
                        let node = match.node;
                        let offset = nodeOffsets.get(node) || 0;
                        
                        // Create a range for this match
                        let range = document.createRange();
                        range.setStart(node, match.start + offset);
                        range.setEnd(node, match.end + offset);
                        
                        // Create a highlight span
                        let span = document.createElement('span');
                        span.className = 'search-highlight';
                        span.style.backgroundColor = 'yellow';
                        span.setAttribute('data-match-index', i);
                        
                        try {
                            range.surroundContents(span);
                            
                            // Update offset - adding span increases text node offsets
                            // Length of the tag is roughly: <span class="search-highlight" data-match-index="X" style="background-color: yellow;"></span>
                            let addedLength = 80;  // approximate length of span markup
                            nodeOffsets.set(node, offset + addedLength);
                        } catch(e) {
                            console.error('Error highlighting match', i, e);
                        }
                    }
                    
                    // Scroll to current match
                    setTimeout(() => {
                        let current = document.querySelector('.search-highlight[data-match-index="' + window.currentSearchMatch + '"]');
                        if (current) {
                            current.scrollIntoView({
                                behavior: 'smooth',
                                block: 'center'
                            });
                            
                            // Add a special class to current match
                            current.classList.add('current-match');
                            current.style.outline = '2px solid blue';
                        }
                    }, 100);
                } catch (e) {
                    console.error("Highlight all error:", e);
                }
            })();
        """
        self.exec_js(script)

    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
            
        script = f"""
            (function() {{
                try {{
                    window.currentSearchMatch = {self.current_search_match};
                    let matches = window.searchMatches || [];
                    let index = {self.current_search_match};
                    
                    if (index >= 0 && index < matches.length) {{
                        let match = matches[index];
                        
                        // Create a range for this match
                        let range = document.createRange();
                        range.setStart(match.node, match.start);
                        range.setEnd(match.node, match.end);
                        
                        // Select the text
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        
                        // Make sure it's visible
                        match.node.parentElement.scrollIntoView({{ 
                            behavior: 'smooth', 
                            block: 'center' 
                        }});
                        
                        // Temporarily flash a background to make it visible
                        let originalBg = match.node.parentElement.style.backgroundColor;
                        let originalColor = match.node.parentElement.style.color;
                        
                        // Create a highlight element
                        let span = document.createElement('span');
                        span.textContent = match.text;
                        span.className = 'temp-highlight';
                        span.style.backgroundColor = 'yellow';
                        
                        // Only change the matched text's background
                        // Save the range contents
                        let fragment = range.extractContents();
                        span.appendChild(fragment);
                        range.insertNode(span);
                        
                        // Remove the highlight after a short time
                        setTimeout(() => {{
                            if (span.parentNode) {{
                                let content = span.textContent;
                                let parent = span.parentNode;
                                parent.replaceChild(document.createTextNode(content), span);
                                parent.normalize();
                            }}
                        }}, 1500);
                    }}
                }} catch (e) {{
                    console.error("Highlight current match error:", e);
                }}
            }})();
        """
        self.exec_js(script)
        
        # Update dialog title with match count
        if self.search_matches:
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")

    def on_highlight_all_toggled(self, check):
        if check.get_active():
            self.highlight_all()
        else:
            self.clear_search_highlights()
            if self.search_matches:
                self.highlight_current_match()

    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            else:
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            
            # Update dialog title with match count
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            if not self.highlight_all_check.get_active():
                self.clear_search_highlights()
                self.highlight_current_match()
            else:
                # Highlight all again with new current index
                script = f"""
                    (function() {{
                        try {{
                            window.currentSearchMatch = {self.current_search_match};
                            
                            // Remove current-match class from any existing elements
                            document.querySelectorAll('.search-highlight.current-match').forEach(el => {{
                                el.classList.remove('current-match');
                                el.style.outline = '';
                            }});
                            
                            // Add current-match to the new current match
                            let current = document.querySelector('.search-highlight[data-match-index="{self.current_search_match}"]');
                            if (current) {{
                                current.classList.add('current-match');
                                current.style.outline = '2px solid blue';
                                current.scrollIntoView({{
                                    behavior: 'smooth',
                                    block: 'center'
                                }});
                            }}
                        }} catch (e) {{
                            console.error("Next/previous navigation error:", e);
                        }}
                    }})();
                """
                self.exec_js(script)

    def on_find_back_clicked(self, btn):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            # Save current direction
            backward = self.search_backwards_check.get_active()
            # Temporarily flip direction for initial search
            self.search_backwards_check.set_active(not backward)
            self.find_text(search_text)
            # Restore direction
            self.search_backwards_check.set_active(backward)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            else:
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            
            # Update dialog title with match count
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            if not self.highlight_all_check.get_active():
                self.clear_search_highlights()
                self.highlight_current_match()
            else:
                # Highlight all again with new current index
                script = f"""
                    (function() {{
                        try {{
                            window.currentSearchMatch = {self.current_search_match};
                            
                            // Remove current-match class from any existing elements
                            document.querySelectorAll('.search-highlight.current-match').forEach(el => {{
                                el.classList.remove('current-match');
                                el.style.outline = '';
                            }});
                            
                            // Add current-match to the new current match
                            let current = document.querySelector('.search-highlight[data-match-index="{self.current_search_match}"]');
                            if (current) {{
                                current.classList.add('current-match');
                                current.style.outline = '2px solid blue';
                                current.scrollIntoView({{
                                    behavior: 'smooth',
                                    block: 'center'
                                }});
                            }}
                        }} catch (e) {{
                            console.error("Next/previous navigation error:", e);
                        }}
                    }})();
                """
                self.exec_js(script)

    def on_search_close_clicked(self, btn):
        self.clear_search_highlights()
        self.search_matches = []
        self.current_search_match = 0
        self.search_dialog.destroy()

    def clear_search_highlights(self):
        script = """
            (function() {
                try {
                    // Remove all search highlights
                    document.querySelectorAll('.search-highlight, .temp-highlight').forEach(h => {
                        if (h.parentNode) {
                            let parent = h.parentNode;
                            parent.replaceChild(document.createTextNode(h.textContent), h);
                            parent.normalize();
                        }
                    });
                    
                    // Clear selection
                    window.getSelection().removeAllRanges();
                } catch (e) {
                    console.error("Clear highlights error:", e);
                }
            })();
        """
        self.exec_js(script)

################################ fix duplication of search
    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
            
        script = f"""
            (function() {{
                try {{
                    window.currentSearchMatch = {self.current_search_match};
                    let matches = window.searchMatches || [];
                    let index = {self.current_search_match};
                    
                    if (index >= 0 && index < matches.length) {{
                        let match = matches[index];
                        
                        // Create a range for this match
                        let range = document.createRange();
                        range.setStart(match.node, match.start);
                        range.setEnd(match.node, match.end);
                        
                        // Select the text
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        
                        // Make sure it's visible
                        match.node.parentElement.scrollIntoView({{ 
                            behavior: 'smooth', 
                            block: 'center' 
                        }});
                        
                        // Remove any existing temporary highlights
                        document.querySelectorAll('.temp-highlight').forEach(el => {{
                            if (el.parentNode) {{
                                let parent = el.parentNode;
                                let text = el.textContent;
                                parent.replaceChild(document.createTextNode(text), el);
                                parent.normalize();
                            }}
                        }});
                        
                        // Create a highlight element but use a different approach
                        // Instead of extracting content, just mark positions with the original content
                        let highlightText = match.text;
                        let highlightNode = match.node;
                        
                        // Split the text node at the match boundaries
                        let beforeText = highlightNode.splitText(match.start);
                        let afterText = beforeText.splitText(match.end - match.start);
                        
                        // Create a span around the middle (match) portion
                        let span = document.createElement('span');
                        span.className = 'temp-highlight';
                        span.style.backgroundColor = 'yellow';
                        
                        // Replace the middle node with our span
                        highlightNode.parentNode.replaceChild(span, beforeText);
                        span.appendChild(beforeText);
                        
                        // Remove the highlight after a short time
                        setTimeout(() => {{
                            if (span.parentNode) {{
                                let parent = span.parentNode;
                                let fragment = document.createDocumentFragment();
                                while (span.firstChild) {{
                                    fragment.appendChild(span.firstChild);
                                }}
                                parent.replaceChild(fragment, span);
                                parent.normalize();
                            }}
                        }}, 1500);
                    }}
                }} catch (e) {{
                    console.error("Highlight current match error:", e);
                }}
            }})();
        """
        self.exec_js(script)
        
        # Update dialog title with match count
        if self.search_matches:
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")

################################ highlight all fix?
    def highlight_all(self):
        # First clear any existing highlights
        self.clear_search_highlights()
        
        script = """
            (function() {
                try {
                    if (!window.searchMatches || window.searchMatches.length === 0) {
                        return;
                    }
                    
                    // Group matches by text node to process them together
                    let nodeMatches = new Map();
                    for (let i = 0; i < window.searchMatches.length; i++) {
                        let match = window.searchMatches[i];
                        if (!nodeMatches.has(match.node)) {
                            nodeMatches.set(match.node, []);
                        }
                        nodeMatches.get(match.node).push({
                            index: i,
                            start: match.start,
                            end: match.end,
                            text: match.text
                        });
                    }
                    
                    // Process each text node separately, from back to front for each node
                    nodeMatches.forEach((matches, textNode) => {
                        // Sort matches in reverse order (process from end to beginning)
                        matches.sort((a, b) => b.start - a.start);
                        
                        let parentNode = textNode.parentNode;
                        if (!parentNode) return;
                        
                        // Process each match for this text node
                        matches.forEach(match => {
                            // Create a range for this match
                            let range = document.createRange();
                            range.setStart(textNode, match.start);
                            range.setEnd(textNode, match.end);
                            
                            // Create a highlight span
                            let span = document.createElement('span');
                            span.className = 'search-highlight';
                            span.style.backgroundColor = 'yellow';
                            span.setAttribute('data-match-index', match.index);
                            
                            try {
                                // Split the text node and insert our span
                                let matchText = textNode.splitText(match.start);
                                matchText.splitText(match.end - match.start);
                                parentNode.replaceChild(span, matchText);
                                span.appendChild(matchText);
                            } catch(e) {
                                console.error('Error highlighting match', match.index, e);
                            }
                        });
                    });
                    
                    // Scroll to current match and highlight it
                    setTimeout(() => {
                        window.currentSearchMatch = 0; // Start with the first match
                        let current = document.querySelector('.search-highlight[data-match-index="0"]');
                        if (current) {
                            current.classList.add('current-match');
                            current.style.outline = '2px solid blue';
                            current.scrollIntoView({
                                behavior: 'smooth',
                                block: 'center'
                            });
                        }
                    }, 100);
                } catch (e) {
                    console.error("Highlight all error:", e);
                }
            })();
        """
        self.exec_js(script)
############################################# find next/back highlight match fix?
    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            else:
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            
            # Update dialog title with match count
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            if self.highlight_all_check.get_active():
                # Just update the current match highlighting when all matches are already highlighted
                script = f"""
                    (function() {{
                        try {{
                            window.currentSearchMatch = {self.current_search_match};
                            
                            // Remove current-match class from any existing elements
                            document.querySelectorAll('.search-highlight.current-match').forEach(el => {{
                                el.classList.remove('current-match');
                                el.style.outline = '';
                            }});
                            
                            // Add current-match to the new current match
                            let current = document.querySelector('.search-highlight[data-match-index="{self.current_search_match}"]');
                            if (current) {{
                                current.classList.add('current-match');
                                current.style.outline = '2px solid blue';
                                current.scrollIntoView({{
                                    behavior: 'smooth',
                                    block: 'center'
                                }});
                            }}
                        }} catch (e) {{
                            console.error("Next/previous navigation error:", e);
                        }}
                    }})();
                """
                self.exec_js(script)
            else:
                # For single-match mode, we need to clear and re-highlight
                self.clear_search_highlights()
                self.highlight_current_match()

    def on_find_back_clicked(self, btn):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            # Save current direction
            backward = self.search_backwards_check.get_active()
            # Temporarily flip direction for initial search
            self.search_backwards_check.set_active(not backward)
            self.find_text(search_text)
            # Restore direction
            self.search_backwards_check.set_active(backward)
            return

        if self.search_matches:
            if self.search_backwards_check.get_active():
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            else:
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            
            # Update dialog title with match count
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            if self.highlight_all_check.get_active():
                # Just update the current match highlighting when all matches are already highlighted
                script = f"""
                    (function() {{
                        try {{
                            window.currentSearchMatch = {self.current_search_match};
                            
                            // Remove current-match class from any existing elements
                            document.querySelectorAll('.search-highlight.current-match').forEach(el => {{
                                el.classList.remove('current-match');
                                el.style.outline = '';
                            }});
                            
                            // Add current-match to the new current match
                            let current = document.querySelector('.search-highlight[data-match-index="{self.current_search_match}"]');
                            if (current) {{
                                current.classList.add('current-match');
                                current.style.outline = '2px solid blue';
                                current.scrollIntoView({{
                                    behavior: 'smooth',
                                    block: 'center'
                                }});
                            }}
                        }} catch (e) {{
                            console.error("Next/previous navigation error:", e);
                        }}
                    }})();
                """
                self.exec_js(script)
            else:
                # For single-match mode, we need to clear and re-highlight
                self.clear_search_highlights()
                self.highlight_current_match()

    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
            
        script = f"""
            (function() {{
                try {{
                    window.currentSearchMatch = {self.current_search_match};
                    let matches = window.searchMatches || [];
                    let index = {self.current_search_match};
                    
                    if (index >= 0 && index < matches.length) {{
                        let match = matches[index];
                        
                        // Create a range for this match
                        let range = document.createRange();
                        range.setStart(match.node, match.start);
                        range.setEnd(match.node, match.end);
                        
                        // Select the text
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        
                        // Make sure it's visible
                        match.node.parentElement.scrollIntoView({{ 
                            behavior: 'smooth', 
                            block: 'center' 
                        }});
                        
                        // Create a highlight span
                        let span = document.createElement('span');
                        span.className = 'temp-highlight';
                        span.style.backgroundColor = 'yellow';
                        
                        try {{
                            // Use surroundContents for simple highlighting (should work for single match)
                            range.surroundContents(span);
                            
                            // Remove the highlight after a delay
                            setTimeout(() => {{
                                if (span.parentNode) {{
                                    let parent = span.parentNode;
                                    let text = span.textContent;
                                    parent.replaceChild(document.createTextNode(text), span);
                                    parent.normalize();
                                }}
                            }}, 1500);
                        }} catch(e) {{
                            console.error("Error highlighting match:", e);
                            
                            // Fallback to selection only if highlighting fails
                            match.node.parentElement.style.backgroundColor = 'yellow';
                            setTimeout(() => {{
                                match.node.parentElement.style.backgroundColor = '';
                            }}, 1500);
                        }}
                    }}
                }} catch (e) {{
                    console.error("Highlight current match error:", e);
                }}
            }})();
        """
        self.exec_js(script)
        
        # Update dialog title with match count
        if self.search_matches:
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
##########################    fix???        #####################
    def highlight_current_match(self):
        if not self.search_matches or self.current_search_match < 0 or self.current_search_match >= len(self.search_matches):
            return
            
        script = f"""
            (function() {{
                try {{
                    window.currentSearchMatch = {self.current_search_match};
                    let matches = window.searchMatches || [];
                    let index = {self.current_search_match};
                    
                    if (index >= 0 && index < matches.length) {{
                        let match = matches[index];
                        
                        // Remove any existing temporary highlights
                        document.querySelectorAll('.temp-highlight').forEach(el => {{
                            if (el.parentNode) {{
                                let parent = el.parentNode;
                                let text = el.textContent;
                                parent.replaceChild(document.createTextNode(text), el);
                                parent.normalize();
                            }}
                        }});
                        
                        // Create a temporary styled div for highlighting
                        let highlightDiv = document.createElement('div');
                        highlightDiv.className = 'temp-highlight';
                        highlightDiv.style.position = 'absolute';
                        highlightDiv.style.backgroundColor = 'yellow';
                        highlightDiv.style.opacity = '0.5';
                        highlightDiv.style.pointerEvents = 'none';
                        document.body.appendChild(highlightDiv);
                        
                        // Create a range and get its client rect
                        let range = document.createRange();
                        range.setStart(match.node, match.start);
                        range.setEnd(match.node, match.end);
                        
                        // Select the text
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        
                        // Position the highlight div over the selection
                        let rects = range.getClientRects();
                        for (let i = 0; i < rects.length; i++) {{
                            let rect = rects[i];
                            let div = document.createElement('div');
                            div.className = 'temp-highlight';
                            div.style.position = 'absolute';
                            div.style.left = (rect.left + window.scrollX) + 'px';
                            div.style.top = (rect.top + window.scrollY) + 'px';
                            div.style.width = rect.width + 'px';
                            div.style.height = rect.height + 'px';
                            div.style.backgroundColor = 'yellow';
                            div.style.opacity = '0.5';
                            div.style.pointerEvents = 'none';
                            document.body.appendChild(div);
                        }}
                        
                        // Scroll the match into view
                        match.node.parentElement.scrollIntoView({{ 
                            behavior: 'smooth', 
                            block: 'center' 
                        }});
                        
                        // Remove highlights after delay
                        setTimeout(() => {{
                            document.querySelectorAll('.temp-highlight').forEach(el => {{
                                if (el.parentNode) {{
                                    el.parentNode.removeChild(el);
                                }}
                            }});
                        }}, 1500);
                    }}
                }} catch (e) {{
                    console.error("Highlight current match error:", e);
                }}
            }})();
        """
        self.exec_js(script)
        
        # Update dialog title with match count
        if self.search_matches:
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            
    def highlight_all(self):
        # First clear any existing highlights
        self.clear_search_highlights()
        
        script = """
            (function() {
                try {
                    if (!window.searchMatches || window.searchMatches.length === 0) {
                        return;
                    }
                    
                    // First, remove any existing overlays
                    document.querySelectorAll('.search-highlight-overlay').forEach(el => {
                        if (el.parentNode) {
                            el.parentNode.removeChild(el);
                        }
                    });
                    
                    // Create a container for all overlays
                    let container = document.createElement('div');
                    container.className = 'search-highlight-container';
                    container.style.position = 'absolute';
                    container.style.top = '0';
                    container.style.left = '0';
                    container.style.pointerEvents = 'none';
                    container.style.zIndex = '1000';
                    document.body.appendChild(container);
                    
                    // Process each match
                    for (let i = 0; i < window.searchMatches.length; i++) {
                        let match = window.searchMatches[i];
                        
                        // Create a range for this match
                        let range = document.createRange();
                        range.setStart(match.node, match.start);
                        range.setEnd(match.node, match.end);
                        
                        // Get the client rects for this range
                        let rects = range.getClientRects();
                        for (let j = 0; j < rects.length; j++) {
                            let rect = rects[j];
                            
                            // Create an overlay div for this rect
                            let overlay = document.createElement('div');
                            overlay.className = 'search-highlight-overlay';
                            overlay.setAttribute('data-match-index', i);
                            overlay.style.position = 'absolute';
                            overlay.style.left = (rect.left + window.scrollX) + 'px';
                            overlay.style.top = (rect.top + window.scrollY) + 'px';
                            overlay.style.width = rect.width + 'px';
                            overlay.style.height = rect.height + 'px';
                            overlay.style.backgroundColor = 'yellow';
                            overlay.style.opacity = '0.5';
                            overlay.style.pointerEvents = 'none';
                            
                            container.appendChild(overlay);
                        }
                    }
                    
                    // Highlight current match
                    window.currentSearchMatch = 0;
                    let currentOverlays = document.querySelectorAll('.search-highlight-overlay[data-match-index="0"]');
                    currentOverlays.forEach(overlay => {
                        overlay.style.backgroundColor = 'orange';
                        overlay.style.opacity = '0.7';
                    });
                    
                    // Scroll to current match
                    if (window.searchMatches.length > 0) {
                        let match = window.searchMatches[0];
                        match.node.parentElement.scrollIntoView({
                            behavior: 'smooth',
                            block: 'center'
                        });
                    }
                } catch (e) {
                    console.error("Highlight all error:", e);
                }
            })();
        """
        self.exec_js(script)
        
        
        
    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text()
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            # Update current match index
            if self.search_backwards_check.get_active():
                self.current_search_match -= 1
                if self.current_search_match < 0:
                    if self.wrap_around_check.get_active():
                        self.current_search_match = len(self.search_matches) - 1
                    else:
                        self.current_search_match = 0
                        return
            else:
                self.current_search_match += 1
                if self.current_search_match >= len(self.search_matches):
                    if self.wrap_around_check.get_active():
                        self.current_search_match = 0
                    else:
                        self.current_search_match = len(self.search_matches) - 1
                        return
            
            # Update dialog title with match count
            self.search_dialog.set_heading(f"Find ({self.current_search_match + 1} of {len(self.search_matches)})")
            
            if self.highlight_all_check.get_active():
                # Update the current highlighted match in overlay mode
                script = f"""
                    (function() {{
                        try {{
                            window.currentSearchMatch = {self.current_search_match};
                            
                            // Reset all overlays
                            document.querySelectorAll('.search-highlight-overlay').forEach(overlay => {{
                                overlay.style.backgroundColor = 'yellow';
                                overlay.style.opacity = '0.5';
                            }});
                            
                            // Highlight current overlays
                            let currentOverlays = document.querySelectorAll('.search-highlight-overlay[data-match-index="{self.current_search_match}"]');
                            currentOverlays.forEach(overlay => {{
                                overlay.style.backgroundColor = 'orange';
                                overlay.style.opacity = '0.7';
                            }});
                            
                            // Scroll to match
                            if (window.searchMatches && window.searchMatches.length > {self.current_search_match}) {{
                                let match = window.searchMatches[{self.current_search_match}];
                                match.node.parentElement.scrollIntoView({{
                                    behavior: 'smooth',
                                    block: 'center'
                                }});
                            }}
                        }} catch (e) {{
                            console.error("Navigation error:", e);
                        }}
                    }})();
                """
                self.exec_js(script)
            else:
                # For individual highlighting
                self.clear_search_highlights()
                self.highlight_current_match()
                
##################### search clear?
    def on_search_close_clicked(self, btn):
        # Clear all types of highlights
        script = """
            (function() {
                try {
                    // Remove all search highlights (for text node modifications)
                    document.querySelectorAll('.search-highlight, .temp-highlight').forEach(h => {
                        if (h.parentNode) {
                            let parent = h.parentNode;
                            parent.replaceChild(document.createTextNode(h.textContent), h);
                            parent.normalize();
                        }
                    });
                    
                    // Remove all highlight overlays
                    document.querySelectorAll('.search-highlight-overlay, .temp-highlight').forEach(el => {
                        if (el.parentNode) {
                            el.parentNode.removeChild(el);
                        }
                    });
                    
                    // Remove highlight container if it exists
                    let container = document.querySelector('.search-highlight-container');
                    if (container && container.parentNode) {
                        container.parentNode.removeChild(container);
                    }
                    
                    // Clear selection
                    window.getSelection().removeAllRanges();
                } catch (e) {
                    console.error("Clear highlights error:", e);
                }
            })();
        """
        self.exec_js(script)
        
        # Reset search state
        self.search_matches = []
        self.current_search_match = 0
        self.search_dialog.destroy()                
      
    def clear_search_highlights(self):
        script = """
            (function() {
                try {
                    // Remove all search highlights (for text node modifications)
                    document.querySelectorAll('.search-highlight, .temp-highlight').forEach(h => {
                        if (h.parentNode) {
                            let parent = h.parentNode;
                            parent.replaceChild(document.createTextNode(h.textContent), h);
                            parent.normalize();
                        }
                    });
                    
                    // Remove all highlight overlays
                    document.querySelectorAll('.search-highlight-overlay, .temp-highlight').forEach(el => {
                        if (el.parentNode) {
                            el.parentNode.removeChild(el);
                        }
                    });
                    
                    // Clear selection
                    window.getSelection().removeAllRanges();
                } catch (e) {
                    console.error("Clear highlights error:", e);
                }
            })();
        """
        self.exec_js(script)          
#########################################################################
if __name__ == "__main__":
    app = Writer()
    app.run()
