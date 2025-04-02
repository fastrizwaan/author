import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio


class FlowBoxExample(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.FlowBox")
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_title("FlowBox Example")
            self.window.set_default_size(400, 300)

            # Create a scrolled window
            scrolled_window = Gtk.ScrolledWindow()
            self.window.set_child(scrolled_window)

            # Create a FlowBox
            flowbox = Gtk.FlowBox()
            flowbox.set_valign(Gtk.Align.START)
            flowbox.set_max_children_per_line(3)
            flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
            scrolled_window.set_child(flowbox)

            # Add some buttons to the FlowBox
            for i in range(12):
                button = Gtk.Button(label=f"Button {i + 1}")
                button.connect("clicked", self.on_button_clicked)
                flowbox.append(button)

        self.window.show()

    def on_button_clicked(self, button):
        print(f"{button.get_label()} clicked!")


def main():
    app = FlowBoxExample()
    app.run()


if __name__ == "__main__":
    main()
