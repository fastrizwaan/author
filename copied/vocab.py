#!/usr/bin/python
import sys
import os
import codecs
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, Adw


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_default_size(500, 400)
        self.set_title("Vocabulary Builder")

        # Initialize variables
        self.define_variable()
        self.read_file_and_import_data()
        self.generate_training_data()

        # Main box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Create header bar
        self.create_header_bar()
        self.start_learning(None)

    def define_variable(self):
        self.fileData = []
        self.data = []
        self.word = ""
        self.difficulty = ""
        self.meaning = ""
        self.count = 0
        self.indexMax = 0
        self.current_mode = "learning"

    def create_header_bar(self):
        self.header = Adw.HeaderBar()
        self.main_box.append(self.header)

        # Menu button
        self.menu_button = Gtk.MenuButton()
        self.menu_button.set_icon_name("open-menu-symbolic")
        self.header.pack_end(self.menu_button)

        # Menu popover
        self.menu_popover = Gtk.PopoverMenu()
        self.menu_button.set_popover(self.menu_popover)

        # Menu model
        menu = Gio.Menu()
        menu.append("Learn Vocabulary", "win.learn")
        menu.append("Take Quiz", "win.quiz")
        menu.append("Quit", "app.quit")
        self.menu_popover.set_menu_model(menu)

        # Navigation buttons
        self.prev_btn = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self.prev_btn.add_css_class("flat")
        self.header.pack_start(self.prev_btn)

        self.next_btn = Gtk.Button.new_from_icon_name("go-next-symbolic")
        self.next_btn.add_css_class("flat")
        self.header.pack_start(self.next_btn)

        # Connect actions
        self.create_action("learn", self.start_learning)
        self.create_action("quiz", self.start_quiz)

    def create_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def start_learning(self, action, param):
        self.current_mode = "learning"
        self.header.set_title("Learning")
        self.update_content()

    def start_quiz(self, action, param):
        self.current_mode = "quiz"
        self.header.set_title("Quiz")
        self.update_content()

    def update_content(self):
        # Clear previous content
        if self.main_box.get_last_child():
            self.main_box.remove(self.main_box.get_last_child())

        if self.current_mode == "learning":
            self.setup_learning_ui()
        else:
            self.setup_quiz_ui()

        self.generate_values(self.data)
        self.update_ui()

    def setup_learning_ui(self):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(10)
        content.set_margin_end(10)
        content.set_margin_top(10)
        content.set_margin_bottom(10)

        self.word_label = Gtk.Label()
        self.word_label.add_css_class("title-1")
        content.append(self.word_label)

        self.difficulty_label = Gtk.Label()
        self.difficulty_label.add_css_class("caption")
        content.append(self.difficulty_label)

        self.meaning_label = Gtk.Label()
        self.meaning_label.set_wrap(True)
        content.append(self.meaning_label)

        self.main_box.append(content)

    def setup_quiz_ui(self):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(10)
        content.set_margin_end(10)
        content.set_margin_top(10)
        content.set_margin_bottom(10)

        self.word_label = Gtk.Label()
        self.word_label.add_css_class("title-1")
        content.append(self.word_label)

        self.difficulty_label = Gtk.Label()
        self.difficulty_label.add_css_class("caption")
        content.append(self.difficulty_label)

        self.quiz_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.buttons = []
        for _ in range(5):
            btn = Gtk.CheckButton()
            btn.connect("toggled", self.on_answer_toggled)
            self.buttons.append(btn)
            self.quiz_box.append(btn)
        
        content.append(self.quiz_box)
        self.main_box.append(content)

    def generate_values(self, data):
        if self.count < 0:
            self.count = 0
        if self.count > self.indexMax:
            self.count = self.indexMax

        self.word = self.data[self.count][0]
        self.difficulty = self.data[self.count][4]
        self.meaning = self.data[self.count][2]

    def update_ui(self):
        self.word_label.set_label(self.word)
        self.difficulty_label.set_label(self.difficulty)
        
        if self.current_mode == "learning":
            self.meaning_label.set_label(self.meaning)
        else:
            # Generate quiz answers
            pass

    def on_answer_toggled(self, button):
        # Handle quiz answer selection
        pass

    def read_file_and_import_data(self):
        try:
            with codecs.open("./vocab_data.tsv", "rb", encoding='UTF-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) == 6:
                        self.fileData.append(parts)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)

    def generate_training_data(self):
        self.data = self.fileData[:10]  # Simple example
        self.indexMax = len(self.data) - 1


class VocabApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.VocabBuilder")
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(app)
        self.win.present()


if __name__ == "__main__":
    app = VocabApp()
    app.run(sys.argv)
