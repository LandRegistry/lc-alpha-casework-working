from application import app
from application.logformat import format_message
from flask import Response, request, send_from_directory, send_file,  url_for, g
import json
import logging
import psycopg2
import psycopg2.extras
import requests
from datetime import datetime
from application.applications import insert_new_application, get_application_list, get_application_by_id, \
    update_application_details, bulk_insert_applications, complete_application, delete_application, \
    amend_application, set_lock_ind, clear_lock_ind, insert_result_row, cancel_application, \
    get_registration_details, store_image_for_later, get_headers, correct_application, get_work_type, reclassify_appn
from application.documents import get_document, get_image, get_raw_image
from application.error import raise_error
import io
from io import BytesIO
from application.ocr import recognise
import traceback
from PIL import Image, ImageDraw, ImageFont, TiffImagePlugin
import os
from application.oc import create_document


valid_types = ['all', 'pab', 'wob',
               'bank', 'bank_regn', 'bank_amend', 'bank_rect', 'bank_with', 'bank_stored',
               'lc_regn', 'lc', 'lc_pn', 'lc_rect', 'lc_renewal', 'lc_stored',
               'amend', 'cancel', 'canc', 'cancel_part', 'cancel_stored',
               'prt_search', 'search', 'search_full', 'search_bank', 'oc', 'unknown']


@app.route('/', methods=["GET"])
def index():
    return Response(status=200)


@app.errorhandler(Exception)
def error_handler(err):
    logging.error(format_message('Unhandled exception: ' + str(err)))
    call_stack = traceback.format_exc()

    lines = call_stack.split("\n")
    for line in lines:
        logging.error(format_message(line))

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
    msg = "{} {} [{}]".format(request.method, request.url, request.remote_addr)
    logging.info(format_message(msg))
    pass


@app.after_request
def after_request(response):
    # logging.info('END %s %s [%s] (%s) -- %s',
    #              request.method, request.url, request.remote_addr, request.__hash__(),
    #              response.status)
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
        logging.debug('something is missing in request')
        return Response(status=400)
    if data['application_data'] == "":
        data['application_data'] = {"document_id": data['document_id']}  # to get incoming scanned docs to display

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
    # store fee info for later use. Quick fix because of data structure in rectifications
    if 'fee_details' in data:
        fee_ind = True
        fee_details = data['fee_details']
    else:
        fee_ind = False
        fee_details = {}

    try:
        if action == 'store':
            update_application_details(cursor, appn_id, data)
            appn = get_application_by_id(cursor, appn_id)
        elif action == 'complete':
            appn = complete_application(cursor, appn_id, data)
        elif action == 'amend' or action == 'rectify':
            appn = amend_application(cursor, appn_id, data)
        elif action == 'cancel':
            appn = cancel_application(cursor, appn_id, data)
            print("appn : ", str(appn))
        elif action == 'correction':
            appn = correct_application(cursor, data)
        else:
            return Response("Invalid action", status=400)
        # sort out the fee
        if fee_ind is True:
            if fee_details['type'] == 'dd':
                logging.debug("Direct debit fee selected" + json.dumps(fee_details))
                # build the fee details to pass to legacy_adapter
                build_fee_data(data, appn, fee_details, action)
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
            cursor.execute('select form_type from documents where document_id=%(doc_id)s and page = 1',
                           {"doc_id": doc_id})
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
        if 'raw' in request.args:
            data = get_raw_image(cursor, doc_id, page_no)
        else:
            data = get_image(cursor, doc_id, page_no)
    finally:
        complete(cursor)
    if data is None:
        return Response(status=404)

    return Response(data['bytes'], status=200, mimetype=data['mimetype'])


@app.route('/registered_forms/<date>/<reg_no>', methods=['PUT'])
def dev_put_reg_form(date, reg_no):

    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    data = request.get_json(force=True)
    store_image_for_later(cursor, data['id'], reg_no, date)
    complete(cursor)
    return Response(status=200)


@app.route('/registered_forms', methods=['DELETE'])
def remove_reg_forms():

    if not app.config['ALLOW_DEV_ROUTES']:
        return Response(status=403)
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('DELETE FROM registered_documents')
    complete(cursor)
    return Response(status=200)


@app.route('/registered_forms/<date>/<reg_no>', methods=['GET'])
def get_registered_forms(date, reg_no):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute('select doc_id from registered_documents '
                       'where number=%(no)s and date=%(date)s', {
                           'no': reg_no, 'date': date
                       })
        rows = cursor.fetchall()
        if len(rows) == 0:
            return Response(status=404)

        result = {
            'document_id': rows[0]['doc_id']
        }
        return Response(json.dumps(result), status=200, mimetype='application/json')
    finally:
        complete(cursor)


