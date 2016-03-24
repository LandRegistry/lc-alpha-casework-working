import json
from application import app
from application.error import ValidationError, CaseworkAPIError
from application.documents import get_document, get_image
import requests
import logging
import re
from datetime import datetime
import logging
from flask import request


def get_headers(headers=None):
    if headers is None:
        headers = {}

    if 'X-Transaction-ID' in request.headers:
        headers['X-Transaction-ID'] = request.headers['X-Transaction-ID']

    if 'X-LC-Username' in request.headers:
        headers['X-LC-Username'] = request.headers['X-LC-Username']

    return headers


def insert_new_application(cursor, data):
    app_data = data['application_data']
    delivery_method = data['delivery_method'] if 'delivery_method' in data else None
    # the scanning system can be set to automatically assign the work queue based on form type
    if data['work_type'] == 'auto':
        response = get_work_type(data['application_type'])
        data['work_type'] = response["work_type"]
    cursor.execute("INSERT INTO pending_application (application_data, date_received, "
                   "application_type, status, work_type, delivery_method) " +
                   "VALUES (%(json)s, %(date)s, %(type)s, %(status)s, %(work_type)s, %(delivery)s) "
                   "RETURNING id", {"json": json.dumps(app_data), "date": data['date_received'],
                                    "type": data['application_type'],
                                    "status": "new", "work_type": data['work_type'],
                                    "delivery": delivery_method})
    item_id = cursor.fetchone()[0]
    return item_id


def get_work_type(application_type):
    # detect the work list from the form
    form_type = application_type.upper()
    if form_type == "WOB" or form_type == "PAB" or form_type == "WO(B)" or form_type == "PA(B)":
        work_type = {"work_type": "bank_regn", "list_title": "Bankruptcy Registrations"}
    elif (form_type == "WOB AMEND" or form_type == "PAB AMEND" or form_type == "WO(B) AMEND" or form_type ==
            "PA(B) AMEND" or form_type == "PABAMEND" or form_type == "WOBAMEND" or form_type == "LRRABO"):
        work_type = {"work_type": "bank_amend", "list_title": "Bankruptcy Amendments"}
    elif form_type == "K1" or form_type == "K2" or form_type == "K3" or form_type == "K4":
        work_type = {"work_type": "lc_regn", "list_title": "Land Charge Registrations"}
    elif form_type == "K6":
        work_type = {"work_type": "lc_pn", "list_title": "Priority Notices"}
    elif form_type == "K7" or form_type == "K8":
        work_type = {"work_type": "lc_renewal", "list_title": "Land Charge Renewals"}
    elif form_type == "K9":
        work_type = {"work_type": "lc_rect", "list_title": "Land Charge Rectifications"}
    elif form_type == "K11" or form_type == "K12" or form_type == "K13":
        work_type = {"work_type": "cancel", "list_title": "Cancellations"}
    elif form_type == "K15":
        work_type = {"work_type": "search_full", "list_title": "Searches - Full"}
    elif form_type == "K16":
        work_type = {"work_type": "search_bank", "list_title": "Searches - Bankruptcy"}
    else:
        work_type = {"work_type": "unknown", "list_title": "Unidentified"}
    return work_type


def get_application_list(cursor, list_type, state='ALL'):
    bank_regn_type = ''
    if list_type == 'pab':
        bank_regn_type = 'PA(B)'
    elif list_type == 'wob':
        bank_regn_type = 'WO(B)'

    if state == 'NEW':
        if list_type == 'all':
            cursor.execute(" SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE lock_ind IS NULL AND stored IS NULL "
                           " order by date_received desc")
        elif bank_regn_type != '':
            cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE application_type=%(bank_regn_type)s AND lock_ind IS NULL AND stored IS NULL "
                           " order by date_received desc",
                           {"bank_regn_type": bank_regn_type})
        else:
            cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE work_type=%(list_type)s AND lock_ind IS NULL AND stored IS NULL "
                           " order by date_received", {"list_type": list_type})
    elif state == 'STORED':
        if list_type == 'all':
            cursor.execute(" SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE lock_ind IS NULL AND stored ='t' "
                           " order by date_received desc")
        elif bank_regn_type != '':
            cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE application_type=%(bank_regn_type)s AND lock_ind IS NULL AND stored ='t' "
                           " order by date_received desc",
                           {"bank_regn_type": bank_regn_type})
        else:
            cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE work_type=%(list_type)s AND lock_ind IS NULL AND stored ='t' "
                           " order by date_received", {"list_type": list_type})
    else:
        if list_type == 'all':
            cursor.execute(" SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE lock_ind IS NULL "
                           " order by date_received desc")
        elif bank_regn_type != '':
            cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE application_type=%(bank_regn_type)s AND lock_ind IS NULL "
                           " order by date_received desc",
                           {"bank_regn_type": bank_regn_type})
        else:
            cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                           " delivery_method, stored, store_time, stored_by, store_reason "
                           " FROM pending_application "
                           " WHERE work_type=%(list_type)s AND lock_ind IS NULL "
                           " order by date_received", {"list_type": list_type})

    rows = cursor.fetchall()
    applications = []

    for row in rows:
        stored = False
        if row['stored']:
            stored = True

        result = {
            "appn_id": row['id'],
            "application_data": row['application_data'],
            "date_received": str(row['date_received']),
            "application_type": row['application_type'],
            "status": row['status'],
            "work_type": row['work_type'],
            "delivery_method": row['delivery_method'],
            "stored": stored
        }

        if stored:
            result['store_time'] = row['store_time'].strftime('%Y-%m-%d %H:%M:%S')
            result['stored_by'] = row['stored_by']
            result['store_reason'] = row['store_reason']

        applications.append(result)
    return applications


