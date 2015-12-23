from application import app
from flask import Response, request, send_from_directory, send_file,  url_for
from flask.ext.cors import cross_origin
import json
import logging
import psycopg2
import psycopg2.extras
import requests
from application.applications import insert_new_application, get_application_list, get_application_by_id, \
    update_application_details, bulk_insert_applications, complete_application, delete_application, \
    amend_application
import io
from application.ocr import recognise
import base64

valid_types = ['all', 'pab', 'wob',
               'bank', 'bank_regn', 'bank_amend', 'bank_rect', 'bank_with', 'bank_stored',
               'lc_regn', 'amend', 'cancel', 'prt_search', 'search', 'oc']


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

    # action = 'store'
    # if 'action' in request.args:
    #     action = request.args['action']

    data = request.get_json(force=True)

    if 'application_type' not in data or 'date_received' not in data \
            or "work_type" not in data or 'application_data' not in data:
        return Response(status=400)
    cursor = connect()
    item_id = insert_new_application(cursor, data)

    # if action == 'store':
    #     item_id = insert_new_application(cursor, data)
    # elif action == 'complete':
    #     complete_application(cursor, data)
    # else:
    #     return Response("Invalid action", status=400)

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
    action = 'store'
    if 'action' in request.args:
        action = request.args['action']

    data = request.get_json(force=True)
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)

    if action == 'store':
        update_application_details(cursor, appn_id, data)
        appn = get_application_by_id(cursor, appn_id)
    elif action == 'complete':
        appn = complete_application(cursor, appn_id, data)
    elif action == 'amend':
        appn = amend_application(cursor, appn_id, data)
    else:
        return Response("Invalid action", status=400)

    complete(cursor)
    return Response(json.dumps(appn), status=200)

# ============ FORMS ==============


@app.route('/forms/<size>', methods=["POST"])
def create_documents(size):
    # create document, add first page image and return document id
    content_type = request.headers['Content-Type']
    if content_type != "image/tiff" and content_type != 'image/jpeg' and content_type != 'application/pdf':
        logging.error('Content-Type is not a valid image format')
        return Response(status=415)

    # ocr form to detect application type
    image_as_bytes = io.BytesIO(request.data)
    form_type = recognise(image_as_bytes)

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute('select max(document_id)+1 from documents')

    next_doc_id = cursor.fetchone()

    if next_doc_id[0] is None:
        next_doc_id[0] = 1

    cursor.execute("insert into documents (document_id, form_type, content_type, page, size, image) "
                   "values ( %(document_id)s, %(form_type)s, %(content_type)s, %(page)s, %(size)s, "
                   "%(image)s ) returning document_id",
                   {
                       "document_id": next_doc_id[0],
                       "form_type": form_type,
                       "content_type": content_type,
                       "page": "1",
                       "size": size,
                       "image": psycopg2.Binary(request.data)
                   })
    res = cursor.fetchone()

    document_id = res[0]
    complete(cursor)

    return Response(json.dumps({"id": document_id, "form_type": form_type}), status=201, mimetype='application/json')


@app.route('/forms/<int:doc_id>/<size>', methods=['POST'])
def append_image(doc_id, size):
    # append new page image to the document
    content_type = request.headers['Content-Type']
    if content_type != "image/tiff" and content_type != 'image/jpeg' and content_type != 'application/pdf':
        logging.error('Content-Type is not a valid image format')
        return Response(status=415)

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute('select max(page)+1 from documents where document_id=%(doc_id)s', {"doc_id": doc_id})

    next_page_no = cursor.fetchone()
    if next_page_no[0] is None:
        return Response(status=404)

    cursor.execute("insert into documents (document_id, content_type, page, size, image) "
                   "values ( %(document_id)s, %(content_type)s, %(page)s, %(size)s, %(image)s )",
                   {
                       "document_id": doc_id,
                       "content_type": content_type,
                       "page": next_page_no[0],
                       "size": size,
                       "image": psycopg2.Binary(request.data)
                   })
    rowcount = cursor.rowcount
    complete(cursor)

    if rowcount == 0:
        return Response(status=404)

    return Response(status=201)


