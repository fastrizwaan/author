#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
from gi.repository import Gtk, Adw, WebKit, GLib, Gio
import os
import sys
import tempfile

class PaginatedEditorWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Setup window properties
        self.set_default_size(800, 850)
        self.set_title("Paginated Editor")
        
        # Create main box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Create header bar
        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton()
        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu_button.set_menu_model(menu)
        menu_button.set_icon_name("open-menu-symbolic")
        header.pack_end(menu_button)
        
        # Create save button
        save_button = Gtk.Button(icon_name="document-save-symbolic")
        save_button.connect("clicked", self.on_save_clicked)
        header.pack_start(save_button)
        
        self.main_box.append(header)
        
        # Create WebKit editor
        self.create_editor()
        
        # Set up the window content
        self.set_content(self.main_box)
        
        # Create temp directory for editing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.html_path = os.path.join(self.temp_dir.name, "editor.html")
        self.create_editor_html()
        
        # Load the editor
        self.webview.load_uri(f"file://{self.html_path}")
    
    def create_editor(self):
        # Create WebKit webview
        self.webview = WebKit.WebView()
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)
        
        # Allow WebKit to edit content
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_javascript_can_access_clipboard(True)
        
        # Wrap webview in a scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_child(self.webview)
        
        self.main_box.append(scrolled_window)
    
    def create_editor_html(self):
        # Create the HTML for the paginated editor
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Paginated Editor</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
            font-family: 'Cantarell', sans-serif;
        }
        
        #editor {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            min-height: 100vh;
        }
        
        .page {
            width: 8.5in;
            height: 11in;
            background-color: white;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
            margin-bottom: 20px;
            padding: 1in;
            box-sizing: border-box;
            position: relative;
            overflow: hidden;
        }
        
        .page-content {
            width: 100%;
            height: 100%;
            outline: none;
            border: none;
            font-family: 'Cantarell', sans-serif;
            font-size: 12pt;
            line-height: 1.5;
        }
        
        /* Hide scrollbars but keep functionality */
        .page-content::-webkit-scrollbar {
            display: none;
        }
        
        .page-number {
            position: absolute;
            bottom: 0.5in;
            right: 0.5in;
            font-size: 10pt;
            color: #888;
        }
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
        // Global variables
        let pages = document.querySelectorAll('.page');
        const editor = document.getElementById('editor');
        
        // Function to calculate content height
        function getContentHeight(element) {
            const clone = element.cloneNode(true);
            clone.style.visibility = 'hidden';
            clone.style.position = 'absolute';
            clone.style.height = 'auto';
            document.body.appendChild(clone);
            const height = clone.scrollHeight;
            document.body.removeChild(clone);
            return height;
        }
        
        // Function to check if content overflows
        function checkOverflow() {
            const pageContent = document.querySelectorAll('.page-content');
            
            // Check each page for overflow
            pageContent.forEach((content, index) => {
                // Skip the last page (we'll handle that separately)
                if (index === pageContent.length - 1) return;
                
                const maxHeight = content.clientHeight;
                
                while (content.scrollHeight > maxHeight) {
                    // Get the last child element or text node
                    let lastNode = content.lastChild;
                    
                    if (!lastNode) break;
                    
                    if (lastNode.nodeType === Node.TEXT_NODE) {
                        // Handle text nodes
                        const text = lastNode.textContent;
                        const words = text.split(' ');
                        
                        if (words.length > 1) {
                            // Move last word to next page
                            const lastWord = words.pop();
                            lastNode.textContent = words.join(' ');
                            moveContentToNextPage(lastWord, index);
                        } else {
                            // Move entire text node
                            content.removeChild(lastNode);
                            moveContentToNextPage(text, index);
                        }
                    } else {
                        // Move element to next page
                        content.removeChild(lastNode);
                        moveContentToNextPage(lastNode, index);
                    }
                }
            });
            
            // Check if we need to add a new page
            const lastPage = pages[pages.length - 1];
            const lastContent = lastPage.querySelector('.page-content');
            
            if (lastContent.scrollHeight > lastContent.clientHeight) {
                addNewPage();
            }
            
            // Check if we need to remove empty pages
            checkForEmptyPages();
        }
        
        // Function to move content to the next page
        function moveContentToNextPage(content, fromPageIndex) {
            const nextPageContent = pages[fromPageIndex + 1].querySelector('.page-content');
            
            // Insert at the beginning of next page
            if (typeof content === 'string') {
                // Insert text at the beginning
                const textNode = document.createTextNode(content + ' ');
                if (nextPageContent.firstChild) {
                    nextPageContent.insertBefore(textNode, nextPageContent.firstChild);
                } else {
                    nextPageContent.appendChild(textNode);
                }
            } else {
                // Insert node at the beginning
                if (nextPageContent.firstChild) {
                    nextPageContent.insertBefore(content, nextPageContent.firstChild);
                } else {
                    nextPageContent.appendChild(content);
                }
            }
            
            // Recursively check if next page now overflows
            setTimeout(checkOverflow, 0);
        }
        
        // Function to add a new page
        function addNewPage() {
            const pageCount = pages.length;
            
            // Create new page
            const newPage = document.createElement('div');
            newPage.className = 'page';
            
            // Create page content
            const newContent = document.createElement('div');
            newContent.className = 'page-content';
            newContent.contentEditable = 'true';
            newContent.addEventListener('input', onInput);
            newContent.addEventListener('keydown', onKeyDown);
            
            // Create page number
            const newPageNumber = document.createElement('div');
            newPageNumber.className = 'page-number';
            newPageNumber.textContent = pageCount + 1;
            
            // Add elements to page
            newPage.appendChild(newContent);
            newPage.appendChild(newPageNumber);
            
            // Add page to editor
            editor.appendChild(newPage);
            
            // Update pages array
            pages = document.querySelectorAll('.page');
            
            // Recheck overflow to distribute content
            checkOverflow();
        }
        
        // Function to check for and remove empty pages
        function checkForEmptyPages() {
            // Skip if there's only one page
            if (pages.length <= 1) return;
            
            // Start from the second-to-last page and go backwards
            for (let i = pages.length - 2; i >= 0; i--) {
                const content = pages[i].querySelector('.page-content');
                const nextContent = pages[i + 1].querySelector('.page-content');
                
                // If this page is empty and there's a next page with content
                if (!content.textContent.trim() && nextContent.textContent.trim()) {
                    // Remove this empty page
                    editor.removeChild(pages[i]);
                    
                    // Update pages array
                    pages = document.querySelectorAll('.page');
                    
                    // Update page numbers
                    updatePageNumbers();
                    
                    // Recheck from the beginning
                    setTimeout(checkForEmptyPages, 0);
                    return;
                }
            }
            
            // Check if last page is empty (except if it's the only page)
            if (pages.length > 1) {
                const lastContent = pages[pages.length - 1].querySelector('.page-content');
                if (!lastContent.textContent.trim()) {
                    editor.removeChild(pages[pages.length - 1]);
                    pages = document.querySelectorAll('.page');
                    updatePageNumbers();
                }
            }
        }
        
        // Function to update page numbers
        function updatePageNumbers() {
            const pageNumbers = document.querySelectorAll('.page-number');
            pageNumbers.forEach((num, index) => {
                num.textContent = index + 1;
            });
        }
        
        // Event handler for input events
        function onInput(event) {
            // Debounce to avoid too many recalculations
            clearTimeout(this.inputTimeout);
            this.inputTimeout = setTimeout(() => {
                checkOverflow();
            }, 100);
        }
        
        // Event handler for keydown events
        function onKeyDown(event) {
            // If Enter is pressed, prevent default and insert a proper break
            if (event.key === 'Enter') {
                event.preventDefault();
                document.execCommand('insertHTML', false, '<br>');
                checkOverflow();
            }
        }
        
        // Initialize event listeners
        function initializeEditor() {
            const firstContent = document.querySelector('.page-content');
            firstContent.addEventListener('input', onInput);
            firstContent.addEventListener('keydown', onKeyDown);
            firstContent.focus();
        }
        
        // Function to get all content as plain text
        window.getEditorContent = function() {
            let content = '';
            const contents = document.querySelectorAll('.page-content');
            contents.forEach(page => {
                content += page.innerText + '\\n\\n';
            });
            return content;
        };
        
        // Function to set content
        window.setEditorContent = function(content) {
            const firstContent = document.querySelector('.page-content');
            firstContent.innerHTML = content.replace(/\\n/g, '<br>');
            checkOverflow();
        };
        
        // Initialize the editor
        window.addEventListener('load', initializeEditor);
    </script>
