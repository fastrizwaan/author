#!/usr/bin/env python3

import os
import gi, json
# Add re import for load_html_callback
import re, sys

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

        # --- Page Layout Settings ---
        self.page_width_inches = 8.5
        self.page_height_inches = 11.0
        self.page_margin_inches = 1.0 # Equal margin for top, right, bottom, left
        self.page_gap_px = 20        # Gap between visual pages (applied as bottom margin)

        # CSS Provider for GTK widgets
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(b"""
            .toolbar-container { padding: 6px; background-color: rgba(127, 127, 127, 0.2); }
            .flat { background: none; border-radius: 5px; }
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

        # Main layout Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Toolbar View
        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        header.add_css_class("flat-header")
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        toolbar_view.add_top_bar(header)

        # Scrolled Window for WebView
        # Set policy to NEVER for horizontal scrollbar
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.webview = WebKit.WebView(editable=True)

        user_content = self.webview.get_user_content_manager()
        user_content.register_script_message_handler('contentChanged')
        user_content.connect('script-message-received::contentChanged', self.on_content_changed_js)
        user_content.register_script_message_handler('selectionChanged')
        user_content.connect('script-message-received::selectionChanged', self.on_selection_changed)
        self.webview.connect('load-changed', self.on_webview_load)

        # --- Initial HTML with Page Layout CSS ---
        self.initial_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        /* Styles for the area OUTSIDE the page */
        html {{
            background-color: #ccc; /* Grey background */
        }}
        body {{
            margin: 0; /* Remove default body margin */
            padding-top: {self.page_gap_px}px; /* Space above the first page */
            /* Center the .page(s) horizontally */
            display: flex;
            flex-direction: column; /* Stack pages vertically */
            align-items: center; /* Center pages horizontally */
            min-height: 100vh; /* Ensure body takes full viewport height */

            /* Default text styles inherited by content inside .page */
            font-family: serif;
            font-size: 12pt;
            line-height: 1.5;
        }}

        /* The Page Itself */
        .page {{
            width: {self.page_width_inches}in;
            min-height: {self.page_height_inches}in; /* Content will make it grow taller */
            padding: {self.page_margin_inches}in; /* Page margins */
            background-color: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.2); /* Subtle shadow */
            box-sizing: border-box; /* Include padding in width/height */
            outline: none; /* Prevent browser focus outline */
            /* Add gap below each page */
            margin-bottom: {self.page_gap_px}px;

            /* NOTE: This CSS provides visual styling only. */
            /* It does NOT automatically create new pages or */
            /* flow text between them when content overflows. */
            /* The single .page div will simply grow taller. */
        }}

        /* Prevent browser focus outline on the body */
         body:focus {{ outline: none; }}

        /* Dark Mode Styles */
        @media (prefers-color-scheme: dark) {{
            html {{ background-color: #333; }} /* Darker grey outside */
            .page {{ background-color: #1e1e1e; color: #e0e0e0; }}
        }}
        /* Light Mode Styles (redundant if default is light, but explicit) */
        @media (prefers-color-scheme: light) {{
            html {{ background-color: #ccc; }}
            .page {{ background-color: #ffffff; color: #000000; }}
        }}
    </style>
</head>
<body contenteditable="true">
    <div class="page">
        <p>\u200B</p>
    </div>

</body>
</html>"""
        # --- End Initial HTML ---

        # Toolbar construction (Groups)
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

        # Toolbar Container FlowBox
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
        toolbars_flowbox.set_max_children_per_line(100) # Effectively make it horizontal
        toolbars_flowbox.add_css_class("toolbar-container")
        toolbars_flowbox.insert(file_toolbar_group, -1)
        toolbars_flowbox.insert(formatting_toolbar_group, -1)

        # Assemble Main Layout
        scroll.set_child(self.webview)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox) # Toolbar first
        content_box.append(scroll) # Then the editor area
        toolbar_view.set_content(content_box)

        # Load initial content
        self.webview.load_html(self.initial_html, "file:///")

        # --- Populate Toolbar Groups (No changes needed here) ---
        # ... (rest of toolbar population code remains the same) ...
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

        # Size dropdown
        self.size_range = [str(size) for size in [6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72, 96]]
        size_store = Gtk.StringList(strings=self.size_range)
        self.size_dropdown = Gtk.DropDown(model=size_store)
        try:
             default_size_index = self.size_range.index("12")
        except ValueError:
             default_size_index = 5 # Fallback index for 12pt
        self.size_dropdown.set_selected(default_size_index)
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

        self.align_left_btn.set_active(True) # Default alignment

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


        # Key Controller
        key_controller = Gtk.EventControllerKey.new()
        self.webview.add_controller(key_controller)
        key_controller.connect("key-pressed", self.on_key_pressed)

        # Close Request
        self.connect("close-request", self.on_close_request)

    def on_content_changed_js(self, manager, js_result):
        # Check if the initial content has loaded and we should ignore changes
        if getattr(self, 'ignore_changes', False):
            return
        # Check if the change is meaningful (more than just the initial setup)
        self.webview.evaluate_javascript(
            # Check if body content is more than just the page div with the initial placeholder
             """(function() {
                 const page = document.querySelector('.page');
                 if (!page) return false; // Should not happen
                 // Check if page content is effectively empty or just the placeholder
                 const content = page.innerHTML.trim();
                 if (content === '<p>\\u200B</p>' || content === '<p><br></p>' || content === '') {
                    return false;
                 }
                 return true; // Has actual content
             })()""",
            -1, None, None, None, self.check_meaningful_change, None
        )

    def check_meaningful_change(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            is_meaningful = js_value.to_boolean()
            if is_meaningful and not getattr(self, 'ignore_changes', False):
                self.is_modified = True
                self.update_title()
        except GLib.Error as e:
            print(f"Error checking meaningful change: {e}")
        except Exception as e: # Catch other potential JS errors
             print(f"Unexpected error in check_meaningful_change: {e}")


    def on_webview_load(self, webview, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            # Inject JavaScript for change detection and selection updates
            # No changes needed in the JS for the visual gap
            self.webview.evaluate_javascript("""
                (function() {
                    // Ensure cursor is placed correctly initially in the first page
                    let pageDiv = document.querySelector('.page'); // Target the first (and only) page
                    let p = pageDiv ? pageDiv.querySelector('p') : null;
                    if (p && p.firstChild) { // Ensure paragraph and its content exist
                        let range = document.createRange();
                        // Place cursor at the beginning of the zero-width space
                        range.setStart(p.firstChild, 0);
                        range.collapse(true); // Collapse to the start
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                    } else if (pageDiv) {
                        // Fallback if paragraph/content missing, place cursor at start of page div
                        let range = document.createRange();
                        range.setStart(pageDiv, 0);
                        range.collapse(true);
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                    }

                    // Debounce function
                    function debounce(func, wait) {
                        let timeout;
                        return function(...args) {
                            clearTimeout(timeout);
                            timeout = setTimeout(() => func.apply(this, args), wait);
                        };
                    }

                    // Content Change Detection
                    let lastContent = document.body.innerHTML;
                    const notifyChange = debounce(function() {
                        let currentContent = document.body.innerHTML;
                        if (currentContent !== lastContent) {
                            // Get content of the single page div for comparison
                            const pageContent = document.querySelector('.page')?.innerHTML.trim() ?? '';
                            const lastPageContent = new DOMParser().parseFromString(lastContent, 'text/html').querySelector('.page')?.innerHTML.trim() ?? '';

                            const simplifiedCurrent = pageContent.replace(/<p>\\u200B<\\/p>|<p><br><\\/p>|^\\s*$/g, '');
                            const simplifiedLast = lastPageContent.replace(/<p>\\u200B<\\/p>|<p><br><\\/p>|^\\s*$/g, '');

                            if (simplifiedCurrent !== simplifiedLast) {
                                 window.webkit.messageHandlers.contentChanged.postMessage('changed');
                            }
                            lastContent = currentContent;
                        }
                    }, 300);

                    // Event Listeners for Content Change
                    document.addEventListener('input', notifyChange);
                    document.addEventListener('paste', notifyChange);
                    document.addEventListener('cut', notifyChange);
                    document.addEventListener('mouseup', notifyChange);
                    document.addEventListener('keyup', (event) => {
                         if (['Enter', 'Backspace', 'Delete'].includes(event.key)) {
                              notifyChange();
                         }
                    });


                    // Selection Change Detection
                    const notifySelectionChange = debounce(function() {
                        const sel = window.getSelection();
                        let state = null; // Default to null

                        if (sel.rangeCount > 0) {
                            const range = sel.getRangeAt(0);
                            let element = range.startContainer;
                            if (element.nodeType === Node.TEXT_NODE) {
                                element = element.parentElement;
                            }
                            // Traverse up until we hit the page or body, or a block element
                            while (element && element.nodeType === Node.ELEMENT_NODE && !['P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'BODY', 'BLOCKQUOTE'].includes(element.tagName)) {
                                 element = element.parentElement;
                            }
                            // Ensure we have a valid element, fallback to page div
                            if (!element || element.nodeType !== Node.ELEMENT_NODE) {
                                element = document.querySelector('.page');
                            }

                            if (element) { // Check if element is valid before getting style
                                const style = window.getComputedStyle(element);
                                state = {
                                    bold: document.queryCommandState('bold'),
                                    italic: document.queryCommandState('italic'),
                                    underline: document.queryCommandState('underline'),
                                    strikethrough: document.queryCommandState('strikeThrough'), // Use strikeThrough here
                                    formatBlock: document.queryCommandValue('formatBlock').toLowerCase() || 'p',
                                    fontName: style.fontFamily.split(',')[0].replace(/['"]/g, '').trim(),
                                    fontSize: style.fontSize,
                                    insertUnorderedList: document.queryCommandState('insertUnorderedList'),
                                    insertOrderedList: document.queryCommandState('insertOrderedList'),
                                    justifyLeft: document.queryCommandState('justifyLeft'),
                                    justifyCenter: document.queryCommandState('justifyCenter'),
                                    justifyRight: document.queryCommandState('justifyRight'),
                                    justifyFull: document.queryCommandState('justifyFull')
                                };
                            }
                        }

                        // If state couldn't be determined, create a default state
                        if (!state) {
                             const pageElement = document.querySelector('.page');
                             const style = pageElement ? window.getComputedStyle(pageElement) : null;
                             state = {
                                bold: false, italic: false, underline: false, strikethrough: false,
                                formatBlock: 'p',
                                fontName: style ? style.fontFamily.split(',')[0].replace(/['"]/g, '').trim() : 'Sans',
                                fontSize: style ? style.fontSize : '16px', // ~12pt
                                insertUnorderedList: false, insertOrderedList: false,
                                justifyLeft: true, justifyCenter: false, justifyRight: false, justifyFull: false
                             };
                        }
                        // Always post a message, even if it's the default state
                        window.webkit.messageHandlers.selectionChanged.postMessage(JSON.stringify(state));

                    }, 150);

                    document.addEventListener('selectionchange', notifySelectionChange);
                    // Ensure initial state is sent even if selectionchange doesn't fire immediately
                    notifySelectionChange();
                })();
            """, -1, None, None, None, None, None)
            # Set ignore_changes flag briefly after load
            self.ignore_changes = True
            GLib.timeout_add(500, self.clear_ignore_changes)
            GLib.idle_add(self.webview.grab_focus)


    def on_selection_changed(self, user_content, message):
        # No changes needed here
        if message.is_string():
            try:
                state_str = message.to_string()
                state = json.loads(state_str)
                self.update_formatting_ui(state)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from selectionChanged: {e}")
                print(f"Received string: {state_str}")
            except Exception as e:
                 print(f"Unexpected error in on_selection_changed: {e}")
        else:
            print("Error: Expected a string message from selectionChanged, got something else")

    def update_formatting_ui(self, state=None):
         # No changes needed here
        if state:
            # --- Toggle Buttons ---
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
            # Ensure JS uses 'strikeThrough' for queryCommandState
            self.strikethrough_btn.set_active(state.get('strikethrough', False))
            self.strikethrough_btn.handler_unblock_by_func(self.on_strikethrough_toggled)

            # --- List Buttons ---
            self.bullet_btn.handler_block_by_func(self.on_bullet_list_toggled)
            self.bullet_btn.set_active(state.get('insertUnorderedList', False))
            self.bullet_btn.handler_unblock_by_func(self.on_bullet_list_toggled)

            self.number_btn.handler_block_by_func(self.on_number_list_toggled)
            self.number_btn.set_active(state.get('insertOrderedList', False))
            self.number_btn.handler_unblock_by_func(self.on_number_list_toggled)

            # --- Alignment Buttons ---
            is_center = state.get('justifyCenter', False)
            is_right = state.get('justifyRight', False)
            is_full = state.get('justifyFull', False)
            # queryCommandState('justifyLeft') might be true even if others are, default if others false
            is_left = state.get('justifyLeft', False) if not (is_center or is_right or is_full) else False
            # Ensure at least one is active, default to left
            if not (is_left or is_center or is_right or is_full):
                is_left = True

            align_states = {
                'justifyLeft': (self.align_left_btn, self.on_align_left, is_left),
                'justifyCenter': (self.align_center_btn, self.on_align_center, is_center),
                'justifyRight': (self.align_right_btn, self.on_align_right, is_right),
                'justifyFull': (self.align_justify_btn, self.on_align_justify, is_full)
            }
            for align, (btn, handler, is_active) in align_states.items():
                btn.handler_block_by_func(handler)
                btn.set_active(is_active)
                btn.handler_unblock_by_func(handler)

            # --- Paragraph Style (Heading) ---
            format_block = state.get('formatBlock', 'p').lower()
            headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
            try:
                 # Map div, blockquote etc also to Normal (p)
                 index = headings.index(format_block) if format_block in headings else 0
            except ValueError:
                 index = 0
            self.heading_dropdown.handler_block(self.heading_dropdown_handler)
            # Check if index is valid before setting
            if index < self.heading_dropdown.get_model().get_n_items():
                 self.heading_dropdown.set_selected(index)
            else:
                 self.heading_dropdown.set_selected(0) # Fallback
            self.heading_dropdown.handler_unblock(self.heading_dropdown_handler)

            # --- Font Family Detection ---
            detected_font_raw = state.get('fontName', self.current_font)
            detected_font = detected_font_raw.lower().strip()

            font_store = self.font_dropdown.get_model()
            final_font_index = Gtk.INVALID_LIST_POSITION
            if font_store:
                 exact_match_index = -1
                 partial_match_index = -1
                 # Find best match
                 for i in range(font_store.get_n_items()):
                     list_font_lower = font_store.get_string(i).lower()
                     if list_font_lower == detected_font:
                         exact_match_index = i
                         break
                     # Basic partial match (e.g., 'arial' matches 'arial black')
                     if partial_match_index == -1 and (detected_font.startswith(list_font_lower) or list_font_lower.startswith(detected_font)):
                          partial_match_index = i

                 if exact_match_index != -1:
                      final_font_index = exact_match_index
                 elif partial_match_index != -1:
                      final_font_index = partial_match_index
                 else:
                      # Fallback to current selection or default if no match
                      final_font_index = self.font_dropdown.get_selected()
                      if final_font_index == Gtk.INVALID_LIST_POSITION:
                           try:
                                final_font_index = [font_store.get_string(i).lower() for i in range(font_store.get_n_items())].index('sans')
                           except ValueError:
                                final_font_index = 0 # Absolute fallback

            if final_font_index != Gtk.INVALID_LIST_POSITION:
                 self.current_font = font_store.get_string(final_font_index)
                 self.font_dropdown.handler_block(self.font_dropdown_handler)
                 self.font_dropdown.set_selected(final_font_index)
                 self.font_dropdown.handler_unblock(self.font_dropdown_handler)


            # --- Font Size Detection ---
            font_size_str = state.get('fontSize', f'{self.current_font_size}pt') # Use current as fallback
            font_size_pt_str = self.current_font_size # Default to current

            try:
                # Prioritize 'pt' if available
                if font_size_str.endswith('pt'):
                    font_size_pt_str = str(round(float(font_size_str[:-2])))
                elif font_size_str.endswith('px'):
                    px_val = float(font_size_str[:-2])
                    # Approximate px to pt mapping (same as before)
                    if px_val <= 8: font_size_pt_str = '6'
                    elif px_val <= 11: font_size_pt_str = '8'
                    elif px_val <= 12: font_size_pt_str = '9'
                    elif px_val <= 13.3: font_size_pt_str = '10'
                    elif px_val <= 14.6: font_size_pt_str = '11'
                    elif px_val <= 16: font_size_pt_str = '12'
                    elif px_val <= 18.6: font_size_pt_str = '14'
                    elif px_val <= 21.3: font_size_pt_str = '16'
                    elif px_val <= 24: font_size_pt_str = '18'
                    elif px_val <= 26.6: font_size_pt_str = '20'
                    elif px_val <= 29.3: font_size_pt_str = '22'
                    elif px_val <= 32: font_size_pt_str = '24'
                    elif px_val <= 34.6: font_size_pt_str = '26'
                    elif px_val <= 37.3: font_size_pt_str = '28'
                    elif px_val <= 48: font_size_pt_str = '36'
                    elif px_val <= 64: font_size_pt_str = '48'
                    elif px_val <= 96: font_size_pt_str = '72'
                    else: font_size_pt_str = '96'
                elif '%' in font_size_str or 'em' in font_size_str or 'rem' in font_size_str:
                     # Relative sizes are hard, stick to current size
                     font_size_pt_str = self.current_font_size
                else: # Try converting directly if just a number string
                      font_size_pt_str = str(round(float(font_size_str)))
            except (ValueError, TypeError):
                 font_size_pt_str = self.current_font_size # Fallback on any error

            # Find closest available size in dropdown
            selected_size_index = Gtk.INVALID_LIST_POSITION
            try:
                 target_pt = int(font_size_pt_str)
                 # Find the index of the size string in self.size_range
                 closest_size_str = min(self.size_range, key=lambda size_str: abs(int(size_str) - target_pt))
                 selected_size_index = self.size_range.index(closest_size_str)
            except (ValueError, IndexError):
                 # Fallback to current selection or default '12'
                 selected_size_index = self.size_dropdown.get_selected()
                 if selected_size_index == Gtk.INVALID_LIST_POSITION:
                     try:
                         selected_size_index = self.size_range.index('12')
                     except ValueError:
                          selected_size_index = 5 # Absolute fallback index

            if selected_size_index != Gtk.INVALID_LIST_POSITION:
                 self.current_font_size = self.size_range[selected_size_index]
                 self.size_dropdown.handler_block(self.size_dropdown_handler)
                 self.size_dropdown.set_selected(selected_size_index)
                 self.size_dropdown.handler_unblock(self.size_dropdown_handler)

        else:
            # If state is None, update UI from internal fallback state
            # (Same logic as before)
            font_store = self.font_dropdown.get_model()
            selected_font_index = 0
            if font_store:
                 for i in range(font_store.get_n_items()):
                     if font_store.get_string(i).lower() == self.current_font.lower():
                         selected_font_index = i
                         break
            self.font_dropdown.handler_block(self.font_dropdown_handler)
            self.font_dropdown.set_selected(selected_font_index)
            self.font_dropdown.handler_unblock(self.font_dropdown_handler)

            selected_size_index = 5 # Default '12'
            try:
                 selected_size_index = self.size_range.index(self.current_font_size)
            except ValueError:
                 pass
            self.size_dropdown.handler_block(self.size_dropdown_handler)
            self.size_dropdown.set_selected(selected_size_index)
            self.size_dropdown.handler_unblock(self.size_dropdown_handler)


    def exec_js(self, script):
        # No changes needed
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def exec_js_with_result(self, js_code, callback, user_data=None):
        # No changes needed
        self.webview.evaluate_javascript(js_code, -1, None, None, None, callback, user_data)

    def _generic_toggle_handler(self, btn, command, state_attr, query_command, toggle_func):
        # No changes needed
        processing_attr = f'_processing_{state_attr}'
        if getattr(self, processing_attr, False):
            return
        setattr(self, processing_attr, True)

        def get_state_callback(webview, result, user_data):
            button, attribute, handler_func = user_data
            current_state = None # Initialize
            try:
                js_value = webview.evaluate_javascript_finish(result)
                current_state = js_value.to_boolean()

                setattr(self, attribute, current_state)
                button.handler_block_by_func(handler_func)
                button.set_active(current_state)
                button.handler_unblock_by_func(handler_func)
                self.webview.grab_focus()

            except GLib.Error as e:
                print(f"Error getting state for '{command}': {e}. Falling back.")
                # Only fallback if current_state is still None
                if current_state is None:
                    fallback_state = not getattr(self, attribute, button.get_active())
                    setattr(self, attribute, fallback_state)
                    button.handler_block_by_func(handler_func)
                    button.set_active(fallback_state)
                    button.handler_unblock_by_func(handler_func)
            except Exception as e:
                 print(f"Unexpected error in {command} callback: {e}")
                 # Consider fallback here too if appropriate
            finally:
                setattr(self, processing_attr, False)

        self.exec_js(f"document.execCommand('{command}')")
        self.exec_js_with_result(f"document.queryCommandState('{query_command}')",
                                 get_state_callback,
                                 (btn, state_attr, toggle_func))

    def on_bold_toggled(self, btn):
        self._generic_toggle_handler(btn, 'bold', 'is_bold', 'bold', self.on_bold_toggled)

    def on_italic_toggled(self, btn):
        self._generic_toggle_handler(btn, 'italic', 'is_italic', 'italic', self.on_italic_toggled)

    def on_underline_toggled(self, btn):
        self._generic_toggle_handler(btn, 'underline', 'is_underline', 'underline', self.on_underline_toggled)

    def on_strikethrough_toggled(self, btn):
        # Use 'strikeThrough' for both command and query
        self._generic_toggle_handler(btn, 'strikeThrough', 'is_strikethrough', 'strikeThrough', self.on_strikethrough_toggled)

    def _list_toggle_handler(self, btn, command, state_attr, query_command, toggle_func, other_btn, other_attr, other_func):
        # No changes needed
        processing_attr = f'_processing_{state_attr}'
        if getattr(self, processing_attr, False):
            return
        setattr(self, processing_attr, True)

        def get_state_callback(webview, result, user_data):
            button, attribute, handler_func, other_button, other_attribute, other_handler_func = user_data
            current_state = None
            try:
                js_value = webview.evaluate_javascript_finish(result)
                current_state = js_value.to_boolean()

                setattr(self, attribute, current_state)
                button.handler_block_by_func(handler_func)
                button.set_active(current_state)
                button.handler_unblock_by_func(handler_func)

                if current_state:
                    setattr(self, other_attribute, False)
                    other_button.handler_block_by_func(other_handler_func)
                    other_button.set_active(False)
                    other_button.handler_unblock_by_func(other_handler_func)

                self.webview.grab_focus()

            except GLib.Error as e:
                print(f"Error getting state for '{command}': {e}. Falling back.")
                if current_state is None:
                    fallback_state = not getattr(self, attribute, button.get_active())
                    setattr(self, attribute, fallback_state)
                    button.handler_block_by_func(handler_func)
                    button.set_active(fallback_state)
                    button.handler_unblock_by_func(handler_func)
                    if fallback_state:
                        setattr(self, other_attribute, False)
                        other_button.handler_block_by_func(other_handler_func)
                        other_button.set_active(False)
                        other_button.handler_unblock_by_func(other_handler_func)
            except Exception as e:
                 print(f"Unexpected error in {command} callback: {e}")
            finally:
                setattr(self, processing_attr, False)

        self.exec_js(f"document.execCommand('{command}')")
        self.exec_js_with_result(f"document.queryCommandState('{query_command}')",
                                 get_state_callback,
                                 (btn, state_attr, toggle_func, other_btn, other_attr, other_func))


    def on_bullet_list_toggled(self, btn):
        self._list_toggle_handler(btn, 'insertUnorderedList', 'is_bullet_list', 'insertUnorderedList', self.on_bullet_list_toggled,
                                  self.number_btn, 'is_number_list', self.on_number_list_toggled)

    def on_number_list_toggled(self, btn):
         self._list_toggle_handler(btn, 'insertOrderedList', 'is_number_list', 'insertOrderedList', self.on_number_list_toggled,
                                   self.bullet_btn, 'is_bullet_list', self.on_bullet_list_toggled)


    def _align_handler(self, btn, command, state_attr, query_command, handler_func):
        # No changes needed
        processing_attr = f'_processing_{state_attr}'
        if getattr(self, processing_attr, False):
            return
        setattr(self, processing_attr, True)

        # Execute command first
        self.exec_js(f"document.execCommand('{command}')")

        # Immediately update UI based on *intended* state, then verify with JS.
        # This makes the UI feel more responsive.
        all_align_buttons = [
            (self.align_left_btn, 'is_align_left', self.on_align_left),
            (self.align_center_btn, 'is_align_center', self.on_align_center),
            (self.align_right_btn, 'is_align_right', self.on_align_right),
            (self.align_justify_btn, 'is_align_justify', self.on_align_justify)
        ]
        for button, attr, handler in all_align_buttons:
             should_be_active = (button == btn) # Activate the clicked one
             setattr(self, attr, should_be_active)
             button.handler_block_by_func(handler)
             button.set_active(should_be_active)
             button.handler_unblock_by_func(handler)

        # Optional: Verify actual state with JS callback (can correct if execCommand failed)
        # self.exec_js_with_result(f"document.queryCommandState('{query_command}')",
        #                          self.verify_align_state_callback,
        #                          (btn, state_attr, handler_func, query_command))

        # For simplicity now, just assume execCommand worked and release flag.
        self.webview.grab_focus()
        setattr(self, processing_attr, False)


    # Optional verification callback (more complex)
    # def verify_align_state_callback(self, webview, result, user_data):
    #     clicked_button, clicked_attribute, clicked_handler, query_command = user_data
    #     processing_attr = f'_processing_{clicked_attribute}'
    #     try:
    #         js_value = webview.evaluate_javascript_finish(result)
    #         actual_state = js_value.to_boolean()
    #         intended_state = getattr(self, clicked_attribute, False)
    #         if actual_state != intended_state:
    #              print(f"Warning: Alignment state mismatch for {query_command}. UI might be inaccurate.")
    #              # Optionally force UI update based on actual_state here if needed
    #     except GLib.Error as e:
    #          print(f"Error verifying align state for {query_command}: {e}")
    #     except Exception as e:
    #          print(f"Unexpected error verifying align state: {e}")
    #     finally:
    #          setattr(self, processing_attr, False) # Ensure flag released


    def on_align_left(self, btn):
        self._align_handler(btn, 'justifyLeft', 'is_align_left', 'justifyLeft', self.on_align_left)

    def on_align_center(self, btn):
        self._align_handler(btn, 'justifyCenter', 'is_align_center', 'justifyCenter', self.on_align_center)

    def on_align_right(self, btn):
        self._align_handler(btn, 'justifyRight', 'is_align_right', 'justifyRight', self.on_align_right)

    def on_align_justify(self, btn):
         self._align_handler(btn, 'justifyFull', 'is_align_justify', 'justifyFull', self.on_align_justify)

    # --- Indent/Outdent ---
    def on_indent_more(self, btn):
        # No changes needed
        self.exec_js("document.execCommand('indent')")
        self.webview.grab_focus()

    def on_indent_less(self, btn):
        # No changes needed
        self.exec_js("document.execCommand('outdent')")
        self.webview.grab_focus()

    # --- Heading/Font/Size Changes ---
    def on_heading_changed(self, dropdown, *args):
        # No changes needed
        headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
        selected_index = dropdown.get_selected()
        if 0 <= selected_index < len(headings):
            tag = headings[selected_index]
            self.exec_js(f"document.execCommand('formatBlock', false, '<{tag}>')")
            self.webview.grab_focus()

    def on_font_family_changed(self, dropdown, *args):
        # No changes needed
        selected_item = dropdown.get_selected_item()
        if selected_item:
            self.current_font = selected_item.get_string()
            font_name_json = json.dumps(self.current_font)
            self.exec_js(f"document.execCommand('fontName', false, {font_name_json})")
            self.webview.grab_focus()

    def on_font_size_changed(self, dropdown, *args):
        # No changes needed
        selected_item = dropdown.get_selected_item()
        if selected_item:
            size_pt_str = selected_item.get_string()
            self.current_font_size = size_pt_str
            try:
                 size_pt = int(size_pt_str)
                 if size_pt <= 9: webkit_size = '1'
                 elif size_pt <= 11: webkit_size = '2'
                 elif size_pt <= 14: webkit_size = '3'
                 elif size_pt <= 18: webkit_size = '4'
                 elif size_pt <= 24: webkit_size = '5'
                 elif size_pt <= 36: webkit_size = '6'
                 else: webkit_size = '7'
            except ValueError:
                 webkit_size = '3' # Default ~12pt

            self.exec_js(f"document.execCommand('fontSize', false, '{webkit_size}')")
            self.webview.grab_focus()


    # --- Dark Mode Toggle ---
    def on_dark_mode_toggled(self, btn):
         # Target the .page element AND the html background
        if btn.get_active():
            btn.set_icon_name("weather-clear-night")
            script = """
            document.documentElement.style.backgroundColor = '#333'; // Darker grey outside
            const pages = document.querySelectorAll('.page'); // Target all potential pages if loaded
            pages.forEach(page => {
                page.style.backgroundColor = '#1e1e1e';
                page.style.color = '#e0e0e0';
            });
            """
        else:
            btn.set_icon_name("display-brightness")
            script = """
            document.documentElement.style.backgroundColor = '#ccc'; // Lighter grey outside
            const pages = document.querySelectorAll('.page');
            pages.forEach(page => {
                page.style.backgroundColor = '#ffffff';
                page.style.color = '#000000';
            });
            """
        self.exec_js(script)
        self.webview.grab_focus()


    # --- File Operations (New, Open, Save, Save As) ---

    def update_title(self):
        # No changes needed
        modified_marker = " *" if self.is_modified else ""
        title_base = f"Document {self.document_number}"
        if self.current_file and not self.is_new:
            try:
                 basename = self.current_file.get_basename()
                 if basename:
                      title_base = os.path.splitext(basename)[0]
            except TypeError:
                 pass # Keep default if error
        title = f"{title_base}{modified_marker} – Writer"
        self.set_title(title)


    # --- Save Confirmation Logic ---
    # This needs careful handling of asynchronous save operations, especially before quit/new/open.
    # The current implementation has FIXME notes about potential race conditions.
    # A full solution involves chaining callbacks or using promises/asyncio if integrated.

    def show_save_confirmation_dialog(self, action_callback, action_args=None):
        """Shows save/discard/cancel. Calls action_callback(response_id, action_args) on confirm."""
        dialog = Adw.MessageDialog(
            transient_for=self, modal=True, heading="Save Changes?",
            body=f"There are unsaved changes in '{self.get_title()}'.\nDo you want to save them?",
            destroy_with_parent=True )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.add_response("save", "Save")
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        # Store callback and args to be called after save/discard/cancel
        dialog.user_data = (action_callback, action_args)

        dialog.connect("response", self.on_save_confirmation_response)
        dialog.present()

    def on_save_confirmation_response(self, dialog, response_id):
        """Handles response from the save confirmation dialog."""
        action_callback, action_args = dialog.user_data

        if response_id == "save":
             # Define a function to run the original action *after* save completes
             def run_action_after_save(success):
                  if success:
                       if action_args:
                            action_callback(response_id, *action_args)
                       else:
                            action_callback(response_id)
                  # else: Save failed, maybe don't proceed with action?
                  #      Or call action_callback("cancel")? Depends on desired behavior.
                  dialog.destroy()

             # Initiate save, passing the post-save action runner as callback
             self.initiate_save_with_callback(run_action_after_save)

             # Don't destroy dialog yet, wait for save completion.
             # Or maybe disable buttons?

        elif response_id == "discard":
             if action_args:
                  action_callback(response_id, *action_args)
             else:
                  action_callback(response_id)
             dialog.destroy()
        else: # Cancel
             # Optionally call callback with "cancel" if it needs to know
             # action_callback("cancel", ...)
             dialog.destroy()


    def initiate_save_with_callback(self, post_save_callback):
         """Saves the current file (or shows Save As) and calls post_save_callback(success: bool)."""
         if self.current_file and not self.is_new:
             self.save_content_to_file(self.current_file, post_save_callback)
         else:
             # Need to show Save As dialog, then save, then callback.
             dialog = Gtk.FileDialog.new()
             dialog.set_title("Save File As")
             dialog.set_initial_name(f"Document {self.document_number}.html")
             filter_html = Gtk.FileFilter()
             filter_html.set_name("HTML Files (*.html)")
             filter_html.add_pattern("*.html")
             filters = Gio.ListStore.new(Gtk.FileFilter)
             filters.append(filter_html)
             dialog.set_filters(filters)
             dialog.set_default_filter(filter_html)

             # Store the post-save callback to be used after file selection
             dialog.user_data = post_save_callback

             dialog.save(self, None, self.save_as_dialog_response_for_callback)

    def save_as_dialog_response_for_callback(self, dialog, result):
         """Handles Save As response when a post-save callback is needed."""
         post_save_callback = dialog.user_data
         try:
             file = dialog.save_finish(result)
             if file:
                 # User selected a file, now save content and trigger callback
                 self.save_content_to_file(file, post_save_callback)
             else:
                  # User cancelled Save As dialog
                  if post_save_callback:
                       post_save_callback(False) # Indicate save didn't happen
         except GLib.Error as e:
             if e.code != Gio.IOErrorEnum.CANCELLED:
                 print(f"Save As error: {e.message}")
                 self.show_error_dialog("Error Saving File", f"Could not save the file:\n{e.message}")
             if post_save_callback:
                 post_save_callback(False) # Indicate save failed/cancelled

    # Modified save_content_to_file to accept optional callback
    def save_content_to_file(self, file, post_save_callback=None):
        """Gets HTML and saves it, calling optional callback(success: bool) on completion."""
        self.webview.evaluate_javascript(
            "document.documentElement.outerHTML;", -1, None, None, None,
            self.get_html_for_save_callback, (file, post_save_callback) # Pass file and callback
        )

    # Modified get_html_for_save_callback
    def get_html_for_save_callback(self, webview, result, user_data):
        """Callback after getting HTML, passes post_save_callback to next step."""
        file, post_save_callback = user_data
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                html_content = js_value.to_string()
                if not html_content: raise ValueError("Empty HTML content.")
                content_bytes = GLib.Bytes.new(html_content.encode('utf-8'))
                file.replace_contents_bytes_async(
                    content_bytes, None, False, Gio.FileCreateFlags.REPLACE_DESTINATION, None,
                    self.final_save_callback, (file, post_save_callback) # Pass file and callback
                )
            else:
                 raise ValueError("Failed to get HTML content.")
        except (GLib.Error, ValueError, Exception) as e:
            print(f"Error getting/preparing HTML for saving: {e}")
            self.show_error_dialog("Error Saving File", f"Could not retrieve/prepare content:\n{e}")
            if post_save_callback:
                 GLib.idle_add(post_save_callback, False) # Ensure callback runs in main loop

    # Modified final_save_callback
    def final_save_callback(self, file_obj, result, user_data):
        """Callback after async save finishes, calls optional post_save_callback."""
        saved_file, post_save_callback = user_data
        success = False
        try:
            # Finish the replace operation
            success = file_obj.replace_contents_finish(result)
            if success:
                print(f"File saved successfully: {saved_file.get_path()}")
                self.current_file = saved_file
                self.is_new = False
                self.is_modified = False
                self.update_title()
            else:
                 raise GLib.Error("Failed to replace file contents (returned false).")
        except GLib.Error as e:
            print(f"Final save error: {e.message}")
            self.show_error_dialog("Error Saving File", f"Could not write the file to disk:\n{e.message}")
            success = False
        except Exception as e:
             print(f"Unexpected error during final save: {e}")
             self.show_error_dialog("Error Saving File", f"An unexpected error occurred during saving:\n{e}")
             success = False
        finally:
             # Call the post-save callback if provided
             if post_save_callback:
                 GLib.idle_add(post_save_callback, success) # Run callback in main loop

    # --- New / Open / Close with Confirmation ---

    def on_new_clicked(self, btn):
        if self.is_modified:
            self.show_save_confirmation_dialog(self.perform_new_action)
        else:
            self.perform_new_action("discard") # Directly perform if not modified

    def perform_new_action(self, response_id):
        """Performs the 'new document' action after confirmation response."""
        if response_id in ["save", "discard"]: # Only proceed if user confirmed save/discard
            self.ignore_changes = True
            self.webview.load_html(self.initial_html, "file:///")
            self.current_file = None
            self.is_new = True
            self.is_modified = False
            self.document_number = EditorWindow.document_counter
            EditorWindow.document_counter += 1
            self.update_title()
            self.reset_formatting_state()
            # Update UI slightly later, after webview load finishes and clears ignore_changes
            # GLib.timeout_add(100, lambda: self.update_formatting_ui(None)) # Moved to clear_ignore_changes

    def on_open_clicked(self, btn):
         if self.is_modified:
            self.show_save_confirmation_dialog(self.perform_open_action)
         else:
            self.perform_open_action("discard")

    def perform_open_action(self, response_id):
        """Shows the open dialog after confirmation response."""
        if response_id in ["save", "discard"]:
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Open File")
            filter_html = Gtk.FileFilter()
            filter_html.set_name("HTML Files (*.html, *.htm)")
            filter_html.add_pattern("*.html")
            filter_html.add_pattern("*.htm")
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_html)
            dialog.set_filters(filters)
            dialog.set_default_filter(filter_html)
            dialog.open(self, None, self.on_open_file_dialog_response)


    def on_open_file_dialog_response(self, dialog, result):
        # No changes needed here
        try:
            file = dialog.open_finish(result)
            if file:
                self.current_file = file
                self.is_new = False
                self.update_title()
                file.load_contents_async(None, self.load_html_callback)
        except GLib.Error as e:
            if e.code != Gio.IOErrorEnum.CANCELLED:
                print(f"Open error: {e.message}")
                self.show_error_dialog("Error Opening File", f"Could not open the selected file:\n{e.message}")

    def load_html_callback(self, file, result):
        # No changes needed here, already handles basic .page wrapping
        try:
            ok, content_bytes, _ = file.load_contents_finish(result)
            if ok:
                self.ignore_changes = True
                html_content = content_bytes.decode('utf-8')
                # Basic check/wrap for .page div (might need improvement for complex HTML)
                if '<div class="page">' not in html_content.lower(): # Case-insensitive check
                     body_match = re.search(r"<body.*?>(.*?)</body>", html_content, re.IGNORECASE | re.DOTALL)
                     if body_match:
                          body_content = body_match.group(1)
                          # Replace body content with wrapped content
                          html_content = re.sub(r"(<body.*?>)(.*?)(</body>)",
                                                rf'\1<div class="page">{body_content}</div>\3',
                                                html_content, count=1, flags=re.IGNORECASE | re.DOTALL)
                     else: # Fallback wrap if no body tag found
                          html_content = f'<html><head>{self.initial_html.split("<head>")[1].split("</head>")[0]}</head><body contenteditable="true"><div class="page">{html_content}</div></body></html>'

                self.webview.load_html(html_content, file.get_uri())
                self.is_modified = False
                self.update_title()
            else:
                 raise GLib.Error("Failed to load file contents.")
        except GLib.Error as e:
            print(f"Load error: {e.message}")
            self.show_error_dialog("Error Loading File", f"Could not read the file contents:\n{e.message}")
            self.current_file = None; self.is_new = True; self.update_title()
        except Exception as e:
             print(f"Unexpected error during file load: {e}")
             self.show_error_dialog("Error Loading File", f"An unexpected error occurred:\n{e}")
             self.current_file = None; self.is_new = True; self.update_title()


    def on_save_clicked(self, btn):
        # Uses the improved save flow
        self.initiate_save_with_callback(None) # No specific action needed after plain save

    def on_save_as_clicked(self, btn):
        # Uses the improved save flow
        self.initiate_save_with_callback(None) # No specific action needed after save as


    def on_close_request(self, *args):
        """Handle the window close request, using improved save confirmation."""
        if self.is_modified:
            # Define what to do after save/discard/cancel
            def post_confirm_action(response_id):
                 if response_id in ["save", "discard"]:
                      # Only quit if save was successful or user discarded
                      self.get_application().quit()
                 # Else (cancel or save failed), do nothing, close is aborted.

            self.show_save_confirmation_dialog(post_confirm_action)
            return True # Prevent default close while dialog is shown/saving
        else:
            # Not modified, allow close immediately
            return False # Let the default handler close the window


    # --- Edit Operations ---
    # No changes needed for Cut/Copy/Paste/Undo/Redo
    def on_cut_clicked(self, btn):
        self.exec_js("document.execCommand('cut')")
        self.webview.grab_focus()

    def on_copy_clicked(self, btn):
        self.exec_js("document.execCommand('copy')")
        self.webview.grab_focus()

    def on_paste_clicked(self, btn):
        self.exec_js("document.execCommand('paste')")
        self.webview.grab_focus()

    def on_undo_clicked(self, btn):
        self.exec_js("document.execCommand('undo')")
        self.webview.grab_focus()

    def on_redo_clicked(self, btn):
        self.exec_js("document.execCommand('redo')")
        self.webview.grab_focus()

    # --- Keyboard Shortcuts ---
    # No changes needed
    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        shift = (state & Gdk.ModifierType.SHIFT_MASK) != 0
        alt = (state & Gdk.ModifierType.ALT_MASK) != 0
        consumed = False

        # Allow WebView default handling for Cut/Copy/Paste/Select All
        if ctrl and keyval in (Gdk.KEY_x, Gdk.KEY_c, Gdk.KEY_v, Gdk.KEY_a):
            return False

        if ctrl and not shift and not alt:
            if keyval == Gdk.KEY_b: consumed = self.trigger_button(self.bold_btn)
            elif keyval == Gdk.KEY_i: consumed = self.trigger_button(self.italic_btn)
            elif keyval == Gdk.KEY_u: consumed = self.trigger_button(self.underline_btn)
            elif keyval == Gdk.KEY_s: self.on_save_clicked(None); consumed = True
            elif keyval == Gdk.KEY_o: self.on_open_clicked(None); consumed = True
            elif keyval == Gdk.KEY_n: self.on_new_clicked(None); consumed = True
            elif keyval == Gdk.KEY_w: self.close_request(); consumed = True # Initiate close request
            elif keyval == Gdk.KEY_z: self.on_undo_clicked(None); consumed = True
            elif keyval == Gdk.KEY_y: self.on_redo_clicked(None); consumed = True
            elif keyval == Gdk.KEY_l: consumed = self.trigger_button(self.align_left_btn) # May conflict
            elif keyval == Gdk.KEY_e: consumed = self.trigger_button(self.align_center_btn)
            elif keyval == Gdk.KEY_r: consumed = self.trigger_button(self.align_right_btn)
            elif keyval == Gdk.KEY_j: consumed = self.trigger_button(self.align_justify_btn)
            elif keyval == Gdk.KEY_0: consumed = self.set_dropdown_index(self.heading_dropdown, 0)
            elif keyval == Gdk.KEY_1: consumed = self.set_dropdown_index(self.heading_dropdown, 1)
            elif keyval == Gdk.KEY_2: consumed = self.set_dropdown_index(self.heading_dropdown, 2)
            elif keyval == Gdk.KEY_3: consumed = self.set_dropdown_index(self.heading_dropdown, 3)
            elif keyval == Gdk.KEY_4: consumed = self.set_dropdown_index(self.heading_dropdown, 4)
            elif keyval == Gdk.KEY_5: consumed = self.set_dropdown_index(self.heading_dropdown, 5)
            elif keyval == Gdk.KEY_6: consumed = self.set_dropdown_index(self.heading_dropdown, 6)

        elif ctrl and shift and not alt:
            if keyval == Gdk.KEY_S: self.on_save_as_clicked(None); consumed = True
            elif keyval == Gdk.KEY_Z: self.on_redo_clicked(None); consumed = True
            elif keyval == Gdk.KEY_X: consumed = self.trigger_button(self.strikethrough_btn)
            elif keyval == Gdk.KEY_L: consumed = self.trigger_button(self.bullet_btn)
            elif keyval == Gdk.KEY_asterisk: consumed = self.trigger_button(self.bullet_btn)
            elif keyval == Gdk.KEY_7: consumed = self.trigger_button(self.number_btn) # Ctrl+Shift+7

        return consumed

    def trigger_button(self, button):
        # No changes needed
        if isinstance(button, Gtk.ToggleButton):
            # Toggling sends signal which runs the handler
            button.set_active(not button.get_active())
        elif isinstance(button, Gtk.Button):
            button.clicked()
        return True

    def set_dropdown_index(self, dropdown, index):
         # No changes needed
         model = dropdown.get_model()
         if model and 0 <= index < model.get_n_items():
              # Setting selected triggers the notify::selected signal -> handler
              dropdown.set_selected(index)
              return True
         return False

    # --- Dialogs and State Management ---
    # Error Dialog unchanged
    def show_error_dialog(self, title, message):
        dialog = Adw.MessageDialog(
            transient_for=self, modal=True, heading=title, body=message,
             destroy_with_parent=True )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    # clear_ignore_changes: Also trigger UI update after ignore flag off
    def clear_ignore_changes(self):
        self.ignore_changes = False
        # Trigger selection check & UI update after changes are no longer ignored
        self.exec_js_with_result("document.queryCommandState('bold')", lambda w, r, u: self.update_formatting_ui_from_current_state()) # Query any state to trigger update
        return False # Remove the timeout source

    def update_formatting_ui_from_current_state(self):
         """Gets the current formatting state from JS and updates the UI"""
         self.webview.evaluate_javascript(
              """
              (function() {
                   const sel = window.getSelection();
                   let state = null;
                   if (sel.rangeCount > 0) {
                        const range = sel.getRangeAt(0);
                        let element = range.startContainer;
                        if (element.nodeType === Node.TEXT_NODE) element = element.parentElement;
                        while (element && element.nodeType === Node.ELEMENT_NODE && !['P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'BODY', 'BLOCKQUOTE'].includes(element.tagName)) {
                             element = element.parentElement;
                        }
                        if (!element || element.nodeType !== Node.ELEMENT_NODE) element = document.querySelector('.page');

                        if (element) {
                             const style = window.getComputedStyle(element);
                             state = {
                                 bold: document.queryCommandState('bold'), italic: document.queryCommandState('italic'),
                                 underline: document.queryCommandState('underline'), strikethrough: document.queryCommandState('strikeThrough'),
                                 formatBlock: document.queryCommandValue('formatBlock').toLowerCase() || 'p',
                                 fontName: style.fontFamily.split(',')[0].replace(/['"]/g, '').trim(), fontSize: style.fontSize,
                                 insertUnorderedList: document.queryCommandState('insertUnorderedList'), insertOrderedList: document.queryCommandState('insertOrderedList'),
                                 justifyLeft: document.queryCommandState('justifyLeft'), justifyCenter: document.queryCommandState('justifyCenter'),
                                 justifyRight: document.queryCommandState('justifyRight'), justifyFull: document.queryCommandState('justifyFull')
                             };
                        }
                   }
                   if (!state) { // Default if no selection or element
                        const pageElement = document.querySelector('.page');
                        const style = pageElement ? window.getComputedStyle(pageElement) : null;
                        state = {
                             bold: false, italic: false, underline: false, strikethrough: false, formatBlock: 'p',
                             fontName: style ? style.fontFamily.split(',')[0].replace(/['"]/g, '').trim() : 'Sans', fontSize: style ? style.fontSize : '16px',
                             insertUnorderedList: false, insertOrderedList: false,
                             justifyLeft: true, justifyCenter: false, justifyRight: false, justifyFull: false
                        };
                   }
                   return JSON.stringify(state);
              })();
              """, -1, None, None, None, self.process_current_state_update, None)

    def process_current_state_update(self, webview, result, user_data):
         """Receives state JSON and calls update_formatting_ui"""
         try:
              js_value = webview.evaluate_javascript_finish(result)
              state_str = js_value.to_string()
              state = json.loads(state_str)
              self.update_formatting_ui(state)
         except (GLib.Error, json.JSONDecodeError, Exception) as e:
              print(f"Error processing current state update: {e}")
              # Fallback: update UI with internal state if JS fails
              self.update_formatting_ui(None)

    # reset_formatting_state unchanged
    def reset_formatting_state(self):
         self.is_bold = False; self.is_italic = False; self.is_underline = False; self.is_strikethrough = False
         self.is_bullet_list = False; self.is_number_list = False
         self.is_align_left = True; self.is_align_center = False; self.is_align_right = False; self.is_align_justify = False
         self.current_font = "Sans"; self.current_font_size = "12"
         # Find default indices
         font_store = self.font_dropdown.get_model()
         default_font_index = 0
         if font_store:
              names = [font_store.get_string(i).lower() for i in range(font_store.get_n_items())]
              try: default_font_index = names.index('sans')
              except ValueError: pass
         default_size_index = 5 # '12'
         try: default_size_index = self.size_range.index('12')
         except ValueError: pass
         # Reset Dropdowns
         self.heading_dropdown.handler_block(self.heading_dropdown_handler)
         self.heading_dropdown.set_selected(0)
         self.heading_dropdown.handler_unblock(self.heading_dropdown_handler)
         self.font_dropdown.handler_block(self.font_dropdown_handler)
         self.font_dropdown.set_selected(default_font_index)
         self.font_dropdown.handler_unblock(self.font_dropdown_handler)
         self.size_dropdown.handler_block(self.size_dropdown_handler)
         self.size_dropdown.set_selected(default_size_index)
         self.size_dropdown.handler_unblock(self.size_dropdown_handler)


# --- Main Execution ---
if __name__ == "__main__":
    app = Writer()
    app.run(sys.argv)