def get_application_by_id(cursor, appn_id):
    cursor.execute("SELECT date_received, application_data, application_type, status, work_type, " +
                   "delivery_method, stored, stored_by, store_reason, store_time "
                   "FROM pending_application "
                   "WHERE id=%(id)s", {"id": appn_id})
    rows = cursor.fetchall()

    if len(rows) == 0:
        return None
    row = rows[0]

    stored = False
    if row['stored']:
        stored = True

    return {
        "appn_id": appn_id,
        "application_data": row['application_data'],
        "date_received": str(row['date_received']),
        "application_type": row['application_type'],
        "status": row['status'],
        "work_type": row['work_type'],
        "delivery_method": row['delivery_method'],
        "stored": stored
    }


def set_lock_ind(cursor, appn_id):
    cursor.execute("UPDATE pending_application SET lock_ind = 'Y' "
                   "WHERE id=%(id)s and lock_ind IS NULL ", {"id": appn_id})

    if cursor.rowcount == 0:
        return None
    else:
        return "success"


def clear_lock_ind(cursor, appn_id):
    cursor.execute("UPDATE pending_application SET lock_ind = NULL "
                   "WHERE id=%(id)s", {"id": appn_id})


def store_application(cursor, appn_id, data):
    cursor.execute("UPDATE pending_application SET stored='y', application_data=%(what)s, stored_by=%(who)s, "
                   "store_reason=%(why)s, store_time=%(when)s "
                   "WHERE id=%(id)s", {
                       'what': json.dumps(data['data']), 'who': data['who'], 'why': data['reason'],
                       'when': datetime.now(), 'id': appn_id
                   })


def delete_application(cursor, appn_id):
    logging.debug('DELETE from pending_application where id=%s', appn_id)
    cursor.execute('DELETE from pending_application where id=%(id)s', {'id': appn_id})
    return cursor.rowcount


def amend_application(cursor, appn_id, data):
    logging.debug(data)
    if data['update_registration']['type'] == 'Amendment':
        doc_id = data['application_data']['document_id']
        reg_data = data['registration']
        if 'wob_original' in data and 'pab_original' in data:
            reg_no = data['wob_original']['number']
            date = data['wob_original']['date']
            reg_data['pab_amendment'] = {'reg_no': data['pab_original']['number'],
                                         'date': data['pab_original']['date'],
                                         }
        elif 'wob_original' in data:
            reg_no = data['wob_original']['number']
            date = data['wob_original']['date']
        else:
            reg_no = data['pab_original']['number']
            date = data['pab_original']['date']
    else:  # rectification
        reg_no = data['regn_no']
        date = data['registration']['date']
        doc_id = data['document_id']
        del data['regn_no']
        del data['registration']
        del data['document_id']
        del data['fee_details']
        reg_data = data

    url = app.config['LAND_CHARGES_URI'] + '/registrations/' + date + '/' + reg_no
    headers = get_headers({'Content-Type': 'application/json'})
    response = requests.put(url, data=json.dumps(reg_data), headers=headers)
    if response.status_code != 200:
        logging.error(response.text)
        error = json.loads(response.text)
        logging.error(json.dumps(error, indent=2))
        raise CaseworkAPIError(json.dumps(error))

    regns = response.json()

    # Insert print job
    insert_result_row(cursor, regns['request_id'], 'registration')

    for regn in regns['new_registrations']:
        number = regn['number']
        date = regn['date']
        store_image_for_later(cursor, doc_id, number, date)

    # Delete work-item
    delete_application(cursor, appn_id)

    # return regn nos
    return regns


