

def complete(cursor):
    cursor.connection.commit()
    cursor.close()
    cursor.connection.close()


def get_document(cursor, document_id):
    cursor.execute("select page from documents where document_id = %(id)s", {"id": document_id})
    rows = cursor.fetchall()

    data = []
    if len(rows) == 0:
        data = None
    else:
        for row in rows:
            data.append(row['page'])
    return data


def get_image(cursor, document_id, page_number):
    cursor.execute("select content_type, image from documents where document_id=%(doc_id)s and page=%(page)s",
                   {"doc_id": document_id, "page": page_number})

    rows = cursor.fetchall()

    if len(rows) == 0:
        return None

    row = rows[0]
    # Python returns blob as memoryview object, convert back to bytes
    return {"bytes": bytes(row['image']), "mimetype": row['content_type']}
