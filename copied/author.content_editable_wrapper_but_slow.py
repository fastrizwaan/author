#!/usr/bin/env python3

import gi, json
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Adw, WebKit, Gio, GLib, Pango, PangoCairo, Gdk

class Author(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.fastrizwaan.author")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = EditorWindow(application=self)
        win.present()

class EditorWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Author")
        self.set_default_size(1000, 700)
        self.add_css_styles()

        # CSS Provider
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(b"""
            .toolbar-container {
                padding: 6px 6px;
                background-color: rgba(127, 127, 127, 0.05);
            }
            .flat {
                background: none;
            }
            .flat:hover {
                background: rgba(127, 127, 127, 0.25);
            }
            .flat:checked {
                background: rgba(127, 127, 127, 0.25);
            }
            colorbutton.flat, 
            colorbutton.flat button {
                background: none;
            }
            colorbutton.flat:hover, 
            colorbutton.flat button:hover {
                background: rgba(127, 127, 127, 0.25);
            }
            dropdown.flat,
            dropdown.flat button {
                background: none;
                border-radius: 5px;
            }
            dropdown.flat:hover {
                background: rgba(127, 127, 127, 0.25);
            }
            .flat-header {
                background: rgba(127, 127, 127, 0.05);
                border: none;
                box-shadow: none;
                padding: 0px;
            }
            .button-box button {
                min-width: 80px;
                min-height: 36px;
            }
            .highlighted {
                background-color: rgba(127, 127, 127, 0.15);
            }
            .toolbar-group {
                margin: 0px 3px;
            }
            .toolbar-separator {
                min-height: 16px;
                min-width: 1px;
                background-color: alpha(currentColor, 0.15);
                margin: 10px 6px;
            }
            .color-indicator {
                min-height: 3px;
                min-width: 16px;
                margin-top: 1px;
                margin-bottom: 0px;
                border-radius: 2px;
            }
            .color-box {
                padding: 0px;
            }
        """)

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.connect("close-request", self.on_close_request)
        self.initial_html = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: sans-serif; font-size: 11pt; margin: 20px; line-height: 1.5; }
        @media (prefers-color-scheme: dark) { body { background-color: #121212; color: #e0e0e0; } }
        @media (prefers-color-scheme: light) { body { background-color: #ffffff; color: #000000; } }
        img { max-width: 100%; resize: both; }
        .content {
            min-height: calc(1056px - 192px); /* Page height - 2*96px padding */
            outline: none;
        }
    </style>
</head>
<body>
    <div class="page">
        <div class="content" contenteditable="true">
            <p><br></p>
        </div>
    </div>
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

        color_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        color_group.add_css_class("toolbar-group")

        # Higher-level toolbar groups
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
        formatting_toolbar_group.append(color_group)

        toolbars_flowbox = Gtk.FlowBox()
        toolbars_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        toolbars_flowbox.set_max_children_per_line(100)
        toolbars_flowbox.add_css_class("toolbar-container")

        toolbars_flowbox.insert(file_toolbar_group, -1)
        toolbars_flowbox.insert(formatting_toolbar_group, -1)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.webview = WebKit.WebView(editable=True)
        self.webview.connect('load-changed', self.on_webview_load)
        scroll.set_child(self.webview)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox)
        content_box.append(scroll)
        toolbar_view.set_content(content_box)

        self.webview.load_html(self.initial_html, "file:///")

        # Populate file group
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

        # Populate edit group
        for icon, handler in [
            ("edit-cut", self.on_cut_clicked),
            ("edit-copy", self.on_copy_clicked),
            ("edit-paste", self.on_paste_clicked),
            ("edit-undo", self.on_undo_clicked),
            ("edit-redo", self.on_redo_clicked),
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.add_css_class("flat")
            btn.connect("clicked", handler)
            edit_group.append(btn)

        # Populate view group
        for icon, handler in [
            ("edit-find", self.on_find_clicked),
            ("edit-find-replace", self.on_replace_clicked)
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.add_css_class("flat")
            btn.connect("clicked", handler)
            view_group.append(btn)

        zoom_store = Gtk.StringList()
        for level in ["10%", "25%", "50%", "75%", "100%", "150%", "200%", "400%", "1000%"]:
            zoom_store.append(level)
        zoom_dropdown = Gtk.DropDown(model=zoom_store)
        zoom_dropdown.set_selected(4)
        zoom_dropdown.connect("notify::selected", self.on_zoom_changed)
        zoom_dropdown.add_css_class("flat")
        view_group.append(zoom_dropdown)

        self.dark_mode_btn = Gtk.ToggleButton(icon_name="display-brightness")
        self.dark_mode_btn.connect("toggled", self.on_dark_mode_toggled)
        self.dark_mode_btn.add_css_class("flat")
        view_group.append(self.dark_mode_btn)

        # Populate text style group
        heading_store = Gtk.StringList()
        for h in ["Normal", "H1", "H2", "H3", "H4", "H5", "H6"]:
            heading_store.append(h)
        heading_dropdown = Gtk.DropDown(model=heading_store)
        heading_dropdown.connect("notify::selected", self.on_heading_changed)
        heading_dropdown.add_css_class("flat")
        text_style_group.append(heading_dropdown)

        font_map = PangoCairo.FontMap.get_default()
        families = font_map.list_families()
        font_names = sorted([family.get_name() for family in families])
        font_store = Gtk.StringList()
        for name in font_names:
            font_store.append(name)
        self.font_dropdown = Gtk.DropDown(model=font_store)
        default_index = font_names.index("Sans") if "Sans" in font_names else 0
        self.font_dropdown.set_selected(default_index)
        self.font_dropdown.connect("notify::selected", self.on_font_family_changed)
        self.font_dropdown.add_css_class("flat")
        text_style_group.append(self.font_dropdown)

        size_store = Gtk.StringList()
        for size in ["8", "10", "11", "12", "14", "16", "18", "24", "36", "48"]:
            size_store.append(size)
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(2)
        self.size_dropdown.connect("notify::selected", self.on_font_size_changed)
        self.size_dropdown.add_css_class("flat")
        text_style_group.append(self.size_dropdown)

        # Populate text format group
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

        # Populate align group
        align_buttons = [
            ("format-justify-left", self.on_align_left),
            ("format-justify-center", self.on_align_center),
            ("format-justify-right", self.on_align_right),
            ("format-justify-fill", self.on_align_justify)
        ]
        for icon, handler in align_buttons:
            btn = Gtk.Button(icon_name=icon)
            btn.add_css_class("flat")
            btn.connect("clicked", handler)
            align_group.append(btn)

        # Populate list group
        self.bullet_btn = Gtk.ToggleButton(icon_name="view-list-bullet")
        self.bullet_btn.connect("toggled", self.on_bullet_list_toggled)
        self.bullet_btn.add_css_class("flat")
        list_group.append(self.bullet_btn)

        self.number_btn = Gtk.ToggleButton(icon_name="view-list-ordered")
        self.number_btn.connect("toggled", self.on_number_list_toggled)
        self.number_btn.add_css_class("flat")
        list_group.append(self.number_btn)

        for icon, handler in [
            ("format-indent-more", self.on_indent_more),
            ("format-indent-less", self.on_indent_less)
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.connect("clicked", handler)
            btn.add_css_class("flat")
            list_group.append(btn)

        # Populate color group
        text_color_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_color_box.set_valign(Gtk.Align.CENTER)
        text_color_box.add_css_class("color-box")
        text_color_icon = Gtk.Image.new_from_icon_name("format-text-rich-symbolic")
        text_color_icon.set_pixel_size(12)
        self.text_color_indicator = Gtk.DrawingArea()
        self.text_color_indicator.set_size_request(16, 3)
        self.text_color_indicator.add_css_class("color-indicator")
        self.text_color_indicator.set_draw_func(self.draw_color_indicator, None)
        text_color_box.append(text_color_icon)
        text_color_box.append(self.text_color_indicator)
        text_color_btn = Gtk.Button(child=text_color_box)
        text_color_btn.add_css_class("flat")
        text_color_btn.connect("clicked", self.on_text_color_clicked)
        color_group.append(text_color_btn)

        bg_color_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        bg_color_box.set_valign(Gtk.Align.CENTER)
        bg_color_box.add_css_class("color-box")
        bg_color_icon = Gtk.Image.new_from_icon_name("applications-graphics-symbolic")
        bg_color_icon.set_pixel_size(12)
        self.bg_color_indicator = Gtk.DrawingArea()
        self.bg_color_indicator.set_size_request(16, 3)
        self.bg_color_indicator.add_css_class("color-indicator")
        self.bg_color_indicator.set_draw_func(self.draw_color_indicator, None)
        bg_color_box.append(bg_color_icon)
        bg_color_box.append(self.bg_color_indicator)
        bg_color_btn = Gtk.Button(child=bg_color_box)
        bg_color_btn.add_css_class("flat")
        bg_color_btn.connect("clicked", self.on_bg_color_clicked)
        color_group.append(bg_color_btn)

        # Initialize colors
        self.current_text_color = Gdk.RGBA()
        self.current_bg_color = Gdk.RGBA()

        # Add key event controller to WebView instead of window
        key_controller = Gtk.EventControllerKey.new()
        self.webview.add_controller(key_controller)
        key_controller.connect("key-pressed", self.on_key_pressed)

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events for shortcuts."""
        print(f"Key pressed: keyval={keyval}, keycode={keycode}, state={state}")  # Debug output
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        shift = (state & Gdk.ModifierType.SHIFT_MASK) != 0

        if ctrl and not shift:
            if keyval == Gdk.KEY_n:
                print("CTRL+N pressed")
                self.on_new_clicked(None)
                return True
            elif keyval == Gdk.KEY_o:
                print("CTRL+O pressed")
                self.on_open_clicked(None)
                return True
            elif keyval == Gdk.KEY_s:
                print("CTRL+S pressed")
                self.on_save_clicked(None)
                return True
            elif keyval == Gdk.KEY_p:
                print("CTRL+P pressed")
                self.on_print_clicked(None)
                return True
            elif keyval == Gdk.KEY_x:
                print("CTRL+X pressed")
                self.exec_js("""
                    (function() {
                        let sel = window.getSelection();
                        if (sel.rangeCount) {
                            let range = sel.getRangeAt(0);
                            let span = document.createElement('span');
                            span.style.backgroundColor = 'yellow';
                            range.surroundContents(span);
                            document.execCommand('cut');
                            setTimeout(() => { if (span.parentNode) span.outerHTML = span.innerHTML; }, 1000);
                        }
                    })();
                """)
                return True
            elif keyval == Gdk.KEY_c:
                print("CTRL+C pressed")
                self.on_copy_clicked(None)
                return True
            elif keyval == Gdk.KEY_v:
                print("CTRL+V pressed")
                self.on_paste_clicked(None)
                return True
            elif keyval == Gdk.KEY_z:
                print("CTRL+Z pressed")
                self.on_undo_clicked(None)
                return True
            elif keyval == Gdk.KEY_y:
                print("CTRL+Y pressed")
                self.on_redo_clicked(None)
                return True
            elif keyval == Gdk.KEY_f:
                print("CTRL+F pressed")
                self.on_find_clicked(None)
                return True
            elif keyval == Gdk.KEY_h:
                print("CTRL+H pressed")
                self.on_replace_clicked(None)
                return True
            elif keyval == Gdk.KEY_l:
                print("CTRL+L pressed")
                self.on_align_left(None)
                return True
            elif keyval == Gdk.KEY_e:
                print("CTRL+E pressed")
                self.on_align_center(None)
                return True
            elif keyval == Gdk.KEY_r:
                print("CTRL+R pressed")
                self.on_align_right(None)
                return True
            elif keyval == Gdk.KEY_j:
                print("CTRL+J pressed")
                self.on_align_justify(None)
                return True
            elif keyval in (Gdk.KEY_0, Gdk.KEY_1, Gdk.KEY_2, Gdk.KEY_3, 
                          Gdk.KEY_4, Gdk.KEY_5, Gdk.KEY_6):
                heading_index = keyval - Gdk.KEY_0
                print(f"CTRL+{heading_index} pressed")
                self.exec_js(f"document.execCommand('formatBlock', false, '{['div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'][heading_index]}')")
                return True

        elif ctrl and shift:
            if keyval == Gdk.KEY_s:
                print("CTRL+SHIFT+S pressed")
                self.on_save_as_clicked(None)
                return True
            elif keyval == Gdk.KEY_z:
                print("CTRL+SHIFT+Z pressed")
                self.on_redo_clicked(None)
                return True

        elif not ctrl:
            if keyval == Gdk.KEY_F12 and not shift:
                print("F12 pressed")
                self.on_number_list_toggled(self.number_btn)
                return True
            elif keyval == Gdk.KEY_F12 and shift:
                print("SHIFT+F12 pressed")
                self.on_bullet_list_toggled(self.bullet_btn)
                return True

        return False

    def draw_color_indicator(self, area, cr, width, height, data):
        if area == self.text_color_indicator:
            color = self.current_text_color
        elif area == self.bg_color_indicator:
            color = self.current_bg_color
        else:
            return
        cr.set_source_rgb(color.red, color.green, color.blue)
        cr.rectangle(0, 0, width, height)
        cr.fill()

    def on_text_color_clicked(self, btn):
        color_dialog = Gtk.ColorDialog()
        color_dialog.set_title("Choose Text Color")
        color_dialog.set_with_alpha(False)
        color_dialog.choose_rgba(self, self.current_text_color, None, self.on_text_color_dialog_response, btn)

    def on_text_color_dialog_response(self, dialog, result, btn):
        try:
            rgba = dialog.choose_rgba_finish(result)
            if rgba:
                self.current_text_color = rgba
                self.text_color_indicator.queue_draw()
                color = rgba.to_string()
                self.exec_js(f"document.execCommand('foreColor', false, '{color}')")
        except GLib.Error as e:
            print("Text color selection error:", e.message)

    def on_bg_color_clicked(self, btn):
        color_dialog = Gtk.ColorDialog()
        color_dialog.set_title("Choose Background Color")
        color_dialog.set_with_alpha(False)
        color_dialog.choose_rgba(self, self.current_bg_color, None, self.on_bg_color_dialog_response, btn)

    def on_bg_color_dialog_response(self, dialog, result, btn):
        try:
            rgba = dialog.choose_rgba_finish(result)
            if rgba:
                self.current_bg_color = rgba
                self.bg_color_indicator.queue_draw()
                color = rgba.to_string()
                self.exec_js(f"document.execCommand('backColor', false, '{color}')")
        except GLib.Error as e:
            print("Background color selection error:", e.message)

    def on_dark_mode_toggled(self, btn):
        if btn.get_active():
            btn.set_icon_name("weather-clear-night")
            script = """
                (function() {
                    let style = document.createElement('style');
                    style.id = 'dynamic-theme-style';
                    style.textContent = `
                        @media screen {
                            body { 
                                background-color: #242424 !important; 
                                color: #e0e0e0 !important; 
                            }
                        }
                    `;
                    document.head.appendChild(style);
                })();
            """
        else:
            btn.set_icon_name("display-brightness")
            script = """
                (function() {
                    let styleId = 'dynamic-theme-style';
                    let existingStyle = document.getElementById(styleId);
                    if (existingStyle) {
                        existingStyle.remove();
                    }
                })();
            """
        self.exec_js(script)

    def on_webview_load(self, webview, load_event):
        if load_event == WebKit.LoadEvent.FINISHED:
            script = """
                let p = document.querySelector('p');
                if (p) {
                    let range = document.createRange();
                    range.setStart(p, 0);
                    range.setEnd(p, 0);
                    let sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                }
            """
            self.webview.evaluate_javascript(script, -1, None, None, None, None, None)
            GLib.idle_add(self.webview.grab_focus)
            if self.dark_mode_btn.get_active():
                dark_mode_script = """
                    (function() {
                        let styleId = 'dynamic-theme-style';
                        let existingStyle = document.getElementById(styleId);
                        if (!existingStyle) {
                            let style = document.createElement('style');
                            style.id = styleId;
                            style.textContent = `
                                @media (prefers-color-scheme: dark) { 
                                    body { background-color: #242424 !important; color: #e0e0e0 !important; } 
                                }
                                @media (prefers-color-scheme: light) { 
                                    body { background-color: #ffffff !important; color: #000000 !important; } 
                                }
                            `;
                            document.head.appendChild(style);
                        }
                    })();
                """
                self.exec_js(dark_mode_script)

    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)
        self.webview.grab_focus()

    def on_new_clicked(self, btn): 
        self.webview.load_html(self.initial_html, "file:///")
    
    def on_open_clicked(self, btn): 
        self.open_file_dialog()
    
    def on_save_clicked(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Save HTML File")
        dialog.set_initial_name("document.html")
        filter_html = Gtk.FileFilter()
        filter_html.set_name("HTML Files (*.html)")
        filter_html.add_pattern("*.html")
        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        filter_store.append(filter_html)
        dialog.set_filters(filter_store)
        dialog.save(self, None, self.save_callback)
    
    def on_save_as_clicked(self, btn): 
        self.on_save_clicked(btn)
    
    def on_print_clicked(self, btn):
        print_operation = WebKit.PrintOperation.new(self.webview)
        print_operation.run_dialog(self)
    
    def on_cut_clicked(self, btn): 
        self.exec_js("""
            (function() {
                let sel = window.getSelection();
                if (sel.rangeCount) {
                    let range = sel.getRangeAt(0);
                    let span = document.createElement('span');
                    span.style.backgroundColor = 'yellow';
                    range.surroundContents(span);
                    document.execCommand('cut');
                    setTimeout(() => { if (span.parentNode) span.outerHTML = span.innerHTML; }, 1000);
                }
            })();
        """)
    
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
    
    def on_find_clicked(self, btn):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Find",
            body="Enter search term",
            close_response="cancel",
            modal=True
        )
        entry = Gtk.Entry()
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("find", "Find")
        dialog.set_response_appearance("find", Adw.ResponseAppearance.SUGGESTED)
        
        def on_response(dialog, response):
            if response == "find":
                search_term = entry.get_text()
                if search_term:
                    script = f"""
                        (function() {{
                            console.log('Find script running with term: ' + {json.dumps(search_term)});
                            const highlights = document.querySelectorAll('span.author-highlight');
                            highlights.forEach(span => {{
                                const parent = span.parentNode;
                                while (span.firstChild) {{
                                    parent.insertBefore(span.firstChild, span);
                                }}
                                parent.removeChild(span);
                                parent.normalize();
                            }});
                            const walker = document.createTreeWalker(
                                document.body,
                                NodeFilter.SHOW_TEXT,
                                {{ acceptNode: node => 
                                    (node.parentNode.tagName !== 'SCRIPT' && 
                                     node.parentNode.tagName !== 'STYLE' && 
                                     node.nodeValue.trim()) 
                                    ? NodeFilter.FILTER_ACCEPT 
                                    : NodeFilter.FILTER_REJECT 
                                }}
                            );
                            const textNodes = [];
                            let node;
                            while ((node = walker.nextNode())) {{
                                textNodes.push(node);
                            }}
                            const regex = new RegExp({json.dumps(search_term)}, 'gi');
                            textNodes.forEach(node => {{
                                const text = node.nodeValue;
                                const matches = [...text.matchAll(regex)];
                                if (matches.length === 0) return;
                                const fragment = document.createDocumentFragment();
                                let lastIndex = 0;
                                matches.forEach(match => {{
                                    const start = match.index;
                                    const matchText = match[0];
                                    if (start > lastIndex) {{
                                        fragment.appendChild(document.createTextNode(
                                            text.slice(lastIndex, start)
                                        ));
                                    }}
                                    const span = document.createElement('span');
                                    span.className = 'author-highlight';
                                    span.style.backgroundColor = 'yellow';
                                    span.textContent = matchText;
                                    fragment.appendChild(span);
                                    lastIndex = start + matchText.length;
                                }});
                                if (lastIndex < text.length) {{
                                    fragment.appendChild(document.createTextNode(
                                        text.slice(lastIndex)
                                    ));
                                }}
                                node.parentNode.replaceChild(fragment, node);
                            }});
                            console.log('Find script completed');
                        }})();
                    """
                    print(f"Executing find script for term: '{search_term}'")
                    self.exec_js(script)
            dialog.destroy()
        
        dialog.connect("response", on_response)
        dialog.present()
    
    def on_replace_clicked(self, btn):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Replace",
            body="Enter search and replacement terms",
            close_response="cancel",
            modal=True
        )
        search_entry = Gtk.Entry(placeholder_text="Search term")
        replace_entry = Gtk.Entry(placeholder_text="Replace with")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.append(search_entry)
        content.append(replace_entry)
        dialog.set_extra_child(content)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("replace", "Replace All")
        dialog.set_response_appearance("replace", Adw.ResponseAppearance.SUGGESTED)
        
        def on_response(dialog, response):
            if response == "replace":
                search = search_entry.get_text()
                replacement = replace_entry.get_text()
                if search and replacement:
                    script = f"""
                        (function() {{
                            let search = {json.dumps(search)};
                            let replace = {json.dumps(replacement)};
                            let regex = new RegExp(search, 'gi');
                            document.body.innerHTML = document.body.innerHTML.replace(regex, replace);
                        }})();
                    """
                    self.exec_js(script)
            dialog.destroy()
        
        dialog.connect("response", on_response)
        dialog.present()
    
    def on_zoom_changed(self, dropdown, *args):
        selected_item = dropdown.get_selected_item()
        if selected_item:
            try:
                zoom_level = int(selected_item.get_string().rstrip('%')) / 100.0
                self.webview.set_zoom_level(zoom_level)
            except ValueError:
                pass
    
    def on_bold_toggled(self, btn):
        self.exec_js("document.execCommand('bold')")
        self.webview.grab_focus()

    def on_italic_toggled(self, btn):
        self.exec_js("document.execCommand('italic')")
        self.webview.grab_focus()

    def on_underline_toggled(self, btn):
        self.exec_js("document.execCommand('underline')")
        self.webview.grab_focus()

    def on_strikethrough_toggled(self, btn):
        self.exec_js("document.execCommand('strikethrough')")
        self.webview.grab_focus()

    def on_bullet_list_toggled(self, btn):
        if btn.get_active():
            if self.number_btn.get_active():
                self.exec_js("document.execCommand('insertOrderedList')")
                self.number_btn.set_active(False)
            self.exec_js("document.execCommand('insertUnorderedList')")
        else:
            self.exec_js("document.execCommand('insertUnorderedList')")
        self.webview.grab_focus()

    def on_number_list_toggled(self, btn):
        if btn.get_active():
            if self.bullet_btn.get_active():
                self.exec_js("document.execCommand('insertUnorderedList')")
                self.bullet_btn.set_active(False)
            self.exec_js("document.execCommand('insertOrderedList')")
        else:
            self.exec_js("document.execCommand('insertOrderedList')")
        self.webview.grab_focus()

    def on_heading_changed(self, dropdown, *args):
        headings = ["div", "h1", "h2", "h3", "h4", "h5", "h6"]
        selected = dropdown.get_selected()
        if 0 <= selected < len(headings):
            self.exec_js(f"document.execCommand('formatBlock', false, '{headings[selected]}')")
    
    def on_align_left(self, *args): 
        self.exec_js("document.execCommand('justifyLeft')")
    
    def on_align_center(self, *args): 
        self.exec_js("document.execCommand('justifyCenter')")
    
    def on_align_right(self, *args): 
        self.exec_js("document.execCommand('justifyRight')")
    
    def on_align_justify(self, *args): 
        self.exec_js("document.execCommand('justifyFull')")
    
    def on_indent_more(self, *args): 
        self.exec_js("document.execCommand('indent')")
    
    def on_indent_less(self, *args): 
        self.exec_js("document.execCommand('outdent')")
    
    def on_font_family_changed(self, dropdown, *args):
        if item := dropdown.get_selected_item():
            font_family = item.get_string()
            script = """
                (function() {
                    let selection = window.getSelection();
                    if (!selection.rangeCount) return;
                    let range = selection.getRangeAt(0);
                    let ancestor = range.commonAncestorContainer;
                    let spans = (ancestor.nodeType === 1) 
                        ? ancestor.querySelectorAll('span[style*="font-family"]') 
                        : ancestor.parentElement.querySelectorAll('span[style*="font-family"]');
                    if (spans.length > 0 && range.toString().length > 0) {
                        let updated = false;
                        spans.forEach(span => {
                            if (range.intersectsNode(span)) {
                                span.style.fontFamily = '""" + font_family + """';
                                updated = true;
                            }
                        });
                        if (updated) {
                            let newRange = document.createRange();
                            newRange.setStart(range.startContainer, range.startOffset);
                            newRange.setEnd(range.endContainer, range.endOffset);
                            selection.removeAllRanges();
                            selection.addRange(newRange);
                            return;
                        }
                    }
                    let contents = range.extractContents();
                    if (!contents.hasChildNodes()) {
                        range.insertNode(contents);
                        return;
                    }
                    let span = document.createElement('span');
                    span.style.fontFamily = '""" + font_family + """';
                    span.appendChild(contents);
                    range.insertNode(span);
                    let newRange = document.createRange();
                    newRange.selectNodeContents(span);
                    selection.removeAllRanges();
                    selection.addRange(newRange);
                })();
            """
            self.exec_js(script)
    
    def on_font_size_changed(self, dropdown, *args):
        if item := dropdown.get_selected_item():
            size_pt = item.get_string()
            script = """
                (function() {
                    let selection = window.getSelection();
                    if (!selection.rangeCount) return;
                    let range = selection.getRangeAt(0);
                    let content = range.extractContents();
                    let span = document.createElement('span');
                    span.style.fontSize = '""" + size_pt + """pt';
                    let tempElement = document.createElement('div');
                    tempElement.appendChild(content);
                    let fontSizeSpans = tempElement.querySelectorAll('span[style*="font-size"]');
                    for (let oldSpan of fontSizeSpans) {
                        while (oldSpan.firstChild) {
                            oldSpan.parentNode.insertBefore(oldSpan.firstChild, oldSpan);
                        }
                        oldSpan.parentNode.removeChild(oldSpan);
                    }
                    while (tempElement.firstChild) {
                        span.appendChild(tempElement.firstChild);
                    }
                    range.insertNode(span);
                    selection.removeAllRanges();
                    let newRange = document.createRange();
                    newRange.selectNodeContents(span);
                    selection.addRange(newRange);
                })();
            """
            self.exec_js(script)
    
    def open_file_dialog(self):
        file_dialog = Gtk.FileDialog.new()
        filter_model = Gio.ListStore.new(Gtk.FileFilter)
        filter_model.append(self.create_file_filter())
        file_dialog.set_filters(filter_model)
        file_dialog.open(self, None, self.on_open_file_dialog_response)
    
    def create_file_filter(self):
        file_filter = Gtk.FileFilter()
        file_filter.set_name("HTML Files (*.html, *.htm)")
        file_filter.add_pattern("*.html")
        file_filter.add_pattern("*.htm")
        return file_filter
    
    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                file.load_contents_async(None, self.load_callback)
        except GLib.Error as e:
            print("Open error:", e.message)
    
    def load_callback(self, file, result):
        try:
            ok, content, _ = file.load_contents_finish(result)
            if ok:
                self.webview.load_html(content.decode(), file.get_uri())
        except GLib.Error as e:
            print("Load error:", e.message)
    
    def save_callback(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            self.webview.evaluate_javascript("document.documentElement.outerHTML", -1, None, None, None, self.save_html_callback, file)
        except GLib.Error as e:
            print("Save error:", e.message)
    
    def save_html_callback(self, webview, result, file):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                html = js_value.to_string()
                file.replace_contents_bytes_async(GLib.Bytes.new(html.encode()), None, False, Gio.FileCreateFlags.REPLACE_DESTINATION, None, self.final_save_callback)
        except GLib.Error as e:
            print("HTML save error:", e.message)
    
    def final_save_callback(self, file, result):
        try:
            file.replace_contents_finish(result)
            print("File saved successfully to", file.get_path())
        except GLib.Error as e:
            print("Final save error:", e.message)
    
    def add_css_styles(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(b"window { background-color: @window_bg_color; }")
        Gtk.StyleContext.add_provider_for_display(self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    
    def on_close_request(self, *args):
        self.get_application().quit()
        return False

if __name__ == "__main__":
    app = Author()
    app.run()
