from application import app
from flask import Response, request
import json
import logging
import psycopg2
import psycopg2.extras
import requests
from application.applications import insert_new_application, get_application_list, get_application_by_id, \
    update_application_details, bulk_insert_applications, complete_application, delete_application

valid_types = ['all', 'pab', 'wob', 'bank_regn', 'lc_regn', 'amend', 'cancel', 'prt_search', 'search', 'oc']


@app.route('/', methods=["GET"])
def index():
    return Response(status=200)


@app.errorhandler(Exception)
def error_handler(err):
    logging.error('========== Error Caught ===========')
    logging.error(err)
    return Response(str(err), status=500)


def check_lc_health():
    return requests.get(app.config['LAND_CHARGES_URI'] + '/health')


application_dependencies = [
    {
        "name": "land-charges",
        "check": check_lc_health
    }
]


@app.route('/health', methods=['GET'])
def health():
    result = {
        'status': 'OK',
        'dependencies': {}
    }

    status = 200
    for dependency in application_dependencies:
        response = dependency["check"]()
        result['dependencies'][dependency['name']] = str(response.status_code) + ' ' + response.reason
        data = json.loads(response.content.decode('utf-8'))
        for key in data['dependencies']:
            result['dependencies'][key] = data['dependencies'][key]

    return Response(json.dumps(result), status=status, mimetype='application/json')


# ============ APPLICATIONS ==============
@app.route('/applications', methods=['GET'])
def get_applications():
    list_type = 'all'
    if 'type' in request.args:
        list_type = request.args['type']
    if list_type not in valid_types:
        return Response("Error: '" + list_type + "' is not one of the accepted work list types", status=400)

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    applications = get_application_list(cursor, list_type)
    complete(cursor)

    data = json.dumps(applications, ensure_ascii=False)
    return Response(data, status=200, mimetype='application/json')


@app.route('/applications', methods=['POST'])
def create_application():
    if request.headers['Content-Type'] != "application/json":
        return Response(status=415)

    action = 'store'
    if 'action' in request.args:
        action = request.args['action']

    data = request.get_json(force=True)
    print(data)
    if 'application_type' not in data or 'date_received' not in data or "work_type" not in data or 'application_data' not in data:
        return Response(status=400)

    cursor = connect()
    if action == 'store':
        item_id = insert_new_application(cursor, data)
    elif action == 'complete':
        complete_application(cursor, data)
    else:
        return Response("Invalid action", status=400)

    complete(cursor)
    return Response(json.dumps({'id': item_id}), status=200, mimetype='application/json')


@app.route('/applications/<appn_id>', methods=['GET'])
def get_application(appn_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    appn = get_application_by_id(cursor, appn_id)
    complete(cursor)

    if appn is None:
        return Response(status=404)
    return Response(json.dumps(appn), status=200, mimetype='application/json')


@app.route('/applications/<appn_id>', methods=['DELETE'])
def remove_application(appn_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    rows = delete_application(cursor, appn_id)
    complete(cursor)

    if rows == 0:
        return Response(status=404)
    return Response(status=204, mimetype='application/json')


@app.route('/applications/<appn_id>', methods=['PUT'])
def update_application(appn_id):
    # TODO: validate
    data = request.get_json(force=True)
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    update_application_details(cursor, appn_id, data)
    appn = get_application_by_id(cursor, appn_id)
    complete(cursor)
    return Response(json.dumps(appn), status=200)


# =========== OTHER ROUTES ==============
@app.route('/keyholders/<key_number>', methods=['GET'])
def get_keyholder(key_number):
    uri = app.config['LEGACY_ADAPTER_URI'] + '/keyholders/' + key_number
    response = requests.get(uri)
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/counties', methods=['GET'])
def get_counties_list():
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT name FROM counties")
    rows = cursor.fetchall()
    counties = [row['name'] for row in rows]
    complete(cursor)
    return Response(json.dumps(counties), status=200, mimetype='application/json')


@app.route('/complex_names/<name>', methods=['GET'])
def get_complex_names(name):
    uri = app.config['LEGACY_ADAPTER_URI'] + 'complex_names/' + name
    response = requests.get(uri)
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/complex_names/search', methods=['POST'])
def get_complex_names_post():
    data = request.get_json(force=True)
    uri = app.config['LEGACY_ADAPTER_URI'] + 'complex_names/search'
    response = requests.post(uri, data=data, headers={'Content-Type': 'application/json'})
    return Response(response.text, status=response.status_code, mimetype='application/json')


# ========= Dev Routes ==============
@app.route('/applications', methods=['DELETE'])
def clear_applications():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    cursor = connect()
    cursor.execute("DELETE FROM pending_application")
    complete(cursor)
    return Response(status=200)


@app.route('/applications', methods=['PUT'])
def bulk_add_applications():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    data = request.get_json(force=True)
    cursor = connect()
    ids = bulk_insert_applications(cursor, data)
    complete(cursor)
    return Response(json.dumps({'ids': ids}), status=200, mimetype='application/json')


@app.route('/counties', methods=['POST'])
def load_counties():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    if request.headers['Content-Type'] != "application/json":
        logging.error('Content-Type is not JSON')
        return Response(status=415)

    json_data = request.get_json(force=True)
    cursor = connect()
    for item in json_data:
        if 'cym' not in item:
            item['cym'] = None

        cursor.execute('INSERT INTO COUNTIES (name, welsh_name) VALUES (%(e)s, %(c)s)',
                       {
                           'e': item['eng'], 'c': item['cym']
                       })
    complete(cursor)
    return Response(status=200)


@app.route('/counties', methods=['DELETE'])
def delete_counties():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    cursor = connect()
    cursor.execute('DELETE FROM COUNTIES')
    complete(cursor)
    return Response(status=200)


def connect(cursor_factory=None):
    connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
        app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
        app.config['DATABASE_PASSWORD']))
    return connection.cursor(cursor_factory=cursor_factory)


