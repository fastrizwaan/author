#!/usr/bin/env python

# Portions and Adaptations Copyright 2023-2024 Hin-Tak Leung
# - Ported to GTK4

# This was originally written by Julita Inca AFAIK, first posted in
# https://lleksah.wordpress.com/2017/07/31/writing-my-first-web-browser-in-python-with-gtk/

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, WebKit, GLib

HISTORY_FILE = "/home/" + GLib.get_user_name() + "/browser2_history.html"
HOME_PAGE = "https://gnome.org"

webview = WebKit.WebView()
entry = Gtk.Entry()

def open_page(url):
    entry.set_text(url)
    webview.load_uri(url)

def open_history(button):
    open_page("file://" + HISTORY_FILE)

def on_load_changed(webview, event):
    url = webview.get_uri ()
    history_file = open(HISTORY_FILE, "a+")
    history_file.writelines("* <a href=\"" + url + "\">" + url + "</a><br>")
    history_file.close()

def on_enter(entry):
    url = entry.get_text()
    webview.load_uri(url)
    if (url == "about:history"):
        open_history(webview)
        return

    open_page(url)

def on_go_back(button):
    webview.go_back()

def on_go_forward(button):
    webview.go_forward()

import sys
if len(sys.argv) > 1:
    open_page(sys.argv[1])
else:
    open_page(HOME_PAGE)
webview.connect("load-changed", on_load_changed)

history_button = Gtk.Button.new_from_icon_name("open-menu-symbolic")
history_button.connect("clicked", open_history)

headerbar = Gtk.HeaderBar()
headerbar.set_show_title_buttons(True)
headerbar.pack_end(history_button)

go_back_button = Gtk.Button.new_from_icon_name("go-previous")
go_back_button.connect("clicked", on_go_back)

go_forward_button = Gtk.Button.new_from_icon_name("go-next")
go_forward_button.connect("clicked", on_go_forward)

headerbar.pack_start(go_back_button)
headerbar.pack_start(go_forward_button)

entry.connect("activate", on_enter)
headerbar.set_title_widget(entry)

def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_title("GUADEC 2017")
    win.set_default_size(1280,720)
    win.set_titlebar(headerbar)
    win.set_child(webview)
    win.present()

app = Gtk.Application()
app.connect('activate', on_activate)

app.run(None)
