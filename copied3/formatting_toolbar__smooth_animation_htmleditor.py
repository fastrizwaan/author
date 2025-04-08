#!/usr/bin/env python3
import sys
import gi
import re
import os

# Hardware Acclerated Rendering (0); Software Rendering (1)
os.environ['WEBKIT_DISABLE_COMPOSITING_MODE'] = '0'

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Adw, Gdk, WebKit, GLib, Gio

class HTMLEditorApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id='io.github.fastrizwaan.htmleditor',
                        flags=Gio.ApplicationFlags.HANDLES_OPEN,
                        **kwargs)
        self.windows = []  # Track all open windows
        self.window_buttons = {}  # Track window menu buttons {window_id: button}
        self.connect('activate', self.on_activate)
        self.connect("open", self.on_open)
        
        # Window properties (migrated from HTMLEditorWindow)
        self.modified = False
        self.auto_save_enabled = False
        self.auto_save_interval = 60
        self.current_file = None
        self.auto_save_source_id = None
        self.overlay_setup_done = False

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.create_actions()

    def on_activate(self, app):
        """Handle application activation (new window)"""
        win = self.create_window()
        win.present()
        self.update_window_menu()

    def on_open(self, app, files, n_files, hint):
        """Handle file opening"""
        windows_added = False
        
        for file in files:
            file_path = file.get_path()
            existing_win = None
            for win in self.windows:
                if hasattr(win, 'current_file') and win.current_file and win.current_file.get_path() == file_path:
                    existing_win = win
                    break
            
            if existing_win:
                existing_win.present()
            else:
                win = self.create_window()
                self.load_file(win, file_path)
                win.present()
                windows_added = True
                
        if windows_added:
            self.update_window_menu()

    def create_window(self):
        """Create a new window with all initialization (former HTMLEditorWindow.__init__)"""
        win = Adw.ApplicationWindow(application=self)
        
        # Set window properties
        win.modified = False
        win.auto_save_enabled = False
        win.auto_save_interval = 60
        win.current_file = None
        win.auto_save_source_id = None
        win.top_toolbar_visible = True  # Track toolbar visibility state
        
        win.set_default_size(900, 700)
        win.set_title("Untitled - HTML Editor")
        
        win.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.main_box.set_vexpand(True)  # Ensure main_box expands vertically
        win.main_box.set_hexpand(True)
        
        # Create header bar and add it to main_box
        self.create_header_bar(win)
        
        # Create bottom toolbar (now top toolbar, below header)
        win.top_toolbar = self.create_bottom_toolbar(win)
        # Add toolbar right after the header
        win.main_box.append(win.top_toolbar)
        
        # Create content area for the webview and statusbar
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Create and configure webview
        win.webview = WebKit.WebView()
        win.webview.set_vexpand(True)
        win.webview.set_hexpand(True) 
        win.webview.load_html(self.get_editor_html(), None)
        settings = win.webview.get_settings()
        try:
            settings.set_enable_developer_extras(True)
        except:
            pass
        
        try:
            user_content_manager = win.webview.get_user_content_manager()
            user_content_manager.register_script_message_handler("contentChanged")
            user_content_manager.connect("script-message-received::contentChanged", 
                                        lambda mgr, res: self.on_content_changed(win, mgr, res))
        except:
            print("Warning: Could not set up JavaScript message handlers")
            
        win.webview.load_html(self.get_initial_html(), None)
        
        win.statusbar = Gtk.Label(label="Ready")
        win.statusbar.set_halign(Gtk.Align.START)
        win.statusbar.set_margin_start(10)
        win.statusbar.set_margin_end(10)
        win.statusbar.set_margin_top(5)
        win.statusbar.set_margin_bottom(5)
        
        # Add webview and statusbar to content box
        content_box.append(win.webview)
        #content_box.append(win.statusbar)
        
        # Add content box to main box
        win.main_box.append(content_box)
        
        # Set the content of the window
        win.set_content(win.main_box)
        
        self.setup_toolbar_animation(win)
        self.setup_keyboard_shortcuts(win)
        
        win.connect("close-request", self.on_window_close_request)
        
        # Add to windows list
        self.windows.append(win)
        self.setup_header_bar(win)
        
        return win            

    def create_header_bar(self, win):
        """Create a header bar for the window"""
        # Create a header bar
        header = Adw.HeaderBar()
        
        # Create buttons for header bar
        new_button = Gtk.Button(icon_name="document-new-symbolic")
        new_button.set_tooltip_text("New Document in New Window")
        new_button.connect("clicked", lambda btn: self.on_new_clicked(win, btn))
        
        open_button = Gtk.Button(icon_name="document-open-symbolic")
        open_button.set_tooltip_text("Open File in New Window")
        open_button.connect("clicked", lambda btn: self.on_open_clicked(win, btn))
        
        save_button = Gtk.Button(icon_name="document-save-symbolic")
        save_button.set_tooltip_text("Save File")
        save_button.connect("clicked", lambda btn: self.on_save_clicked(win, btn))
        
        # Create undo/redo buttons
        win.undo_button = Gtk.Button(icon_name="edit-undo-symbolic")
        win.undo_button.set_tooltip_text("Undo")
        win.undo_button.connect("clicked", lambda btn: self.on_undo_clicked(win, btn))
        win.undo_button.set_sensitive(False)  # Initially disabled
        
        win.redo_button = Gtk.Button(icon_name="edit-redo-symbolic")
        win.redo_button.set_tooltip_text("Redo")
        win.redo_button.connect("clicked", lambda btn: self.on_redo_clicked(win, btn))
        win.redo_button.set_sensitive(False)  # Initially disabled
        
        # Create menu
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About", "app.about")
        menu.append("Quit", "app.quit")
        
        menu_button.set_menu_model(menu)
        
        # Add buttons to header bar
        header.pack_start(new_button)
        header.pack_start(open_button)
        header.pack_start(save_button)
        header.pack_start(win.undo_button)
        header.pack_start(win.redo_button)
        header.pack_end(menu_button)
        
        win.main_box.append(header)
    
    def create_bottom_toolbar(self, win):
        """Create the bottom toolbar for a window"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(10)
        toolbar.set_margin_end(10)
        toolbar.set_margin_top(5)
        toolbar.set_margin_bottom(5)
        
        # Add some HTML editing buttons
        bold_button = Gtk.Button(icon_name="format-text-bold-symbolic")
        bold_button.set_tooltip_text("Bold")
        bold_button.connect("clicked", lambda btn: self.on_bold_clicked(win, btn))
        
        italic_button = Gtk.Button(icon_name="format-text-italic-symbolic")
        italic_button.set_tooltip_text("Italic")
        italic_button.connect("clicked", lambda btn: self.on_italic_clicked(win, btn))
        
        underline_button = Gtk.Button(icon_name="format-text-underline-symbolic")
        underline_button.set_tooltip_text("Underline")
        underline_button.connect("clicked", lambda btn: self.on_underline_clicked(win, btn))
        
        # Add a spacer (expanding box)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        
        # Add a close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda btn: self.on_close_toolbar_clicked(win, btn))
        
        # Add all widgets to the toolbar
        toolbar.append(bold_button)
        toolbar.append(italic_button)
        toolbar.append(underline_button)
        toolbar.append(spacer)
        toolbar.append(close_button)
        
        return toolbar
        
    def setup_keyboard_shortcuts(self, win):
        """Setup keyboard shortcuts for the window"""
        # Create a shortcut controller
        controller = Gtk.ShortcutController()
        
        # Create Ctrl+T shortcut for toggling the toolbar
        trigger = Gtk.ShortcutTrigger.parse_string("<Control>t")
        action = Gtk.CallbackAction.new(lambda *args: self.toggle_toolbar(win, *args))
        shortcut = Gtk.Shortcut.new(trigger, action)
        controller.add_shortcut(shortcut)

        # Create Ctrl+Shift+T shortcut for toggling the top toolbar
        trigger_top = Gtk.ShortcutTrigger.parse_string("<Control><Shift>t")
        action_top = Gtk.CallbackAction.new(lambda *args: self.toggle_top_toolbar(win, *args))
        shortcut_top = Gtk.Shortcut.new(trigger_top, action_top)
        controller.add_shortcut(shortcut_top)
        
        # Create Ctrl+Z shortcut for undo
        trigger_undo = Gtk.ShortcutTrigger.parse_string("<Control>z")
        action_undo = Gtk.CallbackAction.new(lambda *args: self.on_undo_shortcut(win, *args))
        shortcut_undo = Gtk.Shortcut.new(trigger_undo, action_undo)
        controller.add_shortcut(shortcut_undo)
        
        # Create Ctrl+Y shortcut for redo
        trigger_redo = Gtk.ShortcutTrigger.parse_string("<Control>y")
        action_redo = Gtk.CallbackAction.new(lambda *args: self.on_redo_shortcut(win, *args))
        shortcut_redo = Gtk.Shortcut.new(trigger_redo, action_redo)
        controller.add_shortcut(shortcut_redo)
        
        # Create Ctrl+W shortcut for closing current window
        trigger_close = Gtk.ShortcutTrigger.parse_string("<Control>w")
        action_close = Gtk.CallbackAction.new(lambda *args: self.on_close_shortcut(win, *args))
        shortcut_close = Gtk.Shortcut.new(trigger_close, action_close)
        controller.add_shortcut(shortcut_close)
        
        # Create Ctrl+Shift+W shortcut for closing other windows
        trigger_close_others = Gtk.ShortcutTrigger.parse_string("<Control><Shift>w")
        action_close_others = Gtk.CallbackAction.new(lambda *args: self.on_close_others_shortcut(win, *args))
        shortcut_close_others = Gtk.Shortcut.new(trigger_close_others, action_close_others)
        controller.add_shortcut(shortcut_close_others)
        
        # Add controller to the window (not the webview)
        win.add_controller(controller)
        
        # Make it capture events at the capture phase
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        
        # Make shortcut work regardless of who has focus
        controller.set_scope(Gtk.ShortcutScope.GLOBAL)

    def on_close_shortcut(self, win, *args):
        """Handle Ctrl+W shortcut to close current window"""
        win.close()
        return True

    def on_close_others_shortcut(self, win, *args):
        """Handle Ctrl+Shift+W shortcut to close other windows"""
        self.on_close_other_windows(None, None)
        return True
    
    def setup_toolbar_animation(self, win):
        if hasattr(win, 'overlay_setup_done') and win.overlay_setup_done:
            return
        
        # Create an overlay
        win.overlay = Gtk.Overlay()
        win.overlay.set_vexpand(True)  # Ensure overlay expands vertically
        win.overlay.set_hexpand(True)  # Ensure overlay expands horizontally
        
        # Get the content box and remove the webview from its current parent
        content_box = win.webview.get_parent()
        if win.webview.get_parent():
            win.webview.get_parent().remove(win.webview)
        
        # Create a box to hold the webview
        webview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        webview_box.set_vexpand(True)  # Ensure webview_box expands vertically
        webview_box.set_hexpand(True)  # Ensure webview_box expands horizontally
        webview_box.append(win.webview)
        
        # Set webview_box as the main child of the overlay
        win.overlay.set_child(webview_box)
        
        # Create the toolbar box
        win.toolbar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.toolbar_box.set_halign(Gtk.Align.FILL)
        win.toolbar_box.set_valign(Gtk.Align.END)
        win.toolbar_box.set_margin_start(0)
        win.toolbar_box.set_margin_end(0)
        win.toolbar_box.set_margin_bottom(0)
        win.toolbar_box.add_css_class("toolbar-overlay")
        
        # Create and populate the overlay toolbar
        win.overlay_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        win.overlay_toolbar.set_margin_start(0)
        win.overlay_toolbar.set_margin_end(0)
        win.overlay_toolbar.set_margin_top(0)
        win.overlay_toolbar.set_margin_bottom(0)
        
        bold_button = Gtk.Button(icon_name="format-text-bold-symbolic")
        bold_button.set_tooltip_text("Bold")
        bold_button.connect("clicked", lambda btn: self.on_bold_clicked(win, btn))
        
        italic_button = Gtk.Button(icon_name="format-text-italic-symbolic")
        italic_button.set_tooltip_text("Italic")
        italic_button.connect("clicked", lambda btn: self.on_italic_clicked(win, btn))
        
        underline_button = Gtk.Button(icon_name="format-text-underline-symbolic")
        underline_button.set_tooltip_text("Underline")
        underline_button.connect("clicked", lambda btn: self.on_underline_clicked(win, btn))
        
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda btn: self.on_close_toolbar_clicked(win, btn))
        
        win.overlay_toolbar.append(bold_button)
        win.overlay_toolbar.append(italic_button)
        win.overlay_toolbar.append(underline_button)
        win.overlay_toolbar.append(spacer)
        win.overlay_toolbar.append(close_button)
        
        win.toolbar_box.append(win.overlay_toolbar)
        
        # Add toolbar_box as an overlay child
        win.overlay.add_overlay(win.toolbar_box)
        
        # Remove existing children from content_box and add the overlay
        if content_box:
            child = content_box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                if child != win.statusbar and child != win.bottom_toolbar:
                    content_box.remove(child)
                child = next_child
            content_box.append(win.overlay)
        
        # Ensure statusbar is at the bottom
        if win.statusbar.get_parent():
            win.statusbar.get_parent().remove(win.statusbar)
        #content_box.append(win.statusbar)
        
        # Set initial state: hidden with zero opacity
        win.toolbar_box.set_opacity(0.0)  # Start fully transparent
        win.toolbar_box.set_visible(True)  # Keep visible but transparent
        
        # Add CSS for toolbar styling and fade animation
        css_provider = Gtk.CssProvider()
        css_data = """
            .toolbar-overlay {
                background-color: @theme_bg_color;
                border-radius: 0px;
                min-height: 36px;
        }
        """
        css_provider.load_from_data(css_data.encode('utf-8'))
        display = win.get_display()
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        win.overlay_setup_done = True
        print("Overlay toolbar setup complete with fade animation")
        
    def toggle_toolbar(self, win, *args):
        """Toggle the visibility of the toolbar overlay with a fade effect"""
        if hasattr(win, 'toolbar_box'):
            current_opacity = win.toolbar_box.get_opacity()
            
            if current_opacity > 0.0:  # Currently visible, fade out
                win.toolbar_box.set_opacity(0.0)
                win.statusbar.set_text("Toolbar hidden")
                print("Toolbar faded out")
            else:  # Currently hidden, fade in
                win.toolbar_box.set_opacity(1.0)
                win.statusbar.set_text("Toolbar shown")
                print("Toolbar faded in")
        else:
            print("Toolbar box not initialized")
        
        return True
        
    def on_close_toolbar_clicked(self, win, button):
        """Handle the close button click with fade-out"""
        if hasattr(win, 'toolbar_box'):
            win.toolbar_box.set_opacity(0.0)
            win.statusbar.set_text("Toolbar hidden")
        else:
            win.bottom_toolbar.set_visible(False)  # Fallback for old toolbar

    def get_editor_html(self, content=""):
        content = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return f"""
    <!DOCTYPE html>
    <html style="height: 100%;">
    <head>
        <title>HTML Editor</title>
        <style>
            html, body {{
                height: 100%;
                margin: 40px; /*Change this for page border*/
                padding: 0;
                font-family: Arial, sans-serif;
            }}
            #editor {{
                border: 1px solid #ccc;
                padding: 10px;
                outline: none;
                min-height: 200px; /* Reduced fallback minimum height */
                height: 100%; /* Allow it to expand fully */
                box-sizing: border-box; /* Include padding/border in height */
            }}
            #editor div {{
                margin: 0;
                padding: 0;
            }}
            #editor:empty:not(:focus):before {{
                content: "Type here to start editing...";
                color: #aaa;
                font-style: italic;
                position: absolute;
                pointer-events: none;
                top: 10px;
                left: 10px;
            }}
        </style>
        <script>
            window.initialContent = "{content or '<div><br></div>'}";
            {self.get_editor_js()}
        </script>
    </head>
    <body>
        <div id="editor" contenteditable="true"></div>
    </body>
    </html>
    """

    def get_editor_js(self):
        """Return the combined JavaScript logic for the editor."""
        return f"""
        // Global scope for persistence
        window.undoStack = [];
        window.redoStack = [];
        window.isUndoRedo = false;
        window.lastContent = "";

        {self.save_state_js()}
        {self.perform_undo_js()}
        {self.perform_redo_js()}
        {self.find_last_text_node_js()}
        {self.get_stack_sizes_js()}
        {self.set_content_js()}
        {self.init_editor_js()}
        """

    def save_state_js(self):
        """JavaScript to save the editor state to the undo stack."""
        return """
        function saveState() {
            window.undoStack.push(document.getElementById('editor').innerHTML);
            if (window.undoStack.length > 100) {
                window.undoStack.shift();
            }
        }
        """

    def perform_undo_js(self):
        """JavaScript to perform an undo operation."""
        return """
        function performUndo() {
            const editor = document.getElementById('editor');
            if (window.undoStack.length > 1) {
                let selection = window.getSelection();
                let range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
                let cursorNode = range ? range.startContainer : null;
                let cursorOffset = range ? range.startOffset : 0;

                window.redoStack.push(window.undoStack.pop());
                window.isUndoRedo = true;
                editor.innerHTML = window.undoStack[window.undoStack.length - 1];
                window.lastContent = editor.innerHTML;
                window.isUndoRedo = false;

                editor.focus();
                try {
                    const newRange = document.createRange();
                    const sel = window.getSelection();
                    const textNode = findLastTextNode(editor) || editor;
                    const offset = textNode.nodeType === 3 ? textNode.length : 0;
                    newRange.setStart(textNode, offset);
                    newRange.setEnd(textNode, offset);
                    sel.removeAllRanges();
                    sel.addRange(newRange);
                } catch (e) {
                    console.log("Could not restore cursor position:", e);
                }
                return { success: true, isInitialState: window.undoStack.length === 1 };
            }
            return { success: false, isInitialState: window.undoStack.length === 1 };
        }
        """

    def perform_redo_js(self):
        """JavaScript to perform a redo operation."""
        return """
        function performRedo() {
            const editor = document.getElementById('editor');
            if (window.redoStack.length > 0) {
                let selection = window.getSelection();
                let range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
                let cursorNode = range ? range.startContainer : null;
                let cursorOffset = range ? range.startOffset : 0;

                const state = window.redoStack.pop();
                window.undoStack.push(state);
                window.isUndoRedo = true;
                editor.innerHTML = state;
                window.lastContent = editor.innerHTML;
                window.isUndoRedo = false;

                editor.focus();
                try {
                    const newRange = document.createRange();
                    const sel = window.getSelection();
                    const textNode = findLastTextNode(editor) || editor;
                    const offset = textNode.nodeType === 3 ? textNode.length : 0;
                    newRange.setStart(textNode, offset);
                    newRange.setEnd(textNode, offset);
                    sel.removeAllRanges();
                    sel.addRange(newRange);
                } catch (e) {
                    console.log("Could not restore cursor position:", e);
                }
                return { success: true, isInitialState: window.undoStack.length === 1 };
            }
            return { success: false, isInitialState: window.undoStack.length === 1 };
        }
        """

    def find_last_text_node_js(self):
        """JavaScript to find the last text node for cursor restoration."""
        return """
        function findLastTextNode(node) {
            if (node.nodeType === 3) return node;
            for (let i = node.childNodes.length - 1; i >= 0; i--) {
                const found = findLastTextNode(node.childNodes[i]);
                if (found) return found;
            }
            return null;
        }
        """

    def get_stack_sizes_js(self):
        """JavaScript to get the sizes of undo and redo stacks."""
        return """
        function getStackSizes() {
            return {
                undoSize: window.undoStack.length,
                redoSize: window.redoStack.length
            };
        }
        """

    def set_content_js(self):
        """JavaScript to set the editor content and reset stacks."""
        return """
        function setContent(html) {
            const editor = document.getElementById('editor');
            if (!html || html.trim() === '') {
                editor.innerHTML = '<div><br></div>';
            } else if (!html.trim().match(/^<(div|p|h[1-6]|ul|ol|table)/i)) {
                editor.innerHTML = '<div>' + html + '</div>';
            } else {
                editor.innerHTML = html;
            }
            window.lastContent = editor.innerHTML;
            window.undoStack = [window.lastContent];
            window.redoStack = [];
            editor.focus();
        }
        """

    def init_editor_js(self):
        """JavaScript to initialize the editor and set up event listeners."""
        return """
        document.addEventListener('DOMContentLoaded', function() {
            const editor = document.getElementById('editor');
            
            editor.addEventListener('focus', function onFirstFocus(e) {
                if (!editor.textContent.trim() && editor.innerHTML === '') {
                    editor.innerHTML = '<div><br></div>';
                    const range = document.createRange();
                    const sel = window.getSelection();
                    const firstDiv = editor.querySelector('div');
                    if (firstDiv) {
                        range.setStart(firstDiv, 0);
                        range.collapse(true);
                        sel.removeAllRanges();
                        sel.addRange(range);
                    }
                    editor.removeEventListener('focus', onFirstFocus);
                }
            });

            window.lastContent = editor.innerHTML;
            saveState();
            editor.focus();

            editor.addEventListener('input', function(e) {
                if (document.getSelection().anchorNode === editor) {
                    document.execCommand('formatBlock', false, 'div');
                }
                if (!window.isUndoRedo) {
                    const currentContent = editor.innerHTML;
                    if (currentContent !== window.lastContent) {
                        saveState();
                        window.lastContent = currentContent;
                        window.redoStack = [];
                        try {
                            window.webkit.messageHandlers.contentChanged.postMessage("changed");
                        } catch(e) {
                            console.log("Could not notify about changes:", e);
                        }
                    }
                }
            });

            if (window.initialContent) {
                setContent(window.initialContent);
            }
        });
        """
        
    def get_initial_html(self):
        return self.get_editor_html()
    
    def execute_js(self, win, script):
        """Execute JavaScript in the WebView"""
        win.webview.evaluate_javascript(script, -1, None, None, None, None, None)
    
    def extract_body_content(self, html):
        """Extract content from the body or just return the HTML if parsing fails"""
        try:
            # Simple regex to extract content between body tags
            import re
            body_match = re.search(r'<body[^>]*>([\s\S]*)<\/body>', html)
            if body_match:
                return body_match.group(1)
            return html
        except Exception:
            # In case of any error, return the original HTML
            return html
    
    # Undo/Redo related methods
    def on_content_changed(self, win, manager, result):
        win.modified = True
        self.update_window_title(win)
        self.update_undo_redo_state(win)
        
    def update_undo_redo_state(self, win):
        try:
            # Get stack sizes to update button states
            win.webview.evaluate_javascript(
                "JSON.stringify(getStackSizes());",  # Ensure we get a proper JSON string
                -1, None, None, None,
                lambda webview, result, data: self._on_get_stack_sizes(win, webview, result, data), 
                None
            )
        except Exception as e:
            print(f"Error updating undo/redo state: {e}")
            # Fallback - enable buttons
            win.undo_button.set_sensitive(True)
            win.redo_button.set_sensitive(False)
        
    def _on_get_stack_sizes(self, win, webview, result, user_data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                # Try different approaches to get the result based on WebKit version
                try:
                    # Newer WebKit APIs
                    if hasattr(js_result, 'get_js_value'):
                        stack_sizes = js_result.get_js_value().to_string()
                    # Direct value access - works in some WebKit versions
                    elif hasattr(js_result, 'to_string'):
                        stack_sizes = js_result.to_string()
                    elif hasattr(js_result, 'get_string'):
                        stack_sizes = js_result.get_string()
                    else:
                        # Fallback - try converting to string directly
                        stack_sizes = str(js_result)
                    
                    # Parse the JSON result
                    import json
                    try:
                        # Remove any surrounding quotes if present
                        if stack_sizes.startswith('"') and stack_sizes.endswith('"'):
                            stack_sizes = stack_sizes[1:-1]
                        
                        # Try to parse as JSON
                        sizes = json.loads(stack_sizes)
                        # Update button states
                        win.undo_button.set_sensitive(sizes.get('undoSize', 0) > 1)
                        win.redo_button.set_sensitive(sizes.get('redoSize', 0) > 0)
                    except json.JSONDecodeError as je:
                        print(f"Error parsing JSON: {je}, value was: {stack_sizes}")
                        # Set reasonable defaults
                        win.undo_button.set_sensitive(True)
                        win.redo_button.set_sensitive(False)
                except Exception as inner_e:
                    print(f"Inner error processing JS result: {inner_e}")
                    # Set reasonable defaults
                    win.undo_button.set_sensitive(True)
                    win.redo_button.set_sensitive(False)
        except Exception as e:
            print(f"Error getting stack sizes: {e}")
            # Set reasonable defaults in case of error
            win.undo_button.set_sensitive(True)
            win.redo_button.set_sensitive(False)
            
    def on_undo_clicked(self, win, button):
        self.perform_undo(win)
        
    def on_redo_clicked(self, win, button):
        self.perform_redo(win)
        
    def on_undo_shortcut(self, win, *args):
        self.perform_undo(win)
        return True
        
    def on_redo_shortcut(self, win, *args):
        self.perform_redo(win)
        return True
        
    def perform_undo(self, win):
        try:
            win.webview.evaluate_javascript(
                "JSON.stringify(performUndo());",
                -1, None, None, None,
                lambda webview, result, data: self._on_undo_redo_performed(win, webview, result, data),
                "undo"
            )
            win.statusbar.set_text("Undo performed")
        except Exception as e:
            print(f"Error during undo: {e}")
            win.statusbar.set_text("Undo failed")
        
    def perform_redo(self, win):
        try:
            win.webview.evaluate_javascript(
                "JSON.stringify(performRedo());",
                -1, None, None, None,
                lambda webview, result, data: self._on_undo_redo_performed(win, webview, result, data),
                "redo"
            )
            win.statusbar.set_text("Redo performed")
        except Exception as e:
            print(f"Error during redo: {e}")
            win.statusbar.set_text("Redo failed")

    def _on_undo_redo_performed(self, win, webview, result, operation):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                result_str = (js_result.get_js_value().to_string() if hasattr(js_result, 'get_js_value') else
                              js_result.to_string() if hasattr(js_result, 'to_string') else str(js_result))
                import json
                result_data = json.loads(result_str)
                success = result_data.get('success', False)
                is_initial_state = result_data.get('isInitialState', False)

                if success:
                    win.statusbar.set_text(f"{operation.capitalize()} performed")
                    if operation == "undo" and is_initial_state:
                        win.modified = False  # Reset when fully undone
                    else:
                        win.modified = True  # Set for redo or partial undo
                    self.update_window_title(win)
                    self.update_undo_redo_state(win)
                else:
                    win.statusbar.set_text(f"No more {operation} actions available")
        except Exception as e:
            print(f"Error during {operation}: {e}")
            win.statusbar.set_text(f"{operation.capitalize()} failed")
            
    # Event handlers
    def on_new_clicked(self, win, button):
        # Create a new window with a blank document
        new_win = self.create_window()
        new_win.present()
        self.update_window_menu()
        new_win.statusbar.set_text("New document created")
    
    def on_open_clicked(self, win, button):
        """Show open file dialog and decide whether to open in current or new window"""
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Document")
        
        filter_html = Gtk.FileFilter()
        filter_html.set_name("HTML files")
        filter_html.add_pattern("*.html")
        filter_html.add_pattern("*.htm")
        
        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("Text files")
        filter_txt.add_pattern("*.txt")
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        
        filter_list = Gio.ListStore.new(Gtk.FileFilter)
        filter_list.append(filter_html)
        filter_list.append(filter_txt)
        filter_list.append(filter_all)
        
        dialog.set_filters(filter_list)
        
        # If no changes made and no file is open, open in current window, otherwise open in new window
        if win.modified or win.current_file:
            dialog.open(win, None, lambda dialog, result: self.on_open_new_window_response(win, dialog, result))
        else:
            dialog.open(win, None, lambda dialog, result: self.on_open_current_window_response(win, dialog, result))

    def on_open_new_window_response(self, win, dialog, result):
        """Handle open file dialog response to open in a new window"""
        try:
            file = dialog.open_finish(result)
            if file:
                filepath = file.get_path()
                # Create a new window for the file
                new_win = self.create_window()
                self.load_file(new_win, filepath)
                new_win.present()
                self.update_window_menu()
        except GLib.Error as e:
            if e.domain != 'gtk-dialog-error-quark' or e.code != 2:  # Ignore cancel
                self.show_error_dialog(f"Error opening file: {e}")

    def on_open_current_window_response(self, win, dialog, result):
        """Handle open file dialog response to open in current window"""
        try:
            file = dialog.open_finish(result)
            if file:
                filepath = file.get_path()
                self.load_file(win, filepath)
                win.statusbar.set_text(f"Opened {os.path.basename(filepath)}")
        except GLib.Error as e:
            if e.domain != 'gtk-dialog-error-quark' or e.code != 2:  # Ignore cancel
                self.show_error_dialog(f"Error opening file: {e}")

    def load_file(self, win, filepath):
        """Load file content into editor"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            is_html = content.strip().startswith("<") and (
                "<html" in content.lower() or 
                "<body" in content.lower() or 
                "<div" in content.lower()
            )
            if is_html:
                body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
                if body_match:
                    content = body_match.group(1).strip()
            else:
                content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                content = content.replace("\n", "<br>")
            
            # Escape for JavaScript
            content = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            js_code = f'setContent("{content}");'
            
            # Check WebView load status and execute JS accordingly
            def execute_when_ready():
                # Get the current load status
                load_status = win.webview.get_estimated_load_progress()
                
                if load_status == 1.0:  # Fully loaded
                    # Execute directly
                    self.execute_js(win, js_code)
                    return False  # Stop the timeout
                else:
                    # Set up a handler for when loading finishes
                    def on_load_changed(webview, event):
                        if event == WebKit.LoadEvent.FINISHED:
                            self.execute_js(win, js_code)
                            webview.disconnect_by_func(on_load_changed)
                    
                    win.webview.connect("load-changed", on_load_changed)
                    return False  # Stop the timeout
            
            # Use GLib timeout to ensure we're not in the middle of another operation
            GLib.timeout_add(50, execute_when_ready)
            
            # Update file information
            win.current_file = Gio.File.new_for_path(filepath)
            win.modified = False
            self.update_window_title(win)
            win.statusbar.set_text(f"Opened {os.path.basename(filepath)}")
        except Exception as e:
            print(f"Error loading file: {str(e)}")
            win.statusbar.set_text(f"Error loading file: {str(e)}")
            # Call show_error_dialog if it exists
            self.show_error_dialog(f"Error loading file: {e}")
            
    def get_menu_title(self, win):
        if win.current_file:
            # Get the path as a string
            if hasattr(win.current_file, 'get_path'):
                path = win.current_file.get_path()
            else:
                path = win.current_file
            # Extract filename without extension and show modified marker
            filename = os.path.splitext(os.path.basename(path))[0]
            return f"{filename}{'*' if win.modified else ''}"
        else:
            return f"Untitled{'*' if win.modified else ''}"

    def update_window_title(self, win):
        """Update window title to show document name (without extension) and modified status"""
        if win.current_file:
            # Get the path as a string
            if hasattr(win.current_file, 'get_path'):
                path = win.current_file.get_path()
            else:
                path = win.current_file
            # Extract filename without extension
            filename = os.path.splitext(os.path.basename(path))[0]
            title = f"{filename} - HTML Editor{' *' if win.modified else ''}"
        else:
            title = f"Untitled - HTML Editor{' *' if win.modified else ''}"
        win.set_title(title)
    
    def on_save_clicked(self, win, button):
        dialog = Gtk.FileDialog()
        dialog.set_title("Save HTML File")
        
        filter = Gtk.FileFilter()
        filter.set_name("HTML files")
        filter.add_pattern("*.html")
        filter.add_pattern("*.htm")
        
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter)
        
        dialog.set_filters(filters)
        dialog.save(win, None, lambda dialog, result: self._on_save_response(win, dialog, result))
    
    def _on_save_response(self, win, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                win.current_file = file  # Already a Gio.File
                win.webview.evaluate_javascript(
                    "document.getElementById('editor').innerHTML;",
                    -1, None, None, None,
                    lambda webview, result, file: self._on_get_html_content(win, webview, result, file), 
                    file
                )
        except GLib.Error as error:
            print(f"Error saving file: {error.message}")
    
    def _on_snapshot_ready(self, win, webview, result, file):
        try:
            # Get just the editor content using JavaScript instead of the whole document
            win.webview.evaluate_javascript(
                "document.getElementById('editor').innerHTML;",
                -1, None, None,
                None,
                lambda webview, result, file: self._on_get_html_content(win, webview, result, file), 
                file
            )
        except Exception as e:
            print(f"Error preparing content: {e}")
            
    def save_html_content(self, win, editor_content, file, callback):
        try:
            if editor_content.strip() == "" or editor_content == "<br>":
                editor_content = "<div><br></div>"
            elif not (editor_content.startswith('<div') and editor_content.endswith('</div>')):
                editor_content = f"<div>{editor_content.strip()}</div>"
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>HTML Document</title>
    <meta charset="utf-8">
</head>
<body>
{editor_content}
</body>
</html>
"""
            file_bytes = html_content.encode('utf-8')
            file.replace_contents_async(file_bytes, None, False, Gio.FileCreateFlags.NONE, None, callback)
        except Exception as e:
            print(f"Error saving content: {e}")

    def _on_get_html_content(self, win, webview, result, file):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                editor_content = (js_result.get_js_value().to_string() if hasattr(js_result, 'get_js_value') else
                                js_result.to_string() if hasattr(js_result, 'to_string') else str(js_result))
                self.save_html_content(win, editor_content, file, 
                                      lambda file, result: self._on_file_saved(win, file, result))
            else:
                print("Failed to get HTML content from webview")
        except Exception as e:
            print(f"Error getting HTML content: {e}")
    
    def _on_file_saved(self, win, file, result):
        try:
            success, _ = file.replace_contents_finish(result)
            if success:
                win.current_file = file  # Ensure consistency by updating win.current_file
                win.statusbar.set_text(f"Saved: {file.get_path()}")
                win.modified = False  # Reset modified flag after save
                self.update_window_title(win)
            else:
                print("File save was not successful")
        except GLib.Error as error:
            print(f"Error writing file: {error.message}")
            
    def on_bold_clicked(self, win, button):
        self.execute_js(win, "document.execCommand('bold', false, null);")
    
    def on_italic_clicked(self, win, button):
        self.execute_js(win, "document.execCommand('italic', false, null);")
    
    def on_underline_clicked(self, win, button):
        self.execute_js(win, "document.execCommand('underline', false, null);")
    
    # Window Close Request
    def on_window_close_request(self, win, *args):
        """Handle window close request with save confirmation if needed"""
        if win.modified:
            # Show confirmation dialog
            self.show_save_confirmation_dialog(win, lambda response: self._handle_close_confirmation(win, response))
            # Return True to stop the default close handler
            return True
        else:
            # No unsaved changes, proceed with closing
            self.remove_window(win)
            return False

    def _handle_close_confirmation(self, win, response):
        """Handle the response from the save confirmation dialog"""
        if response == "save":
            # Save and then close
            if win.current_file:
                # We have a file path, save directly
                win.webview.evaluate_javascript(
                    "document.getElementById('editor').innerHTML;",
                    -1, None, None, None,
                    lambda webview, result, data: self._on_save_before_close(win, webview, result, data),
                    None
                )
            else:
                # No file path, show save dialog
                dialog = Gtk.FileDialog()
                dialog.set_title("Save Before Closing")
                
                filter = Gtk.FileFilter()
                filter.set_name("HTML files")
                filter.add_pattern("*.html")
                filter.add_pattern("*.htm")
                
                filters = Gio.ListStore.new(Gtk.FileFilter)
                filters.append(filter)
                
                dialog.set_filters(filters)
                dialog.save(win, None, lambda dialog, result: self._on_save_response_before_close(win, dialog, result))
        elif response == "discard":
            # Mark as unmodified before closing
            win.modified = False
            
            # Close without saving
            self.remove_window(win)
            win.close()
        # If response is "cancel", do nothing and keep the window open

    def _on_save_before_close(self, win, webview, result, data):
        """Save the content and then close the window"""
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                editor_content = (js_result.get_js_value().to_string() if hasattr(js_result, 'get_js_value') else
                               js_result.to_string() if hasattr(js_result, 'to_string') else str(js_result))
                
                # Define a callback that will close the window after saving
                def after_save(file, result):
                    try:
                        success, _ = file.replace_contents_finish(result)
                        if success:
                            win.modified = False  # Mark as unmodified
                            self.update_window_title(win)
                            # Now close the window
                            self.remove_window(win)
                            win.close()
                    except Exception as e:
                        print(f"Error during save before close: {e}")
                        # Close anyway in case of error
                        self.remove_window(win)
                        win.close()
                
                self.save_html_content(win, editor_content, win.current_file, after_save)
        except Exception as e:
            print(f"Error getting HTML content: {e}")
            # Close anyway in case of error
            self.remove_window(win)
            win.close()

    def _on_saved_close_window(self, file, result):
        """After saving, close the window"""
        try:
            success, _ = file.replace_contents_finish(result)
            # Find the window with this file
            for win in self.windows:
                if win.current_file and win.current_file.equal(file):
                    self.remove_window(win)
                    win.close()
                    break
        except Exception as e:
            print(f"Error saving before close: {e}")

    def _on_save_response_before_close(self, win, dialog, result):
        """Handle save dialog response before closing"""
        try:
            file = dialog.save_finish(result)
            if file:
                win.current_file = file
                win.webview.evaluate_javascript(
                    "document.getElementById('editor').innerHTML;",
                    -1, None, None, None,
                    lambda webview, result, data: self._on_save_before_close(win, webview, result, data),
                    None
                )
            else:
                # User cancelled save dialog, keep window open
                pass
        except GLib.Error as error:
            if error.domain != 'gtk-dialog-error-quark' or error.code != 2:  # Ignore cancel
                print(f"Error saving file: {error.message}")
            # Keep window open

    def show_save_confirmation_dialog(self, win, callback):
        """Show dialog asking if user wants to save changes before closing"""
        dialog = Adw.Dialog.new()
        dialog.set_title("Unsaved Changes")
        dialog.set_content_width(400)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_top(24)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        
        # Warning icon
        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warning_icon.set_pixel_size(48)
        warning_icon.set_margin_bottom(12)
        content_box.append(warning_icon)
        
        # Message
        document_name = "Untitled"
        if win.current_file:
            path = win.current_file.get_path() if hasattr(win.current_file, 'get_path') else win.current_file
            document_name = os.path.splitext(os.path.basename(path))[0]
            
        message_label = Gtk.Label()
        message_label.set_markup(f"<b>Save changes to \"{document_name}\" before closing?</b>")
        message_label.set_wrap(True)
        message_label.set_max_width_chars(40)
        content_box.append(message_label)
        
        description_label = Gtk.Label(label="If you don't save, your changes will be lost.")
        description_label.set_wrap(True)
        description_label.set_max_width_chars(40)
        content_box.append(description_label)
        
        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        
        # Discard button
        discard_button = Gtk.Button(label="Discard")
        discard_button.add_css_class("destructive-action")
        discard_button.connect("clicked", lambda btn: [dialog.close(), callback("discard")])
        button_box.append(discard_button)
        
        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda btn: [dialog.close(), callback("cancel")])
        button_box.append(cancel_button)
        
        # Save button
        save_button = Gtk.Button(label="Save")
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", lambda btn: [dialog.close(), callback("save")])
        button_box.append(save_button)
        
        content_box.append(button_box)
        
        # Present the dialog
        dialog.set_child(content_box)
        dialog.present(win)
        #/ Window Close Request

    def create_actions(self):
        """Set up application actions"""
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.add_action(quit_action)
        
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        self.add_action(about_action)
        
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self.on_preferences)
        self.add_action(preferences_action)
        
        # New window action
        new_window_action = Gio.SimpleAction.new("new-window", None)
        new_window_action.connect("activate", self.on_new_window)
        self.add_action(new_window_action)
        
        # Close other windows action
        close_other_windows_action = Gio.SimpleAction.new("close-other-windows", None)
        close_other_windows_action.connect("activate", self.on_close_other_windows)
        self.add_action(close_other_windows_action)

        # Window switching action
        switch_window_action = Gio.SimpleAction.new(
            "switch-window", 
            GLib.VariantType.new("i")
        )
        switch_window_action.connect("activate", self.on_switch_window)
        self.add_action(switch_window_action)

    def create_window_menu(self):
        """Create a fresh window menu"""
        menu = Gio.Menu()
        actions_section = Gio.Menu()
        window_section = Gio.Menu()
        
        # Add "Close Other Windows" option at the top if there's more than one window
        if len(self.windows) > 1:
            actions_section.append("Close Other Windows", "app.close-other-windows")
            menu.append_section("Actions", actions_section)
        
        # Add all windows to the menu
        for i, win in enumerate(self.windows):
            title = self.get_menu_title(win)
            action_string = f"app.switch-window({i})"
            window_section.append(title, action_string)
        
        menu.append_section("Windows", window_section)
        return menu

    def update_window_menu(self):
        """Force update all window menu buttons"""
        fresh_menu = self.create_window_menu()
        
        # Should we show the window menu button?
        show_button = len(self.windows) > 1
        
        # Create a set of windows that still need a button
        windows_needing_buttons = set(self.windows)
        
        # First, update existing buttons
        buttons_to_remove = []
        for window_id, button in self.window_buttons.items():
            # Check if the window still exists
            window_exists = False
            for win in self.windows:
                if id(win) == window_id:
                    window_exists = True
                    windows_needing_buttons.remove(win)
                    break
            
            if window_exists:
                # Update existing button with fresh menu and visibility
                button.set_menu_model(fresh_menu)
                button.set_visible(show_button)
            else:
                # Window no longer exists, mark button for removal
                buttons_to_remove.append(window_id)
        
        # Remove buttons for closed windows
        for window_id in buttons_to_remove:
            del self.window_buttons[window_id]
        
        # Add buttons for new windows
        for win in windows_needing_buttons:
            self.add_window_menu_button(win, fresh_menu)
    
    def add_window_menu_button(self, win, menu_model=None):
        """Add a window menu button to a window or update an existing one"""
        header = win.main_box.get_first_child()
        if not header or not isinstance(header, Adw.HeaderBar):
            return
        
        # Look for existing window menu button
        child = header.get_first_child()
        window_button = None
        while child:
            if (isinstance(child, Gtk.MenuButton) and 
                child.get_icon_name() == "window-new-symbolic"):
                window_button = child
                break
            child = child.get_next_sibling()
        
        # Create a new menu model if not provided
        if menu_model is None:
            menu_model = self.create_window_menu()
        
        # Only show the window menu button if there's more than one window
        show_button = len(self.windows) > 1
        
        if window_button:
            # Update existing button's menu and visibility
            window_button.set_menu_model(menu_model)
            window_button.set_visible(show_button)
        elif show_button:
            # Only create a new button if we need to show it
            window_button = Gtk.MenuButton()
            window_button.set_icon_name("window-new-symbolic")
            window_button.set_tooltip_text("Window List")
            window_button.set_menu_model(menu_model)
            window_button.set_visible(show_button)
            header.pack_end(window_button)
            
            # Store reference to the button
            self.window_buttons[id(win)] = window_button
        
        # Make sure we keep the reference if button exists
        if window_button:
            self.window_buttons[id(win)] = window_button
            
    def setup_header_bar(self, win):
        """Initialize the header bar for a window"""
        header = win.main_box.get_first_child()
        if not header:
            self.create_header_bar(win)
        
        # Add window menu button (uses cached menu if available)
        self.add_window_menu_button(win)

    def on_switch_window(self, action, param):
        """Handle window switching action"""
        index = param.get_int32()
        if 0 <= index < len(self.windows):
            self.windows[index].present()
            
    def on_new_window(self, action, param):
        """Create a new empty window"""
        win = self.create_window()
        win.present()
        # Update all window menus
        self.update_window_menu()

    def on_close_other_windows(self, action, param):
        """Close all windows except the active one with confirmation"""
        if len(self.windows) <= 1:
            return
            
        # Find the active window (the one that was most recently focused)
        active_window = None
        for win in self.windows:
            if win.is_active():
                active_window = win
                break
                
        # If no active window found, use the first one
        if not active_window and self.windows:
            active_window = self.windows[0]
            
        if not active_window:
            return
            
        # The number of windows that will be closed
        windows_to_close_count = len(self.windows) - 1
        
        # Create confirmation dialog using non-deprecated methods
        dialog = Adw.Dialog.new()
        dialog.set_title(f"Close {windows_to_close_count} Other Window{'s' if windows_to_close_count > 1 else ''}?")
        dialog.set_content_width(350)
        
        # Create dialog content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_top(24)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        
        # Message label
        message_label = Gtk.Label()
        message_label.set_text(f"Are you sure you want to close {windows_to_close_count} other window{'s' if windows_to_close_count > 1 else ''}?")
        message_label.set_wrap(True)
        message_label.set_max_width_chars(40)
        content_box.append(message_label)
        
        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        
        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda btn: dialog.close())
        button_box.append(cancel_button)
        
        # Close button (destructive)
        close_button = Gtk.Button(label="Close Windows")
        close_button.add_css_class("destructive-action")
        close_button.connect("clicked", lambda btn: self._on_close_others_response(dialog, active_window))
        button_box.append(close_button)
        
        content_box.append(button_box)
        
        # Set the dialog content and present
        dialog.set_child(content_box)
        dialog.present(active_window)

    def _on_close_others_response(self, dialog, active_window):
        """Handle the close action from the dialog"""
        # Close dialog
        dialog.close()
        
        # Get windows to close (all except active_window)
        windows_to_close = [win for win in self.windows if win != active_window]
        
        # Close each window
        for win in windows_to_close[:]:  # Use a copy of the list since we'll modify it
            win.close()
            
        # Make sure active window is still presented
        if active_window in self.windows:
            active_window.present()
            
        # Update window menu
        self.update_window_menu()

    def remove_window(self, window):
        """Properly remove a window and update menus"""
        if window in self.windows:
            # Remove window from list
            self.windows.remove(window)
            # Clean up button reference
            if id(window) in self.window_buttons:
                del self.window_buttons[id(window)]
            # Update menus in all remaining windows
            self.update_window_menu()
            
            # Focus the next window if available
            if self.windows:
                self.windows[0].present()
    # On Quit
    def on_quit(self, action, param):
        """Quit the application with save confirmation if needed"""
        # Check if any window has unsaved changes
        windows_with_changes = [win for win in self.windows if win.modified]
        
        if windows_with_changes:
            # Prioritize the active window if it has unsaved changes
            active_window = None
            for win in self.windows:
                if win.is_active() and win.modified:
                    active_window = win
                    break
                    
            # If no active window with changes, use the first window with changes
            if not active_window and windows_with_changes:
                active_window = windows_with_changes[0]
            
            # Move the active window to the front of the list
            if active_window in windows_with_changes:
                windows_with_changes.remove(active_window)
                windows_with_changes.insert(0, active_window)
            
            # Start handling windows one by one
            self._handle_quit_with_unsaved_changes(windows_with_changes)
        else:
            # No unsaved changes, quit directly
            self.quit()

    def _handle_quit_with_unsaved_changes(self, windows_with_changes):
        """Handle unsaved changes during quit, one window at a time"""
        if not windows_with_changes:
            # All windows handled, check if we should quit
            if not self.windows:
                self.quit()
            return
            
        win = windows_with_changes[0]
        # Make sure the window is presented to the user
        win.present()
        # Show the confirmation dialog
        self.show_save_confirmation_dialog(win, lambda response: self._handle_quit_confirmation(
            response, windows_with_changes, win))

    def _handle_quit_confirmation(self, response, windows_with_changes, win):
        """Handle the response from the save confirmation dialog during quit"""
        if response == "save":
            # Save and then close this window
            if win.current_file:
                # We have a file path, save directly
                win.webview.evaluate_javascript(
                    "document.getElementById('editor').innerHTML;",
                    -1, None, None, None,
                    lambda webview, result, data: self._on_save_continue_quit(
                        win, webview, result, windows_with_changes),
                    None
                )
            else:
                # No file path, show save dialog
                dialog = Gtk.FileDialog()
                dialog.set_title("Save Before Quitting")
                
                filter = Gtk.FileFilter()
                filter.set_name("HTML files")
                filter.add_pattern("*.html")
                filter.add_pattern("*.htm")
                
                filters = Gio.ListStore.new(Gtk.FileFilter)
                filters.append(filter)
                
                dialog.set_filters(filters)
                dialog.save(win, None, lambda dialog, result: self._on_save_response_during_quit(
                    win, dialog, result, windows_with_changes))
        elif response == "discard":
            # Explicitly mark as unmodified before closing
            win.modified = False
            
            # Close this window without saving and continue with the next
            self.remove_window(win)
            win.close()
            
            # Continue with remaining windows
            remaining_windows = windows_with_changes[1:]
            if remaining_windows:
                GLib.idle_add(lambda: self._handle_quit_with_unsaved_changes(remaining_windows))
            elif not self.windows:
                # If all windows are closed, quit the application
                self.quit()
        elif response == "cancel":
            # Cancel the entire quit operation
            # Continue with other windows that might be open but not modified
            pass

    def _on_save_continue_quit(self, win, webview, result, windows_with_changes):
        """Save the content, close this window, and continue with the quit process"""
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                editor_content = (js_result.get_js_value().to_string() if hasattr(js_result, 'get_js_value') else
                               js_result.to_string() if hasattr(js_result, 'to_string') else str(js_result))
                
                # Define a callback for after saving
                def after_save(file, result):
                    try:
                        success, _ = file.replace_contents_finish(result)
                        if success:
                            win.modified = False  # Mark as unmodified
                            self.update_window_title(win)
                        
                        # Close this window
                        self.remove_window(win)
                        win.close()
                        
                        # Continue with remaining windows
                        remaining_windows = windows_with_changes[1:]
                        if remaining_windows:
                            GLib.idle_add(lambda: self._handle_quit_with_unsaved_changes(remaining_windows))
                        elif not self.windows:
                            # If all windows are closed, quit the application
                            self.quit()
                    except Exception as e:
                        print(f"Error saving during quit: {e}")
                        # Close anyway and continue
                        self.remove_window(win)
                        win.close()
                        
                        # Continue with remaining windows
                        remaining_windows = windows_with_changes[1:]
                        if remaining_windows:
                            GLib.idle_add(lambda: self._handle_quit_with_unsaved_changes(remaining_windows))
                        elif not self.windows:
                            # If all windows are closed, quit the application
                            self.quit()
                
                # Save with our callback
                self.save_html_content(win, editor_content, win.current_file, after_save)
        except Exception as e:
            print(f"Error getting HTML content during quit: {e}")
            # Close anyway and continue
            self.remove_window(win)
            win.close()
            
            # Continue with remaining windows
            remaining_windows = windows_with_changes[1:]
            if remaining_windows:
                GLib.idle_add(lambda: self._handle_quit_with_unsaved_changes(remaining_windows))
            elif not self.windows:
                # If all windows are closed, quit the application
                self.quit()

    def _on_save_response_during_quit(self, win, dialog, result, windows_with_changes):
        """Handle save dialog response during quit"""
        try:
            file = dialog.save_finish(result)
            if file:
                win.current_file = file
                win.webview.evaluate_javascript(
                    "document.getElementById('editor').innerHTML;",
                    -1, None, None, None,
                    lambda webview, result, data: self._on_save_continue_quit(
                        win, webview, result, windows_with_changes),
                    None
                )
            else:
                # User cancelled save dialog, cancel quit for this window
                # but continue with other windows that might need attention
                remaining_windows = windows_with_changes[1:]
                if remaining_windows:
                    GLib.idle_add(lambda: self._handle_quit_with_unsaved_changes(remaining_windows))
        except GLib.Error as error:
            if error.domain != 'gtk-dialog-error-quark' or error.code != 2:  # Ignore cancel
                print(f"Error saving file during quit: {error.message}")
            # Continue with other windows
            remaining_windows = windows_with_changes[1:]
            if remaining_windows:
                GLib.idle_add(lambda: self._handle_quit_with_unsaved_changes(remaining_windows))
        #/On Quit
    def on_about(self, action, param):
        """Show about dialog"""
        parent_window = self.windows[0] if self.windows else None
        about = Adw.AboutWindow(
            transient_for=parent_window,
            application_name="HTML Editor",
            application_icon="text-editor",
            developer_name="Developer",
            version="1.0",
            developers=["Your Name"],
            copyright="© 2025"
        )
        about.present()
    
    def on_preferences(self, action, param):
        """Show preferences dialog"""
        if not self.windows:
            return
            
        # Find the active window instead of just using the first window
        active_win = None
        for win in self.windows:
            if win.is_active():
                active_win = win
                break
        
        # If no active window found, use the first one as fallback
        if not active_win:
            active_win = self.windows[0]
            
        # Create dialog
        dialog = Adw.Dialog.new()
        dialog.set_title("Preferences")
        dialog.set_content_width(450)
        
        # Create content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_top(24)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        
        # Add settings UI
        header = Gtk.Label()
        header.set_markup("<b>Editor Settings</b>")
        header.set_halign(Gtk.Align.START)
        header.set_margin_bottom(12)
        content_box.append(header)
        
        # Auto-save toggle
        auto_save_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        auto_save_box.set_margin_start(12)
        
        auto_save_label = Gtk.Label(label="Auto Save:")
        auto_save_label.set_halign(Gtk.Align.START)
        auto_save_label.set_hexpand(True)
        
        auto_save_switch = Gtk.Switch()
        auto_save_switch.set_active(active_win.auto_save_enabled)
        auto_save_switch.set_valign(Gtk.Align.CENTER)
        
        auto_save_box.append(auto_save_label)
        auto_save_box.append(auto_save_switch)
        content_box.append(auto_save_box)
        
        # Interval settings
        interval_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        interval_box.set_margin_start(12)
        interval_box.set_margin_top(12)
        
        interval_label = Gtk.Label(label="Auto-save Interval (seconds):")
        interval_label.set_halign(Gtk.Align.START)
        interval_label.set_hexpand(True)
        
        adjustment = Gtk.Adjustment(
            value=active_win.auto_save_interval,
            lower=10,
            upper=600,
            step_increment=10
        )
        
        spinner = Gtk.SpinButton()
        spinner.set_adjustment(adjustment)
        spinner.set_valign(Gtk.Align.CENTER)
        
        interval_box.append(interval_label)
        interval_box.append(spinner)
        content_box.append(interval_box)
        
        # Dialog buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(24)
        
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda btn: dialog.close())
        button_box.append(cancel_button)
        
        ok_button = Gtk.Button(label="OK")
        ok_button.add_css_class("suggested-action")
        ok_button.connect("clicked", lambda btn: self.save_preferences(
            dialog, active_win, auto_save_switch.get_active(), spinner.get_value_as_int()
        ))
        button_box.append(ok_button)
        
        content_box.append(button_box)
        
        # Set dialog content and show
        dialog.set_child(content_box)
        dialog.present(active_win)

    def save_preferences(self, dialog, win, auto_save_enabled, auto_save_interval):
        """Save preferences settings"""
        previous_auto_save = win.auto_save_enabled
        
        win.auto_save_enabled = auto_save_enabled
        win.auto_save_interval = auto_save_interval
        
        # Update auto-save timer if needed
        if auto_save_enabled != previous_auto_save:
            if auto_save_enabled:
                self.start_auto_save_timer(win)
                win.statusbar.set_text("Auto-save enabled")
            else:
                self.stop_auto_save_timer(win)
                win.statusbar.set_text("Auto-save disabled")
        elif auto_save_enabled:
            # Restart timer with new interval
            self.stop_auto_save_timer(win)
            self.start_auto_save_timer(win)
            win.statusbar.set_text(f"Auto-save interval set to {auto_save_interval} seconds")
        
        dialog.close()

    def show_error_dialog(self, message):
        """Show error message dialog"""
        if not self.windows:
            print(f"Error: {message}")
            return
            
        # Find the active window
        active_window = None
        for win in self.windows:
            if win.is_active():
                active_window = win
                break
                
        # Fallback to first window if none is active
        if not active_window:
            active_window = self.windows[0]
        
        dialog = Adw.Dialog.new()
        dialog.set_title("Error")
        dialog.set_content_width(350)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_top(24)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        
        error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        error_icon.set_pixel_size(48)
        error_icon.set_margin_bottom(12)
        content_box.append(error_icon)
        
        message_label = Gtk.Label(label=message)
        message_label.set_wrap(True)
        message_label.set_max_width_chars(40)
        content_box.append(message_label)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(12)
        
        ok_button = Gtk.Button(label="OK")
        ok_button.add_css_class("suggested-action")
        ok_button.connect("clicked", lambda btn: dialog.close())
        button_box.append(ok_button)
        
        content_box.append(button_box)
        
        dialog.set_child(content_box)
        dialog.present(active_window)

##################################
# Here are all the methods that need to be updated or added:

    def create_window(self):
        """Create a new window with all initialization (former HTMLEditorWindow.__init__)"""
        win = Adw.ApplicationWindow(application=self)
        
        # Set window properties
        win.modified = False
        win.auto_save_enabled = False
        win.auto_save_interval = 60
        win.current_file = None
        win.auto_save_source_id = None
        win.top_toolbar_visible = True  # Track toolbar visibility state
        
        win.set_default_size(900, 700)
        win.set_title("Untitled - HTML Editor")
        
        win.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.main_box.set_vexpand(True)  # Ensure main_box expands vertically
        win.main_box.set_hexpand(True)
        
        # Create header bar and add it to main_box
        self.create_header_bar(win)
        
        # Create top toolbar (below header)
        win.top_toolbar = self.create_top_toolbar(win)
        # Add toolbar right after the header
        win.main_box.append(win.top_toolbar)
        
        # Create content area for the webview and statusbar
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Create and configure webview
        win.webview = WebKit.WebView()
        win.webview.set_vexpand(True)
        win.webview.set_hexpand(True) 
        win.webview.load_html(self.get_editor_html(), None)
        settings = win.webview.get_settings()
        try:
            settings.set_enable_developer_extras(True)
        except:
            pass
        
        try:
            user_content_manager = win.webview.get_user_content_manager()
            user_content_manager.register_script_message_handler("contentChanged")
            user_content_manager.connect("script-message-received::contentChanged", 
                                        lambda mgr, res: self.on_content_changed(win, mgr, res))
        except:
            print("Warning: Could not set up JavaScript message handlers")
            
        win.webview.load_html(self.get_initial_html(), None)
        
        win.statusbar = Gtk.Label(label="Ready")
        win.statusbar.set_halign(Gtk.Align.START)
        win.statusbar.set_margin_start(10)
        win.statusbar.set_margin_end(10)
        win.statusbar.set_margin_top(5)
        win.statusbar.set_margin_bottom(5)
        
        # Add webview and statusbar to content box
        content_box.append(win.webview)
        #content_box.append(win.statusbar)
        
        # Add content box to main box
        win.main_box.append(content_box)
        
        # Set the content of the window
        win.set_content(win.main_box)
        
        self.setup_toolbar_animation(win)
        self.setup_keyboard_shortcuts(win)
        
        win.connect("close-request", self.on_window_close_request)
        
        # Add to windows list
        self.windows.append(win)
        self.setup_header_bar(win)
        
        return win

    def create_top_toolbar(self, win):
        """Create the formatting toolbar for a window"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(10)
        toolbar.set_margin_end(10)
        toolbar.set_margin_top(5)
        toolbar.set_margin_bottom(5)
        
        # Add some HTML editing buttons
        bold_button = Gtk.Button(icon_name="format-text-bold-symbolic")
        bold_button.set_tooltip_text("Bold")
        bold_button.connect("clicked", lambda btn: self.on_bold_clicked(win, btn))
        
        italic_button = Gtk.Button(icon_name="format-text-italic-symbolic")
        italic_button.set_tooltip_text("Italic")
        italic_button.connect("clicked", lambda btn: self.on_italic_clicked(win, btn))
        
        underline_button = Gtk.Button(icon_name="format-text-underline-symbolic")
        underline_button.set_tooltip_text("Underline")
        underline_button.connect("clicked", lambda btn: self.on_underline_clicked(win, btn))
        
        # Add a spacer (expanding box)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        
        # Add a hide button
        hide_button = Gtk.Button(label="Hide")
        hide_button.set_tooltip_text("Hide formatting toolbar (Ctrl+Shift+T)")
        hide_button.connect("clicked", lambda btn: self.toggle_top_toolbar(win))
        
        # Add all widgets to the toolbar
        toolbar.append(bold_button)
        toolbar.append(italic_button)
        toolbar.append(underline_button)
        toolbar.append(spacer)
        toolbar.append(hide_button)
        
        return toolbar

    def setup_keyboard_shortcuts(self, win):
        """Setup keyboard shortcuts for the window"""
        # Create a shortcut controller
        controller = Gtk.ShortcutController()
        
        # Create Ctrl+T shortcut for toggling the overlay toolbar
        trigger = Gtk.ShortcutTrigger.parse_string("<Control>t")
        action = Gtk.CallbackAction.new(lambda *args: self.toggle_toolbar(win, *args))
        shortcut = Gtk.Shortcut.new(trigger, action)
        controller.add_shortcut(shortcut)
        
        # Create Ctrl+Shift+T shortcut for toggling the top toolbar
        trigger_top = Gtk.ShortcutTrigger.parse_string("<Control><Shift>t")
        action_top = Gtk.CallbackAction.new(lambda *args: self.toggle_top_toolbar(win, *args))
        shortcut_top = Gtk.Shortcut.new(trigger_top, action_top)
        controller.add_shortcut(shortcut_top)
        
        # Create Ctrl+Z shortcut for undo
        trigger_undo = Gtk.ShortcutTrigger.parse_string("<Control>z")
        action_undo = Gtk.CallbackAction.new(lambda *args: self.on_undo_shortcut(win, *args))
        shortcut_undo = Gtk.Shortcut.new(trigger_undo, action_undo)
        controller.add_shortcut(shortcut_undo)
        
        # Create Ctrl+Y shortcut for redo
        trigger_redo = Gtk.ShortcutTrigger.parse_string("<Control>y")
        action_redo = Gtk.CallbackAction.new(lambda *args: self.on_redo_shortcut(win, *args))
        shortcut_redo = Gtk.Shortcut.new(trigger_redo, action_redo)
        controller.add_shortcut(shortcut_redo)
        
        # Create Ctrl+W shortcut for closing current window
        trigger_close = Gtk.ShortcutTrigger.parse_string("<Control>w")
        action_close = Gtk.CallbackAction.new(lambda *args: self.on_close_shortcut(win, *args))
        shortcut_close = Gtk.Shortcut.new(trigger_close, action_close)
        controller.add_shortcut(shortcut_close)
        
        # Create Ctrl+Shift+W shortcut for closing other windows
        trigger_close_others = Gtk.ShortcutTrigger.parse_string("<Control><Shift>w")
        action_close_others = Gtk.CallbackAction.new(lambda *args: self.on_close_others_shortcut(win, *args))
        shortcut_close_others = Gtk.Shortcut.new(trigger_close_others, action_close_others)
        controller.add_shortcut(shortcut_close_others)
        
        # Add controller to the window (not the webview)
        win.add_controller(controller)
        
        # Make it capture events at the capture phase
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        
        # Make shortcut work regardless of who has focus
        controller.set_scope(Gtk.ShortcutScope.GLOBAL)

    def toggle_top_toolbar(self, win, *args):
        """Toggle the visibility of the top toolbar below the header bar"""
        if hasattr(win, 'top_toolbar'):
            win.top_toolbar_visible = not win.top_toolbar_visible
            win.top_toolbar.set_visible(win.top_toolbar_visible)
            win.statusbar.set_text(f"Formatting toolbar {'shown' if win.top_toolbar_visible else 'hidden'}")
            print(f"Top toolbar toggled: {'visible' if win.top_toolbar_visible else 'hidden'}")
            return True
        else:
            print("Window does not have top_toolbar attribute")
        return False
##################
    def create_window(self):
        """Create a new window with all initialization (former HTMLEditorWindow.__init__)"""
        win = Adw.ApplicationWindow(application=self)
        
        # Set window properties
        win.modified = False
        win.auto_save_enabled = False
        win.auto_save_interval = 60
        win.current_file = None
        win.auto_save_source_id = None
        win.top_toolbar_visible = True  # Track toolbar visibility state
        
        win.set_default_size(900, 700)
        win.set_title("Untitled - HTML Editor")
        
        win.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.main_box.set_vexpand(True)
        win.main_box.set_hexpand(True)
        
        # Create header bar and add it to main_box
        self.create_header_bar(win)
        
        # Create toolbar container with fixed height to prevent webview movement
        win.toolbar_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.toolbar_container.set_vexpand(False)
        win.toolbar_container.add_css_class("toolbar-container")
        
        # Create top toolbar (below header)
        win.top_toolbar = self.create_top_toolbar(win)
        win.top_toolbar.add_css_class("top-toolbar")
        
        # Add toolbar to its container
        win.toolbar_container.append(win.top_toolbar)
        
        # Add toolbar container to main box
        win.main_box.append(win.toolbar_container)
        
        # Create content area for the webview and statusbar
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Create and configure webview
        win.webview = WebKit.WebView()
        win.webview.set_vexpand(True)
        win.webview.set_hexpand(True) 
        win.webview.load_html(self.get_editor_html(), None)
        settings = win.webview.get_settings()
        try:
            settings.set_enable_developer_extras(True)
        except:
            pass
        
        try:
            user_content_manager = win.webview.get_user_content_manager()
            user_content_manager.register_script_message_handler("contentChanged")
            user_content_manager.connect("script-message-received::contentChanged", 
                                        lambda mgr, res: self.on_content_changed(win, mgr, res))
        except:
            print("Warning: Could not set up JavaScript message handlers")
            
        win.webview.load_html(self.get_initial_html(), None)
        
        win.statusbar = Gtk.Label(label="Ready")
        win.statusbar.set_halign(Gtk.Align.START)
        win.statusbar.set_margin_start(10)
        win.statusbar.set_margin_end(10)
        win.statusbar.set_margin_top(5)
        win.statusbar.set_margin_bottom(5)
        
        # Add webview and statusbar to content box
        content_box.append(win.webview)
        content_box.append(win.statusbar)
        
        # Add content box to main box
        win.main_box.append(content_box)
        
        # Set the content of the window
        win.set_content(win.main_box)
        
        # Apply CSS for smooth toolbar animation
        self.apply_toolbar_css(win)
        
        self.setup_toolbar_animation(win)
        self.setup_keyboard_shortcuts(win)
        
        win.connect("close-request", self.on_window_close_request)
        
        # Add to windows list
        self.windows.append(win)
        self.setup_header_bar(win)
        
        return win

    def apply_toolbar_css(self, win):
        """Apply CSS for smooth toolbar animations"""
        css_provider = Gtk.CssProvider()
        css_data = """
            .toolbar-container {
                min-height: 45px; /* Fixed height to reserve space */
            }
            
            .top-toolbar {
                transition: opacity 200ms ease, margin-top 200ms ease;
                opacity: 1;
                margin-top: 0px;
            }
            
            .top-toolbar.hidden {
                opacity: 0;
                margin-top: -45px; /* Match the container height */
                pointer-events: none;
            }
        """
        css_provider.load_from_data(css_data.encode('utf-8'))
        display = win.get_display()
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def toggle_top_toolbar(self, win, *args):
        """Toggle the visibility of the top toolbar below the header bar with animation"""
        if hasattr(win, 'top_toolbar'):
            win.top_toolbar_visible = not win.top_toolbar_visible
            
            # Apply or remove CSS class for animation instead of hiding
            if win.top_toolbar_visible:
                win.top_toolbar.remove_css_class("hidden")
            else:
                win.top_toolbar.add_css_class("hidden")
                
            win.statusbar.set_text(f"Formatting toolbar {'shown' if win.top_toolbar_visible else 'hidden'}")
            print(f"Top toolbar toggled: {'visible' if win.top_toolbar_visible else 'hidden'}")
            return True
        else:
            print("Window does not have top_toolbar attribute")
        return False        
def main():
    app = HTMLEditorApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    Adw.init()
    sys.exit(main())       
