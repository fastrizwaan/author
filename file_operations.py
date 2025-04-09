#!/usr/bin/env python3

import os
import re
import importlib.util
from datetime import datetime
from gi.repository import Gtk, GLib, Gio, WebKit

# Check if markdown package is available
MARKDOWN_AVAILABLE = False
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    pass

# Check if html2text package is available (for HTML to Markdown conversion)
HTML2TEXT_AVAILABLE = False
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    pass

# Open operations
def on_open_clicked(self, win, button):
    """Show open file dialog and decide whether to open in current or new window"""
    dialog = Gtk.FileDialog()
    dialog.set_title("Open Document")
    
    # Create file filters for all supported formats
    filter_html = Gtk.FileFilter()
    filter_html.set_name("HTML files")
    filter_html.add_pattern("*.html")
    filter_html.add_pattern("*.htm")
    filter_html.add_pattern("*.mht")
    filter_html.add_pattern("*.mhtml")
    
    filter_md = Gtk.FileFilter()
    filter_md.set_name("Markdown files")
    filter_md.add_pattern("*.md")
    filter_md.add_pattern("*.markdown")
    
    filter_txt = Gtk.FileFilter()
    filter_txt.set_name("Text files")
    filter_txt.add_pattern("*.txt")
    
    filter_all = Gtk.FileFilter()
    filter_all.set_name("All files")
    filter_all.add_pattern("*")
    
    filter_list = Gio.ListStore.new(Gtk.FileFilter)
    filter_list.append(filter_html)
    filter_list.append(filter_md)
    filter_list.append(filter_txt)
    filter_list.append(filter_all)
    
    dialog.set_filters(filter_list)
    
    # If no changes made and no file is open, open in current window, otherwise open in new window
    if win.modified or win.current_file:
        dialog.open(win, None, lambda dialog, result: self.on_open_new_window_response(win, dialog, result))
    else:
        dialog.open(win, None, lambda dialog, result: self.on_open_current_window_response(win, dialog, result))

def on_open_new_window_response(self, win, dialog, result):
    """Handle open file dialog response to open in a new window"""
    try:
        file = dialog.open_finish(result)
        if file:
            filepath = file.get_path()
            # Create a new window for the file
            new_win = self.create_window()
            self.load_file(new_win, filepath)
            new_win.present()
            self.update_window_menu()
    except GLib.Error as e:
        if e.domain != 'gtk-dialog-error-quark' or e.code != 2:  # Ignore cancel
            self.show_error_dialog(f"Error opening file: {e}")

def on_open_current_window_response(self, win, dialog, result):
    """Handle open file dialog response to open in current window"""
    try:
        file = dialog.open_finish(result)
        if file:
            filepath = file.get_path()
            self.load_file(win, filepath)
            win.statusbar.set_text(f"Opened {os.path.basename(filepath)}")
    except GLib.Error as e:
        if e.domain != 'gtk-dialog-error-quark' or e.code != 2:  # Ignore cancel
            self.show_error_dialog(f"Error opening file: {e}")

