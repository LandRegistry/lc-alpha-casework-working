from application import app
from flask import Response, request
import json
import logging
import psycopg2
import psycopg2.extras


valid_types = ['all', 'pab', 'wob', 'bank_regn', 'lc_regn', 'amend', 'cancel', 'prt_search', 'search', 'oc']


@app.route('/', methods=["GET"])
def index():
    return Response(status=200)


@app.route('/workitem', methods=["POST"])
def manual():
    if request.headers['Content-Type'] != "application/json":
        return Response(status=415)

    data = request.get_json(force=True)
    if 'application_type' not in data \
            or 'date' not in data \
            or "work_type" not in data \
            or 'document_id' not in data:
        return Response(status=400)

    app_data = {
        "document_id": data['document_id']
    }

    cursor = connect()
    cursor.execute("INSERT INTO pending_application (application_data, date_received, "
                   "application_type, status, work_type) " +
                   "VALUES (%(json)s, %(date)s, %(type)s, %(status)s, %(work_type)s) "
                   "RETURNING id", {"json": json.dumps(app_data), "date": data['date'],
                                    "type": data['application_type'],
                                    "status": "new", "work_type": data['work_type']})
    item_id = cursor.fetchone()[0]
    complete(cursor)
    return Response(json.dumps({'id': item_id}), status=200, mimetype='application/json')


@app.route('/workitem/<int:item_id>', methods=["DELETE"])
def delete_item(item_id):
    cursor = connect()
    cursor.execute("DELETE FROM pending_application WHERE id=%(id)s",
                   {"id": item_id})
    rows = cursor.rowcount
    complete(cursor)
    if rows == 0:
        return Response(status=404)
    else:
        return Response(status=204)


@app.route('/lodge_manual', methods=['POST'])
def lodge_manual():
    if request.headers['Content-Type'] != "application/json":
        return Response(status=415)

    data = request.get_json(force=True)

    print(json.dumps(data))
    if 'application_type' not in data or 'date' not in data or 'debtor_name' not in data:
        return Response(status=400)

    forenames = data['debtor_name']['forenames']
    name_str = ''
    for item in forenames:
        name_str += '%s ' % item.strip()

    name_str.strip()

    status = "new"
    assigned = ""
    work_type = "bank_regn"

    try:
        connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
            app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
            app.config['DATABASE_PASSWORD']))

    except Exception as error:
        return Response("Failed to connect to database: {}".format(error), status=500)

    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO pending_application (application_data, date_received, "
                       "application_type, forenames, surname, status, assigned_to, work_type) " +
                       "VALUES (%(json)s, %(date)s, %(type)s, %(forenames)s, %(surname)s, "
                       "%(status)s, %(assigned)s, %(work_type)s) "
                       "RETURNING id", {"json": json.dumps(data), "date": data['date'],
                                        "type": data['application_type'], "forenames": name_str,
                                        "surname": data['debtor_name']['surname'],
                                        "status": status, "assigned": assigned, "work_type": work_type})
        id = cursor.fetchone()[0]
    except Exception as error:
        return Response("Failed to insert to database: {}".format(error), status=500)

    connection.commit()
    cursor.close()
    connection.close()
    return Response(json.dumps({'id': id}), status=200, mimetype='application/json')

@app.route('/search/<int:id>', methods=["GET"])
def get(id):
    try:
        connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
            app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
            app.config['DATABASE_PASSWORD']))
    except Exception as error:
        print(error)
        return Response("Failed to connect to database", status=500)

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT application_data FROM pending_application WHERE id=%(id)s", {"id": id})
    except Exception as error:
        print(error)
        return Response("Failed to select from database", status=500)

    rows = cursor.fetchall()
    if len(rows) == 0:
        return Response(status=404)

    data = json.dumps(rows[0][0], ensure_ascii=False)

    cursor.close()
    connection.close()

    return Response(data, status=200, mimetype='application/json')


