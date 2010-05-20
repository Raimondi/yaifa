YAIFA: Yet Another Indent Finder, Almost...


This plug-in will try to detect the kind of indentation in your file and set
Vim's options to keep it that way. It recognizes three types of indentation:

1.- Space: Only spaces are used to indent.

2.- Tab: Only tabs are used.

3.- Mixed: A combination of tabs and space is used. e.g.: a tab stands for 8
    spaces, but each indentation level is 4 spaces.

You can set three options to customize the default values when the file's
indentation can't be determined:

- yaifa_max_lines       The max number of lines that will be scanned to
                        determine the file indentation.


- yaifa_tab_width       Default tab width to be used when the indentation
                        can't be determined.


- yaifa_indentation     Default kind of indentation, accepts the following
                        numeric values:
                        - 0: Space.
                        - 1: Tab.
                        - 2: Mixed.

This script is a port to VimL from Philippe Fremy's Python script Indent
Finder, hence the "Almost" part of the name.
