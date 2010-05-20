#
# -----------------------------------------------------------------------
# cml.py - Plugin for Canadian movie listings
# -----------------------------------------------------------------------
#
#  Copyright (C) 2005 James Oakley
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2.1 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# -----------------------------------------------------------------------
#
# Usage:
#        Add "plugin.activate('video.cml')" in local_conf.py
#        to activate
#

import os
import config
import plugin
import menu
import stat
import string
import time
import re
import urllib2
import util.fileops

from item import Item
from video.videoitem import VideoItem
from gui.ProgressBox import ProgressBox
from gui.AlertBox import AlertBox

cities = {'Amherst': 'sco',
          'Baie-Comeau': 'que',
          'Banff': 'alb',
          'Belleville': 'ont',
          'Brandon': 'man',
          'Brantford': 'ont',
          'Brooks': 'alb',
          'Calgary': 'alb',
          'Campbell River': 'bri',
          'Charlottetown': 'pei',
          'Chicoutimi': 'que',
          'Corner Brook': 'fou',
          'Cranbrook': 'bri',
          'Dawson Creek': 'bri',
          'Drummondville': 'que',
          'Edmonton': 'alb',
          'Edson/Hinton': 'alb',
          'Fredericton': 'bru',
          'Grande Prairie': 'alb',
          'Halifax': 'sco',
          'Hamilton': 'ont',
          'Joliette': 'que',
          'Kamloops': 'bri',
          'Kelowna': 'bri',
          'Kentville': 'sco',
          'Kingston': 'ont',
          'Kitchener': 'ont',
          'Lethbridge': 'alb',
          'London': 'ont',
          'Medicine Hat': 'alb',
          'Miramichi': 'bru',
          'Moncton': 'bru',
          'Montreal': 'que',
          'Nanaimo': 'bri',
          'New Glasgow': 'sco',
          'North Bay': 'ont',
          'Oshawa': 'ont',
          'Ottawa': 'ont',
          'Peterborough': 'ont',
          'Prince George': 'bri',
          'Prince Rupert': 'bri',
          'Quebec': 'que',
          'Red Deer': 'alb',
          'Regina': 'sas',
          'Saint John': 'bru',
          'Sarnia': 'ont',
          'Saskatoon': 'sas',
          'Sault Ste. Marie': 'ont',
          'Sept-Iles': 'que',
          'Sherbrooke': 'que',
          'St-Georges': 'que',
          'St. Catharines': 'ont',
          "St. John's": 'fou',
          'Sudbury': 'ont',
          'Sydney': 'sco',
          'Thunder Bay': 'ont',
          'Toronto': 'ont',
          'Trois-Rivieres': 'que',
          'Truro': 'sco',
          'Vancouver': 'bri',
          'Victoria': 'bri',
          'Weyburn': 'sas',
          'Whitehorse': 'yuk',
          'Windsor': 'ont',
          'Winnipeg': 'man',
          'Yarmouth': 'sco',
          'Yorkton': 'sas'}

CC_URL = 'http://www.cinemaclock.com/'
CC_PROV = cities[config.CML_CITY]
CC_CITY = string.translate(config.CML_CITY, string.maketrans(" .'", "___"))
CC_MAIN_URL = CC_URL+'clock/%s/%s.html' % (CC_PROV, CC_CITY)
CC_THEATRE_URL = CC_URL+'aw/ctha.aw?p=clock&r=%s&m=%s&j=e' % (CC_PROV, CC_CITY)
CC_MOVIE_URL = CC_URL+'aw/cmva.aw?p=clock&r=%s&m=%s&j=e' % (CC_PROV, CC_CITY)

MAX_CACHE_AGE = (60 * 60) * 8 # 8 hours
MAX_POSTER_AGE = (60 * 60) * 24 * 7 # 1 week

