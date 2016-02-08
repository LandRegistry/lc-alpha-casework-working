from application import app
from flask import Response, request, send_from_directory, send_file,  url_for, g
from flask.ext.cors import cross_origin
import json
import logging
import psycopg2
import psycopg2.extras
import requests
from datetime import datetime
from application.applications import insert_new_application, get_application_list, get_application_by_id, \
    update_application_details, bulk_insert_applications, complete_application, delete_application, \
    amend_application, set_lock_ind, clear_lock_ind, insert_result_row
from application.documents import get_document, get_image
from application.error import raise_error
import io
from application.ocr import recognise
import traceback
from PIL import Image, ImageDraw, ImageFont, TiffImagePlugin
import os


valid_types = ['all', 'pab', 'wob',
               'bank', 'bank_regn', 'bank_amend', 'bank_rect', 'bank_with', 'bank_stored',
               'lc_regn', 'lc', 'lc_pn', 'lc_rect', 'lc_renewal', 'lc_stored',
               'amend', 'cancel', 'canc', 'cancel_part', 'cancel_stored',
               'prt_search', 'search', 'search_full', 'search_bank', 'oc']


@app.route('/', methods=["GET"])
def index():
    return Response(status=200)


@app.errorhandler(Exception)
def error_handler(err):
    logging.error('Unhandled exception: ' + str(err))
    call_stack = traceback.format_exc()

    lines = call_stack.split("\n")
    for line in lines:
        logging.error(line)

    error = {
        "type": "F",
        "message": str(err),
        "stack": call_stack
    }
    raise_error(error)
    return Response(json.dumps(error), status=500)


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


@app.before_request
def before_request():
    logging.info("BEGIN %s %s [%s] (%s)",
                 request.method, request.url, request.remote_addr, request.__hash__())


@app.after_request
def after_request(response):
    logging.info('END %s %s [%s] (%s) -- %s',
                 request.method, request.url, request.remote_addr, request.__hash__(),
                 response.status)
    return response


# ============ APPLICATIONS ==============
@app.route('/applications', methods=['GET'])
def get_applications():
    list_type = 'all'
    if 'type' in request.args:
        list_type = request.args['type']
    if list_type not in valid_types:
        return Response("Error: '" + list_type + "' is not one of the accepted work list types", status=400)

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        applications = get_application_list(cursor, list_type)
    finally:
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
    if data['application_data'] == "":
        data['application_data'] = {"document_id": data['document_id']} #to get incoming scanned docs to display

    cursor = connect()
    try:
        item_id = insert_new_application(cursor, data)
    finally:
        complete(cursor)
    return Response(json.dumps({'id': item_id}), status=200, mimetype='application/json')

