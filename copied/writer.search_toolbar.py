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
            .search-toolbar { padding: 6px; background-color: rgba(127, 127, 127, 0.05); }
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

        # Bottom toolbar for Find/Replace
        self.search_toolbar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.search_toolbar.add_css_class("search-toolbar")
        self.search_toolbar.set_visible(False)  # Hidden by default
        self.find_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.replace_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        scroll.set_child(self.webview)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox)
        content_box.append(scroll)
        content_box.append(self.search_toolbar)
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
            ("edit-find", self.on_search_clicked),
            ("edit-find-replace", self.on_replace_clicked),
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
            #GLib.idle_add(self.webview.grab_focus)
            self.webview.grab_focus()

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

    def check_save_before_new(self):
        if self.is_modified:
            dialog = Adw.MessageDialog(transient_for=self, heading="Save changes?", modal=True)
            dialog.set_body("Do you want to save changes to this document before creating a new one?")
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("no", "No")
            dialog.add_response("yes", "Yes")
            dialog.set_response_appearance("yes", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", self.on_new_response)
            dialog.present()
            return True
        return False

    def on_new_response(self, dialog, response):
        if response == "yes":
            self.on_save_clicked(None)
            self.on_new_clicked(None)
        elif response == "no":
            self.on_new_clicked(None)
        dialog.destroy()

    def clear_ignore_changes(self):
        self.ignore_changes = False
        return False

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
        self.webview.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, self.show_search_toolbar, None)

    def on_replace_clicked(self, btn):
        self.webview.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, self.show_replace_toolbar, None)

    def show_search_toolbar(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            selected_text = js_value.to_string() if js_value else ""
        except Exception as e:
            print(f"Error getting selection: {e}")
            selected_text = ""

        # Clear previous content in find_box
        child = self.find_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.find_box.remove(child)
            child = next_child

        # Clear previous content in replace_box
        child = self.replace_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.replace_box.remove(child)
            child = next_child

        # Clear previous content in search_toolbar
        child = self.search_toolbar.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.search_toolbar.remove(child)
            child = next_child

        # Find Entry
        self.search_entry = Gtk.Entry(placeholder_text="Find")
        self.search_entry.set_text(selected_text)
        self.search_entry.connect("activate", self.on_find_next_clicked)
        self.find_box.append(self.search_entry)

        # Buttons
        back_btn = Gtk.Button(label="Back")
        back_btn.connect("clicked", self.on_find_back_clicked)
        self.find_box.append(back_btn)

        next_btn = Gtk.Button(label="Next")
        next_btn.connect("clicked", self.on_find_next_clicked)
        self.find_box.append(next_btn)

        # Checkboxes
        self.highlight_all_check = Gtk.CheckButton(label="Highlight All")
        self.highlight_all_check.connect("toggled", self.on_highlight_all_toggled)
        self.find_box.append(self.highlight_all_check)

        self.match_case_check = Gtk.CheckButton(label="Match Case")
        self.find_box.append(self.match_case_check)

        self.match_entire_word_check = Gtk.CheckButton(label="Match Entire Word")
        self.find_box.append(self.match_entire_word_check)

        # Close button
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self.on_search_close_clicked)
        self.find_box.append(close_btn)

        # Add only Find box to toolbar
        self.search_toolbar.append(self.find_box)
        self.search_toolbar.set_visible(True)

        # Explicitly grab focus to the search entry
        self.search_entry.grab_focus()

        if selected_text:
            self.find_text(selected_text)

    def show_replace_toolbar(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            selected_text = js_value.to_string() if js_value else ""
        except Exception as e:
            print(f"Error getting selection: {e}")
            selected_text = ""

        # Clear previous content in find_box
        child = self.find_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.find_box.remove(child)
            child = next_child

        # Clear previous content in replace_box
        child = self.replace_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.replace_box.remove(child)
            child = next_child

        # Clear previous content in search_toolbar
        child = self.search_toolbar.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.search_toolbar.remove(child)
            child = next_child

        # Find Entry
        self.search_entry = Gtk.Entry(placeholder_text="Find")
        self.search_entry.set_text(selected_text)
        self.search_entry.connect("activate", self.on_find_next_clicked)
        self.find_box.append(self.search_entry)

        back_btn = Gtk.Button(label="Back")
        back_btn.connect("clicked", self.on_find_back_clicked)
        self.find_box.append(back_btn)

        next_btn = Gtk.Button(label="Next")
        next_btn.connect("clicked", self.on_find_next_clicked)
        self.find_box.append(next_btn)

        self.highlight_all_check = Gtk.CheckButton(label="Highlight All")
        self.highlight_all_check.connect("toggled", self.on_highlight_all_toggled)
        self.find_box.append(self.highlight_all_check)

        self.match_case_check = Gtk.CheckButton(label="Match Case")
        self.find_box.append(self.match_case_check)

        self.match_entire_word_check = Gtk.CheckButton(label="Match Entire Word")
        self.find_box.append(self.match_entire_word_check)

        # Close button for Find
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self.on_search_close_clicked)
        self.find_box.append(close_btn)

        # Replace Entry and Buttons
        self.replace_entry = Gtk.Entry(placeholder_text="Replace with")
        self.replace_entry.connect("activate", self.on_replace_clicked_handler)
        self.replace_box.append(self.replace_entry)

        replace_btn = Gtk.Button(label="Replace")
        replace_btn.connect("clicked", self.on_replace_clicked_handler)
        self.replace_box.append(replace_btn)

        replace_all_btn = Gtk.Button(label="Replace All")
        replace_all_btn.connect("clicked", self.on_replace_all_clicked)
        self.replace_box.append(replace_all_btn)

        # Add both Find and Replace boxes to toolbar
        self.search_toolbar.append(self.find_box)
        self.search_toolbar.append(self.replace_box)
        self.search_toolbar.set_visible(True)

        # Explicitly grab focus to the search entry
        self.search_entry.grab_focus()

        if selected_text:
            self.find_text(selected_text)

    def find_text(self, search_text):
        self.clear_search_highlights()
        
        # Fix flags: 'g' always, 'i' only if Match Case is unchecked
        flags = 'g'
        if not self.match_case_check.get_active():
            flags += 'i'
        
        # Escape special regex characters
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
                        regex.lastIndex = 0;
                        let match;
                        while ((match = regex.exec(text)) !== null) {{
                            matches.push({{
                                node: node,
                                start: match.index,
                                end: match.index + match[0].length,
                                text: match[0]
                            }});
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
                    return JSON.stringify({{ count: 0, matches: [] }});
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
                    self.current_search_match = 0
                    if self.highlight_all_check.get_active():
                        self.highlight_all()
                    else:
                        self.highlight_current_match()
                    self.search_entry.set_text(f"{self.last_search_text} {self.current_search_match + 1} of {match_count}")
                else:
                    print("No matches found")
                    self.search_entry.set_text(f"{self.last_search_text} (No matches)")
            else:
                self.search_matches = []
                self.current_search_match = 0
                self.search_entry.set_text(f"{self.last_search_text} (No matches)")
        except Exception as e:
            print(f"Error finding matches: {e}")
            self.search_matches = []
            self.current_search_match = 0
            self.search_entry.set_text(f"{self.last_search_text} (Error)")

    def highlight_all(self):
        self.clear_search_highlights()
        
        script = """
            (function() {
                try {
                    if (!window.searchMatches || window.searchMatches.length === 0) return;
                    
                    let nodeMatches = new Map();
                    for (let i = 0; i < window.searchMatches.length; i++) {
                        let match = window.searchMatches[i];
                        if (!nodeMatches.has(match.node)) {
                            nodeMatches.set(match.node, []);
                        }
                        nodeMatches.get(match.node).push({
                            index: i,
                            start: match.start,
                            end: match.end
                        });
                    }
                    
                    nodeMatches.forEach((matches, textNode) => {
                        matches.sort((a, b) => b.start - a.start);
                        let parentNode = textNode.parentNode;
                        if (!parentNode) return;
                        
                        matches.forEach(match => {
                            let range = document.createRange();
                            range.setStart(textNode, match.start);
                            range.setEnd(textNode, match.end);
                            let span = document.createElement('span');
                            span.className = 'search-highlight';
                            span.style.backgroundColor = 'yellow';
                            span.setAttribute('data-match-index', match.index);
                            try {
                                let matchText = textNode.splitText(match.start);
                                matchText.splitText(match.end - match.start);
                                parentNode.replaceChild(span, matchText);
                                span.appendChild(matchText);
                            } catch(e) {
                                console.error('Error highlighting:', e);
                            }
                        });
                    });
                    
                    let current = document.querySelector(`.search-highlight[data-match-index="${window.currentSearchMatch || 0}"]`);
                    if (current) {
                        current.style.outline = '2px solid blue';
                        current.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
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
                        
                        let span = document.createElement('span');
                        span.className = 'temp-highlight';
                        span.style.backgroundColor = 'yellow';
                        try {{
                            range.surroundContents(span);
                            setTimeout(() => {{
                                if (span.parentNode) {{
                                    let parent = span.parentNode;
                                    parent.replaceChild(document.createTextNode(span.textContent), span);
                                    parent.normalize();
                                }}
                            }}, 1500);
                        }} catch(e) {{
                            console.error("Highlight error:", e);
                        }}
                    }}
                }} catch (e) {{
                    console.error("Highlight current match error:", e);
                }}
            }})();
        """
        self.exec_js(script)
        self.search_entry.set_text(f"{self.last_search_text} {self.current_search_match + 1} of {len(self.search_matches)}")

    def on_highlight_all_toggled(self, check):
        if check.get_active():
            self.highlight_all()
        else:
            self.clear_search_highlights()
            if self.search_matches:
                self.highlight_current_match()

    def on_find_next_clicked(self, btn_or_entry):
        search_text = self.search_entry.get_text().split(" ")[0]  # Extract search term if count is appended
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            self.current_search_match = (self.current_search_match + 1) % len(self.search_matches)
            if self.highlight_all_check.get_active():
                script = f"""
                    (function() {{
                        document.querySelectorAll('.search-highlight').forEach(el => {{
                            el.style.outline = '';
                        }});
                        let current = document.querySelector('.search-highlight[data-match-index="{self.current_search_match}"]');
                        if (current) {{
                            current.style.outline = '2px solid blue';
                            current.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }})();
                """
                self.exec_js(script)
            else:
                self.clear_search_highlights()
                self.highlight_current_match()
            self.search_entry.set_text(f"{self.last_search_text} {self.current_search_match + 1} of {len(self.search_matches)}")

    def on_find_back_clicked(self, btn):
        search_text = self.search_entry.get_text().split(" ")[0]
        if not search_text:
            return
        if not self.search_matches or search_text != self.last_search_text:
            self.find_text(search_text)
            return

        if self.search_matches:
            self.current_search_match = (self.current_search_match - 1) if self.current_search_match > 0 else len(self.search_matches) - 1
            if self.highlight_all_check.get_active():
                script = f"""
                    (function() {{
                        document.querySelectorAll('.search-highlight').forEach(el => {{
                            el.style.outline = '';
                        }});
                        let current = document.querySelector('.search-highlight[data-match-index="{self.current_search_match}"]');
                        if (current) {{
                            current.style.outline = '2px solid blue';
                            current.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }})();
                """
                self.exec_js(script)
            else:
                self.clear_search_highlights()
                self.highlight_current_match()
            self.search_entry.set_text(f"{self.last_search_text} {self.current_search_match + 1} of {len(self.search_matches)}")

    def on_search_close_clicked(self, btn):
        self.clear_search_highlights()
        self.search_matches = []
        self.current_search_match = 0
        self.search_toolbar.set_visible(False)

    def clear_search_highlights(self):
        script = """
            (function() {
                try {
                    document.querySelectorAll('.search-highlight, .temp-highlight').forEach(h => {
                        if (h.parentNode) {
                            let parent = h.parentNode;
                            parent.replaceChild(document.createTextNode(h.textContent), h);
                            parent.normalize();
                        }
                    });
                    window.getSelection().removeAllRanges();
                } catch (e) {
                    console.error("Clear highlights error:", e);
                }
            })();
        """
        self.exec_js(script)

    def on_replace_clicked_handler(self, btn_or_entry):
        find_text = self.search_entry.get_text().split(" ")[0]
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
        find_text = self.search_entry.get_text().split(" ")[0]
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
            elif keyval == Gdk.KEY_f:
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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
                #self.webview.grab_focus()
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

    def on_close_request(self, *args):
        if self.is_modified:
            dialog = Adw.MessageDialog(transient_for=self, heading="Save changes?", modal=True)
            dialog.set_body("Do you want to save changes to this document before closing?")
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("no", "No")
            dialog.add_response("yes", "Yes")
            dialog.set_response_appearance("yes", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", self.on_close_response)
            dialog.present()
            return True
        return False

    def on_close_response(self, dialog, response):
        if response == "yes":
            self.on_save_clicked(None)
            self.destroy()
        elif response == "no":
            self.destroy()
        dialog.destroy()

if __name__ == "__main__":
    app = Writer()
    app.run()
