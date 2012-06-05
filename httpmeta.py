# -*- coding: utf-8 -*-
#
# httpmeta : Lightweight library for fetching HTTP resource metadata.
# Copyright (C) 2012  Joseph Leeper
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import urllib.parse
import re
from random import choice
import urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler
import chardet2
import html.entities
import time

# List of common browser user agents.
#USER_AGENTS = (
#    'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11',
#    'Opera/9.25 (Windows NT 5.1; U; en)',
#    'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)',
#    'Mozilla/5.0 (compatible; Konqueror/3.5; Linux) KHTML/3.5.5 (like Gecko) (Kubuntu)',
#    'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.0.12) Gecko/20070731 Ubuntu/dapper-security Firefox/1.5.0.12',
#    'Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/1.2.9'
#)
USER_AGENT = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11'

# HTML MIME types.
HTML_TYPES = ('text/html', 'application/xhtml+xml')
# HTTP status codes appropriate for detecting normal redirection.
REDIRECT_CODES = (301, 302, 303)
# Regex range that matches all Unicode characters except the C0 (U+0000-U+001F) and
# C1 (U+007F-U+009F) control characters and the space (U+0020)
#ALL_CONTROLS_AND_SPACE = '[^\u0000-\u0020\u007f-\u009f]'

def ajax_url(url):
    """ AJAX HTML snapshot URL parsing, pretty much required for a modern scraper.
    https://developers.google.com/webmasters/ajax-crawling/docs/specification
    Take a URL string, turn its #! fragment into the prescribed query, and return a string.
    """
    hashbang_index = url.find('#!')
    if hashbang_index != -1:
        base = url[:hashbang_index]
        joiner = '?' if '?' not in base else '&'
        url = ''.join((base, joiner, '_escaped_fragment_=', urllib.parse.quote(url[hashbang_index+2:], '!"$\'()*,/:;<=>?@[\\]^`{|}~')))
    return url

def prettify_url(url):
    """ Removes URL baggage to display a clean hostname/path.
    Passed a string or a urlparse.ParseResult object; return a string.
    The result is not meant to be clickable or navigable.
    """
    if isinstance(url, urllib.parse.ParseResult) == False:
        url = urllib.parse.urlparse(url)
    urlstr = url.hostname + url.path
    return urlstr if urlstr[-1] != '/' else urlstr[0:-1]

class NoTitleError(Exception):
    """ Just a simple, fake, and unique exception to faciliate the main logic. """
    def __init__(self):
        pass

# Thanks to Fredrik Lundh: http://effbot.org/zone/re-sub.htm#unescape-html
def html_unescape(text):
    """ Removes HTML or XML character references and entities from a text string.
    @param text The HTML (or XML) source text.
    @return The plain text, as a Unicode string, if necessary.
    """
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return chr(int(text[3:-1], 16))
                else:
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = chr(html.entities.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;?", fixup, text)

def get(url, full=False):
    request_headers = {'User-Agent': USER_AGENT}
    # GO!
    start_time = time.time()
    resource = requests.head(url, headers=request_headers, allow_redirects=True)
    if resource.status_code == 405:
        resource = requests.get(url, headers=dict(request_headers.items() + [('Range', 'bytes=1-5')]), allow_redirects=True)
    else:
        resource.raise_for_status()

    if resource.history != [] and resource.history[-1].status_code in REDIRECT_CODES:
        url = resource.history[-1].headers['Location']
        redirection_url = urllib.parse.urlparse(url)
        if redirection_url.netloc == '':
            url = ''.join((url_parsed.scheme, '://', url_parsed.netloc, redirection_url.path))
        elif redirection_url.hostname != url_hostname:
            url_hostname = '%s \x03#->\x03 %s' % (url_hostname, prettify_url(url))
        url = ajax_url(url)

    resource_type = resource.headers['Content-Type'].split(';')[0]
    if resource_type in HTML_TYPES:
        resource = requests.get(url, headers=request_headers)
        resource.raise_for_status()
        # RFC 2616 (HTTP/1.1) discourages this, but then again it also doesn't require the charset to be specified.
        # The requests library, in accordance with the RFC, falls back to Latin-1 if charset is not in the Content-Type header.
        # This conditional at least ensures that the charset is checked, even if the result is incorrect.
        # https://github.com/kennethreitz/requests/issues/592
        if resource.encoding == 'ISO-8859-1':
            resource.encoding = chardet.detect(resource.content)['encoding']
        try:
            title = re.findall('(?si)(?<=<title).*?>.*(?=</title>)', resource.text)[0]
            title = re.sub('.*?>', '', title)
        except IndexError:
            raise NoTitleError
        title = re.sub('(?s)\s+', ' ', html_unescape(title).strip())
    else:
        # TODO: Make this feature togglable, since it can seem spammy for image dumps.
        raise NoTitleError

    try:
        data_length = filesize.size(float(resource.headers['Content-Length']), FILESIZES)
    except TypeError:
        data_length = 'size unknown'
    # STOP!
    end_time = time.time()

class HTTPMeta():
    def __init__(self, url):
        self.resource = None


    def title(self, url):

        time_length = '%.2f seconds' % (end_time - start_time)
        return '%s \x03#|\x03 %s \x03#|\x03 \x02%s\x02' % (title, time_length, url_hostname)