@app.route('/applications/<appn_id>/lock', methods=['POST'])
def lock_application(appn_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        locked = set_lock_ind(cursor, appn_id)
        if locked is None:
            # Selected application already locked or no longer on work list
            return Response(status=404)
        else:
            return Response(status=200)
    finally:
        complete(cursor)


@app.route('/applications/<appn_id>/lock', methods=['DELETE'])
def unlock_application(appn_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        clear_lock_ind(cursor, appn_id)
    finally:
        complete(cursor)
    return Response(status=200)


@app.route('/applications/<appn_id>', methods=['GET'])
def get_application(appn_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)

    # locked = lock_application(cursor, appn_id)
    # if locked is None:
    #     # Selected application already locked or no longer on work list
    #     complete(cursor)
    #     return Response(status=404)
    # else:
    try:
        appn = get_application_by_id(cursor, appn_id)
    finally:
        complete(cursor)

    return Response(json.dumps(appn), status=200, mimetype='application/json')


@app.route('/applications/<appn_id>', methods=['DELETE'])
def remove_application(appn_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        rows = delete_application(cursor, appn_id)
    finally:
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

    try:
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
    except:
        rollback(cursor)
        raise


    return Response(json.dumps(appn), status=200)

# ============ FORMS ==============


@app.route('/forms/<size>', methods=["POST"])
def create_documents(size):
    # create document, add first page image and return document id
    content_type = request.headers['Content-Type']
    if content_type != "image/tiff" and content_type != 'image/jpeg' and content_type != 'application/pdf':
        logging.error('Content-Type is not a valid image format')
        return Response(status=415)

    if 'type' in request.args:
        logging.info("Form type specified")
        form_type = request.args['type']
    else:
        # ocr form to detect application type
        image_as_bytes = io.BytesIO(request.data)
        form_type = recognise(image_as_bytes)

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
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
    except:
        rollback(cursor)
        raise

    return Response(json.dumps({"id": document_id, "form_type": form_type}), status=201, mimetype='application/json')


@app.route('/forms/<int:doc_id>/<size>', methods=['POST'])
def append_image(doc_id, size):
    # append new page image to the document
    content_type = request.headers['Content-Type']
    if content_type != "image/tiff" and content_type != 'image/jpeg' and content_type != 'application/pdf':
        logging.error('Content-Type is not a valid image format')
        return Response(status=415)

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
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
    except:
        rollback(cursor)
        raise

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
    try:
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
    except:
        rollback(cursor)
        raise

    if rowcount == 0:
        return Response(status=404)

    return Response(status=200)


@app.route('/forms/<int:doc_id>/<int:page_no>', methods=["DELETE"])
def delete_image(doc_id, page_no):
    cursor = connect()
    try:
        cursor.execute("delete from documents where document_id=%(doc_id)s and page=%(page)s",
                       {"doc_id": doc_id, "page": page_no})

        rowcount = cursor.rowcount
        complete(cursor)
    except:
        rollback(cursor)
        raise

    if rowcount == 0:
        return Response(status=404)
    return Response(status=200)


@app.route('/forms/<int:doc_id>', methods=["GET"])
def get_document_info(doc_id):
    # retrieve page info for a document

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        data = get_document(cursor, doc_id)
    finally:
        complete(cursor)
    return Response(json.dumps({"images": data}), status=200, mimetype='application/json')


@app.route('/forms/<int:doc_id>/<int:page_no>', methods=["GET"])
def get_form_image(doc_id, page_no):
    # retrieve byte[] for a page

    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        data = get_image(cursor, doc_id, page_no)
    finally:
        complete(cursor)
    if data is None:
        return Response(status=404)

    return Response(data['bytes'], status=200, mimetype=data['mimetype'])


# =========== OTHER ROUTES ==============
@app.route('/keyholders/<key_number>', methods=['GET'])
@cross_origin()
def get_keyholder(key_number):
    uri = app.config['LEGACY_ADAPTER_URI'] + '/keyholders/' + key_number
    response = requests.get(uri)
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/counties/', methods=['GET'])
@cross_origin()
def get_counties_list():
    params = ""
    if 'welsh' in request.args:
        if request.args['welsh'] == "yes":
            params = "?welsh=yes"
    else:
        params = "?welsh=no"

    url = app.config['LAND_CHARGES_URI'] + '/counties' + params
    data = requests.get(url)
    return Response(data, status=200, mimetype='application/json')


@app.route('/county/<county_name>', methods=['GET'])
@cross_origin()
def get_translated_county(county_name):

    url = app.config['LAND_CHARGES_URI'] + '/county/' + county_name
    data = requests.get(url)
    return Response(data, status=200, mimetype='application/json')


@app.route('/complex_names/<name>', methods=['GET'])
@cross_origin()
def get_complex_names(name):
    uri = app.config['LEGACY_ADAPTER_URI'] + '/complex_names/' + name
    response = requests.get(uri)
    logging.info('GET {} -- {}'.format(uri, response))
    return Response(response.text, status=200, mimetype='application/json')


@app.route('/complex_names/search', methods=['POST'])
def get_complex_names_post():
    data = request.get_json(force=True)
    uri = app.config['LEGACY_ADAPTER_URI'] + '/complex_names/search'
    response = requests.post(uri, data=json.dumps(data), headers={'Content-Type': 'application/json'})
    logging.info('POST {} -- {}'.format(uri, response))
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/searches', methods=['POST'])
def post_search():
    data = request.get_json(force=True)

    logging.debug(json.dumps(data))

    today = datetime.now().strftime('%Y-%m-%d')
    date_uri = app.config['LEGACY_ADAPTER_URI'] + '/dates/' + today
    date_response = requests.get(date_uri)

    if date_response.status_code != 200:
        raise RuntimeError("Unexpected return from legacy_adapter/dates: " + str(date_response.status_code))

    date_info = date_response.json()
    data['expiry_date'] = date_info['search_expires']
    data['search_date'] = date_info['prev_working']

    uri = app.config['LAND_CHARGES_URI'] + '/searches'
    response = requests.post(uri, data=json.dumps(data), headers={'Content-Type': 'application/json'})
    logging.info('POST {} -- {}'.format(uri, response.text))

    # store result
    response_data = response.json()

    cursor = connect()
    for id in response_data:
        uri = app.config['LAND_CHARGES_URI'] + '/search_type/'+str(id)
        response = requests.get(uri)
        resp_data = response.json()
        res_type = resp_data['search_type']
        insert_result_row(cursor, id, res_type)
    complete(cursor)

    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/office_copy', methods=['GET'])
def get_office_copy():
    class_of_charge = request.args['class']
    reg_no = request.args['reg_no']
    date = request.args['date']

    uri = app.config['LAND_CHARGES_URI'] + '/office_copy' + '?class=' + class_of_charge + '&reg_no=' + reg_no + \
          '&date=' + date
    response = requests.get(uri, headers={'Content-Type': 'application/json'})
    logging.info('GET {} -- {}'.format(uri, response.text))
    size = (992, 1430)
    clWhite = (255, 255, 255)
    clBlack = (0, 0, 0)
    clGrey = (178, 178, 178)
    arial = 'arial.ttf'
    arialbold = 'arialbd.ttf'
    im = Image.new('RGB', size, clWhite)
    draw = ImageDraw.Draw(im)
    cursor_pos = 50
    draw_text(draw, (120, cursor_pos), 'Application for Registration of Petition in Bankruptcy', arialbold, 32, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'This is an official copy of the data provided by the Insolvency',
              arial, 28, clBlack)
    cursor_pos += 30
    draw_text(draw, (200, cursor_pos), 'Service to register a Pending Action in Bankruptcy', arial, 28, clBlack)
    cursor_pos += 80
    draw_text(draw, (100, cursor_pos), 'Particulars of Application:', arialbold, 22, clBlack)
    cursor_pos += 30
    draw.line((100,cursor_pos,(im.size[1]-300),cursor_pos),fill=0)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Reference: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Key Number: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Date: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (100, cursor_pos), 'Particulars of Debtor:', arialbold, 22, clBlack)
    cursor_pos += 30
    draw.line((100, cursor_pos,(im.size[1]-300),cursor_pos),fill=0)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Name: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Alternative Names: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Date of Birth: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Gender: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Trading Name: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Occupation: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Residence: ', arial, 22, clBlack)
    cursor_pos += 150
    draw_text(draw, (150, cursor_pos), 'Business Address: ', arial, 22, clBlack)
    cursor_pos += 50
    draw_text(draw, (150, cursor_pos), 'Investment Property: ', arial, 22, clBlack)
    cursor_pos = 1250
    left_pos = 50
    draw_text(draw, (left_pos, cursor_pos), 'Land Registry', arial, 12, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Land Charges Department', arial, 12, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Seaton Court', arial, 12, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), '2 William Prance Road', arial, 12, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Plymouth', arial, 12, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'PL6 5WS', arial, 12, clGrey)
    del draw
    image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'application/images')
    im.save(os.path.join(image_path, 'test.tiff'), 'tiff', resolution=120.0)
    im.save(os.path.join(image_path, 'test.pdf'), 'PDF', resolution=120.0)
    TiffImagePlugin.WRITE_LIBTIFF = True
    im.save(os.path.join(image_path, 'compressedtiff.tiff'), compression = "tiff_lzw", resolution=120.0)
    TiffImagePlugin.WRITE_LIBTIFF = False
    response = send_file(os.path.join(image_path, 'compressedtiff.tiff'), as_attachment=True, attachment_filename='mytiff.tiff')
    return response


def draw_text(canvas, text_pos, text, font_name, font_size, font_color):
    fonts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'application/static/fonts')
    fnt = ImageFont.truetype(os.path.join(fonts_path, font_name), font_size)
    canvas.text(text_pos, text, font_color, font=fnt )
    return "ok"