def correct_application(cursor, data):
    logging.debug("begin to correct application" + json.dumps(data))
    date = data['orig_regn']['date']
    reg_no = data['orig_regn']['number']
    reg_data = data['registration']
    url = app.config['LAND_CHARGES_URI'] + '/registrations/' + date + '/' + reg_no
    headers = get_headers({'Content-Type': 'application/json'})
    response = requests.put(url, data=json.dumps(reg_data), headers=headers)
    if response.status_code != 200:
        logging.error(response.text)
        raise ValidationError(response.text)

    regns = response.json()

    if data['k22'] is True:
        insert_result_row(cursor, regns['request_id'], 'registration')

    return regns


def create_lc_registration(data):
    coc_lut = {
        'C(I)': 'C1',
        'C(II)': 'C2',
        'C(III)': 'C3',
        'C(IV)': 'C4',
        'D(I)': 'D1',
        'D(II)': 'D2',
        'D(III)': 'D3',
    }

    c = data['lc_register_details']['class']
    if c in coc_lut:
        c = coc_lut[c]
    else:
        c = re.sub("[\(\)]", "", c)

    registration = {
        "parties": [],
        "class_of_charge": c,
        "applicant": {
            "name": data['customer_name'],
            "address": data['customer_address'],
            "address_type": data['address_type'],
            "key_number": data["key_number"],
            "reference": data['application_ref']
        }
    }

    party = {
        "type": "Estate Owner",
        "names": []
    }

    name_data = data['lc_register_details']["estate_owner"]
    name = {
        "type": name_data['estate_owner_ind']
    }

    if name['type'] == 'Private Individual':
        name['private'] = {
            'forenames': name_data['private']['forenames'],
            'surname': name_data['private']['surname']
        }
    elif name['type'] == "County Council" or name['type'] == "Parish Council" or name['type'] == "Other Council":
        name['local'] = {
            'name': name_data['local']['name'],
            'area': name_data['local']['area']
        }
    elif name['type'] == "Development Corporation" or name['type'] == "Other" or name['type'] == 'Coded Name':
        name['other'] = name_data['other']
    elif name['type'] == "Limited Company":
        name['company'] = name_data['company']
    elif name['type'] == "Complex Name":
        name['complex'] = {
            'name': name_data['complex']['name'],
            'number': name_data['complex']['number']
        }
    else:
        raise CaseworkAPIError("Unexpected name type: {}".format(name['type']))

    party['names'].append(name)
    party['occupation'] = data['lc_register_details']['occupation']
    registration['parties'].append(party)

    if 'additional_info' in data['lc_register_details']:
        registration['additional_information'] = data['lc_register_details']['additional_info']

    registration['particulars'] = {
        "counties": data['lc_register_details']['county'],
        "district": data['lc_register_details']['district'],
        "description": data['lc_register_details']['short_description']
    }

    if data['lc_register_details']['priority_notice'] != '':
        registration['particulars']['priority_notice'] = data['lc_register_details']['priority_notice']

    if 'priority_notice_ind' in data:
        # get the priority notice expiry date
        today = datetime.now().strftime('%Y-%m-%d')
        date_uri = app.config['LEGACY_ADAPTER_URI'] + '/dates/' + today
        date_response = requests.get(date_uri, headers=get_headers())

        if date_response.status_code != 200:
            raise CaseworkAPIError(json.dumps(date_response.text))

        date_info = date_response.json()
        registration['priority_notice'] = {'expires': date_info['priority_notice_expires']}

    return registration


def store_image_for_later(cursor, document_id, reg_no=None, reg_date=None, request_id=None):
    try:
        cursor.execute('INSERT INTO registered_documents (number, date, doc_id, request_id) '
                       'VALUES( %(num)s, %(date)s, %(doc)s, %(request)s ) RETURNING id', {
                           'num': reg_no, 'date': reg_date, 'doc': document_id, 'request': request_id
                       })
    except:
        raise
    return 'success'


