#!/usr/bin/env python3

import os
import gi
import json
import base64
import re
import shutil
import tempfile
from urllib.parse import urlparse
from datetime import datetime
import markdown

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
    document_counter = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Author")
        self.set_default_size(1000, 700)
        self.add_css_styles()

        # State tracking for formatting
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

        # Document state
        self.current_file = None
        self.is_new = True
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.webview = WebKit.WebView(editable=True)

        # Register content change handler
        user_content = self.webview.get_user_content_manager()
        user_content.register_script_message_handler('contentChanged')
        user_content.connect('script-message-received::contentChanged', self.on_content_changed_js)

        self.webview.connect('load-changed', self.on_webview_load)

        # CSS Provider
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(b"""
            .toolbar-container { padding: 6px 6px; background-color: rgba(127, 127, 127, 0.05); }
            .flat { background: none; }
            .flat:hover { background: rgba(127, 127, 127, 0.25); }
            .flat:checked { background: rgba(127, 127, 127, 0.25); }
            colorbutton.flat, colorbutton.flat button { background: none; }
            colorbutton.flat:hover, colorbutton.flat button:hover { background: rgba(127, 127, 127, 0.25); }
            dropdown.flat, dropdown.flat button { background: none; border-radius: 5px; }
            dropdown.flat:hover { background: rgba(127, 127, 127, 0.25); }
            .flat-header { background: rgba(127, 127, 127, 0.05); border: none; box-shadow: none; padding: 0px; }
            .button-box button { min-width: 80px; min-height: 36px; }
            .highlighted { background-color: rgba(127, 127, 127, 0.15); }
            .toolbar-group { margin: 0px 3px; }
            .toolbar-separator { min-height: 16px; min-width: 1px; background-color: alpha(currentColor, 0.15); margin: 10px 6px; }
            .color-indicator { min-height: 3px; min-width: 16px; margin-top: 1px; margin-bottom: 0px; border-radius: 2px; }
            .color-box { padding: 0px; }
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
        body { font-family: sans-serif; font-size: 12pt; margin: 20px; line-height: 1.5; }
        @media (prefers-color-scheme: dark) { body { background-color: #1e1e1e; color: #e0e0e0; } }
        @media (prefers-color-scheme: light) { body { background-color: #ffffff; color: #000000; } }
    </style>
    <meta charset="UTF-8">
    <title>Editor</title>
    <style>
        .content {
            min-height: 0px;
            padding: 0px;
            outline: none;
            box-sizing: border-box;
        }
    </style>
</head>
<body>
    <div class="content" contenteditable="true"><p>\u200B</p></div>

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

        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.connect("scroll", self.on_scroll)
        self.webview.add_controller(scroll_controller)
        scroll.set_child(self.webview)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(toolbars_flowbox)
        content_box.append(scroll)
        toolbar_view.set_content(content_box)

        self.webview.load_html(self.initial_html, "file:///")

        # Populate toolbar buttons
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

        for icon, handler in [
            ("edit-find", self.on_find_clicked),
            ("edit-find-replace", self.on_replace_clicked)
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.add_css_class("flat")
            btn.connect("clicked", handler)
            view_group.append(btn)

        zoom_store = Gtk.StringList()
        for level in ["50%", "60%", "70%", "80%", "90%", "100%", "110%", "120%", "130%", "140%", "150%", "160%", "170%", "180%", "190%", "200%", "210%", "220%", "230%", "240%", "250%", "260%", "270%", "280%", "290%", "300%", "320%", "340%", "360%", "380%", "400%", "425%", "450%", "475%", "500%", "600%", "700%", "800%", "900%", "1000%"]:
            zoom_store.append(level)
        zoom_dropdown = Gtk.DropDown(model=zoom_store)
        zoom_dropdown.set_selected(5)
        zoom_dropdown.connect("notify::selected", self.on_zoom_changed)
        zoom_dropdown.add_css_class("flat")
        view_group.append(zoom_dropdown)

        self.dark_mode_btn = Gtk.ToggleButton(icon_name="display-brightness")
        self.dark_mode_btn.connect("toggled", self.on_dark_mode_toggled)
        self.dark_mode_btn.add_css_class("flat")
        view_group.append(self.dark_mode_btn)

        heading_store = Gtk.StringList()
        for h in ["Normal", "H1", "H2", "H3", "H4", "H5", "H6"]:
            heading_store.append(h)
        self.heading_dropdown = Gtk.DropDown(model=heading_store)
        self.heading_dropdown.connect("notify::selected", self.on_heading_changed)
        self.heading_dropdown.add_css_class("flat")
        text_style_group.append(self.heading_dropdown)

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
        for size in ["6", "7", "8", "9", "10", "10.5", "11", "12", "13", "14", "15", "16", "18", "20", "21", "22", "24", "26", "28", "32", "36", "40", "42", "44", "48", "54", "60", "66", "72", "80", "88", "96"]:
            size_store.append(size)
        self.size_dropdown = Gtk.DropDown(model=size_store)
        self.size_dropdown.set_selected(6)
        self.size_dropdown.connect("notify::selected", self.on_font_size_changed)
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
            ("format-indent-more", self.on_indent_more),
            ("format-indent-less", self.on_indent_less)
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.connect("clicked", handler)
            btn.add_css_class("flat")
            list_group.append(btn)

        text_color_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_color_box.set_valign(Gtk.Align.CENTER)
        text_color_box.add_css_class("color-box")
        text_color_icon = Gtk.Image.new_from_icon_name("draw-text-symbolic")
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

        self.current_text_color = Gdk.RGBA()
        self.current_bg_color = Gdk.RGBA()

        key_controller = Gtk.EventControllerKey.new()
        self.webview.add_controller(key_controller)
        key_controller.connect("key-pressed", self.on_key_pressed)

        self.is_modified = False
        self.update_title()

    def on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        ctrl_pressed = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        if ctrl_pressed:
            if dy < 0:
                self.adjust_zoom_level(0.1)
            elif dy > 0:
                self.adjust_zoom_level(-0.1)
            return True
        return False

    def on_content_changed_js(self, manager, js_result):
        if getattr(self, 'ignore_changes', False):
            return
        try:
            if js_result and hasattr(js_result, 'get_js_value'):
                js_value = js_result.get_js_value()
                if js_value and js_value.is_string():
                    value = js_value.to_string()
                    if value == 'changed':
                        self.is_modified = True
                        self.update_title()
                    elif value == 'selection':
                        self.update_formatting_state()
                else:
                    self.is_modified = True
                    self.update_title()
        except Exception as e:
            print(f"Error in on_content_changed_js: {e}")
            self.is_modified = True
            self.update_title()

    def adjust_zoom_level(self, delta):
        current = self.webview.get_zoom_level()
        new_zoom = max(0.5, min(current + delta, 10.0))
        self.webview.set_zoom_level(new_zoom)

    def on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        shift = (state & Gdk.ModifierType.SHIFT_MASK) != 0

        if ctrl:
            if keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
                self.adjust_zoom_level(0.1)
                return True
            elif keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
                self.adjust_zoom_level(-0.1)
                return True

        if ctrl and not shift:
            if keyval == Gdk.KEY_b:
                self.is_bold = not self.is_bold
                self.apply_persistent_formatting('bold', self.is_bold)
                self.bold_btn.set_active(self.is_bold)
                self.webview.grab_focus()
                return True
            elif keyval == Gdk.KEY_i:
                self.is_italic = not self.is_italic
                self.apply_persistent_formatting('italic', self.is_italic)
                self.italic_btn.set_active(self.is_italic)
                self.webview.grab_focus()
                return True
            elif keyval == Gdk.KEY_u:
                self.is_underline = not self.is_underline
                self.apply_persistent_formatting('underline', self.is_underline)
                self.underline_btn.set_active(self.is_underline)
                self.webview.grab_focus()
                return True
            elif keyval == Gdk.KEY_s:
                self.on_save_clicked(None)
                return True
            elif keyval == Gdk.KEY_w:
                self.on_close_document_clicked(None)
                return True
            elif keyval == Gdk.KEY_n:
                self.on_new_clicked(None)
                return True
            elif keyval == Gdk.KEY_o:
                self.on_open_clicked(None)
                return True
            elif keyval == Gdk.KEY_p:
                self.on_print_clicked(None)
                return True
            elif keyval == Gdk.KEY_x:
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
            elif keyval == Gdk.KEY_f:
                self.on_find_clicked(None)
                return True
            elif keyval == Gdk.KEY_h:
                self.on_replace_clicked(None)
                return True
            elif keyval == Gdk.KEY_l:
                self.align_left_btn.set_active(not self.align_left_btn.get_active())
                self.on_align_left(self.align_left_btn)
                return True
            elif keyval == Gdk.KEY_e:
                self.align_center_btn.set_active(not self.align_center_btn.get_active())
                self.on_align_center(self.align_center_btn)
                return True
            elif keyval == Gdk.KEY_r:
                self.align_right_btn.set_active(not self.align_right_btn.get_active())
                self.on_align_right(self.align_right_btn)
                return True
            elif keyval == Gdk.KEY_j:
                self.align_justify_btn.set_active(not self.align_justify_btn.get_active())
                self.on_align_justify(self.align_justify_btn)
                return True

        elif ctrl and shift:
            if keyval == Gdk.KEY_S:
                self.on_save_as_clicked(None)
                return True
            elif keyval == Gdk.KEY_Z:
                self.on_redo_clicked(None)
                return True
            elif keyval == Gdk.KEY_X:
                self.is_strikethrough = not self.is_strikethrough
                self.apply_persistent_formatting('strikethrough', self.is_strikethrough)
                self.strikethrough_btn.set_active(self.is_strikethrough)
                self.webview.grab_focus()
                return True
            elif keyval == Gdk.KEY_L:
                self.is_bullet_list = not self.is_bullet_list
                self.apply_list_formatting('unordered', self.is_bullet_list)
                self.bullet_btn.set_active(self.is_bullet_list)
                self.webview.grab_focus()
                return True
            elif keyval == Gdk.KEY_asterisk:
                self.is_bullet_list = not self.is_bullet_list
                self.apply_list_formatting('unordered', self.is_bullet_list)
                self.bullet_btn.set_active(self.is_bullet_list)
                self.webview.grab_focus()
                return True
            elif keyval == Gdk.KEY_ampersand:
                self.is_number_list = not self.is_number_list
                self.apply_list_formatting('ordered', self.is_number_list)
                self.number_btn.set_active(self.is_number_list)
                self.webview.grab_focus()
                return True
        elif not ctrl:
            if keyval == Gdk.KEY_F12 and not shift:
                self.is_number_list = not self.is_number_list
                self.apply_list_formatting('ordered', self.is_number_list)
                self.number_btn.set_active(self.is_number_list)
                self.webview.grab_focus()
                return True
            elif keyval == Gdk.KEY_F12 and shift:
                self.is_bullet_list = not self.is_bullet_list
                self.apply_list_formatting('unordered', self.is_bullet_list)
                self.bullet_btn.set_active(self.is_bullet_list)
                self.webview.grab_focus()
                return True
        GLib.idle_add(self.update_formatting_state)
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
                self.update_formatting_state()
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
                self.update_formatting_state()
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
                            body { background-color: #242424 !important; color: #e0e0e0 !important; }
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
            cursor_script = """
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
            self.webview.evaluate_javascript(cursor_script, -1, None, None, None, None, None)
            GLib.idle_add(self.webview.grab_focus)

            change_detection_script = """
                (function() {
                    let lastContent = document.body.innerHTML;
                    function debounce(func, wait) {
                        let timeout;
                        return function executedFunction(...args) {
                            clearTimeout(timeout);
                            timeout = setTimeout(() => func(...args), wait);
                        };
                    }
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
                    document.addEventListener('selectionchange', () => {
                        window.webkit.messageHandlers.contentChanged.postMessage('selection');
                    });
                })();
            """
            self.webview.evaluate_javascript(change_detection_script, -1, None, None, None, None, None)

            if self.dark_mode_btn.get_active():
                dark_mode_script = """
                    (function() {
                        let styleId = 'dynamic-theme-style';
                        if (!document.getElementById(styleId)) {
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

            selection_script = """
                (function() {
                    document.addEventListener('selectionchange', () => {
                        window.webkit.messageHandlers.contentChanged.postMessage('selection');
                    });
                })();
            """
            self.webview.evaluate_javascript(selection_script, -1, None, None, None, None, None)

    def exec_js(self, script, callback=None):
        self.webview.evaluate_javascript(script, -1, None, None, None,
                                        callback or self.on_js_executed, None)

    def on_js_executed(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value and js_value.is_string():
                print(f"JS Result: {js_value.to_string()}")
        except Exception as e:
            print(f"JS Execution Error: {e}")
        self.webview.grab_focus()

    def on_open_clicked(self, btn):
        self.open_file_dialog()

    def update_title(self):
        modified_marker = "⃰" if self.is_modified else ""
        if self.current_file and not self.is_new:
            base_name = os.path.splitext(self.current_file.get_basename())[0]
            title = f"{modified_marker}{base_name} – Author"
        else:
            title = f"{modified_marker}Document {self.document_number} – Author"
        self.set_title(title)

    def on_save_clicked(self, btn):
        if self.current_file and not self.is_new:
            file_path = self.current_file.get_path()
            if file_path.endswith(".mhtml"):
                self.save_as_mhtml(self.current_file)
            elif file_path.endswith(".html") or file_path.endswith(".htm"):
                self.save_as_html(self.current_file)
            elif file_path.endswith(".txt"):
                self.save_as_txt(self.current_file)
            else:
                self.show_save_dialog()
        else:
            self.show_save_dialog()

    def on_new_clicked(self, btn):
        self.ignore_changes = True
        self.webview.load_html(self.initial_html, "file:///")
        self.current_file = None
        self.is_new = True
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()
        GLib.timeout_add(500, self.clear_ignore_changes)

    def on_save_as_clicked(self, btn):
        self.show_save_dialog(is_save_as=True)

    def show_save_dialog(self, is_save_as=False):
        dialog = Gtk.FileDialog()
        dialog.set_title("Save As" if is_save_as else "Save")
        if self.current_file and not self.is_new:
            dialog.set_initial_file(self.current_file)
        else:
            dialog.set_initial_name(self.generate_default_name())

        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        filter_mhtml = Gtk.FileFilter()
        filter_mhtml.set_name("MHTML Files (*.mhtml)")
        filter_mhtml.add_pattern("*.mhtml")
        filter_store.append(filter_mhtml)

        filter_html = Gtk.FileFilter()
        filter_html.set_name("HTML Files (*.html, *.htm)")
        filter_html.add_pattern("*.html")
        filter_html.add_pattern("*.htm")
        filter_store.append(filter_html)

        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("Text Files (*.txt)")
        filter_txt.add_pattern("*.txt")
        filter_store.append(filter_txt)

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Supported Files")
        filter_all.add_pattern("*.mhtml")
        filter_all.add_pattern("*.html")
        filter_all.add_pattern("*.htm")
        filter_all.add_pattern("*.txt")
        filter_store.append(filter_all)

        dialog.set_filters(filter_store)
        dialog.set_default_filter(filter_mhtml)
        dialog.save(self, None, self.save_callback)

    def generate_default_name(self):
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"Document {self.document_number} - {current_date}.mhtml"

    def save_callback(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                file_path = file.get_path()
                print(f"Original file path: {file_path}")

                if file_path.endswith(".mhtml"):
                    self.save_as_mhtml(file)
                elif file_path.endswith(".html") or file_path.endswith(".htm"):
                    self.save_as_html(file)
                elif file_path.endswith(".txt"):
                    self.save_as_txt(file)
                else:
                    new_path = file_path + ".mhtml"
                    file = Gio.File.new_for_path(new_path)
                    self.save_as_mhtml(file)

                self.current_file = file
                self.is_new = False
                self.update_title()

        except GLib.Error as e:
            print("Save error:", e.message)

    def save_as_mhtml(self, file):
        self.webview.save_to_file(file, WebKit.SaveMode.MHTML, None, self.final_save_callback, None)

    def save_as_html(self, file):
        self.webview.evaluate_javascript(
            "document.documentElement.outerHTML",
            -1,
            None,
            None,
            None,
            self.save_html_callback,
            file
        )

    def save_html_callback(self, webview, result, file):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                html = js_value.to_string()
                file.replace_contents_bytes_async(
                    GLib.Bytes.new(html.encode()),
                    None,
                    False,
                    Gio.FileCreateFlags.REPLACE_DESTINATION,
                    None,
                    self.final_save_callback
                )
        except GLib.Error as e:
            print("HTML save error:", e.message)

    def save_as_txt(self, file):
        self.webview.evaluate_javascript(
            "document.body.textContent",
            -1,
            None,
            None,
            None,
            self.save_txt_callback,
            file
        )

    def save_txt_callback(self, webview, result, file):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value:
                text = js_value.to_string()
                file.replace_contents_bytes_async(
                    GLib.Bytes.new(text.encode()),
                    None,
                    False,
                    Gio.FileCreateFlags.REPLACE_DESTINATION,
                    None,
                    self.final_save_callback
                )
        except GLib.Error as e:
            print("Text save error:", e.message)

    def final_save_callback(self, file, result):
        try:
            file.replace_contents_finish(result)
            self.is_modified = False
            self.update_title()
            print(f"File successfully saved to: {file.get_path()}")
        except GLib.Error as e:
            print("Final save error:", e.message)

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
        self.is_bold = btn.get_active()
        self.apply_persistent_formatting('bold', self.is_bold)
        self.webview.grab_focus()
        self.update_formatting_state()

    def on_italic_toggled(self, btn):
        self.is_italic = btn.get_active()
        self.apply_persistent_formatting('italic', self.is_italic)
        self.webview.grab_focus()
        self.update_formatting_state()

    def on_underline_toggled(self, btn):
        self.is_underline = btn.get_active()
        self.apply_persistent_formatting('underline', self.is_underline)
        self.webview.grab_focus()
        self.update_formatting_state()

    def on_strikethrough_toggled(self, btn):
        self.is_strikethrough = btn.get_active()
        self.apply_persistent_formatting('strikethrough', self.is_strikethrough)
        self.webview.grab_focus()
        self.update_formatting_state()

    def on_bullet_list_toggled(self, btn):
        self.is_bullet_list = btn.get_active()
        self.apply_list_formatting('unordered', self.is_bullet_list)
        self.webview.grab_focus()
        self.update_formatting_state()

    def on_number_list_toggled(self, btn):
        self.is_number_list = btn.get_active()
        self.apply_list_formatting('ordered', self.is_number_list)
        self.webview.grab_focus()
        self.update_formatting_state()

    def on_heading_changed(self, dropdown, *args):
        headings = ["div", "h1", "h2", "h3", "h4", "h5", "h6"]
        selected = dropdown.get_selected()
        if 0 <= selected < len(headings):
            self.exec_js(f"document.execCommand('formatBlock', false, '{headings[selected]}')")
            self.update_formatting_state()

    def on_align_left(self, btn):
        if btn.get_active():
            self.is_align_left = True
            self.is_align_center = self.is_align_right = self.is_align_justify = False
            self.align_center_btn.set_active(False)
            self.align_right_btn.set_active(False)
            self.align_justify_btn.set_active(False)
            self.exec_js("document.execCommand('justifyLeft')")
            self.webview.grab_focus()
            self.update_formatting_state()

    def on_align_center(self, btn):
        if btn.get_active():
            self.is_align_center = True
            self.is_align_left = self.is_align_right = self.is_align_justify = False
            self.align_left_btn.set_active(False)
            self.align_right_btn.set_active(False)
            self.align_justify_btn.set_active(False)
            self.exec_js("document.execCommand('justifyCenter')")
            self.webview.grab_focus()
            self.update_formatting_state()

    def on_align_right(self, btn):
        if btn.get_active():
            self.is_align_right = True
            self.is_align_left = self.is_align_center = self.is_align_justify = False
            self.align_left_btn.set_active(False)
            self.align_center_btn.set_active(False)
            self.align_justify_btn.set_active(False)
            self.exec_js("document.execCommand('justifyRight')")
            self.webview.grab_focus()
            self.update_formatting_state()

    def on_align_justify(self, btn):
        if btn.get_active():
            self.is_align_justify = True
            self.is_align_left = self.is_align_center = self.is_align_right = False
            self.align_left_btn.set_active(False)
            self.align_center_btn.set_active(False)
            self.align_right_btn.set_active(False)
            self.exec_js("document.execCommand('justifyFull')")
            self.webview.grab_focus()
            self.update_formatting_state()

    def on_indent_more(self, *args):
        self.exec_js("document.execCommand('indent')")
        self.update_formatting_state()

    def on_indent_less(self, *args):
        self.exec_js("document.execCommand('outdent')")
        self.update_formatting_state()

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
            self.update_formatting_state()

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
            self.update_formatting_state()

    def open_file_dialog(self):
        file_dialog = Gtk.FileDialog.new()
        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        combined_filter = Gtk.FileFilter()
        combined_filter.set_name("Supported Files (*.mhtml, *.html, *.htm, *.md, *.txt)")
        combined_filter.add_pattern("*.mhtml")
        combined_filter.add_pattern("*.html")
        combined_filter.add_pattern("*.htm")
        combined_filter.add_pattern("*.md")
        combined_filter.add_pattern("*.txt")
        filter_store.append(combined_filter)

        mhtml_filter = Gtk.FileFilter()
        mhtml_filter.set_name("MHTML Files (*.mhtml)")
        mhtml_filter.add_pattern("*.mhtml")
        filter_store.append(mhtml_filter)

        html_filter = Gtk.FileFilter()
        html_filter.set_name("HTML Files (*.html, *.htm)")
        html_filter.add_pattern("*.html")
        html_filter.add_pattern("*.htm")
        filter_store.append(html_filter)

        md_filter = Gtk.FileFilter()
        md_filter.set_name("Markdown Files (*.md)")
        md_filter.add_pattern("*.md")
        filter_store.append(md_filter)

        txt_filter = Gtk.FileFilter()
        txt_filter.set_name("Text Files (*.txt)")
        txt_filter.add_pattern("*.txt")
        filter_store.append(txt_filter)

        file_dialog.set_filters(filter_store)
        file_dialog.set_default_filter(combined_filter)
        file_dialog.open(self, None, self.on_open_file_dialog_response)

    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.current_file = file
                self.is_new = False
                self.update_title()
                file_path = file.get_path()
                if file_path.endswith(".mhtml"):
                    self.webview.load_uri(file.get_uri())
                elif file_path.endswith(".html") or file_path.endswith(".htm"):
                    file.load_contents_async(None, self.load_html_callback)
                elif file_path.endswith(".md"):
                    self.load_markdown_file(file)
                elif file_path.endswith(".txt"):
                    self.load_txt_file(file)
                else:
                    print("Unsupported file type")
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

    def load_markdown_file(self, file):
        try:
            with open(file.get_path(), 'r', encoding='utf-8') as f:
                md_content = f.read()
            with tempfile.TemporaryDirectory() as temp_dir:
                assets_dir = os.path.join(temp_dir, "assets")
                os.makedirs(assets_dir, exist_ok=True)
                base_dir = os.path.dirname(file.get_path())
                md_content = self.process_markdown_images(md_content, base_dir, assets_dir)
                html_body = markdown.markdown(md_content, extensions=['extra', 'codehilite'])
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; font-size: 11pt; margin: 20px; line-height: 1.5; }}
        @media (prefers-color-scheme: dark) {{ body {{ background-color: #121212; color: #e0e0e0; }} }}
        @media (prefers-color-scheme: light) {{ body {{ background-color: #ffffff; color: #000000; }} }}
        img {{ max-width: 100%; resize: both; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; }}
        code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
    </style>
</head>
<body>{html_body}</body>
</html>"""
                html_content = html_content.replace("assets/", f"file://{assets_dir}/")
                self.ignore_changes = True
                self.webview.load_html(html_content, f"file://{temp_dir}/")
                GLib.timeout_add(500, self.clear_ignore_changes)
                self.is_modified = False
                self.update_title()
                print(f"Loaded Markdown file: {file.get_path()}")
        except Exception as e:
            print(f"Error loading Markdown file: {e}")

    def load_txt_file(self, file):
        try:
            with open(file.get_path(), 'r', encoding='utf-8') as f:
                text = f.read()
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; font-size: 11pt; margin: 20px; line-height: 1.5; }}
        @media (prefers-color-scheme: dark) {{ body {{ background-color: #121212; color: #e0e0e0; }} }}
        @media (prefers-color-scheme: light) {{ body {{ background-color: #ffffff; color: #000000; }} }}
    </style>
</head>
<body><pre>{text}</pre></body>
</html>"""
            self.ignore_changes = True
            self.webview.load_html(html_content, file.get_uri())
            GLib.timeout_add(500, self.clear_ignore_changes)
            self.is_modified = False
            self.update_title()
        except Exception as e:
            print(f"Error loading text file: {e}")

    def process_markdown_images(self, md_content, base_dir, temp_assets_dir):
        img_pattern = r'!\[.*?\]\((.*?)\)'
        matches = re.findall(img_pattern, md_content)
        
        for i, src in enumerate(matches):
            if src.startswith("http://") or src.startswith("https://"):
                continue
            elif src.startswith("data:image"):
                try:
                    header, data = src.split(",", 1)
                    mime_type = header.split(";")[0].replace("data:", "")
                    ext = mime_type.split("/")[1]
                    img_data = base64.b64decode(data)
                    img_name = f"image_{i}.{ext}"
                    img_path = os.path.join(temp_assets_dir, img_name)
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    md_content = md_content.replace(src, f"assets/{img_name}")
                except Exception as e:
                    print(f"Error processing Markdown base64 image {i}: {e}")
            else:
                try:
                    abs_path = os.path.join(base_dir, src)
                    if os.path.exists(abs_path):
                        img_name = f"image_{i}{os.path.splitext(abs_path)[1]}"
                        img_path = os.path.join(temp_assets_dir, img_name)
                        shutil.copy(abs_path, img_path)
                        md_content = md_content.replace(src, f"assets/{img_name}")
                    else:
                        print(f"Markdown image not found: {abs_path}")
                except Exception as e:
                    print(f"Error copying Markdown image {i}: {e}")
        
        return md_content

    def clear_ignore_changes(self):
        self.ignore_changes = False
        return False

    def add_css_styles(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(b"window { background-color: @window_bg_color; }")
        Gtk.StyleContext.add_provider_for_display(self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def check_save_before_new(self):
        if self.is_modified:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Save changes?",
                body="Do you want to save changes to this document before starting a new one?",
                close_response="cancel",
                modal=True
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)

            def on_response(dialog, response):
                if response == "save":
                    if self.current_file and not self.is_new:
                        file_path = self.current_file.get_path()
                        if file_path.endswith(".mhtml"):
                            self.save_as_mhtml(self.current_file)
                        elif file_path.endswith(".html") or file_path.endswith(".htm"):
                            self.save_as_html(self.current_file)
                        elif file_path.endswith(".txt"):
                            self.save_as_txt(self.current_file)
                        self.start_new_document()
                    else:
                        self.show_save_dialog()
                        self.start_new_document()
                elif response == "discard":
                    self.start_new_document()
                dialog.destroy()

            dialog.connect("response", on_response)
            dialog.present()
            return True
        return False

    def check_save_before_close(self):
        if self.is_modified:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Save changes?",
                body="Do you want to save changes to this document before closing?",
                close_response="cancel",
                modal=True
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)

            def on_response(dialog, response):
                if response == "save":
                    if self.current_file and not self.is_new:
                        file_path = self.current_file.get_path()
                        if file_path.endswith(".mhtml"):
                            self.save_as_mhtml(self.current_file)
                        elif file_path.endswith(".html") or file_path.endswith(".htm"):
                            self.save_as_html(self.current_file)
                        elif file_path.endswith(".txt"):
                            self.save_as_txt(self.current_file)
                        self.get_application().quit()
                    else:
                        self.show_save_dialog()
                elif response == "discard":
                    self.get_application().quit()
                dialog.destroy()

            dialog.connect("response", on_response)
            dialog.present()
            return True
        return False

    def start_new_document(self):
        self.webview.load_html(self.initial_html, "file:///")
        self.current_file = None
        self.is_new = True
        self.is_modified = False
        self.document_number = EditorWindow.document_counter
        EditorWindow.document_counter += 1
        self.update_title()

    def on_close_document_clicked(self, btn):
        if not self.check_save_before_new():
            self.start_new_document()

    def on_close_request(self, *args):
        if not self.check_save_before_close():
            self.get_application().quit()
        return True

    def apply_persistent_formatting(self, format_type, enable):
        desired = str(enable).lower()
        script = f"""
            (function() {{
                let sel = window.getSelection();
                if (!sel.rangeCount) {{
                    let range = document.createRange();
                    range.selectNodeContents(document.body);
                    range.collapse(false);
                    sel.removeAllRanges();
                    sel.addRange(range);
                }}
                let cmd = '{format_type}';
                let currentState = document.queryCommandState(cmd);
                if (currentState !== {desired}) {{
                    document.execCommand(cmd, false, null);
                }}
            }})();
        """
        self.exec_js(script)

    def apply_list_formatting(self, list_type, enable):
        cmd = 'insertUnorderedList' if list_type == 'unordered' else 'insertOrderedList'
        list_tag = 'ul' if list_type == 'unordered' else 'ol'
        script = f"""
            (function() {{
                let sel = window.getSelection();
                if (!sel.rangeCount) {{
                    let body = document.body;
                    let range = document.createRange();
                    range.selectNodeContents(body);
                    range.collapse(false);
                    sel.removeAllRanges();
                    sel.addRange(range);
                }}
                let range = sel.getRangeAt(0);
                let isEnabled = {'true' if enable else 'false'};
                let ancestor = range.commonAncestorContainer;
                let parentElement = (ancestor.nodeType === 3) ? ancestor.parentElement : ancestor;
                let currentList = parentElement.closest('{list_tag}');
                if (isEnabled && !currentList) {{
                    document.execCommand('{cmd}', false, null);
                }} else if (!isEnabled && currentList) {{
                    document.execCommand('{cmd}', false, null);
                }}
            }})();
        """
        self.exec_js(script)
        if list_type == 'unordered' and enable:
            self.is_number_list = False
            self.number_btn.set_active(False)
        elif list_type == 'ordered' and enable:
            self.is_bullet_list = False
            self.bullet_btn.set_active(False)

    def update_formatting_state(self):
        script = """
            (function() {
                let sel = window.getSelection();
                if (!sel.rangeCount) return JSON.stringify({});
                let range = sel.getRangeAt(0);
                let container = range.startContainer;
                let parent = (container.nodeType === 3) ? container.parentElement : container;
                let computedStyle = window.getComputedStyle(parent);
                let blockParent = parent;
                while (blockParent && !window.getComputedStyle(blockParent).display.includes('block')) {
                    blockParent = blockParent.parentElement;
                }
                let heading = blockParent ? blockParent.tagName.toLowerCase() : 'div';
                if (heading === 'p' || !['h1','h2','h3','h4','h5','h6'].includes(heading)) heading = 'div';
                let states = {
                    bold: computedStyle.fontWeight === 'bold' || parseInt(computedStyle.fontWeight) > 400,
                    italic: computedStyle.fontStyle === 'italic',
                    underline: computedStyle.textDecorationLine.includes('underline'),
                    strikethrough: computedStyle.textDecorationLine.includes('line-through'),
                    ul: parent.closest('ul') !== null,
                    ol: parent.closest('ol') !== null,
                    justifyLeft: document.queryCommandState('justifyLeft'),
                    justifyCenter: document.queryCommandState('justifyCenter'),
                    justifyRight: document.queryCommandState('justifyRight'),
                    justifyFull: document.queryCommandState('justifyFull'),
                    fontFamily: computedStyle.fontFamily.split(',')[0].replace(/['"]/g, ''),
                    fontSize: computedStyle.fontSize,
                    color: computedStyle.color,
                    backgroundColor: computedStyle.backgroundColor,
                    heading: heading
                };
                return JSON.stringify(states);
            })();
        """
        self.webview.evaluate_javascript(script, -1, None, None, None, self.on_formatting_state_received, None)

    def on_formatting_state_received(self, webview, result, user_data):
        try:
            js_value = webview.evaluate_javascript_finish(result)
            if js_value and js_value.is_string():
                states = json.loads(js_value.to_string())
                
                # Bold
                if states.get('bold', False) != self.is_bold:
                    self.is_bold = states['bold']
                    self.bold_btn.set_active(self.is_bold)
                
                # Italic
                if states.get('italic', False) != self.is_italic:
                    self.is_italic = states['italic']
                    self.italic_btn.set_active(self.is_italic)
                
                # Underline
                if states.get('underline', False) != self.is_underline:
                    self.is_underline = states['underline']
                    self.underline_btn.set_active(self.is_underline)
                
                # Strikethrough
                if states.get('strikethrough', False) != self.is_strikethrough:
                    self.is_strikethrough = states['strikethrough']
                    self.strikethrough_btn.set_active(self.is_strikethrough)
                
                # Bullet List
                if states.get('ul', False) != self.is_bullet_list:
                    self.is_bullet_list = states['ul']
                    self.bullet_btn.set_active(self.is_bullet_list)
                
                # Numbered List
                if states.get('ol', False) != self.is_number_list:
                    self.is_number_list = states['ol']
                    self.number_btn.set_active(self.is_number_list)
                
                # Alignment
                if states.get('justifyLeft', False) != self.is_align_left:
                    self.is_align_left = states['justifyLeft']
                    self.align_left_btn.set_active(self.is_align_left)
                if states.get('justifyCenter', False) != self.is_align_center:
                    self.is_align_center = states['justifyCenter']
                    self.align_center_btn.set_active(self.is_align_center)
                if states.get('justifyRight', False) != self.is_align_right:
                    self.is_align_right = states['justifyRight']
                    self.align_right_btn.set_active(self.is_align_right)
                if states.get('justifyFull', False) != self.is_align_justify:
                    self.is_align_justify = states['justifyFull']
                    self.align_justify_btn.set_active(self.is_align_justify)
                
                # Font Family
                font_family = states.get('fontFamily', 'Sans')
                model = self.font_dropdown.get_model()
                for i in range(model.get_n_items()):
                    if model.get_item(i).get_string() == font_family:
                        self.font_dropdown.set_selected(i)
                        break
                
                # Font Size
                font_size = states.get('fontSize', '11pt').replace('px', '').replace('pt', '')
                try:
                    font_size = str(float(font_size))
                    model = self.size_dropdown.get_model()
                    for i in range(model.get_n_items()):
                        if model.get_item(i).get_string() == font_size:
                            self.size_dropdown.set_selected(i)
                            break
                except ValueError:
                    pass
                
                # Text Color
                color = states.get('color', 'rgb(0, 0, 0)')
                if Gdk.RGBA().parse(color):
                    self.current_text_color = Gdk.RGBA()
                    self.current_text_color.parse(color)
                    self.text_color_indicator.queue_draw()
                
                # Background Color
                bg_color = states.get('backgroundColor', 'rgba(0, 0, 0, 0)')
                if Gdk.RGBA().parse(bg_color):
                    self.current_bg_color = Gdk.RGBA()
                    self.current_bg_color.parse(bg_color)
                    self.bg_color_indicator.queue_draw()
                
                # Heading
                heading = states.get('heading', 'div')
                headings = {"div": 0, "h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
                self.heading_dropdown.set_selected(headings.get(heading, 0))
        except Exception as e:
            print(f"Error updating formatting state: {e}")

if __name__ == "__main__":
    app = Author()
    app.run()