# Regexes
sttheatrename_re = re.compile(r"<span class=verdanab2><font color=#0055aa>(.*)</font></span></a>")
showtime_re = re.compile(r"<span class=arial2> &nbsp;(.*)<br>&nbsp;<br></span>")
stmovieurl_re = re.compile(r"""<td align="center" background="/html/tabtlo0.gif" class="verdanab2">&nbsp;&nbsp;&nbsp;<a href="(.*)">The Movie</a>""")
movie_res = {'name': re.compile(r"""<span class=movietitle>"(.*)"</span>""", re.MULTILINE),
             'genre': re.compile(r"""<td align="right"><span class=arialb2>Genre:&nbsp;</span></td>\n\s*<td><span class=arial2>(.*)</span></td>""", re.MULTILINE),
             'rating': re.compile(r"""<td align="right"><span class=arialb2>Rating:&nbsp;</span></td>\n\s*<td><span class=arial2>(.*)</span></td>""", re.MULTILINE),
             'length': re.compile(r"""<td align="right"><span class=arialb2>Length:&nbsp;</span></td>\n\s*<td><span class=arial2>(.*)</span></td>""", re.MULTILINE),
             'director': re.compile(r"""<td align="right"><span class=arialb2>Directed&nbsp;by:&nbsp;</span></td>\n\s*<td><span class=arial2>(.*)</span></td>""", re.MULTILINE),
             'writer': re.compile(r"""<td align="right"><span class=arialb2>Written&nbsp;by:&nbsp;</span></td>\n\s*<td><span class=arial2>(.*)</span></td>""", re.MULTILINE),
             'company': re.compile(r"""<td align="right"><span class=arialb2>Company:&nbsp;</span></td>\n\s*<td><span class=arial2>(.*)</span></td>""", re.MULTILINE),
             'starring': re.compile(r"""<td align="right"><span class=arialb2>Starring:&nbsp;</span></td>\n\s*<td><span class=arial2>(.*)</span></td>""", re.MULTILINE),
             'poster': re.compile(r"""</center></td><td valign=top width=140>\n<img src="(.*)" border=2><br><br>""", re.MULTILINE)}
tmovieurl_re = re.compile(r"""<a href="(.*)"><span class=verdanab2>.*</span></a>""")
htmlstrip_re = re.compile(r"<.*?>", re.IGNORECASE | re.DOTALL)
asx_re = re.compile(r"""<ref\s*href\s*=\s*"(.*)"\s*""", re.IGNORECASE | re.MULTILINE)

class PluginInterface(plugin.MainMenuPlugin):
    """
    A freevo interface to cinemaclock.com's Canadian movie listings

    plugin.activate('video.cml')
    """
    def __init__(self):
        plugin.MainMenuPlugin.__init__(self)
        _debug_('Initialising Canadian Movie Listings Plugin', 1)

    def items(self, parent):
        return [cml(parent)]


class Trailer(VideoItem):
    def __init__(self, trailer, parent):
        VideoItem.__init__(self, trailer['url'], parent)
        self.name = "%(type)s - %(speed)s" % trailer
        self.trailer = trailer
        self.type = 'video'

    def play(self, arg=None, menuw=None, alternateplayer=False):
        """
        Check url before playing
        """
        # Check to see if there's some intermediate file...
        try:
            trailerdata = urllib2.urlopen(self.trailer['url']).read(1024)
        except HTTPError, e:
            AlertBox("%s %s: %s" % (_("Could not retrieve URL"), self.trailer['url'], e)).show()
            return

        if trailerdata.find('<?quicktime type="application/x-quicktime-media-link"?>') > -1:
            self.set_url(trailerdata.split('src="')[1].split('"')[0])
        elif trailerdata.lower().find('<asx') == 0:
            res = asx_re.search(trailerdata)
            if res:
                self.set_url(res.group(1))
        elif trailerdata.lower().find('rtsp:') == 0:
            self.set_url(trailerdata)
        
        VideoItem.play(self, arg, menuw, alternateplayer)

class TrailerMenu(Item):
    def __init__(self, movie, parent):
        Item.__init__(self, parent)
        self.movie = movie
        self.name = _('Watch Trailer')

    def actions(self):
        return [ (self.make_menu, 'Trailers') ]

    def make_menu(self, arg=None, menuw=None):
        items = []
        for trailer in self.movie['trailers']:
            items.append(Trailer(trailer, self))
        menuw.pushmenu(menu.Menu(_('Watch Trailers'), items))


