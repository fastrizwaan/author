#!/usr/bin/env python3

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QComboBox, QFileDialog, QMessageBox,
    QVBoxLayout, QWidget
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QIcon, QAction, QFont

class RichTextEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Rich Text Editor")
        self.setGeometry(100, 100, 1000, 700)

        self.current_file = None
        self.is_modified = False

        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)

        # WebEngineView for HTML editing
        self.webview = QWebEngineView()
        self.layout.addWidget(self.webview)
        self.webview.setHtml(self.initial_html())
        self.webview.loadFinished.connect(self.on_load_finished)  # Inject JS after load

        # File actions
        new_action = QAction(QIcon.fromTheme("document-new"), "New", self)
        new_action.triggered.connect(self.new_file)
        self.toolbar.addAction(new_action)

        open_action = QAction(QIcon.fromTheme("document-open"), "Open", self)
        open_action.triggered.connect(self.open_file)
        self.toolbar.addAction(open_action)

        save_action = QAction(QIcon.fromTheme("document-save"), "Save", self)
        save_action.triggered.connect(self.save_file)
        self.toolbar.addAction(save_action)

        self.toolbar.addSeparator()

        # Formatting actions
        bold_action = QAction(QIcon.fromTheme("format-text-bold"), "Bold", self)
        bold_action.triggered.connect(lambda: self.exec_command("bold"))
        self.toolbar.addAction(bold_action)

        italic_action = QAction(QIcon.fromTheme("format-text-italic"), "Italic", self)
        italic_action.triggered.connect(lambda: self.exec_command("italic"))
        self.toolbar.addAction(italic_action)

        underline_action = QAction(QIcon.fromTheme("format-text-underline"), "Underline", self)
        underline_action.triggered.connect(lambda: self.exec_command("underline"))
        self.toolbar.addAction(underline_action)

        self.toolbar.addSeparator()

        # Font family combo
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Arial", "Times New Roman", "Courier New", "Verdana"])
        self.font_combo.setCurrentText("Arial")
        self.font_combo.currentTextChanged.connect(self.change_font)
        self.toolbar.addWidget(self.font_combo)

        # Font size combo
        self.size_combo = QComboBox()
        self.size_combo.addItems([str(i) for i in range(8, 25, 2)] + ["28", "32", "36"])
        self.size_combo.setCurrentText("12")
        self.size_combo.currentTextChanged.connect(self.change_font_size)
        self.toolbar.addWidget(self.size_combo)

        self.toolbar.addSeparator()

        # Alignment actions
        align_left = QAction(QIcon.fromTheme("format-justify-left"), "Align Left", self)
        align_left.triggered.connect(lambda: self.exec_command("justifyLeft"))
        self.toolbar.addAction(align_left)

        align_center = QAction(QIcon.fromTheme("format-justify-center"), "Align Center", self)
        align_center.triggered.connect(lambda: self.exec_command("justifyCenter"))
        self.toolbar.addAction(align_center)

        align_right = QAction(QIcon.fromTheme("format-justify-right"), "Align Right", self)
        align_right.triggered.connect(lambda: self.exec_command("justifyRight"))
        self.toolbar.addAction(align_right)

        # Keyboard shortcuts
        self.webview.keyPressEvent = self.handle_key_press

    def initial_html(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial; font-size: 12pt; margin: 20px; line-height: 1.5; }
                img { max-width: 100%; }
            </style>
        </head>
        <body contenteditable="true" oninput="window.modified = true;"><p> </p></body>
        </html>
        """

    def on_load_finished(self, ok):
        if ok:
            # Reset modified flag after loading
            self.webview.page().runJavaScript("window.modified = false;")

    def check_modified(self):
        def callback(result):
            if result:
                self.is_modified = True
                self.update_title()
        self.webview.page().runJavaScript("window.modified", callback)

    def exec_command(self, command, value=None):
        script = f"document.execCommand('{command}', false, {value if value else 'null'});"
        self.webview.page().runJavaScript(script)
        self.webview.setFocus()
        self.check_modified()  # Check after each command

    def change_font(self, font):
        self.exec_command("fontName", f"'{font}'")
        self.check_modified()

    def change_font_size(self, size):
        self.exec_command("fontSize", str(int(int(size) / 2)))  # Convert pt to HTML size (approx)
        self.check_modified()

    def update_title(self):
        title = "Qt Rich Text Editor"
        if self.current_file:
            title = f"{os.path.basename(self.current_file)} - {title}"
        if self.is_modified:
            title = f"*{title}"
        self.setWindowTitle(title)

    def new_file(self):
        if self.check_save():
            self.webview.setHtml(self.initial_html())
            self.current_file = None
            self.is_modified = False
            self.update_title()

    def open_file(self):
        if self.check_save():
            file_name, _ = QFileDialog.getOpenFileName(self, "Open HTML File", "", "HTML Files (*.html *.htm)")
            if file_name:
                with open(file_name, "r", encoding="utf-8") as f:
                    html_content = f.read()
                self.webview.setHtml(html_content, QUrl.fromLocalFile(file_name))
                self.current_file = file_name
                self.is_modified = False
                self.update_title()

    def save_file(self):
        if not self.current_file:
            self.save_file_as()
        else:
            self.save_to_file(self.current_file)

    def save_file_as(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save HTML File", "Document.html", "HTML Files (*.html *.htm)")
        if file_name:
            self.current_file = file_name
            self.save_to_file(file_name)

    def save_to_file(self, file_name):
        def callback(content):
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(content)
            self.is_modified = False
            self.webview.page().runJavaScript("window.modified = false;")
            self.update_title()

        self.webview.page().toHtml(callback)

    def check_save(self):
        self.check_modified()  # Ensure latest state
        if not self.is_modified:
            return True
        reply = QMessageBox.question(
            self, "Save Changes?",
            "Do you want to save changes before proceeding?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Save:
            self.save_file()
            return not self.is_modified
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        return False

    def handle_key_press(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_B:
                self.exec_command("bold")
            elif event.key() == Qt.Key.Key_I:
                self.exec_command("italic")
            elif event.key() == Qt.Key.Key_U:
                self.exec_command("underline")
            elif event.key() == Qt.Key.Key_S:
                self.save_file()
            elif event.key() == Qt.Key.Key_N:
                self.new_file()
            elif event.key() == Qt.Key.Key_O:
                self.open_file()
        QWebEngineView.keyPressEvent(self.webview, event)

    def closeEvent(self, event):
        if self.check_save():
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = RichTextEditor()
    editor.show()
    sys.exit(app.exec())
