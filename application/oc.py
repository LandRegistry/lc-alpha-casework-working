from PIL import Image, ImageDraw, ImageFont, TiffImagePlugin
import os
from io import BytesIO
import logging
import json
import subprocess
import psycopg2


def draw_text(canvas, text_pos, text, font_name, font_size, font_color):
    fonts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'application/static/fonts')
    fnt = ImageFont.truetype(os.path.join(fonts_path, font_name), font_size)
    canvas.text(text_pos, text, font_color, font=fnt)


def create_ins_image(data, filename, config, registration_no):
    cl_white = (255, 255, 255)
    cl_black = (0, 0, 0)
    arial = 'arial.ttf'
    arialbold = 'arialbd.ttf'
    fs_main = 28
    fs_sub = 24
    fs_sub_title = 20
    fs_text = 16

    size = (992, 1430)
    im = Image.new('RGB', size, cl_white)
    draw = ImageDraw.Draw(im)
    cursor_pos = 50
    draw_text(draw, (100, cursor_pos),
              'Application for Registration of Pending Action in Bankruptcy', arialbold, fs_main, cl_black)
    cursor_pos += 50
    draw_text(draw, (165, cursor_pos), 'This is an official copy of the relevant particulars provided by the',
              arial, fs_sub, cl_black)
    cursor_pos += 30
    draw_text(draw, (180, cursor_pos),
              'Insolvency Service to register a Pending Action in Bankruptcy', arial, fs_sub, cl_black)
    cursor_pos += 80
    draw_text(draw, (100, cursor_pos), 'Particulars of Application:', arialbold, fs_sub_title, cl_black)
    cursor_pos += 30
    draw.line((100, cursor_pos, 900, cursor_pos), fill=0)
    cursor_pos += 30
    label_pos = 150
    data_pos = 400
    print("data", str(data))
    draw_text(draw, (label_pos, cursor_pos), 'Land Charge Reference: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), registration_no, arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (label_pos, cursor_pos), 'Key Number: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['key_number'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (label_pos, cursor_pos), 'Date: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['application_date'], arial, fs_text, cl_black)
    cursor_pos += 30
    draw_text(draw, (label_pos, cursor_pos), 'Adjudicator Reference: ', arial, fs_text, cl_black)
    draw_text(draw, (data_pos, cursor_pos), data['application_ref'], arial, fs_text, cl_black)
    cursor_pos += 50
    draw_text(draw, (100, cursor_pos), 'Particulars of Debtor:', arialbold, fs_sub_title, cl_black)

    cursor_pos += 30
    draw.line((100, cursor_pos, 900, cursor_pos), fill=0)

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
            draw_text(draw, (data_pos, cursor_pos), debtor_forenames + " " +
                      debtor_name['surname'], arial, fs_text, cl_black)
            name_count += 1
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
    draw_text(draw, (150, cursor_pos), 'Addresses: ', arial, fs_text, cl_black)

    if data['residence_withheld'] is True:
        draw_text(draw, (data_pos, cursor_pos), "DEBTORS ADDRESS IS STATED TO BE UNKNOWN", arial, fs_text, cl_black)
    else:  # print debtors addresses
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
    if 'business_address' in data:
        cursor_pos += 25
        draw_text(draw, (data_pos, cursor_pos), data['business_address'], arial, fs_text, cl_black)
    cursor_pos += 30
    if 'investment_property' in data:
        cursor_pos += 25
        draw_text(draw, (data_pos, cursor_pos), data['investment_property'], arial, fs_text, cl_black)
    del draw

    directory = config['TEMP_DIR']
    TiffImagePlugin.WRITE_LIBTIFF = True
    file_path = os.path.join(directory, filename)
    im.save(file_path, compression="tiff_deflate", resolution=120.0)
    TiffImagePlugin.WRITE_LIBTIFF = False
    return file_path


def compress_image(filename, config):
    directory = config['TEMP_DIR']
    alt_filename = 'tmp_' + filename
    subprocess.call(['tiff2bw', os.path.join(directory, filename), os.path.join(directory, alt_filename)])
    subprocess.call(['tiffdither', os.path.join(directory, alt_filename), os.path.join(directory, filename)])
    subprocess.call(['tiffcp', '-c', 'g4', os.path.join(directory, filename), os.path.join(directory, alt_filename)])
    os.remove(os.path.join(directory, filename))
    os.rename(os.path.join(directory, alt_filename), os.path.join(directory, filename))


def create_document(cursor, data, config):
    logging.debug('Create Image')
    filename = str(data['new_registrations'][0]['number']) + '.tiff'

    ins_data = json.loads(data['request_text'])
    create_ins_image(ins_data, filename, config, str(data['new_registrations'][0]['number']))
    compress_image(filename, config)

    image_file = open(os.path.join(config['TEMP_DIR'], filename), 'rb')
    image_bytes = image_file.read()
    image_file.close()

    cursor.execute('select max(document_id)+1 from documents')
    row = cursor.fetchone()
    if row is None:
        doc_id = 1
    else:
        doc_id = row[0]

    cursor.execute("insert into documents (document_id, form_type, content_type, page, size, image) "
                   "values ( %(document_id)s, %(form_type)s, %(content_type)s, %(page)s, %(size)s, "
                   "%(image)s ) returning id",
                   {
                       "document_id": doc_id,
                       "form_type": 'PAB',
                       "content_type": 'image/tiff',
                       "page": "1",
                       "size": 'A4',
                       "image": psycopg2.Binary(image_bytes)
                   })

    for reg in data['new_registrations']:
        reg_no = reg['number']
        date = reg['date']

        cursor.execute('INSERT INTO registered_documents (number, date, doc_id) '
                       'VALUES( %(num)s, %(date)s, %(doc)s ) RETURNING id', {
                           'num': reg_no, 'date': date, 'doc': doc_id
                       })
    logging.info('IMAGE CREATED')


def create_document_only(data, config):
    # create the doc but dont store the document on the db
    filename = str(data['new_registrations'][0]['number']) + '.tiff'
    ins_data = data['request_text']
    image_path = create_ins_image(ins_data, filename, config, str(data['new_registrations'][0]['number']))
    compress_image(filename, config)
    file_name = 'officecopy_' + ins_data['application_type'] + '_' + str(data['new_registrations'][0]['number']) + \
                '_' + str(data['new_registrations'][0]['date']) + '.tiff'
    with open(image_path, 'rb') as f:
        contents = f.read()
    return contents, file_name
