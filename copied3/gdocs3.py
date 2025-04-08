#!/usr/bin/env python3
import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Adw, WebKit, GLib, Gio

class WritepadApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.writepad",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Create the main window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(1024, 768)
        self.win.set_title("Writepad")
        
        # Create a header bar
        header = Adw.HeaderBar()
        
        # Create WebKit settings
        settings = WebKit.Settings()
        settings.set_enable_javascript(True)
        settings.set_javascript_can_access_clipboard(True)
        settings.set_enable_developer_extras(True)
        settings.set_user_agent_with_application_details(
            "WritepadGTK", "1.0"
        )
        
        # Create color scheme manager to track dark/light mode
        color_manager = Adw.StyleManager.get_default()
        
        # Create WebKit web view with default context
        self.webview = WebKit.WebView()
        self.webview.set_settings(settings)
        
        # Get the network session and configure cookie persistence
        network_session = self.webview.get_network_session()
        cookie_manager = network_session.get_cookie_manager()
        cookie_manager.set_persistent_storage(
            "cookies.db",
            WebKit.CookiePersistentStorage.SQLITE
        )
        
        # Set up a custom web view controller to handle theme changes
        self.web_controller = self.webview.get_website_policies()
        
        # Set up the initial theme
        self.update_webkit_colors(color_manager)
        
        # Connect to style change signal to update when theme changes
        color_manager.connect("notify::color-scheme", self.on_theme_changed)
        
        # Load Writepad instead of Google Docs
        self.webview.load_uri("https://writepad.glitch.me/")
        
        # Create refresh button
        refresh_button = Gtk.Button()
        refresh_button.set_icon_name("view-refresh-symbolic")
        refresh_button.connect("clicked", self.on_refresh_clicked)
        header.pack_start(refresh_button)
        
        # Create back button
        back_button = Gtk.Button()
        back_button.set_icon_name("go-previous-symbolic")
        back_button.connect("clicked", self.on_back_clicked)
        header.pack_start(back_button)
        
        # Create forward button
        forward_button = Gtk.Button()
        forward_button.set_icon_name("go-next-symbolic")
        forward_button.connect("clicked", self.on_forward_clicked)
        header.pack_start(forward_button)
        
        # Create main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(header)
        
        # Create a scrolled window to hold the web view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.webview)
        box.append(scrolled)
        
        # Set the window content
        self.win.set_content(box)
        self.win.present()
    
    def update_webkit_colors(self, color_manager):
        # Check if we're in dark mode
        is_dark = color_manager.get_color_scheme() in [
            Adw.ColorScheme.PREFER_DARK, 
            Adw.ColorScheme.FORCE_DARK
        ]
        
        # Use WebView's settings for WebKit 6.0 to inject CSS for dark mode
        if is_dark:
            # Load Writepad with dark mode detection via JS
            script = """
            document.addEventListener('DOMContentLoaded', function() {
                // Add dark mode detection
                const darkModeStyle = document.createElement('style');
                darkModeStyle.textContent = `
                    @media (prefers-color-scheme: dark) {
                        html {
                            filter: invert(100%) hue-rotate(180deg);
                        }
                        img, video, canvas {
                            filter: invert(100%) hue-rotate(180deg);
                        }
                    }
                `;
                document.head.appendChild(darkModeStyle);
                
                // Force dark mode regardless of media query
                const forceDarkStyle = document.createElement('style');
                forceDarkStyle.textContent = `
                    html {
                        filter: invert(100%) hue-rotate(180deg);
                    }
                    img, video, canvas {
                        filter: invert(100%) hue-rotate(180deg);
                    }
                `;
                document.head.appendChild(forceDarkStyle);
            });
            """
            self.webview.evaluate_javascript(script, -1, None, None, None, None, None)
        else:
            # Remove any dark mode styling if we switch back to light
            script = """
            document.addEventListener('DOMContentLoaded', function() {
                // Remove any previously added dark mode styles
                Array.from(document.head.getElementsByTagName('style')).forEach(style => {
                    if (style.textContent.includes('filter: invert(100%)')) {
                        style.remove();
                    }
                });
            });
            """
            self.webview.evaluate_javascript(script, -1, None, None, None, None, None)
        
        # Force reload if page is already loaded to apply theme change
        if self.webview.get_uri():
            self.webview.reload()
    
    def on_theme_changed(self, color_manager, pspec):
        # Update WebKit colors when theme changes
        self.update_webkit_colors(color_manager)
        
    def on_refresh_clicked(self, button):
        self.webview.reload()
        
    def on_back_clicked(self, button):
        if self.webview.can_go_back():
            self.webview.go_back()
            
    def on_forward_clicked(self, button):
        if self.webview.can_go_forward():
            self.webview.go_forward()

if __name__ == "__main__":
    # Initialize Adwaita before running the app
    Adw.init()
    
    app = WritepadApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