@app.route('/forms/<int:doc_id>/<int:page_no>/<size>', methods=["PUT"])
def change_image(doc_id, page_no, size):
    # replace an existing page image
    content_type = request.headers['Content-Type']
    if content_type != "image/tiff" and content_type != 'image/jpeg' and content_type != 'application/pdf':
        logging.error('Content-Type is not a valid image format')
        return Response(status=415)

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)

    if page_no == 1:
        # ocr form to detect application type
        bytes = io.BytesIO(request.data)
        form_type = recognise(bytes)
        # TODO: if form_type is different to the original type, need to consider updating any page 2,3 etc...
    else:
        cursor.execute('select form_type from documents where document_id=%(doc_id)s and page = 1', {"doc_id": doc_id})

        row = cursor.fetchone()
        if row is None:
            return Response(status=404)
        form_type = row['form_type']

    cursor.execute("update documents set form_type=%(form_type)s, content_type=%(content_type)s, "
                   "size=%(size)s , image=%(image)s where document_id=%(doc_id)s and page=%(page)s",
                   {
                       "doc_id": doc_id,
                       "form_type": form_type,
                       "content_type": content_type,
                       "page": page_no,
                       "size": size,
                       "image": psycopg2.Binary(request.data)
                   })
    rowcount = cursor.rowcount
    complete(cursor)

    if rowcount == 0:
        return Response(status=404)

    return Response(status=200)


@app.route('/forms/<int:doc_id>/<int:page_no>', methods=["DELETE"])
def delete_image(doc_id, page_no):
    cursor = connect()
    cursor.execute("delete from documents where document_id=%(doc_id)s and page=%(page)s",
                   {"doc_id": doc_id, "page": page_no})

    rowcount = cursor.rowcount
    complete(cursor)

    if rowcount == 0:
        return Response(status=404)
    return Response(status=200)


@app.route('/forms/<int:doc_id>', methods=["GET"])
def get_document_info(doc_id):
    # retrieve page info for a document

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("select page from documents where document_id = %(id)s", {"id": doc_id})
    rows = cursor.fetchall()
    complete(cursor)

    data = []
    if len(rows) == 0:
        data = None
    else:
        for row in rows:
            data.append(row['page'])

    return Response(json.dumps({"images": data}), status=200, mimetype='application/json')


@app.route('/forms/<int:doc_id>/<int:page_no>', methods=["GET"])
def get_image(doc_id, page_no):
    # retrieve byte[] for a page

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("select content_type, (image) from documents where document_id=%(doc_id)s and page=%(page)s",
                   {"doc_id": doc_id, "page": page_no})

    rows = cursor.fetchall()
    complete(cursor)

    if len(rows) == 0:
        return Response(status=404)

    row = rows[0]

    return Response(row['image'], status=200, mimetype=row['content_type'])


# =========== OTHER ROUTES ==============
@app.route('/keyholders/<key_number>', methods=['GET'])
@cross_origin()
def get_keyholder(key_number):
    uri = app.config['LEGACY_ADAPTER_URI'] + '/keyholders/' + key_number
    response = requests.get(uri)
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/counties', methods=['GET'])
@cross_origin()
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

@app.route('/forms', methods=['DELETE'])
def delete():
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)
    cursor = connect()
    cursor.execute("DELETE FROM documents")
    complete(cursor)
    return Response(status=200, mimetype='application/json')


@app.route('/forms/bulk', methods=['POST'])
def bulk_load():
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    data = request.get_json(force=True)
    cursor = connect()
    for item in data:
        cursor.execute("INSERT INTO documents (id, metadata, image_paths) "
                       "VALUES ( %(id)s, %(meta)s, %(image)s )",
                       {
                           'id': item['id'],
                           'meta': json.dumps(item['metadata']),
                           'image': json.dumps(item['image_paths'])
                       })
    cursor.execute("SELECT setval('documents_id_seq', (SELECT MAX(id) FROM documents)+1);")

    complete(cursor)
    return Response(status=200, mimetype='application/json')


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
