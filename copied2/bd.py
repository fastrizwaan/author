#!/usr/bin/env python3

import gi
import sys
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk

class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.example.GtkApp')
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Create the main application window
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(400, 300)
        self.window.set_title('Flowbox Example')

        # Create a flowbox
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create a flowbox child for Button1
        flowbox_child = Gtk.FlowBoxChild()

        # Create the main button
        main_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        main_button_box.set_name('main_button_box')
        main_button_box.add_controller(self.create_click_controller('Button1'))

        # Create buttons A and B
        button_a = Gtk.Button(label='A')
        button_a.connect('clicked', self.on_button_a_clicked)
        main_button_box.append(button_a)

        button_b = Gtk.Button(label='B')
        button_b.connect('clicked', self.on_button_b_clicked)
        main_button_box.append(button_b)

        flowbox_child.set_child(main_button_box)
        self.flowbox.append(flowbox_child)

        # Add the flowbox to a scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_child(self.flowbox)

        # Set the scrolled window as the main window content
        self.window.set_child(scrolled_window)
        self.window.present()

    def create_click_controller(self, label):
        click_controller = Gtk.GestureClick()
        click_controller.connect('pressed', self.on_main_button_pressed)
        click_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)  # Capture phase to intercept before child widgets
        click_controller.label = label  # Store the label in the controller
        return click_controller

    def on_main_button_pressed(self, controller, n_press, x, y):
        widget = controller.get_widget()
        if widget and isinstance(widget, Gtk.Button):
            if widget.get_label() in ('A', 'B'):
                return  # Stop propagation if it's button A or B

        # Otherwise, it's a click on the main button box
        print(controller.label)

    def on_button_a_clicked(self, button):
        print('A')

    def on_button_b_clicked(self, button):
        print('B')

def main():
    app = MyApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()

