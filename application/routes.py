from application import app
from application.logformat import format_message
from application.error import ValidationError, CaseworkAPIError
from flask import Response, request, send_from_directory, send_file,  url_for, g
import json
import logging
import psycopg2
import psycopg2.extras
import requests
from datetime import datetime
from application.applications import insert_new_application, get_application_list, get_application_by_id, \
    bulk_insert_applications, complete_application, delete_application, store_application, \
    amend_application, set_lock_ind, clear_lock_ind, insert_result_row, cancel_application, \
    get_registration_details, store_image_for_later, get_headers, correct_application, get_work_type, \
    reclassify_appn, renew_application
from application.documents import get_document, get_image, get_raw_image
from application.error import raise_error
import io
from io import BytesIO
from application.ocr import recognise
import traceback
from PIL import Image, ImageDraw, ImageFont, TiffImagePlugin
import os
from application.oc import create_document, create_document_only


valid_types = ['all', 'pab', 'wob',
               'bank', 'bank_regn', 'bank_amend', 'bank_rect', 'bank_with',
               'lc_regn', 'lc', 'lc_pn', 'lc_rect', 'lc_renewal',
               'amend', 'cancel', 'canc', 'cancel_part',
               'prt_search', 'search', 'search_full', 'search_bank', 'oc', 'unknown',
               'stored']


@app.route('/', methods=["GET"])
def index():
    return Response(status=200)


@app.errorhandler(Exception)
def error_handler(err):
    logging.debug('-----------------')
    logging.error(str(err))
    logging.error(format_message('Unhandled exception: ' + str(err)))
    call_stack = traceback.format_exc()

    lines = call_stack.split("\n")
    for line in lines[0:-2]:
        logging.error(format_message(line))

    error = {
        "type": "F",
        "stack": lines[0:-2]
    }

    try:
        error["dict"] = json.loads(str(err))
    except ValueError as e:
        error["text"] = str(err)

    logging.error(json.dumps(error, indent=2))

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
    # logging.info(format_message(msg))
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
    state = 'all'
    if 'type' in request.args:
        list_type = request.args['type']

    if 'state' in request.args:
        state = request.args['state'].upper()

    if list_type not in valid_types:
        return Response("Error: '" + list_type + "' is not one of the accepted work list types", status=400)

    logging.info(format_message('Get worklist %s'), list_type)
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        applications = get_application_list(cursor, list_type, state)
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
    logging.info(format_message("Lock application"))
    logging.audit(format_message("Lock application"))
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
    logging.info(format_message("Unlock application"))
    logging.audit(format_message("Unlock application"))
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
        logging.audit("Retrieve application")
        appn = get_application_by_id(cursor, appn_id)
    finally:
        complete(cursor)

    return Response(json.dumps(appn), status=200, mimetype='application/json')


