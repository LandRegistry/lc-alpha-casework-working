import json


def insert_new_application(cursor, data):
    app_data = {
        "document_id": data['document_id']
    }

    cursor.execute("INSERT INTO pending_application (application_data, date_received, "
                   "application_type, status, work_type) " +
                   "VALUES (%(json)s, %(date)s, %(type)s, %(status)s, %(work_type)s) "
                   "RETURNING id", {"json": json.dumps(app_data), "date": data['date'],
                                    "type": data['application_type'],
                                    "status": "new", "work_type": data['work_type']})
    item_id = cursor.fetchone()[0]
    return item_id


def get_application_list(cursor, list_type):
    bank_regn_type = ''
    if list_type == 'pab':
        bank_regn_type = 'PA(B)'
    elif list_type == 'wob':
        bank_regn_type = 'WO(B)'

    if list_type == 'all':
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, assigned_to "
                       "FROM pending_application order by date_received desc")
    elif bank_regn_type != '':
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, assigned_to "
                       "FROM pending_application "
                       "WHERE application_type=%(bank_regn_type)s order by date_received desc",
                       {"bank_regn_type": bank_regn_type})
    else:
        cursor.execute("SELECT id, date_received, application_data, application_type, status, work_type, assigned_to "
                       "FROM pending_application "
                       "WHERE work_type=%(list_type)s order by date_received", {"list_type": list_type})
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
        }
        applications.append(result)
    return applications


def get_application_by_id(cursor, id):
    cursor.execute("SELECT date_received, application_data, application_type, status, work_type, assigned_to "
                   "FROM pending_application "
                   "WHERE id=%(id)s", {"id": id})
    rows = cursor.fetchall()

    if len(rows) == 0:
        return None
    row = rows[0]
    return {
        "appn_id": row['id'],
        "application_data": row['application_data'],
        "date_received": str(row['date_received']),
        "application_type": row['application_type'],
        "status": row['status'],
        "work_type": row['work_type'],
        "assigned_to": row['assigned_to'],
    }


def update_application_details(cursor, appn_id, data):
    cursor.execute("UPDATE pending_application SET application_data=%(data)s, status=%(status)s, "
                   "assigned_to=%(assign)s WHERE id=%(id)s", {
                       "data": data['application_data'],
                       "status": data['status'],
                       "assign": data['assigned_to'],
                       "id": appn_id
                   })