class Showtime(Item):
    def __init__(self, theatre, showtime, parent):
        Item.__init__(self, parent)
        self.name = theatre
        self.description = showtime
        self.type = 'showtime'


class ShowtimeMenu(Item):
    def __init__(self, movie, parent):
        Item.__init__(self, parent)
        self.movie = movie
        self.name = _('Showtimes')

    def actions(self):
        return [ (self.make_menu, 'Showtimes') ]

    def make_menu(self, arg=None, menuw=None):
        items = []
        for theatre in self.movie['showtimes'].keys():
            items.append(Showtime(theatre, self.movie['showtimes'][theatre], self))
        menuw.pushmenu(menu.Menu(_('Showtimes'), items))


class Movie(Item):
    def __init__(self, movie, parent):
        Item.__init__(self, parent)
        self.movie = movie
        self.name = movie['name']
        if movie.has_key('poster_path'):
            self.image = movie['poster_path']
        if parent.type == 'theatre':
            self.description = movie['showtimes'][parent.name]+'\n'
        if movie.has_key('description'):
            self.description += movie['description']

    def actions(self):
        return [ (self.make_menu, 'Movies') ]

    def make_menu(self, arg=None, menuw=None):
        items = []
        menuw.pushmenu(menu.Menu(_('Movie Menu'),
                                 [ShowtimeMenu(self.movie, self),
                                  TrailerMenu(self.movie, self)]))


class Theatre(Item):
    def __init__(self, theatre, parent):
        Item.__init__(self, parent)
        self.theatre = theatre
        self.name = theatre['name']
        self.type = 'theatre'

    def actions(self):
        return [ (self.make_menu, 'Movies') ]

    def make_menu(self, arg=None, menuw=None):
        items = []
        for movie in self.theatre['movies']:
            items.append(Movie(movie, self))
        menuw.pushmenu(menu.Menu(_('Movies'), items))


