" YAIFA: Yet Another Indent Finder, Almost...
" Version: 2.0
" Author: Israel Chauca F. <israelchauca@gmail.com>
"
" This plug-in will try to detect the kind of indentation in your file and set
" Vim's options to keep it that way. It recognizes three types of indentation:
"
" 1.- Space: Only spaces are used to indent.
"
" 2.- Tab: Only tabs are used.
"
" 3.- Mixed: A combination of tabs and space is used. e.g.: a tab stands for 8
"     spaces, but each indentation level is 4 spaces.
"
" Use :YAIFAMagic to manually set the indenting settings for the current file.
"
" Depending on the system set-up and the file size scanning too many lines can
" be painfully slow, so YAIFA processes 2048 lines by default, that value can
" be changed with the following line in your .vimrc:
"
"    let yaifa_max_lines = 4096
"
" This script is base on Philippe Fremy's Python script Indent Finder, hence
" the "Almost" part of the name.

if exists('g:loaded_yaifa') && !get(g:, 'yaifa_debug', 0)
  finish
endif
let g:loaded_yaifa = 1

let s:script_dir = expand('<sfile>:p:h:h')

function! s:log(level, message) "{{{
  if a:level <= get(g:, 'yaifa_debug', 0)
    echomsg printf('yaifa[%s]: %s', a:level, a:message)
  endif
endfunction "}}}

function! s:is_continued_line(previous, current, filetype) "{{{
  if a:filetype ==? 'vim'
    return a:current =~# '\m^\s*\\'
  "elseif ...
  " TODO: Consider other syntaxes for line continuation
  " https://en.wikipedia.org/wiki/Comparison_of_programming_languages_(syntax)
  else
    return a:previous =~# '\m\\$'
  endif
endfunction "}}}

function! s:is_comment(line, filetype) "{{{
  if a:filetype ==# 'vim'
    return a:line =~# '\m^\s*"'
  "elseif ...
  " TODO: Consider other syntaxes for comments
  " https://en.wikipedia.org/wiki/Comparison_of_programming_languages_(syntax)
  else
    return a:line =~# '\m^\s*\%(/\*\|\*\|#\|//\)'
  endif
endfunction "}}}

function! s:l2str(line) "{{{
  if a:line.tab
    let type = 'tab'
  elseif a:line.space && a:line.mixed
    let type = 'either'
  elseif a:line.space
    let type = 'space'
  elseif a:line.mixed
    let type = 'mixed'
  elseif a:line.crazy
    let type = 'crazy'
  else
    let type = 'empty'
  endif
  let line = substitute(a:line.line, '\m\t', '|-------', 'g')
  let line = substitute(line, '\m ', nr2char(183), 'g')
  return printf('[%s:%2s]%-5s:%s',
        \ a:line.linenr, a:line.length, type, line)
endfunction "}}}

