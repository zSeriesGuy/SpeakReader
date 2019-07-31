#  This file is part of SpeakReader.
#

from datetime import datetime, timedelta
from urllib.parse import quote, unquote

import cherrypy
from passlib.hash import pbkdf2_sha256
import jwt

import speakreader
from speakreader import logger
from speakreader.config import DEFAULT_USERNAME, DEFAULT_PASSWORD


JWT_ALGORITHM = 'HS256'
JWT_COOKIE_NAME = 'speakreader'


def check_credentials(username=None, password=None):
    """Verifies credentials for username and password.
    Returns True or False"""

    if username and password:
        if speakreader.CONFIG.HTTP_PASSWORD:

            if speakreader.CONFIG.HTTP_HASH_PASSWORD and \
                    username == speakreader.CONFIG.HTTP_USERNAME and pbkdf2_sha256.verify(password, speakreader.CONFIG.HTTP_PASSWORD):
                return True
            elif not speakreader.CONFIG.HTTP_HASH_PASSWORD and \
                    username == speakreader.CONFIG.HTTP_USERNAME and password == speakreader.CONFIG.HTTP_PASSWORD:
                return True

    return False


def check_jwt_token():
    jwt_cookie = JWT_COOKIE_NAME
    jwt_token = cherrypy.request.cookie.get(jwt_cookie)

    if jwt_token:
        try:
            payload = jwt.decode(
                jwt_token.value, speakreader.CONFIG.JWT_SECRET, leeway=timedelta(seconds=10), algorithms=[JWT_ALGORITHM]
            )
        except (jwt.DecodeError, jwt.ExpiredSignatureError):
            return None

        return payload


def check_auth(*args, **kwargs):
    """A tool that looks in config for 'auth.require'. If found and it
    is not None, a login is required and the entry is evaluated as a list of
    conditions that the user must fulfill"""
    conditions = cherrypy.request.config.get('auth.require', None)
    if conditions is not None:
        payload = check_jwt_token()

        if payload:
            cherrypy.request.login = payload

            for condition in conditions:
                # A condition is just a callable that returns true or false
                if not condition():
                    raise cherrypy.HTTPRedirect(speakreader.CONFIG.HTTP_ROOT)

        else:
            raise cherrypy.HTTPRedirect(speakreader.CONFIG.HTTP_ROOT + "auth/logout")


def requireAuth(*conditions):
    """A decorator that appends conditions to the auth.require config
    variable."""
    def decorate(f):
        if not hasattr(f, '_cp_config'):
            f._cp_config = dict()
        if 'auth.require' not in f._cp_config:
            f._cp_config['auth.require'] = []
        f._cp_config['auth.require'].extend(conditions)
        return f
    return decorate


# Conditions are callables that return True
# if the user fulfills the conditions they define, False otherwise
#
# They can access the current username as cherrypy.request.login
#
# Define those at will however suits the application.

def member_of(user_group):
    return lambda: cherrypy.request.login and cherrypy.request.login['user_group'] == user_group


def name_is(user_name):
    return lambda: cherrypy.request.login and cherrypy.request.login['user'] == user_name


def is_admin():
    user_name = speakreader.CONFIG.HTTP_USERNAME
    return lambda: cherrypy.request.login and cherrypy.request.login['user'] == user_name


# These might be handy

def any_of(*conditions):
    """Returns True if any of the conditions match"""
    def check():
        for c in conditions:
            if c():
                return True
        return False
    return check


# By default all conditions are required, but this might still be
# needed if you want to use it inside of an any_of(...) condition
def all_of(*conditions):
    """Returns True if all of the conditions match"""
    def check():
        for c in conditions:
            if not c():
                return False
        return True
    return check


# Controller to provide login and logout actions

class AuthController(object):

    def check_auth_enabled(self):
        if not speakreader.CONFIG.HTTP_BASIC_AUTH and speakreader.CONFIG.HTTP_USERNAME and speakreader.CONFIG.HTTP_PASSWORD:
            return
        raise cherrypy.HTTPRedirect(speakreader.CONFIG.HTTP_ROOT + "manage")

    def on_login(self, username=None, success=False):
        """Called on successful login"""
        if success:
            logger.debug("WebAuth :: Admin user '%s' logged into SpeakReader." % (username))
    
    def on_logout(self, username):
        """Called on logout"""
        logger.debug("WebAuth :: Admin user '%s' logged out of SpeakReader." % (username))
    
    def get_loginform(self):
        from speakreader.webserve import serve_template
        login_default = False
        if speakreader.CONFIG.HTTP_USERNAME == DEFAULT_USERNAME \
            and speakreader.CONFIG.HTTP_PASSWORD == DEFAULT_PASSWORD:
            login_default = True
        return serve_template(templatename="login.html",
                              title="Login",
                              login_default=int(login_default))
    
    @cherrypy.expose
    def index(self, *args, **kwargs):
        raise cherrypy.HTTPRedirect(speakreader.CONFIG.HTTP_ROOT + "auth/login")

    @cherrypy.expose
    def login(self, *args, **kwargs):
        self.check_auth_enabled()

        return self.get_loginform()

    @cherrypy.expose
    def logout(self, *args, **kwargs):

        payload = check_jwt_token()
        if payload:
            self.on_logout(payload['user'])

        jwt_cookie = JWT_COOKIE_NAME
        cherrypy.response.cookie[jwt_cookie] = 'expire'
        cherrypy.response.cookie[jwt_cookie]['expires'] = 0
        cherrypy.response.cookie[jwt_cookie]['path'] = '/'

        cherrypy.request.login = None

        raise cherrypy.HTTPRedirect(speakreader.CONFIG.HTTP_ROOT + "auth/login")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def signin(self, username=None, password=None, remember_me='0', *args, **kwargs):
        if cherrypy.request.method != 'POST':
            cherrypy.response.status = 405
            return {'status': 'error', 'message': 'Sign in using POST.'}

        error_message = {'status': 'error', 'message': 'Invalid credentials.'}

        valid_login = check_credentials(username=username, password=password)

        if valid_login:
            time_delta = timedelta(days=30) if remember_me == '1' else timedelta(minutes=60)
            expiry = datetime.utcnow() + time_delta

            payload = {
                'user': username,
                'exp': expiry
            }

            jwt_token = jwt.encode(payload, speakreader.CONFIG.JWT_SECRET, algorithm=JWT_ALGORITHM).decode('utf-8')

            self.on_login(username=username,
                          success=True,
                          )

            jwt_cookie = JWT_COOKIE_NAME
            cherrypy.response.cookie[jwt_cookie] = jwt_token
            cherrypy.response.cookie[jwt_cookie]['expires'] = int(time_delta.total_seconds())
            cherrypy.response.cookie[jwt_cookie]['path'] = '/'

            cherrypy.request.login = payload
            cherrypy.response.status = 200
            return {'status': 'success'}

        else:
            self.on_login(username=username)
            logger.debug("WebAuth :: Invalid admin login attempt from '%s'." % username)
            cherrypy.response.status = 401
            return error_message