def complete(cursor):
    cursor.connection.commit()
    cursor.close()
    cursor.connection.close()


# ========= OLD ROUTES ============
# @app.route('/workitem', methods=["POST"])
# def manual():
#     if request.headers['Content-Type'] != "application/json":
#         return Response(status=415)
#
#     data = request.get_json(force=True)
#     if 'application_type' not in data \
#             or 'date' not in data \
#             or "work_type" not in data \
#             or 'document_id' not in data:
#         return Response(status=400)
#
#     app_data = {
#         "document_id": data['document_id']
#     }
#
#     cursor = connect()
#     cursor.execute("INSERT INTO pending_application (application_data, date_received, "
#                    "application_type, status, work_type) " +
#                    "VALUES (%(json)s, %(date)s, %(type)s, %(status)s, %(work_type)s) "
#                    "RETURNING id", {"json": json.dumps(app_data), "date": data['date'],
#                                     "type": data['application_type'],
#                                     "status": "new", "work_type": data['work_type']})
#     item_id = cursor.fetchone()[0]
#     complete(cursor)
#     return Response(json.dumps({'id': item_id}), status=200, mimetype='application/json')
#
#
# @app.route('/workitems', methods=['DELETE'])
# def delete_workitems():
#     cursor = connect()
#     cursor.execute("DELETE FROM pending_application")
#     complete(cursor)
#     return Response(status=200)
#
#
# @app.route('/workitem/bulk', methods=["POST"])
# def bulk_load():
#     data = request.get_json(force=True)
#     for item in data:
#         if 'application_type' not in item or 'date' not in item or "work_type" not in item or 'document_id' not in item:
#             return Response(status=400)
#
#     items = []
#     cursor = connect()
#     for item in data:
#         app_data = {
#             "document_id": item['document_id']
#         }
#         cursor.execute("INSERT INTO pending_application (application_data, date_received, "
#                        "application_type, status, work_type) " +
#                        "VALUES (%(json)s, %(date)s, %(type)s, %(status)s, %(work_type)s) "
#                        "RETURNING id", {"json": json.dumps(app_data), "date": item['date'],
#                                         "type": item['application_type'],
#                                         "status": "new", "work_type": item['work_type']})
#         items.append(cursor.fetchone()[0])
#     complete(cursor)
#     return Response(json.dumps({'ids': items}), status=200, mimetype='application/json')
#
#
# @app.route('/workitem/<int:item_id>', methods=["DELETE"])
# def delete_item(item_id):
#     cursor = connect()
#     cursor.execute("DELETE FROM pending_application WHERE id=%(id)s",
#                    {"id": item_id})
#     rows = cursor.rowcount
#     complete(cursor)
#     if rows == 0:
#         return Response(status=404)
#     else:
#         return Response(status=204)
#
#
# @app.route('/lodge_manual', methods=['POST'])
# def lodge_manual():
#     if request.headers['Content-Type'] != "application/json":
#         return Response(status=415)
#
#     data = request.get_json(force=True)
#
#     print(json.dumps(data))
#     if 'application_type' not in data or 'date' not in data or 'debtor_name' not in data:
#         return Response(status=400)
#
#     forenames = data['debtor_name']['forenames']
#     name_str = ''
#     for item in forenames:
#         name_str += '%s ' % item.strip()
#
#     name_str.strip()
#
#     status = "new"
#     assigned = ""
#     work_type = "bank_regn"
#
#     try:
#         connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
#             app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
#             app.config['DATABASE_PASSWORD']))
#
#     except psycopg2.OperationalError as exception:
#         return Response("Failed to connect to database: {}".format(exception), status=500)
#
#     try:
#         cursor = connection.cursor()
#         cursor.execute("INSERT INTO pending_application (application_data, date_received, "
#                        "application_type, forenames, surname, status, assigned_to, work_type) " +
#                        "VALUES (%(json)s, %(date)s, %(type)s, %(forenames)s, %(surname)s, "
#                        "%(status)s, %(assigned)s, %(work_type)s) "
#                        "RETURNING id", {"json": json.dumps(data), "date": data['date'],
#                                         "type": data['application_type'], "forenames": name_str,
#                                         "surname": data['debtor_name']['surname'],
#                                         "status": status, "assigned": assigned, "work_type": work_type})
#         appn_id = cursor.fetchone()[0]
#     except psycopg2.OperationalError as exception:
#         return Response("Failed to insert to database: {}".format(exception), status=500)
#
#     connection.commit()
#     cursor.close()
#     connection.close()
#     return Response(json.dumps({'id': appn_id}), status=200, mimetype='application/json')
#
#
# @app.route('/search/<int:appn_id>', methods=["GET"])
# def get(appn_id):
#     try:
#         connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
#             app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
#             app.config['DATABASE_PASSWORD']))
#     except psycopg2.OperationalError as exception:
#         print(exception)
#         return Response("Failed to connect to database", status=500)
#
#     try:
#         cursor = connection.cursor()
#         cursor.execute("SELECT application_data FROM pending_application WHERE id=%(id)s", {"id": appn_id})
#     except psycopg2.OperationalError as exception:
#         print(exception)
#         return Response("Failed to select from database", status=500)
#
#     rows = cursor.fetchall()
#     if len(rows) == 0:
#         return Response(status=404)
#
#     data = json.dumps(rows[0][0], ensure_ascii=False)
#
#     cursor.close()
#     connection.close()
#
#     return Response(data, status=200, mimetype='application/json')
#
#
# @app.route('/search_by_name', methods=["POST"])
# def get_by_name():
#     try:
#         data = (request.get_json(force=True))
#         forenames = data['forenames']
#         surname = data['surname']
#
#         connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
#             app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
#             app.config['DATABASE_PASSWORD']))
#     except psycopg2.OperationalError as exception:
#         print(exception)
#         return Response("Failed to connect to database", status=500)
#
#     try:
#         cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         cursor.execute("SELECT application_data FROM pending_application "
#                        "WHERE trim(both ' ' from UPPER(forenames))=%(forenames)s AND UPPER(surname)=%(surname)s",
#                        {"forenames": forenames.upper(), "surname": surname.upper()})
#
#     except psycopg2.OperationalError as exception:
#         print(exception)
#         return Response("Failed to select from database", status=500)
#
#     rows = cursor.fetchall()
#
#     if len(rows) == 0:
#         return Response(status=404)
#     applications = []
#     for row in rows:
#         applications.append(row['application_data'])
#
#     data = json.dumps(applications, ensure_ascii=False)
#
#     cursor.close()
#     connection.close()
#
#     return Response(data, status=200, mimetype='application/json')
#
#

