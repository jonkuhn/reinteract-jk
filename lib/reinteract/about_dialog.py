# Copyright 2007, 2008 Owen Taylor
# Copyright 2007 Luis Medina
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gtk

import os
import sys

def _find_program_in_path(progname):
    try:
        path = os.environ['PATH']
    except KeyError:
        path = os.defpath

    for dir in path.split(os.pathsep):
        p = os.path.join(dir, progname)
        if os.path.exists(p):
            return p

    return None

def _find_url_open_program():
    if sys.platform == 'darwin':
        return '/usr/bin/open'

    for progname in ['xdg-open', 'htmlview', 'gnome-open']:
        path = _find_program_in_path(progname)
        if path != None:
            return path
    return None

def _open_url(dialog, url):
    prog = _find_url_open_program()
    os.spawnl(os.P_NOWAIT, prog, prog, url)

class AboutDialog(gtk.AboutDialog):
    def __init__(self):
        if _find_url_open_program() != None:
            gtk.about_dialog_set_url_hook(_open_url)

        gtk.AboutDialog.__init__(self)
        self.set_name("Reinteract")
        self.set_logo_icon_name("reinteract")
        self.set_copyright("Copyright \302\251 2007-2008 Owen Taylor, Red Hat, Inc., and others")
        self.set_website("http://www.reinteract.org")
        self.connect("response", lambda d, r: d.destroy())
