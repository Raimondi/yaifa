#!/usr/bin/env python
#
# Make beautifier
#
# Author   : Philippe Fremy <pfremy@kde.org>
# 			 contributions from Adrian Thurston <adriant@ragel.ca>
# Version  : 1.1
# License  : Do whatever you want with this program!
# Warranty : None. Me and my program are not responsible for anything in the
# 			 world and more particularly on your computer.
#
# Usage : try --help

from string import *
import getopt
import sys
import os
import tempfile

### Default values for command-line options:
SCREENWIDTH = 80 	# Fallback value, current value is deduced from resize
MAKEPROG = [ "make" ]
HIDE_LIBTOOL = 1
HIDE_WOPT = 1
HIDE_DOPT = 0
HIDE_IOPT = 0
HIDE_LOPT = 0
HIDE_FOPT = 1
HIDE_MOPT = 1
USE_STDIN = 0
USE_COLOR = 1

### Add more if I miss some!
COMPILER_NAME = ["cc", "gcc", "g++", "cpp", "c++" ]

### Color codes:
#
#  The escape magic is:
#  <esc code>[<attribute>;<fg>;<bg>m
#  
#  <attribute> can be:
#  0 - Reset All Attributes (return to normal mode)
#  1 - Bright (Usually turns on BOLD)
#  2 - Dim
#  3 - Underline
#  5 - Blink
#  7 - Reverse
#  8 - Hidden
#  
#  <fg> is:     	<bg> is:    	  				
#  30 Black         40 Black                                        
#  31 Red           41 Red                                          
#  32 Green         42 Green                                        
#  33 Yellow        43 Yellow                                       
#  34 Blue          44 Blue                                         
#  35 Magenta       45 Magenta                                      
#  36 Cyan          46 Cyan                                         
#  37 White         47 White                                        
#  

colordict = { 
			"normal": 		"[0;37;40m", # disable bold when finishing
			#"normal": 		"[1;37;40m", # enable bold when finishing
			"unknown": 		"[1;37;44m",
			"warnother": 	"[1;36;40m",
			"wopt": 		"[1;37;40m",
			"iopt": 		"[1;36;40m",
			"lopt": 		"[1;35;40m",
			"dopt": 		"[1;32;40m",
			"fopt": 		"[1;37;40m",
			"mopt": 		"[1;37;40m",
			"uic": 			"[1;33;40m",
			"moc": 			"[1;33;40m",
			"dcopidl": 		"[1;33;40m",
			"dcopidl2cpp": 	"[1;33;40m"
			}

def processLine( words ):
	global HIDE_WOPT, HIDE_DOPT, HIDE_IOPT, HIDE_LOPT, HIDE_FOPT, HIDE_MOPT

	unknown = []
	hidden = [ words[0] ]
	includes = []
	defines = []
	warnopt = []
	warnother = []
	codegenopt = []
	archopt = []
	libopt = []
	for w in words[1:]:
		if   w[:2] == "-I" : includes.append( w )
		elif w[:2] == "-D" : defines.append( w )
		elif w[:2] == "-W" : warnopt.append( w )
		elif w[:2] == "-l" : libopt.append( w )
		elif w[:2] == "-L" : libopt.append( w )
		elif w == "-pedantic" : warnother.append( w )
		elif w == "-ansi" : warnother.append( w )
		elif w[:2] == "-f" : codegenopt.append( w )
		elif w == "-module" : unknown.append( w )
		elif w[:2] == "-m" : archopt.append( w )
		else: unknown.append( w )

	# result
	if HIDE_WOPT == 1 and len(warnopt)  > 0: hidden.append( "<-W>" )
	if HIDE_IOPT == 1 and len(includes) > 0: hidden.append( "<-I>" )
	if HIDE_DOPT == 1 and len(defines)  > 0: hidden.append( "<-D>" )
	if HIDE_LOPT == 1 and len(libopt)   > 0: hidden.append( "<-L>" )
	if HIDE_FOPT == 1 and len(codegenopt) > 0: hidden.append( "<-f>" )
	if HIDE_MOPT == 1 and len(archopt)  > 0: hidden.append( "<-m>" )

	unknown = hidden + warnother + unknown;
	formatOutput( unknown, "unknown", 1)
	if HIDE_WOPT == 0: formatOutput( warnopt, "wopt" )
	if HIDE_IOPT == 0: formatOutput( includes, "iopt" )
	if HIDE_DOPT == 0: formatOutput( defines, "dopt" )
	if HIDE_LOPT == 0: formatOutput( libopt, "lopt" )
	if HIDE_FOPT == 0: formatOutput( codegenopt, "fopt"  )
	if HIDE_MOPT == 0: formatOutput( archopt, "mopt"  )
	print

