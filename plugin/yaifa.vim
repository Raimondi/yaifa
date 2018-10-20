" Yaifa: Yet another indent finder, almost...
" Version: 2.0
" Author: Israel Chauca F. <israelchauca@gmail.com>

if exists('g:loaded_yaifa') && !get(g:, 'yaifa_debug', 0)
  finish
endif
let g:loaded_yaifa = 1

function! s:log(level, message) "{{{
  if a:level <= get(g:, 'yaifa_debug', 0)
    echomsg printf('yaifa[%s]: %s', a:level, a:message)
  endif
endfunction "}}}

function! s:apply_settings(force, bufnr) "{{{
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
  if !has('job')
    " We can be a bit slow on big files, this should mask it.
    call jobstart(yaifa#magic(a:bufnr))
  else
    call yaifa#magic(a:bufnr)
  endif
endfunction "}}}

augroup Yaifa
  au!
  au FileType * call s:apply_settings(0, bufnr('%'))
augroup End

command! -nargs=0 -bar -bang Yaifa call s:apply_settings(<bang>0, bufnr('%'))
command! -bar TestYaifa call yaifa#test()
if get(g:, 'yaifa_debug', 0)
  command! -count=1 -nargs=* DebugYaifa call s:log(<count>, <args>)
else
  command! -count=1 -nargs=* DebugYaifa :
endif
