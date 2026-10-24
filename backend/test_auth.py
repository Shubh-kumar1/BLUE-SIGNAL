import hashlib
import os
import secrets
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATABASE_DIR = tempfile.TemporaryDirectory(prefix='bluesignal-auth-')
os.chdir(TEST_DATABASE_DIR.name)
sys.path.insert(0, BACKEND_DIR)
os.environ['SECRET_KEY'] = secrets.token_urlsafe(48)

transformers_stub = types.ModuleType('transformers')
transformers_stub.pipeline = lambda *args, **kwargs: (_ for _ in ()).throw(
    AssertionError('AI models should not initialize for auth tests')
)
sys.modules.setdefault('transformers', transformers_stub)

torch_stub = types.ModuleType('torch')
torch_stub.set_num_threads = lambda *_args: None
torch_stub.get_num_threads = lambda: 1
sys.modules.setdefault('torch', torch_stub)

geopy_stub = types.ModuleType('geopy')
geocoders_stub = types.ModuleType('geopy.geocoders')
geocoders_stub.Nominatim = object
sys.modules.setdefault('geopy', geopy_stub)
sys.modules.setdefault('geopy.geocoders', geocoders_stub)

import jwt
import database
from app import app, hash_password, verify_password
from werkzeug.security import check_password_hash


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.usernames = []

    def tearDown(self):
        conn = database.get_connection()
        try:
            for username in self.usernames:
                conn.execute('DELETE FROM users WHERE username = ?', (username,))
            conn.commit()
        finally:
            conn.close()

    def make_user_data(self, **updates):
        data = {
            'username': 'auth_test_user',
            'email': 'auth-test@example.invalid',
            'password': 'safe-test-password',
            'role': 'citizen',
            'full_name': 'Auth Test User',
        }
        data.update(updates)
        self.usernames.append(data['username'])
        return data

    def register_user(self, **updates):
        data = self.make_user_data(**updates)
        response = self.client.post('/api/auth/register', json=data)
        return data, response

    def test_successful_signup_stores_a_secure_hash(self):
        data, response = self.register_user()
        self.assertEqual(response.status_code, 201)
        stored = database.get_user_by_username(data['username'])
        self.assertNotEqual(stored['password'], data['password'])
        self.assertTrue(stored['password'].startswith(('scrypt:', 'pbkdf2:')))
        self.assertTrue(check_password_hash(stored['password'], data['password']))

    def test_duplicate_username_and_email_are_conflicts(self):
        data, response = self.register_user()
        self.assertEqual(response.status_code, 201)

        duplicate_username = self.client.post(
            '/api/auth/register',
            json={**data, 'email': 'different@example.invalid'}
        )
        duplicate_email = self.client.post(
            '/api/auth/register',
            json={**data, 'username': 'another_test_user'}
        )
        self.usernames.append('another_test_user')
        self.assertEqual(duplicate_username.status_code, 409)
        self.assertEqual(duplicate_email.status_code, 409)

    def test_malformed_missing_and_invalid_signup_inputs_are_rejected(self):
        for body in (None, {}, {'username': [], 'email': 'bad', 'password': '123', 'role': 'citizen'}):
            response = self.client.post('/api/auth/register', json=body)
            self.assertEqual(response.status_code, 400)
            self.assertIsInstance(response.get_json(), dict)

        response = self.client.post(
            '/api/auth/register',
            json=self.make_user_data(role='superuser')
        )
        self.assertEqual(response.status_code, 400)

    def test_successful_login_returns_a_signed_expiring_token(self):
        data, response = self.register_user()
        self.assertEqual(response.status_code, 201)

        response = self.client.post('/api/auth/login', json={
            'username': data['username'],
            'password': data['password'],
        })
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        payload = jwt.decode(body['token'], app.config['SECRET_KEY'], algorithms=['HS256'])
        self.assertEqual(payload['username'], data['username'])
        self.assertGreater(payload['exp'], datetime.now(timezone.utc).timestamp())

    def test_wrong_password_and_unknown_username_are_unauthorized(self):
        data, response = self.register_user()
        self.assertEqual(response.status_code, 201)

        wrong_password = self.client.post('/api/auth/login', json={
            'username': data['username'],
            'password': 'incorrect-password',
        })
        unknown_user = self.client.post('/api/auth/login', json={
            'username': 'unknown-auth-user',
            'password': data['password'],
        })
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_user.status_code, 401)
        self.assertEqual(wrong_password.get_json(), unknown_user.get_json())

    def test_login_rejects_malformed_input_and_migrates_legacy_hash(self):
        self.assertEqual(self.client.post('/api/auth/login', data='not json').status_code, 400)
        self.assertEqual(self.client.post('/api/auth/login', json={}).status_code, 400)

        data = self.make_user_data()
        legacy_hash = hashlib.sha256(data['password'].encode()).hexdigest()
        user_id = database.create_user(
            data['username'], data['email'], legacy_hash, data['role'], data['full_name']
        )
        response = self.client.post('/api/auth/login', json={
            'username': data['username'],
            'password': data['password'],
        })
        updated = database.get_user_by_username(data['username'])
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(updated['password'], legacy_hash)
        self.assertTrue(verify_password(data['password'], updated['password']))
        self.assertIsNotNone(user_id)

    def test_invalid_and_expired_tokens_are_rejected(self):
        self.assertEqual(
            self.client.get('/api/auth/citizen/posts', headers={'Authorization': 'Bearer not-a-jwt'}).status_code,
            401
        )

        expired = jwt.encode({
            'username': 'expired_test_user',
            'exp': datetime.now(timezone.utc) - timedelta(seconds=1),
        }, app.config['SECRET_KEY'], algorithm='HS256')
        response = self.client.get(
            '/api/auth/citizen/posts',
            headers={'Authorization': f'Bearer {expired}'}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'Token has expired')

        bad_signature = jwt.encode({
            'username': 'expired_test_user',
            'exp': datetime.now(timezone.utc) + timedelta(minutes=5),
        }, secrets.token_urlsafe(48), algorithm='HS256')
        response = self.client.get(
            '/api/auth/citizen/posts',
            headers={'Authorization': f'Bearer {bad_signature}'}
        )
        self.assertEqual(response.status_code, 401)

    def test_protected_route_checks_role(self):
        data, response = self.register_user(role='authority')
        self.assertEqual(response.status_code, 201)
        login = self.client.post('/api/auth/login', json={
            'username': data['username'],
            'password': data['password'],
        }).get_json()
        response = self.client.get(
            '/api/auth/citizen/posts',
            headers={'Authorization': f"Bearer {login['token']}"}
        )
        self.assertEqual(response.status_code, 403)

    def test_database_errors_return_safe_json_errors(self):
        with patch.object(database, 'get_user_by_username', side_effect=sqlite3.OperationalError('database unavailable')):
            response = self.client.post('/api/auth/login', json={
                'username': 'db-error-user',
                'password': 'safe-test-password',
            })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error'], 'Login is temporarily unavailable')

        with patch.object(database, 'create_user', side_effect=sqlite3.OperationalError('database unavailable')):
            response = self.client.post('/api/auth/register', json=self.make_user_data())
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['error'], 'Registration is temporarily unavailable')

    def test_cors_allows_the_production_frontend(self):
        response = self.client.options(
            '/api/auth/login',
            headers={
                'Origin': 'https://blue-signal.vercel.app',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            },
        )
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'https://blue-signal.vercel.app')


if __name__ == '__main__':
    unittest.main()