def load_file(self, win, filepath):
    """Load file content into editor with support for various formats"""
    try:
        # Store the original file path format for reference
        win.original_format = os.path.splitext(filepath)[1].lower()
        
        # Try to detect file encoding
        encoding = 'utf-8'  # Default encoding
        try:
            import chardet
            with open(filepath, 'rb') as raw_file:
                raw_content = raw_file.read()
                detected = chardet.detect(raw_content)
                if detected['confidence'] > 0.7:
                    encoding = detected['encoding']
        except ImportError:
            pass  # Fallback to utf-8 if chardet not available
            
        # Now read the file with the detected encoding
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError:
            # If there's a decode error, try a fallback encoding
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Determine file type and process accordingly
        file_ext = os.path.splitext(filepath)[1].lower()
        
        if file_ext in ['.mht', '.mhtml']:
            # Handle MHTML files - extract the HTML content
            try:
                import email
                message = email.message_from_string(content)
                for part in message.walk():
                    if part.get_content_type() == 'text/html':
                        content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        break
            except ImportError:
                # Fallback to regex extraction if email module not ideal
                body_match = re.search(r'Content-Type: text/html.*?charset=["\']?([\w-]+)["\']?.*?(?:\r?\n){2}(.*?)(?:\r?\n){1,2}--', 
                                       content, re.DOTALL | re.IGNORECASE)
                if body_match:
                    charset, html_content = body_match.groups()
                    content = html_content
                    
            # Extract body content from the HTML
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = body_match.group(1).strip()
                    
        elif file_ext in ['.html', '.htm']:
            # Handle HTML content
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = body_match.group(1).strip()
                
        elif file_ext in ['.md', '.markdown']:
            # Convert markdown to HTML
            if MARKDOWN_AVAILABLE:
                try:
                    # Get available extensions
                    available_extensions = []
                    for ext in ['tables', 'fenced_code', 'codehilite', 'nl2br', 'sane_lists', 'smarty', 'attr_list']:
                        try:
                            # Test if extension can be loaded
                            markdown.markdown("test", extensions=[ext])
                            available_extensions.append(ext)
                        except (ImportError, ValueError):
                            pass
                    
                    # Convert markdown to HTML
                    content = markdown.markdown(content, extensions=available_extensions)
                except Exception as e:
                    print(f"Error converting markdown: {e}")
                    # Fallback to simple conversion
                    content = _simple_markdown_to_html(content)
            else:
                # Use simplified markdown conversion
                content = _simple_markdown_to_html(content)
        else:  # .txt or other plain text
            # Convert plain text to HTML
            content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            content = f"<div>{content.replace(chr(10), '<br>')}</div>"
        
        # Ensure content is properly wrapped in a div if not already
        if not (content.strip().startswith('<div') or content.strip().startswith('<p') or 
                content.strip().startswith('<h')):
            content = f"<div>{content}</div>"
        
        # Escape for JavaScript
        content = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        js_code = f'setContent("{content}");'
        
        # Check WebView load status and execute JS accordingly
        def execute_when_ready():
            # Get the current load status
            load_status = win.webview.get_estimated_load_progress()
            
            if load_status == 1.0:  # Fully loaded
                # Execute directly
                self.execute_js(win, js_code)
                return False  # Stop the timeout
            else:
                # Set up a handler for when loading finishes
                def on_load_changed(webview, event):
                    if event == WebKit.LoadEvent.FINISHED:
                        self.execute_js(win, js_code)
                        webview.disconnect_by_func(on_load_changed)
                
                win.webview.connect("load-changed", on_load_changed)
                return False  # Stop the timeout
        
        # Use GLib timeout to ensure we're not in the middle of another operation
        GLib.timeout_add(50, execute_when_ready)
        
        # Update file information
        win.current_file = Gio.File.new_for_path(filepath)
        win.modified = False
        self.update_window_title(win)
        win.statusbar.set_text(f"Opened {os.path.basename(filepath)}")
    except Exception as e:
        print(f"Error loading file: {str(e)}")
        win.statusbar.set_text(f"Error loading file: {str(e)}")
        # Call show_error_dialog if it exists
        self.show_error_dialog(f"Error loading file: {e}")

def _simple_markdown_to_html(content):
    """Static method for simple markdown to HTML conversion as fallback"""
    html = content
    
    # Basic markdown conversions
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
    html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html)
    
    # Convert paragraphs
    paragraphs = re.split(r'\n\s*\n', html)
    processed_paragraphs = []
    for p in paragraphs:
        if p.strip() and not p.strip().startswith('<'):
            processed_paragraphs.append(f'<p>{p}</p>')
        else:
            processed_paragraphs.append(p)
    
    html = '\n'.join(processed_paragraphs)
    return html

