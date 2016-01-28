import json
from application import app
from application.documents import get_document, get_image
import requests
from datetime import datetime


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
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, assigned_to, delivery_method "
                       "FROM pending_application "
                       "WHERE lock_ind IS NULL "
                       "order by date_received desc")
    elif bank_regn_type != '':
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, assigned_to, delivery_method "
                       "FROM pending_application "
                       "WHERE application_type=%(bank_regn_type)s AND lock_ind IS NULL "
                       "order by date_received desc",
                       {"bank_regn_type": bank_regn_type})
    else:
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, assigned_to, delivery_method "
                       "FROM pending_application "
                       "WHERE work_type=%(list_type)s AND lock_ind IS NULL "
                       "order by date_received", {"list_type": list_type})
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
    cursor.execute('DELETE from pending_application where id=%(id)s', {'id': appn_id})
    return cursor.rowcount


def amend_application(cursor, appn_id, data):
    reg_no = data['regn_no']
    date = data['registration']['date']
    url = app.config['LAND_CHARGES_URI'] + '/registrations/' + date + '/' + reg_no
    headers = {'Content-Type': 'application/json'}
    response = requests.put(url, data=json.dumps(data), headers=headers)
    if response.status_code != 200:
        return response

    # Archive amendment docs under new ID
    regns = response.json()
    date_string = datetime.now().strftime("%Y_%m_%d")
    for reg_no in regns['new_registrations']:
        url = app.config['DOCUMENT_API_URI'] + '/archive/' + date_string + '/' + str(reg_no)
        body = {'document_id': data['document_id']}
        doc_response = requests.post(url, data=json.dumps(body), headers=headers)
        if doc_response.status_code != 200:
            return doc_response

    # Delete work-item
    delete_application(cursor, appn_id)

    # return regn nos
    return regns


def complete_application(cursor, appn_id, data):
    # Submit registration
    url = app.config['LAND_CHARGES_URI'] + '/registrations'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps(data), headers=headers)

    if response.status_code != 200:
        return response

    regns = response.json()


    # Insert print job
    try:
        insert_result_row(cursor, regns['request_id'],'registration')
    except:
        #TODO error inserting print job row
        pass

    # Archive document
    document_id = data['application_data']['document_id']
    pages = get_document(cursor, document_id)

    for regn in regns['new_registrations']:
        number = regn['number']
        date = regn['date']
        for page in pages:
            image = get_image(cursor, document_id, page)
            url = "{}/images/{}/{}/{}".format(app.config['LEGACY_ADAPTER_URI'],
                                              date,
                                              number,
                                              'A4')
            headers = {'Content-Type': image['mimetype']}
            doc_response = requests.put(url, data=image['bytes'], headers=headers)
            if doc_response.status_code != 200:
                # TODO: error!
                pass

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


#insert a print job row on the result table
def insert_result_row(cursor, request_id, result_type):
    try:
        cursor.execute("INSERT into results(request_id, res_type, print_status) values(%(request_id)s, %(res_type)s, " +
                   "%(print_status)s) ",
                   {
                       'request_id': request_id,
                        'res_type': result_type,
                        'print_status': "",
                    })
    except:
       raise