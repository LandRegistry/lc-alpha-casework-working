import json
from application import app
from application.documents import get_document, get_image
import requests
import logging
import re
from datetime import datetime
import logging


def insert_new_application(cursor, data):
    app_data = data['application_data']
    delivery_method = data['delivery_method'] if 'delivery_method' in data else None

    cursor.execute("INSERT INTO pending_application (application_data, date_received, "
                   "application_type, status, work_type, delivery_method) " +
                   "VALUES (%(json)s, %(date)s, %(type)s, %(status)s, %(work_type)s, %(delivery)s) "
                   "RETURNING id", {"json": json.dumps(app_data), "date": data['date_received'],
                                    "type": data['application_type'],
                                    "status": "new", "work_type": data['work_type'],
                                    "delivery": delivery_method})
    item_id = cursor.fetchone()[0]
    return item_id


def get_application_list(cursor, list_type):
    bank_regn_type = ''
    if list_type == 'pab':
        bank_regn_type = 'PA(B)'
    elif list_type == 'wob':
        bank_regn_type = 'WO(B)'

    if list_type == 'all':
        cursor.execute(" SELECT id, date_received, application_data, application_type, status, work_type, "
                       " assigned_to, delivery_method "
                       " FROM pending_application "
                       " WHERE lock_ind IS NULL "
                       " order by date_received desc")
    elif bank_regn_type != '':
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                       " assigned_to, delivery_method "
                       " FROM pending_application "
                       " WHERE application_type=%(bank_regn_type)s AND lock_ind IS NULL "
                       " order by date_received desc",
                       {"bank_regn_type": bank_regn_type})
    else:
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, "
                       " assigned_to, delivery_method "
                       " FROM pending_application "
                       " WHERE work_type=%(list_type)s AND lock_ind IS NULL "
                       " order by date_received", {"list_type": list_type})
    rows = cursor.fetchall()
    applications = []

    for row in rows:
        result = {
            "appn_id": row['id'],
            "application_data": row['application_data'],
            "date_received": str(row['date_received']),
            "application_type": row['application_type'],
            "status": row['status'],
            "work_type": row['work_type'],
            "assigned_to": row['assigned_to'],
            "delivery_method": row['delivery_method']
        }
        applications.append(result)
    return applications


def get_application_by_id(cursor, appn_id):
    cursor.execute("SELECT date_received, application_data, application_type, status, work_type, assigned_to "
                   "FROM pending_application "
                   "WHERE id=%(id)s", {"id": appn_id})
    rows = cursor.fetchall()

    if len(rows) == 0:
        return None
    row = rows[0]
    return {
        "appn_id": appn_id,
        "application_data": row['application_data'],
        "date_received": str(row['date_received']),
        "application_type": row['application_type'],
        "status": row['status'],
        "work_type": row['work_type'],
        "assigned_to": row['assigned_to'],
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


def update_application_details(cursor, appn_id, data):
    cursor.execute("UPDATE pending_application SET application_data=%(data)s, status=%(status)s, "
                   "assigned_to=%(assign)s WHERE id=%(id)s", {
                       "data": data['application_data'],
                       "status": data['status'],
                       "assign": data['assigned_to'],
                       "id": appn_id
                   })


def delete_application(cursor, appn_id):
    logging.info('DELETE from pending_application where id=%s', appn_id)
    cursor.execute('DELETE from pending_application where id=%(id)s', {'id': appn_id})
    return cursor.rowcount


def amend_application(cursor, appn_id, data):
    logging.debug(data)
    if data['update_registration']['type'] == 'Amendment':
        doc_id = data['application_data']
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
        reg_data = data

    url = app.config['LAND_CHARGES_URI'] + '/registrations/' + date + '/' + reg_no
    headers = {'Content-Type': 'application/json'}
    response = requests.put(url, data=json.dumps(reg_data), headers=headers)
    if response.status_code != 200:
        return response

    regns = response.json()

    for regn in regns['new_registrations']:
        number = regn['number']
        date = regn['date']
        store_image_for_later(cursor, doc_id, number, date)

    # need to cancel PAB registrations if WOB and PAB provided for amendment
    """if 'wob_original' in data and 'pab_original' in data:
        reg_no = data['pab_original']['number']
        date = data['pab_original']['date']
        reg_data['pab_amendment'] = {'reg_no': regns['new_registrations'][0]['number'],
                                     'date': regns['new_registrations'][0]['date']}
        url = app.config['LAND_CHARGES_URI'] + '/registrations/' + date + '/' + reg_no
        headers = {'Content-Type': 'application/json'}
        response = requests.put(url, data=json.dumps(reg_data), headers=headers)
        if response.status_code != 200:
            return response"""

    # Delete work-item
    delete_application(cursor, appn_id)

    # return regn nos
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
        raise RuntimeError("Unexpected name type: {}".format(name['type']))

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
        date_response = requests.get(date_uri)

        if date_response.status_code != 200:
            raise RuntimeError("Unexpected return from legacy_adapter/dates: " + str(date_response.status_code))

        date_info = date_response.json()
        registration['priority_notice'] = {'expires': date_info['priority_notice_expires']}

    return registration


def store_image_for_later(cursor, document_id, reg_no, reg_date):
    cursor.execute('INSERT INTO registered_documents (number, date, doc_id) '
                   'VALUES( %(num)s, %(date)s, %(doc)s ) RETURNING id', {
                       'num': reg_no, 'date': reg_date, 'doc': document_id
                   })


def complete_application(cursor, appn_id, data):
    # Submit registration
    url = app.config['LAND_CHARGES_URI'] + '/registrations'
    headers = {'Content-Type': 'application/json'}
    if 'lc_register_details' in data:
        response = requests.post(url, data=json.dumps(create_lc_registration(data)), headers=headers)
    else:  # banks registration
        response = requests.post(url, data=json.dumps(data['registration']), headers=headers)
    if response.status_code != 200:
        logging.error(response.text)
        raise RuntimeError("Unexpected response from /registrations: {}".format(response.status_code))

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
        cursor.execute("INSERT into results(request_id, res_type, print_status) values(%(request_id)s, %(res_type)s, "
                       " %(print_status)s) ",
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
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    if response.status_code != 200:
        logging.error(response.text)
        raise RuntimeError("Unexpected response from /cancellations: {}".format(response.status_code))

    regns = response.json()

    # Insert print job
    # insert_result_row(cursor, regns['request_id'], 'registration')
    # TODO error handling on inserting print job row

    logging.debug("data = ", str(data))
    # Archive document
    document_id = data['document_id']
    # pages = get_document(cursor, document_id)
    for regn in regns['cancellations']:
        number = regn['number']
        date = regn['date']
        store_image_for_later(cursor, document_id, number, date)

    # Delete work-item
    delete_application(cursor, appn_id)

    # return regn nos
    return regns


def get_registration_details(reg_date, reg_no):
    url = app.config['LAND_CHARGES_URI'] + '/registrations/' + reg_date + '/' + reg_no
    response = requests.get(url)
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
        if 'short_description' in api_data['particulars']:
            result['short_description'] = api_data['particulars']['description']
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
        name_for_screen['company'] = name['company']
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
            raise RuntimeError("Unexpected name type: {}".format(name['type']))

        party['names'].append(name)
        party['occupation'] = data['occupation']

        return party


def get_additional_info(response):
    info = ''
    if 'additional_information' in response:
        info = response['additional_information']

    return info


def get_occupation(party):
    occupation = ''
    if 'occupation' in party:
        occupation = party['occupation']

    return occupation