@app.route('/registered_forms/<date>/<reg_no>', methods=['DELETE'])
def delete_all_reg_forms(date, reg_no):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute('delete from registered_documents '
                       'where number=%(no)s and date=%(date)s', {
                           'no': reg_no, 'date': date
                       })
        return Response(status=200)

    # TODO: also remove form from documents table?
    finally:
        complete(cursor)


# =========== OTHER ROUTES ==============
@app.route('/keyholders/<key_number>', methods=['GET'])
def get_keyholder(key_number):
    uri = app.config['LEGACY_ADAPTER_URI'] + '/keyholders/' + key_number
    response = requests.get(uri, headers=get_headers())
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/counties', methods=['GET'])
def get_counties_list():
    params = ""
    if 'welsh' in request.args:
        if request.args['welsh'] == "yes":
            params = "?welsh=yes"
    else:
        params = "?welsh=no"

    url = app.config['LAND_CHARGES_URI'] + '/counties' + params
    data = requests.get(url, headers=get_headers())
    return Response(data, status=200, mimetype='application/json')


@app.route('/county/<county_name>', methods=['GET'])
def get_translated_county(county_name):

    url = app.config['LAND_CHARGES_URI'] + '/county/' + county_name
    data = requests.get(url, headers=get_headers())
    return Response(data, status=200, mimetype='application/json')


@app.route('/complex_names/<name>', methods=['GET'])
def get_complex_names(name):
    uri = app.config['LEGACY_ADAPTER_URI'] + '/complex_names/' + name
    response = requests.get(uri, headers=get_headers())
    logging.info('GET {} -- {}'.format(uri, response))
    return Response(response.text, status=200, mimetype='application/json')


@app.route('/complex_names/search', methods=['POST'])
def get_complex_names_post():
    data = request.get_json(force=True)
    uri = app.config['LEGACY_ADAPTER_URI'] + '/complex_names/search'
    response = requests.post(uri, data=json.dumps(data), headers=get_headers({'Content-Type': 'application/json'}))
    logging.info('POST {} -- {}'.format(uri, response))
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/complex_names/<name>/<number>', methods=['POST'])
def insert_complex_name(name, number):
    logging.debug("Complex insert")
    today = datetime.now().strftime('%Y-%m-%d')
    data = {"amend": " ",
            "date": today,
            "number": number,
            "source": " ",
            "uid": " ",  # TODO: what is this going to be?
            "name": name
            }
    uri = app.config['LEGACY_ADAPTER_URI'] + '/complex_names'
    response = requests.post(uri, data=json.dumps(data), headers=get_headers({'Content-Type': 'application/json'}))
    logging.info('POST {} -- {}'.format(uri, response))
    result = {'response': response.text}
    return Response(json.dumps(result), status=response.status_code, mimetype='application/json')


@app.route('/court_check/<court>/<ref>', methods=['GET'])
def court_ref_existence_check(court, ref):
    logging.debug("Court existence checking")

    url = app.config['LAND_CHARGES_URI'] + '/court_check/' + court + '/' + ref
    response = requests.get(url, headers=get_headers())
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/original', methods=['POST'])
def get__originals():
    data = request.get_json(force=True)
    logging.debug(json.dumps(data))

    date = data['date']
    number = data['number']
    url = app.config['LAND_CHARGES_URI'] + '/registrations/' + date + '/' + number
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        result = (json.loads(response.text))
    else:
        return Response(json.dumps(response.text), status=response.status_code, mimetype='application/json')

    return Response(json.dumps(result), status=response.status_code, mimetype='application/json')


