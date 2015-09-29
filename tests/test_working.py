from application.routes import app
from unittest import mock
import psycopg2
import os
import json


class MockConnection:
    def __init__(self, results, del_flag=None):
        self.results = results
        self.del_flag = del_flag

    def cursor(self, **kwargs):
        return MockCursor(self.results, self, self.del_flag)

    def commit(self):
        pass

    def close(self):
        pass


class MockCursor:
    def __init__(self, results, conn, del_flag):
        self.results = results
        self.connection = conn
        if del_flag == 'Y':
            count = 0
        else:
            count = 1
        self.rowcount = count

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
work_item_data = open(os.path.join(dir_, 'data/workitem_data.json'), 'r').read()
error_data = open(os.path.join(dir_, 'data/error_data.json'), 'r').read()

mock_connection = MockConnection([])
mock_connection_no_data = MockConnection("")
mock_connection_valid_data = MockConnection([[json.loads(valid_data)]])

row = {'application_data': json.loads(search_name_result)}
mock_connection_valid_data_dict = MockConnection([row])

mock_worklist_connection = MockConnection([json.loads(worklist_data)])
mock_worklist_connection_del = MockConnection([json.loads(worklist_data)], 'Y')
mock_error_connection = MockConnection([json.loads(error_data)])


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

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    def test_work_item_insert(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/workitem', data=work_item_data, headers=headers)
        assert response.status_code == 200

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    def test_work_item_invalid_data(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/workitem', data=worklist_data, headers=headers)
        assert response.status_code == 400

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    def test_work_item_invalid_header(self, mock_connect):
        headers = {'Content-Type': 'text'}
        response = self.app.post('/workitem', data=work_item_data, headers=headers)
        assert response.status_code == 415

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection_del)
    def test_work_item_delete_fail(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.delete('/workitem/16', headers=headers)
        assert response.status_code == 404

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    def test_work_item_delete(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.delete('/workitem/16', headers=headers)
        assert response.status_code == 204

    def test_error_get(self):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/error', headers=headers)
        assert response.status_code == 200

    @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    def test_error_post(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.post('/error', data=error_data, headers=headers)
        assert response.status_code == 201

    @mock.patch('psycopg2.connect', return_value=mock_error_connection)
    def test_errors(self, mock_connect):
        headers = {'Content-Type': 'application/json'}
        response = self.app.get('/errors', data=error_data, headers=headers)
        assert response.status_code == 200