# ========= Dev Routes ==============

@app.route('/forms', methods=['DELETE'])
def delete():
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)
    cursor = connect()
    try:
        cursor.execute("DELETE FROM documents")
        complete(cursor)
    except:
        rollback(cursor)
        raise
    return Response(status=200, mimetype='application/json')


@app.route('/forms/bulk', methods=['POST'])
def bulk_load():
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    data = request.get_json(force=True)
    cursor = connect()
    try:
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
    except:
        rollback(cursor)
        raise
    return Response(status=200, mimetype='application/json')


@app.route('/applications', methods=['DELETE'])
def clear_applications():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    cursor = connect()
    try:
        cursor.execute("DELETE FROM pending_application")
        complete(cursor)
    except:
        rollback(cursor)
        raise
    return Response(status=200)


@app.route('/applications', methods=['PUT'])
def bulk_add_applications():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    data = request.get_json(force=True)
    cursor = connect()
    try:
        ids = bulk_insert_applications(cursor, data)
        complete(cursor)
    except:
        rollback(cursor)
        raise
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
    try:
        for item in json_data:
            if 'cym' not in item:
                item['cym'] = None

            cursor.execute('INSERT INTO COUNTIES (name, welsh_name) VALUES (%(e)s, %(c)s)',
                           {
                               'e': item['eng'], 'c': item['cym']
                           })
        complete(cursor)
    except:
        rollback(cursor)
        raise
    return Response(status=200)