# Save operations
def on_save_clicked(self, win, button):
    """Handle save button click"""
    if win.current_file:
        # Get the file path
        file_path = win.current_file.get_path()
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Save based on file extension
        if file_ext in ['.mht', '.mhtml']:
            self.save_as_mhtml(win, win.current_file)
        elif file_ext in ['.html', '.htm']:
            self.save_as_html(win, win.current_file)
        elif file_ext in ['.md', '.markdown']:
            self.save_as_markdown(win, win.current_file)
        elif file_ext in ['.txt']:
            self.save_as_text(win, win.current_file)
        else:
            # For unknown extensions, save as MHTML by default
            self.save_as_mhtml(win, win.current_file)
    else:
        # Show save dialog for new file
        self.show_save_dialog(win)

def on_save_as_clicked(self, win, button):
    """Show save as dialog to save current document with a new filename"""
    self.show_save_dialog(win, is_save_as=True)

def show_save_dialog(self, win, is_save_as=False):
    """Show save dialog with appropriate filters"""
    dialog = Gtk.FileDialog()
    dialog.set_title("Save As" if is_save_as else "Save File")
    
    # Create file filters for supported save formats
    filter_mht = Gtk.FileFilter()
    filter_mht.set_name("MHTML files (*.mht)")
    filter_mht.add_pattern("*.mht")
    filter_mht.add_pattern("*.mhtml")
    
    filter_html = Gtk.FileFilter()
    filter_html.set_name("HTML files (*.html)")
    filter_html.add_pattern("*.html")
    filter_html.add_pattern("*.htm")
    
    filter_txt = Gtk.FileFilter()
    filter_txt.set_name("Text files (*.txt)")
    filter_txt.add_pattern("*.txt")
    
    filters = Gio.ListStore.new(Gtk.FileFilter)
    filters.append(filter_mht)  # MHT first as default
    filters.append(filter_html)
    filters.append(filter_txt)
    
    # Only add markdown filter if html2text is available
    if HTML2TEXT_AVAILABLE:
        filter_md = Gtk.FileFilter()
        filter_md.set_name("Markdown files (*.md)")
        filter_md.add_pattern("*.md")
        filter_md.add_pattern("*.markdown")
        filters.append(filter_md)
    
    dialog.set_filters(filters)
    
    # If there's a current file and we're in save-as mode, use its parent directory
    if win.current_file:
        if is_save_as:
            parent_dir = win.current_file.get_parent()
            if parent_dir:
                dialog.set_initial_folder(parent_dir)
        # Use the current file name as the initial filename
        dialog.set_initial_name(os.path.basename(win.current_file.get_path()))
    else:
        # Generate a default filename with current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        dialog.set_initial_name(f"Document - {current_date}.mht")
    
    dialog.save(win, None, lambda dialog, result: self.save_dialog_callback(win, dialog, result))

def save_dialog_callback(self, win, dialog, result):
    """Handle save dialog response"""
    try:
        file = dialog.save_finish(result)
        if file:
            path = file.get_path()
            file_ext = os.path.splitext(path)[1].lower()
            
            # Check if file has an extension, if not, add .mht as default
            if not file_ext:
                path = path + ".mht"
                file = Gio.File.new_for_path(path)
                file_ext = ".mht"
            
            # Save based on file extension
            if file_ext in ['.mht', '.mhtml']:
                self.save_as_mhtml(win, file)
            elif file_ext in ['.html', '.htm']:
                self.save_as_html(win, file)
            elif file_ext in ['.md', '.markdown']:
                self.save_as_markdown(win, file)
            elif file_ext in ['.txt']:
                self.save_as_text(win, file)
            else:
                # For unknown extensions, save as MHTML by default
                self.save_as_mhtml(win, file)
        else:
            # File is None - user canceled the dialog or error occurred
            win.statusbar.set_text("Save canceled or no file selected")
            print("Save dialog: No file selected or dialog canceled")
                
    except GLib.Error as error:
        if error.domain != 'gtk-dialog-error-quark' or error.code != 2:  # Ignore cancel
            print(f"Error saving file: {error.message if hasattr(error, 'message') else str(error)}")
            # Use the existing show_error_dialog method with the right number of arguments
            self.show_error_dialog(f"Error saving file: {error.message if hasattr(error, 'message') else str(error)}")
        else:
            # User canceled the dialog
            win.statusbar.set_text("Save canceled")
    except Exception as e:
        print(f"Unexpected error in save dialog: {e}")
        win.statusbar.set_text(f"Error: {str(e)}")
        # Use existing show_error_dialog with the right number of arguments
        self.show_error_dialog(f"Error saving file: {str(e)}")


