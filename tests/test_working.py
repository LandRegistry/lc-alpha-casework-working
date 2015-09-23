from application.routes import app
from unittest import mock
import psycopg2
import os
import json


class MockConnection:
    def __init__(self, results):
        self.results = results

    def cursor(self, **kwargs):
        return MockCursor(self.results)

    def commit(self):
        pass

    def close(self):
        pass


class MockCursor:
    def __init__(self, results):
        self.results = results

    def execute(self, *args):
        pass

    def close(self):
        pass

    def fetchone(self):
        return [42]

    def fetchall(self):
        return self.results


dir_ = os.path.dirname(__file__)
valid_data = open(os.path.join(dir_, 'data/valid_data.json'), 'r').read()
search_data = open(os.path.join(dir_, 'data/search_data.json'), 'r').read()
no_date = open(os.path.join(dir_, 'data/no_date_data.json'), 'r').read()
no_ref = open(os.path.join(dir_, 'data/no_type_data.json'), 'r').read()
no_data = open(os.path.join(dir_, 'data/no_data.json'), 'r').read()
search_name_result = open(os.path.join(dir_, 'data/search_name_result.json'), 'r').read()
worklist_data = open(os.path.join(dir_, 'data/worklist_data.json'), 'r').read()

mock_connection = MockConnection([])
mock_connection_no_data = MockConnection("")
mock_connection_valid_data = MockConnection([[json.loads(valid_data)]])

row = {'application_data': json.loads(search_name_result)}
mock_connection_valid_data_dict = MockConnection([row])

mock_worklist_connection = MockConnection([json.loads(worklist_data)])


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
        assert response.status_code == 200
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

    @mock.patch('psycopg2.connect', side_effect=psycopg2.OperationalError('Fail'))
    def test_connect_failed(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/lodge_manual', data=valid_data, headers=headers)
        assert response.status_code == 500

    @mock.patch('psycopg2.connect', return_value=mock_connection_valid_data)
    def test_get(self, mock_connect):
        response = self.app.get('/search/42', data=valid_data)
        assert response.status_code == 200
        data = json.loads(response.data.decode())
        assert data['application_ref'] == '1222'

    @mock.patch('psycopg2.connect', side_effect=psycopg2.OperationalError('Fail'))
    def test_get_connect_failed(self, mock_connect):
        response = self.app.get('/search/42', data=valid_data)
        assert response.status_code == 500

    @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    def test_get_no_result(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/search/42', data=no_data)
        assert response.status_code == 404

    @mock.patch('psycopg2.connect', return_value=mock_connection_valid_data_dict)
    def test_get_by_name(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/search_by_name', data=search_data, headers=headers)
        print(response)
        assert response.status_code == 200
        data = json.loads(response.data.decode())
        assert data[0]['application_ref'] == '1222'

    @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    def test_get_by_name_no_result(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/search_by_name', data=search_data, headers=headers)
        assert response.status_code == 404

    @mock.patch('psycopg2.connect', side_effect=psycopg2.OperationalError('Fail'))
    def test__get_by_name_connect_failed(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/search_by_name', data=search_data, headers=headers)
        assert response.status_code == 500

    @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    def test_invalid_work_list(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/work_list/wrong_type', data=search_data, headers=headers)
        assert response.status_code == 400

    @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    def test_get_pab_list(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/work_list/pab', data=search_data, headers=headers)
        assert response.status_code == 200

    @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    def test_get_wob_list(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/work_list/wob', data=search_data, headers=headers)
        assert response.status_code == 200

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    def test_get_all_list(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/work_list/all', data=worklist_data, headers=headers)
        assert response.status_code == 200

    @mock.patch('psycopg2.connect', side_effect=psycopg2.OperationalError('Fail'))
    def test__work_list_connect_failed(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/work_list/all', data=worklist_data, headers=headers)
        assert response.status_code == 500

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    def test_get_other_list(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/work_list/amend', data=worklist_data, headers=headers)
        assert response.status_code == 200
