from application import app
from flask import Response, request
import json
import psycopg2
import psycopg2.extras


@app.route('/', methods=["GET"])
def index():
    return Response(status=200)


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

    try:
        connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
            app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
            app.config['DATABASE_PASSWORD']))
    except Exception as error:
        return Response("Failed to connect to database: {}".format(error), status=500)

    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO pending_application (application_data, date_received, "
                       "application_type, forenames, surname) " +
                       "VALUES (%(json)s, %(date)s, %(type)s, %(forenames)s, %(surname)s) "
                       "RETURNING id", {"json": json.dumps(data), "date": data['date'],
                                        "type": data['application_type'], "forenames": name_str,
                                        "surname": data['debtor_name']['surname']})
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
    print(type(data))
    print(data)

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


    return Response(data, status=200, mimetype='application/json')
