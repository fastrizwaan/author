#!/usr/bin/env python3

import os
import gi, json
import re, sys # Added re and sys

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, WebKit, Gio, GLib, Pango, PangoCairo, Gdk
from datetime import datetime

# --- Constants ---
PPI = 96 # Approximate pixels per inch
PLACEHOLDER_HTML = '<p class="placeholder">\u200B</p>' # Placeholder with zero-width space


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
        self.page_margin_inches = 1.0 # Inner padding T/R/B/L
        self.page_gap_px = 20        # Gap below each page

        # Calculate target inner height in pixels for JS
        self.page_height_px = self.page_height_inches * PPI
        self.page_padding_px = self.page_margin_inches * PPI
        self.target_inner_height_px = self.page_height_px - (2 * self.page_padding_px)

        # --- CSS Provider for GTK ---
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

        # --- UI Setup ---
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)
        header = Adw.HeaderBar()
        header.add_css_class("flat-header")
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        toolbar_view.add_top_bar(header)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.webview = WebKit.WebView(editable=True)
        settings = self.webview.get_settings()
        settings.set_enable_developer_extras(True) # Enable DevTools (Right Click -> Inspect Element)
        scroll.set_child(self.webview)

        # --- WebView User Content Manager and Signals ---
        user_content = self.webview.get_user_content_manager()
        user_content.register_script_message_handler('contentChanged')
        user_content.connect('script-message-received::contentChanged', self.on_content_changed_js)
        user_content.register_script_message_handler('selectionChanged')
        user_content.connect('script-message-received::selectionChanged', self.on_selection_changed)
        self.webview.connect('load-changed', self.on_webview_load)

        # --- Initial HTML with Pagination CSS ---
        # Corrected HTML comment escaping {{/* ... */}}
        self.initial_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Editor</title>
    </style>
</head>
<body>
    <div class="content" contenteditable="true"></div>

