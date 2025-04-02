#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
from gi.repository import Gtk, Adw, WebKit, Gio
import os
import sys
import tempfile

class PaginatedEditorWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(800, 850)
        self.set_title("Paginated Editor")
        
        # Main container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)
        
        # Header with menu and save button
        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton.new()
        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu_button.set_menu_model(menu)
        menu_button.set_icon_name("open-menu-symbolic")
        header.pack_end(menu_button)
        
        save_button = Gtk.Button.new_from_icon_name("document-save-symbolic")
        save_button.connect("clicked", self.on_save_clicked)
        header.pack_start(save_button)
        self.main_box.append(header)
        
        # Setup WebKit editor
        self.create_editor()
        
        # Create temporary file for HTML
        self.temp_dir = tempfile.TemporaryDirectory()
        self.html_path = os.path.join(self.temp_dir.name, "editor.html")
        self.create_editor_html()
        self.webview.load_uri(f"file://{self.html_path}")
    
    def create_editor(self):
        self.webview = WebKit.WebView.new()
        self.webview.set_hexpand(True)
        self.webview.set_vexpand(True)
        
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_javascript_can_access_clipboard(True)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.webview)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        self.main_box.append(scrolled)
    
    def create_editor_html(self):
        html_content = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Paginated Editor</title>
  <style>
    body { margin: 0; padding: 0; background: #f0f0f0; font-family: 'Cantarell', sans-serif; }
    #editor { display: flex; flex-direction: column; align-items: center; padding: 20px; min-height: 100vh; }
    .page { width: 8.5in; height: 11in; background: white; box-shadow: 0 0 10px rgba(0,0,0,0.2); margin-bottom: 20px; padding: 1in; box-sizing: border-box; position: relative; overflow: hidden; }
    .page-content { width: 100%; height: 100%; outline: none; border: none; font-size: 12pt; line-height: 1.5; }
    .page-content::-webkit-scrollbar { display: none; }
    .page-number { position: absolute; bottom: 0.5in; right: 0.5in; font-size: 10pt; color: #888; }
  </style>
</head>
<body>
  <div id="editor">
    <div class="page">
      <div class="page-content" contenteditable="true"></div>
      <div class="page-number">1</div>
    </div>
  </div>
  <script>
    let pages = document.querySelectorAll('.page');
    const editor = document.getElementById('editor');
    function getContentHeight(el) {
      let clone = el.cloneNode(true);
      clone.style.visibility = 'hidden'; clone.style.position = 'absolute'; clone.style.height = 'auto';
      document.body.appendChild(clone);
      let h = clone.scrollHeight;
      document.body.removeChild(clone);
      return h;
    }
    function checkOverflow() {
      document.querySelectorAll('.page-content').forEach((content, index, contents) => {
        if (index === contents.length - 1) return;
        let maxHeight = content.clientHeight;
        while (content.scrollHeight > maxHeight) {
          let lastNode = content.lastChild;
          if (!lastNode) break;
          if (lastNode.nodeType === Node.TEXT_NODE) {
            let words = lastNode.textContent.split(' ');
            if (words.length > 1) {
              let lastWord = words.pop();
              lastNode.textContent = words.join(' ');
              moveContentToNextPage(lastWord, index);
            } else {
              content.removeChild(lastNode);
              moveContentToNextPage(lastNode.textContent, index);
            }
          } else {
            content.removeChild(lastNode);
            moveContentToNextPage(lastNode, index);
          }
        }
      });
      let lastPage = pages[pages.length - 1].querySelector('.page-content');
      if (lastPage.scrollHeight > lastPage.clientHeight) addNewPage();
      checkForEmptyPages();
    }
    function moveContentToNextPage(content, fromPageIndex) {
      let nextPage = pages[fromPageIndex + 1].querySelector('.page-content');
      if (typeof content === 'string') {
        let textNode = document.createTextNode(content + ' ');
        nextPage.insertBefore(textNode, nextPage.firstChild);
      } else {
        nextPage.insertBefore(content, nextPage.firstChild);
      }
      setTimeout(checkOverflow, 0);
    }
    function addNewPage() {
      let newPage = document.createElement('div');
      newPage.className = 'page';
      let newContent = document.createElement('div');
      newContent.className = 'page-content';
      newContent.contentEditable = 'true';
      newContent.addEventListener('input', onInput);
      newContent.addEventListener('keydown', onKeyDown);
      let newPageNumber = document.createElement('div');
      newPageNumber.className = 'page-number';
      newPageNumber.textContent = pages.length + 1;
      newPage.append(newContent, newPageNumber);
      editor.appendChild(newPage);
      pages = document.querySelectorAll('.page');
      checkOverflow();
    }
    function checkForEmptyPages() {
      if (pages.length <= 1) return;
      for (let i = pages.length - 2; i >= 0; i--) {
        let content = pages[i].querySelector('.page-content');
        let nextContent = pages[i+1].querySelector('.page-content');
        if (!content.textContent.trim() && nextContent.textContent.trim()) {
          editor.removeChild(pages[i]);
          pages = document.querySelectorAll('.page');
          updatePageNumbers();
          setTimeout(checkForEmptyPages, 0);
          return;
        }
      }
      if (pages.length > 1) {
        let lastContent = pages[pages.length - 1].querySelector('.page-content');
        if (!lastContent.textContent.trim()) {
          editor.removeChild(pages[pages.length - 1]);
          pages = document.querySelectorAll('.page');
          updatePageNumbers();
        }
      }
    }
    function updatePageNumbers() {
      document.querySelectorAll('.page-number').forEach((num, i) => num.textContent = i + 1);
    }
    function onInput(event) {
      clearTimeout(this.inputTimeout);
      this.inputTimeout = setTimeout(checkOverflow, 100);
    }
    function onKeyDown(event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        document.execCommand('insertHTML', false, '<br>');
        checkOverflow();
      }
    }
    function initializeEditor() {
      let firstContent = document.querySelector('.page-content');
      firstContent.addEventListener('input', onInput);
      firstContent.addEventListener('keydown', onKeyDown);
      firstContent.focus();
    }
    window.getEditorContent = function() {
      let content = '';
      document.querySelectorAll('.page-content').forEach(page => content += page.innerText + '\\n\\n');
      return content;
    };
    window.setEditorContent = function(content) {
      let firstContent = document.querySelector('.page-content');
      firstContent.innerHTML = content.replace(/\\n/g, '<br>');
      checkOverflow();
    };
    window.addEventListener('load', initializeEditor);
  </script>
</body>
</html>
        """
        with open(self.html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def on_save_clicked(self, button):
        self.webview.evaluate_javascript(
            "getEditorContent()", -1, None, None, None,
            self.on_get_content_finished, None
        )
    
    def on_get_content_finished(self, webview, result, user_data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                content = js_result.get_js_value().to_string()
                self.show_save_dialog(content)
        except Exception as e:
            self.show_error_dialog(str(e))
    
    def show_save_dialog(self, content):
        dialog = Gtk.FileChooserDialog(
            title="Save Document",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.ACCEPT)
        dialog.set_current_name("Untitled.txt")
        dialog.connect("response", self.on_save_dialog_response, content)
        dialog.show()
    
    def on_save_dialog_response(self, dialog, response, content):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                file_path = file.get_path()
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.show_toast("Document saved successfully")
                except Exception as e:
                    self.show_error_dialog(str(e))
        dialog.destroy()
    
    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        toast_overlay = Adw.ToastOverlay.new()
        toast_overlay.set_child(self.get_content())
        self.set_content(toast_overlay)
        toast_overlay.add_toast(toast)
    
    def show_error_dialog(self, error):
        error_dialog = Gtk.AlertDialog.new("Error saving file")
        error_dialog.set_detail(error)
        error_dialog.show(self)
    
    def __del__(self):
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()

class EditorApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.paginatededitor")
        self.connect("activate", self.on_activate)
    
    def on_activate(self, app):
        window = PaginatedEditorWindow(application=app)
        window.present()
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_action)
        self.add_action(about_action)
    
    def on_about_action(self, action, param):
        about = Adw.AboutWindow(
            application_name="Paginated Editor",
            application_icon="text-editor-symbolic",
            developer_name="PyGObject Developer",
            version="1.0",
            copyright="© 2025",
            license_type=Gtk.License.GPL_3_0,
            transient_for=self.get_active_window()
        )
        about.present()

def main():
    app = EditorApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()

