import sys
import gtk
import csv
import numpy
import gobject
import reinteract.custom_result as custom_result

class NumpyNdArrayTableResult(custom_result.CustomResult):
    def __init__(self, obj, dimensions=(500,200)):
        """
        @type  obj: L{numpy.ndarray} or ...
        @param obj: An object of a supported type to be turned into a table.
        @type  dimensions: L{tuple}
        @param dimensions: A tuple (width, height) of the size of the table
        """
        self.obj = obj
        self.dimensions = dimensions

    def create_widget(self):
        widget = NumpyArrayWidget(self)

        return widget

class PyContainerTableResult(custom_result.CustomResult):
    def __init__(self, obj, dimensions=(500,200)):
        """
        @type  obj: sequency or mapping
        @param obj: An object of a supported type to be turned into a table.
        @type  dimensions: L{tuple}
        @param dimensions: A tuple (width, height) of the size of the table
        """
        self.obj = obj
        self.dimensions = dimensions

    def create_widget(self):
        widget = PyContainerWidget(self)
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
    __gsignals__ =\
    {
        'button-press-event':'override'
    }
    def __init__(self, numCols, colNames, colTypes, treeStore, dimensions):
        # create the TreeView using treestore
        self.__treeview = gtk.TreeView(treeStore)

        # create the TreeViewColumns to display data
        self.__tvCols = []
        self.__cellRenderers = []
        for col in range(numCols):
            if col == 0:
                tvcol = gtk.TreeViewColumn(colNames[col])
                self.__tvCols.append(tvcol)
                self.__treeview.append_column(tvcol)
                cellRenderer = gtk.CellRendererText()
                tvcol.pack_start(cellRenderer, True)
                tvcol.add_attribute(cellRenderer, 'text', col)
                tvcol.set_resizable(True)
                self.__cellRenderers.append(cellRenderer)
            else:
                tvcol = gtk.TreeViewColumn(colNames[col])
                self.__tvCols.append(tvcol)
                self.__treeview.append_column(tvcol)
                if colTypes[col] == gobject.TYPE_INT64:
                    cellRenderer = CellRendererNumericText('%d')
                    tvcol.pack_start(cellRenderer, True)
                    tvcol.add_attribute(cellRenderer, 'value', col)
                elif colTypes[col] == gobject.TYPE_DOUBLE:
                    cellRenderer = CellRendererNumericText('%f')
                    tvcol.pack_start(cellRenderer, True)
                    tvcol.add_attribute(cellRenderer, 'value', col)
                elif colTypes[col] == gobject.TYPE_STRING:
                    cellRenderer = gtk.CellRendererText()
                    tvcol.pack_start(cellRenderer, True)
                    tvcol.add_attribute(cellRenderer, 'text', col)
                #tvcol.set_sort_column_id(col)
                tvcol.set_resizable(True)
                self.__cellRenderers.append(cellRenderer)

        # Show grid lines
        self.__treeview.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)

        gtk.ScrolledWindow.__init__(self)
        self.set_border_width(10)
        self.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.add(self.__treeview)
        self.set_size_request(dimensions[0], dimensions[1])
        self.__treeview.show()

    def do_button_press_event(self, event):
        if event.button == 3:
            custom_result.show_menu(self, event, save_callback=self.save)
            return True
        else:
            return gtk.TreeView.do_button_press_event(self, event)

    def save(self, filename):
        self.__result.dataset.saveFile(filename)

class NumpyArrayWidget(ScrolledTableWidget):
    def __init__(self, result):
        self.__result = result
        self.__oneDimAsRow = True
        self.__numDataCols = 0
        self.__dataColNames = []
        self.__dataType = None

        if isinstance(result.obj, numpy.ndarray):
            self.__init_numpy_ndarray()
        else:
            raise ValueError(\
                'NumpyArrayWidget: result.obj is of an unsupported type')

        ScrolledTableWidget.__init__(\
            self,
            numCols    = self.__numDataCols+1,
            colNames   = ['indices']+self.__dataColNames,
            colTypes   = [gobject.TYPE_STRING]*(self.__numDataCols+1),
            treeStore  = self.__treestore,
            dimensions = self.__result.dimensions)


    def __add_numpy_ndarray(self, parent, arrNd, preidx=''):
        if len(arrNd.shape) <= 2:
            for i in xrange(len(arrNd)):
                data = arrNd[i]
                if not hasattr(data, '__iter__'):
                    data = [data]
                idxstr = preidx+'[%d]'%i
                row = [idxstr]
                for value in data:
                    row.append(str(value))
                self.__treestore.append(parent, row)
        else:
            for i in xrange(len(arrNd)):
                child = arrNd[i]
                child_dim = len(arrNd[i].shape)
                idxstr = preidx+'[%d]'%i
                row = [idxstr] + ['-'*child_dim]*self.__numDataCols
                thisrow = self.__treestore.append(parent, row)
                self.__add_numpy_ndarray(thisrow, child, idxstr)

    def __init_numpy_ndarray(self):
        result = self.__result

        shape = result.obj.shape
        if len(shape) == 1:
            higher_dim = tuple()
            if self.__oneDimAsRow:
                self.__numDataCols = shape[0]
            else:
                self.__numDataCols = 1
        else:
            higher_dim = shape[0:-2]
            self.__numDataCols = shape[-1]

        for col in xrange(self.__numDataCols):
            if len(shape) == 1 and not self.__oneDimAsRow:
                self.__dataColNames.append('[%d]'%col)
            else:
                self.__dataColNames.append('[%d]'%col)
        
        args = (gobject.TYPE_STRING,) * (self.__numDataCols+1)
        self.__treestore = gtk.TreeStore(*args)

        # we'll add some data now
        if len(shape) == 1 and self.__oneDimAsRow:
            data = list(result.obj)
            if not hasattr(row, '__iter__'):
                row = [data]
            row = ['[0]']
            for value in data:
                row.append(str(value))
                
            self.__treestore.append(None, row)
        else:
            self.__add_numpy_ndarray(None, result.obj)

class PyContainerWidget(ScrolledTableWidget):
    def __init__(self, result):
        self.__result = result

        if hasattr(result.obj, '__getitem__'):
            self.__init_pycol()
        else:
            raise ValueError(\
                'NumpyArrayWidget: result.obj is of an unsupported type')

        ScrolledTableWidget.__init__(\
            self,
            numCols    = 2,
            colNames   = ['indices', 'value'],
            colTypes   = [gobject.TYPE_STRING]*2,
            treeStore  = self.__treestore,
            dimensions = self.__result.dimensions)


    def __add_pycol(self, parent, pycol, preidx=''):
        if hasattr(pycol, '__getitem__') and hasattr(pycol, '__len__'):
            if hasattr(pycol, 'keys'):
                for key in pycol.keys():
                    child = pycol[key]
                    idxstr = preidx+'[%s]'%repr(key)
                    row = [idxstr, repr(child)]
                    thisrow = self.__treestore.append(parent, row)
                    self.__add_pycol(thisrow, child, idxstr)
            elif len(pycol) > 1:
                for i in xrange(len(pycol)):
                    child = pycol[i]
                    idxstr = preidx+'[%s]'%repr(i)
                    row = [idxstr, repr(child)]
                    thisrow = self.__treestore.append(parent, row)
                    self.__add_pycol(thisrow, child, idxstr)

    def __init_pycol(self):
        result = self.__result

        args = (gobject.TYPE_STRING,) * 2 
        self.__treestore = gtk.TreeStore(*args)
        self.__add_pycol(None, result.obj)