function! s:analyze_lines(lines, filetype, defaults) "{{{
  let times = []
  call add(times, reltime())
  let defaults = {'type': 'space', 'indent': 4, 'tabstop': 8,
        \ 'max_lines': 0}
  call extend(defaults, a:defaults, 'force')
  let previous = {'line': '', 'linenr': 0, 'indent': 'X', 'delta': '',
          \ 'tab': 0, 'space': 0, 'mixed': 0, 'crazy': 0,
          \ 'tabs': 0, 'spaces': 0, 'length': 0, 'skipped': 0}
  let lines = map(copy(a:lines), 'extend(deepcopy(previous), '
        \ . '{''line'': v:val, ''linenr'': v:key + 1, '
        \ . '''indent'': matchstr(v:val, ''\m^\s*'')}, ''force'')')
  let mixed = {}
  let space = {}
  let tab = 0
  let processed_count = 0
  let ignored_count = 0
  let hint_count = 0
  let max_lines = defaults.max_lines
  call add(times, reltime())
  while !empty(lines) && (max_lines == 0
        \ || (processed_count -ignored_count) < max_lines)
    let processed_count += 1
    let current = remove(lines, 0)
    let skip_msg = ''
    if s:is_continued_line(previous.line, current.line, a:filetype)
      let skip_msg = 'line continuation'
      " Use the properties of the "main" line since that's the one with the
      " correct indentation.
      let current_line = current.line
      let current = copy(previous)
      let current.line = current_line
      let previous = current
    elseif s:is_comment(current.line, a:filetype)
      let skip_msg = 'comment'
    endif
    if !empty(skip_msg)
      " This is meaningless line, just skip it.
      3DebugYaifa s:l2str(current)
      3DebugYaifa printf('Hint: none (%s)', skip_msg)
      let ignored_count += 1
      continue
    endif
    let current.length =
          \ len(substitute(current.indent, '\t', repeat(' ', 8), 'g'))
    " Determine indentation type.
    if current.indent =~# '\m^ \+$'
      let current.space = 1
      let current.spaces = len(matchstr(current.indent, '\m^\zs *'))
      if current.spaces < 8
        " This line could also use mixed indentation.
        let current.mixed = 1
      endif
    elseif current.indent =~# '\m^\t\+ \+$'
      let current.mixed = 1
      let current.spaces = len(matchstr(current.indent, '\m^\t*\zs *'))
      let current.tabs = len(matchstr(current.indent, '\m^\t*'))
    elseif current.indent =~# '\m^\t\+$'
      let current.tab = 1
      let current.tabs = len(matchstr(current.indent, '\m^\t*'))
    elseif current.indent =~# '\m \t'
      let current.crazy = 1
    endif
    3DebugYaifa s:l2str(current)
    let current.delta = current.length - previous.length
    if empty(current.line) || current.line =~# '\m^\s*$'
      " Skip empty or blank lines
      let current.skipped = 1
      3DebugYaifa printf('Hint: none (%3s:empty line)', current.delta)
    elseif previous.indent ==# current.indent
      " Skip lines without indentation change
      3DebugYaifa printf('Hint: none (%3s: same indent)', current.delta)
    elseif current.crazy
      " Skip lines with crazy indentation
      let current.skipped = 1
      3DebugYaifa printf('Hint: none (%3s:crazy indent)', current.delta)
    elseif (current.mixed && current.spaces >= 8)
      " Skip mixed lines with too many spaces, looks like crazy indentation
      let current.skipped = 1
      3DebugYaifa printf('Hint: none (%3s:mixed & wrong number of spaces)',
            \ current.delta)
    elseif previous.skipped
      " Not enough context to analyze this line, just skip it.
      3DebugYaifa printf('Hint: none (%3s:previous was skipped)',
            \ current.delta)
    elseif (current.delta <= 1) || (current.delta > 8)
      " Ignore indent change too small or too big
      3DebugYaifa printf('Hint: none (%3s:wrong change size)', current.delta)
    elseif (previous.length == 0 || previous.tab) && current.tab
      " Indent change hints at tabs
      " Increment tab count
      let tab += 1
      let hint_count += 1
      3DebugYaifa printf('Hint: tab   (%3s)', current.delta)
    elseif (previous.length == 0 || previous.space) && current.space
          \ && !current.mixed
      " Indent change hints at spaces
      " Increment space count
      let space[current.delta] = get(space, current.delta, 0) + 1
      let hint_count += 1
      3DebugYaifa printf('Hint: space (%3s)', current.delta)
    elseif (previous.mixed && previous.space || previous.length == 0)
          \ && current.space && current.mixed
      " Indent change hints at spaces or mixed
      " Increment space and mixed count
      let space[current.delta] = get(space, current.delta, 0) + 1
      let mixed[current.delta] = get(mixed, current.delta, 0) + 1
      let hint_count += 1
      3DebugYaifa printf('Hint: either(%3s)', current.delta)
    elseif previous.tab && current.mixed && (previous.tabs == current.tabs)
      " Indent change hints at mixed
      " Increment mixed count
      let mixed[current.delta] = get(mixed, current.delta, 0) + 1
      let hint_count += 1
      3DebugYaifa printf('Hint: mixed (%3s)', current.delta)
    elseif previous.mixed && current.tab
          \ && (previous.tabs == current.tabs - 1)
      " Indent change hints at mixed
      " Increment mixed count
      let mixed[current.delta] = get(mixed, current.delta, 0) + 1
      let hint_count += 1
      3DebugYaifa printf('Hint: mixed (%3s)', current.delta)
    elseif previous.mixed && current.mixed && (previous.tabs == current.tabs)
      " Indent change hints at mixed
      " Increment mixed count
      let mixed[current.delta] = get(mixed, current.delta, 0) + 1
      let hint_count += 1
      3DebugYaifa printf('Hint: mixed (%3s)', current.delta)
    else
      " Nothing to do here
      3DebugYaifa printf('Hint: none  (%3s)', current.delta)
    endif
    let previous = current
  endwhile
  let time = reltimestr(reltime(remove(times, -1)))
  2DebugYaifa printf('Time taken to analyze all lines: %s', time)
  let max_space = max(space)
  let max_mixed = max(mixed)
  let max_tab   = tab
  let result = {'type': '', 'indent': 0}
  if max_space * 1.1 >= max_mixed && max_space >= max_tab
    " Go with spaces
    let line_count = 0
    let indent = 0
    for i in range(8, 1, -1)
      if get(space, i, 0) > floor(line_count * 1.1)
        " Give preference to higher indentation
        let indent = i
        let line_count = space[i]
      endif
    endfor
    if indent == 0
      " No guess on size, return defaults
      let result.type = defaults.type
      let result.indent = defaults.indent
    else
      let result.type = 'space'
      let result.indent = indent
    endif
  elseif max_mixed > max_tab
    " Go with mixed
    let line_count = 0
    let indent = 0
    for i in range(8, 1, -1)
      if get(mixed, i, 0) > floor(line_count * 1.1)
        " Give preference to higher indentation
        let indent = i
        let line_count = mixed[i]
      endif
    endfor
    if indent == 0
      " No guess on size, return defaults
      let result.type = defaults.type
      let result.indent = defaults.indent
    else
      let result.type = 'mixed'
      let result.indent = indent
    endif
  else
    " Go with tabs
    let result.type = 'tab'
    let result.indent = defaults.tabstop
  endif
  if get(g:, 'yaifa_debug', 0) > 1
    " Print some info for debugging
    2DebugYaifa printf('Processed lines count: %s', processed_count)
    2DebugYaifa printf('Hints count: %s', hint_count)
    if tab > 0
      2DebugYaifa printf('    tab  (8) => %s', tab)
    endif
    for key in keys(space)
      if space[key] > 0
        2DebugYaifa printf('    space(%s) => %s', key, space[key])
      endif
    endfor
    for key in keys(mixed)
      if mixed[key] > 0
        2DebugYaifa printf('    mixed(%s) => %s', key, mixed[key])
      endif
    endfor
    2DebugYaifa  'max_space: ' . max_space
    2DebugYaifa  'max_mixed: ' . max_mixed
    2DebugYaifa  'max_tab: ' . max_tab
  endif
  let time = reltimestr(reltime(remove(times, -1)))
  1DebugYaifa printf('Time taken to guess: %s', time)
  1DebugYaifa 'Result: ' . string(result)
  return result
endfunction "}}}

function! s:l2str2(line) "{{{
  if a:line.type ==# "\t"
    let type = 'tab'
  elseif a:line.type ==# ' ' && a:line.length < 8
    let type = 'either'
  elseif a:line.type ==# ' '
    let type = 'space'
  elseif a:line.type ==# "\t "
    let type = 'mixed'
  elseif a:line.crazy
    let type = 'crazy'
  else
    let type = 'empty'
  endif
  let line = substitute(a:line.line, '\m\t', '|-------', 'g')
  let line = substitute(line, '\m ', nr2char(183), 'g')
  return printf('[%s:%2s]%-5s:%s',
        \ a:line.linenr, a:line.length, type, line)
endfunction "}}}

function! s:analyze_line(previous, line, filetype) "{{{
  if s:is_continued_line(a:previous.line, a:line, a:filetype)
    " Use the properties of the "main" line since that's the one with the
    " correct indentation.
    let current = copy(a:previous)
    let current.line = a:line
    return current
  endif
  let current = deepcopy(a:previous)
  let current.line = a:line
  let current.indent = matchstr(a:line, '^\s\+')
  let current.length = len(substitute(current.indent, '\t', '        ', 'g'))
  let current.tabs = len(matchstr(current.indent, '\m^\t*'))
  let current.spaces = current.length - (current.tabs * 8)
  let current.delta = current.length - a:previous.length
  let current.type = matchstr(current.indent,
        \ '\m^\%(\t\{-}\zs\t \?\ze \{-,6}\| \ze *\)$')
  let current.either = current.indent =~# '\m^ \ze \{,6}$'
  let current.crazy = current.indent =~# ' \t'
  let current.good_delta = current.delta > 1 && current.delta <= 8
        \ && !current.crazy
  let current.key = printf('%s:%s:%s:%s:%s:%s:%s:%s:%s',
        \ a:previous.crazy,
        \ current.crazy,
        \ current.good_delta,
        \ current.spaces >= 8,
        \ a:previous.length == 0,
        \ current.length == 0,
        \ current.delta == 8,
        \ a:previous.type,
        \ current.type
        \)
  return current
endfunction "}}}

function! s:analyze_lines(lines, filetype, defaults) "{{{
  let result = {}
  let result.space = {}
  let result.mixed = {}
  let result.tab = {}
  let result.hints = 0
  let result.no_hints = 0
  function result.tabf(current)
    let self.tab['8'] = get(self.tab, 8, 0) + 1
    let self.hints += 1
    3DebugYaifa printf('tabf    : %-19s:%s',
          \ substitute(a:current.key, '\s',
          \     '\=submatch(0) == " " ? "." : "-"', 'g'),
          \ s:l2str2(a:current))
    return a:current
  endfunction
  function result.spacef(current)
    let self.space[a:current.delta] = get(self.space, a:current.delta, 0) + 1
    let self.hints += 1
    3DebugYaifa printf('spacef  : %-19s:%s',
          \ substitute(a:current.key, '\s',
          \     '\=submatch(0) == " " ? "." : "-"', 'g'),
          \ s:l2str2(a:current))
    return a:current
  endfunction
  function result.mixedf(current)
    let self.mixed[a:current.delta] = get(self.mixed, a:current.delta, 0) + 1
    let self.hints += 1
    3DebugYaifa printf('mixedf  : %-19s:%s',
          \ substitute(a:current.key, '\s',
          \     '\=submatch(0) == " " ? "." : "-"', 'g'),
          \ s:l2str2(a:current))
    return a:current
  endfunction
  function result.eitherf(current)
    let self.space[a:current.delta] = get(self.space, a:current.delta, 0) + 1
    let self.mixed[a:current.delta] = get(self.mixed, a:current.delta, 0) + 1
    let self.hints += 1
    3DebugYaifa printf('eitherf : %-19s:%s',
          \ substitute(a:current.key, '\s',
          \     '\=submatch(0) == " " ? "." : "-"', 'g'),
          \ s:l2str2(a:current))
    return a:current
  endfunction
  function result.defaultf(current)
    let self.no_hints += 1
    3DebugYaifa printf('defaultf: %-19s:%s',
          \ substitute(a:current.key, '\s',
          \     '\=submatch(0) == " " ? "." : "-"', 'g'),
          \ s:l2str2(a:current))
    return a:current
  endfunction

  " case   | pc | c | d | s>=8 | pe | e | d=8 | pt    | t
  "--------+----+---+---+------+-----+--+-----+-------+-------
  " tab    | 0  | 0 | 1 | 0    | 0  | 0 | 1   | "\t"  | "\t"
  " tab    | 0  | 0 | 1 | 0    | 1  | 0 | 1   | "\t"  | "\t"
  " tab    | 0  | 0 | 1 | 0    | 0  | 0 | 1   | ""    | "\t"
  " tab    | 0  | 0 | 1 | 0    | 1  | 0 | 1   | ""    | "\t"
  " space  | 0  | 0 | 1 | 1    | 0  | 0 | 0   | ""    | " "
  " space  | 0  | 0 | 1 | 1    | 1  | 0 | 0   | ""    | " "
  " space  | 0  | 0 | 1 | 1    | 0  | 0 | 1   | ""    | " "
  " space  | 0  | 0 | 1 | 1    | 1  | 0 | 1   | ""    | " "
  " space  | 0  | 0 | 1 | 1    | 0  | 0 | 0   | " "   | " "
  " space  | 0  | 0 | 1 | 1    | 1  | 0 | 0   | " "   | " "
  " space  | 0  | 0 | 1 | 1    | 0  | 0 | 1   | " "   | " "
  " space  | 0  | 0 | 1 | 1    | 1  | 0 | 1   | " "   | " "
  " either | 0  | 0 | 1 | 0    | 0  | 0 | 0   | ""    | " "
  " either | 0  | 0 | 1 | 0    | 1  | 0 | 0   | ""    | " "
  " either | 0  | 0 | 1 | 0    | 0  | 0 | 0   | " "   | " "
  " either | 0  | 0 | 1 | 0    | 1  | 0 | 0   | " "   | " "
  " mixed  | 0  | 0 | 1 | 0    | 0  | 0 | 0   | "\t " | "\t"
  " mixed  | 0  | 0 | 1 | 0    | 0  | 0 | 0   | "\t " | "\t "
  " mixed  | 0  | 0 | 1 | 0    | 0  | 0 | 0   | "\t"  | "\t "
  " mixed  | 0  | 0 | 1 | 0    | 0  | 0 | 0   | " "  | "\t"
  let result["0:0:1:0:0:0:1:\t:\t" ] = result.tabf
  let result["0:0:1:0:1:0:1:\t:\t" ] = result.tabf
  let result["0:0:1:0:0:0:1::\t" ] = result.tabf
  let result["0:0:1:0:1:0:1::\t" ] = result.tabf
  let result['0:0:1:1:0:0:0:: ' ] = result.spacef
  let result['0:0:1:1:1:0:0:: ' ] = result.spacef
  let result['0:0:1:1:0:0:1:: ' ] = result.spacef
  let result['0:0:1:1:1:0:1:: ' ] = result.spacef
  let result['0:0:1:1:0:0:0: : ' ] = result.spacef
  let result['0:0:1:1:1:0:0: : ' ] = result.spacef
  let result['0:0:1:1:0:0:1: : ' ] = result.spacef
  let result['0:0:1:1:1:0:1: : ' ] = result.spacef
  let result['0:0:1:0:0:0:0:: ' ] = result.eitherf
  let result['0:0:1:0:1:0:0:: ' ] = result.eitherf
  let result['0:0:1:0:0:0:0: : ' ] = result.eitherf
  let result['0:0:1:0:1:0:0: : ' ] = result.eitherf
  let result["0:0:1:0:0:0:0:\t :\t" ] = result.mixedf
  let result["0:0:1:0:0:0:0:\t :\t "] = result.mixedf
  let result["0:0:1:0:0:0:0:\t:\t " ] = result.mixedf
  let result["0:0:1:0:0:0:0: :\t" ] = result.mixedf

  let times = []
  call add(times, reltime())
  let defaults = {'type': 'space', 'indent': 4, 'tabstop': 8,
        \ 'max_lines': 0}
  call extend(defaults, a:defaults, 'force')
  let previous = {'line': '', 'linenr': 0, 'indent': 'X', 'delta': 0,
          \ 'tab': 0, 'space': 0, 'mixed': 0, 'crazy': 0, 'good': 0,
          \ 'tabs': 0, 'spaces': 0, 'length': 0, 'skipped': 0, 'type': ''}
  let lines = filter(copy(a:lines), {key, val ->
        \ !empty(val) && val !~# '\m^\s*$' && !s:is_comment(val, a:filetype)})
  let lines = defaults.max_lines == 0 || len(lines) > defaults.max_lines
        \ ? lines : lines[0 : defaults.max_lines]
  let lines = lines + ['']
  call add(times, reltime())
  call map(lines,
        \{key, val -> s:analyze_line(
        \                 get(lines,
        \                   key > 0 ? key - 1 : len(lines),
        \                   previous),
        \                 val, a:filetype)})
  call map(lines, {key, val ->
        \ call(get(result, val.key, result.defaultf), [val], result)})

  "for val in lines
  "  call call(get(result, val.key, result.defaultf), [val], result)
  "endfor
  let time = reltimestr(reltime(remove(times, -1)))
  2DebugYaifa printf('Time taken to analyze all lines: %s', time)
  let max_space = max(result.space)
  let max_mixed = max(result.mixed)
  let max_tab   = max(result.tab)
  let result.type = ''
  let result.indent = 0
  if max_space * 1.1 >= max_mixed && max_space >= max_tab
    " Go with spaces
    let line_count = 0
    let indent = 0
    for i in range(8, 1, -1)
      if get(result.space, i, 0) > floor(line_count * 1.1)
        " Give preference to higher indentation
        let indent = i
        let line_count = result.space[i]
      endif
    endfor
    if indent == 0
      " No guess on size, return defaults
      let result.type = defaults.type
      let result.indent = defaults.indent
    else
      let result.type = 'space'
      let result.indent = indent
    endif
  elseif max_mixed > max_tab
    " Go with mixed
    let line_count = 0
    let indent = 0
    for i in range(8, 1, -1)
      if get(result.mixed, i, 0) > floor(line_count * 1.1)
        " Give preference to higher indentation
        let indent = i
        let line_count = result.mixed[i]
      endif
    endfor
    if indent == 0
      " No guess on size, return defaults
      let result.type = defaults.type
      let result.indent = defaults.indent
    else
      let result.type = 'mixed'
      let result.indent = indent
    endif
  else
    " Go with tabs
    let result.type = 'tab'
    let result.indent = defaults.tabstop
  endif
  if get(g:, 'yaifa_debug', 0) > 1
    " Print some info for debugging
    2DebugYaifa printf('Processed lines count: %s',
          \ result.hints + result.no_hints)
    2DebugYaifa printf('Hints count: %s', result.hints)
    for type in ['tab', 'space', 'mixed']
      for key in keys(result[type])
        if result[type][key] > 0
          2DebugYaifa printf('    %s(%s) => %s', type, key, result[type][key])
        endif
      endfor
    endfor
    2DebugYaifa  'max_space: ' . max_space
    2DebugYaifa  'max_mixed: ' . max_mixed
    2DebugYaifa  'max_tab: ' . max_tab
  endif
  let time = reltimestr(reltime(remove(times, -1)))
  1DebugYaifa printf('Time taken to guess: %s', time)
  1DebugYaifa 'Result: ' . string(filter(result, 'type(v:val) != 2'))
  return result
endfunction "}}}

function! s:apply_settings(force) "{{{
  " Is it a special buffer?
  let is_special = !empty(&buftype)
  " Do not try to guess in non-code buffers
  let is_code = index(['help', 'text', 'mail'], &filetype) < 0
  " Does the user wants it ignored?
  let skip_it = get(b:, 'yaifa_disabled', get(g:, 'yaifa_disabled', 0))
  if !a:force && (is_special || !is_code || skip_it)
    " Seems like we are skipping this buffer
    return
  endif
  let lines = getline(1, '$')
  let default_shiftwidth =
        \ get(b:, 'yaifa_shiftwidth', get(g:, 'yaifa_shiftwidth', 4))
  let default_tabstop = get(b:, 'yaifa_tabstop', get(g:, 'yaifa_tabstop', 8))
  let default_expandtab =
        \ get(b:, 'yaifa_expandtab', get(g:, 'yaifa_expandtab', 1))
  if default_expandtab
    let default_type = 'space'
  elseif !default_shiftwidth || default_shiftwidth == default_tabstop
    let default_type = 'tab'
  else
    let default_type = 'mixed'
  endif
  let defaults = {}
  let defaults.max_lines = 1024
  let defaults.type = default_type
  let defaults.indent = default_shiftwidth
  let defaults.tabstop = default_tabstop
  " Do the guess work
  let result = s:analyze_lines(lines, &filetype, defaults)
  if result.type ==# 'tab'
    " Use tabs
    let expandtab = 'noexpandtab'
    let shiftwidth = 0
    let softtabstop = 0
    let tabstop = default_tabstop
  elseif result.type ==# 'mixed'
    " Use tabs and spaces
    let expandtab = 'noexpandtab'
    let shiftwidth = result.indent
    let softtabstop = result.indent
    let tabstop = 8
  else
    " Use spaces only
    let expandtab = 'expandtab'
    let shiftwidth = result.indent
    let softtabstop = result.indent
    let tabstop = 8
  endif
  let template = 'setlocal %s tabstop=%s shiftwidth=%s softtabstop=%s'
  let set_cmd = printf(template, expandtab, tabstop, shiftwidth, softtabstop)
  execute set_cmd
  1DebugYaifa set_cmd
  return set_cmd
endfunction "}}}

function! s:test() "{{{
  let start_time = reltime()
  let results = {}
  let results.files = []
  let testdirspat = s:script_dir . '/test/*'
  let testdirs = glob(testdirspat, 0, 1)
  call map(testdirs, 'fnamemodify(v:val, '':p:h'')')
  call filter(testdirs, 'isdirectory(v:val)')
  for dir in testdirs
    let files = glob(dir . '/*', 0, 1)
    echom printf('dir name: %s', fnamemodify(dir, ':t'))
    " Directories with test files should be named <type>-<value>
    let [type, value] = split(fnamemodify(dir, ':t'), '-')
    for file in files
      let lines = readfile(file)
      let test_time = reltime()
      " Do some guessing
      let result = s:analyze_lines(lines, '', {'max_lines': 1024 * 2})
      let test_time = reltimefloat(reltime(test_time)) * 100
      let test_time = floor(test_time) / 100.0
      let test_path = printf('%s/%s', fnamemodify(dir, ':p:h:t'),
            \ fnamemodify(file, ':p:t'))
      let result.path = file
      let result.error = 0
      let result.exp_type = type
      let result.exp_value = value
      if result.type ==? type
        if result.indent != value
          let result.error = 2
          echohl WarningMsg
          echom printf('%ss:%s failed: wrong value, expected %s but got %s',
                \ test_time, test_path, result.exp_value, result.indent)
          echohl Normal
        else
          echom printf('%ss:%s passed: type %s and value %s',
                \ test_time, test_path, result.type, result.indent)
        endif
      else
        echohl WarningMsg
          echom printf('%ss:%s failed: wrong type, expected %s but got %s',
              \ test_time, test_path, result.exp_type, result.type)
        echohl Normal
        let result.error = 1
      endif
      call add(results.files, result)
    endfor
  endfor
  echom ' '
  echom printf('Elapsed time: %s seconds',
        \ floor(reltimefloat(reltime(start_time))))
  for file in results.files
    let file.path = fnamemodify(file.path, ':~:.')
  endfor
  let results.passed_files = filter(copy(results.files), '!v:val.error')
  let results.failed_files = filter(copy(results.files), 'v:val.error')
  let results.failed_types = filter(copy(results.files), 'v:val.error == 1')
  let results.failed_values = filter(copy(results.files), 'v:val.error == 2')
  if empty(results.failed_files)
    echom 'All tests passed'
  else
    echohl WarningMsg
    echom 'Failed tests:'
    echohl Normal
  endif
  for file in results.failed_files
    echom printf('%s: exp: %s-%s, act: %s-%s', file.path, file.exp_type,
          \ file.exp_value, file.type, file.indent)
  endfor
  let g:yaifa_test_result = results
  return results
endfunction "}}}

augroup YAIFA
  au!
  au FileType * call s:apply_settings(0)
augroup End

command! -nargs=0 -bar -bang Yaifa call s:apply_settings(<bang>0)
command! -bar TestYaifa call s:test()
if get(g:, 'yaifa_debug', 0)
  command! -count=1 -nargs=* DebugYaifa call s:log(<count>, <args>)
else
  command! -count=1 -nargs=* DebugYaifa :
endif