@app.route('/searches', methods=['POST'])
def post_search():
    data = request.get_json(force=True)

    logging.debug(json.dumps(data))

    today = datetime.now().strftime('%Y-%m-%d')
    date_uri = app.config['LEGACY_ADAPTER_URI'] + '/dates/' + today
    date_response = requests.get(date_uri, headers=get_headers())

    if date_response.status_code != 200:
        raise RuntimeError("Unexpected return from legacy_adapter/dates: " + str(date_response.status_code))

    date_info = date_response.json()
    data['expiry_date'] = date_info['search_expires']
    data['search_date'] = date_info['prev_working']

    uri = app.config['LAND_CHARGES_URI'] + '/searches'
    response = requests.post(uri, data=json.dumps(data), headers=get_headers({'Content-Type': 'application/json'}))
    logging.info('POST {} -- {}'.format(uri, response.text))

    # store result
    response_data = response.json()
    logging.debug("search data returned" + json.dumps(response_data))
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # process fee info
        if data['fee_details']['type'] == 'dd':
            build_fee_data(data, response_data, data['fee_details'], 'search')
        store_image_for_later(cursor, data['document_id'], None, None, response_data[0])
        complete(cursor)
    except:
        rollback(cursor)
        raise

    cursor = connect()
    for req_id in response_data:
        uri = app.config['LAND_CHARGES_URI'] + '/search_type/' + str(req_id)
        response = requests.get(uri, headers=get_headers())
        resp_data = response.json()
        res_type = resp_data['search_type']
        insert_result_row(cursor, req_id, res_type)
    complete(cursor)
    return Response(response.text, status=response.status_code, mimetype='application/json')


