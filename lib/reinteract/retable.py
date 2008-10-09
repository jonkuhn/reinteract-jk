import sys
import gtk
import csv
import numpy
import gobject
import reinteract.custom_result as custom_result

class TableResult(custom_result.CustomResult):
    def __init__(self, tableobj, dimensions=(500,200)):
        """
        @type  tableobj: L{numpy.ndarray} or ...
        @param tableobj: An object of a supported type to be turned into a table.
        @type  dimensions: L{tuple}
        @param dimensions: A tuple (width, height) of the size of the table
        """
        self.tableobj = tableobj
        self.dimensions = dimensions

    def create_widget(self):
        widget = ScrolledTableWidget(self)

        return widget

class CellRendererNumericText(gtk.CellRendererText):
    __gproperties__ = {
        'value' : (gobject.TYPE_DOUBLE,
                  'value of the cell',
                  'value of the cell',
                  -1e308,
                  1e308,
                  0.0,
                  gobject.PARAM_WRITABLE)
        }

    def __init__(self, format='%f'):
        gobject.GObject.__init__(self)
        self.__format = format

    def do_set_property(self, property, value):
        if property.name == 'value':
            strvalue = self.__format % value
            gtk.CellRendererText.set_property(self, 'text', strvalue)
        else:
            raise AttributeError, 'unknown property %s' % property.name

gobject.type_register(CellRendererNumericText)

class ScrolledTableWidget(gtk.ScrolledWindow):
    def __init__(self, result):
        self.tbl = TableWidget(result)

        # create a new scrolled window.
        gtk.ScrolledWindow.__init__(self)

        self.set_border_width(10)
        self.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)

        self.add(self.tbl)
        self.set_size_request(result.dimensions[0], result.dimensions[1])
        self.tbl.show()

class TableWidget(gtk.TreeView):
    __gsignals__ =\
    {
        'button-press-event':'override'
    }
    def __init__(self, result):
        self.__result = result

        if isinstance(result.tableobj, numpy.ndarray):
            self.__init_numpy_ndarray()
        else:
            raise ValueError('Unsupported type for tableobj')

    def __init_numpy_ndarray(self):
        result = self.__result
        # create a TreeStore to use as the model
        shape = result.tableobj.shape
        num_rows = result.tableobj.shape[0]
        if len(shape) == 1:
            num_cols = 1
        elif len(shape) == 2:
            num_cols = result.tableobj.shape[1]
        else:
            raise ValueError('Unsupported array dimensions')
        
        # TODO: Check this on 32-bit installs
        if result.tableobj.dtype == numpy.dtype('int32'):
            data_type = gobject.TYPE_INT
        elif result.tableobj.dtype == numpy.dtype('int64'):
            data_type = gobject.TYPE_INT64
        elif result.tableobj.dtype == numpy.dtype('float64'):
            data_type = gobject.TYPE_DOUBLE
        elif result.tableobj.dtype == numpy.dtype('float32'):
            data_type = gobject.TYPE_DOUBLE
        # Maybe there is a nicer way to detect string types
        elif result.tableobj.dtype.name.startswith('|S'):
            data_type = gobject.TYPE_STRING

        args = (gobject.TYPE_STRING,) + (data_type,) * num_cols
        self.__liststore = gtk.ListStore(*args)

        # we'll add some data now
        for r in range(0, num_rows):
            row = result.tableobj[r]
            if not hasattr(row, '__iter__'):
                row = [row]
            row = ['[%d]'%r] + list(row)
            self.__liststore.append(row)

        # create the TreeView using treestore
        gtk.TreeView.__init__(self, self.__liststore)

        # create the TreeViewColumn to display the data
        self.tvCols = []
        self.cellRenderers = []
        for col in range(0, num_cols+1):
            if col == 0:
                tvcol = gtk.TreeViewColumn('row')
                self.tvCols.append(tvcol)
                self.append_column(tvcol)
                cellRenderer = gtk.CellRendererText()
                tvcol.pack_start(cellRenderer, True)
                tvcol.add_attribute(cellRenderer, 'text', col)
                tvcol.set_sort_column_id(col)
                tvcol.set_resizable(True)
                self.cellRenderers.append(cellRenderer)
            else:
                tvcol = gtk.TreeViewColumn('[%d]' % (col-1))
                self.tvCols.append(tvcol)
                self.append_column(tvcol)
                if data_type == gobject.TYPE_INT64:
                    cellRenderer = CellRendererNumericText('%d')
                    tvcol.pack_start(cellRenderer, True)
                    tvcol.add_attribute(cellRenderer, 'value', col)
                elif data_type == gobject.TYPE_DOUBLE:
                    cellRenderer = CellRendererNumericText('%f')
                    tvcol.pack_start(cellRenderer, True)
                    tvcol.add_attribute(cellRenderer, 'value', col)
                elif data_type == gobject.TYPE_STRING:
                    cellRenderer = gtk.CellRendererText()
                    tvcol.pack_start(cellRenderer, True)
                    tvcol.add_attribute(cellRenderer, 'text', col)
                tvcol.set_sort_column_id(col)
                tvcol.set_resizable(True)
                self.cellRenderers.append(cellRenderer)

        # make it searchable
        #self.set_search_column(0)

        # Allow drag and drop reordering of rows
        # self.set_reorderable(True)

        # Show grid lines
        self.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

    def do_button_press_event(self, event):
        if event.button == 3:
            custom_result.show_menu(self, event, save_callback=self.save)
            return True
        else:
            return gtk.TreeView.do_button_press_event(self, event)

    def save(self, filename):
        self.__result.dataset.saveFile(filename)