@app.route('/counties', methods=['DELETE'])
def delete_counties():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    cursor = connect()
    try:
        cursor.execute('DELETE FROM COUNTIES')
        complete(cursor)
    except:
        rollback(cursor)
        raise
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


def rollback(cursor):
    cursor.connection.rollback()
    cursor.close()
    cursor.connection.close()


# clear the results table
@app.route('/results', methods=['DELETE'])
def delete_results():  # pragma: no cover
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)
    cursor = connect()
    try:
        cursor.execute('DELETE FROM RESULTS')
        complete(cursor)
    except:
        rollback(cursor)
        raise

    return Response(status=200)


# for testing purposes insert into the results table
@app.route('/results', methods=['POST'])
def load_results():
    logging.debug("Calling load results")
    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)

    if request.headers['Content-Type'] != "application/json":
        logging.error('Content-Type is not JSON')
        return Response(status=415)
    json_data = request.get_json(force=True)
    # go and get some genuine landcharges.request.ids to feed into the results table
    id_count = str(len(json_data))
    response = requests.get(app.config['LAND_CHARGES_URI'] + '/request_ids/' + id_count)
    id_list = json.loads(response.content.decode('utf-8'))
    if id_list is None:
        print("no ids retrieved from the land charges uri, run casework-api/data/setup.rb after reset-data")
        return Response(status=200)
    try:
        ctr = 0
        for item in json_data:
            insert_result(id_list[ctr]['request_id'],  item['res_type'])
            ctr += 1
    except:
        raise
    return Response(status=200)


# update the status of the result to show it has been printed.
@app.route('/results/<result_id>', methods=['POST'])
def set_result_status(result_id):
    cursor = connect()
    json_data = request.get_json(force=True)
    
    try:
        if 'print_status' in json_data:
            cursor.execute('UPDATE results set print_status = %(result_status)s WHERE id = %(result_id)s',
                           {
                               "result_status": json_data['print_status'],
                               "result_id": result_id
                           })
            complete(cursor)
    except:
        rollback(cursor)
        raise
    return Response(status=200)


# get details of the passed in result.id
@app.route('/results/<result_id>', methods=["GET"])
def get_result(result_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    job = None
    
    try:
        cursor.execute("SELECT id, request_id, res_type FROM results Where id = %(id)s", {'id': result_id})
        rows = cursor.fetchall()
        
        if len(rows) > 0:
            job = {
                'id': rows[0]['id'],
                'request_id': rows[0]['request_id'],
                'res_type': rows[0]['res_type']
            }        
    finally:
        complete(cursor)
    if job is None:
        return Response(status=404)
    return Response(json.dumps(job), status=200, mimetype='application/json')


# get details of all results the are ready for printing
@app.route('/results', methods=["GET"])
def get_results():
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT id, request_id, res_type " +
                       "FROM results Where print_status <> 'Y' ORDER BY res_type ")
        rows = cursor.fetchall()
        logging.debug("row count = " + str(len(rows)) )
        res_list = []
        rowcount = 1
        for row in rows:
            job = {
                'id': row['id'], 'request_id': row['request_id'], 'res_type': row['res_type']
            }
            rowcount += 1
            res_list.append(job)
    finally:
        complete(cursor)
    return Response(json.dumps(res_list), status=200, mimetype='application/json')


#insert a print job row on the result table
@app.route('/results/<request_id>/<result_type>', methods=["POST"])
def insert_result(request_id, result_type):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        insert_result_row(cursor, request_id, result_type)
        complete(cursor)
    except:
        rollback(cursor)
        raise
    return Response(status=200)