def complete_application(cursor, appn_id, data):
    # Submit registration
    url = app.config['LAND_CHARGES_URI'] + '/registrations'
    headers = get_headers({'Content-Type': 'application/json'})
    if 'lc_register_details' in data:
        response = requests.post(url, data=json.dumps(create_lc_registration(data)), headers=headers)
    else:  # banks registration
        response = requests.post(url, data=json.dumps(data['registration']), headers=headers)

    if response.status_code == 400:
        logging.error(response.text)
        raise ValidationError(response.text)

    elif response.status_code != 200:
        logging.error(response.text)
        error = json.loads(response.text)
        logging.error(json.dumps(error, indent=2))
        raise CaseworkAPIError(json.dumps(error))

    regns = response.json()

    # Insert print job
    insert_result_row(cursor, regns['request_id'], 'registration')
    # TODO error handling on inserting print job row

    # Archive document
    document_id = data['application_data']['document_id']
    # pages = get_document(cursor, document_id)

    if data['form'] == 'K6':
        reg_type = 'priority_notices'
    else:
        reg_type = 'new_registrations'

    for regn in regns[reg_type]:
        number = regn['number']
        date = regn['date']
        store_image_for_later(cursor, document_id, number, date)

    # Delete work-item
    delete_application(cursor, appn_id)

    # return regn nos
    return regns


def bulk_insert_applications(cursor, data):  # pragma: no cover
    items = []
    for item in data:
        app_data = {
            "document_id": item['document_id']
        }
        cursor.execute("INSERT INTO pending_application (application_data, date_received, "
                       "application_type, status, work_type, delivery_method) " +
                       "VALUES (%(json)s, %(date)s, %(type)s, %(status)s, %(work_type)s, %(delivery)s) "
                       "RETURNING id", {"json": json.dumps(app_data), "date": item['date'],
                                        "type": item['application_type'],
                                        "status": "new", "work_type": item['work_type'],
                                        "delivery": item['delivery_method']})
        items.append(cursor.fetchone()[0])
    return items


# insert a print job row on the result table
def insert_result_row(cursor, request_id, result_type):
    try:
        cursor.execute("INSERT into results(request_id, res_type, print_status, insert_timestamp) "
                       "values(%(request_id)s, %(res_type)s, %(print_status)s, current_timestamp) ",
                       {
                           'request_id': request_id,
                           'res_type': result_type,
                           'print_status': "",
                       })
    except:
        raise
    return "success"


def cancel_application(cursor, appn_id, data):
    # Cancel registration
    url = app.config['LAND_CHARGES_URI'] + '/cancellations'
    headers = get_headers({'Content-Type': 'application/json'})

    response = requests.post(url, data=json.dumps(data), headers=headers)
    if response.status_code != 200:
        logging.error(response.text)
        raise CaseworkAPIError(json.dumps(response.text))

    regns = response.json()
    # Insert print job
    insert_result_row(cursor, regns['request_id'], 'registration')
    # Archive document
    document_id = data['document_id']
    # pages = get_document(cursor, document_id)
    for regn in regns['cancellations']:
        number = regn['number']
        date = regn['date']
        store_image_for_later(cursor, document_id, number, date)
    # Delete work-item
    delete_application(cursor, appn_id)
    return regns


def renew_application(cursor, appn_id, data):
    # renew registration
    print("renew req")
    url = app.config['LAND_CHARGES_URI'] + '/renewals'
    headers = get_headers({'Content-Type': 'application/json'})
    response = requests.post(url, data=json.dumps(data), headers=headers)
    if response.status_code != 200:
        logging.error(response.text)
        raise CaseworkAPIError(json.dumps(response.text))

    regns = response.json()
    # Insert print job
    insert_result_row(cursor, regns['request_id'], 'registration')
    # Archive document
    document_id = data['document_id']
    # pages = get_document(cursor, document_id)
    print("renewal reg nos", regns)
    for regn in regns["new_registrations"]:
        number = regn['number']
        date = regn['date']
        store_image_for_later(cursor, document_id, number, date)
    # Delete work-item
    delete_application(cursor, appn_id)
    return regns


def get_registration_details(reg_date, reg_no, class_of_charge=None):
    url = app.config['LAND_CHARGES_URI'] + '/registrations/' + reg_date + '/' + reg_no
    if class_of_charge is not None:
        url += '?class_of_charge=' + class_of_charge
    response = requests.get(url, headers=get_headers())
    if response.status_code != 200:
        return {"data": "could not find registration for " + reg_no + " " + reg_date, "status": response.status_code}
    data = response.json()
    converted_data = convert_response_data(data)
    return {"data": converted_data, "status": response.status_code}


