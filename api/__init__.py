"""
Forged Alliance Forever API project

Distributed under GPLv3, see license.txt
"""
import sys
import time
from urllib.parse import urlencode

import flask
import statsd
from flask import Flask, session, jsonify, request
from flask_cache import Cache
from flask_cors import CORS
from flask_jwt import JWT
from flask_login import LoginManager
from flask_oauthlib.contrib.oauth2 import bind_cache_grant
from flask_oauthlib.provider import OAuth2Provider

from api.deployment.deployment_manager import DeploymentManager
from api.error import ApiException
from api.jwt_user import JwtUser
from api.user import User, UserGroup

__version__ = '0.7.0'
__author__ = 'Chris Kitching, Michael Søndergaard, Vytautas Mickus, Michel Jung'
__contact__ = 'admin@faforever.com'
__license__ = 'GPLv3'
__copyright__ = 'Copyright (c) 2011-2015 ' + __author__

if sys.version_info.major != 3:
    raise RuntimeError(
        "FAForever API requires python 3.\n")


# ======== Init Flask ==========

app = Flask('api')
CORS(app)
cache = Cache(config={'CACHE_TYPE': 'simple'}, with_jinja2_ext=False)

login_manager = LoginManager()
login_manager.init_app(app)

_make_response = app.make_response

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE'
    return response

@app.errorhandler(ApiException)
def handle_api_exception(error):
    mt = request.accept_mimetypes.best_match([
        'application/vnd.api+json',
        'application/json',
        'text/plain',
        'text/html'
        ],
        'application/vnd.api+json',
        )
    if mt.startswith('application'):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        response.headers['content-type'] = mt
        return response
    elif mt == 'text/plain':
        response = error.to_text()
    elif mt == 'text/html':
        response = """
<html>
<head><title>API Error</title></head>
<body>
<pre>
{}
</pre>
</body>
</html>
        """.format(error.to_text())
    resp = _make_response(response)
    resp.status_code = error.status_code
    resp.headers['content-type'] =  mt
    return resp


def default_cache_key():
    args = flask.request.args
    key = flask.request.path + '?' + urlencode(
        [(k, v) for k in sorted(args) for v in sorted(args.getlist(k))])
    return key

def jwt_identity(payload):
    return User.get_by_id(payload['identity'])

flask_jwt = JWT(None, authentication_handler=None, identity_handler=jwt_identity)


def make_response_json(rv):
    """
    Override the flask make_response function to default to application/json
    for lists and dictionaries.
    """
    if isinstance(rv, app.response_class):
        return rv
    if isinstance(rv, dict):
        response = jsonify(rv)
        response.headers['content-type'] = 'application/vnd.api+json'
        return response
    elif isinstance(rv, tuple):
        values = dict(zip(['response', 'status', 'headers'], rv))
        response, status, headers = values.get('response', ''), values.get('status', 200), values.get('headers', [])
        if isinstance(response, dict):
            response = jsonify(values['response'])
        else:
            response = _make_response(response)
        response.status_code = values.get('status', 200)

        if 'headers' in values and values['headers'] is not None:
            response.headers = values.get('headers')
        response.headers['content-type'] = 'application/vnd.api+json'
        return response
    else:
        return _make_response(rv)


app.make_response = make_response_json

# ======== Init Database =======

import faf.db


# ======== Init App =======

def api_init():
    """
    Initializes flask. Call _after_ setting flask config.
    """

    faf.db.init_db(app.config)
    github = api.deployment.github.make_session(app.config['GITHUB_USER'],
                                                app.config['GITHUB_TOKEN'])
    slack = api.deployment.slack.make_session(app.config['SLACK_HOOK_URL'])

    app.deployment_manager = DeploymentManager(app.config['ENVIRONMENT'], app.config['GITHUB_SECRET'],
                                               app.config['GIT_OWNER'], github, slack)
    for deploy_configuration in app.config['DEPLOYMENTS']:
        app.deployment_manager.add(deploy_configuration)
    app.github = github

    app.secret_key = app.config['FLASK_LOGIN_SECRET_KEY']
    flask_jwt.init_app(app)
    cache.init_app(app)


    if app.config.get('STATSD_SERVER'):
        host, port = app.config['STATSD_SERVER'].split(':')
        stats = statsd.StatsClient(host, port)

        @app.before_request
        def before_req():
            request._start_time = time.time()

        @app.after_request
        def after_req(response):
            stats.timing('api.request', (time.time()-request._start_time)*1000)
            return response
            

# ======== Init OAuth =======


def get_current_user():
    if 'user_id' not in session:
        return None

    return User.get_by_id(session['user_id'])


oauth = OAuth2Provider(app)
app.config.update({'OAUTH2_CACHE_TYPE': 'simple'})

bind_cache_grant(app, oauth, get_current_user)

# ======== Import (initialize) oauth2 handlers =====
import api.oauth_handlers
# ======== Import (initialize) routes =========
import api.auth
import api.avatars
import api.bugreports
import api.mods
import api.maps
import api.oauth_client
import api.oauth_token
import api.deployment.slack
import api.achievements
import api.events
import api.query_commons
import api.leaderboards
import api.coop
import api.players
import api.users_route
import api.featured_mods
import api.deployment.routes
