# Copyright 2007, 2008 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import cairo
import gtk
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_cairo import RendererCairo, FigureCanvasCairo
import numpy

import reinteract.custom_result as custom_result

class _PlotResultCanvas(FigureCanvasCairo):
    def draw_event(*args):
        # Since we never change anything about the figure, the only time we
        # need to redraw is in response to an expose event, which we handle
        # ourselves
        pass

class PlotResult(custom_result.CustomResult):
    def __init__(self, *args, **kwargs):
        self.__args = args
        self.__kwargs = kwargs

    def create_widget(self):
        widget = PlotWidget(self)
        widget.axes.plot(*self.__args, **self.__kwargs)

        return widget
    
class ImshowResult(custom_result.CustomResult):
    def __init__(self, *args, **kwargs):
        self.__args = args
        self.__kwargs = kwargs

    def create_widget(self):
        widget = PlotWidget(self)
        widget.axes.imshow(*self.__args, **self.__kwargs)

        return widget
    
class PlotWidget(gtk.DrawingArea):
    __gsignals__ = {
        'button-press-event': 'override',
        'button-release-event': 'override',
        'expose-event': 'override',
        'size-allocate': 'override',
        'unrealize': 'override'
    }

    def __init__(self, result):
        gtk.DrawingArea.__init__(self)
        self.figure = Figure(facecolor='white', figsize=(6,4.5))
        self.canvas = _PlotResultCanvas(self.figure)

        self.axes = self.figure.add_subplot(111)

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE)

        self.cached_contents = None

    def do_expose_event(self, event):
        cr = self.window.cairo_create()

        if not self.cached_contents:
            self.cached_contents = cr.get_target().create_similar(cairo.CONTENT_COLOR,
                                                                  self.allocation.width, self.allocation.height)

            renderer = RendererCairo(self.figure.dpi)
            renderer.set_width_height(self.allocation.width, self.allocation.height)
            renderer.set_ctx_from_surface(self.cached_contents)

            self.figure.draw(renderer)

        # event.region is not bound: http://bugzilla.gnome.org/show_bug.cgi?id=487158
#        gdk_context = gtk.gdk.CairoContext(renderer.ctx)
#        gdk_context.region(event.region)
#        gdk_context.clip()

        cr.set_source_surface(self.cached_contents, 0, 0)
        cr.paint()

    def do_size_allocate(self, allocation):
        if allocation.width != self.allocation.width or allocation.height != self.allocation.height:
            self.cached_contents = None

        gtk.DrawingArea.do_size_allocate(self, allocation)

    def do_unrealize(self):
        gtk.DrawingArea.do_unrealize(self)

        self.cached_contents = None

    def do_button_press_event(self, event):
        if event.button == 3:
            custom_result.show_menu(self, event, save_callback=self.__save)
            return True
        else:
            return True
    
    def do_button_release_event(self, event):
        return True

    def do_realize(self):
        gtk.DrawingArea.do_realize(self)
        cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
        self.window.set_cursor(cursor)
    
    def do_size_request(self, requisition):
        try:
            # matplotlib < 0.98
            requisition.width = self.figure.bbox.width()
            requisition.height = self.figure.bbox.height()
        except TypeError:
            # matplotlib >= 0.98
            requisition.width = self.figure.bbox.width
            requisition.height = self.figure.bbox.height
            

    def __save(self, filename):
        # The save/restore here was added to matplotlib's after 0.90. We duplicate
        # it for compatibility with older versions. (The code would need modification
        # for 0.98 and newer, which is the reason for the particular version in the
        # check)

        version = [int(x) for x in matplotlib.__version__.split('.')]
        need_save = version[:2] < [0, 98]
        if need_save:
            orig_dpi = self.figure.dpi.get()
            orig_facecolor = self.figure.get_facecolor()
            orig_edgecolor = self.figure.get_edgecolor()

        try:
            self.canvas.print_figure(filename)
        finally:
            if need_save:
                self.figure.dpi.set(orig_dpi)
                self.figure.set_facecolor(orig_facecolor)
                self.figure.set_edgecolor(orig_edgecolor)
                self.figure.set_canvas(self.canvas)

#    def do_size_allocate(self, allocation):
#        gtk.DrawingArea.do_size_allocate(self, allocation)
#        
#        dpi = self.figure.dpi.get()
#        self.figure.set_size_inches (allocation.width / dpi, allocation.height / dpi)

def _validate_args(args):
    #
    # The matplotlib argument parsing is a little wonky
    #
    #  plot(x, y, 'fmt', y2)
    #  plot(x1, y2, x2, y2, 'fmt', y3)
    # 
    # Are valid, but
    #
    #  plot(x, y, y2)
    #
    # is not. We just duplicate the algorithm here
    #
    l = len(args)
    i = 0
    while True:
        xi = None
        yi = None
        formati = None
        
        remaining = l - i
        if remaining == 0:
            break
        elif remaining == 1:
            yi = i
            i += 1
        # The 'remaining != 3 and' encapsulates the wonkyness referred to above
        elif remaining == 2 or (remaining != 3 and not isinstance(args[i + 2], basestring)):
            # plot(...., x, y [, ....])
            xi = i
            yi = i + 1
            i += 2
        else:
            # plot(....., x, y, format [, ...])
            xi = i
            yi = i + 1
            formati = i + 2
            i += 3

        if xi != None:
            arg = args[xi]
            if isinstance(arg, numpy.ndarray):
                xshape = arg.shape
            elif isinstance(arg, list):
                # Not supporting nested python lists here
                xshape = (len(arg),)
            else:
                raise TypeError("Expected numpy array or list for argument %d" % (xi + 1))
        else:
            xshape = None

        # y isn't optional, pretend it is to preserve code symmetry
            
        if yi != None:
            arg = args[yi]
            if isinstance(arg, numpy.ndarray):
                yshape = arg.shape
            elif isinstance(arg, list):
                # Not supporting nested python lists here
                yshape = (len(arg),)
            else:
                raise TypeError("Expected numpy array or list for argument %d" % (yi + 1))
        else:
            yshape = None

        if xshape != None and yshape != None and xshape != yshape:
            raise TypeError("Shapes of arguments %d and %d aren't compatible" % ((xi + 1), (yi + 1)))
        
        if formati != None and not isinstance(args[formati], basestring):
            raise TypeError("Expected format string for argument %d" % (formati + 1))


def plot(*args, **kwargs):
    _validate_args(args)
    return PlotResult(*args, **kwargs)

def imshow(*args, **kwargs):
    return ImshowResult(*args, **kwargs)
