import datetime
import importlib
import json
import time
from unittest.mock import Mock

import pytest
from faf import db

import api
from api import User
from api.error import ErrorCode
from api.users_route import create_token


@pytest.fixture
def setup_users(request, app):
    app.debug = True
    with db.connection:
        cursor = db.connection.cursor()
        cursor.execute("TRUNCATE TABLE ladder1v1_rating")
        cursor.execute("TRUNCATE TABLE global_rating")
        cursor.execute("delete from login")
        cursor.execute("""INSERT INTO login
        (id, login, password, email) VALUES
        (1, 'abc', 'pw_a', 'a@aa.aa'),
        (2, 'bcd', 'pw_b', 'b@bb.bb')""")
        cursor.execute("TRUNCATE TABLE email_domain_blacklist")
        cursor.execute("INSERT INTO email_domain_blacklist VALUES ('zzz.com'), ('abc.de')")

    def finalizer():
        with db.connection:
            cursor = db.connection.cursor()
            cursor.execute("TRUNCATE TABLE ladder1v1_rating")
            cursor.execute("TRUNCATE TABLE global_rating")

    request.addfinalizer(finalizer)


@pytest.fixture
def oauth():
    def get_token(access_token=None, refresh_token=None):
        return Mock(
            user=User(id=1),
            expires=datetime.datetime.now() + datetime.timedelta(hours=1),
            scopes=['write_account_data']
        )

    importlib.reload(api)
    importlib.reload(api.oauth_handlers)
    importlib.reload(api.users_route)

    api.app.config.from_object('config')
    api.api_init()
    api.app.debug = True

    api.oauth.tokengetter(get_token)

    return api.app.test_client()


def test_register_invalid_email(test_client, setup_users):
    response = test_client.post('/users/register',
                                data={'name': 'new_user', 'email': 'abbb.cc', 'pw_hash': '0000'})

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.INVALID_EMAIL.value['code']


def test_register_invalid_username(test_client, setup_users):
    response = test_client.post('/users/register',
                                data={'name': 'a,b', 'email': 'a@bbb.cc', 'pw_hash': '0000'})

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.INVALID_USERNAME.value['code']


def test_register_username_taken(test_client, setup_users):
    response = test_client.post('/users/register',
                                data={'name': 'Abc', 'email': 'a@bbb.cc', 'pw_hash': '0000'})

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.USERNAME_TAKEN.value['code']


def test_register_email_taken(test_client, setup_users):
    response = test_client.post('/users/register',
                                data={'name': 'new_user', 'email': 'a@AA.aa', 'pw_hash': '0000'})

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.EMAIL_REGISTERED.value['code']


def test_register_email_blacklisted(test_client, setup_users):
    response = test_client.post('/users/register',
                                data={'name': 'new_user', 'email': 'alpha@ZZZ.com', 'pw_hash': '0000'})

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.BLACKLISTED_EMAIL.value['code']


def test_register_success(test_client, setup_users):
    response = test_client.post('/users/register',
                                data={'name': 'alpha', 'email': 'a@validmail.com', 'pw_hash': '0000'})

    assert response.status_code == 200


def test_validate_registration_invalid_email(test_client, setup_users):
    response = test_client.get('/users/validate_registration/' + create_token('new_user', 'abbb.cc', '0000', 0))

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.INVALID_EMAIL.value['code']


def test_validate_registration_username_taken(test_client, setup_users):
    response = test_client.get('/users/validate_registration/' + create_token('Abc', 'a@bbb.cc', '0000', 0))

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.USERNAME_TAKEN.value['code']


def test_validate_registration_email_taken(test_client, setup_users):
    response = test_client.get('/users/validate_registration/' + create_token('new_user', 'a@AA.aa', '0000', 0))

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.EMAIL_REGISTERED.value['code']


def test_validate_registration_email_blacklisted(test_client, setup_users):
    response = test_client.get('/users/validate_registration/' + create_token('new_user', 'a@ZZZ.com', '0000', 0))

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.BLACKLISTED_EMAIL.value['code']


