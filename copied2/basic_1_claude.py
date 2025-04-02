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
        }
        
        .page-content {
            width: 100%;
            height: 100%;
            outline: none;
            border: none;
            font-family: 'Cantarell', sans-serif;
            font-size: 12pt;
            line-height: 1.5;
            overflow: hidden;
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
        let activePageIndex = 0; // Track active page
        let isReflowing = false; // Prevent recursive reflow
        let caretPosition = {
            pageIndex: 0,
            node: null,
            offset: 0
        };
        
        // Function to save caret position
        function saveCaretPosition() {
            const selection = window.getSelection();
            if (selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                const startNode = range.startContainer;
                const startOffset = range.startOffset;
                
                // Find which page contains this node
                let pageIndex = 0;
                const pageContents = document.querySelectorAll('.page-content');
                
                for (let i = 0; i < pageContents.length; i++) {
                    if (pageContents[i].contains(startNode) || pageContents[i] === startNode) {
                        pageIndex = i;
                        break;
                    }
                }
                
                caretPosition = {
                    pageIndex: pageIndex,
                    node: startNode,
                    offset: startOffset
                };
                
                activePageIndex = pageIndex;
            }
        }
        
        // Function to restore caret position after reflow
        function restoreCaretPosition() {
            try {
                const pageContents = document.querySelectorAll('.page-content');
                
                // Check if the saved page index is still valid
                if (caretPosition.pageIndex >= pageContents.length) {
                    caretPosition.pageIndex = pageContents.length - 1;
                }
                
                // Get the target page content
                const targetPage = pageContents[caretPosition.pageIndex];
                
                // If we have a saved node and it's still in the document
                if (caretPosition.node && document.contains(caretPosition.node)) {
                    // Create a new range
                    const range = document.createRange();
                    const selection = window.getSelection();
                    
                    // Try to set the range to the saved position
                    try {
                        range.setStart(caretPosition.node, caretPosition.offset);
                        range.collapse(true);
                        
                        // Clear existing selection and add our range
                        selection.removeAllRanges();
                        selection.addRange(range);
                        
                        // Ensure the page with the caret is visible
                        pages[caretPosition.pageIndex].scrollIntoView({
                            behavior: 'smooth', 
                            block: 'center'
                        });
                    } catch (e) {
                        // If setting the range failed, just focus the page
                        targetPage.focus();
                    }
                } else {
                    // If the node is no longer valid, just focus on the target page
                    targetPage.focus();
                }
            } catch (e) {
                console.error("Error restoring caret position:", e);
                // As a fallback, focus the first page
                document.querySelector('.page-content').focus();
            }
        }
        
        // Calculate maximum content height for a page (accounting for padding)
        function getMaxHeight() {
            const page = document.querySelector('.page');
            const pageContent = page.querySelector('.page-content');
            return pageContent.clientHeight;
        }
        
        // Function to check if content overflows
        function checkOverflow() {
            if (isReflowing) return; // Prevent recursive calls
            isReflowing = true;
            
            // Save current caret position before reflowing
            saveCaretPosition();
            
            const pageContents = document.querySelectorAll('.page-content');
            const maxHeight = getMaxHeight();
            
            // Process all pages except the last one
            for (let i = 0; i < pageContents.length - 1; i++) {
                const content = pageContents[i];
                
                // Check if this page overflows
                while (content.scrollHeight > maxHeight) {
                    // Get the last node of this page
                    const lastNode = content.lastChild;
                    if (!lastNode) break;
                    
                    // Remove it from this page
                    content.removeChild(lastNode);
                    
                    // Add it to the beginning of the next page
                    const nextPageContent = pageContents[i + 1];
                    if (nextPageContent.firstChild) {
                        nextPageContent.insertBefore(lastNode, nextPageContent.firstChild);
                    } else {
                        nextPageContent.appendChild(lastNode);
                    }
                }
                
                // Check if we can pull content from the next page
                while (content.scrollHeight < maxHeight - 10) { // Leave a small buffer
                    const nextPageContent = pageContents[i + 1];
                    const firstNode = nextPageContent.firstChild;
                    
                    // If next page is empty or adding this node would overflow, break
                    if (!firstNode) break;
                    
                    // Temporarily add node to check if it would overflow
                    nextPageContent.removeChild(firstNode);
                    content.appendChild(firstNode);
                    
                    // If it overflows, put it back
                    if (content.scrollHeight > maxHeight) {
                        content.removeChild(firstNode);
                        nextPageContent.insertBefore(firstNode, nextPageContent.firstChild);
                        break;
                    }
                }
            }
            
            // Check the last page for overflow
            const lastPage = pageContents[pageContents.length - 1];
            if (lastPage.scrollHeight > maxHeight) {
                addNewPage();
                
                // Now move overflowing content to the new page
                const newLastPage = document.querySelector('.page-content:last-child');
                while (lastPage.scrollHeight > maxHeight) {
                    const lastNode = lastPage.lastChild;
                    if (!lastNode) break;
                    
                    lastPage.removeChild(lastNode);
                    if (newLastPage.firstChild) {
                        newLastPage.insertBefore(lastNode, newLastPage.firstChild);
                    } else {
                        newLastPage.appendChild(lastNode);
                    }
                }
            }
            
            // Check if we need to remove empty pages
            checkForEmptyPages();
            
            // Restore caret position after reflowing
            setTimeout(() => {
                restoreCaretPosition();
                isReflowing = false;
            }, 0);
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
            newContent.addEventListener('focus', () => {
                activePageIndex = Array.from(document.querySelectorAll('.page')).length - 1;
            });
            
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
        }
        
        // Function to check for and remove empty pages
        function checkForEmptyPages() {
            // Skip if there's only one page
            if (pages.length <= 1) return;
            
            // Check all pages except the first one
            for (let i = 1; i < pages.length; i++) {
                const content = pages[i].querySelector('.page-content');
                
                // If this page is empty (no content or just whitespace)
                if (!content.textContent.trim() && !content.querySelector('br')) {
                    // Don't remove the very last page if it's the only empty one
                    if (i === pages.length - 1 && pages.length === 2) {
                        continue;
                    }
                    
                    // Remove the empty page
                    editor.removeChild(pages[i]);
                    
                    // Update pages array
                    pages = document.querySelectorAll('.page');
                    
                    // Update page numbers
                    updatePageNumbers();
                    
                    // Update active page index if needed
                    if (activePageIndex >= i) {
                        activePageIndex = Math.max(0, activePageIndex - 1);
                    }
                    
                    // Check again from the beginning
                    checkForEmptyPages();
                    return;
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
        
        // Debounced version of checkOverflow
        let overflowTimer = null;
        function debouncedCheckOverflow() {
            if (overflowTimer) clearTimeout(overflowTimer);
            overflowTimer = setTimeout(() => {
                checkOverflow();
            }, 100);
        }
        
        // Event handler for input events
        function onInput(event) {
            // Save which page is active
            const pageContents = document.querySelectorAll('.page-content');
            for (let i = 0; i < pageContents.length; i++) {
                if (pageContents[i] === event.target) {
                    activePageIndex = i;
                    break;
                }
            }
            
            // Save caret position
            saveCaretPosition();
            
            // Trigger reflow check
            debouncedCheckOverflow();
        }
        
        // Event handler for keydown events
        function onKeyDown(event) {
            // Handle Enter key
            if (event.key === 'Enter') {
                event.preventDefault();
                
                // Save current position
                saveCaretPosition();
                
                // Insert a proper line break
                const selection = window.getSelection();
                if (selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    const br = document.createElement('br');
                    range.deleteContents();
                    range.insertNode(br);
                    
                    // Move caret after the break
                    range.setStartAfter(br);
                    range.collapse(true);
                    selection.removeAllRanges();
                    selection.addRange(range);
                    
                    // Force reflow
                    debouncedCheckOverflow();
                }
                return false;
            }
            
            // Handle page navigation with arrow keys
            if (event.key === 'ArrowUp') {
                const selection = window.getSelection();
                if (selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    const rect = range.getBoundingClientRect();
                    
                    // If at the top of the page and there's a previous page
                    if (rect.top <= event.target.getBoundingClientRect().top + 20 && activePageIndex > 0) {
                        event.preventDefault();
                        // Focus the previous page
                        const prevPage = pages[activePageIndex - 1].querySelector('.page-content');
                        activePageIndex--;
                        prevPage.focus();
                        
                        // Move caret to the end of the previous page
                        const range = document.createRange();
                        range.selectNodeContents(prevPage);
                        range.collapse(false);
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }
                }
            } else if (event.key === 'ArrowDown') {
                const selection = window.getSelection();
                if (selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    const rect = range.getBoundingClientRect();
                    
                    // If at the bottom of the page and there's a next page
                    if (rect.bottom >= event.target.getBoundingClientRect().bottom - 20 && activePageIndex < pages.length - 1) {
                        event.preventDefault();
                        // Focus the next page
                        const nextPage = pages[activePageIndex + 1].querySelector('.page-content');
                        activePageIndex++;
                        nextPage.focus();
                        
                        // Move caret to the beginning of the next page
                        const range = document.createRange();
                        range.selectNodeContents(nextPage);
                        range.collapse(true);
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }
                }
            }
            
            // For all other keys, trigger reflow check after a short delay
            setTimeout(() => {
                debouncedCheckOverflow();
            }, 0);
        }
        
        // Initialize event listeners
        function initializeEditor() {
            // Add focus event listeners to all pages
            document.querySelectorAll('.page-content').forEach((content, index) => {
                content.addEventListener('focus', () => {
                    activePageIndex = index;
                });
                content.addEventListener('click', () => {
                    activePageIndex = index;
                    saveCaretPosition();
                });
                content.addEventListener('input', onInput);
                content.addEventListener('keydown', onKeyDown);
            });
            
            // Focus the first page
            document.querySelector('.page-content').focus();
            
            // Setup continuous overflow checking
            setInterval(() => {
                if (!isReflowing) {
                    checkOverflow();
                }
            }, 2000);
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