@app.route('/search_by_name', methods=["POST"])
def get_by_name():
    try:
        data = (request.get_json(force=True))
        forenames = data['forenames']
        surname = data['surname']

        connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
            app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
            app.config['DATABASE_PASSWORD']))
    except Exception as error:
        print(error)
        return Response("Failed to connect to database", status=500)

    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT application_data FROM pending_application "
                       "WHERE trim(both ' ' from UPPER(forenames))=%(forenames)s AND UPPER(surname)=%(surname)s",
                       {"forenames": forenames.upper(), "surname": surname.upper()})

    except Exception as error:
        print(error)
        return Response("Failed to select from database", status=500)

    rows = cursor.fetchall()

    if len(rows) == 0:
        return Response(status=404)
    applications = []
    for n in rows:
        applications.append(n['application_data'])

    data = json.dumps(applications, ensure_ascii=False)

    cursor.close()
    connection.close()

    return Response(data, status=200, mimetype='application/json')


def connect(cursor_factory=None):
    connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
        app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
        app.config['DATABASE_PASSWORD']))
    return connection.cursor(cursor_factory=cursor_factory)


def complete(cursor):
    cursor.connection.commit()
    cursor.close()
    cursor.connection.close()


@app.route('/error', methods=["GET", "POST"])
def error():
    if request.method == "GET":

        data = {}
        return Response(json.dumps(data), status=200)
    elif request.method == "POST":
        data = (request.get_json(force=True))
        cursor = connect()
        cursor.execute("INSERT INTO errors (date_logged, source, data) " +
                       "VALUES (%(date)s, %(source)s, %(data)s ) RETURNING id",
                       {
                           "date": data["date"],
                           "source": data["source"],
                           "data": json.dumps(data["data"])
                       })
        new_id = cursor.fetchone()[0]
        complete(cursor)
        return Response(json.dumps({"id": new_id}), status=201)


@app.route('/errors', methods=["GET"])
def get_errors():
    cursor = connect(psycopg2.extras.DictCursor)
    cursor.execute("SELECT date_logged, source, data FROM ERRORS")
    rows = cursor.fetchall()

    result = []
    for row in rows:
        result.append({
            "date": str(row["date_logged"]),
            "source": row["source"],
            "data": row["data"]
        })

    complete(cursor)
    return Response(json.dumps(result), status=200)


@app.route('/work_list/<list_type>', methods=["GET"])
def get_work_list(list_type):

    if list_type not in valid_types:
        return Response("Error: '" + list_type + "' is not one of the accepted work list types", status=400)

    bank_regn_type = ''
    if list_type == 'pab':
        bank_regn_type = 'PA(B)'
    elif list_type == 'wob':
        bank_regn_type = 'WO(B)'

    try:

        connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
            app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
            app.config['DATABASE_PASSWORD']))
    except Exception as error:
        logging.error(error)
        return Response("Failed to connect to database", status=500)

    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if list_type == 'all':
            cursor.execute("SELECT id, date_received, application_type, status, work_type, assigned_to "
                           "FROM pending_application order by date_received")
        elif bank_regn_type != '':
            cursor.execute("SELECT id, date_received, application_type, status, work_type, assigned_to "
                           "FROM pending_application "
                           "WHERE application_type=%(bank_regn_type)s order by date_received",
                           {"bank_regn_type": bank_regn_type})
        else:
            cursor.execute("SELECT id, date_received, application_type, status, work_type, assigned_to "
                           "FROM pending_application "
                           "WHERE work_type=%(list_type)s order by date_received", {"list_type": list_type})

    except Exception as error:
        logging.error(error)
        return Response("Failed to select from database", status=500)

    rows = cursor.fetchall()

    applications = []

    if len(rows) > 0:

        for row in rows:
            print(row)
            result = {
                "appn_id": row['id'],
                "date_received": str(row['date_received']),
                "application_type": row['application_type'],
                "status": row['status'],
                "work_type": row['work_type'],
                "assigned_to": row['assigned_to'],
                }
            applications.append(result)

    data = json.dumps(applications, ensure_ascii=False)

    cursor.close()
    connection.close()

    return Response(data, status=200, mimetype='application/json')