@app.route('/office_copy', methods=['GET'])
def get_office_copy():
    class_of_charge = request.args['class']
    reg_no = request.args['reg_no']
    date = request.args['date']
    if 'pdf' in request.args:
        return_pdf = True
    else:
        return_pdf = False
    uri = app.config['LAND_CHARGES_URI'] + '/office_copy' + '?class=' + class_of_charge + '&reg_no=' + reg_no + \
        '&date=' + date
    response = requests.get(uri, headers=get_headers({'Content-Type': 'application/json'}))
    logging.info('GET {} -- {}'.format(uri, response.text))
    data = json.loads(response.text)
    size = (992, 1430)
    cl_white = (255, 255, 255)
    cl_black = (0, 0, 0)
    cl_grey = (178, 178, 178)
    arial = 'arial.ttf'
    arialbold = 'arialbd.ttf'
    fs_main = 28
    fs_sub = 24
    fs_sub_title = 20
    fs_text = 16
    fs_footer = 12

    im = Image.new('RGB', size, cl_white)
    draw = ImageDraw.Draw(im)
    cursor_pos = 50
    draw_text(draw, (140, cursor_pos), 'Application for Registration of Petition in Bankruptcy', arialbold, fs_main, 
              cl_black)
    cursor_pos += 50
    draw_text(draw, (170, cursor_pos), 'This is an official copy of the data provided by the Insolvency',
              arial, fs_sub, cl_black)
    cursor_pos += 30
    draw_text(draw, (210, cursor_pos), 'Service to register a Pending Action in Bankruptcy', arial, fs_sub, cl_black)
    cursor_pos += 80
    draw_text(draw, (100, cursor_pos), 'Particulars of Application:', arialbold, fs_sub_title, cl_black)
    cursor_pos += 30
    draw.line((100, cursor_pos, (im.size[1]-300), cursor_pos), fill=0)
    cursor_pos += 30
    label_pos = 150
    data_pos = 400
    draw_text(draw, (label_pos, cursor_pos), 'Reference: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['application_ref'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (label_pos, cursor_pos), 'Key Number: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['key_number'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (label_pos, cursor_pos), 'Date: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['application_date'], arial, fs_text, cl_black)
    cursor_pos += 50
    draw_text(draw, (100, cursor_pos), 'Particulars of Debtor:', arialbold, fs_sub_title, cl_black)

    cursor_pos += 30
    draw.line((100, cursor_pos, (im.size[1]-300), cursor_pos), fill=0)

    if 'debtor_names' in data:
        name_count = 1
        for debtor_name in data['debtor_names']:
            if name_count == 1:
                cursor_pos += 30
                draw_text(draw, (label_pos, cursor_pos), 'Name: ', arial, fs_text, cl_black)
            elif name_count == 2:
                cursor_pos += 30
                draw_text(draw, (label_pos, cursor_pos), 'Alternative Names: ', arial, fs_text, cl_black)
            else:
                cursor_pos += 25
            debtor_forenames = ""
            for forenames in debtor_name['forenames']:
                debtor_forenames += forenames + " "
            debtor_forenames = debtor_forenames.strip()
            draw_text(draw, (data_pos, cursor_pos), debtor_forenames + " " + debtor_name['surname'], arial,
                      fs_text, cl_black)
            name_count += 1
    # cursor_pos += 50
    # draw_text(draw, (label_pos, cursor_pos), 'Alternative Names: ', arial, 22, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Date of Birth: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['date_of_birth'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Gender: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['gender'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Trading Name: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['trading_name'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Occupation: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['occupation'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Residence: ', arial, fs_text, cl_black)
    if data['residence_withheld']:
        draw_text(draw, (data_pos, cursor_pos), "DEBTORS ADDRESS IS STATED TO BE UNKNOWN", arial, fs_text, cl_black)
    else:
        cursor_pos -= 40
        for address in data['residence']:
            cursor_pos += 40
            for address_line in address['address_lines']:
                draw_text(draw, (data_pos, cursor_pos), address_line, arial, fs_text, cl_black)
                cursor_pos += 25
            draw_text(draw, (data_pos, cursor_pos), address['county'], arial, fs_text, cl_black)
            cursor_pos += 25
            draw_text(draw, (data_pos, cursor_pos), address['postcode'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Business Address: ', arial, fs_text, cl_black)
    if 'business_address' in data:
        draw_text(draw, (data_pos, cursor_pos), data['business_address'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Investment Property: ', arial, fs_text, cl_black)
    if 'investment_property' in data:
        draw_text(draw, (data_pos, cursor_pos), data['investment_property'], arial, fs_text, cl_black)
    cursor_pos = 1250
    left_pos = 50
    draw_text(draw, (left_pos, cursor_pos), 'Land Registry', arial, fs_footer, cl_grey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Land Charges Department', arial, fs_footer, cl_grey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Seaton Court', arial, fs_footer, cl_grey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), '2 William Prance Road', arial, fs_footer, cl_grey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Plymouth', arial, fs_footer, cl_grey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'PL6 5WS', arial, fs_footer, cl_grey)
    del draw
    image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'application/images')
    file_name = 'officeopy_'+class_of_charge + '_' + reg_no + '_' + date
    if return_pdf:
        file_path = os.path.join(image_path, 'output.pdf')
        im.save(file_path, 'PDF', resolution=120.0)
        file_name += '.pdf'
    else:
        TiffImagePlugin.WRITE_LIBTIFF = True
        file_path = os.path.join(image_path, 'output.tiff')
        im.save(file_path, compression="tiff_lzw", resolution=120.0)
        TiffImagePlugin.WRITE_LIBTIFF = False
        file_name += '.tiff'

    with open(file_path, 'rb') as f:
        contents = f.read()
    response = send_file(BytesIO(contents), as_attachment=True, attachment_filename=file_name)
    os.remove(file_path)
    return response


def draw_text(canvas, text_pos, text, font_name, font_size, font_color):
    fonts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'application/static/fonts')
    fnt = ImageFont.truetype(os.path.join(fonts_path, font_name), font_size)
    canvas.text(text_pos, text, font_color, font=fnt)
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
    response = requests.get(app.config['LAND_CHARGES_URI'] + '/request_ids/' + id_count,
                            headers=get_headers())
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
        logging.debug("row count = " + str(len(rows)))
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


# insert a print job row on the result table
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


@app.route('/b2b_forms', methods=['POST'])
def insert_b2b_form():
    data = request.get_json()

    logging.info(data)
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        create_document(cursor, data, app.config)
        complete(cursor)
    except:
        rollback(cursor)
        raise
    return Response(status=200)


@app.route('/reprints/<reprint_type>', methods=['GET'])
def reprints(reprint_type):
    request_id = ''
    if reprint_type == 'registration':
        registration_no = request.args['registration_no']
        registration_date = request.args['registration_date']
        url = app.config['LAND_CHARGES_URI'] + '/request_details?reprint_type=' + reprint_type
        url += '&registration_no=' + registration_no + '&registration_date=' + registration_date
        response = requests.get(url, headers=get_headers())
        data = json.loads(response.content.decode('utf-8'))
        if "request_id" not in data:
            return "invalid request_id for " + registration_no + ' ' + registration_date
        request_id = data['request_id']
    elif reprint_type == 'search':
        request_id = request.args['request_id']
    if request_id == '':
        return Response("Error: could not determine request id", status=400)
    # for the time being call reprint on result-generate. this probably needs moving into casework-api
    url = app.config['RESULT_GENERATE_URI'] + '/reprints?request=' + str(request_id)
    response = requests.get(url, headers=get_headers())
    return send_file(BytesIO(response.content), as_attachment=False, attachment_filename='reprint.pdf',
                     mimetype='application/pdf')


@app.route('/reprints/search', methods=['POST'])
def get_searches():
    search_data = request.data
    response = requests.post(app.config['LAND_CHARGES_URI'] + '/request_search_details', data=search_data,
                             headers=get_headers({'Content-Type': 'application/json'}))
    data = json.loads(response.content.decode('utf-8'))
    return Response(json.dumps(data), status=200, mimetype='application/json')


@app.route('/registrations/<reg_date>/<reg_name>', methods=['GET'])
def get_registration(reg_date, reg_name):
    response = get_registration_details(reg_date, reg_name)
    logging.debug("HERE!!!!!!!")
    logging.debug(response['data'])
    logging.debug("AND HERE!!!!!!!")
    if response['status'] != 200:
        return Response(json.dumps(response['data']), status=response['status'], mimetype='application/json')
    else:
        return Response(json.dumps(response['data']), status=200, mimetype='application/json')


@app.route('/reclassify', methods=['POST'])
def reclassify_form():
    data = request.get_json(force=True)
    appn_id = data['appn_id']
    form_type = data['form_type']
    logging.info("T:%s Reclassify %s Application ", data['appn_id'], data['form_type'])
    work_type = get_work_type(form_type)
    logging.info("as ", work_type["list_title"])
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        reclassify_appn(cursor, appn_id, form_type, work_type["work_type"])
    finally:
        complete(cursor)
    return Response(json.dumps(work_type), status=200, mimetype='application/json')


def build_fee_data(data, appn, fee_details, action):
    if action == 'complete':
        fee = {'transaction_code': 'RN',
               'key_number': data['key_number'],
               'reference': data['application_ref'],
               'class_of_charge': data['lc_register_details']['class']}
        reg_type = 'new_registrations'
    elif action == 'rectify':
        fee = {'transaction_code': 'RN',
               'key_number': data['applicant']['key_number'],
               'reference': data['applicant']['reference'],
               'class_of_charge': data['class_of_charge']}
        reg_type = 'new registrations'
    elif action == 'cancel':
        fee = {'transaction_code': 'CN',
               'key_number': data['applicant']['key_number'],
               'reference': data['applicant']['reference']}
        reg_type = 'cancellations'
        date = data['registration']['date']
        number = data['registration_no']
        url = app.config['LAND_CHARGES_URI'] + '/registrations/' + date + '/' + number
        response = requests.get(url, headers=get_headers())
        if response.status_code == 200:
            result = (json.loads(response.text))
            fee['class_of_charge'] = result['class_of_charge']
        else:
            err = 'Failed to get registration for ' + number + ' dated ' + date + '. Error code:' \
                  + str(response.status_code)

            logging.error(format_message(err))
            raise RuntimeError(err)
    elif action == 'search':
        # TODO: still need to sort out serach certificate no
        if fee_details['delivery'] == 'Postal':
            transaction_code = 'PS'
            search_appn = str(appn[0]) + 'P'
        else:
            transaction_code = 'XS'
            search_appn = str(appn[0]) + 'D'

        fee = {'transaction_code': transaction_code,
               'key_number': data['customer']['key_number'],
               'reference': data['customer']['reference'],
               'class_of_charge': ' '}

        fee_data = {'fee_info': fee,
                    'reg_no': ' ',
                    'appn_no': search_appn,
                    'fee_factor': fee_details['fee_factor']}

        # call legacy_adapter to process fee for search and return
        logging.debug("fee information" + json.dumps(fee_data))
        url = app.config['LEGACY_ADAPTER_URI'] + '/fee_process'
        response = requests.post(url, data=fee_data, headers=get_headers())
        if response.status_code == 200:
            return response.status_code
        else:
            err = 'Failed to call fee_process for ' + search_appn + '. Error code:' \
                  + str(response.status_code)

            logging.error(format_message(err))
            raise RuntimeError(err)
    else:
        err = 'The fee action is incorrect: ' + action
        logging.error(format_message(err))
        raise RuntimeError(err)

        # call legacy_adapter for each registration number
    if 'priority_notices' in appn:
        reg_type = 'priority_notices'

    for reg in appn[reg_type]:
        fee_data = {'fee_info': fee}
        if action == 'cancel':
            fee_data['reg_no'] = number
            fee_data['appn_no'] = reg['number']
        else:
            fee_data['reg_no'] = reg['number']
            fee_data['appn_no'] = reg['number']
        fee_data['fee_factor'] = fee_details['fee_factor']

        logging.debug("fee information" + json.dumps(fee_data))
        url = app.config['LEGACY_ADAPTER_URI'] + '/fee_process'
        response = requests.post(url, data=fee_data, headers=get_headers())
        if response.status_code != 200:
            err = 'Failed to call fee_process for ' + str(fee_data['appn_no']) + '. Error code:' \
                  + str(response.status_code)

            logging.error(format_message(err))
            raise RuntimeError(err)

    return