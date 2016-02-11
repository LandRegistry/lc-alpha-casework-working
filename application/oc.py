from PIL import Image, ImageDraw, ImageFont, TiffImagePlugin
import os
from io import BytesIO
import logging
import json
import subprocess
import psycopg2


def draw_text(canvas, text_pos, text, font_name, font_size, font_color):
    fonts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'application/static/fonts')
    #fonts_path = ''
    fnt = ImageFont.truetype(os.path.join(fonts_path, font_name), font_size)
    canvas.text(text_pos, text, font_color, font=fnt )


def create_ins_image(data, filename, config):
    clWhite = (255, 255, 255)
    clBlack = (0, 0, 0)
    clGrey = (178, 178, 178)
    arial = 'arial.ttf'
    arialbold = 'arialbd.ttf'
    fs_main = 28
    fs_sub = 24
    fs_sub_title = 20
    fs_text = 16
    fs_footer = 12

    size = (992, 1430)
    im = Image.new('RGB', size, clWhite)
    draw = ImageDraw.Draw(im)
    cursor_pos = 50
    draw_text(draw, (140, cursor_pos), 'Application for Registration of Petition in Bankruptcy', arialbold, fs_main, clBlack)
    cursor_pos += 50
    draw_text(draw, (170, cursor_pos), 'This is an official copy of the data provided by the Insolvency',
              arial, fs_sub, clBlack)
    cursor_pos += 30
    draw_text(draw, (210, cursor_pos), 'Service to register a Pending Action in Bankruptcy', arial, fs_sub, clBlack)
    cursor_pos += 80
    draw_text(draw, (100, cursor_pos), 'Particulars of Application:', arialbold, fs_sub_title, clBlack)
    cursor_pos += 30
    draw.line((100,cursor_pos,(im.size[1]-300),cursor_pos),fill=0)
    cursor_pos += 30
    label_pos = 150
    data_pos = 400
    draw_text(draw, (label_pos, cursor_pos), 'Reference: ', arial, fs_text, clBlack)
    draw_text(draw, (data_pos, cursor_pos), data['application_ref'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (label_pos, cursor_pos), 'Key Number: ', arial, fs_text, clBlack)
    draw_text(draw, (data_pos, cursor_pos), data['key_number'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (label_pos, cursor_pos), 'Date: ', arial, fs_text, clBlack)
    draw_text(draw, (data_pos, cursor_pos), data['application_date'], arial, fs_text, clBlack)
    cursor_pos += 50
    draw_text(draw, (100, cursor_pos), 'Particulars of Debtor:', arialbold, fs_sub_title, clBlack)

    cursor_pos += 30
    draw.line((100, cursor_pos,(im.size[1]-300),cursor_pos),fill=0)

    if 'debtor_names' in data:
        name_count = 1
        for debtor_name in data['debtor_names']:
            if name_count == 1:
                cursor_pos += 30
                draw_text(draw, (label_pos, cursor_pos), 'Name: ', arial, fs_text, clBlack)
            elif name_count == 2:
                cursor_pos += 30
                draw_text(draw, (label_pos, cursor_pos), 'Alternative Names: ', arial, fs_text, clBlack)
            else:
                cursor_pos += 25
            debtor_forenames = ""
            for forenames in debtor_name['forenames']:
                debtor_forenames += forenames + " "
            debtor_forenames = debtor_forenames.strip()
            draw_text(draw, (data_pos, cursor_pos), debtor_forenames + " " + debtor_name['surname'], arial, fs_text, clBlack)
            name_count += 1
    # cursor_pos += 50
    # draw_text(draw, (label_pos, cursor_pos), 'Alternative Names: ', arial, 22, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Date of Birth: ', arial, fs_text, clBlack)
    draw_text(draw, (data_pos, cursor_pos), data['date_of_birth'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Gender: ', arial, fs_text, clBlack)
    draw_text(draw, (data_pos, cursor_pos), data['gender'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Trading Name: ', arial, fs_text, clBlack)
    draw_text(draw, (data_pos, cursor_pos), data['trading_name'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Occupation: ', arial, fs_text, clBlack)
    draw_text(draw, (data_pos, cursor_pos), data['occupation'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Residence: ', arial, fs_text, clBlack)

    if data['residence_withheld'] == True:
        draw_text(draw, (data_pos, cursor_pos), "DEBTORS ADDRESS IS STATED TO BE UNKNOWN", arial, fs_text, clBlack)
    else:  # print debtors addresses
        cursor_pos -=40
        for address in data['residence']:
            cursor_pos += 40
            for address_line in address['address_lines']:
                draw_text(draw, (data_pos, cursor_pos), address_line, arial, fs_text, clBlack)
                cursor_pos += 25
            draw_text(draw, (data_pos, cursor_pos), address['county'], arial, fs_text, clBlack)
            cursor_pos += 25
            draw_text(draw, (data_pos, cursor_pos), address['postcode'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Business Address: ', arial, fs_text, clBlack)
    if 'business_address' in data:
        draw_text(draw, (data_pos, cursor_pos), data['business_address'], arial, fs_text, clBlack)
    cursor_pos += 30
    draw_text(draw, (150, cursor_pos), 'Investment Property: ', arial, fs_text, clBlack)
    if 'investment_property' in data:
        draw_text(draw, (data_pos, cursor_pos), data['investment_property'], arial, fs_text, clBlack)
    cursor_pos = 1250
    left_pos = 50
    draw_text(draw, (left_pos, cursor_pos), 'Land Registry', arial, fs_footer, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Land Charges Department', arial, fs_footer, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Seaton Court', arial, fs_footer, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), '2 William Prance Road', arial, fs_footer, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'Plymouth', arial, fs_footer, clGrey)
    cursor_pos += 20
    draw_text(draw, (left_pos, cursor_pos), 'PL6 5WS', arial, fs_footer, clGrey)
    del draw

    directory = config['TEMP_DIRECTORY']

    TiffImagePlugin.WRITE_LIBTIFF = True
    file_path = os.path.join(directory, filename)
    im.save(file_path, compression="tiff_deflate", resolution=120.0)
    TiffImagePlugin.WRITE_LIBTIFF = False
    return file_path


def compress_image(filename, config):
    directory = config['TEMP_DIRECTORY']
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
    create_ins_image(ins_data, filename, config)
    compress_image(filename, config)

    image_file = open(os.path.join(config['TEMP_DIRECTORY'], filename), 'rb')
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