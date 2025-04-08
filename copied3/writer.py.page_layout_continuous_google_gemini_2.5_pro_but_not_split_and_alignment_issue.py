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
            padding: 20px; /* Space around the page area */
            /* Center the .page div horizontally */
            display: flex;
            justify-content: center;
            min-height: 100vh; /* Ensure body takes full viewport height */

            /* Default text styles will be inherited by content inside .page */
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
            /* Prevent browser focus outline on the page div itself */
            outline: none;
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
        # size_range = [str(i) for i in range(6, 97)] # Original range 6-96
        size_store = Gtk.StringList(strings=self.size_range)
        self.size_dropdown = Gtk.DropDown(model=size_store)
        try:
             # Find index for 12pt
             default_size_index = self.size_range.index("12")
        except ValueError:
             default_size_index = 5 # Fallback if 12 isn't in the list for some reason
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
                 if (page.innerHTML.trim() === '<p>\\u200B</p>' || page.innerHTML.trim() === '<p><br></p>' || page.innerHTML.trim() === '') {
                    return false; // Still effectively empty
                 }
                 return true; // Has actual content
             })()""",
            -1, None, None, None, self.check_meaningful_change, None
        )

    def check_meaningful_change(self, webview, result, user_data):
        try:
            is_meaningful = webview.evaluate_javascript_finish(result).to_boolean()
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
            self.webview.evaluate_javascript("""
                (function() {
                    // Ensure cursor is placed correctly initially
                    let pageDiv = document.querySelector('.page');
                    let p = pageDiv ? pageDiv.querySelector('p') : null;
                    if (p) {
                        let range = document.createRange();
                        range.setStart(p, 0); // Start of the paragraph
                        range.collapse(true); // Collapse to the start
                        let sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                    }

                    // Debounce function to limit rapid event firing
                    function debounce(func, wait) {
                        let timeout;
                        return function(...args) {
                            clearTimeout(timeout);
                            timeout = setTimeout(() => func.apply(this, args), wait);
                        };
                    }

                    // Content Change Detection
                    let lastContent = document.body.innerHTML; // Track whole body
                    const notifyChange = debounce(function() {
                        let currentContent = document.body.innerHTML;
                        if (currentContent !== lastContent) {
                            // Check if it's just whitespace or empty paragraph changes sometimes ignored
                            const pageContent = document.querySelector('.page')?.innerHTML.trim() ?? '';
                            const lastPageContent = new DOMParser().parseFromString(lastContent, 'text/html').querySelector('.page')?.innerHTML.trim() ?? '';

                            // More robust check: ignore if only difference is empty tags or placeholders
                            const simplifiedCurrent = pageContent.replace(/<p>\\u200B<\\/p>|<p><br><\\/p>|^\\s*$/g, '');
                            const simplifiedLast = lastPageContent.replace(/<p>\\u200B<\\/p>|<p><br><\\/p>|^\\s*$/g, '');

                            if (simplifiedCurrent !== simplifiedLast) {
                                 window.webkit.messageHandlers.contentChanged.postMessage('changed');
                            }
                            lastContent = currentContent;
                        }
                    }, 300); // Increased debounce slightly

                    // Listen to relevant events
                    document.addEventListener('input', notifyChange);
                    document.addEventListener('paste', notifyChange);
                    document.addEventListener('cut', notifyChange);
                    // Sometimes execCommand changes don't fire 'input'
                    document.addEventListener('mouseup', notifyChange); // Catch changes after format commands
                    document.addEventListener('keyup', (event) => {
                         // Trigger on keys that modify content but might not fire 'input' consistently
                         if (['Enter', 'Backspace', 'Delete'].includes(event.key)) {
                              notifyChange();
                         }
                    });


                    // Selection Change Detection
                    const notifySelectionChange = debounce(function() {
                        const sel = window.getSelection();
                        if (sel.rangeCount > 0) {
                            const range = sel.getRangeAt(0);
                            let element = range.startContainer;
                            // Traverse up from text node if necessary
                            if (element.nodeType === Node.TEXT_NODE) {
                                element = element.parentElement;
                            }
                            // Ensure we are checking an element node
                            if (element.nodeType !== Node.ELEMENT_NODE) {
                                element = document.querySelector('.page'); // Fallback
                            }

                            // Get computed style from the container element
                            const style = window.getComputedStyle(element);

                            const state = {
                                bold: document.queryCommandState('bold'),
                                italic: document.queryCommandState('italic'),
                                underline: document.queryCommandState('underline'),
                                strikethrough: document.queryCommandState('strikethrough'),
                                formatBlock: document.queryCommandValue('formatBlock') || 'p',
                                // Normalize font family name
                                fontName: style.fontFamily.split(',')[0].replace(/['"]/g, '').trim(),
                                fontSize: style.fontSize, // e.g., "16px"
                                insertUnorderedList: document.queryCommandState('insertUnorderedList'),
                                insertOrderedList: document.queryCommandState('insertOrderedList'),
                                justifyLeft: document.queryCommandState('justifyLeft'),
                                justifyCenter: document.queryCommandState('justifyCenter'),
                                justifyRight: document.queryCommandState('justifyRight'),
                                justifyFull: document.queryCommandState('justifyFull')
                            };
                            window.webkit.messageHandlers.selectionChanged.postMessage(JSON.stringify(state));
                        } else {
                             // Send default state if no selection (e.g., after load)
                             const pageElement = document.querySelector('.page');
                             const style = pageElement ? window.getComputedStyle(pageElement) : null;
                             const defaultState = {
                                bold: false, italic: false, underline: false, strikethrough: false,
                                formatBlock: 'p',
                                fontName: style ? style.fontFamily.split(',')[0].replace(/['"]/g, '').trim() : 'Sans',
                                fontSize: style ? style.fontSize : '16px', // ~12pt
                                insertUnorderedList: false, insertOrderedList: false,
                                justifyLeft: true, justifyCenter: false, justifyRight: false, justifyFull: false
                             };
                             window.webkit.messageHandlers.selectionChanged.postMessage(JSON.stringify(defaultState));
                        }
                    }, 150); // Shorter debounce for selection responsiveness

                    document.addEventListener('selectionchange', notifySelectionChange);
                    notifySelectionChange(); // Get initial state after load
                })();
            """, -1, None, None, None, None, None) # No callback needed for setup script
            # Set ignore_changes flag briefly after load to prevent initial setup triggering modification state
            self.ignore_changes = True
            GLib.timeout_add(500, self.clear_ignore_changes) # Allow time for JS init
            GLib.idle_add(self.webview.grab_focus)


    def on_selection_changed(self, user_content, message):
        # No changes needed here, logic relies on JS state which should be correct
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
         # This function updates GTK widgets based on the state from JS
         # No changes should be strictly necessary here due to the page layout,
         # but ensure font/size parsing is robust.

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
            # Determine active alignment (only one should be true)
            is_center = state.get('justifyCenter', False)
            is_right = state.get('justifyRight', False)
            is_full = state.get('justifyFull', False)
            is_left = not is_center and not is_right and not is_full # Default to left if others false

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
            # Map 'div' or other non-heading tags to 'Normal' (index 0)
            headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
            try:
                 index = headings.index(format_block) if format_block in headings else 0
            except ValueError:
                 index = 0 # Default to Normal/p
            self.heading_dropdown.handler_block(self.heading_dropdown_handler)
            self.heading_dropdown.set_selected(index)
            self.heading_dropdown.handler_unblock(self.heading_dropdown_handler)

            # --- Font Family Detection ---
            detected_font_raw = state.get('fontName', self.current_font)
            detected_font = detected_font_raw.lower().strip() # Normalize

            font_store = self.font_dropdown.get_model()
            selected_font_index = -1 # Use -1 to indicate not found yet
            exact_match_index = -1

            # Prioritize exact match, then partial match (like 'Arial' matching 'Arial Black')
            for i in range(font_store.get_n_items()):
                list_font_lower = font_store.get_string(i).lower()
                if list_font_lower == detected_font:
                    exact_match_index = i
                    break # Found exact match
                elif selected_font_index == -1 and detected_font.startswith(list_font_lower):
                     # Allow partial match if detected is more specific (e.g., "Arial Black" vs "Arial")
                    selected_font_index = i
                elif selected_font_index == -1 and list_font_lower.startswith(detected_font):
                     # Allow partial match if list is more specific (e.g. "Arial" vs "Arial Narrow")
                     selected_font_index = i


            if exact_match_index != -1:
                 final_font_index = exact_match_index
            elif selected_font_index != -1:
                 final_font_index = selected_font_index
            else:
                 # Fallback to current selection or default if no match
                 final_font_index = self.font_dropdown.get_selected()
                 if final_font_index == Gtk.INVALID_LIST_POSITION:
                      # Find 'Sans' or use 0
                      try:
                           final_font_index = [font_store.get_string(i).lower() for i in range(font_store.get_n_items())].index('sans')
                      except ValueError:
                           final_font_index = 0


            if final_font_index != Gtk.INVALID_LIST_POSITION:
                 self.current_font = font_store.get_string(final_font_index)
                 self.font_dropdown.handler_block(self.font_dropdown_handler)
                 self.font_dropdown.set_selected(final_font_index)
                 self.font_dropdown.handler_unblock(self.font_dropdown_handler)

            # --- Font Size Detection ---
            font_size_str = state.get('fontSize', '12pt') # Default to 12pt if not found
            font_size_pt_str = '12' # Default

            try:
                 if font_size_str.endswith('px'):
                     # More accurate conversion: 1pt = 1.333px is common but not always exact.
                     # Let's round common pixel values. A direct CSS pt value is better if available.
                     px_val = float(font_size_str[:-2])
                     # Approximate mapping (adjust if needed)
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
                 elif font_size_str.endswith('pt'):
                     font_size_pt_str = str(round(float(font_size_str[:-2]))) # Round to nearest whole pt
                 elif font_size_str.endswith('%'):
                      # Percentage is relative, hard to map directly, fallback
                      font_size_pt_str = self.current_font_size
                 else:
                      # Assume it might be a number string already (less common)
                      font_size_pt_str = str(round(float(font_size_str)))

            except ValueError:
                 font_size_pt_str = '12' # Fallback on parsing error

            size_store = self.size_dropdown.get_model()
            available_sizes = self.size_range # Use the predefined list
            selected_size_index = -1

            # Find the closest available size in our dropdown
            try:
                 target_pt = int(font_size_pt_str)
                 closest_size = min(available_sizes, key=lambda size: abs(int(size) - target_pt))
                 selected_size_index = available_sizes.index(closest_size)
            except ValueError:
                 # If conversion fails, fallback to current or default
                 selected_size_index = self.size_dropdown.get_selected()
                 if selected_size_index == Gtk.INVALID_LIST_POSITION:
                     try:
                         selected_size_index = available_sizes.index('12')
                     except ValueError:
                          selected_size_index = 5 # Fallback index for 12pt

            if selected_size_index != -1:
                 self.current_font_size = available_sizes[selected_size_index]
                 self.size_dropdown.handler_block(self.size_dropdown_handler)
                 self.size_dropdown.set_selected(selected_size_index)
                 self.size_dropdown.handler_unblock(self.size_dropdown_handler)

        else:
            # If called without state (e.g., maybe on init or error),
            # try to set dropdowns based on tracked state. Less reliable.
            # Font Family
            font_store = self.font_dropdown.get_model()
            selected_font_index = 0
            for i in range(font_store.get_n_items()):
                if font_store.get_string(i).lower() == self.current_font.lower():
                    selected_font_index = i
                    break
            self.font_dropdown.handler_block(self.font_dropdown_handler)
            self.font_dropdown.set_selected(selected_font_index)
            self.font_dropdown.handler_unblock(self.font_dropdown_handler)

            # Font Size
            size_store = self.size_dropdown.get_model()
            available_sizes = self.size_range
            selected_size_index = 5 # Default index for 12pt
            try:
                 selected_size_index = available_sizes.index(self.current_font_size)
            except ValueError:
                 pass # Keep default if current not found
            self.size_dropdown.handler_block(self.size_dropdown_handler)
            self.size_dropdown.set_selected(selected_size_index)
            self.size_dropdown.handler_unblock(self.size_dropdown_handler)

    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    # --- exec_js_with_result and formatting toggles (bold, italic, etc.) ---
    # These functions execute JS and update the button state.
    # They need robust error handling and state management.
    # Using evaluate_javascript_finish is generally preferred over run_javascript if available.

    def exec_js_with_result(self, js_code, callback, user_data=None):
        """Executes JS and calls the callback with the result."""
        self.webview.evaluate_javascript(js_code, -1, None, None, None, callback, user_data)

    def _generic_toggle_handler(self, btn, command, state_attr, query_command, toggle_func):
        """Generic handler for simple toggle commands (bold, italic, etc.)."""
        processing_attr = f'_processing_{state_attr}'
        if getattr(self, processing_attr, False):
            return
        setattr(self, processing_attr, True)

        def get_state_callback(webview, result, user_data):
            button, attribute, handler_func = user_data
            try:
                # Use evaluate_javascript_finish to get the result
                js_value = webview.evaluate_javascript_finish(result)
                current_state = js_value.to_boolean() # Get boolean result

                # Update internal state and button appearance
                setattr(self, attribute, current_state)
                button.handler_block_by_func(handler_func)
                button.set_active(current_state)
                button.handler_unblock_by_func(handler_func)
                self.webview.grab_focus() # Return focus to editor

            except GLib.Error as e:
                print(f"Error getting state for '{command}': {e}. Falling back.")
                # Fallback: toggle internal state and update button
                fallback_state = not getattr(self, attribute, button.get_active())
                setattr(self, attribute, fallback_state)
                button.handler_block_by_func(handler_func)
                button.set_active(fallback_state)
                button.handler_unblock_by_func(handler_func)
            except Exception as e:
                 print(f"Unexpected error in {command} callback: {e}")
            finally:
                setattr(self, processing_attr, False) # Reset processing flag

        # Execute the command first
        self.exec_js(f"document.execCommand('{command}')")
        # Then query the state and use the callback
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
        self._generic_toggle_handler(btn, 'strikeThrough', 'is_strikethrough', 'strikeThrough', self.on_strikethrough_toggled)


    def _list_toggle_handler(self, btn, command, state_attr, query_command, toggle_func, other_btn, other_attr, other_func):
        """Generic handler for list toggles (bullet, number)."""
        processing_attr = f'_processing_{state_attr}'
        if getattr(self, processing_attr, False):
            return
        setattr(self, processing_attr, True)

        def get_state_callback(webview, result, user_data):
            button, attribute, handler_func, other_button, other_attribute, other_handler_func = user_data
            try:
                js_value = webview.evaluate_javascript_finish(result)
                current_state = js_value.to_boolean()

                setattr(self, attribute, current_state)
                button.handler_block_by_func(handler_func)
                button.set_active(current_state)
                button.handler_unblock_by_func(handler_func)

                # If this list type is now active, deactivate the other
                if current_state:
                    setattr(self, other_attribute, False)
                    other_button.handler_block_by_func(other_handler_func)
                    other_button.set_active(False)
                    other_button.handler_unblock_by_func(other_handler_func)

                self.webview.grab_focus()

            except GLib.Error as e:
                print(f"Error getting state for '{command}': {e}. Falling back.")
                fallback_state = not getattr(self, attribute, button.get_active())
                setattr(self, attribute, fallback_state)
                button.handler_block_by_func(handler_func)
                button.set_active(fallback_state)
                button.handler_unblock_by_func(handler_func)
                if fallback_state: # Deactivate other on fallback too
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
        """Handler for alignment commands."""
        processing_attr = f'_processing_{state_attr}'
        if getattr(self, processing_attr, False):
            return
        setattr(self, processing_attr, True)

        # Define all alignment buttons and their attributes/handlers
        all_align_buttons = [
            (self.align_left_btn, 'is_align_left', self.on_align_left, 'justifyLeft'),
            (self.align_center_btn, 'is_align_center', self.on_align_center, 'justifyCenter'),
            (self.align_right_btn, 'is_align_right', self.on_align_right, 'justifyRight'),
            (self.align_justify_btn, 'is_align_justify', self.on_align_justify, 'justifyFull')
        ]

        def get_align_state_callback(webview, result, user_data):
            clicked_button, clicked_attribute, clicked_handler = user_data
            try:
                js_value = webview.evaluate_javascript_finish(result)
                command_succeeded = js_value.to_boolean() # Sometimes execCommand returns bool? Check queryCommandState instead.

                # Re-query the state *after* executing the command
                self.webview.evaluate_javascript(
                    f"document.queryCommandState('{query_command}')", -1, None, None, None,
                    self.update_align_buttons_state, (clicked_button, clicked_attribute, clicked_handler)
                )

            except GLib.Error as e:
                print(f"Error getting state for '{command}': {e}. State might be incorrect.")
                setattr(self, processing_attr, False) # Ensure flag is cleared on error
            except Exception as e:
                 print(f"Unexpected error in {command} callback: {e}")
                 setattr(self, processing_attr, False)

    def update_align_buttons_state(self, webview, result, user_data):
         clicked_button, clicked_attribute, clicked_handler = user_data
         state_attr = clicked_attribute.replace('is_align_', '') # e.g., 'left', 'center'
         processing_attr = f'_processing_is_align_{state_attr}'

         try:
             js_value = webview.evaluate_javascript_finish(result)
             is_active = js_value.to_boolean()

             # Update all alignment buttons based on the new state
             all_align_buttons = [
                 (self.align_left_btn, 'is_align_left', self.on_align_left, 'justifyLeft'),
                 (self.align_center_btn, 'is_align_center', self.on_align_center, 'justifyCenter'),
                 (self.align_right_btn, 'is_align_right', self.on_align_right, 'justifyRight'),
                 (self.align_justify_btn, 'is_align_justify', self.on_align_justify, 'justifyFull')
             ]

             # Determine which one *should* be active now
             # Note: queryCommandState might return true for multiple if underlying state is complex.
             # We enforce mutual exclusivity based on the *last clicked* command.
             # A better JS approach might query the computed text-align style.

             for button, attr, handler, cmd in all_align_buttons:
                 # Activate the clicked button, deactivate others
                 should_be_active = (button == clicked_button)
                 setattr(self, attr, should_be_active)
                 button.handler_block_by_func(handler)
                 button.set_active(should_be_active)
                 button.handler_unblock_by_func(handler)

             self.webview.grab_focus()

         except GLib.Error as e:
              print(f"Error updating align buttons state: {e}")
         except Exception as e:
              print(f"Unexpected error updating align buttons: {e}")
         finally:
             # Reset the specific processing flag
             setattr(self, processing_attr, False)


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
        self.exec_js("document.execCommand('indent')")
        self.webview.grab_focus()

    def on_indent_less(self, btn):
        self.exec_js("document.execCommand('outdent')")
        self.webview.grab_focus()

    # --- Heading/Font/Size Changes ---
    def on_heading_changed(self, dropdown, *args):
        headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"] # Use 'p' for Normal
        selected_index = dropdown.get_selected()
        if 0 <= selected_index < len(headings):
            tag = headings[selected_index]
            # formatBlock works best with block elements
            self.exec_js(f"document.execCommand('formatBlock', false, '<{tag}>')")
            self.webview.grab_focus()

    def on_font_family_changed(self, dropdown, *args):
        selected_item = dropdown.get_selected_item()
        if selected_item:
            self.current_font = selected_item.get_string()
            # Use JSON stringify for safety with font names containing spaces/quotes
            font_name_json = json.dumps(self.current_font)
            self.exec_js(f"document.execCommand('fontName', false, {font_name_json})")
            # No need to call update_formatting_ui here, selection change handles it
            self.webview.grab_focus()


    def on_font_size_changed(self, dropdown, *args):
        selected_item = dropdown.get_selected_item()
        if selected_item:
            size_pt_str = selected_item.get_string()
            self.current_font_size = size_pt_str

            # Map pt size to legacy 1-7 size for execCommand('fontSize')
            # This is less reliable than directly setting style.fontSize
            try:
                 size_pt = int(size_pt_str)
                 if size_pt <= 9: webkit_size = '1' # ~8pt
                 elif size_pt <= 11: webkit_size = '2' # ~10pt
                 elif size_pt <= 14: webkit_size = '3' # ~12pt
                 elif size_pt <= 18: webkit_size = '4' # ~14pt
                 elif size_pt <= 24: webkit_size = '5' # ~18pt
                 elif size_pt <= 36: webkit_size = '6' # ~24pt
                 else: webkit_size = '7' # ~36pt+
            except ValueError:
                 webkit_size = '3' # Default to ~12pt if parsing fails

            # Attempt 1: Use execCommand (often wraps in <font size="...">)
            self.exec_js(f"document.execCommand('fontSize', false, '{webkit_size}')")

            # Attempt 2 (More robust): Directly apply style.fontSize = '...pt'
            # This requires wrapping the selection or modifying existing elements.
            # It's complex to do correctly for all selection cases (collapsed, partial, multi-node).
            # Let's stick to execCommand for now, accepting its limitations.
            # A more advanced editor would use custom JS range manipulation here.

            # Example of direct style application (simplified, might break things):
            # self.exec_js(f"""
            # (function() {{
            #     const sel = window.getSelection();
            #     if (!sel.rangeCount) return;
            #     const range = sel.getRangeAt(0);
            #     if (range.collapsed) {{
            #         // Apply to typing attribute (hard in contenteditable)
            #         // Or insert a styled span (better)
            #         let span = document.createElement('span');
            #         span.style.fontSize = '{size_pt_str}pt';
            #         span.innerHTML = '​'; // Zero-width space
            #         range.insertNode(span);
            #         range.setStartAfter(span);
            #         range.collapse(true);
            #         sel.removeAllRanges();
            #         sel.addRange(range);
            #     }} else {{
            #         // Apply to selected text - execCommand often handles this better
            #         // document.execCommand('fontSize', false, '{webkit_size}'); // Already done above
            #         // Could try to wrap with styled span here too, more complex
            #     }}
            # }})();
            # """)

            # No need to call update_formatting_ui here, selection change handles it
            self.webview.grab_focus()

    # --- Dark Mode Toggle ---
    def on_dark_mode_toggled(self, btn):
         # Target the .page element for theme changes
        if btn.get_active():
            btn.set_icon_name("weather-clear-night")
            # Apply dark theme styles to the page
            script = """
            const page = document.querySelector('.page');
            if (page) {
                page.style.backgroundColor = '#1e1e1e';
                page.style.color = '#e0e0e0';
            }
            // Optionally change the outer background too
            document.documentElement.style.backgroundColor = '#333';
            """
        else:
            btn.set_icon_name("display-brightness")
            # Apply light theme styles to the page
            script = """
            const page = document.querySelector('.page');
            if (page) {
                page.style.backgroundColor = '#ffffff';
                page.style.color = '#000000';
            }
             // Optionally change the outer background too
            document.documentElement.style.backgroundColor = '#ccc';
            """
        self.exec_js(script)
        self.webview.grab_focus()


    # --- File Operations (New, Open, Save, Save As) ---

    def update_title(self):
        modified_marker = " *" if self.is_modified else ""
        if self.current_file and not self.is_new:
            try:
                base_name = os.path.splitext(self.current_file.get_basename())[0]
                title = f"{base_name}{modified_marker} – Writer"
            except TypeError: # Handle cases where get_basename might return None initially
                 title = f"Document {self.document_number}{modified_marker} – Writer"
        else:
            title = f"Document {self.document_number}{modified_marker} – Writer"
        self.set_title(title)

    def on_new_clicked(self, btn):
        # Check if modifications need saving before proceeding
        if self.is_modified:
            self.show_save_confirmation_dialog(self.perform_new_action)
        else:
            self.perform_new_action("discard") # Directly perform if not modified

    def perform_new_action(self, response):
        """Performs the 'new document' action after confirmation."""
        if response in ["save", "discard"]:
             # If saving, the save operation happens first via the dialog response.
             # Here, we just reset the state for the new document.
             if response == "discard" or not self.is_modified: # Proceed if discarded or wasn't modified
                self.ignore_changes = True # Prevent modification flag during load
                self.webview.load_html(self.initial_html, "file:///")
                self.current_file = None
                self.is_new = True
                self.is_modified = False # Reset modification status
                self.document_number = EditorWindow.document_counter
                EditorWindow.document_counter += 1
                self.update_title()
                # clear_ignore_changes is called by on_webview_load finish handler
                # Reset formatting state/UI might be needed here if desired
                self.reset_formatting_state()
                GLib.timeout_add(100, lambda: self.update_formatting_ui(None)) # Update UI after slight delay


    def on_open_clicked(self, btn):
         if self.is_modified:
            self.show_save_confirmation_dialog(self.perform_open_action)
         else:
            self.perform_open_action("discard") # Directly open if not modified


    def perform_open_action(self, response):
        """Shows the open dialog after confirmation."""
        if response in ["save", "discard"]:
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
        try:
            file = dialog.open_finish(result)
            if file:
                self.current_file = file
                self.is_new = False
                self.update_title() # Update title before loading starts
                # Load contents asynchronously
                file.load_contents_async(None, self.load_html_callback)
        except GLib.Error as e:
            if e.code != Gio.IOErrorEnum.CANCELLED: # Ignore user cancellation
                print(f"Open error: {e.message}")
                self.show_error_dialog("Error Opening File", f"Could not open the selected file:\n{e.message}")

    def load_html_callback(self, file, result):
        try:
            ok, content_bytes, _ = file.load_contents_finish(result)
            if ok:
                self.ignore_changes = True # Ignore changes during load
                html_content = content_bytes.decode('utf-8') # Ensure decoding
                # Check if the loaded content has our .page structure, add if missing
                if '<div class="page">' not in html_content:
                     # Basic wrapping - might not be perfect for complex files
                     body_match = re.search(r"<body.*?>(.*?)</body>", html_content, re.IGNORECASE | re.DOTALL)
                     if body_match:
                          body_content = body_match.group(1)
                          html_content = re.sub(r"(<body.*?>)(.*?)(</body>)",
                                                rf'\1<div class="page">{body_content}</div>\3',
                                                html_content, flags=re.IGNORECASE | re.DOTALL)
                     else: # Fallback if body tag not found (unlikely for valid html)
                          html_content = f'<html><head><style>/* Minimal styles */</style></head><body contenteditable="true"><div class="page">{html_content}</div></body></html>'

                self.webview.load_html(html_content, file.get_uri())
                self.is_modified = False # Reset modified state after successful load
                self.update_title()
                # clear_ignore_changes is handled by on_webview_load finish
                # Update UI after load finishes (handled by selection change)
            else:
                 raise GLib.Error("Failed to load file contents.")
        except GLib.Error as e:
            print(f"Load error: {e.message}")
            self.show_error_dialog("Error Loading File", f"Could not read the file contents:\n{e.message}")
            # Reset state if loading failed
            self.current_file = None
            self.is_new = True
            self.update_title()
        except Exception as e: # Catch decoding errors etc.
             print(f"Unexpected error during file load: {e}")
             self.show_error_dialog("Error Loading File", f"An unexpected error occurred:\n{e}")
             self.current_file = None
             self.is_new = True
             self.update_title()


    def on_save_clicked(self, btn):
        if self.current_file and not self.is_new:
            # Save to the existing file
            self.save_content_to_file(self.current_file)
        else:
            # No current file or it's a new doc, show Save As dialog
            self.show_save_dialog()

    def on_save_as_clicked(self, btn):
        self.show_save_dialog()

    def show_save_dialog(self):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Save File As")

        # Suggest a filename
        if self.current_file and not self.is_new:
            dialog.set_initial_file(self.current_file) # Suggest current file
        else:
            dialog.set_initial_name(f"Document {self.document_number}.html") # Suggest default name

        # Set file filter
        filter_html = Gtk.FileFilter()
        filter_html.set_name("HTML Files (*.html)")
        filter_html.add_pattern("*.html")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_html)
        dialog.set_filters(filters)
        dialog.set_default_filter(filter_html)

        dialog.save(self, None, self.save_dialog_response_callback)

    def save_dialog_response_callback(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                # User selected a file, now save the content
                self.save_content_to_file(file)
        except GLib.Error as e:
            if e.code != Gio.IOErrorEnum.CANCELLED:
                print(f"Save As error: {e.message}")
                self.show_error_dialog("Error Saving File", f"Could not save the file:\n{e.message}")

    def save_content_to_file(self, file):
        """Gets HTML from WebView and saves it to the specified Gio.File."""
        # Get the complete HTML content
        self.webview.evaluate_javascript(
            # Get outerHTML of the html element for full document structure
            "document.documentElement.outerHTML;",
            -1, None, None, None, self.get_html_for_save_callback, file # Pass file as user_data
        )

    def get_html_for_save_callback(self, webview, result, file):
        """Callback after getting HTML content from JavaScript."""
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                html_content = js_value.to_string()
                if not html_content:
                     raise ValueError("Received empty HTML content from WebView.")

                # Convert string to bytes for saving
                content_bytes = GLib.Bytes.new(html_content.encode('utf-8'))

                # Save asynchronously, replacing existing content
                file.replace_contents_bytes_async(
                    content_bytes,
                    None, # Etag (optional)
                    False, # Make backup
                    Gio.FileCreateFlags.REPLACE_DESTINATION,
                    None, # Cancellable
                    self.final_save_callback,
                    file # Pass file to final callback to update state
                )
            else:
                 raise ValueError("Failed to get HTML content from WebView.")

        except GLib.Error as e:
            print(f"Error getting HTML for saving: {e.message}")
            self.show_error_dialog("Error Saving File", f"Could not retrieve content from the editor:\n{e.message}")
        except Exception as e: # Catch encoding errors, etc.
             print(f"Unexpected error preparing content for save: {e}")
             self.show_error_dialog("Error Saving File", f"An unexpected error occurred while preparing the content:\n{e}")

    def final_save_callback(self, file_obj, result, saved_file):
        """Callback after the asynchronous save operation finishes."""
        try:
            # Finish the replace operation (important!)
            # `file_obj` here is the source object used for the async call
            # `saved_file` is the Gio.File we passed as user_data
            success = file_obj.replace_contents_finish(result) # Returns True/False

            if success:
                print(f"File saved successfully: {saved_file.get_path()}")
                self.current_file = saved_file # Update current file reference
                self.is_new = False # It's no longer a new, unnamed file
                self.is_modified = False # Mark as unmodified
                self.update_title() # Update window title
            else:
                 # This path might be less common if exceptions are raised earlier
                 raise GLib.Error("Failed to replace file contents.")

        except GLib.Error as e:
            print(f"Final save error: {e.message}")
            self.show_error_dialog("Error Saving File", f"Could not write the file to disk:\n{e.message}")
        except Exception as e:
             print(f"Unexpected error during final save: {e}")
             self.show_error_dialog("Error Saving File", f"An unexpected error occurred during saving:\n{e}")


    # --- Edit Operations (Cut, Copy, Paste, Undo, Redo) ---
    def on_cut_clicked(self, btn):
        self.exec_js("document.execCommand('cut')")
        self.webview.grab_focus()

    def on_copy_clicked(self, btn):
        self.exec_js("document.execCommand('copy')")
        self.webview.grab_focus()

    def on_paste_clicked(self, btn):
        # Use execCommand for paste - allows browser to handle different content types
        self.exec_js("document.execCommand('paste')")
        self.webview.grab_focus()
        # Note: Reading clipboard manually (like in original code) is complex
        # due to async nature and handling different formats (HTML, text).
        # Relying on execCommand is generally simpler for rich text.

    def on_undo_clicked(self, btn):
        self.exec_js("document.execCommand('undo')")
        self.webview.grab_focus()

    def on_redo_clicked(self, btn):
        self.exec_js("document.execCommand('redo')")
        self.webview.grab_focus()

    # --- Keyboard Shortcuts ---
    def on_key_pressed(self, controller, keyval, keycode, state):
        # Ctrl key is pressed (or Cmd on macOS, GDK handles this)
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        # Shift key is pressed
        shift = (state & Gdk.ModifierType.SHIFT_MASK) != 0
        # Alt key is pressed
        alt = (state & Gdk.ModifierType.ALT_MASK) != 0 # Gdk.ModifierType.MOD1_MASK in older GTK

        consumed = False # Flag to indicate if we handled the key press

        if ctrl and not shift and not alt:
            if keyval == Gdk.KEY_b: consumed = self.trigger_button(self.bold_btn)
            elif keyval == Gdk.KEY_i: consumed = self.trigger_button(self.italic_btn)
            elif keyval == Gdk.KEY_u: consumed = self.trigger_button(self.underline_btn)
            elif keyval == Gdk.KEY_s: consumed = self.on_save_clicked(None) or True
            elif keyval == Gdk.KEY_o: consumed = self.on_open_clicked(None) or True
            elif keyval == Gdk.KEY_n: consumed = self.on_new_clicked(None) or True
            elif keyval == Gdk.KEY_w: consumed = self.close_request() or True # Trigger close
            # Cut/Copy/Paste/Undo/Redo often handled by WebView/OS, but can override
            # elif keyval == Gdk.KEY_x: consumed = self.on_cut_clicked(None) or True
            # elif keyval == Gdk.KEY_c: consumed = self.on_copy_clicked(None) or True
            # elif keyval == Gdk.KEY_v: consumed = self.on_paste_clicked(None) or True
            elif keyval == Gdk.KEY_z: consumed = self.on_undo_clicked(None) or True
            elif keyval == Gdk.KEY_y: consumed = self.on_redo_clicked(None) or True # Redo often Ctrl+Y or Ctrl+Shift+Z
            # Alignment
            elif keyval == Gdk.KEY_l: consumed = self.trigger_button(self.align_left_btn) # Ctrl+L usually location bar
            elif keyval == Gdk.KEY_e: consumed = self.trigger_button(self.align_center_btn)
            elif keyval == Gdk.KEY_r: consumed = self.trigger_button(self.align_right_btn)
            elif keyval == Gdk.KEY_j: consumed = self.trigger_button(self.align_justify_btn)
             # Headings (Ctrl+Alt+Num usually better, but for simplicity)
            elif keyval == Gdk.KEY_0: consumed = self.set_dropdown_index(self.heading_dropdown, 0) # Normal
            elif keyval == Gdk.KEY_1: consumed = self.set_dropdown_index(self.heading_dropdown, 1) # H1
            elif keyval == Gdk.KEY_2: consumed = self.set_dropdown_index(self.heading_dropdown, 2) # H2
            elif keyval == Gdk.KEY_3: consumed = self.set_dropdown_index(self.heading_dropdown, 3) # H3
            elif keyval == Gdk.KEY_4: consumed = self.set_dropdown_index(self.heading_dropdown, 4) # H4
            elif keyval == Gdk.KEY_5: consumed = self.set_dropdown_index(self.heading_dropdown, 5) # H5
            elif keyval == Gdk.KEY_6: consumed = self.set_dropdown_index(self.heading_dropdown, 6) # H6

        elif ctrl and shift and not alt:
            if keyval == Gdk.KEY_S: consumed = self.on_save_as_clicked(None) or True
            elif keyval == Gdk.KEY_Z: consumed = self.on_redo_clicked(None) or True # Common alternative Redo
            elif keyval == Gdk.KEY_X: consumed = self.trigger_button(self.strikethrough_btn)
            elif keyval == Gdk.KEY_L: consumed = self.trigger_button(self.bullet_btn) # Or maybe Ctrl+Shift+8?
            elif keyval == Gdk.KEY_asterisk: consumed = self.trigger_button(self.bullet_btn) # Ctrl+Shift+* (often 8)
            elif keyval == Gdk.KEY_7: consumed = self.trigger_button(self.number_btn) # Ctrl+Shift+7 (&)

        # Add other combos if needed (e.g., Ctrl+Alt)

        return consumed # Return True if handled, False to allow default processing

    def trigger_button(self, button):
        """Helper to simulate a click/toggle on a button for shortcuts."""
        if isinstance(button, Gtk.ToggleButton):
            button.set_active(not button.get_active()) # Toggles the button state
        elif isinstance(button, Gtk.Button):
            button.clicked() # Emits the clicked signal
        return True # Assume handled

    def set_dropdown_index(self, dropdown, index):
         """Helper to set dropdown index and trigger its action."""
         if dropdown.get_model() and index < dropdown.get_model().get_n_items():
              dropdown.set_selected(index)
              # Manually emit notify::selected if needed, depends on handler connection
              # dropdown.emit("notify::selected") # Or directly call the handler
              if dropdown == self.heading_dropdown:
                   self.on_heading_changed(dropdown)
              # Add elif for other dropdowns if necessary
              return True
         return False

    # --- Dialogs and State Management ---

    def show_save_confirmation_dialog(self, callback_on_confirm):
        """Shows a dialog asking to save, discard, or cancel."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Save Changes?",
            body=f"There are unsaved changes in '{self.get_title()}'.\nDo you want to save them?",
            destroy_with_parent=True
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.add_response("save", "Save")
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        def on_response(d, response_id):
            if response_id == "save":
                # Initiate save, then call the original action callback after save completes
                # Modify save_content_to_file or its callbacks to trigger callback_on_confirm('save')
                # For simplicity now, assume save happens, then call callback.
                # A more robust solution needs chaining.
                if self.current_file and not self.is_new:
                     self.save_content_to_file(self.current_file)
                     # FIXME: Saving is async. Callback should ideally be chained *after* save finishes.
                     # For now, call immediately after initiating save. Might race.
                     GLib.idle_add(callback_on_confirm, "save")

                else:
                     self.show_save_dialog() # This flow needs more work to chain the callback
                     # Maybe pass callback_on_confirm to the save dialog flow?
                     print("FIXME: Chaining callback after Save As dialog not fully implemented.")
                     # For now, cancel the original action if Save As is needed here.
                     pass # Or call callback_on_confirm("cancel") ?

            elif response_id == "discard":
                callback_on_confirm("discard") # Call the original action with 'discard'
            # else response is "cancel" - do nothing
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.present()


    def on_close_request(self, *args):
        """Handle the window close request (X button or Ctrl+W)."""
        if self.is_modified:
            dialog = Adw.MessageDialog(
                transient_for=self,
                modal=True,
                heading="Quit Without Saving?",
                body=f"There are unsaved changes in '{self.get_title()}'.\nClosing will discard these changes.",
                 destroy_with_parent=True
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard Changes")
            dialog.add_response("save", "Save")
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

            def on_response(d, response_id):
                if response_id == "save":
                     # FIXME: Need robust way to ensure app quits *after* save finishes
                     if self.current_file and not self.is_new:
                          self.save_content_to_file(self.current_file)
                          # Problem: save is async. Quit might happen before save finishes.
                          # Need a signal/callback from save completion to quit.
                          print("FIXME: Quitting after async save needs proper handling.")
                          GLib.timeout_add(500, self.get_application().quit) # Quit after delay (bad!)
                     else:
                          self.show_save_dialog()
                          # How to quit after Save As dialog finishes? Needs chaining.
                          print("FIXME: Quitting after Save As needs proper handling.")
                          # Don't quit automatically here. User might cancel Save As.

                elif response_id == "discard":
                    self.get_application().quit() # Quit immediately
                # else response is "cancel" - do nothing, close is aborted
                dialog.destroy()

            dialog.connect("response", on_response)
            dialog.present()
            return True # Prevent default close if modified

        # Not modified, allow close immediately
        self.get_application().quit() # Or just return False to let default handler close?
        return False # Let the default handler close the window


    def show_error_dialog(self, title, message):
        """Displays a simple error message dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading=title,
            body=message,
             destroy_with_parent=True
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def clear_ignore_changes(self):
        """Callback to reset the ignore_changes flag."""
        self.ignore_changes = False
        # Trigger an initial selection check *after* ignoring is off
        self.webview.evaluate_javascript("document.dispatchEvent(new Event('selectionchange'));", -1, None, None, None, None, None)
        return False # Remove the timeout source

    def reset_formatting_state(self):
         """Resets internal formatting state variables to default."""
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
         self.current_font = "Sans" # Or get default from dropdown model
         self.current_font_size = "12"

         # Find default font index
         font_store = self.font_dropdown.get_model()
         default_font_index = 0
         if font_store:
              names = [font_store.get_string(i).lower() for i in range(font_store.get_n_items())]
              try:
                   default_font_index = names.index('sans')
              except ValueError: pass # Keep 0 if sans not found

         # Find default size index
         default_size_index = 5 # Index for '12'
         try:
             default_size_index = self.size_range.index('12')
         except ValueError: pass

         # Reset Dropdowns (block handlers to prevent signals)
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
    import sys, re # Import re for potential HTML manipulation on load
    app = Writer()
    app.run(sys.argv)