def outputline( line, colorcode ):
	global USE_COLOR, colordict

	if len( line ) == 0 : return
	if USE_COLOR: sys.stdout.write(colordict[ colorcode ])
	print line,
	if USE_COLOR: sys.stdout.write( colordict[ "normal" ] )
	print 

def formatOutput( words, colorcode, noindent = 0 ):
	global USE_COLOR, colordict

	if len(words) == 0: return

	if USE_COLOR: sys.stdout.write(colordict[ colorcode ])

	intro = " " * 4
	current = intro
	if noindent == 1:
		current = ""

	for w in words:
		if len(current) + len(w) + 1 >= SCREENWIDTH:
			print current,
			if USE_COLOR: sys.stdout.write(colordict[ colorcode ])
			print
			current = intro
		if len(current) > 1: current = current + " "
		current = current + w
	else:
		if len(current) > len( intro ): print current, 

	if USE_COLOR: sys.stdout.write( colordict[ "normal" ] )
	print


def usage():
	print "Make output beautifier. By default, run make and beautify its output.\nOptions are:"
	for o in opt_list:
		so, lo, have_arg, desc = o
		s = ''
		if len(so): s = s + so
		if len(so) and len(lo): s = s + ","
		if len(lo): s = s + lo
		if have_arg: s = s + "=<arg>"
		print "  ", s, "\t", desc

	print "All unrecognised options are passed to make."


opt_list = [	
	("-h", "--help", 		0, "This description"),
	(""  , "--stdin", 		0, "Read input from stdin. Don't launch make"),
	(""  , "--screenwidth",	1, "Output formatted for a screen of width <arg>"),
	(""  , "--use-colors",	0, "Colored output"),
	(""  , "--no-colors",	0, "Non colored output"),
	(""  , "--makeprog" , 	1, "Will run and parse the output of the program <arg> instead of 'make'."),
	(""  , "--hide-libtool", 	0,  "Displays just <libtool line> for all libtool lines"),
	(""  , "--show-libtool", 	0,  "Displays all libtool lines"),
	(""  , "--hide-wopt", 	0,  "Displays just <-W> for all -W options"),
	(""  , "--show-wopt", 	0,  "Displays all -W options"),
	(""  , "--hide-iopt", 	0,  "Displays just <-I> for all -I options"),
	(""  , "--show-iopt", 	0,  "Displays all -I options"),
	(""  , "--hide-dopt", 	0,  "Displays just <-D> for all -D options"),
	(""  , "--show-dopt", 	0,  "Displays all -D options"),
	(""  , "--hide-lopt", 	0,  "Displays just <-L> for all -l and -L options"),
	(""  , "--show-lopt", 	0,  "Displays all -l and -L options"),
	(""  , "--hide-fopt", 	0,  "Displays just <-f> for all -f options"),
	(""  , "--show-fopt", 	0,  "Displays all -f options"),
	(""  , "--hide-mopt", 	0,  "Displays just <-m> for all -m options"),
	(""  , "--show-mopt", 	0,  "Displays all -m options")
	]

def scan_args( args, option_list ):
	"""Returns a tuple (recognised_opts, remaining_args) from an arglist args
	and an option list option_list. 

	Option list format:
	(short option name, long option name, have extra argument, help text ).

	recognised_opts format: ("recognised option", "optional argument")

	All unrecognised argument are put into remaining_args
	"""
	
	remaining_args = []
	recognised_opts = []
	use_arg = 0
	for i in range( len(args) ):
		arg = args[i]
		arg_opt = ""

		if use_arg == 1:
			use_arg = 0
			if arg[0] != "-":
				recognised_opts[-1:] = [ (recognised_opts[-1][0], arg) ]
				continue

		if arg.find("=") != -1:
			l = split( arg, "=" )
			arg = l[0]
			arg_opt = l[1]

		for opt in opt_list:
			so, lo, have_arg, desc = opt
			if so == arg or lo == arg:
				recognised_opts.append( (arg, arg_opt) )
				if have_arg == 1 and len(arg_opt) == 0:
					use_arg = 1
				break
		else:
			remaining_args.append( arg )
	return ( recognised_opts,  remaining_args)
			