def save_as_mhtml(self, win, file):
    """Save document as MHTML using WebKit's save method"""
    try:
        # Get the file URI
        file_uri = file.get_uri()
        
        # Check which WebKit version and methods are available
        if hasattr(win.webview, 'save_to_file'):
            # WebKit 6.0+ method
            win.webview.save_to_file(file, WebKit.SaveMode.MHTML, None, 
                                  lambda webview, result: self.save_webkit_callback(win, file, result))
        elif hasattr(win.webview, 'save'):
            # Older WebKit method
            win.webview.save(WebKit.SaveMode.MHTML, None,  # No cancellable
                          lambda webview, result: self.save_webkit_callback(win, file, result))
        else:
            # Fallback for even older WebKit versions
            print("WebKit save methods not available, falling back to HTML")
            self.save_as_html(win, file)
            return
            
        win.statusbar.set_text(f"Saving MHTML file: {file.get_path()}")
    except Exception as e:
        print(f"Error saving as MHTML: {e}")
        win.statusbar.set_text(f"Error saving MHTML: {e}")
        # Fallback to manual saving
        self.save_as_html(win, file)

def save_webkit_callback(self, win, file, result):
    """Handle WebKit save result"""
    try:
        # Check if this is a WebKit 6.0+ result with get_web_error
        if hasattr(result, 'get_web_error'):
            error = result.get_web_error()
            if error is None:
                # Successful WebKit save
                win.current_file = file
                win.modified = False
                self.update_window_title(win)
                win.statusbar.set_text(f"Saved: {file.get_path()}")
            else:
                # WebKit save failed
                print(f"WebKit save error: {error.get_message()}")
                win.statusbar.set_text(f"Error: {error.get_message()}")
                # Fallback to manual saving
                self.save_as_html(win, file)
        else:
            # For older WebKit versions without detailed error info
            # Just assume success and update the UI
            win.current_file = file
            win.modified = False
            self.update_window_title(win)
            win.statusbar.set_text(f"Saved: {file.get_path()}")
    except Exception as e:
        print(f"Error in WebKit save callback: {e}")
        # Fallback to manual saving
        self.save_as_html(win, file)

def save_as_html(self, win, file):
    """Save document as HTML by extracting just the editor content"""
    # We only want to get the editor content, not the entire HTML document
    win.webview.evaluate_javascript(
        "document.getElementById('editor').innerHTML",
        -1, None, None, None,
        lambda webview, result, data: self.save_html_callback(win, webview, result, file),
        None
    )
    win.statusbar.set_text(f"Saving HTML file: {file.get_path()}")

def save_html_callback(self, win, webview, result, file):
    """Process HTML content from webview and save to file"""
    try:
        js_result = webview.evaluate_javascript_finish(result)
        if js_result:
            # Get the content based on the available API
            if hasattr(js_result, 'get_js_value'):
                editor_content = js_result.get_js_value().to_string()
            else:
                editor_content = js_result.to_string()
            
            # Wrap the content in a proper HTML document
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>HTML Document</title>
    <meta charset="utf-8">
