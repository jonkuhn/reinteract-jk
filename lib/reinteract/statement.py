# Copyright 2007, 2008 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import copy
import traceback
import sys
import numpy
import retable

from custom_result import CustomResult
from notebook import HelpResult
from rewrite import Rewriter
from stdout_capture import StdoutCapture

class WarningResult(object):
    def __init__(self, message):
        self.message = message
    
class Statement:
    """

    Class that wraps a section of Python code for compilation and execution. (The section
    doesn't actually have to be a single statement.)

    """

    NEW = 0
    COMPILE_SUCCESS = 1
    COMPILE_ERROR = 2
    EXECUTING = 3
    EXECUTE_SUCCESS = 4
    EXECUTE_ERROR = 5
    INTERRUPTED = 6

    def __init__(self, text, worksheet, parent=None):
        self.__text = text
        self.__worksheet = worksheet

        #: current state of the statement (one of the constants defined within the class)
        self.state = Statement.NEW

        #: description of the imports of the statement. Set after compilation. See L{Rewriter.get_imports}
        self.imports = None
        #: names imported from __future__. Used when compiling subsequent statements
        self.future_features = None

        #: scope at the end of successful execution
        self.result_scope = None
        #: list of results from the statement. Set after successful execution
        self.results = None

        #: error_message: error message in case of compilation or execution error
        self.error_message = None
        #: line where error occured in case of compilation or execution error
        self.error_line = None
        #: offset within line of a compilation error
        self.error_offset = None

        self.__compiled = None
        self.__parent_future_features = None

        self.set_parent(parent)

        self.__stdout_buffer = None
        self.__capture = None

    def set_parent(self, parent):
        """Set the parent statement for this statement.

        The parent statement provides context for the compilation and execution
        of a statement. After setting the parent statement the statement will
        need to be reexecuted and may need to be recompiled. (Recompilation is
        needed if the set of features imported from __future__ changes.)

        """
        self.__parent = parent

    def compile(self):
        """Compile the statement.

        @returns: True if the statement was succesfully compiled.

        """

        if self.__parent:
            new_future_features = self.__parent.future_features
        else:
            new_future_features = None

        if new_future_features != self.__parent_future_features:
            self.__parent_future_features = new_future_features
        elif self.state != Statement.NEW:
            return self.state != Statement.COMPILE_ERROR

        self.error_message = None
        self.error_line = None
        self.error_offset = None

        try:
            rewriter = Rewriter(self.__text, future_features=self.__parent_future_features)
            self.imports = rewriter.get_imports()
            self.__compiled, self.__mutated = rewriter.rewrite_and_compile(output_func_name='reinteract_output')
        except SyntaxError, e:
            self.error_message = e.msg
            self.error_line = e.lineno
            self.error_offset = e.offset
            self.state = Statement.COMPILE_ERROR
            return False
        except UnsupportedSyntaxError, e:
            self.error_message = e.value
            self.state = Statement.COMPILE_ERROR
            return False

        self.future_features = self.__parent_future_features
        if self.imports != None:
            for module, symbols in self.imports:
                if module == '__future__' and symbols != '*' and symbols[0][0] != '.':
                    merged = set()
                    if self.future_features:
                        merged.update(self.future_features)
                    merged.update((sym for sym, _ in symbols))
                    self.future_features = sorted(merged)

        self.state = Statement.COMPILE_SUCCESS
        return True

    def do_output(self, *args):
        """Called by execution of statements with non-None output (see L{Rewriter})"""

        if len(args) == 1:
            arg = args[0]
            
            if args[0] == None:
                return
            elif isinstance(args[0], CustomResult) or isinstance(args[0], HelpResult):
                self.results.append(args[0])
            elif isinstance(args[0], numpy.ndarray):
                self.results.append(retable.NumpyNdArrayTableResult(args[0]))
                self.result_scope['_'] = args[0]
            elif isinstance(args[0], list)\
              or isinstance(args[0], dict)\
              or isinstance(args[0], tuple):
                self.results.append(retable.PyContainerTableResult(args[0]))
                self.result_scope['_'] = args[0]
            else:
                self.results.append(repr(args[0]))
                self.result_scope['_'] = args[0]
        else:
            self.results.append(repr(args))
            self.result_scope['_'] = args

    def do_print(self, *args):
        """Called by execution of print statements (see L{Rewriter})"""

        self.results.append(" ".join(map(str, args)))

    def __stdout_write(self, str):
        if self.__stdout_buffer == None:
            self.__stdout_buffer = str
        else:
            self.__stdout_buffer += str

        pos = 0
        while True:
            next = self.__stdout_buffer.find("\n", pos)
            if next < 0:
                break
            self.results.append(self.__stdout_buffer[pos:next])
            pos = next + 1
            
        if pos > 0:
            self.__stdout_buffer = self.__stdout_buffer[pos:]

    def before_execute(self):
        """Set up for execution

        Although before_execute() and after_execute() are automatically called when
        execute() is invoked, provision is made to call them separately to allow
        the caller to add locking so that execute() can be interrupted safely.
        before_execute() and after_execute() must not themselves not be interrupted
        and after_execute() must be called if before_execute() is called; with those
        provisions the operation of execute() can be interrupted at any point and
        the statement will be left in a sane state.

        """
        assert self.state != Statement.NEW and self.state != Statement.COMPILE_ERROR
        self.state = Statement.EXECUTING

        self.__worksheet.global_scope['__reinteract_statement'] = self
        self.__capture = StdoutCapture(self.__stdout_write)
        self.__capture.push()

    def after_execute(self):
        """Do cleanup tasks after execution

        See before_setup for details.

        """

        if self.state == Statement.EXECUTING:
            self.state = Statement.INTERRUPTED
            self.results = None
            self.result_scope = None

        self.__worksheet.global_scope['__reinteract_statement'] = None
        self.__stdout_buffer = None
        self.__capture.pop()
        self.__capture = None

    def __do_execute(self):
        root_scope = self.__worksheet.global_scope
        if self.__parent:
            scope = copy.copy(self.__parent.result_scope)
        else:
            scope = copy.copy(root_scope)

        self.results = []
        self.result_scope = scope
        self.__stdout_buffer = None

        for mutation in self.__mutated:
            if isinstance(mutation, tuple):
                variable, method = mutation
            else:
                variable = mutation

            try:
                if variable in scope and type(scope[variable]) != type(sys):
                    scope[variable] = copy.copy(scope[variable])
            except:
                self.results.append(WarningResult("Variable '%s' apparently modified, but can't copy it" % variable))

        try:
            exec self.__compiled in scope, scope
            if self.__stdout_buffer != None and self.__stdout_buffer != '':
                self.results.append(self.__stdout_buffer)
            self.state = Statement.EXECUTE_SUCCESS
        except KeyboardInterrupt, e:
            raise e
        except:
            self.results = None
            self.result_scope = None
            error_type, value, tb = sys.exc_info()

            self.error_message = ("\n".join(traceback.format_tb(tb)[2:]) + "\n".join(traceback.format_exception_only(error_type, value))).strip()
            self.error_line = tb.tb_frame.f_lineno
            self.error_offset = None

            self.state = Statement.EXECUTE_ERROR

        return self.state == Statement.EXECUTE_SUCCESS

    def execute(self):
        """Execute the statement"""
        was_in_execute = self.state == Statement.EXECUTING
        if not was_in_execute:
            self.before_execute()
        try:
            return self.__do_execute()
        finally:
            if not was_in_execute:
                self.after_execute()

    def mark_for_execute(self):
        """Mark a statement that executed succesfully as needing execution again"""
        if self.state != Statement.NEW and self.state != Statement.COMPILE_ERROR:
            self.state = Statement.COMPILE_SUCCESS

