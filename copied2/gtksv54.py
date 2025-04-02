#!/usr/bin/env python3
import gi
import os
import sys
import tempfile
import webbrowser
import base64
import mimetypes

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Adw, Gio, GLib, Gdk, WebKit
from pathlib import Path

class WYSIWYGTextEditor(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.wysiwygeditor",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        
        self.connect('activate', self.on_activate)
        self.current_file = None
        
    def on_activate(self, app):
        # Create the main window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(800, 600)
        self.win.set_title("WYSIWYG Editor")
        
        # Create a header bar
        self.header = Adw.HeaderBar()
        
        # Create a box for the main content
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Add the header to the main box
        self.main_box.append(self.header)
        
        # Create actions
        self.create_actions()
        
        # Create menus
        self.create_menus()
        
        # Create the editor
        self.create_editor()
        
        # Add the main box to the window
        self.win.set_content(self.main_box)
        
        # Show the window
        self.win.present()
    
    def create_actions(self):
        # File actions
        actions = [
            ('new', self.on_new_clicked),
            ('open', self.on_open_clicked),
            ('save', self.on_save_clicked),
            ('save_as', self.on_save_as_clicked),
            ('export_html', self.on_export_html_clicked),
            ('preview', self.on_preview_clicked),
            ('quit', self.on_quit_clicked),
            
            # Edit actions
            ('cut', self.on_cut_clicked),
            ('copy', self.on_copy_clicked),
            ('paste', self.on_paste_clicked),
            ('select_all', self.on_select_all_clicked),
            ('undo', self.on_undo_clicked),
            ('redo', self.on_redo_clicked),
            
            # Format actions
            ('bold', self.on_bold_clicked),
            ('italic', self.on_italic_clicked),
            ('underline', self.on_underline_clicked),
            ('heading1', self.on_heading1_clicked),
            ('heading2', self.on_heading2_clicked),
            ('bullet_list', self.on_bullet_list_clicked),
            ('number_list', self.on_number_list_clicked),
            ('align_left', self.on_align_left_clicked),
            ('align_center', self.on_align_center_clicked),
            ('align_right', self.on_align_right_clicked),
            ('insert_image', self.on_insert_image_clicked),
            ('insert_link', self.on_insert_link_clicked),
        ]
        
        for action_name, callback in actions:
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", callback)
            self.add_action(action)
    
    def create_menus(self):
        # Create menu button for the header bar
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        
        # Create menu model
        menu = Gio.Menu.new()
        
        # File submenu
        file_menu = Gio.Menu.new()
        file_menu.append("New", "app.new")
        file_menu.append("Open", "app.open")
        file_menu.append("Save", "app.save")
        file_menu.append("Save As", "app.save_as")
        file_menu.append("Export HTML", "app.export_html")
        file_menu.append("Preview in Browser", "app.preview")
        file_menu.append("Quit", "app.quit")
        
        # Edit submenu
        edit_menu = Gio.Menu.new()
        edit_menu.append("Undo", "app.undo")
        edit_menu.append("Redo", "app.redo")
        edit_menu.append("Cut", "app.cut")
        edit_menu.append("Copy", "app.copy")
        edit_menu.append("Paste", "app.paste")
        edit_menu.append("Select All", "app.select_all")
        
        # Format submenu
        format_menu = Gio.Menu.new()
        format_menu.append("Bold", "app.bold")
        format_menu.append("Italic", "app.italic")
        format_menu.append("Underline", "app.underline")
        format_menu.append("Heading 1", "app.heading1")
        format_menu.append("Heading 2", "app.heading2")
        format_menu.append("Bullet List", "app.bullet_list")
        format_menu.append("Numbered List", "app.number_list")
        format_menu.append("Align Left", "app.align_left")
        format_menu.append("Align Center", "app.align_center")
        format_menu.append("Align Right", "app.align_right")
        format_menu.append("Insert Image", "app.insert_image")
        format_menu.append("Insert Link", "app.insert_link")
        
        # Add submenus to main menu
        menu.append_submenu("File", file_menu)
        menu.append_submenu("Edit", edit_menu)
        menu.append_submenu("Format", format_menu)
        
        # Connect menu to button
        menu_button.set_menu_model(menu)
        
        # Add menu button to header bar
        self.header.pack_end(menu_button)
        
        # Create toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.add_css_class("toolbar")
        
        # Add formatting buttons to toolbar
        buttons = [
            ("edit-undo-symbolic", "Undo", self.on_undo_clicked),
            ("edit-redo-symbolic", "Redo", self.on_redo_clicked),
            ("format-text-bold-symbolic", "Bold", self.on_bold_clicked),
            ("format-text-italic-symbolic", "Italic", self.on_italic_clicked),
            ("format-text-underline-symbolic", "Underline", self.on_underline_clicked),
            ("format-text-heading-1-symbolic", "Heading 1", self.on_heading1_clicked),
            ("format-text-heading-2-symbolic", "Heading 2", self.on_heading2_clicked),
            ("format-list-unordered-symbolic", "Bullet List", self.on_bullet_list_clicked),
            ("format-list-ordered-symbolic", "Numbered List", self.on_number_list_clicked),
            ("format-justify-left-symbolic", "Align Left", self.on_align_left_clicked),
            ("format-justify-center-symbolic", "Align Center", self.on_align_center_clicked),
            ("format-justify-right-symbolic", "Align Right", self.on_align_right_clicked),
            ("insert-image-symbolic", "Insert Image", self.on_insert_image_clicked),
            ("insert-link-symbolic", "Insert Link", self.on_insert_link_clicked),
        ]
        
        for icon_name, tooltip, callback in buttons:
            button = Gtk.Button.new_from_icon_name(icon_name)
            button.set_tooltip_text(tooltip)
            button.connect("clicked", lambda btn, cb=callback: cb(None, None))

            toolbar.append(button)
        
        # Add toolbar to main box
        self.main_box.append(toolbar)
    
    def create_editor(self):
        # Create a scrolled window for the WebView
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        
        # Create WebView
        self.webview = WebKit.WebView()
        
        # Set WebView settings
        settings = self.webview.get_settings()
        settings.set_javascript_can_access_clipboard(True)
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)
        
        # Load the editor HTML
        self.init_editor_content()
        
        # Add the WebView to the scrolled window
        scrolled_window.set_child(self.webview)
        
        # Add the scrolled window to the main box
        self.main_box.append(scrolled_window)
        
        # Status bar
        self.status_bar = Gtk.Label()
        self.status_bar.set_xalign(0)
        self.status_bar.add_css_class("statusbar")
        self.main_box.append(self.status_bar)
        self.update_status("Ready")
    
    def init_editor_content(self):
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>WYSIWYG Editor</title>
                <style>
                    body {
                        font-family: system-ui, -apple-system, sans-serif;
                        margin: 0;
                        padding: 10px;
                        background-color: white;
                        color: black;
                        min-height: 100vh;
                    }
                    #editor {
                        outline: none;
                        padding: 10px;
                        border: 1px solid #ccc;
                        min-height: 500px;
                        overflow-y: auto;
                    }
                    img {
                        display: inline-block;
                        max-width: 100%;
                        cursor: move;
                    }
                    img.selected {
                        outline: 2px solid #4285f4;
                        box-shadow: 0 0 10px rgba(66, 133, 244, 0.5);
                    }
                    img.resizing {
                        outline: 2px dashed #4285f4;
                    }
                    .resize-handle {
                        position: absolute;
                        width: 10px;
                        height: 10px;
                        background-color: #4285f4;
                        border: 1px solid white;
                        border-radius: 50%;
                        z-index: 999;
                    }
                    .tl-handle { top: -5px; left: -5px; cursor: nw-resize; }
                    .tr-handle { top: -5px; right: -5px; cursor: ne-resize; }
                    .bl-handle { bottom: -5px; left: -5px; cursor: sw-resize; }
                    .br-handle { bottom: -5px; right: -5px; cursor: se-resize; }
                    
                    /* Context menu styles */
                    .context-menu {
                        position: absolute;
                        background-color: white;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
                        padding: 5px 0;
                        z-index: 1000;
                        min-width: 150px;
                    }
                    .context-menu-item {
                        padding: 8px 15px;
                        cursor: pointer;
                        user-select: none;
                    }
                    .context-menu-item:hover {
                        background-color: #f0f0f0;
                    }
                    .context-menu-separator {
                        height: 1px;
                        background-color: #e0e0e0;
                        margin: 5px 0;
                    }
                    .context-menu-submenu {
                        position: relative;
                    }
                    .context-menu-submenu::after {
                        content: '▶';
                        position: absolute;
                        right: 10px;
                        top: 8px;
                        font-size: 10px;
                    }
                    .context-menu-submenu-content {
                        display: none;
                        position: absolute;
                        left: 100%;
                        top: 0;
                        background-color: white;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
                        padding: 5px 0;
                        min-width: 150px;
                    }
                    .context-menu-submenu:hover .context-menu-submenu-content {
                        display: block;
                    }
                    
                    /* Image alignment styles */
                    img.align-left {
                        float: left;
                        margin: 0 15px 10px 0;
                    }
                    img.align-right {
                        float: right;
                        margin: 0 0 10px 15px;
                    }
                    img.align-center {
                        float: center;
                        margin: 0 0 10px 15px;
                    }
                    img.align-center {
                        display: block;
                        margin: 10px auto;
                        float: none;
                    }
                    img.align-none {
                        float: none;
                        margin: 10px 0;
                    }
                    .text-wrap-none {
                        clear: both;
                    }
                    
                    @media (prefers-color-scheme: dark) {
                        body {
                            background-color: #333;
                            color: #eee;
                        }
                        #editor {
                            border-color: #555;
                            background-color: #222;
                            color: #eee;
                        }
                        img.selected {
                            outline-color: #5e97f6;
                            box-shadow: 0 0 10px rgba(94, 151, 246, 0.5);
                        }
                        .context-menu {
                            background-color: #333;
                            border-color: #555;
                            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
                        }
                        .context-menu-item:hover {
                            background-color: #444;
                        }
                        .context-menu-separator {
                            background-color: #555;
                        }
                        .context-menu-submenu-content {
                            background-color: #333;
                            border-color: #555;
                        }
                    }
                </style>
            </head>
            <body>
                <div id="editor" contenteditable="true"></div>
                
                <script>
                    // Initialize editor
                    const editor = document.getElementById('editor');
                    let selectedImage = null;
                    let resizeHandles = [];
                    let isDragging = false;
                    let isResizing = false;
                    let lastX, lastY;
                    let resizeStartWidth, resizeStartHeight;
                    let currentResizeHandle = null;
                    let contextMenu = null;
                    
                    // Make the editor focusable
                    editor.focus();
                    
                    // Create context menu
                    function createContextMenu(x, y) {
                        // Remove any existing context menu
                        removeContextMenu();
                        
                        // Create context menu container
                        contextMenu = document.createElement('div');
                        contextMenu.className = 'context-menu';
                        contextMenu.style.left = x + 'px';
                        contextMenu.style.top = y + 'px';
                        
                        // Add menu items
                        const menuItems = [
                            { label: 'Resize Image', action: 'resize' },
                            { label: 'Alignment', submenu: [
                                { label: 'Left', action: 'align-left' },
                                { label: 'Center', action: 'align-center' },
                                { label: 'Right', action: 'align-right' },
                                { label: 'None', action: 'align-none' }
                            ]},
                            { label: 'Text Wrap', submenu: [
                                { label: 'Around', action: 'wrap-around' },
                                { label: 'None', action: 'wrap-none' }
                            ]},
                            { type: 'separator' },
                            { label: 'Copy Image', action: 'copy' },
                            { label: 'Delete Image', action: 'delete' }
                        ];
                        
                        // Create menu items
                        createMenuItems(contextMenu, menuItems);
                        
                        // Add to document
                        document.body.appendChild(contextMenu);
                        
                        // Add click handler to close menu when clicking outside
                        setTimeout(() => {
                            document.addEventListener('click', closeContextMenuOnClickOutside);
                        }, 0);
                    }
                    
                    // Create menu items from config
                    function createMenuItems(parent, items) {
                        items.forEach(item => {
                            if (item.type === 'separator') {
                                const separator = document.createElement('div');
                                separator.className = 'context-menu-separator';
                                parent.appendChild(separator);
                            } else if (item.submenu) {
                                const submenuItem = document.createElement('div');
                                submenuItem.className = 'context-menu-item context-menu-submenu';
                                submenuItem.textContent = item.label;
                                
                                const submenuContent = document.createElement('div');
                                submenuContent.className = 'context-menu-submenu-content';
                                createMenuItems(submenuContent, item.submenu);
                                
                                submenuItem.appendChild(submenuContent);
                                parent.appendChild(submenuItem);
                            } else {
                                const menuItem = document.createElement('div');
                                menuItem.className = 'context-menu-item';
                                menuItem.textContent = item.label;
                                menuItem.addEventListener('click', (e) => {
                                    e.stopPropagation();
                                    handleContextMenuAction(item.action);
                                    removeContextMenu();
                                });
                                parent.appendChild(menuItem);
                            }
                        });
                    }
                    
                    // Handle context menu actions
                    function handleContextMenuAction(action) {
                        if (!selectedImage) return;
                        
                        switch (action) {
                            case 'resize':
                                // Just keep the image selected with resize handles
                                break;
                            case 'align-left':
                                setImageAlignment(selectedImage, 'left');
                                break;
                            case 'align-center':
                                setImageAlignment(selectedImage, 'center');
                                break;
                            case 'align-right':
                                setImageAlignment(selectedImage, 'right');
                                break;
                            case 'align-none':
                                setImageAlignment(selectedImage, 'none');
                                break;
                            case 'wrap-around':
                                setTextWrap(selectedImage, 'around');
                                break;
                            case 'wrap-none':
                                setTextWrap(selectedImage, 'none');
                                break;
                            case 'copy':
                                copyImageToClipboard(selectedImage);
                                break;
                            case 'delete':
                                deleteImage(selectedImage);
                                break;
                        }
                    }
                    
                    // Set image alignment
                    function setImageAlignment(image, alignment) {
                        // Remove existing alignment classes
                        image.classList.remove('align-left', 'align-right', 'align-center', 'align-none');
                        
                        // Add new alignment class
                        image.classList.add(`align-${alignment}`);
                        
                        // Update handles
                        updateResizeHandles();
                    }
                    
                    // Set text wrap
                    function setTextWrap(image, wrap) {
                        if (wrap === 'none') {
                            // Make sure image doesn't have float
                            image.style.float = 'none';
                            
                            // Insert a div with clear: both after the image
                            const clearDiv = document.createElement('div');
                            clearDiv.className = 'text-wrap-none';
                            clearDiv.style.clear = 'both';
                            
                            // Remove any existing clear divs
                            const siblings = Array.from(image.parentNode.children);
                            siblings.forEach(sibling => {
                                if (sibling.classList && sibling.classList.contains('text-wrap-none') && 
                                    siblings.indexOf(sibling) > siblings.indexOf(image)) {
                                    sibling.remove();
                                }
                            });
                            
                            // Insert after the image
                            if (image.nextSibling) {
                                image.parentNode.insertBefore(clearDiv, image.nextSibling);
                            } else {
                                image.parentNode.appendChild(clearDiv);
                            }
                        } else if (wrap === 'around') {
                            // For text wrap, we need to ensure the image has float applied
                            // If no alignment is set, default to left alignment
                            if (!image.classList.contains('align-left') && !image.classList.contains('align-right')) {
                                setImageAlignment(image, 'left');
                            }
                            
                            // Remove any clear divs that might prevent wrapping
                            const nextSibling = image.nextSibling;
                            if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                                nextSibling.remove();
                            }
                        }
                    }
                    
                    // Copy image to clipboard
                    function copyImageToClipboard(image) {
                        // Create a canvas element
                        const canvas = document.createElement('canvas');
                        canvas.width = image.naturalWidth;
                        canvas.height = image.naturalHeight;
                        
                        // Draw the image to the canvas
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(image, 0, 0);
                        
                        // Convert to blob and copy
                        canvas.toBlob(blob => {
                            const item = new ClipboardItem({ 'image/png': blob });
                            navigator.clipboard.write([item]).then(
                                () => console.log('Image copied to clipboard'),
                                err => console.error('Error copying image: ', err)
                            );
                        });
                    }
                    
                    // Delete image
                    function deleteImage(image) {
                        // Also remove any associated text-wrap-none divs
                        const nextSibling = image.nextSibling;
                        if (nextSibling && nextSibling.classList && nextSibling.classList.contains('text-wrap-none')) {
                            nextSibling.remove();
                        }
                        
                        deselectImage();
                        image.remove();
                    }
                    
                    // Close context menu when clicking outside
                    function closeContextMenuOnClickOutside(e) {
                        if (contextMenu && !contextMenu.contains(e.target)) {
                            removeContextMenu();
                        }
                    }
                    
                    // Remove context menu
                    function removeContextMenu() {
                        if (contextMenu) {
                            document.removeEventListener('click', closeContextMenuOnClickOutside);
                            contextMenu.remove();
                            contextMenu = null;
                        }
                    }
                    
                    // Create resize handles for selected images
                    function createResizeHandles(image) {
                        // Remove any existing handles
                        removeResizeHandles();
                        
                        // Create container for handles
                        const container = document.createElement('div');
                        container.style.position = 'absolute';
                        container.style.left = image.offsetLeft + 'px';
                        container.style.top = image.offsetTop + 'px';
                        container.style.width = image.offsetWidth + 'px';
                        container.style.height = image.offsetHeight + 'px';
                        container.style.pointerEvents = 'none';
                        container.className = 'resize-container';
                        
                        // Create handles
                        const positions = ['tl', 'tr', 'bl', 'br'];
                        positions.forEach(pos => {
                            const handle = document.createElement('div');
                            handle.className = `resize-handle ${pos}-handle`;
                            handle.style.pointerEvents = 'all';
                            handle.dataset.position = pos;
                            
                            handle.addEventListener('mousedown', (e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                startResize(e, handle);
                            });
                            
                            container.appendChild(handle);
                            resizeHandles.push(handle);
                        });
                        
                        document.body.appendChild(container);
                        return container;
                    }
                    
                    // Remove resize handles
                    function removeResizeHandles() {
                        const container = document.querySelector('.resize-container');
                        if (container) {
                            container.remove();
                        }
                        resizeHandles = [];
                    }
                    
                    // Update resize handles position
                    function updateResizeHandles() {
                        if (!selectedImage) return;
                        
                        const container = document.querySelector('.resize-container');
                        if (container) {
                            const rect = selectedImage.getBoundingClientRect();
                            const editorRect = editor.getBoundingClientRect();
                            
                            container.style.left = (rect.left - editorRect.left + editor.scrollLeft) + 'px';
                            container.style.top = (rect.top - editorRect.top + editor.scrollTop) + 'px';
                            container.style.width = selectedImage.offsetWidth + 'px';
                            container.style.height = selectedImage.offsetHeight + 'px';
                        }
                    }
                    
                    // Start resizing an image
                    function startResize(e, handle) {
                        if (!selectedImage) return;
                        
                        isResizing = true;
                        currentResizeHandle = handle;
                        lastX = e.clientX;
                        lastY = e.clientY;
                        resizeStartWidth = selectedImage.offsetWidth;
                        resizeStartHeight = selectedImage.offsetHeight;
                        selectedImage.classList.add('resizing');
                        
                        document.addEventListener('mousemove', handleResize);
                        document.addEventListener('mouseup', stopResize);
                    }
                    
                    // Handle resize move event
                    function handleResize(e) {
                        if (!isResizing || !selectedImage || !currentResizeHandle) return;
                        
                        const deltaX = e.clientX - lastX;
                        const deltaY = e.clientY - lastY;
                        const position = currentResizeHandle.dataset.position;
                        
                        let newWidth = resizeStartWidth;
                        let newHeight = resizeStartHeight;
                        
                        // Calculate new dimensions based on resize handle position
                        if (position.includes('r')) { // right handles
                            newWidth = resizeStartWidth + deltaX;
                        } else if (position.includes('l')) { // left handles
                            newWidth = resizeStartWidth - deltaX;
                        }
                        
                        if (position.includes('b')) { // bottom handles
                            newHeight = resizeStartHeight + deltaY;
                        } else if (position.includes('t')) { // top handles
                            newHeight = resizeStartHeight - deltaY;
                        }
                        
                        // Maintain aspect ratio if shift key is pressed
                        if (e.shiftKey) {
                            const aspectRatio = resizeStartWidth / resizeStartHeight;
                            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                                newHeight = newWidth / aspectRatio;
                            } else {
                                newWidth = newHeight * aspectRatio;
                            }
                        }
                        
                        // Apply minimum sizes
                        newWidth = Math.max(20, newWidth);
                        newHeight = Math.max(20, newHeight);
                        
                        // Apply new dimensions
                        selectedImage.style.width = newWidth + 'px';
                        selectedImage.style.height = newHeight + 'px';
                        
                        // Update handles position
                        updateResizeHandles();
                    }
                    
                    // Stop resizing
                    function stopResize() {
                        if (selectedImage) {
                            selectedImage.classList.remove('resizing');
                        }
                        
                        isResizing = false;
                        currentResizeHandle = null;
                        
                        document.removeEventListener('mousemove', handleResize);
                        document.removeEventListener('mouseup', stopResize);
                    }
                    
                    // Start dragging an image
                    function startDrag(e, image) {
                        if (isResizing) return;
                        
                        isDragging = true;
                        lastX = e.clientX;
                        lastY = e.clientY;
                        
                        document.addEventListener('mousemove', handleDrag);
                        document.addEventListener('mouseup', stopDrag);
                    }
                    
                    // Handle drag move event
                    function handleDrag(e) {
                        if (!isDragging || !selectedImage) return;
                        
                        // Create a temporary element to determine valid drop position
                        const temp = document.createElement('span');
                        temp.style.display = 'inline-block';
                        temp.style.width = '1px';
                        temp.style.height = '1px';
                        
                        // Get caret position at mouse coordinates
                        const range = document.caretRangeFromPoint(e.clientX, e.clientY);
                        if (range) {
                            range.insertNode(temp);
                            
                            // Move the image to new position
                            temp.parentNode.insertBefore(selectedImage, temp);
                            temp.remove();
                            
                            // Update resize handles
                            updateResizeHandles();
                        }
                    }
                    
                    // Stop dragging
                    function stopDrag() {
                        isDragging = false;
                        document.removeEventListener('mousemove', handleDrag);
                        document.removeEventListener('mouseup', stopDrag);
                    }
                    
                    // Select an image
                    function selectImage(image) {
                        // Deselect previous image
                        if (selectedImage && selectedImage !== image) {
                            selectedImage.classList.remove('selected');
                        }
                        
                        // Select new image
                        selectedImage = image;
                        selectedImage.classList.add('selected');
                        
                        // Create resize handles
                        createResizeHandles(image);
                    }
                    
                    // Deselect current image
                    function deselectImage() {
                        if (selectedImage) {
                            selectedImage.classList.remove('selected');
                            selectedImage = null;
                            removeResizeHandles();
                        }
                    }
                    
                    // Handle clicks on the editor
                    editor.addEventListener('click', (e) => {
                        // Close any open context menu
                        removeContextMenu();
                        
                        if (e.target.tagName === 'IMG') {
                            e.preventDefault();
                            selectImage(e.target);
                        } else {
                            deselectImage();
                        }
                    });
                    
                    // Handle right click on images
                    editor.addEventListener('contextmenu', (e) => {
                        if (e.target.tagName === 'IMG') {
                            e.preventDefault();
                            selectImage(e.target);
                            createContextMenu(e.clientX, e.clientY);
                        }
                    });
                    
                    // Handle mousedown on images for dragging
                    editor.addEventListener('mousedown', (e) => {
                        if (e.target.tagName === 'IMG') {
                            if (!isResizing && e.button === 0) { // Left click only
                                e.preventDefault();
                                
                                // Select the image if not already selected
                                if (selectedImage !== e.target) {
                                    selectImage(e.target);
                                }
                                
                                // Start dragging
                                startDrag(e, e.target);
                            }
                        }
                    });
                    
                    // Handle image insertion
                    function setupNewImage(img) {
                        // Make sure contenteditable doesn't interfere with dragging
                        img.contentEditable = false;
                        
                        // When loaded, select the image
                        img.onload = function() {
                            selectImage(img);
                            // Set default alignment and text wrap for new images
                            setImageAlignment(img, 'left');
                            setTextWrap(img, 'around');
                        };
                    }
                    
                    // Initialize images when page loads
                    document.addEventListener('DOMContentLoaded', () => {
                        const images = editor.querySelectorAll('img');
                        images.forEach(img => {
                            img.contentEditable = false;
                            // If no alignment is set, set default to left with text wrap
                            if (!img.classList.contains('align-left') && 
                                !img.classList.contains('align-right') && 
                                !img.classList.contains('align-center') && 
                                !img.classList.contains('align-none')) {
                                setImageAlignment(img, 'left');
                                setTextWrap(img, 'around');
                            }
                        });
                    });
                    
                    // Helper function to get selected HTML
                    function getSelectedHtml() {
                        const selection = window.getSelection();
                        if (selection.rangeCount > 0) {
                            const range = selection.getRangeAt(0);
                            const clonedRange = range.cloneContents();
                            const div = document.createElement('div');
                            div.appendChild(clonedRange);
                            return div.innerHTML;
                        }
                        return '';
                    }
                    
                    // Helper function to get editor content
                    function getContent() {
                        deselectImage();
                        return editor.innerHTML;
                    }
                    
                    // Helper function to set editor content
                    function setContent(html) {
                        editor.innerHTML = html;
                        // Initialize all images
                        const images = editor.querySelectorAll('img');
                        images.forEach(img => {
                            img.contentEditable = false;
                            // If no alignment is set, set default to left with text wrap
                            if (!img.classList.contains('align-left') && 
                                !img.classList.contains('align-right') && 
                                !img.classList.contains('align-center') && 
                                !img.classList.contains('align-none')) {
                                setImageAlignment(img, 'left');
                                setTextWrap(img, 'around');
                            }
                        });
                    }
                    
                    // Custom image insertion function
                    function insertImage(src) {
                        document.execCommand('insertHTML', false, '<img src="' + src + '">');
                        const images = editor.querySelectorAll('img');
                        const lastImage = images[images.length - 1];
                        if (lastImage) {
                            setupNewImage(lastImage);
                        }
                    }
                    
                    // Execute command helper
                    function execCommand(command, value=null) {
                        deselectImage();
                        document.execCommand(command, false, value);
                        editor.focus();
                    }
                </script>
            </body>
            </html>
            """
            
            self.webview.load_html(html_content, "file:///")    
    def update_status(self, message):
        self.status_bar.set_text(message)
    
    def exec_js(self, script):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)
    
    def get_editor_content(self, callback):
        self.webview.evaluate_javascript("getContent();", -1, None, None, None, self.handle_js_result, callback)
    
    def handle_js_result(self, webview, result, callback):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            if js_result is not None:
                value = js_result.get_js_value().to_string()
                callback(value)
        except GLib.Error as error:
            self.show_error_dialog(f"JavaScript error: {error.message}")
    
    # File actions
    def on_new_clicked(self, action, param):
        self.get_editor_content(self.check_modified_for_new)
    
    def check_modified_for_new(self, content):
        if content and content.strip():
            dialog = Adw.MessageDialog.new(self.win, "Unsaved Changes", 
                                          "Do you want to save the changes?")
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_default_response("save")
            dialog.connect("response", self.on_new_file_response)
            dialog.present()
        else:
            self.new_file()
    
    def on_new_file_response(self, dialog, response):
        if response == "save":
            self.on_save_clicked(None, None)
            self.new_file()
        elif response == "discard":
            self.new_file()
    
    def new_file(self):
        self.exec_js("setContent('');")
        self.current_file = None
        self.update_status("New file created")
    
    def on_open_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open File")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("text/html")
        filters.add_mime_type("text/plain")
        dialog.set_default_filter(filters)
        
        dialog.open(self.win, None, self.on_open_file_dialog_response)
    
    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.load_file(file)
        except GLib.Error as error:
            self.show_error_dialog(f"Error opening file: {error.message}")
    
    def load_file(self, file):
        try:
            success, contents, _ = file.load_contents()
            if success:
                try:
                    text = contents.decode('utf-8')
                    # Load content into editor
                    escaped_text = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                    self.exec_js(f"setContent('{escaped_text}');")
                    self.current_file = file
                    self.update_status(f"Loaded {file.get_path()}")
                except UnicodeDecodeError:
                    self.show_error_dialog("File is not in UTF-8 encoding")
        except GLib.Error as error:
            self.show_error_dialog(f"Error loading file: {error.message}")
    
    def on_save_clicked(self, action, param):
        if self.current_file:
            self.get_editor_content(lambda content: self.save_file(self.current_file, content))
        else:
            self.on_save_as_clicked(action, param)
    
    def on_save_as_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Save File")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("text/html")
        dialog.set_default_filter(filters)
        
        dialog.save(self.win, None, self.on_save_file_dialog_response)
    
    def on_save_file_dialog_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.get_editor_content(lambda content: self.save_file(file, content))
        except GLib.Error as error:
            self.show_error_dialog(f"Error saving file: {error.message}")
    
    def save_file(self, file, content):
        try:
            # Ensure the file has .html extension
            path = file.get_path()
            if not path.lower().endswith('.html'):
                path += '.html'
                file = Gio.File.new_for_path(path)
            
            # Create a complete HTML document
            html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Document</title>
</head>
<body>
{content}
</body>
</html>"""
            
            file.replace_contents(html_document.encode('utf-8'), None, 
                                 False, Gio.FileCreateFlags.NONE, 
                                 None)
            self.current_file = file
            self.update_status(f"Saved to {file.get_path()}")
        except GLib.Error as error:
            self.show_error_dialog(f"Error saving file: {error.message}")
    
    def on_export_html_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Export HTML")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("text/html")
        dialog.set_default_filter(filters)
        
        dialog.save(self.win, None, self.on_export_html_dialog_response)
    
    def on_export_html_dialog_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                self.get_editor_content(lambda content: self.export_html(file, content))
        except GLib.Error as error:
            self.show_error_dialog(f"Error exporting HTML: {error.message}")
    
    def export_html(self, file, content):
        try:
            # Ensure the file has .html extension
            path = file.get_path()
            if not path.lower().endswith('.html'):
                path += '.html'
                file = Gio.File.new_for_path(path)
            
            # Create a complete HTML document
            html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Exported Document</title>
