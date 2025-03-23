import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GObject, Pango

class WordItem(GObject.Object):
    __gtype_name__ = 'WordItem'

    word = GObject.Property(type=str)
    meaning = GObject.Property(type=str)
    usage = GObject.Property(type=str)

    def __init__(self, word, meaning, usage):
        super().__init__()
        self.word = word
        self.meaning = meaning
        self.usage = usage

class VocabularyBuilderWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(800, 600)
        self.set_title("Vocabulary Builder")
        
        # Create main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_content(self.main_box)

        # Header Bar
        header = Adw.HeaderBar()
        self.main_box.append(header)

        # Add word button
        self.add_button = Gtk.Button(label="Add Word")
        self.add_button.add_css_class('suggested-action')
        self.add_button.connect('clicked', self.add_word)
        header.pack_start(self.add_button)

        # Remove word button
        self.remove_button = Gtk.Button(label="Remove Word")
        self.remove_button.add_css_class('destructive-action')
        self.remove_button.connect('clicked', self.on_remove_clicked)
        header.pack_end(self.remove_button)

        # Create entry fields
        entries_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=10, margin_end=10)
        self.main_box.append(entries_box)

        self.word_entry = self.create_entry("Word")
        entries_box.append(self.word_entry)

        self.meaning_entry = self.create_entry("Meaning")
        entries_box.append(self.meaning_entry)

        self.usage_entry = self.create_entry("Usage in Sentence")
        entries_box.append(self.usage_entry)

        # Create word list
        self.list_store = Gio.ListStore(item_type=WordItem)
        self.selection_model = Gtk.SingleSelection(model=self.list_store)
        
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.on_factory_setup)
        factory.connect("bind", self.on_factory_bind)

        self.column_view = Gtk.ColumnView(model=self.selection_model)
        self.column_view.set_reorderable(False)
        self.column_view.add_css_class('data-table')
        
        # Create columns
        for i, title in enumerate(["Word", "Meaning", "Usage"]):
            column = Gtk.ColumnViewColumn(title=title, factory=factory)
            column.set_resizable(True)
            self.column_view.append_column(column)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_child(self.column_view)
        scrolled_window.set_vexpand(True)
        entries_box.append(scrolled_window)

    def create_entry(self, placeholder):
        entry = Adw.EntryRow(title=placeholder)
        entry.set_show_apply_button(True)
        entry.set_margin_top(10)
        return entry

    def on_factory_setup(self, factory, list_item):
        label = Gtk.Label()
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_xalign(0)
        list_item.set_child(label)

    def on_factory_bind(self, factory, list_item):
        label = list_item.get_child()
        word_item = list_item.get_item()
        column = list_item.get_position()
        
        if column == 0:
            label.set_label(word_item.word)
        elif column == 1:
            label.set_label(word_item.meaning)
        elif column == 2:
            label.set_label(word_item.usage)

    def add_word(self, widget):
        word = self.word_entry.get_text()
        meaning = self.meaning_entry.get_text()
        usage = self.usage_entry.get_text()

        if word and meaning and usage:
            self.list_store.append(WordItem(word, meaning, usage))
            self.clear_fields()

    def on_remove_clicked(self, widget):
        position = self.selection_model.get_selected()
        if position != Gtk.INVALID_LIST_POSITION:
            self.list_store.remove(position)

    def clear_fields(self):
        self.word_entry.set_text('')
        self.meaning_entry.set_text('')
        self.usage_entry.set_text('')

class VocabularyBuilderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.VocabularyBuilder')
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = VocabularyBuilderWindow(application=self)
            self.setup_style()
        self.window.present()

    def setup_style(self):
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

class VocabularyBuilder:
    def __init__(self):
        self.app = VocabularyBuilderApp()

    def run(self):
        self.app.run(None)

if __name__ == "__main__":
    vb = VocabularyBuilder()
    vb.run()
