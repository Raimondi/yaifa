# Copyright (c) 2000 Phil Thompson <phil@river-bank.demon.co.uk>
# Copyright (c) 2002 Detlev Offenbach <detlev@die-offenbachs.de>


import sys
import socket
import select
import codeop
import traceback
import bdb
import os
import inspect
import types
import string
from qt import PYSIGNAL

from DebugProtocol import *
from AsyncIO import *
from Config import ConfigVarTypeStrings


DebugClientInstance = None

def DebugClientPreEventLoopHook():
    """Called by PyQt just before the Qt event loop is entered.
    """
    if DebugClientInstance is not None:
        DebugClientInstance.preEventLoopHook()
		a = \
			1 + \
			1

def DebugClientPostEventLoopHook():
    """Called by PyQt just after the Qt event loop is left.
    """
    if DebugClientInstance is not None:
        DebugClientInstance.postEventLoopHook()
 
# Make the hooks available to PyQt.
__builtins__.__dict__['__pyQtPreEventLoopHook__'] = DebugClientPreEventLoopHook
__builtins__.__dict__['__pyQtPostEventLoopHook__'] = DebugClientPostEventLoopHook


def DebugClientRawInput(prompt):
    """A replacement for the standard raw_input builtin that works with the
    event loop.
    """
    if DebugClientInstance is None:
        return DebugClientOrigRawInput(prompt)

    return DebugClientInstance.raw_input(prompt)

# Use our own raw_input().
DebugClientOrigRawInput = __builtins__.__dict__['raw_input']
__builtins__.__dict__['raw_input'] = DebugClientRawInput
 

