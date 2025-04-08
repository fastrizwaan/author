#!/usr/bin/env python3
import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Adw, WebKit, GLib, Gio

class GoogleDocsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.googledocs",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Create the main window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(1024, 768)
        self.win.set_title("Google Docs")
        
        # Create a header bar
        header = Adw.HeaderBar()
        
        # Create WebKit settings
        settings = WebKit.Settings()
        settings.set_enable_javascript(True)
        settings.set_javascript_can_access_clipboard(True)
        settings.set_enable_developer_extras(True)
        settings.set_user_agent_with_application_details(
            "GoogleDocsGTK", "1.0"
        )
        
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
        
        # Load Google Docs
        self.webview.load_uri("https://docs.google.com")
        
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
        
    def on_refresh_clicked(self, button):
        self.webview.reload()
        
    def on_back_clicked(self, button):
        if self.webview.can_go_back():
            self.webview.go_back()
            
    def on_forward_clicked(self, button):
        if self.webview.can_go_forward():
            self.webview.go_forward()

if __name__ == "__main__":
    app = GoogleDocsApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