def test_validate_registration_success(test_client, setup_users):
    response = test_client.get(
        '/users/validate_registration/' + create_token('alpha', 'a@faforever.com', '0000', time.time() + 60))

    assert response.status_code == 200

    with db.connection:
        cursor = db.connection.cursor(db.pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM login WHERE login = 'alpha'")

        result = cursor.fetchone()
        user_id = result['id']

        assert result['login'] == 'alpha'
        assert result['email'] == 'a@faforever.com'
        assert result['password'] == '0000'

        cursor.execute("SELECT * FROM global_rating WHERE id = %s" % user_id)
        assert cursor.fetchone() is not None

        cursor.execute("SELECT * FROM ladder1v1_rating WHERE id = %s" % user_id)
        assert cursor.fetchone() is not None


def test_validate_token_expired(test_client, setup_users):
    response = test_client.get(
        '/users/validate_registration/' + create_token('alpha', 'a@faforever.com', '0000', time.time() - 60))

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.USER_TOKEN_EXPIRED.value['code']


def test_reset_password_success(test_client, setup_users):
    response = test_client.post('/users/reset_password',
                                data={'name': 'abc', 'email': 'a@aa.aa', 'pw_hash': '0000'})

    assert response.status_code == 200


def test_reset_password_wrong_username(test_client, setup_users):
    response = test_client.post('/users/reset_password',
                                data={'name': 'wrong_user', 'email': 'a@aa.aa', 'pw_hash': '0000'})

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.PASSWORD_RESET_INVALID.value['code']


def test_reset_password_wrong_email(test_client, setup_users):
    response = test_client.post('/users/reset_password',
                                data={'name': 'abc', 'email': 'wrong_mail@bbb.cc', 'pw_hash': '0000'})

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.PASSWORD_RESET_INVALID.value['code']


def test_validate_password_expired(test_client, setup_users):
    response = test_client.get('/users/validate_password/' + create_token('abc', 'a@aa.aa', '0000', time.time() - 60))

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.USER_TOKEN_EXPIRED.value['code']


def test_validate_password_invalid_data(test_client, setup_users):
    response = test_client.get(
        '/users/validate_password/' + create_token('wrong_user', 'a@aa.aa', '0000', time.time() + 60))

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.PASSWORD_RESET_FAILED.value['code']


def test_validate_password_success(test_client, setup_users):
    response = test_client.get(
        '/users/validate_password/' + create_token('abc', 'a@aa.aa', 'test123', time.time() + 60))

    assert response.status_code == 200

    with db.connection:
        cursor = db.connection.cursor(db.pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM login WHERE login = 'abc' AND password = 'test123'")
        assert cursor.fetchone() is not None


def test_change_password_invalid_user(oauth, test_client, setup_users):
    response = test_client.post('/users/change_password', data={
        'name': 'wrong_user', 'pw_hash_old': '0000', 'pw_hash_new': '0001'
    })

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.PASSWORD_CHANGE_FAILED.value['code']


def test_change_password_invalid_password(oauth, test_client, setup_users):
    response = test_client.post('/users/change_password', data={
        'name': 'abc', 'pw_hash_old': 'wrong_password', 'pw_hash_new': '0001'
    })

    assert response.status_code == 400
    assert response.content_type == 'application/vnd.api+json'

    result = json.loads(response.data.decode('utf-8'))
    assert len(result['errors']) == 1
    assert result['errors'][0]['code'] == ErrorCode.PASSWORD_CHANGE_FAILED.value['code']


def test_change_password_success(oauth, test_client, setup_users):
    response = test_client.post('/users/change_password', data={
        'name': 'abc', 'pw_hash_old': 'pw_a', 'pw_hash_new': 'new_pw_a'
    })

    assert response.status_code == 200

    with db.connection:
        cursor = db.connection.cursor(db.pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM login WHERE login = 'abc' AND password = 'new_pw_a'")
        assert cursor.fetchone() is not None
