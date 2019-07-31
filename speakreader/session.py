#  This file is part of SpeakReader.
#

import cherrypy

def get_session_info():
    """
    Returns the session info for the user session
    """
    _session = {'user_id': None,
                'user': None,
                'user_group': 'admin',
                'access_level': 9,
                'exp': None}

    if isinstance(cherrypy.request.login, dict):
        return cherrypy.request.login

    return _session

def get_session_user_group():
    """
    Returns the user_group for the current logged in session
    """
    _session = get_session_info()
    return _session['user_group']

def get_session_user():
    """
    Returns the user_id for the current logged in session
    """
    _session = get_session_info()
    return _session['user'] if _session['user_group'] != 'admin' and _session['user'] else None

def get_session_user_id():
    """
    Returns the user_id for the current logged in session
    """
    _session = get_session_info()
    return str(_session['user_id']) if _session['user_group'] != 'admin' and _session['user_id'] else None
