# **************************************************************************************
# * This file is part of SpeakReader.
# *
# *  SpeakReader is free software: you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License V3 as published by
# *  the Free Software Foundation.
# *
# *  SpeakReader is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with SpeakReader.  If not, see <http://www.gnu.org/licenses/gpl-3.0.html>.
# **************************************************************************************

#  This module is the configuration and startup module for the web server.

import os
import sys
import cherrypy
import portend

import speakreader
from speakreader import logger


def initialize(options):
    from speakreader import webauth
    from speakreader.webserve import WebInterface

    CONFIG = options['config']

    options_dict = {
        'server.socket_port': options['http_port'],
        'server.socket_host': CONFIG.HTTP_HOST,
        'environment': 'production',
        'server.thread_pool': 50,
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True
    }

    if CONFIG.ENABLE_HTTPS:
        options_dict['server.ssl_certificate'] = CONFIG.HTTPS_CERT
        options_dict['server.ssl_certificate_chain'] = CONFIG.HTTPS_CERT_CHAIN
        options_dict['server.ssl_private_key'] = CONFIG.HTTPS_KEY
        protocol = "https"
    else:
        protocol = "http"

    if CONFIG.HTTP_PROXY:
        # Overwrite cherrypy.tools.proxy with our own proxy handler
        cherrypy.tools.proxy = cherrypy.Tool('before_handler', proxy, priority=1)

    if CONFIG.HTTP_PASSWORD:
        login_allowed = ["SpeakReader admin (username is '%s')" % CONFIG.HTTP_USERNAME]

        logger.info("WebStart :: Web server authentication is enabled: %s.", ' and '.join(login_allowed))

        if CONFIG.HTTP_BASIC_AUTH:
            auth_enabled = False
            basic_auth_enabled = True
        else:
            auth_enabled = True
            basic_auth_enabled = False
            cherrypy.tools.auth = cherrypy.Tool('before_handler', webauth.check_auth, priority=2)
    else:
        auth_enabled = basic_auth_enabled = False

    cherrypy.config.update(options_dict)

    conf = {
        '/': {
            'tools.staticdir.root': os.path.join(options['prog_dir'], 'html'),
            'tools.proxy.on': bool(CONFIG.HTTP_PROXY),
            'tools.gzip.on': True,
            'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/css',
                                      'text/javascript', 'application/json',
                                      'application/javascript'],
            'tools.auth.on': False,
            'tools.auth_basic.on': False,
            'tools.sessions.on': True,
        },
        '/manage': {
            'tools.staticdir.root': os.path.join(options['prog_dir'], 'html'),
            'tools.proxy.on': bool(CONFIG.HTTP_PROXY),
            'tools.gzip.on': True,
            'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/css',
                                      'text/javascript', 'application/json',
                                      'application/javascript'],
            'tools.auth.on': auth_enabled,
            'tools.auth_basic.on': basic_auth_enabled,
            'tools.auth_basic.realm': 'SpeakReader web server',
            'tools.auth_basic.checkpassword': cherrypy.lib.auth_basic.checkpassword_dict({
                CONFIG.HTTP_USERNAME: CONFIG.HTTP_PASSWORD}),
            'tools.sessions.on': True,
        },
        '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "images",
            'tools.staticdir.content_types': {'svg': 'image/svg+xml'},
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/css': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "css",
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/fonts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "fonts",
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/js': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "js",
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/favicon.ico': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': os.path.abspath(os.path.join(options['prog_dir'], '/html/images/favicon/favicon.ico')),
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        }
    }

    # Prevent time-outs
    appTree = cherrypy.tree.mount(WebInterface(), CONFIG.HTTP_ROOT, config=conf)
    if CONFIG.HTTP_ROOT != '/':
        cherrypy.tree.mount(BaseRedirect(), '/')

    try:
        logger.info("WebStart :: Starting Web Server on %s://%s:%d%s", protocol,
                    CONFIG.HTTP_HOST, options['http_port'], CONFIG.HTTP_ROOT)
        portend.free(str(CONFIG.HTTP_HOST), options['http_port'])
    except IOError:
        sys.stderr.write('Failed to start on port: %i. Is something else running?\n' % (options['http_port']))
        sys.exit(1)
    #
    return appTree


class BaseRedirect(object):
    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect(speakreader.CONFIG.HTTP_ROOT)


def proxy():
    # logger.debug("REQUEST URI: %s, HEADER [X-Forwarded-Host]: %s, [X-Host]: %s, [Origin]: %s, [Host]: %s",
    #              cherrypy.request.wsgi_environ['REQUEST_URI'],
    #              cherrypy.request.headers.get('X-Forwarded-Host'),
    #              cherrypy.request.headers.get('X-Host'),
    #              cherrypy.request.headers.get('Origin'),
    #              cherrypy.request.headers.get('Host'))

    # Change cherrpy.tools.proxy.local header if X-Forwarded-Host header is not present
    local = 'X-Forwarded-Host'
    if not cherrypy.request.headers.get('X-Forwarded-Host'):
        if cherrypy.request.headers.get('X-Host'):  # lighttpd
            local = 'X-Host'
        elif cherrypy.request.headers.get('Origin'):  # Squid
            local = 'Origin'
        elif cherrypy.request.headers.get('Host'):  # nginx
            local = 'Host'
        # logger.debug("cherrypy.tools.proxy.local set to [%s]", local)

    # Call original cherrypy proxy tool with the new local
    cherrypy.lib.cptools.proxy(local=local)