@app.route('/applications/<appn_id>', methods=['DELETE'])
def remove_application(appn_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        if 'reject' in request.args:
            logging.audit(format_message("Reject application"))
        else:
            logging.audit(format_message("Remove application"))
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

    logging.debug(request.headers)

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
            logging.info(format_message("Store application"))
            logging.audit(format_message("Store application"))
            # logging.debug(data)
            # update_application_details(cursor, appn_id, data)
            store_application(cursor, appn_id, data)
            appn = get_application_by_id(cursor, appn_id)
        elif action == 'complete':
            logging.info(format_message("Complete registration"))
            logging.audit(format_message("Complete application"))
            appn = complete_application(cursor, appn_id, data)
        elif action == 'amend' or action == 'rectify':
            logging.info(format_message("Complete update"))
            logging.audit(format_message("Complete update application"))
            appn = amend_application(cursor, appn_id, data)
        elif action == 'cancel':
            logging.info(format_message("Complete cancellation"))
            logging.audit(format_message("Complete cancellation application"))
            appn = cancel_application(cursor, appn_id, data)
        elif action == 'renewal':
            logging.info(format_message("Complete renewal"))
            logging.audit(format_message("Complete renewal application"))
            appn = renew_application(cursor, appn_id, data)
        elif action == 'correction':
            logging.info(format_message("Complete correction"))
            logging.audit(format_message("Complete correction"))
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
        status = 200
    except ValidationError as e:
        rollback(cursor)
        error_str = str(e)
        error_dict = json.loads(error_str[1:-1])  # Exception seems to add quotes, annoyingly
        appn = {"ValidationError": error_dict}
        status = 400
    except:
        rollback(cursor)
        raise
    return Response(json.dumps(appn), status=status)

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


@app.route('/forms/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    cursor = connect()
    try:
        cursor.execute("delete from documents where document_id=%(doc_id)s",
                       {"doc_id": doc_id})

        rowcount = cursor.rowcount
        complete(cursor)
    except:
        rollback(cursor)
        raise

    if rowcount == 0:
        return Response(status=404)
    return Response(status=204)


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


@app.route('/registered_forms', methods=['GET'])
def get_all_registered_forms():
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute('select number, date, doc_id from registered_documents ')
        rows = cursor.fetchall()
        if len(rows) == 0:
            return Response(status=404)

        result = []
        for row in rows:
            result.append({
                'document_id': row['doc_id'],
                'number': row['number'],
                'date': row['date'].strftime('%Y-%m-%d')
            })
        return Response(json.dumps(result), status=200, mimetype='application/json')
    finally:
        complete(cursor)


@app.route('/registered_search_forms/<request_id>', methods=['GET'])
def get_registered_search_forms(request_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute('select doc_id from registered_documents '
                       'where request_id=%(id)s', {
                           'id': request_id
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
        cursor.execute('select doc_id from registered_documents '
                       'where number=%(no)s and date=%(date)s', {
                           'no': reg_no, 'date': date
                       })
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise CaseworkAPIError("Could not retrieve unique document id")

        document_id = rows[0]['document_id']
        cursor.execute('delete from registered_documents '
                       'where number=%(no)s and date=%(date)s', {
                           'no': reg_no, 'date': date
                       })

        cursor.execute('delete from documents where document_id = %(id)s', {
            'id': document_id
        })
        return Response(status=200)

    # TODO: also remove form from documents table? <<- TEST! IMPORTANT!
    finally:
        complete(cursor)


@app.route('/registered_search_forms/<request_id>', methods=['DELETE'])
def delete_all_search_forms(request_id):
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute('select doc_id from registered_documents '
                       'where request_id=%(id)s', {
                           'id': request_id
                       })
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise CaseworkAPIError("Could not retrieve unique document id")

        document_id = rows[0]['document_id']
        cursor.execute('delete from registered_documents '
                       'where request_id=%(id)s', {
                           'id': request_id
                       })

        cursor.execute('delete from documents where document_id = %(id)s', {
            'id': document_id
        })
        return Response(status=200)

    # TODO: also remove form from documents table? <<- TEST! IMPORTANT!
    finally:
        complete(cursor)


# =========== OTHER ROUTES ==============


@app.route('/keyholders/<key_number>', methods=['GET'])
def get_keyholder(key_number):
    logging.audit(format_message("Get keyholder details"))
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


@app.route('/court_check/<ref>', methods=['GET'])
def court_ref_existence_check(ref):
    logging.debug("Court existence checking")

    url = app.config['LAND_CHARGES_URI'] + '/court_check/' + ref
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
    logging.audit("Submit search")

    today = datetime.now().strftime('%Y-%m-%d')
    date_uri = app.config['LEGACY_ADAPTER_URI'] + '/dates/' + today
    date_response = requests.get(date_uri, headers=get_headers())

    if date_response.status_code != 200:
        raise CaseworkAPIError(json.dumps({
            "message": "Unexpected response from legacy_adapter/dates: " + str(date_response.status_code),
            "response": date_response.text
        }))

    # call legacy_adapter to retrieve the next search number
    url = app.config['LEGACY_ADAPTER_URI'] + '/search_number'
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        cert_no = response.text
    else:
        err = 'Failed to call search_number. Error code: {}'.format(str(response.status_code))
        logging.error(format_message(err))
        raise CaseworkAPIError(json.dumps({
            "message": err,
            "response": response.text
        }))

    date_info = date_response.json()
    data['expiry_date'] = date_info['search_expires']
    data['search_date'] = date_info['prev_working']
    data['cert_no'] = cert_no

    uri = app.config['LAND_CHARGES_URI'] + '/searches'
    response = requests.post(uri, data=json.dumps(data), headers=get_headers({'Content-Type': 'application/json'}))
    if response.status_code != 200:
        raise CaseworkAPIError(json.dumps(response.text))

    logging.info('POST {} -- {}'.format(uri, response.text))

    # store result
    response_data = response.json()
    logging.debug(json.dumps(response_data))
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
    logging.audit("Retrieve office copy")
    class_of_charge = request.args['class']
    reg_no = request.args['reg_no']
    date = request.args['date']
    uri = app.config['LAND_CHARGES_URI'] + '/office_copy' + '?class=' + class_of_charge + '&reg_no=' + reg_no + \
        '&date=' + date
    response = requests.get(uri, headers=get_headers({'Content-Type': 'application/json'}))
    logging.info('GET {} -- {}'.format(uri, response.text))
    data = json.loads(response.text)
    contents, file_name = create_document_only(data, app.config)
    response = send_file(BytesIO(contents), as_attachment=True, attachment_filename=file_name)
    return response


@app.route('/assoc_image', methods=['PUT'])
def associate_image():
    data = request.get_json(force=True)
    logging.debug(json.dumps(data))
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    logging.audit(format_message("Link image to registration %s of %s"), data['reg_no'], data['date'])
    try:
        cursor.execute("UPDATE registered_documents SET doc_id = %(doc_id)s " +
                       "WHERE number=%(reg)s and date=%(date)s",
                       {
                           "doc_id": data['document_id'], "reg": int(data['reg_no']), "date": data['date']
                       })
        rows = cursor.rowcount
        if rows == 0:
            status_code = 404
        else:
            delete_application(cursor, data['appn_id'])
            status_code = 200
        complete(cursor)
    except:
        rollback(cursor)
        raise

    return Response(status=status_code, mimetype='application/json')


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
    logging.audit(format_message("Pre-generate B2B office copy for %s"), json.dumps(data['new_registrations']))

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

    logging.audit(format_message("Request reprint for %s"), request_id)
    # for the time being call reprint on result-generate. this probably needs moving into casework-api
    url = app.config['RESULT_GENERATE_URI'] + '/reprints?request=' + str(request_id)
    response = requests.get(url, headers=get_headers())
    return send_file(BytesIO(response.content), as_attachment=False, attachment_filename='reprint.pdf',
                     mimetype='application/pdf')


@app.route('/reprints/search', methods=['POST'])
def get_searches():
    logging.audit(format_message("Search reprints"))
    search_data = request.data
    response = requests.post(app.config['LAND_CHARGES_URI'] + '/request_search_details', data=search_data,
                             headers=get_headers({'Content-Type': 'application/json'}))
    data = json.loads(response.content.decode('utf-8'))
    return Response(json.dumps(data), status=200, mimetype='application/json')


@app.route('/registrations/<reg_date>/<reg_name>', methods=['GET'])
def get_registration(reg_date, reg_name):
    if "class_of_charge" in request.args:
        class_of_charge = request.args["class_of_charge"]
    else:
        class_of_charge = None

    logging.audit(format_message("Retrieve registration details for %s / %s"), reg_date, reg_name)
    response = get_registration_details(reg_date, reg_name, class_of_charge)
    logging.debug(response['data'])

    if response['status'] != 200:
        return Response(json.dumps(response['data']), status=response['status'], mimetype='application/json')
    else:
        return Response(json.dumps(response['data']), status=200, mimetype='application/json')


@app.route('/reclassify', methods=['POST'])
def reclassify_form():
    data = request.get_json(force=True)
    appn_id = data['appn_id']
    form_type = data['form_type']
    logging.info("T:%s Reclassify as a %s Application ", str(appn_id), str(form_type))
    logging.audit(format_message("Reclassify %s as %s"), str(appn_id), str(form_type))
    work_type = get_work_type(form_type)
    logging.info("move to %s", work_type["list_title"])
    cursor = connect(cursor_factory=psycopg2.extras.DictCursor)
    try:
        unlock_application(appn_id)
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
    elif action == 'renewal':
        fee = {'transaction_code': 'RN',
               'key_number': data['applicant']['key_number'],
               'reference': data['applicant']['reference'],
               'class_of_charge': data['class_of_charge']}
        reg_type = 'new_registrations'
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
            err = "Failed to get registration {} of {}. Code: {}".format(
                number, date, response.status_code
            )
            logging.error(format_message(err))
            raise CaseworkAPIError(json.dumps({
                "message": err,
                "response": response.text
            }))

    elif action == 'search':
        if fee_details['delivery'] == 'Postal':
            transaction_code = 'PS'
        else:
            transaction_code = 'XS'

        fee = {'transaction_code': transaction_code,
               'key_number': data['customer']['key_number'],
               'reference': data['customer']['reference'],
               'class_of_charge': ' '}

        fee_data = {'fee_info': fee,
                    'reg_no': ' ',
                    'appn_no': data['cert_no'],
                    'fee_factor': fee_details['fee_factor']}

        # call legacy_adapter to process fee for search and return
        logging.debug("fee information" + json.dumps(fee_data))
        url = app.config['LEGACY_ADAPTER_URI'] + '/fee_process'
        response = requests.post(url, data=json.dumps(fee_data), headers=get_headers())
        if response.status_code == 200:
            fee = response.text
            save_request_fee(str(appn[0]), fee)
            return response.status_code
        else:
            err = "Failed to call fee_process for {}. Code: {}".format(
                data["cert_no"], response.status_code
            )

            logging.error(format_message(err))
            raise CaseworkAPIError(json.dumps({
                "message": err,
                "response": response.text
            }))

    else:
        err = "The fee action is incorrect: {}".format(action)
        logging.error(format_message(err))
        raise CaseworkAPIError(json.dumps({
            "message": err
        }))

        # call legacy_adapter for each registration number
    if 'priority_notices' in appn:
        reg_type = 'priority_notices'

    for reg in appn[reg_type]:
        fee_data = {'fee_info': fee}
        if action == 'cancel':
            fee_data['reg_no'] = number
            fee_data['appn_no'] = str(reg['number'])
        else:
            fee_data['reg_no'] = str(reg['number'])
            fee_data['appn_no'] = str(reg['number'])
        fee_data['fee_factor'] = fee_details['fee_factor']

        logging.debug("fee information" + json.dumps(fee_data))
        url = app.config['LEGACY_ADAPTER_URI'] + '/fee_process'
        response = requests.post(url, data=json.dumps(fee_data), headers=get_headers())
        if response.status_code != 200:
            err = "Failed to call fee_process for {}. Code: {}".format(
                fee_data['appn_no'], response.status_code
            )

            logging.error(format_message(err))
            raise CaseworkAPIError(json.dumps({
                "message": err
            }))
        else:
            fee = response.text
            save_request_fee(str(appn['request_id']), fee)

    return


def save_request_fee(id, fee):
    assert (fee is not None and fee != ''), "Fee is missing"

    # Add transaction fee to the associated request
    url = app.config['LAND_CHARGES_URI'] + '/request/' + id + "/" + fee
    response = requests.put(url, headers=get_headers())
    if response.status_code != 200:
        err = 'Failed to store fee against request ' + id + '. Error code:' \
              + str(response.status_code)

        logging.error(format_message(err))
        raise RuntimeError(err)

    return Response(status=response.status_code, mimetype='application/json')



@app.route('/multi_reg_check/<reg_date>/<reg_no>', methods=['GET'])
def get_multi_reg_check(reg_date, reg_no):
    logging.audit(format_message("Check multiple registration for %s %s"), reg_no, reg_date)
    url = app.config['LAND_CHARGES_URI'] + '/multi_reg_check/' + reg_date + "/" + reg_no
    data = requests.get(url, headers=get_headers())
    return Response(data, status=200, mimetype='application/json')


@app.route('/next_registration_date/<date>', methods=['GET'])
def get_next_date_for_registration(date):
    url = app.config['LEGACY_ADAPTER_URI'] + '/dates/' + date
    response = requests.get(url, headers=get_headers())
    data = response.json()
    return Response(json.dumps({'date': data['next_working']}), status=200, mimetype='application/json')