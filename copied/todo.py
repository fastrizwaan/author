import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GObject
import json
from datetime import datetime
import os

class TodoApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Create main window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(450, 600)
        self.win.set_title("Tasks")

        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.set_content(main_box)

        # Create header bar
        header_bar = Adw.HeaderBar()
        main_box.append(header_bar)

        # Create entry box at the top
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Add a new task...")
        self.entry.set_hexpand(True)
        self.entry.set_margin_start(12)
        self.entry.set_margin_end(12)
        self.entry.set_margin_top(12)
        self.entry.set_margin_bottom(12)
        self.entry.connect('activate', self.on_add_button_clicked)
        main_box.append(self.entry)

        # Add button in header
        add_button = Gtk.Button(label="Add Task")
        add_button.add_css_class("suggested-action")
        add_button.connect('clicked', self.on_add_button_clicked)
        header_bar.pack_end(add_button)

        # Create scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

        # Create list box
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        scrolled.set_child(self.list_box)

        # Load saved tasks
        self.load_tasks()

        # Present the window
        self.win.present()

    def create_row(self, text, completed=False, timestamp=None):
        # Create row box
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Create checkbox
        check_button = Gtk.CheckButton()
        check_button.set_active(completed)
        check_button.connect('toggled', self.on_check_toggled)
        box.append(check_button)

        # Create task label
        label = Gtk.Label(label=text)
        label.set_hexpand(True)
        label.set_xalign(0)
        if completed:
            label.add_css_class("dim-label")
        box.append(label)

        # Create delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.add_css_class("flat")
        delete_button.connect('clicked', self.on_delete_clicked)
        box.append(delete_button)

        # Create row
        row = Gtk.ListBoxRow()
        row.task_text = text
        row.completed = completed
        row.timestamp = timestamp or datetime.now().isoformat()
        row.set_child(box)
        
        return row

    def on_add_button_clicked(self, widget):
        text = self.entry.get_text().strip()
        if text:
            row = self.create_row(text)
            self.list_box.append(row)
            self.entry.set_text("")  # Clear the entry
            self.save_tasks()

    def on_check_toggled(self, check_button):
        box = check_button.get_parent()
        row = box.get_parent()
        label = box.get_first_child().get_next_sibling()
        
        row.completed = check_button.get_active()
        if check_button.get_active():
            label.add_css_class("dim-label")
        else:
            label.remove_css_class("dim-label")
        
        self.save_tasks()

    def on_delete_clicked(self, button):
        row = button.get_parent().get_parent()
        self.list_box.remove(row)
        self.save_tasks()

    def save_tasks(self):
        tasks = []
        child = self.list_box.get_first_child()
        
        while child:
            if isinstance(child, Gtk.ListBoxRow):
                tasks.append({
                    'text': child.task_text,
                    'completed': child.completed,
                    'timestamp': child.timestamp
                })
            child = child.get_next_sibling()
            
        try:
            save_path = os.path.expanduser('~/.local/share/todo-app')
            os.makedirs(save_path, exist_ok=True)
            save_file = os.path.join(save_path, 'tasks.json')
            
            with open(save_file, 'w') as f:
                json.dump(tasks, f)
        except Exception as e:
            print(f"Error saving tasks: {e}")

    def load_tasks(self):
        try:
            save_path = os.path.expanduser('~/.local/share/todo-app')
            save_file = os.path.join(save_path, 'tasks.json')
            
            with open(save_file, 'r') as f:
                tasks = json.load(f)
                for task in tasks:
                    row = self.create_row(
                        task['text'],
                        task.get('completed', False),
                        task.get('timestamp')
                    )
                    self.list_box.append(row)
        except FileNotFoundError:
            # No saved tasks yet - that's okay
            pass
        except Exception as e:
            print(f"Error loading tasks: {e}")

app = TodoApp(application_id='com.example.TodoApp')
app.run(None)