</head>
<body>
{editor_content}
</body>
</html>"""

            # Convert the string to bytes
            content_bytes = html_content.encode('utf-8')
            
            # Use the synchronous replace_contents method
            try:
                success, etag = file.replace_contents(
                    content_bytes,
                    None,  # etag
                    False,  # make_backup
                    Gio.FileCreateFlags.REPLACE_DESTINATION,
                    None   # cancellable
                )
                
                if success:
                    win.current_file = file
                    win.modified = False
                    self.update_window_title(win)
                    win.statusbar.set_text(f"Saved: {file.get_path()}")
                else:
                    win.statusbar.set_text("File save was not successful")
                    
            except GLib.Error as e:
                print(f"Error writing file: {e.message if hasattr(e, 'message') else str(e)}")
                win.statusbar.set_text(f"Error writing file: {str(e)}")
                
    except Exception as e:
        print(f"Error processing HTML for save: {e}")
        win.statusbar.set_text(f"Error saving HTML: {e}")
        
def save_as_html_fallback(self, win, file):
    """Fallback method to save HTML when JavaScript evaluation fails"""
    try:
        # Create basic HTML content with the current content
        win.webview.evaluate_javascript(
            "document.body.innerHTML",
            -1, None, None, None,
            lambda webview, result, data: self.save_html_body_callback(win, webview, result, file),
            None
        )
    except Exception as e:
        print(f"Error in HTML fallback save: {e}")
        win.statusbar.set_text(f"Error saving HTML: {e}")
        self.show_error_dialog(win, f"Could not save file: {e}")

def save_html_body_callback(self, win, webview, result, file):
    """Process HTML body content and save to file"""
    try:
        js_result = webview.evaluate_javascript_finish(result)
        if js_result:
            # Get the body HTML content
            if hasattr(js_result, 'get_js_value'):
                body_content = js_result.get_js_value().to_string()
            else:
                body_content = js_result.to_string()
            
            # Create a complete HTML document
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>HTML Document</title>
    <meta charset="utf-8">
</head>
<body>
{body_content}
</body>
</html>"""

            # Convert the string to bytes
            content_bytes = html_content.encode('utf-8')
            
            # Use the simpler replace_contents method
            try:
                success, etag = file.replace_contents(
                    content_bytes,
                    None,  # etag
                    False,  # make_backup
                    Gio.FileCreateFlags.REPLACE_DESTINATION,
                    None   # cancellable
                )
                
                if success:
                    win.current_file = file
                    win.modified = False
                    self.update_window_title(win)
                    win.statusbar.set_text(f"Saved: {file.get_path()}")
                else:
                    win.statusbar.set_text("File save was not successful")
                    
            except GLib.Error as e:
                print(f"Error writing file: {e.message}")
                win.statusbar.set_text(f"Error writing file: {e.message}")
                
        else:
            print("Failed to get HTML content from webview")
            win.statusbar.set_text("Failed to get HTML content for saving")
    except Exception as e:
        print(f"Error processing HTML body for save: {e}")
        win.statusbar.set_text(f"Error saving HTML: {e}")

def save_as_text(self, win, file):
    """Save document as plain text by extracting text content from the webview"""
    win.webview.evaluate_javascript(
        "document.body.innerText || document.body.textContent",
        -1, None, None, None,
        lambda webview, result, data: self.save_text_callback(win, webview, result, file),
        None
    )
    win.statusbar.set_text(f"Saving text file: {file.get_path()}")

def save_text_callback(self, win, webview, result, file):
    """Process text content from webview and save to file"""
    try:
        js_result = webview.evaluate_javascript_finish(result)
        if js_result:
            text_content = js_result.get_js_value().to_string() if hasattr(js_result, 'get_js_value') else js_result.to_string()
            
            # Replace the file with the new content
            file.replace_contents_async(
                text_content.encode('utf-8'),
                None,
                False,
                Gio.FileCreateFlags.REPLACE_DESTINATION,
                None,
                lambda file, result: self.save_completion_callback(win, file, result)
            )
    except Exception as e:
        print(f"Error processing text for save: {e}")
        win.statusbar.set_text(f"Error saving text: {e}")