class DebugClient(AsyncIO,bdb.Bdb):
    """DebugClient(self)

    Provide access to the Python interpeter from a debugger running in another
    process whether or not the Qt event loop is running.

    The protocol between the debugger and the client assumes that there will be
    a single source of debugger commands and a single source of Python
    statements.  Commands and statement are always exactly one line and may be
    interspersed.

    The protocol is as follows.  First the client opens a connection to the
    debugger and then sends a series of one line commands.  A command is either
    >Load<, >Step<, >StepInto< or a Python statement.

    The response to >Load< is...

    The response to >Step< and >StepInto< is...

    A Python statement consists of the statement to execute, followed (in a
    separate line) by >OK?<.  If the statement was incomplete then the response
    is >Continue<.  If there was an exception then the response is >Exception<.
    Otherwise the response is >OK<.  The reason for the >OK?< part is to
    provide a sentinal (ie. the responding >OK<) after any possible output as a
    result of executing the command.

    The client may send any other lines at any other time which should be
    interpreted as program output.

    If the debugger closes the session there is no response from the client.
    The client may close the session at any time as a result of the script
    being debugged closing or crashing.

    """
    def __init__(self):
        AsyncIO.__init__(self)
        bdb.Bdb.__init__(self)

        # The context to run the debugged program in.
        self.context = {'__name__' : '__main__'}

        # The list of complete lines to execute.
        self.buffer = ''

        self.connect(self,PYSIGNAL('lineReady'),self.handleLine)
        self.connect(self,PYSIGNAL('gotEOF'),self.sessionClose)

        self.pendingResponse = ResponseOK
        self.fncache = {}
        self.dircache = []
        self.eventLoopDepth = 0
        self.inRawMode = 0

        # So much for portability.
        if sys.platform == 'win32':
            self.skipdir = sys.prefix
        else:
            self.skipdir = os.path.join(sys.prefix,'lib/python' + sys.version[0:3])

    def preEventLoopHook(self):
        """
        Public method to handle the hook called when the Qt event loop is about
        to be entered.
        """
        if self.eventLoopDepth == 0:
            self.setNotifiers()
            self.flushResponse()

        self.eventLoopDepth = self.eventLoopDepth + 1

    def postEventLoopHook(self):
        """
        Public method to handle the hook called when the Qt event loop has
        terminated.
        """
        self.eventLoopDepth = self.eventLoopDepth - 1

        if self.eventLoopDepth == 0:
            self.setNotifiers()

    def raw_input(self,prompt):
        """
        Public method to implement raw_input() using the event loop.
        """
        self.write("%s%s\n" % (ResponseRaw, prompt))
        self.inRawMode = 1
        self.eventLoop()
        return self.rawLine

    def handleException(self):
        """
        Private method to handle the response to the debugger in the event of
        an exception.
        """
        self.pendingResponse = ResponseException

    def dispatch_exception(self, frame, arg):
        # Modified version of the one found in bdb.py
        # Here we always call user_exception
        self.user_exception(frame, arg)
        if self.quitting: raise bdb.BdbQuit
        return self.trace_dispatch

    def set_continue(self):
        # Modified version of the one found in bdb.py
        # Here we leave tracing switched on in order to get
        # informed of exceptions
        
        # Don't stop except at breakpoints or when finished
        self.stopframe = self.botframe
        self.returnframe = None
        self.quitting = 0

    def sessionClose(self):
        """
        Private method to close the session with the debugger and terminate.
        """
        try:
            self.set_quit()
        except:
            pass

        self.disconnect()
        sys.exit()

    def handleLine(self,line):
        """
        Private method to handle a complete line by trying to execute the lines
        accumulated so far.
        """
        # Remove any newline.
        if line[-1] == '\n':
            line = line[:-1]

        # If we are handling raw mode input then reset the mode and break out
        # of the current event loop.
        if self.inRawMode:
            self.inRawMode = 0
            self.rawLine = line
            self.eventExit = 1
            return

        eoc = line.find('<')

        if eoc >= 0 and line[0] == '>':
            # Get the command part and any argument.
            cmd = line[:eoc + 1]
            arg = line[eoc + 1:]
            
            if cmd == RequestVariables:
                scope, filter = eval(arg)
                self.dumpVariables(int(scope), filter)
                return
                
            if cmd == RequestStep:
                self.currentFrame = None
                self.set_step()
                self.eventExit = 1
                return

            if cmd == RequestStepOver:
                self.set_next(self.currentFrame)
                self.eventExit = 1
                return
                
            if cmd == RequestStepOut:
                self.set_return(self.currentFrame)
                self.eventExit = 1
                return
                
            if cmd == RequestStepQuit:
                self.currentFrame = None
                self.set_quit()
                self.eventExit = 1
                return

            if cmd == RequestContinue:
                self.currentFrame = None
                self.set_continue()
                self.eventExit = 1
                return

            if cmd == RequestOK:
                self.write(self.pendingResponse + '\n')
                self.pendingResponse = ResponseOK
                return

            if cmd == RequestLoad:
                self.fncache = {}
                self.dircache = []
                sys.argv = arg.split()
                sys.path[0] = os.path.dirname(sys.argv[0])
                self.running = sys.argv[0]
                self.firstFrame = None
                self.currentFrame = None
                self.inRawMode = 0
                self.eventLoopDepth = 0

                # This will eventually enter a local event loop.
                self.run('execfile("%s")' % (self.running),self.context)
                return

            if cmd == RequestBreak:
                fn, line, set, cond = arg.split(',')
                line = int(line)
                set = int(set)

                if set:
                    if cond == 'None':
                        cond = None
                    self.set_break(fn,line, 0, cond)
                else:
                    self.clear_break(fn,line)

                return
            
        if self.buffer:
            self.buffer = self.buffer + '\n' + line
        else:
            self.buffer = line

        try:
            code = codeop.compile_command(self.buffer,sys.stdin.name)
        except (OverflowError, SyntaxError):
            # Report the exception
            sys.last_type, sys.last_value, sys.last_traceback = sys.exc_info()
            map(self.write,traceback.format_exception_only(sys.last_type,sys.last_value))
            self.buffer = ''

            self.handleException()
        else:
            if code is None:
                self.pendingResponse = ResponseContinue
            else: 
                self.buffer = ''

                try:
                    exec code in self.context
                except SystemExit:
                    self.sessionClose()
                except:
                    # Report the exception and the traceback
                    try:
                        type, value, tb = sys.exc_info()
                        sys.last_type = type
                        sys.last_value = value
                        sys.last_traceback = tb
                        tblist = traceback.extract_tb(tb)
                        del tblist[:1]
                        list = traceback.format_list(tblist)
                        if list:
                            list.insert(0, "Traceback (innermost last):\n")
                            list[len(list):] = traceback.format_exception_only(type, value)
                    finally:
                        tblist = tb = None

                    map(self.write,list)

                    self.handleException()


    def write(self,s):
        sys.stdout.write(s)
        sys.stdout.flush()

    def interact(self):
        """
        Interact with whatever is on stdin and stdout - usually the debugger.
        This method will never terminate.
        """
        # Set the descriptors now and the notifiers when the QApplication
        # instance is created.
        global DebugClientInstance

        self.setDescriptors(sys.stdin,sys.stdout)
        DebugClientInstance = self

        # At this point the Qt event loop isn't running, so simulate it.
        self.eventLoop()

    def eventLoop(self):
        self.eventExit = None

        while self.eventExit is None:
            if self.eventLoopDepth > 0:
                qApp.processOneEvent()
            else:
                wrdy = []
    
                if AsyncPendingWrite(sys.stdout):
                    wrdy.append(sys.stdout)

                #if AsyncPendingWrite(sys.stderr):
                    #wrdy.append(sys.stderr)

                rrdy, wrdy, xrdy = select.select([sys.stdin],wrdy,[])

                if sys.stdin in rrdy:
                    self.readReady(sys.stdin.fileno())

                if sys.stdout in wrdy:
                    self.writeReady(sys.stdout.fileno())

                if sys.stderr in wrdy:
                    self.writeReady(sys.stderr.fileno())

        self.eventExit = None

    def connectDebugger(self,port):
        """
        Establish a session with the debugger and connect it to stdin, stdout
        and stderr.
        """
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.connect((DebugAddress,port))
        sock.setblocking(0)

        sys.stdin = AsyncFile(sock,sys.stdin.mode,sys.stdin.name)
        sys.stdout = AsyncFile(sock,sys.stdout.mode,sys.stdout.name)
        #sys.stderr = AsyncFile(sock,sys.stderr.mode,sys.stderr.name)

    def user_line(self,frame):
        """
        Re-implemented to handle the program about to execute a particular
        line.
        """
        line = frame.f_lineno

        # We never stop an line 0.
        if line == 0:
            return

        fn = self.absPath(frame.f_code.co_filename)

        # See if we are skipping at the start of a newly loaded program.
        if self.firstFrame is None:
            if fn != self.running:
                return

            self.firstFrame = frame

        self.currentFrame = frame
        
        self.write('%s%s,%d\n' % (ResponseLine,fn,line))
        self.eventLoop()

    def user_exception(self,frame,(exctype,excval,exctb)):
        if exctype == SystemExit:
            self.progTerminated(excval)
            
        elif exctype == SyntaxError:
            try:
                message, (filename, linenr, charnr, text) = excval
            except:
                exclist = []
            else:
                exclist = [message, (filename, linenr, charnr)]
            
            self.write("%s%s\n" % (ResponseSyntax, str(exclist)))
            
        else:
            if inspect.isclass(exctype):
                exctype = exctype.__name__
                
            if excval is None:
                excval = ''
                
            exclist = [str(exctype), str(excval)]
            
            tblist = traceback.extract_tb(exctb)
            tblist.reverse()
            
            for tb in tblist:
                filename, linenr, func, text = tb
                
                exclist.append((filename, linenr))
            
            self.write("%s%s\n" % (ResponseException, str(exclist)))
            
        self.eventLoop()

    def user_return(self,frame,retval):
        # The program has finished if we have just left the first frame.
        if frame == self.firstFrame:
            self.progTerminated(retval)

    def stop_here(self,frame):
        """
        Re-implemented to turn off tracing for files that are part of the
        debugger that are called from the application being debugged.
        """
        fn = frame.f_code.co_filename

        # Eliminate things like <string> and <stdin>.
        if fn[0] == '<':
            return 0

        #XXX - think of a better way to do this.  It's only a convience for
        #debugging the debugger - when the debugger code is in the current
        #directory.
        if os.path.basename(fn) in ['AsyncIO.py', 'DebugClient.py']:
            return 0

        # Eliminate anything that is part of the Python installation.
        #XXX - this should be a user option, or an extension of the meaning of
        # 'step into', or a separate type of step altogether, or have a
        #configurable set of ignored directories.
        afn = self.absPath(fn)

        if afn.find(self.skipdir) == 0:
                return 0

        return bdb.Bdb.stop_here(self,frame)

    def absPath(self,fn):
        """
        Private method to convert a filename to an absolute name using sys.path
        as a set of possible prefixes. The name stays relative if a file could
        not be found.
        """
        if os.path.isabs(fn):
            return fn

        # Check the cache.
        if self.fncache.has_key(fn):
            return self.fncache[fn]

        # Search sys.path.
        for p in sys.path:
            afn = os.path.normpath(os.path.join(p,fn))

            if os.path.exists(afn):
                self.fncache[fn] = afn
                d = os.path.dirname(afn)
                if (d not in sys.path) and (d not in self.dircache):
                    self.dircache.append(d)
                return afn

        # Search the additional directory cache
        for p in self.dircache:
            afn = os.path.normpath(os.path.join(p,fn))
            
            if os.path.exists(afn):
                self.fncache[fn] = afn
                return afn
                
        # Nothing found.
        return fn

    def progTerminated(self,status):
        """
        Private method to tell the debugger that the program has terminated.
        """
        if status is None:
            status = 0
        else:
            try:
                int(status)
            except:
                status = 1

        self.set_quit()
        self.write('%s%d\n' % (ResponseExit,status))

    def dumpVariables(self, scope, filter):
        """
        Private method to return the global variables and the
        local variables of the current frame
        """
        f = self.currentFrame
        
        if f is None:
            return
        
        if scope:
            dict = f.f_globals
        else:
            dict = f.f_locals
            
            if f.f_globals is f.f_locals:
                scope = -1
                
        varlist = [scope]
        
        if scope != -1:
            keylist = dict.keys()
            
            (vlist, klist) = self.formatVariablesList(keylist, dict, filter)
            varlist = varlist + vlist
            
            if len(klist):
                for key in klist:
                    cdict = dict[key].__dict__
                    keylist = cdict.keys()
                    (vlist, klist) = \
                        self.formatVariablesList(keylist, cdict, filter, 1, key)
                    varlist = varlist + vlist
                
        self.write('%s%s\n' % (ResponseVariables, str(varlist)))
    
    def formatVariablesList(self, keylist, dict, filter = [], classdict = 0, prefix = ''):
        """
        Private method to produce a formated variables list out
        of the dictionary passed in to it. If classdict is false,
        it builds a list of all class instances in dict. If it is
        true, we are formatting a class dictionary. In this case
        we prepend prefix to the variable names. Variables are
        only added to the list, if their type is not contained 
        in the filter list. The formated variables list (a list of 
        tuples of 3 values) and the list of class instances is returned.
        """
        varlist = []
        classes = []
        
        for key in keylist:
            # filter hidden attributes (filter #0)
            if 0 in filter and str(key)[:2] == '__':
                continue
            
            # special handling for '__builtins__' (it's way too big)
            if key == '__builtins__':
                rvalue = '<module __builtin__ (built-in)>'
                valtype = 'module'
            else:
                value = dict[key]
                valtypestr = str(type(value))[1:-1]
                if string.split(valtypestr,' ',1)[0] == 'class':
                    # handle new class type of python 2.2+
                    if ConfigVarTypeStrings.index('instance') in filter:
                        continue
                    valtype = valtypestr[7:-1]
                    classes.append(key)
                else:
                    valtype = valtypestr[6:-1]
                    try:
                        if ConfigVarTypeStrings.index(valtype) in filter:
                            continue
                        if valtype == 'instance':
                            classes.append(key)
                    except ValueError:
                        if ConfigVarTypeStrings.index('other') in filter:
                            continue
                    
                try:
                    rvalue = repr(value)
                except:
                    rvalue = ''
                    
                if classdict:
                    key = prefix + '.' + key
                    
            varlist.append((key, valtype, rvalue))
        
        return (varlist, classes)

# We are normally called by the debugger to execute directly.

if __name__ == '__main__':
    try:
        port = int(sys.argv[1])
    except:
        port = -1
    sys.argv = ['']
    sys.path[0] = ''
    debugClient = DebugClient()
    if port >= 0:
        debugClient.connectDebugger(port)
    debugClient.interact()
