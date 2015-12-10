


def read_result(cursor, state):
    if state is None:
        cursor.execute('SELECT id, type, state, number, date FROM results')
    else:
        cursor.execute('SELECT id, type, state, number, date FROM results WHERE state=%(state)s', {
            'state': state
        })
    rows = cursor.fetchall()
    result = []
    for row in rows:
        result.append({
            'id': row['id'],
            'type': row['type'],
            'state': row['state'],
            'number': row['number'],
            'date': None if row['date'] is None else row['date'].isoformat()
            
        })
    return result
    
    
def read_result_by_id(cursor, id):
    cursor.execute('SELECT id, type, state, number, date FROM results WHERE id=%(id)s', {
        'id': id
    })
    rows = cursor.fetchall()
    if len(rows) == 0:
        return None
    return {
        'id': rows[0]['id'],
        'type': rows[0]['type'],
        'state': rows[0]['state'],
        'number': rows[0]['number'],
        'date': None if rows[0]['date'] is None else rows[0]['date'].isoformat()
    }
        
    
def update_result_data(cursor, id, new_state):
    cursor.execute('UPDATE results SET state = %(state)s WHERE id=%(id)s', {
        'state': new_state,
        'id': id
    })