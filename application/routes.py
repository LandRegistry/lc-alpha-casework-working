from application import app
from flask import Response, request
import json
import psycopg2


@app.route('/', methods=["GET"])
def index():
    return Response(status=200)


@app.route('/lodge_manual', methods=['POST'])
def lodge_manual():
    if request.headers['Content-Type'] != "application/json":
        return Response(status=415)

    data = request.get_json(force=True)
    if 'application_type' not in data or 'date' not in data:
        return Response(status=400)

    try:
        connection = psycopg2.connect("dbname='{}' user='{}' host='{}' password='{}'".format(
            app.config['DATABASE_NAME'], app.config['DATABASE_USER'], app.config['DATABASE_HOST'],
            app.config['DATABASE_PASSWORD']))
    except Exception as error:
        return Response("Failed to connect to database: {}".format(error), status=500)

    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO pending_application (application_data, date_received, application_type) " +
                       "VALUES (%(json)s, %(date)s, %(type)s) RETURNING id", {"json": json.dumps(data), "date": data['date'],
                                                                              "type": data['application_type']})
        id = cursor.fetchone()[0]
    except Exception as error:
        return Response("Failed to insert to database: {}".format(error), status=500)

    connection.commit()
    cursor.close()
    connection.close()
    return Response(json.dumps({'id': id}), status=202, mimetype='application/json')