if __name__=='__main__':
    import stdout_capture
    from notebook import Notebook
    from worksheet import Worksheet

    from test_utils import assert_equals

    stdout_capture.init()

    notebook = Notebook()
    worksheet = Worksheet(notebook)

    def expect_result(text, result):
        s = Statement(text, worksheet)
        s.compile()
        s.execute()
        if isinstance(result, basestring):
            assert_equals(s.results[0], result)
        else:
            assert_equals(s.results, result)

    # A bare expression should give the repr of the expression
    expect_result("'a'", repr('a'))
    expect_result("1,2", repr((1,2)))

    # Print, on the other hand, gives the string form of the expression, with
    # one result object per output line
    expect_result("print 'a'", 'a')
    expect_result("print 'a', 'b'", ['a b'])
    expect_result("print 'a\\nb'", ['a','b'])

    # Test that we copy a variable before mutating it (when we can detect
    # the mutation)
    s1 = Statement("b = [0]", worksheet)
    s1.compile()
    s1.execute()
    s2 = Statement("b[0] = 1", worksheet, parent=s1)
    s2.compile()
    s2.execute()
    s3 = Statement("b[0]", worksheet, parent=s2)
    s3.compile()
    s3.execute()
    assert_equals(s3.results[0], "1")
    
    s2a = Statement("b[0]", worksheet, parent=s1)
    s2a.compile()
    s2a.execute()
    assert_equals(s2a.results[0], "0")

    # Tests of catching errors
    s1 = Statement("b = ", worksheet)
    assert_equals(s1.compile(), False)
    assert s1.error_message != None

    s1 = Statement("b", worksheet)
    assert_equals(s1.compile(), True)
    assert_equals(s1.execute(), False)
    assert s1.error_message != None

    # Tests of 'from __future__ import...'
    s1 = Statement("from __future__ import division", worksheet)
    s1.compile()
    assert_equals(s1.future_features, ['division'])
    s2 = Statement("from __future__ import with_statement", worksheet, parent=s1)
    s2.compile()
    assert_equals(s2.future_features, ['division', 'with_statement'])

    s1 = Statement("import  __future__", worksheet) # just a normal import
    assert_equals(s1.future_features, None)
