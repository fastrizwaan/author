import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw, Gtk

class AdwCheckboxApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.AdwCheckboxApp')
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Use Gtk.ApplicationWindow instead of Adw.ApplicationWindow
        self.win = Gtk.ApplicationWindow(application=app)
        self.win.set_default_size(400, 300)
        self.win.set_title('Adw Checkboxes')
        
        # Create Adw.HeaderBar manually
        header = Adw.HeaderBar()
        
        # Add custom button
        add_btn = Gtk.Button.new_from_icon_name('list-add-symbolic')
        add_btn.add_css_class('flat')
        add_btn.connect('clicked', self.show_dialog)
        header.pack_end(add_btn)
        
        # Set header bar as titlebar
        self.win.set_titlebar(header)
        
        # Create content
        self.setup_content()
        self.win.present()

    def setup_content(self):
        # Create responsive clamp
        clamp = Adw.Clamp()
        
        # Create vertical container
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.vbox.set_margin_top(24)
        self.vbox.set_margin_bottom(24)
        self.vbox.set_margin_start(24)
        self.vbox.set_margin_end(24)
        
        # Add initial checkboxes
        for i in range(1, 5):
            self.add_checkbox(f'Option {i}')
        
        clamp.set_child(self.vbox)
        self.win.set_child(clamp)  # Use set_child() for Gtk.ApplicationWindow

    def add_checkbox(self, label):
        check = Gtk.CheckButton.new_with_label(label)
        check.add_css_class('card')
        self.vbox.append(check)

    def show_dialog(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self.win,
            heading='Add New Option',
            body='Enter option name:'
        )
        
        entry = Gtk.Entry()
        entry.set_placeholder_text('New option')
        dialog.set_extra_child(entry)
        
        dialog.add_response('cancel', '_Cancel')
        dialog.add_response('add', '_Add')
        dialog.set_response_appearance('add', Adw.ResponseAppearance.SUGGESTED)
        
        dialog.connect('response', self.handle_response, entry)
        dialog.present()

    def handle_response(self, dialog, response, entry):
        if response == 'add':
            text = entry.get_text().strip()
            if text:
                self.add_checkbox(text)
        dialog.close()

if __name__ == '__main__':
    app = AdwCheckboxApp()
    app.run()
