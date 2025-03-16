
# Author

**A simple, open-source WYSIWYG HTML editor that lets you create and edit documents effortlessly with instant visual feedback.**

*Write effortlessly, see instantly.*

## Overview

Author is a lightweight, GTK-based application built with Python and WebKit, offering a user-friendly interface for creating and editing HTML documents in a What-You-See-Is-What-You-Get (WYSIWYG) environment. Whether you're drafting a blog post, designing a webpage, or jotting down notes, Author provides the tools you need with real-time preview.

## Features

- **Rich Text Editing**: Bold, italic, underline, strikethrough, headings, lists, and text alignment.
- **Font Customization**: Choose from system fonts and adjust sizes.
- **Color Options**: Set text and background colors with a color picker.
- **File Operations**: New, open, save, save as, and print HTML files.
- **Search & Replace**: Find and replace text within your document.
- **Zoom Control**: Adjust zoom levels from 10% to 1000%.
- **Dark Mode**: Toggle between light and dark themes.
- **Cross-Platform**: Runs on Linux (and potentially other platforms with GTK support).

## Screenshots

*(Add screenshots here, e.g., `![Main Window](screenshots/main_window.png)` after uploading them to the repo.)*

## Installation

### Prerequisites

- Python 3.6+
- GTK 4.0
- Adwaita (libadwaita) 1.0+
- WebKitGTK 6.0+
- Pango & PangoCairo

On a Debian-based system (e.g., Ubuntu), install dependencies with:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0 gir1.2-pango-1.0 gir1.2-pangocairo-1.0
```

### Clone and Run

1. Clone the repository:
   ```bash
   git clone https://github.com/fastrizwaan/author.git
   cd author
   ```
2. Run the app:
   ```bash
   python3 author.py
   ```

## Usage

1. Launch the app with `python3 author.py`.
2. Use the toolbar to format text, adjust fonts, or apply colors.
3. Save your work as an HTML file via *File > Save* or *Save As*.
4. Open existing HTML files with *File > Open*.
5. Toggle dark mode with the brightness button in the view group.

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository.
2. Create a branch: `git checkout -b feature/your-feature-name`.
3. Commit your changes: `git commit -m "Add your feature"`.
4. Push to your fork: `git push origin feature/your-feature-name`.
5. Open a pull request.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) (feel free to add one).

## License

This project is licensed under the [MIT License](LICENSE). See the LICENSE file for details.

## Acknowledgments

- Built with [GTK 4](https://www.gtk.org/), [Libadwaita](https://gitlab.gnome.org/GNOME/libadwaita), and [WebKitGTK](https://webkitgtk.org/).
- Created by [fastrizwaan](https://github.com/fastrizwaan).