def save_as_markdown(self, win, file):
    """Save document as Markdown using html2text if available"""
    if not HTML2TEXT_AVAILABLE:
        win.statusbar.set_text("html2text library not available for Markdown conversion")
        # Fallback to HTML
        self.save_as_html(win, file)
        return
        
    win.webview.evaluate_javascript(
        "document.documentElement.outerHTML",
        -1, None, None, None,
        lambda webview, result, data: self.save_markdown_callback(win, webview, result, file),
        None
    )
    win.statusbar.set_text(f"Saving Markdown file: {file.get_path()}")

def save_markdown_callback(self, win, webview, result, file):
    """Convert HTML to Markdown and save to file"""
    try:
        js_result = webview.evaluate_javascript_finish(result)
        if js_result and HTML2TEXT_AVAILABLE:
            html_content = js_result.get_js_value().to_string() if hasattr(js_result, 'get_js_value') else js_result.to_string()
            
            # Convert HTML to Markdown
            h2t = html2text.HTML2Text()
            h2t.unicode_snob = True        # Use Unicode
            h2t.body_width = 0             # Don't wrap lines
            h2t.ignore_links = False       # Preserve links
            h2t.ignore_images = False      # Preserve images
            h2t.ignore_tables = False      # Try to handle tables
            
            markdown_content = h2t.handle(html_content)
            
            # Replace the file with the new content
            file.replace_contents_async(
                markdown_content.encode('utf-8'),
                None,
                False,
                Gio.FileCreateFlags.REPLACE_DESTINATION,
                None,
                lambda file, result: self.save_completion_callback(win, file, result)
            )
    except Exception as e:
        print(f"Error converting to Markdown for save: {e}")
        win.statusbar.set_text(f"Error saving Markdown: {e}")
        # Fallback to HTML
        self.save_as_html(win, file)

def save_completion_callback(self, win, file, result):
    """Handle save completion"""
    try:
        # For WebKit save operations, the result might be None or not a valid GIO task
        if result is None:
            # WebKit's direct save doesn't provide a result to finish
            success = True
        else:
            try:
                # Check if this is a WebKit result (which is different from a GIO result)
                if hasattr(result, 'get_web_error'):
                    # WebKit result handling
                    error = result.get_web_error()
                    success = (error is None)
                    if not success:
                        print(f"WebKit save error: {error.get_message()}")
                elif hasattr(file, 'replace_contents_finish'):
                    # Standard GIO result
                    success, _ = file.replace_contents_finish(result)
                else:
                    # Fallback - assume success unless we have evidence otherwise
                    success = True
            except GLib.Error as e:
                print(f"Error finishing file operation: {e}")
                success = False
            except Exception as e:
                print(f"Unexpected error in save completion: {e}")
                success = False
                
        if success:
            win.current_file = file
            win.modified = False
            self.update_window_title(win)
            win.statusbar.set_text(f"Saved: {file.get_path()}")
        else:
            win.statusbar.set_text("File save was not successful")
    except Exception as e:
        print(f"Error completing save: {e}")
        win.statusbar.set_text(f"Error completing save: {e}")

# Legacy aliases for backward compatibility
def _on_save_response(self, win, dialog, result):
    """Backward compatibility method"""
    return self.save_dialog_callback(win, dialog, result)
    
def _on_save_as_response(self, win, dialog, result):
    """Backward compatibility method"""
    return self.save_dialog_callback(win, dialog, result)
    
def _on_get_html_content(self, win, webview, result, file):
    """Backward compatibility method - redirects to HTML save"""
    return self.save_html_callback(win, webview, result, file)
    
def _on_file_saved(self, win, file, result):
    """Backward compatibility method"""
    return self.save_completion_callback(win, file, result)



####################




   




