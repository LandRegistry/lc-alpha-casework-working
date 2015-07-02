from application.routes import app
from unittest import mock
import os
import json


class MockConnection:
    def cursor(self):
        return MockCursor()

    def commit(self):
        pass

    def close(self):
        pass


class MockCursor:
    def execute(self, sql, dict):
        pass

    def close(self):
        pass

    def fetchone(self):
        return [42]


mock_connection = MockConnection()
dir = os.path.dirname(__file__)
valid_data = open(os.path.join(dir, 'data/valid_data.json'), 'r').read()
no_date = open(os.path.join(dir, 'data/no_date_data.json'), 'r').read()
no_ref = open(os.path.join(dir, 'data/no_type_data.json'), 'r').read()

class TestWorking:
    def setup_method(self, method):
        self.app = app.test_client()

    def test_health_check(self):
        response = self.app.get("/")
        assert response.status_code == 200

    @mock.patch('psycopg2.connect', return_value=mock_connection)
    def test_row_insert(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/lodge_manual', data=valid_data, headers=headers)
        assert response.status_code == 202
        dict = json.loads(response.data.decode())
        assert dict['id'] == 42

    @mock.patch('psycopg2.connect', return_value=mock_connection)
    def test_not_json(self, mock_connect):
        headers = {'Content-Type': 'application/xml'}
        response = self.app.post('/lodge_manual', data=valid_data, headers=headers)
        assert response.status_code == 415

    @mock.patch('psycopg2.connect', return_value=mock_connection)
    def test_no_date(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/lodge_manual', data=no_date, headers=headers)
        assert response.status_code == 400

    @mock.patch('psycopg2.connect', return_value=mock_connection)
    def test_no_type(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/lodge_manual', data=no_ref, headers=headers)
        assert response.status_code == 400

    @mock.patch('psycopg2.connect', side_effect=Exception('Fail'))
    def test_connect_failed(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/lodge_manual', data=valid_data, headers=headers)
        assert response.status_code == 500
