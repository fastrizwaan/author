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
        
        # Window setup
        self.set_default_size(800, 850)
        self.set_title("Paginated Editor")
        
        # Main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header bar with buttons
        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton()
        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu_button.set_menu_model(menu)
        menu_button.set_icon_name("open-menu-symbolic")
        header.pack_end(menu_button)
        
        save_button = Gtk.Button(icon_name="document-save-symbolic")
        save_button.connect("clicked", self.on_save_clicked)
        header.pack_start(save_button)
        
        save_html_button = Gtk.Button(label="Save HTML")
        save_html_button.connect("clicked", self.on_save_html_clicked)
        header.pack_start(save_html_button)
        
        self.main_box.append(header)
        
        # WebView editor
        self.create_editor()
        self.set_content(self.main_box)
        
        # Temporary files setup
        self.temp_dir = tempfile.TemporaryDirectory()
        self.html_path = os.path.join(self.temp_dir.name, "editor.html")
        self.create_editor_html()
        self.webview.load_uri(f"file://{self.html_path}")
    
    def create_editor(self):
        """Initialize WebKit WebView for editor content"""
        self.webview = WebKit.WebView()
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)
        
        # Configure editor settings
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_javascript_can_access_clipboard(True)
        
        # Scrolling container
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_child(self.webview)
        self.main_box.append(scrolled_window)
    
    def create_editor_html(self):
        """Create the HTML structure for the paginated editor"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Paginated Editor</title>
    <style>
        body { margin: 0; padding: 0; background-color: #f0f0f0; font-family: 'Cantarell', sans-serif; }
        #editor { display: flex; flex-direction: column; align-items: center; padding: 20px; min-height: 100vh; }
        .page { width: 8.5in; height: 11in; background-color: white; box-shadow: 0 0 10px rgba(0,0,0,0.2); 
                margin-bottom: 20px; padding: 1in; box-sizing: border-box; position: relative; overflow: hidden; }
        .page-content { width: 100%; height: 100%; outline: none; border: none; 
                       font-family: 'Cantarell', sans-serif; font-size: 12pt; line-height: 1.5; }
        .page-content::-webkit-scrollbar { display: none; }
        .page-number { position: absolute; bottom: 0.5in; right: 0.5in; font-size: 10pt; color: #888; }
        @media print {
            body { background-color: white; }
            #editor { padding: 0; }
            .page { box-shadow: none; margin: 0; padding: 0; page-break-after: always; }
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
        let pages = document.querySelectorAll('.page');
        const editor = document.getElementById('editor');
        let lastActivePage = 0;
        let isRedistributing = false;
        let isProcessing = false;
        
        function logPageContents() {
            console.log("--- Page Contents ---");
            document.querySelectorAll('.page-content').forEach((content, i) => {
                console.log(`Page ${i+1}: ${content.textContent.substring(0, 30)}... (${content.scrollHeight}/${content.clientHeight})`);
            });
        }

        function checkOverflow() {
            if (isProcessing) return;
            isProcessing = true;
            
            const savedSelection = saveSelection();
            
            // First, check if we need to pull content back from next pages
            redistributeContent();
            
            // Then handle overflow to push content forward
            document.querySelectorAll('.page-content').forEach((content, index) => {
                if (index === pages.length - 1) return;
                
                const maxHeight = content.clientHeight;
                while (content.scrollHeight > maxHeight) {
                    const lastNode = content.lastChild;
                    if (!lastNode) break;

                    if (lastNode.nodeType === Node.TEXT_NODE) {
                        const text = lastNode.textContent;
                        const words = text.split(' ');
                        if (words.length > 1) {
                            const lastWord = words.pop();
                            lastNode.textContent = words.join(' ');
                            moveContentToNextPage(lastWord, index);
                        } else {
                            content.removeChild(lastNode);
                            moveContentToNextPage(text, index);
                        }
                    } else {
                        content.removeChild(lastNode);
                        moveContentToNextPage(lastNode, index);
                    }
                }
            });

            // Check if new page needed
            const lastContent = pages[pages.length-1].querySelector('.page-content');
            if (lastContent.scrollHeight > lastContent.clientHeight) {
                addNewPage();
            }

            checkForEmptyPages();
            restoreSelection(savedSelection);
            
            isProcessing = false;
        }

        function redistributeContent() {
            if (isRedistributing) return;
            isRedistributing = true;
            
            for (let i = 0; i < pages.length - 1; i++) {
                const currentContent = pages[i].querySelector('.page-content');
                const nextContent = pages[i+1].querySelector('.page-content');
                
                // Skip if next page is empty
                if (!nextContent.hasChildNodes()) continue;
                
                // Check if current page has space
                const currentHeight = currentContent.scrollHeight;
                const maxHeight = currentContent.clientHeight;
                
                // While there's space in current page and content in next page
                let iterations = 0;
                while (currentHeight < maxHeight * 0.95 && nextContent.hasChildNodes() && iterations < 100) {
                    iterations++;
                    
                    // Pull first node from next page to current page
                    const firstNode = nextContent.firstChild;
                    if (!firstNode) break;
                    
                    const originalHeight = currentContent.scrollHeight;
                    
                    // Clone the node first to measure if it would fit
                    const cloneNode = firstNode.cloneNode(true);
                    currentContent.appendChild(cloneNode);
                    
                    // Check if adding this node caused overflow
                    if (currentContent.scrollHeight > maxHeight) {
                        // If it caused overflow, remove the clone
                        currentContent.removeChild(cloneNode);
                        break;
                    } else {
                        // It fits, so remove the clone and move the real node
                        currentContent.removeChild(cloneNode);
                        nextContent.removeChild(firstNode);
                        currentContent.appendChild(firstNode);
                    }
                    
                    // Break out if no more space was used - likely at a natural boundary
                    if (currentContent.scrollHeight <= originalHeight) {
                        break;
                    }
                }
            }
            
            isRedistributing = false;
        }

        function saveSelection() {
            const selection = window.getSelection();
            if (selection.rangeCount === 0) return null;
            
            const range = selection.getRangeAt(0);
            const pageContents = document.querySelectorAll('.page-content');
            let selectionPage = -1;
            
            for (let i = 0; i < pageContents.length; i++) {
                if (pageContents[i].contains(range.commonAncestorContainer)) {
                    selectionPage = i;
                    break;
                }
            }
            return selectionPage === -1 ? null : { page: selectionPage, range: range.cloneRange() };
        }

        function restoreSelection(savedSelection) {
            const pageContents = document.querySelectorAll('.page-content');
            const selection = window.getSelection();
            selection.removeAllRanges();

            if (!savedSelection || !tryRestoreSelection(savedSelection)) {
                // Smart cursor positioning
                const targetPage = Math.min(lastActivePage, pageContents.length - 1);
                const targetContent = pageContents[targetPage];
                
                if (targetContent.childNodes.length > 0) {
                    placeCursorAtEnd(targetContent);
                } else {
                    placeCursorAtBeginning(targetContent);
                }
                scrollToPage(targetPage);
            }
        }

        function tryRestoreSelection(savedSelection) {
            try {
                if (savedSelection.page >= pages.length) return false;
                const content = pages[savedSelection.page].querySelector('.page-content');
                if (!content.contains(savedSelection.range.startContainer)) return false;
                
                window.getSelection().addRange(savedSelection.range);
                lastActivePage = savedSelection.page;
                return true;
            } catch(e) {
                return false;
            }
        }

        function moveContentToNextPage(content, fromPageIndex) {
            const nextPage = pages[fromPageIndex + 1];
            const nextContent = nextPage.querySelector('.page-content');

            if (typeof content === 'string') {
                const textNode = document.createTextNode(content + ' ');
                nextContent.prepend(textNode);
            } else {
                nextContent.prepend(content);
            }

            // Update cursor position if needed
            if (lastActivePage === fromPageIndex) {
                const selection = window.getSelection();
                if (selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    const currentContent = pages[fromPageIndex].querySelector('.page-content');
                    
                    if (isSelectionAtEnd(currentContent, range)) {
                        lastActivePage = fromPageIndex + 1;
                        placeCursorAtBeginning(nextContent);
                        scrollToPage(lastActivePage);
                    }
                }
            }
        }

        function isSelectionAtEnd(element, range) {
            if (!element.hasChildNodes()) return true;
            const lastNode = element.lastChild;
            return range.endContainer === lastNode && 
                   range.endOffset === (lastNode.nodeType === Node.TEXT_NODE ? lastNode.length : lastNode.childNodes.length);
        }

        function addNewPage() {
            const newPage = document.createElement('div');
            newPage.className = 'page';
            
            const newContent = document.createElement('div');
            newContent.className = 'page-content';
            newContent.contentEditable = 'true';
            
            const pageNumber = document.createElement('div');
            pageNumber.className = 'page-number';
            pageNumber.textContent = pages.length + 1;
            
            newPage.append(newContent, pageNumber);
            editor.appendChild(newPage);
            
            // Add event listeners to new page
            newContent.addEventListener('input', onInput);
            newContent.addEventListener('keydown', onKeyDown);
            newContent.addEventListener('focus', () => {
                lastActivePage = Array.from(pages).findIndex(page => 
                    page.querySelector('.page-content') === newContent);
            });
            
            pages = document.querySelectorAll('.page');
            updatePageNumbers();
        }

        function checkForEmptyPages() {
            if (pages.length <= 1) return;
            
            for (let i = pages.length - 2; i >= 0; i--) {
                const content = pages[i].querySelector('.page-content');
                const nextContent = pages[i+1].querySelector('.page-content');
                
                if (!content.textContent.trim() && nextContent.textContent.trim()) {
                    editor.removeChild(pages[i]);
                    pages = document.querySelectorAll('.page');
                    updatePageNumbers();
                    return;
                }
            }
        }

        function updatePageNumbers() {
            document.querySelectorAll('.page-number').forEach((num, index) => {
                num.textContent = index + 1;
            });
        }

        function placeCursorAtEnd(element) {
            const range = document.createRange();
            range.selectNodeContents(element);
            range.collapse(false);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            element.focus();
        }

        function placeCursorAtBeginning(element) {
            const range = document.createRange();
            if (element.firstChild) {
                range.setStart(element.firstChild, 0);
                range.setEnd(element.firstChild, 0);
            } else {
                range.setStart(element, 0);
                range.setEnd(element, 0);
            }
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            element.focus();
        }

        function scrollToPage(pageIndex) {
            if (pageIndex >= 0 && pageIndex < pages.length) {
                pages[pageIndex].scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        // Event handlers
        function onInput(event) {
            clearTimeout(this.inputTimeout);
            this.inputTimeout = setTimeout(checkOverflow, 100);
        }

        function onKeyDown(event) {
            // Special handling for backspace and delete to ensure content redistribution
            if (event.key === 'Backspace' || event.key === 'Delete') {
                // Run after the browser has processed the key event
                setTimeout(() => {
                    // Force redistribution of content immediately
                    checkOverflow();
                }, 0);
            }
            
            if (event.key === 'Enter') {
                event.preventDefault();
                const selection = window.getSelection();
                const range = selection.getRangeAt(0);
                const br = document.createElement('br');
                range.deleteContents();
                range.insertNode(br);
                range.setStartAfter(br);
                range.setEndAfter(br);
                selection.removeAllRanges();
                selection.addRange(range);
                checkOverflow();
            }
        }

        // Initialization
        window.getEditorContent = () => {
            return Array.from(document.querySelectorAll('.page-content'))
                   .map(page => page.innerText)
                   .join('\\n\\n');
        };
        
        window.getEditorHtml = () => {
            const clone = document.getElementById('editor').cloneNode(true);
            
            // Make content non-editable for export
            Array.from(clone.querySelectorAll('.page-content')).forEach(content => {
                content.contentEditable = 'false';
            });
            
            // Wrap in HTML document
            return `<!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Exported Document</title>
                <style>
                    body { margin: 0; padding: 0; background-color: white; font-family: 'Cantarell', sans-serif; }
                    #editor { display: flex; flex-direction: column; align-items: center; }
                    .page { width: 8.5in; height: 11in; background-color: white;
                            margin-bottom: 20px; padding: 1in; box-sizing: border-box; position: relative; overflow: hidden; }
                    .page-content { width: 100%; height: 100%; font-family: 'Cantarell', sans-serif; font-size: 12pt; line-height: 1.5; }
                    .page-number { position: absolute; bottom: 0.5in; right: 0.5in; font-size: 10pt; color: #888; }
                    @media print {
                        .page { box-shadow: none; margin: 0; padding: 1in; page-break-after: always; }
                    }
                </style>
            </head>
            <body>
                ${clone.outerHTML}
            </body>
            </html>`;
        };

        window.setEditorContent = (content) => {
            const firstContent = document.querySelector('.page-content');
            firstContent.innerHTML = content.replace(/\\n/g, '<br>');
            checkOverflow();
        };

        window.addEventListener('load', () => {
            document.querySelectorAll('.page-content').forEach(content => {
                content.addEventListener('input', onInput);
                content.addEventListener('keydown', onKeyDown);
                content.addEventListener('focus', function() {
                    lastActivePage = Array.from(pages).findIndex(page => 
                        page.querySelector('.page-content') === this);
                });
            });
            placeCursorAtEnd(document.querySelector('.page-content'));
        });
    </script>
</body>
</html>
        """
        with open(self.html_path, 'w') as f:
            f.write(html_content)

    def on_save_clicked(self, button):
        self.webview.evaluate_javascript(
            "getEditorContent()", -1, None, None, None,
            self.on_get_content_finished, None
        )

    def on_save_html_clicked(self, button):
        self.webview.evaluate_javascript(
            "getEditorHtml()", -1, None, None, None,
            self.on_get_html_finished, None
        )

    def on_get_content_finished(self, webview, result, user_data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                content = js_result.to_string()
                self.show_save_dialog("Save Document", "Untitled.txt", content, self.on_save_dialog_response)
        except Exception as e:
            self.show_error("Error getting content", str(e))

    def on_get_html_finished(self, webview, result, user_data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                html_content = js_result.to_string()
                self.show_save_dialog("Save HTML Document", "Document.html", html_content, self.on_save_html_dialog_response)
        except Exception as e:
            self.show_error("Error getting HTML content", str(e))

    def show_save_dialog(self, title, default_name, content, callback):
        dialog = Gtk.FileChooserDialog(
            title=title,
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Save", Gtk.ResponseType.ACCEPT
        )
        dialog.set_current_name(default_name)
        dialog.connect("response", callback, content)
        dialog.show()

    def show_error(self, title, message):
        error_dialog = Gtk.AlertDialog.new(title)
        error_dialog.set_detail(message)
        error_dialog.show(self)

    def on_save_dialog_response(self, dialog, response, content):
        if response == Gtk.ResponseType.ACCEPT:
            try:
                file = dialog.get_file()
                with open(file.get_path(), 'w') as f:
                    f.write(content)
                toast = Adw.Toast.new("Document saved successfully")
                toast_overlay = Adw.ToastOverlay.new()
                toast_overlay.set_child(self.get_content())
                self.set_content(toast_overlay)
                toast_overlay.add_toast(toast)
            except Exception as e:
                self.show_error("Error saving file", str(e))
        dialog.destroy()

    def on_save_html_dialog_response(self, dialog, response, html_content):
        if response == Gtk.ResponseType.ACCEPT:
            try:
                file = dialog.get_file()
                with open(file.get_path(), 'w') as f:
                    f.write(html_content)
                toast = Adw.Toast.new("HTML document saved successfully")
                toast_overlay = Adw.ToastOverlay.new()
                toast_overlay.set_child(self.get_content())
                self.set_content(toast_overlay)
                toast_overlay.add_toast(toast)
            except Exception as e:
                self.show_error("Error saving HTML file", str(e))
        dialog.destroy()


    def on_save_clicked(self, button):
        self.webview.evaluate_javascript(
            "getEditorContent()", -1, None, None, None,
            self.on_get_content_finished, None
        )

    def on_save_html_clicked(self, button):
        self.webview.evaluate_javascript(
            "getEditorHtml()", -1, None, None, None,
            self.on_get_html_finished, None
        )

    def on_get_content_finished(self, webview, result, user_data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                content = js_result.to_string()
                self.show_save_dialog("Save Document", "Untitled.txt", content, self.on_save_dialog_response)
        except Exception as e:
            self.show_error("Error getting content", str(e))

    def on_get_html_finished(self, webview, result, user_data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result:
                html_content = js_result.to_string()
                self.show_save_dialog("Save HTML Document", "Document.html", html_content, self.on_save_html_dialog_response)
        except Exception as e:
            self.show_error("Error getting HTML content", str(e))

    def show_save_dialog(self, title, default_name, content, callback):
        dialog = Gtk.FileChooserDialog(
            title=title,
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Save", Gtk.ResponseType.ACCEPT
        )
        dialog.set_current_name(default_name)  # Still needed though deprecated
        dialog.connect("response", callback, content)
        dialog.present()  # Use present() instead of show()

    def show_error(self, title, message):
        error_dialog = Gtk.AlertDialog.new(title)
        error_dialog.set_detail(message)
        error_dialog.present(self)  # Use present() instead of show()

    def on_save_dialog_response(self, dialog, response, content):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            GLib.idle_add(self.save_file_async, file_path, content, "Document saved successfully")
        dialog.destroy()

    def on_save_html_dialog_response(self, dialog, response, html_content):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            GLib.idle_add(self.save_file_async, file_path, html_content, "HTML document saved successfully")
        dialog.destroy()

    def save_file_async(self, file_path, content, success_message):
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            
            # Create and show toast on main thread
            GLib.idle_add(self.show_success_toast, success_message)
        except Exception as e:
            GLib.idle_add(self.show_error, "Error saving file", str(e))
        return False  # Important: return False to remove from idle queue

    def show_success_toast(self, message):
        # Create a toast with the success message
        toast = Adw.Toast.new(message)
        
        # Get current content and its parent
        current_content = self.get_content()
        parent = current_content.get_parent()
        
        # If parent is already a toast overlay, use it
        if isinstance(parent, Adw.ToastOverlay):
            parent.add_toast(toast)
        else:
            # Otherwise, create a new toast overlay and set it up
            toast_overlay = Adw.ToastOverlay.new()
            # First set the child on the new overlay
            toast_overlay.set_child(current_content)
            # Then set the overlay as the window content
            self.set_content(toast_overlay)
            # Finally add the toast
            toast_overlay.add_toast(toast)
        
        return False  # Important: return False to remove from idle queue





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
            developer_name="Your Name",
            version="1.0",
            copyright="© 2024",
            license_type=Gtk.License.GPL_3_0,
            transient_for=self.get_active_window()
        )
        about.present()

def main():
    app = EditorApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