</head>
<body>
{content}
</body>
</html>"""
            
            file.replace_contents(html_document.encode('utf-8'), None, 
                                 False, Gio.FileCreateFlags.NONE, 
                                 None)
            self.update_status(f"Exported HTML to {file.get_path()}")
        except GLib.Error as error:
            self.show_error_dialog(f"Error exporting HTML: {error.message}")
    
    def on_preview_clicked(self, action, param):
        self.get_editor_content(self.preview_content)
    
    def preview_content(self, content):
        # Create a complete HTML document
        html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Preview</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; padding: 20px; }}
    </style>
</head>
<body>
{content}
</body>
</html>"""
        
        # Create a temporary file for preview
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f:
            f.write(html_document.encode('utf-8'))
            temp_path = f.name
        
        # Open the file in the default web browser
        webbrowser.open('file://' + temp_path)
        self.update_status("Previewing in browser")
    
    def on_quit_clicked(self, action, param):
        self.get_editor_content(self.check_modified_for_quit)
    
    def check_modified_for_quit(self, content):
        if content and content.strip() and self.current_file is None:
            dialog = Adw.MessageDialog.new(self.win, "Unsaved Changes", 
                                          "Do you want to save the changes before quitting?")
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_default_response("save")
            dialog.connect("response", self.on_quit_response)
            dialog.present()
        else:
            self.quit()
    
    def on_quit_response(self, dialog, response):
        if response == "save":
            self.on_save_clicked(None, None)
            GLib.timeout_add(500, self.quit)  # Give time for save to complete
        elif response == "discard":
            self.quit()
    
    # Edit actions
    def on_cut_clicked(self, action, param):
        self.exec_js("execCommand('cut');")
    
    def on_copy_clicked(self, action, param):
        self.exec_js("execCommand('copy');")
    
    def on_paste_clicked(self, action, param):
        self.exec_js("execCommand('paste');")
    
    def on_select_all_clicked(self, action, param):
        self.exec_js("execCommand('selectAll');")
    
    def on_undo_clicked(self, action, param):
        self.exec_js("execCommand('undo');")
    
    def on_redo_clicked(self, action, param):
        self.exec_js("execCommand('redo');")
    
    # Format actions
    def on_bold_clicked(self, action, param):
        self.exec_js("execCommand('bold');")
    
    def on_italic_clicked(self, action, param):
        self.exec_js("execCommand('italic');")
    
    def on_underline_clicked(self, action, param):
        self.exec_js("execCommand('underline');")
    
    def on_heading1_clicked(self, action, param):
        self.exec_js("execCommand('formatBlock', '<h1>');")
    
    def on_heading2_clicked(self, action, param):
        self.exec_js("execCommand('formatBlock', '<h2>');")
    
    def on_bullet_list_clicked(self, action, param):
        self.exec_js("execCommand('insertUnorderedList');")
    
    def on_number_list_clicked(self, action, param):
        self.exec_js("execCommand('insertOrderedList');")
    
    def on_align_left_clicked(self, action, param):
        self.exec_js("execCommand('justifyLeft');")
    
    def on_align_center_clicked(self, action, param):
        self.exec_js("execCommand('justifyCenter');")
    
    def on_align_right_clicked(self, action, param):
        self.exec_js("execCommand('justifyRight');")
    
    def on_insert_image_clicked(self, action, param):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Insert Image")
        
        filters = Gtk.FileFilter.new()
        filters.add_mime_type("image/png")
        filters.add_mime_type("image/jpeg")
        filters.add_mime_type("image/gif")
        dialog.set_default_filter(filters)
        
        dialog.open(self.win, None, self.on_insert_image_dialog_response)
    
    def on_insert_image_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.insert_image(file)
        except GLib.Error as error:
            self.show_error_dialog(f"Error opening image: {error.message}")
    
    def insert_image(self, file):
        try:
            success, contents, _ = file.load_contents()
            if success:
                # Determine MIME type
                mime_type, _ = mimetypes.guess_type(file.get_path())
                if not mime_type:
                    mime_type = 'image/png'  # Default to PNG
                
                # Convert image to base64 for embedding
                base64_data = base64.b64encode(contents).decode('utf-8')
                data_url = f"data:{mime_type};base64,{base64_data}"
                
                # Insert image
                self.exec_js(f"insertImage('{data_url}');")
                self.update_status("Image inserted")
        except GLib.Error as error:
            self.show_error_dialog(f"Error inserting image: {error.message}")
    
    def on_insert_link_clicked(self, action, param):
        dialog = Adw.MessageDialog.new(self.win, "Insert Link", "Enter the URL:")
        
        # Add a URL entry
        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("https://example.com")
        url_entry.set_activates_default(True)
        dialog.set_extra_child(url_entry)
        
        # Add buttons
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("insert", "Insert")
        dialog.set_default_response("insert")
        dialog.set_response_appearance("insert", Adw.ResponseAppearance.SUGGESTED)
        
        # Connect response signal
        dialog.connect("response", self.on_insert_link_dialog_response, url_entry)
        dialog.present()
    
    def on_insert_link_dialog_response(self, dialog, response, url_entry):
        if response == "insert":
            url = url_entry.get_text()
            if url:
                self.exec_js(f"execCommand('createLink', '{url}');")
                self.update_status("Link inserted")
    
    def show_error_dialog(self, message):
        dialog = Adw.MessageDialog.new(self.win, "Error", message)
        dialog.add_response("ok", "OK")
        dialog.present()

def main():
    app = WYSIWYGTextEditor()
    app.run(sys.argv)

if __name__ == "__main__":
    main()