#
#
# @app.route('/work_list/<list_type>', methods=["GET"])
# def get_work_list(list_type):
#
#     if list_type not in valid_types:
#         return Response("Error: '" + list_type + "' is not one of the accepted work list types", status=400)
#
#     bank_regn_type = ''
#     if list_type == 'pab':
#         bank_regn_type = 'PA(B)'
#     elif list_type == 'wob':
#         bank_regn_type = 'WO(B)'
#
#     try:
#         connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
#             app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
#             app.config['DATABASE_PASSWORD']))
#     except psycopg2.OperationalError as exception:
#         logging.error(exception)
#         return Response("Failed to connect to database", status=500)
#
#     try:
#         cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         if list_type == 'all':
#             cursor.execute("SELECT id, date_received, application_type, status, work_type, assigned_to "
#                            "FROM pending_application order by date_received desc")
#         elif bank_regn_type != '':
#             cursor.execute("SELECT id, date_received, application_type, status, work_type, assigned_to "
#                            "FROM pending_application "
#                            "WHERE application_type=%(bank_regn_type)s order by date_received desc",
#                            {"bank_regn_type": bank_regn_type})
#         else:
#             cursor.execute("SELECT id, date_received, application_type, status, work_type, assigned_to "
#                            "FROM pending_application "
#                            "WHERE work_type=%(list_type)s order by date_received", {"list_type": list_type})
#
#     except psycopg2.OperationalError as exception:
#         logging.error(exception)
#         return Response("Failed to select from database", status=500)
#
#     rows = cursor.fetchall()
#     applications = []
#
#     for row in rows:
#         result = {
#             "appn_id": row['id'],
#             "date_received": str(row['date_received']),
#             "application_type": row['application_type'],
#             "status": row['status'],
#             "work_type": row['work_type'],
#             "assigned_to": row['assigned_to'],
#         }
#         applications.append(result)
#
#     data = json.dumps(applications, ensure_ascii=False)
#
#     cursor.close()
#     connection.close()
#
#     return Response(data, status=200, mimetype='application/json')