def convert_response_data(api_data):
    result = {'status': api_data['status'], 'class': convert_class_of_charge(api_data['class_of_charge']),
              'estate_owner': get_estate_owner(api_data['parties'][0]['names'][0]),
              'estate_owner_ind': api_data['parties'][0]['names'][0]['type'],
              'occupation': get_occupation(api_data['parties'][0]),
              'additional_info': get_additional_info(api_data)
              }
    if 'particulars' in api_data:
        if 'counties' in api_data['particulars']:
            result['county'] = api_data['particulars']['counties']
        if 'district' in api_data['particulars']:
            result['district'] = api_data['particulars']['district']
        if 'description' in api_data['particulars']:
            result['short_description'] = api_data['particulars']['description']
    if 'amends_registration' in api_data:
        result['amends_registration'] = api_data['amends_registration']
    return result


def convert_class_of_charge(class_of_charge):
    charge_class = {
        "C1": "C(I)", "C2": "C(II)", "C3": "C(III)", "C4": "C(IV)",
        "D1": "D(I)", "D2": "D(II)", "D3": "D(III)",
        "C(I)": "C1", "C(II)": "C2", "C(III)": "C3", "C(IV)": "C4",
        "D(I)": "D1", "D(II)": "D2", "D(III)": "D3"
    }

    if class_of_charge in charge_class:
        return charge_class.get(class_of_charge)
    else:
        return class_of_charge


def get_estate_owner(name):
    name_for_screen = {'private': {'forenames': [''], 'surname': ''},
                       'company': '',
                       'local': {'name': '', 'area': ''},
                       'complex': {"name": '', "number": ''},
                       'other': ''}

    if name['type'] == 'Private Individual':
        name_for_screen['private'] = {'forenames': name['private']['forenames'], 'surname': name['private']['surname']}
    elif name['type'] == 'Limited Company':
        name_for_screen['company'] = name['company']
    elif name['type'] == 'County Council':
        name_for_screen['local'] = {'name': name['local']['name'], 'area': name['local']['area']}
    elif name['type'] == 'Parish Council':
        name_for_screen['local'] = {'name': name['local']['name'], 'area': name['local']['area']}
    elif name['type'] == 'Other Council':
        name_for_screen['local'] = {'name': name['local']['name'], 'area': name['local']['area']}
    elif name['type'] == 'Development Corporation':
        name_for_screen['other'] = name['other']
    elif name['type'] == 'Complex Name':
        name_for_screen['complex'] = {"name": name['complex']['name'], "number": name['complex']['number']}
    elif name['type'] == 'Other':
        name_for_screen['other'] = name['other']
    return name_for_screen


def get_party_name(data):
        party = {
            "type": "Estate Owner",
            "names": []}
        name = {"type": data['estate_owner_ind']}

        if name['type'] == 'Private Individual':
            name['private'] = {
                'forenames': data['estate_owner']['private']['forenames'],
                'surname': data['estate_owner']['private']['surname']}
        elif name['type'] == "County Council" or name['type'] == "Parish Council" or name['type'] == "Other Council":
            name['local'] = {
                'name': data['estate_owner']['local']['name'],
                'area': data['estate_owner']['local']['area']}
        elif name['type'] == "Development Corporation" or name['type'] == "Other":
            name['other'] = data['estate_owner']['other']
        elif name['type'] == "Limited Company":
            name['company'] = data['estate_owner']['company']
        elif name['type'] == "Complex Name":
            name['complex'] = {
                'name': data['estate_owner']['complex']['name'],
                'number': data['estate_owner']['complex']['number']}
        else:
            raise CaseworkAPIError("Unexpected name type: {}".format(name['type']))

        party['names'].append(name)
        party['occupation'] = data['occupation']

        return party


def get_additional_info(response):
    info = ''
    if 'entered_addl_info' in response:
        info = response['entered_addl_info']

    return info


def get_occupation(party):
    occupation = ''
    if 'occupation' in party:
        occupation = party['occupation']

    return occupation


def reclassify_appn(cursor, appn_id, form_type, work_type):
    cursor.execute("UPDATE pending_application SET application_type = %(form_type)s, work_type = %(work_type)s "
                   "WHERE id=%(id)s and lock_ind IS NULL ",
                   {"form_type": form_type, "work_type": work_type, "id": appn_id}
                   )
    if cursor.rowcount == 0:
        logging.info("could not reclassify %s, %s, %s: no rows updated", appn_id, form_type, work_type)
        return None
    else:
        return "success"