class By(Item):
    def __init__(self, name, parent):
        Item.__init__(self, parent)
        self.name = _("By "+name)
        self.type = name
        self.cachedir = '%s/cml' % config.FREEVO_CACHEDIR
        if not os.path.isdir(self.cachedir):
            os.mkdir(self.cachedir,
                     stat.S_IMODE(os.stat(config.FREEVO_CACHEDIR)[stat.ST_MODE]))
        self.posterdir = os.path.join(self.cachedir, 'posters')
        if not os.path.isdir(self.posterdir):
            os.mkdir(self.posterdir)
        
    def actions(self):
        return [(self.make_menu, self.name)]
        
    def make_menu(self, arg=None, menuw=None):
        pfile = os.path.join(self.cachedir, 'main_info')
        if (os.path.isfile(pfile) == 0 or \
            (abs(time.time() - os.path.getmtime(pfile)) > MAX_CACHE_AGE)):
            _debug_('Fetching movies and theatres', 2)
            main_info = self.getMainInfo()
            util.fileops.save_pickle(main_info, pfile)
        else:
            _debug_('Using cached movies and theatres', 2)
            main_info = util.fileops.read_pickle(pfile)

        if self.type == 'Movie':
            items = [Movie(movie, self) for movie in main_info['Movies']]
        else:
            items = [Theatre(theatre, self) for theatre in main_info['Theatres']]
        menuw.pushmenu(menu.Menu(_(self.name), items))

    def getMainInfo(self):
        """
        Get main info for city
        
        Returns a dict of the form::
        
          { 'Movies': [{'sysname': string,
                        'name': string,
                        'showtimes': string,
                        'url': string,
                        'genre': string,
                        'rating': string,
                        'length': string,
                        'director': string,
                        'writer': string,
                        'company': string,
                        'starring': string,
                        'poster_path': string}],
            'Theatres': [{'sysname': string,
                          'name': string,
                          'movies': list of movies as above}]}
        """
        d = {'Movies': [], 'Theatres': []}
        page = urllib2.urlopen(CC_MAIN_URL).read()
        rawmovies = page.split('<select name=f>')[1].split('</select>')[0]
        rms = rawmovies.split('<OPTION value="')[1:]
        pbox = ProgressBox(_("Retrieving Movie Information"), full=len(rms))
        pbox.show()
        for rm in rms:
            names = rm.split('">')
            movie = {'sysname': names[0].strip()}
            _debug_("getting showtime info for "+movie['sysname'], 2)
            showtimepage = urllib2.urlopen(CC_MOVIE_URL+'&f='+movie['sysname']).read()
            movie['showtimes'] = {}
            for rawst in showtimepage.split('<table cellspacing=0 cellpadding=0 border=0><tr><td><a')[1:]:
                theatrename = sttheatrename_re.search(rawst).group(1)
                movie['showtimes'][theatrename] = showtime_re.search(rawst).group(1).replace(' <br> &nbsp;', '\n')
            movie['url'] = CC_URL+stmovieurl_re.search(showtimepage).group(1)
            moviepage = urllib2.urlopen(movie['url']).read()
            movie['name'] = movie_res['name'].search(moviepage).group(1)
            
            for key in ('genre', 'rating', 'length', 'director', 'writer', 'company', 'starring'):
                res = movie_res[key].search(moviepage)
                if res:
                    movie['key'] = res.group(1)

            if movie.has_key('starring'):
                movie['starring'] = htmlstrip_re.sub('', movie['starring'])

            res = movie_res['poster'].search(moviepage)
            if res:
                poster_url = CC_URL+res.group(1)

                imgfile = os.path.join(self.posterdir,
                                       str(movie['sysname']) + '.' + poster_url.split('.')[-1])
                if (os.path.isfile(imgfile) == 0 or \
                    (abs(time.time() - os.path.getmtime(imgfile)) > MAX_POSTER_AGE)):
                    open(imgfile, 'w').write(urllib2.urlopen(poster_url).read())
                movie['poster_path'] = imgfile
            
            movie['trailers'] = []
            for trailertype in (('QuickTime', '<span class=arial2>Quick&nbsp;Time:&nbsp;</span>'), \
                                ('RealVideo', '<span class=arial2>Real&nbsp;Video:&nbsp;</span>'), \
                                ('Windows Media', '<span class=arial2>Windows&nbsp;Media:&nbsp;</span>')):
                if moviepage.find(trailertype[1]) == -1:
                    continue
                rawtrailers = moviepage.split(trailertype[1])[1].split('<br>')[0]
                for s in rawtrailers.split("window.open('/aw/trailer.aw?p=clock&j=e&t=")[1:]:
                    trailer = {}
                    trailer['type'] = trailertype[0]
                    trailer['url'] = s.split('&mv=')[0]
                        
                    trailer['speed'] = s.split('return false;">')[1].split('</a></span>')[0]
                    movie['trailers'].append(trailer)
            
            if moviepage.find('<p STYLE="text-align: justify"><span class=arial2>') > -1:
                movie['description'] = moviepage.split('<p STYLE="text-align: justify"><span class=arial2>')[1].split('</span></p></td>')[0]            

            d['Movies'].append(movie)
            pbox.tick()

        rawtheatres = page.split('<select name=k>')[1].split('</select>')[0].replace('</option>', '')
        for rt in rawtheatres.split('<OPTION value="')[1:]:
            names = rt.split('">')
            theatre = {'sysname': names[0].strip(),
	:                       'name': names[1].strip(),
                       'movies': []}
            theatrepage = urllib2.urlopen(CC_THEATRE_URL+'&k='+theatre['sysname']).read()
            for rawmovie in theatrepage.split('<span class=arial1><br></span>')[1:]:
                murl = CC_URL+tmovieurl_re.search(rawmovie).group(1)
                for m in d['Movies']:
                    if m['url'] == murl:
                        theatre['movies'].append(m)
            
            d['Theatres'].append(theatre)
        
        pbox.destroy()               
        return d


class cml(Item):
    def __init__(self, parent):
        Item.__init__(self, parent)
        self.name = 'Movie Listings'
        self.type = 'video' # ?
        
    def actions(self):
        return [(self.make_menu, "Movie Listings")]

    def make_menu(self, arg=None, menuw=None):
        menuw.pushmenu(menu.Menu('Movie Listings',
                                 [By('Movie', self),
                                  By('Theatre', self)]))