</body>
</html>
        """
        
        # Write HTML to file
        with open(self.html_path, 'w') as f:
            f.write(html_content)
    
    def on_save_clicked(self, button):
        # Execute JavaScript to get content
        self.webview.evaluate_javascript("getEditorContent()", -1, None, None, None, self.on_get_content_finished, None)
    
    def on_get_content_finished(self, webview, result, user_data):
        js_result = webview.evaluate_javascript_finish(result)
        if js_result:
            content = js_result.get_js_value().to_string()
            dialog = Gtk.FileChooserDialog(
                title="Save Document",
                transient_for=self,
                action=Gtk.FileChooserAction.SAVE
            )
            dialog.add_buttons(
                "_Cancel", Gtk.ResponseType.CANCEL,
                "_Save", Gtk.ResponseType.ACCEPT
            )
            dialog.set_current_name("Untitled.txt")
            dialog.connect("response", self.on_save_dialog_response, content)
            dialog.show()
    
    def on_save_dialog_response(self, dialog, response, content):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            try:
                with open(file_path, 'w') as f:
                    f.write(content)
                # Show a toast notification for successful save
                toast = Adw.Toast.new("Document saved successfully")
                toast_overlay = Adw.ToastOverlay.new()
                toast_overlay.set_child(self.get_content())
                self.set_content(toast_overlay)
                toast_overlay.add_toast(toast)
            except Exception as e:
                error_dialog = Gtk.AlertDialog.new("Error saving file")
                error_dialog.set_detail(str(e))
                error_dialog.show(self)
        dialog.destroy()
    
    def __del__(self):
        # Clean up temporary files
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()

class EditorApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.paginatededitor")
        self.connect("activate", self.on_activate)
    
    def on_activate(self, app):
        window = PaginatedEditorWindow(application=app)
        window.present()
        
        # Set up about action
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
