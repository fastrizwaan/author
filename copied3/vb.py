#!/usr/bin/python3

import codecs
import os
import sys
from random import sample

import gi

gi.require_version("Gtk", "4.0")
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_default_size(500, 400)
        self.draw_main_window_headerbar()
        self.define_variable()
        self.read_file_and_import_data()
        self.generate_training_data()

        # Initialize vbox1 and add the header bar once
        self.vbox1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.vbox1.append(self.hb)  # Add header bar to vbox1 only once
        self.set_content(self.vbox1)

        self.start_learning(None)  # Start with learning mode

    def set_vbox(self):
        # Remove all children from vbox1 except the header bar (self.hb)
        child = self.vbox1.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            if child != self.hb:
                self.vbox1.remove(child)
            child = next_child


    def start_learning(self, button):
        self.count = 0
        self.change_to_learning_headerbar()
        self.generate_values(self.data)
        self.set_vbox()

        # Update title and subtitle using the title box
        self.update_headerbar_title("Vocabulary Builder", "Learning")

        self.show_learning_labels()

        self.hbox0 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.vbox1.append(self.hbox0)
        self.hbox0.append(self.word_label)
        self.hbox0.append(self.word_difficulty)
        self.vbox1.append(self.word_meaning)
        print(self.word)

    def show_learning_labels(self):
        """Display word, difficulty, and meaning labels in learning mode."""
        self.word_label.set_markup(f"<span size='xx-large'><b>{self.word}</b></span>")
        self.word_label.set_halign(Gtk.Align.START)

        self.word_difficulty.set_markup(f"<span size='xx-small'><b>{self.difficulty}</b></span>")
        self.word_difficulty.set_halign(Gtk.Align.END)
        self.word_difficulty.set_wrap(True)

        self.word_meaning.set_markup(self.answer)
        self.word_meaning.set_halign(Gtk.Align.START)
        self.word_meaning.set_wrap(True)

    def start_quiz(self, button):
        self.count = 0
        self.update_headerbar_title("Vocabulary Builder", "Quiz")
        self.change_to_quiz_headerbar()
        self.generate_values(self.data)
        self.set_vbox()

        self.button = [Gtk.CheckButton() for _ in range(5)]

        self.vbox0 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.hbox0 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=150)

        self.vbox1.append(self.hbox0)
        self.vbox1.append(self.vbox0)

        self.hbox0.append(self.word_label)
        self.hbox0.append(self.word_difficulty)

        self.show_quiz_labels()

    def generate_values(self, data):
        """Generate values for learning or quiz sessions."""
        self.count = max(0, min(self.count, self.indexMax))
        self.buttonBack.set_sensitive(self.count > 0)
        self.buttonNext.set_sensitive(self.count < self.indexMax)

        randList = sample(range(0, len(self.fileData)), 5)

        quizWord = self.data[self.count][0]
        self.answer = self.data[self.count][1]
        self.difficulty = self.data[self.count][4]
        answer1 = self.fileData[randList[1]][1]
        answer2 = self.fileData[randList[2]][1]
        answer3 = self.fileData[randList[3]][1]
        answer4 = self.fileData[randList[4]][1]

        randList2 = sample(range(0, 5), 5)
        xlist = [self.answer, answer1, answer2, answer3, answer4]
        self.randXList = [xlist[i] for i in randList2]
        self.correct = self.randXList.index(self.answer)
        self.word = quizWord

    def update_headerbar_title(self, title, subtitle):
        title_box = self.hb.get_title_widget()
        if title_box:
            title_box.get_first_child().set_text(title)
            title_box.get_last_child().set_text(subtitle)

    def on_button_toggled(self, button, name):
        if button.get_active():
            if self.correct != name:
                print("Incorrect!")
                output = button.get_label()
                button.get_child().set_markup(f"<span><s>{output}</s></span>")
            else:
                print("Correct!!!!")

            for x in range(5):
                self.button[x].set_sensitive(False)
            self.button[self.correct].set_active(True)

    def read_file_and_import_data(self):
        try:
            fileName = "./vocab_data.tsv"
            file = codecs.open(fileName, "rb", encoding='UTF-8')
        except IndexError:
            print("Error: Please provide filename as argument")
            sys.exit(2)
        except IOError:
            print("Error: Cannot open file:", fileName)
            sys.exit(2)

        for line in file:
            line = line.strip(os.linesep)
            line = line.strip()
            try:
                (one, two, three, four, five, six) = line.split('\t')
                x = [one, two, three, four, five, six]
                self.fileData.append(x)
            except ValueError:
                print("*** Each Line with 6 values (word, pos, mean, example, difficulty, mastered) separated by Tabs")
                print("the bad line is")
                print('*' * 50)
                print(line)
                print('*' * 50)
                file.close()
                sys.exit(2)

        file.close()

    def define_variable(self):
        self.fileData = []
        self.data = []
        self.css = ""
        self.second = ""
        self.third = ""
        self.fourth = ""
        self.fifth = ""
        self.word = ""
        self.difficulty = ""
        self.meaning = ""
        self.what = ''
        self.answer = ""
        self.word_label = Gtk.Label()
        self.word_difficulty = Gtk.Label()
        self.word_meaning = Gtk.Label()
        self.icon = ""
        self.count = 0

    def generate_training_data(self):
        """Populate sample training data from fileData"""
        needItems = 10  # Number of items to add
        idxMax = len(self.fileData) - 1
        r = sample(range(0, idxMax), min(needItems, len(self.fileData)))

        self.data = [self.fileData[i] for i in r]
        self.indexMax = len(self.data) - 1

    def draw_main_window_headerbar(self):
        self.hb = Adw.HeaderBar()
        self.hb.set_show_end_title_buttons(True)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title_label = Gtk.Label(label="Vocabulary Builder")
        subtitle_label = Gtk.Label(label="Learning")
        title_box.append(title_label)
        title_box.append(subtitle_label)
        self.hb.set_title_widget(title_box)

        self.buttonBack = Gtk.Button()
        self.backIcon = Gio.ThemedIcon(name="go-previous-symbolic")
        self.backImage = Gtk.Image.new_from_gicon(self.backIcon)
        self.buttonBack.set_child(self.backImage)
        self.buttonBack.set_sensitive(False)
        self.hb.pack_start(self.buttonBack)

        self.buttonNext = Gtk.Button()
        self.nextIcon = Gio.ThemedIcon(name="go-next-symbolic")
        self.nextImage = Gtk.Image.new_from_gicon(self.nextIcon)
        self.buttonNext.set_child(self.nextImage)
        self.buttonNext.set_sensitive(False)
        self.hb.pack_start(self.buttonNext)

        self.menu_button = Gtk.MenuButton()
        self.icon = Gio.ThemedIcon(name="open-menu-symbolic")
        self.image = Gtk.Image.new_from_gicon(self.icon)
        self.menu_button.set_child(self.image)
        self.hb.pack_end(self.menu_button)

        self.popover = Gtk.Popover()
        self.menu_button.set_popover(self.popover)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.set_margin_top(5)
        vbox.set_margin_bottom(5)
        vbox.set_margin_start(5)
        vbox.set_margin_end(5)

        menu_item_button1 = Gtk.Button(label="Learn Vocabulary")
        menu_item_button1.connect("clicked", self.start_learning)
        vbox.append(menu_item_button1)

        menu_item_button2 = Gtk.Button(label="Take Quiz")
        menu_item_button2.connect("clicked", self.start_quiz)
        vbox.append(menu_item_button2)

        menu_item_button3 = Gtk.CheckButton(label="Dark Theme")
        menu_item_button3.connect("toggled", self.set_dark_theme)
        vbox.append(menu_item_button3)

        menu_item_button4 = Gtk.Button(label="Quit")
        menu_item_button4.connect("clicked", self.on_quit)
        vbox.append(menu_item_button4)

        self.popover.set_child(vbox)

    def change_to_learning_headerbar(self):
        self.count = 0
        try:
            self.buttonBack.disconnect_by_func(self.on_click_me_clicked_back_quiz)
            self.buttonNext.disconnect_by_func(self.on_click_me_clicked_next_quiz)
        except TypeError:
            pass

        self.buttonBack.connect("clicked", self.on_click_me_clicked_back_learn)
        self.buttonNext.connect("clicked", self.on_click_me_clicked_next_learn)
        self.buttonBack.set_sensitive(False)
        self.buttonNext.set_sensitive(True)

    def on_click_me_clicked_back_learn(self, widget):
        if self.count >= 1:
            self.count -= 1
            self.generate_values(self.data)
        self.show_learning_labels()

    def on_click_me_clicked_back_quiz(self, widget):
        if self.count >= 1:
            self.count -= 1
            self.generate_values(self.data)
        self.show_quiz_labels()

    def change_to_quiz_headerbar(self):
        self.count = 0
        try:
            self.buttonBack.disconnect_by_func(self.on_click_me_clicked_back_learn)
            self.buttonNext.disconnect_by_func(self.on_click_me_clicked_next_learn)
        except TypeError:
            pass

        self.buttonBack.connect("clicked", self.on_click_me_clicked_back_quiz)
        self.buttonNext.connect("clicked", self.on_click_me_clicked_next_quiz)
        self.buttonBack.set_sensitive(False)
        self.buttonNext.set_sensitive(True)

    def on_click_me_clicked_next_learn(self, widget):
        if self.count < self.indexMax:
            self.count += 1
            self.generate_values(self.data)
        self.show_learning_labels()

    def on_click_me_clicked_next_quiz(self, widget):
        if self.count < self.indexMax:
            self.count += 1
            self.generate_values(self.data)
        self.show_quiz_labels()

    def set_dark_theme(self, button):
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", button.get_active())

    def on_quit(self, widget):
        self.get_application().quit()


class MyApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.VocabularyBuilder')
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = MainWindow(application=app)
        win.present()


def main():
    app = MyApplication()
    app.run(sys.argv)


if __name__ == "__main__":
    main()

