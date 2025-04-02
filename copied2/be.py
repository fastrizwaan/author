#!/usr/bin/env python3

import gi
import sys
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio

class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.example.GtkApp')
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Create the main application window
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(400, 300)
        self.window.set_title('Button Example')

        # Create the main button (Button1)
        self.main_button = Gtk.Button(label='Button1')
        self.main_button.connect('clicked', self.on_main_button_clicked)

        # Create buttons A and B
        button_a = Gtk.Button(label='A')
        button_a.connect('clicked', self.on_button_a_clicked)
        button_b = Gtk.Button(label='B')
        button_b.connect('clicked', self.on_button_b_clicked)

        # Create a box for buttons A and B
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.append(button_a)
        button_box.append(button_b)

        # Create an overlay to stack Button1 and the button box
        overlay = Gtk.Overlay()
        overlay.add_overlay(button_box)
        overlay.set_child(self.main_button)

        # Set the overlay as the main window content
        self.window.set_child(overlay)
        self.window.present()

        # Connect the enter-notify-event and leave-notify-event signals to enable/disable Button1
        enter_controller = Gtk.EventControllerMotion()
        enter_controller.connect('enter', self.on_button_box_enter)
        button_box.add_controller(enter_controller)

        leave_controller = Gtk.EventControllerMotion()
        leave_controller.connect('leave', self.on_button_box_leave)
        button_box.add_controller(leave_controller)

    def on_main_button_clicked(self, button):
        print('Button1')

    def on_button_a_clicked(self, button):
        print('A')

    def on_button_b_clicked(self, button):
        print('B')

    def on_button_box_enter(self, controller, x, y, data=None):
        self.main_button.set_sensitive(False)

    def on_button_box_leave(self, controller, x, y, data=None):
        self.main_button.set_sensitive(True)

def main():
    app = MyApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()