def guessScreenWidth():
	fname = tempfile.mktemp()
	os.system("resize > " + fname + " 2> /dev/null" )
	f = open(fname, "r")
	setColumn( f.readlines() )
	f.close()
	os.remove(fname)


def main():
	global USE_STDIN, MAKEPROG, SCREENWIDTH, COMPILER_NAME
	global HIDE_LIBTOOL, HIDE_WOPT, HIDE_DOPT, HIDE_IOPT, HIDE_LOPT
	global HIDE_FOPT, HIDE_MOPT, USE_COLOR, colordict

	guessScreenWidth()
	#print "width : ", SCREENWIDTH

	opts, args = scan_args( sys.argv[1:], opt_list )

#	print opts, args

	for o, a in opts:
		if o == "--help" or o == "-h":
			usage()
			sys.exit()
		elif o == "--stdin":
			USE_STDIN = 1
		elif o == "--use-colors":
			USE_COLOR = 1
		elif o == "--no-colors":
			USE_COLOR = 0
		elif o == "--screenwidth":
			try:
				SCREENWIDTH = int(a)
			except ValueError:
				print "Bad screen width argument : '%s'" % a
				sys.exit(1)
			if SCREENWIDTH <= 5:
				print "Too small screen width : ", a
				sys.exit(1)
		elif o == "--makeprog":
			MAKEPROG = [ a ]
		elif o == "--hide-libtool":
			HIDE_LIBTOOL=1
		elif o == "--show-libtool":
			HIDE_LIBTOOL=0
		elif o == "--hide-wopt":
			HIDE_WOPT=1
		elif o == "--show-wopt":
			HIDE_WOPT=0
		elif o == "--hide-dopt":
			HIDE_DOPT=1
		elif o == "--show-dopt":
			HIDE_DOPT=0
		elif o == "--hide-iopt":
			HIDE_IOPT=1
		elif o == "--show-iopt":
			HIDE_IOPT=0
		elif o == "--hide-lopt":
			HIDE_LOPT=1
		elif o == "--show-lopt":
			HIDE_LOPT=0
		elif o == "--hide-fopt":
			HIDE_FOPT=1
		elif o == "--show-fopt":
			HIDE_FOPT=0
		elif o == "--hide-mopt":
			HIDE_MOPT=1
		elif o == "--show-mopt":
			HIDE_MOPT=0

	MAKEPROG = MAKEPROG + args
		
	if USE_STDIN == 1:
		f = sys.stdin
	else:
		hop, f = os.popen4( join( MAKEPROG ) )
		#hop, f = os.popen4( 'python -c "import sys; sys.stderr.write(\'hoperr\\n\'); sys.stdout.write(\'hopout\\n\');"')

	l = f.readline()
	while len(l) :
		l = l[:-1]
		words = split( strip(l))
		words = map( strip, words)

		if len(words) == 0: 
			l = f.readline()
			continue

		if words[0] == "/bin/sh":
			if HIDE_LIBTOOL == 1:
				print "<libtool line>"
			else:
				processLine( words )
		elif   words[0] in COMPILER_NAME: 
			processLine( words )
		elif words[0].find("bin/moc") != -1:
			outputline( l, "moc" )
		elif words[0].find("bin/uic") != -1:
			outputline( l, "uic" )
		elif words[0].find("/dcopidl") != -1:
			outputline( l, "dcopidl" )
		elif words[0].find("/dcopidl2cpp") != -1:
			outputline( l, "dcopidl2cpp" )
		else:
			print l

		sys.stdout.flush()
		l = f.readline()
	f.close()


def setColumn( s ) :
	global SCREENWIDTH

	for i in s:
		#print "Parsing ", i
		if i.find("COLUMNS") == -1: continue
		i = replace(i, '=',' ')
		i = replace(i, "'",' ')
		i = replace(i, ';',' ')
		l = split( i )
		#print "List:", l
		for w in l:
			try:
				val = int(w)
				if val > 5:
					SCREENWIDTH = val
					return
			except ValueError:
				continue


if __name__ == "__main__":
    main()



