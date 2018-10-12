Yaifa: Yet another indent finder, almost...

This plug-in will try to detect the kind of indentation used in your file and
set the indenting options to the appropriate values. It recognizes three types
of indentation:

1. Space: Only spaces are used to indent.
2. Tab: Only tabs are used.
3. Mixed: A combination of tabs and space is used. e.g.: a tab stands for 8
    spaces, but each indentation level is 4 spaces.

In order to guess the indentation of the buffer, it looks for increments in
the indentation level and into the involved lines to see the type of
indentation and the number of spaces of the change.  The type of indentation
with the most lines is used to set the options.

If Yaifa ever guesses wrong indentation, send me immediately a mail, if
possible with the offending file, or open an issue on GitHub.

This script is based on Philippe Fremy's Python script
[Indent Finder](http://www.freehackers.org/Indent_Finder), hence the "almost"
part of the name.
