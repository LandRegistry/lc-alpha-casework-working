from application.routes import app
from application.ocr import recognise
from unittest import mock
import psycopg2
import os
import json


class FakeResponse:
    def __init__(self, data=None, text=None, status_code=200):
        self.data = data
        self.text = text
        self.status_code = status_code


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
# work_item_data = open(os.path.join(dir_, 'data/workitem_data.json'), 'r').read()
error_data = open(os.path.join(dir_, 'data/error_data.json'), 'r').read()

mock_connection = MockConnection([])
mock_connection_no_data = MockConnection("")
mock_connection_valid_data = MockConnection([[json.loads(valid_data)]])

row = {'application_data': json.loads(search_name_result)}
mock_connection_valid_data_dict = MockConnection([row])

mock_worklist_connection = MockConnection([json.loads(worklist_data)])
mock_worklist_connection_del = MockConnection([json.loads(worklist_data)], 'Y')
mock_error_connection = MockConnection([json.loads(error_data)])

keyno_get = FakeResponse(text='{"key_number": "1234567"}')
counties_get = MockConnection([{"name": "Devon"}, {"name": "Cornwall"}])


class TestWorking:
    def setup_method(self, method):
        self.app = app.test_client()

    def test_health_check(self):
        response = self.app.get("/")
        assert response.status_code == 200

    # @mock.patch('psycopg2.connect', return_value=mock_connection)
    # def test_row_insert(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.post('/applications', data=worklist_data, headers=headers)
    #     assert response.status_code == 200
    #     dict = json.loads(response.data.decode())
    #     assert dict['id'] == 42
    #
    # @mock.patch('psycopg2.connect', return_value=mock_connection)
    # def test_not_json(self, mock_connect):
    #     headers = {'Content-Type': 'application/xml'}
    #     response = self.app.post('/applications', data=valid_data, headers=headers)
    #     assert response.status_code == 415
    #
    # @mock.patch('psycopg2.connect', return_value=mock_connection)
    # def test_no_date(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.post('/applications', data=no_date, headers=headers)
    #     assert response.status_code == 400
    #
    # @mock.patch('psycopg2.connect', return_value=mock_connection)
    # def test_no_type(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.post('/applications', data=no_ref, headers=headers)
    #     assert response.status_code == 400
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    # def test_get(self, mock_connect):
    #     response = self.app.get('/applications/42', data=valid_data)
    #     assert response.status_code == 200
    #     data = json.loads(response.data.decode())
    #     assert data['work_type'] == 'bank_regn'
    #
    # @mock.patch('psycopg2.connect', side_effect=psycopg2.OperationalError('Fail'))
    # def test_get_connect_failed(self, mock_connect):
    #     response = self.app.get('/applications/42', data=valid_data)
    #     assert response.status_code == 500
    #
    # @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    # def test_get_no_result(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.get('/applications/42', data=no_data)
    #     assert response.status_code == 404
    #
    # @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    # def test_invalid_work_list(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.get('/applications?type=wrong_type', data=search_data, headers=headers)
    #     assert response.status_code == 400
    #
    # @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    # def test_get_pab_list(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.get('/applications?type=pab', data=search_data, headers=headers)
    #     assert response.status_code == 200
    #
    # @mock.patch('psycopg2.connect', return_value=mock_connection_no_data)
    # def test_get_wob_list(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.get('/applications?type=wob', data=search_data, headers=headers)
    #     assert response.status_code == 200
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    # def test_get_all_list(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.get('/applications?type=all', data=worklist_data, headers=headers)
    #     assert response.status_code == 200
    #
    # @mock.patch('psycopg2.connect', side_effect=psycopg2.OperationalError('Fail'))
    # def test_work_list_connect_failed(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.get('/applications', data=worklist_data, headers=headers)
    #     assert response.status_code == 500
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    # def test_get_other_list(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.get('/applications?type=amend', data=worklist_data, headers=headers)
    #     assert response.status_code == 200
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    # def test_work_item_insert(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.post('/applications', data=worklist_data, headers=headers)
    #     assert response.status_code == 200
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    # def test_work_item_invalid_data(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.post('/applications', data='{"foo": "bar"}', headers=headers)
    #     assert response.status_code == 400
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    # def test_work_item_invalid_header(self, mock_connect):
    #     headers = {'Content-Type': 'text'}
    #     response = self.app.post('/applications', data=worklist_data, headers=headers)
    #     assert response.status_code == 415
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection_del)
    # def test_work_item_delete_fail(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.delete('/applications/16', headers=headers)
    #     assert response.status_code == 404
    #
    # @mock.patch('psycopg2.connect', return_value=mock_worklist_connection)
    # def test_work_item_delete(self, mock_connect):
    #     headers = {'Content-Type': 'application/json'}
    #     response = self.app.delete('/applications/16', headers=headers)
    #     assert response.status_code == 204
    #
    # @mock.patch('requests.get', return_value=keyno_get)
    # def test_get_keyholder(self, mock_get):
    #     response = self.app.get('/keyholders/1123456')
    #     data = json.loads(response.data.decode())
    #     print(data)
    #     assert data['key_number'] == '1234567'
    #     assert response.status_code == 200
    #
    # @mock.patch('psycopg2.connect', return_value=counties_get)
    # def test_get_counties(self, mock_get):
    #     response = self.app.get('/counties')
    #     print(response.data)
    #     data = json.loads(response.data.decode())
    #     assert len(data) == 2
    #     assert data[0] == "Devon"

    def scan_image(self, file):
        filename = os.path.join(dir_, "ocr_test/" + file)
        file_bytes = open(filename, 'rb')
        return recognise(file_bytes)

    def test_ocr_k1(self):
        assert self.scan_image('k1.tiff') == 'K1'

    def test_ocr_k2(self):
        assert self.scan_image('k2.tiff') == 'K2'

    def test_ocr_k3(self):
        assert self.scan_image('k3.tiff') == 'K3'

    def test_ocr_k4(self):
        assert self.scan_image('k4.tiff') == 'K4'

    def test_ocr_k6(self):
        assert self.scan_image('k6.tiff') == 'K6'

    def test_ocr_k7(self):
        assert self.scan_image('k7.tiff') == 'K7'

    def test_ocr_k8(self):
        assert self.scan_image('k8.tiff') == 'K8'

    def test_ocr_k9(self):
        assert self.scan_image('k9.tiff') == 'K9'

    def test_ocr_k10(self):
        assert self.scan_image('k10.tiff') == 'K10'

    def test_ocr_k11(self):
        assert self.scan_image('k11.tiff') == 'K11'

    def test_ocr_k12(self):
        assert self.scan_image('k12.tiff') == 'K12'

    def test_ocr_k13(self):
        assert self.scan_image('k13.tiff') == 'K13'

    def test_ocr_k15(self):
        assert self.scan_image('k15.tiff') == 'K15'

    def test_ocr_k16(self):
        assert self.scan_image('k16.tiff') == 'K16'

    def test_ocr_k19(self):
        assert self.scan_image('k19.tiff') == 'K19'

    def test_ocr_k20(self):
        assert self.scan_image('k20.tiff') == 'K20'

    # def test_ocr_k108(self):
    #     assert False
    #
    # def test_ocr_k113(self):
    #     assert False
    #
    # def test_ocr_k164(self):
    #     assert False
    #
    # def test_ocr_k199(self):
    #     assert False

    def test_ocr_k16(self):
        assert self.scan_image('6.14.tiff') == 'PA(B)'

    def test_ocr_k19(self):
        assert self.scan_image('6.46.tiff') == 'WO(B)'

    def test_ocr_k20(self):
        assert self.scan_image('LRRABO.tiff') == 'WO(B) Amend'