</body>
</html>"""
        # --- End Initial HTML ---

        # --- Toolbar Setup ---
        file_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0); file_group.add_css_class("toolbar-group")
        edit_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0); edit_group.add_css_class("toolbar-group")
        view_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0); view_group.add_css_class("toolbar-group")
        text_style_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0); text_style_group.add_css_class("toolbar-group")
        text_format_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2); text_format_group.add_css_class("toolbar-group")
        list_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0); list_group.add_css_class("toolbar-group")
        align_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0); align_group.add_css_class("toolbar-group")
        file_toolbar_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15); file_toolbar_group.add_css_class("toolbar-group-container")
        file_toolbar_group.append(file_group); file_toolbar_group.append(edit_group); file_toolbar_group.append(view_group)
        formatting_toolbar_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); formatting_toolbar_group.add_css_class("toolbar-group-container")
        formatting_toolbar_group.append(text_style_group); formatting_toolbar_group.append(text_format_group); formatting_toolbar_group.append(list_group); formatting_toolbar_group.append(align_group)
        toolbars_flowbox = Gtk.FlowBox(); toolbars_flowbox.set_selection_mode(Gtk.SelectionMode.NONE); toolbars_flowbox.set_max_children_per_line(100); toolbars_flowbox.add_css_class("toolbar-container")
        toolbars_flowbox.insert(file_toolbar_group, -1); toolbars_flowbox.insert(formatting_toolbar_group, -1)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox); content_box.append(scroll)
        toolbar_view.set_content(content_box)

        # --- Populate Toolbar Groups ---
        # (This order is important - define widgets before connecting signals that might reference others)
        new_btn = Gtk.Button(icon_name="document-new"); new_btn.add_css_class("flat"); new_btn.connect("clicked", self.on_new_clicked); file_group.append(new_btn)
        open_btn = Gtk.Button(icon_name="document-open"); open_btn.add_css_class("flat"); open_btn.connect("clicked", self.on_open_clicked); file_group.append(open_btn)
        save_btn = Gtk.Button(icon_name="document-save"); save_btn.add_css_class("flat"); save_btn.connect("clicked", self.on_save_clicked); file_group.append(save_btn)
        save_as_btn = Gtk.Button(icon_name="document-save-as"); save_as_btn.add_css_class("flat"); save_as_btn.connect("clicked", self.on_save_as_clicked); file_group.append(save_as_btn)

        cut_btn = Gtk.Button(icon_name="edit-cut"); cut_btn.add_css_class("flat"); cut_btn.connect("clicked", self.on_cut_clicked); edit_group.append(cut_btn)
        copy_btn = Gtk.Button(icon_name="edit-copy"); copy_btn.add_css_class("flat"); copy_btn.connect("clicked", self.on_copy_clicked); edit_group.append(copy_btn)
        paste_btn = Gtk.Button(icon_name="edit-paste"); paste_btn.add_css_class("flat"); paste_btn.connect("clicked", self.on_paste_clicked); edit_group.append(paste_btn)
        undo_btn = Gtk.Button(icon_name="edit-undo"); undo_btn.add_css_class("flat"); undo_btn.connect("clicked", self.on_undo_clicked); edit_group.append(undo_btn)
        redo_btn = Gtk.Button(icon_name="edit-redo"); redo_btn.add_css_class("flat"); redo_btn.connect("clicked", self.on_redo_clicked); edit_group.append(redo_btn)

        self.dark_mode_btn = Gtk.ToggleButton(icon_name="display-brightness"); self.dark_mode_btn.add_css_class("flat"); self.dark_mode_btn.connect("toggled", self.on_dark_mode_toggled); view_group.append(self.dark_mode_btn)

        heading_store = Gtk.StringList(); [heading_store.append(h) for h in ["Normal", "H1", "H2", "H3", "H4", "H5", "H6"]]; self.heading_dropdown = Gtk.DropDown(model=heading_store); self.heading_dropdown_handler = self.heading_dropdown.connect("notify::selected", self.on_heading_changed); self.heading_dropdown.add_css_class("flat"); text_style_group.append(self.heading_dropdown)

        font_map = PangoCairo.FontMap.get_default(); families = font_map.list_families(); font_names = sorted([f.get_name() for f in families]); font_store = Gtk.StringList(strings=font_names); self.font_dropdown = Gtk.DropDown(model=font_store); default_font_index = font_names.index("Sans") if "Sans" in font_names else 0; self.font_dropdown.set_selected(default_font_index); self.font_dropdown_handler = self.font_dropdown.connect("notify::selected", self.on_font_family_changed); self.font_dropdown.add_css_class("flat"); text_style_group.append(self.font_dropdown)

        self.size_range = [str(s) for s in [6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72, 96]]; size_store = Gtk.StringList(strings=self.size_range); self.size_dropdown = Gtk.DropDown(model=size_store); default_size_index = self.size_range.index("12") if "12" in self.size_range else 5; self.size_dropdown.set_selected(default_size_index); self.size_dropdown_handler = self.size_dropdown.connect("notify::selected", self.on_font_size_changed); self.size_dropdown.add_css_class("flat"); text_style_group.append(self.size_dropdown)

        self.bold_btn = Gtk.ToggleButton(icon_name="format-text-bold"); self.bold_btn.add_css_class("flat"); self.bold_btn.connect("toggled", self.on_bold_toggled); text_format_group.append(self.bold_btn)
        self.italic_btn = Gtk.ToggleButton(icon_name="format-text-italic"); self.italic_btn.add_css_class("flat"); self.italic_btn.connect("toggled", self.on_italic_toggled); text_format_group.append(self.italic_btn)
        self.underline_btn = Gtk.ToggleButton(icon_name="format-text-underline"); self.underline_btn.add_css_class("flat"); self.underline_btn.connect("toggled", self.on_underline_toggled); text_format_group.append(self.underline_btn)
        self.strikethrough_btn = Gtk.ToggleButton(icon_name="format-text-strikethrough"); self.strikethrough_btn.add_css_class("flat"); self.strikethrough_btn.connect("toggled", self.on_strikethrough_toggled); text_format_group.append(self.strikethrough_btn)

        # Define all alignment buttons before connecting signals that might reference others
        self.align_left_btn = Gtk.ToggleButton(icon_name="format-justify-left"); self.align_left_btn.add_css_class("flat"); self.align_left_btn.set_active(True)
        self.align_center_btn = Gtk.ToggleButton(icon_name="format-justify-center"); self.align_center_btn.add_css_class("flat")
        self.align_right_btn = Gtk.ToggleButton(icon_name="format-justify-right"); self.align_right_btn.add_css_class("flat")
        self.align_justify_btn = Gtk.ToggleButton(icon_name="format-justify-fill"); self.align_justify_btn.add_css_class("flat")

        # Now connect signals and append
        self.align_left_btn.connect("toggled", self.on_align_left); align_group.append(self.align_left_btn)
        self.align_center_btn.connect("toggled", self.on_align_center); align_group.append(self.align_center_btn)
        self.align_right_btn.connect("toggled", self.on_align_right); align_group.append(self.align_right_btn)
        self.align_justify_btn.connect("toggled", self.on_align_justify); align_group.append(self.align_justify_btn)

        self.bullet_btn = Gtk.ToggleButton(icon_name="view-list-bullet"); self.bullet_btn.add_css_class("flat"); self.bullet_btn.connect("toggled", self.on_bullet_list_toggled); list_group.append(self.bullet_btn)
        self.number_btn = Gtk.ToggleButton(icon_name="view-list-ordered"); self.number_btn.add_css_class("flat"); self.number_btn.connect("toggled", self.on_number_list_toggled); list_group.append(self.number_btn)

        indent_btn = Gtk.Button(icon_name="format-indent-more"); indent_btn.add_css_class("flat"); indent_btn.connect("clicked", self.on_indent_more); list_group.append(indent_btn)
        outdent_btn = Gtk.Button(icon_name="format-indent-less"); outdent_btn.add_css_class("flat"); outdent_btn.connect("clicked", self.on_indent_less); list_group.append(outdent_btn)

        # --- Key Controller & Close Request ---
        key_controller = Gtk.EventControllerKey.new()
        self.webview.add_controller(key_controller)
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.connect("close-request", self.on_close_request)

        # --- Load Initial Content ---
        self.webview.load_html(self.initial_html, "file:///")


    # --- WebView Load Finished Handler ---
    def on_webview_load(self, webview, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            pagination_js = f"""
                (function() {{
                    const PAGE_HEIGHT = {self.page_height_px};
                    const PAGE_PADDING = {self.page_padding_px};
                    const LINE_HEIGHT = 24; // Matches CSS line-height (12pt * 1.5 = 18pt ≈ 24px at 96 PPI)
                    let isPaginating = false;

                    function createNewPage() {{
                        const newPage = document.createElement('div');
                        newPage.className = 'page';
                        newPage.innerHTML = '<p class="placeholder">\\u200B</p>';
                        document.body.appendChild(newPage);
                        return newPage;
                    }}

                    function maintainPlaceholder(page) {{
                        const hasContent = page.textContent.trim() !== '' && 
                                          !(page.children.length === 1 && 
                                            page.children[0].classList.contains('placeholder'));
                        if (!hasContent) {{
                            page.innerHTML = '<p class="placeholder">\\u200B</p>';
                        }}
                    }}

                    function paginateContent() {{
                        if (isPaginating) return;
                        isPaginating = true;

                        let pages = document.querySelectorAll('.page');
                        let currentPage = pages[pages.length - 1];

                        // Check if we need to create new pages
                        while (currentPage.scrollHeight > PAGE_HEIGHT) {{
                            const newPage = createNewPage();
                            let movedContent = false;

                            // Move content until current page fits
                            while (currentPage.scrollHeight > PAGE_HEIGHT) {{
                                const lastChild = currentPage.lastChild;
                                if (!lastChild || (lastChild.classList && lastChild.classList.contains('placeholder'))) break;

                                // Handle text nodes by wrapping in paragraph
                                if (lastChild.nodeType === Node.TEXT_NODE) {{
                                    const wrapper = document.createElement('p');
                                    wrapper.appendChild(lastChild);
                                    currentPage.replaceChild(wrapper, lastChild);
                                }}

                                newPage.insertBefore(lastChild, newPage.firstChild);
                                movedContent = true;
                            }}

                            if (movedContent) {{
                                maintainPlaceholder(currentPage);
                            }} else {{
                                newPage.remove();
                            }}

                            currentPage = document.querySelector('.page:last-child');
                        }}

                        // Cleanup empty pages (keep at least one)
                        document.querySelectorAll('.page').forEach((page, index) => {{
                            if (index !== 0 && page.innerHTML.trim() === '') {{
                                page.remove();
                            }}
                        }});

                        isPaginating = false;
                    }}

                    // Event listeners
                    document.addEventListener('input', paginateContent);
                    document.addEventListener('paste', paginateContent);

                    // Initial setup
                    if (!document.querySelector('.page')) createNewPage();
                    setTimeout(() => {{
                        paginateContent();
                        document.querySelector('.page').focus();
                    }}, 100);

                    // Notify Python of content changes
                    document.addEventListener('input', () => {{
                        window.webkit.messageHandlers.contentChanged.postMessage('changed');
                    }});

                    // Selection change handler
                    document.addEventListener('selectionchange', () => {{
                        const sel = window.getSelection();
                        let state = {{}};
                        if (sel.rangeCount > 0) {{
                            try {{
                                state.bold = document.queryCommandState('bold');
                                state.italic = document.queryCommandState('italic');
                                state.underline = document.queryCommandState('underline');
                                state.strikethrough = document.queryCommandState('strikeThrough');
                                state.insertUnorderedList = document.queryCommandState('insertUnorderedList');
                                state.insertOrderedList = document.queryCommandState('insertOrderedList');
                                state.justifyLeft = document.queryCommandState('justifyLeft');
                                state.justifyCenter = document.queryCommandState('justifyCenter');
                                state.justifyRight = document.queryCommandState('justifyRight');
                                state.justifyFull = document.queryCommandState('justifyFull');
                                state.formatBlock = document.queryCommandValue('formatBlock') || 'p';
                                const style = window.getComputedStyle(sel.focusNode.parentElement || document.body);
                                state.fontName = style.fontFamily.split(',')[0].replace(/['"]/g, '').trim();
                                state.fontSize = style.fontSize;
                            }} catch (e) {{
                                console.error('Error in selectionchange:', e);
                            }}
                        }}
                        window.webkit.messageHandlers.selectionChanged.postMessage(JSON.stringify(state));
                    }});
                }})();
            """
            webview.evaluate_javascript(pagination_js, -1, None, None, None, None, None)
            self.ignore_changes = True
            GLib.timeout_add(700, self.clear_ignore_changes)

    # --- Python Signal Handlers ---
    def on_content_changed_js(self, manager, js_result):
        if getattr(self, 'ignore_changes', False): return
        if not self.is_modified:
            self.is_modified = True
            self.update_title()

    def on_selection_changed(self, user_content, message):
        if message.is_string():
            try:
                state_str = message.to_string(); state = json.loads(state_str)
                self.update_formatting_ui(state)
            except (json.JSONDecodeError, Exception) as e: print(f"Error processing selection update: {e}")
        else: print("Error: Expected string message from selectionChanged")

    # --- UI Update Methods ---
    def update_formatting_ui(self, state=None):
        if state:
            self.bold_btn.handler_block_by_func(self.on_bold_toggled); self.bold_btn.set_active(state.get('bold', False)); self.bold_btn.handler_unblock_by_func(self.on_bold_toggled)
            self.italic_btn.handler_block_by_func(self.on_italic_toggled); self.italic_btn.set_active(state.get('italic', False)); self.italic_btn.handler_unblock_by_func(self.on_italic_toggled)
            self.underline_btn.handler_block_by_func(self.on_underline_toggled); self.underline_btn.set_active(state.get('underline', False)); self.underline_btn.handler_unblock_by_func(self.on_underline_toggled)
            self.strikethrough_btn.handler_block_by_func(self.on_strikethrough_toggled); self.strikethrough_btn.set_active(state.get('strikethrough', False)); self.strikethrough_btn.handler_unblock_by_func(self.on_strikethrough_toggled)
            self.bullet_btn.handler_block_by_func(self.on_bullet_list_toggled); self.bullet_btn.set_active(state.get('insertUnorderedList', False)); self.bullet_btn.handler_unblock_by_func(self.on_bullet_list_toggled)
            self.number_btn.handler_block_by_func(self.on_number_list_toggled); self.number_btn.set_active(state.get('insertOrderedList', False)); self.number_btn.handler_unblock_by_func(self.on_number_list_toggled)
            is_center=state.get('justifyCenter',False); is_right=state.get('justifyRight',False); is_full=state.get('justifyFull',False); is_left=not(is_center or is_right or is_full)
            align_states={'justifyLeft':(self.align_left_btn,self.on_align_left,is_left),'justifyCenter':(self.align_center_btn,self.on_align_center,is_center),'justifyRight':(self.align_right_btn,self.on_align_right,is_right),'justifyFull':(self.align_justify_btn,self.on_align_justify,is_full)}
            for align,(btn,handler,is_active) in align_states.items(): btn.handler_block_by_func(handler); btn.set_active(is_active); btn.handler_unblock_by_func(handler)

            # CORRECTED Heading Dropdown Index Logic
            format_block = state.get('formatBlock', 'p').lower()
            headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
            index = 0
            try:
                if format_block in headings:
                    index = headings.index(format_block)
            except ValueError:
                 index = 0 # Fallback
            if not (0 <= index < len(headings)): index = 0
            self.heading_dropdown.handler_block(self.heading_dropdown_handler)
            model = self.heading_dropdown.get_model()
            if model and index < model.get_n_items(): self.heading_dropdown.set_selected(index)
            else: self.heading_dropdown.set_selected(0)
            self.heading_dropdown.handler_unblock(self.heading_dropdown_handler)

            detected_font=state.get('fontName', self.current_font).lower().strip(); font_store=self.font_dropdown.get_model(); final_font_index=Gtk.INVALID_LIST_POSITION
            if font_store:
                names = [font_store.get_string(i).lower() for i in range(font_store.get_n_items())]; exact=names.index(detected_font) if detected_font in names else -1
                partial = next((i for i,n in enumerate(names) if exact == -1 and (detected_font.startswith(n) or n.startswith(detected_font))), -1)
                if exact != -1: final_font_index=exact
                elif partial != -1: final_font_index=partial
                else: final_font_index = self.font_dropdown.get_selected(); final_font_index = (names.index('sans') if 'sans' in names else 0) if final_font_index == Gtk.INVALID_LIST_POSITION else final_font_index
            if final_font_index != Gtk.INVALID_LIST_POSITION and final_font_index < font_store.get_n_items(): self.current_font = font_store.get_string(final_font_index); self.font_dropdown.handler_block(self.font_dropdown_handler); self.font_dropdown.set_selected(final_font_index); self.font_dropdown.handler_unblock(self.font_dropdown_handler)

            font_size_str=state.get('fontSize',f'{self.current_font_size}pt'); font_size_pt_str=self.current_font_size
            try:
                if font_size_str.endswith('pt'): font_size_pt_str=str(round(float(font_size_str[:-2])))
                elif font_size_str.endswith('px'): px=float(font_size_str[:-2]); font_size_pt_str='6' if px<=8 else('8' if px<=11 else('9' if px<=12 else('10' if px<=13.3 else('11' if px<=14.6 else('12' if px<=16 else('14' if px<=18.6 else('16' if px<=21.3 else('18' if px<=24 else('20' if px<=26.6 else('22' if px<=29.3 else('24' if px<=32 else('26' if px<=34.6 else('28' if px<=37.3 else('36' if px<=48 else('48' if px<=64 else('72' if px<=96 else '96'))))))))))))))))
                elif '%' in font_size_str or 'em' in font_size_str: pass
                else: font_size_pt_str=str(round(float(font_size_str)))
            except(ValueError, TypeError): pass
            selected_size_index=Gtk.INVALID_LIST_POSITION
            try: target_pt=int(font_size_pt_str); closest=min(self.size_range, key=lambda s:abs(int(s)-target_pt)); selected_size_index=self.size_range.index(closest)
            except(ValueError, IndexError): selected_size_index=self.size_dropdown.get_selected(); selected_size_index=(self.size_range.index('12') if '12' in self.size_range else 5) if selected_size_index==Gtk.INVALID_LIST_POSITION else selected_size_index
            if selected_size_index!=Gtk.INVALID_LIST_POSITION: self.current_font_size=self.size_range[selected_size_index]; self.size_dropdown.handler_block(self.size_dropdown_handler); self.size_dropdown.set_selected(selected_size_index); self.size_dropdown.handler_unblock(self.size_dropdown_handler)
        else:
             font_store = self.font_dropdown.get_model(); selected_font_index = 0
             if font_store: names=[font_store.get_string(i).lower() for i in range(font_store.get_n_items())]; selected_font_index=(names.index(self.current_font.lower()) if self.current_font.lower() in names else 0)
             self.font_dropdown.handler_block(self.font_dropdown_handler); self.font_dropdown.set_selected(selected_font_index); self.font_dropdown.handler_unblock(self.font_dropdown_handler)
             selected_size_index = (self.size_range.index(self.current_font_size) if self.current_font_size in self.size_range else 5)
             self.size_dropdown.handler_block(self.size_dropdown_handler); self.size_dropdown.set_selected(selected_size_index); self.size_dropdown.handler_unblock(self.size_dropdown_handler)

    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def exec_js_with_result(self, js_code, callback, user_data=None):
        self.webview.evaluate_javascript(js_code, -1, None, None, None, callback, user_data)

    # --- Formatting Toggle Handlers ---
    def _generic_toggle_handler(self, btn, command, state_attr, query_command, toggle_func):
        processing_attr = f'_processing_{state_attr}';
        if getattr(self, processing_attr, False): return
        setattr(self, processing_attr, True)
        def get_state_callback(webview, result, user_data):
            button, attribute, handler_func = user_data; current_state = None
            try:
                js_value = webview.evaluate_javascript_finish(result); current_state = js_value.to_boolean()
                setattr(self, attribute, current_state); button.handler_block_by_func(handler_func); button.set_active(current_state); button.handler_unblock_by_func(handler_func);
            except (GLib.Error, Exception) as e: print(f"Error get state '{command}': {e}. Fallback."); fallback=not getattr(self,attribute,button.get_active()); setattr(self,attribute,fallback); button.handler_block_by_func(handler_func); button.set_active(fallback); button.handler_unblock_by_func(handler_func)
            finally: setattr(self, processing_attr, False)
        self.exec_js(f"document.execCommand('{command}')")
        GLib.timeout_add(50, lambda: self.exec_js_with_result(f"document.queryCommandState('{query_command}')", get_state_callback, (btn, state_attr, toggle_func)) or False)

    def on_bold_toggled(self, btn): self._generic_toggle_handler(btn, 'bold', 'is_bold', 'bold', self.on_bold_toggled)
    def on_italic_toggled(self, btn): self._generic_toggle_handler(btn, 'italic', 'is_italic', 'italic', self.on_italic_toggled)
    def on_underline_toggled(self, btn): self._generic_toggle_handler(btn, 'underline', 'is_underline', 'underline', self.on_underline_toggled)
    def on_strikethrough_toggled(self, btn): self._generic_toggle_handler(btn, 'strikeThrough', 'is_strikethrough', 'strikeThrough', self.on_strikethrough_toggled)

    def _list_toggle_handler(self, btn, command, state_attr, query_command, toggle_func, other_btn, other_attr, other_func):
        processing_attr = f'_processing_{state_attr}';
        if getattr(self, processing_attr, False): return
        setattr(self, processing_attr, True)
        def get_state_callback(webview, result, user_data):
            button, attribute, handler_func, other_button, other_attribute, other_handler_func = user_data; current_state = None
            try:
                js_value = webview.evaluate_javascript_finish(result); current_state = js_value.to_boolean()
                setattr(self, attribute, current_state); button.handler_block_by_func(handler_func); button.set_active(current_state); button.handler_unblock_by_func(handler_func)
                if current_state: setattr(self, other_attribute, False); other_button.handler_block_by_func(other_handler_func); other_button.set_active(False); other_button.handler_unblock_by_func(other_handler_func)
            except (GLib.Error, Exception) as e: print(f"Error get state '{command}': {e}. Fallback."); fallback=not getattr(self,attribute,button.get_active()); setattr(self,attribute,fallback); button.handler_block_by_func(handler_func); button.set_active(fallback); button.handler_unblock_by_func(handler_func);
            finally: setattr(self, processing_attr, False)
        self.exec_js(f"document.execCommand('{command}')")
        GLib.timeout_add(50, lambda: self.exec_js_with_result(f"document.queryCommandState('{query_command}')", get_state_callback, (btn, state_attr, toggle_func, other_btn, other_attr, other_func)) or False)

    def on_bullet_list_toggled(self, btn): self._list_toggle_handler(btn, 'insertUnorderedList', 'is_bullet_list', 'insertUnorderedList', self.on_bullet_list_toggled, self.number_btn, 'is_number_list', self.on_number_list_toggled)
    def on_number_list_toggled(self, btn): self._list_toggle_handler(btn, 'insertOrderedList', 'is_number_list', 'insertOrderedList', self.on_number_list_toggled, self.bullet_btn, 'is_bullet_list', self.on_bullet_list_toggled)

    # --- Alignment Handler (Simplified) ---
    def _align_handler(self, btn, command, state_attr, query_command, handler_func):
        # Only execute the command. UI update relies on selectionChanged.
        self.exec_js(f"document.execCommand('{command}')")
        # Set internal flag immediately for potential later reference if needed
        setattr(self, 'is_align_left', btn == self.align_left_btn)
        setattr(self, 'is_align_center', btn == self.align_center_btn)
        setattr(self, 'is_align_right', btn == self.align_right_btn)
        setattr(self, 'is_align_justify', btn == self.align_justify_btn)

    def on_align_left(self, btn): self._align_handler(btn, 'justifyLeft', 'is_align_left', 'justifyLeft', self.on_align_left)
    def on_align_center(self, btn): self._align_handler(btn, 'justifyCenter', 'is_align_center', 'justifyCenter', self.on_align_center)
    def on_align_right(self, btn): self._align_handler(btn, 'justifyRight', 'is_align_right', 'justifyRight', self.on_align_right)
    def on_align_justify(self, btn): self._align_handler(btn, 'justifyFull', 'is_align_justify', 'justifyFull', self.on_align_justify)

    def on_indent_more(self, btn): self.exec_js("document.execCommand('indent')")
    def on_indent_less(self, btn): self.exec_js("document.execCommand('outdent')")

    def on_heading_changed(self, dropdown, *args):
        headings = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]; idx = dropdown.get_selected()
        tag = headings[idx] if 0 <= idx < len(headings) else 'p'
        self.exec_js(f"document.execCommand('formatBlock', false, '<{tag}>')")

    def on_font_family_changed(self, dropdown, *args):
        item = dropdown.get_selected_item(); font_name = item.get_string() if item else self.current_font
        self.current_font = font_name
        self.exec_js(f"document.execCommand('fontName', false, {json.dumps(font_name)})")

    def on_font_size_changed(self, dropdown, *args):
        item = dropdown.get_selected_item()
        if item:
            size_pt_str = item.get_string()
            self.current_font_size = size_pt_str
            # CORRECTED: Properly indented try...except block
            webkit_size = '3' # Default ~12pt
            try:
                 s = int(size_pt_str)
                 if s <= 9: webkit_size = '1'
                 elif s <= 11: webkit_size = '2'
                 elif s <= 14: webkit_size = '3'
                 elif s <= 18: webkit_size = '4'
                 elif s <= 24: webkit_size = '5'
                 elif s <= 36: webkit_size = '6'
                 else: webkit_size = '7'
            except ValueError:
                 pass # Keep default webkit_size if conversion fails

            self.exec_js(f"document.execCommand('fontSize', false, '{webkit_size}')")

    # --- Dark Mode ---
    def on_dark_mode_toggled(self, btn):
        # CORRECTED: Escaped all JS {{}}
        if btn.get_active():
            btn.set_icon_name("weather-clear-night")
            script = "document.documentElement.style.backgroundColor = '#333'; document.querySelectorAll('.page').forEach(p => {{ p.style.backgroundColor = '#1e1e1e'; p.style.color = '#e0e0e0'; }});"
        else:
            btn.set_icon_name("display-brightness")
            script = "document.documentElement.style.backgroundColor = '#ccc'; document.querySelectorAll('.page').forEach(p => {{ p.style.backgroundColor = '#ffffff'; p.style.color = '#000000'; }});"
        self.exec_js(script)

    # --- File Operations & Confirmation Logic ---
    def update_title(self):
        modified_marker = " *" if self.is_modified else ""
        title_base = f"Document {self.document_number}"
        if self.current_file and not self.is_new:
            try: basename = self.current_file.get_basename(); title_base = os.path.splitext(basename)[0] if basename else title_base
            except TypeError: pass
        self.set_title(f"{title_base}{modified_marker} – Writer")

    def on_new_clicked(self, btn):
        if self.is_modified: self.show_save_confirmation_dialog(self.perform_new_action)
        else: self.perform_new_action("discard")

    def perform_new_action(self, response_id):
        if response_id in ["save", "discard"]:
            self.ignore_changes = True; self.webview.load_html(self.initial_html, "file:///")
            self.current_file = None; self.is_new = True; self.is_modified = False
            self.document_number = EditorWindow.document_counter; EditorWindow.document_counter += 1
            self.update_title(); self.reset_formatting_state()

    def on_open_clicked(self, btn):
         if self.is_modified: self.show_save_confirmation_dialog(self.perform_open_action)
         else: self.perform_open_action("discard")

    def perform_open_action(self, response_id):
        if response_id in ["save", "discard"]:
            dialog = Gtk.FileDialog.new(); dialog.set_title("Open File")
            filter_html = Gtk.FileFilter(); filter_html.set_name("HTML Files (*.html, *.htm)"); filter_html.add_pattern("*.html"); filter_html.add_pattern("*.htm")
            filters = Gio.ListStore.new(Gtk.FileFilter); filters.append(filter_html); dialog.set_filters(filters); dialog.set_default_filter(filter_html)
            dialog.open(self, None, self.on_open_file_dialog_response)

    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file: self.current_file = file; self.is_new = False; self.update_title(); file.load_contents_async(None, self.load_html_callback)
        except GLib.Error as e:
            if e.code != Gio.IOErrorEnum.CANCELLED: print(f"Open error: {e.message}"); self.show_error_dialog("Error Opening File", f"Could not open file:\n{e.message}")

    def load_html_callback(self, file, result):
        try:
            ok, content_bytes, _ = file.load_contents_finish(result)
            if ok:
                self.ignore_changes = True
                html_content = content_bytes.decode('utf-8', errors='replace')
                body_content_match = re.search(r"<body.*?>(.*?)</body>", html_content, re.IGNORECASE | re.DOTALL)
                inner_content = html_content
                if body_content_match:
                    inner_content = body_content_match.group(1).strip()
                    inner_content = re.sub(r'<div class="page"[^>]*>(.*?)</div>', r'\1', inner_content, flags=re.IGNORECASE | re.DOTALL).strip()

                head_match = re.search(r"<head.*?>(.*?)</head>", self.initial_html, re.IGNORECASE | re.DOTALL)
                head_content = head_match.group(1) if head_match else "<meta charset=\"UTF-8\"><style></style>"

                final_html_to_load = f"""<!DOCTYPE html>
<html>
<head>
    {head_content}
</head>
<body contenteditable="true">
    <div class="page">
        {inner_content if inner_content else PLACEHOLDER_HTML}
    </div>
</body>
</html>"""
                self.webview.load_html(final_html_to_load, file.get_uri())
                self.is_modified = False; self.update_title()
            else: raise GLib.Error("Failed load.")
        except (GLib.Error, Exception) as e: print(f"Load error: {e}"); self.show_error_dialog("Error Loading", f"Could not read/process file:\n{e}"); self.current_file=None; self.is_new=True; self.update_title()

    def on_save_clicked(self, btn): self.initiate_save_with_callback(None)
    def on_save_as_clicked(self, btn): self.initiate_save_with_callback(None)

    def show_save_dialog(self): # Simple save as trigger
        dialog = Gtk.FileDialog.new(); dialog.set_title("Save File As")
        if self.current_file and not self.is_new: dialog.set_initial_file(self.current_file)
        else: dialog.set_initial_name(f"Document {self.document_number}.html")
        filter_html = Gtk.FileFilter(); filter_html.set_name("HTML Files (*.html)"); filter_html.add_pattern("*.html")
        filters = Gio.ListStore.new(Gtk.FileFilter); filters.append(filter_html); dialog.set_filters(filters); dialog.set_default_filter(filter_html)
        dialog.save(self, None, self.save_dialog_response_callback)

    def save_dialog_response_callback(self, dialog, result): # Simple save as response
        try:
            file = dialog.save_finish(result)
            if file: self.save_content_to_file(file)
        except GLib.Error as e:
            if e.code != Gio.IOErrorEnum.CANCELLED: print(f"Save As error: {e.message}"); self.show_error_dialog("Error Saving File", f"Could not save file:\n{e.message}")

    def show_save_confirmation_dialog(self, action_callback, action_args=None):
        dialog = Adw.MessageDialog(transient_for=self, modal=True, heading="Save Changes?", body=f"Unsaved changes in '{self.get_title()}'.\nSave them?", destroy_with_parent=True)
        dialog.add_response("cancel", "Cancel"); dialog.add_response("discard", "Discard"); dialog.add_response("save", "Save")
        dialog.set_default_response("save"); dialog.set_close_response("cancel"); dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE); dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.user_data = (action_callback, action_args)
        dialog.connect("response", self.on_save_confirmation_response)
        dialog.present()

    def on_save_confirmation_response(self, dialog, response_id):
        action_callback, action_args = dialog.user_data if hasattr(dialog, 'user_data') else (None, None)
        if not action_callback: dialog.destroy(); return
        if response_id == "save":
             def run_action_after_save(success):
                  if success: GLib.idle_add(action_callback, response_id, *(action_args or []))
                  if dialog and dialog.get_visible(): dialog.destroy()
             self.initiate_save_with_callback(run_action_after_save)
        elif response_id == "discard": GLib.idle_add(action_callback, response_id, *(action_args or [])); dialog.destroy()
        else: dialog.destroy() # Cancel

    def initiate_save_with_callback(self, post_save_callback):
         if self.current_file and not self.is_new: self.save_content_to_file(self.current_file, post_save_callback)
         else:
             dialog = Gtk.FileDialog.new(); dialog.set_title("Save File As"); dialog.set_initial_name(f"Document {self.document_number}.html")
             filter_html = Gtk.FileFilter(); filter_html.set_name("HTML Files (*.html)"); filter_html.add_pattern("*.html")
             filters = Gio.ListStore.new(Gtk.FileFilter); filters.append(filter_html); dialog.set_filters(filters); dialog.set_default_filter(filter_html)
             dialog.user_data = post_save_callback
             dialog.save(self, None, self.save_as_dialog_response_for_callback)

    def save_as_dialog_response_for_callback(self, dialog, result):
         post_save_callback = dialog.user_data if hasattr(dialog, 'user_data') else None
         try:
             file = dialog.save_finish(result)
             if file: self.save_content_to_file(file, post_save_callback)
             elif post_save_callback: GLib.idle_add(post_save_callback, False)
         except GLib.Error as e:
             if e.code != Gio.IOErrorEnum.CANCELLED: print(f"Save As error: {e.message}"); self.show_error_dialog("Error Saving", f"Could not save file:\n{e.message}")
             if post_save_callback: GLib.idle_add(post_save_callback, False)

    def save_content_to_file(self, file, post_save_callback=None):
        safe_callback = post_save_callback if callable(post_save_callback) else None
        self.webview.evaluate_javascript("document.documentElement.outerHTML;", -1, None, None, None, self.get_html_for_save_callback, (file, safe_callback))

    def get_html_for_save_callback(self, webview, result, user_data):
        file, post_save_callback = user_data
        try:
            js_value = webview.evaluate_javascript_finish(result); html_content = js_value.to_string()
            if not html_content: raise ValueError("Empty HTML.")
            # CORRECTED: Use \\\\s for regex in Python f-string
            html_content = re.sub(r'<p class="placeholder">\\s*(?: |\u200B)?\\s*</p>', '', html_content, flags=re.IGNORECASE)
            content_bytes = GLib.Bytes.new(html_content.encode('utf-8'))
            file.replace_contents_bytes_async(content_bytes, None, False, Gio.FileCreateFlags.REPLACE_DESTINATION, None, self.final_save_callback, (file, post_save_callback))
        except (GLib.Error, ValueError, Exception) as e: print(f"Error get/prep HTML: {e}"); self.show_error_dialog("Error Saving", f"Could not retrieve/prep content:\n{e}"); GLib.idle_add(post_save_callback or (lambda s: None), False)

    def final_save_callback(self, file_obj, result, user_data):
        saved_file, post_save_callback = user_data; success = False
        try:
            success = file_obj.replace_contents_finish(result)
            if success: self.current_file = saved_file; self.is_new = False; self.is_modified = False; self.update_title()
            else: raise GLib.Error("Failed replace_contents.")
        except GLib.Error as e: print(f"Final save error: {e.message}"); self.show_error_dialog("Error Saving", f"Could not write file:\n{e.message}"); success = False
        except Exception as e: print(f"Unexpected save error: {e}"); self.show_error_dialog("Error Saving", f"Unexpected error:\n{e}"); success = False
        finally:
             if post_save_callback: GLib.idle_add(post_save_callback, success)

    def on_close_request(self, *args):
        if self.is_modified:
            def post_confirm_action(response_id):
                 if response_id in ["save", "discard"]:
                      self.destroy(); self.get_application().quit()
            self.show_save_confirmation_dialog(post_confirm_action)
            return True
        else:
             self.destroy(); self.get_application().quit()
             return False

    def show_error_dialog(self, title, message):
        dialog = Adw.MessageDialog(transient_for=self, modal=True, heading=title, body=message, destroy_with_parent=True)
        dialog.add_response("ok", "OK"); dialog.set_default_response("ok")
        dialog.connect("response", lambda d, r: d.destroy()); dialog.present()

    def clear_ignore_changes(self):
        self.ignore_changes = False
        GLib.idle_add(self.update_formatting_ui_from_current_state)
        return False

    def update_formatting_ui_from_current_state(self):
         # CORRECTED: Escaped all JS {} as {{}} and `${VAR}` as `${{VAR}}`
         self.webview.evaluate_javascript(
              """
              (function() {{ // Escaped {{}}
                   const sel = window.getSelection(); let state = null;
                   if (sel.rangeCount > 0) {{ // Escaped {{}}
                        const range = sel.getRangeAt(0); let element = range.startContainer;
                        if (element.nodeType === Node.TEXT_NODE) element = element.parentElement;
                        while (element && element !== document.body && element.nodeType === Node.ELEMENT_NODE && window.getComputedStyle(element).display !== 'block' && !element.classList?.contains('page')) {{ element = element.parentElement; }} // Escaped {{}}
                        if (!element || element === document.body || element.nodeType !== Node.ELEMENT_NODE) {{ let tempNode = range.startContainer; while(tempNode && !tempNode.classList?.contains('page')) {{ tempNode = tempNode.parentElement; }} element = tempNode || document.body.querySelector('.page'); }} // Escaped {{}}
                        if (element && element.classList?.contains('page')) {{ try {{ let focusParent = sel.focusNode?.parentElement; if (focusParent && focusParent !== document.body && window.getComputedStyle(focusParent).display === 'block') {{ element = focusParent; }} }} catch(e) {{}} }} // Escaped {{}}

                        if (element && element !== document.body) {{ // Escaped {{}}
                             try {{ // Escaped {{}}
                                  const style = window.getComputedStyle(element);
                                  let blockFmt = 'p'; try {{ blockFmt = document.queryCommandValue('formatBlock').toLowerCase() || 'p'; }} catch(e){{}} // Escaped {{}}
                                  if (blockFmt === 'div' || blockFmt === 'blockquote') blockFmt = 'p';
                                  // Using individual assignments to avoid potential large literal issues
                                  let tempState = {{}}; // Escaped {{}}
                                  tempState.bold = document.queryCommandState('bold');
                                  tempState.italic = document.queryCommandState('italic');
                                  tempState.underline = document.queryCommandState('underline');
                                  tempState.strikethrough = document.queryCommandState('strikeThrough');
                                  tempState.formatBlock = blockFmt;
                                  tempState.fontName = style.fontFamily.split(',')[0].replace(/['"]/g, '').trim();
                                  tempState.fontSize = style.fontSize;
                                  tempState.insertUnorderedList = document.queryCommandState('insertUnorderedList');
                                  tempState.insertOrderedList = document.queryCommandState('insertOrderedList');
                                  tempState.justifyLeft = document.queryCommandState('justifyLeft');
                                  tempState.justifyCenter = document.queryCommandState('justifyCenter');
                                  tempState.justifyRight = document.queryCommandState('justifyRight');
                                  tempState.justifyFull = document.queryCommandState('justifyFull');
                                  state = tempState; // Assign the completed object

                             }} catch(e) {{ // Escaped {{}} for catch block
                                 console.error("Error getting style/state in update request:", e);
                                 state = null;
                             }} // Escaped }}
                        }} // Escaped }}
                   }} // Escaped }}
                   if (!state) {{ // Default state
                        const pageElement = document.querySelector('.page'); const style = pageElement ? window.getComputedStyle(pageElement) : null; state = {{ bold: false, italic: false, underline: false, strikethrough: false, formatBlock: 'p', fontName: style ? style.fontFamily.split(',')[0].replace(/['"]/g, '').trim() : 'Sans', fontSize: style ? style.fontSize : '16px', insertUnorderedList: false, insertOrderedList: false, justifyLeft: true, justifyCenter: false, justifyRight: false, justifyFull: false }}; }} // Escaped {{}}
                   return JSON.stringify(state);
              }})(); // Escaped }}
              """, -1, None, None, None, self.process_current_state_update, None)

    def process_current_state_update(self, webview, result, user_data):
         try:
              js_value = webview.evaluate_javascript_finish(result); state_str = js_value.to_string()
              state = json.loads(state_str); self.update_formatting_ui(state)
         except (GLib.Error, json.JSONDecodeError, Exception) as e: print(f"Error processing UI update: {e}"); self.update_formatting_ui(None)

    def reset_formatting_state(self):
         self.is_bold=False; self.is_italic=False; self.is_underline=False; self.is_strikethrough=False; self.is_bullet_list=False; self.is_number_list=False; self.is_align_left=True; self.is_align_center=False; self.is_align_right=False; self.is_align_justify=False; self.current_font="Sans"; self.current_font_size="12"
         font_store = self.font_dropdown.get_model(); default_font_index=0;
         if font_store: names=[font_store.get_string(i).lower() for i in range(font_store.get_n_items())]; default_font_index=(names.index('sans') if 'sans' in names else 0)
         default_size_index = (self.size_range.index('12') if '12' in self.size_range else 5)
         self.heading_dropdown.handler_block(self.heading_dropdown_handler); self.heading_dropdown.set_selected(0); self.heading_dropdown.handler_unblock(self.heading_dropdown_handler)
         self.font_dropdown.handler_block(self.font_dropdown_handler); self.font_dropdown.set_selected(default_font_index); self.font_dropdown.handler_unblock(self.font_dropdown_handler)
         self.size_dropdown.handler_block(self.size_dropdown_handler); self.size_dropdown.set_selected(default_size_index); self.size_dropdown.handler_unblock(self.size_dropdown_handler)

    # --- Edit Operations ---
    def on_cut_clicked(self, btn): self.exec_js("document.execCommand('cut')")
    def on_copy_clicked(self, btn): self.exec_js("document.execCommand('copy')")
    def on_paste_clicked(self, btn): self.exec_js("document.execCommand('paste')")
    def on_undo_clicked(self, btn): self.exec_js("document.execCommand('undo')") # JS handler should trigger pagination check
    def on_redo_clicked(self, btn): self.exec_js("document.execCommand('redo')") # JS handler should trigger pagination check

    # --- Keyboard Shortcuts ---
    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0; shift = (state & Gdk.ModifierType.SHIFT_MASK) != 0; alt = (state & Gdk.ModifierType.ALT_MASK) != 0
        consumed = False
        # Let browser/JS handle editing/navigation keys
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_Delete, Gdk.KEY_BackSpace, Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Page_Up, Gdk.KEY_Page_Down, Gdk.KEY_Home, Gdk.KEY_End): return False
        if ctrl and keyval in (Gdk.KEY_x, Gdk.KEY_c, Gdk.KEY_v, Gdk.KEY_a): return False

        if ctrl and not shift and not alt:
            if keyval == Gdk.KEY_b: consumed = self.trigger_button(self.bold_btn)
            elif keyval == Gdk.KEY_i: consumed = self.trigger_button(self.italic_btn)
            elif keyval == Gdk.KEY_u: consumed = self.trigger_button(self.underline_btn)
            elif keyval == Gdk.KEY_s: self.on_save_clicked(None); consumed = True
            elif keyval == Gdk.KEY_o: self.on_open_clicked(None); consumed = True
            elif keyval == Gdk.KEY_n: self.on_new_clicked(None); consumed = True
            elif keyval == Gdk.KEY_w: self.close_request(); consumed = True
            elif keyval == Gdk.KEY_z: self.on_undo_clicked(None); consumed = True
            elif keyval == Gdk.KEY_y: self.on_redo_clicked(None); consumed = True
            elif keyval == Gdk.KEY_l: consumed = self.trigger_button(self.align_left_btn)
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
            elif keyval == Gdk.KEY_7: consumed = self.trigger_button(self.number_btn)
        return consumed

    def trigger_button(self, button):
        if isinstance(button, Gtk.ToggleButton): button.set_active(not button.get_active())
        elif isinstance(button, Gtk.Button): button.clicked()
        return True

    def set_dropdown_index(self, dropdown, index):
         model = dropdown.get_model()
         if model and 0 <= index < model.get_n_items(): dropdown.set_selected(index); return True
         return False

# --- Main Execution ---
if __name__ == "__main__":
    app = Writer()
    app.run(sys.argv)
