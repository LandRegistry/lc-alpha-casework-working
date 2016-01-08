from PIL import Image
from pytesseract import image_to_string
import re
import logging


image_data = [
    {
        'bounds': [0.280449, 0.034227, 0.200321, 0.08275],
        'options': [
            {'pattern': '.*K(1|I|l)($|[^\d])', 'result': 'K1'},
            {'pattern': '.*K4', 'result': 'K4'},
            {'pattern': '.*K3', 'result': 'K3'},
#"Form Kl"
            {'pattern': '.*K6', 'result': 'K6'},
            {'pattern': '.*K7', 'result': 'K7'},
            {'pattern': '.*K8', 'result': 'K8'},
            {'pattern': '.*K9', 'result': 'K9'},
            {'pattern': '.*K10', 'result': 'K10'},
        ]
    },
    {
        'bounds': [0.264423, 0.028523, 0.184295, 0.06275],
        'options': [
            {'pattern': '.*K(1|I|l)3', 'result': 'K13'},
            {'pattern': '.*K2', 'result': 'K2'},
        ]
    },
    {
        'bounds': [0.761217948717949, 0.246434683399886, 0.128205128205128, 0.0570450656018254],
        'options': [
            {'pattern': '.*PAB', 'result': 'PA(B)'},
            {'pattern': '.*WOB', 'result': 'WO(B)'},
        ]
    },
    {
        'bounds': [0.833333333333333, 0.0376497432972048, 0.112179487179487, 0.0228180262407302],
        'options': [
            {'pattern': '.*K(1|I|l)(1|I|l)', 'result': 'K11'},
        ]
    },
    {
        'bounds': [0.240384615384615, 0.0456360524814604, 0.16025641025641, 0.0342270393610953],
        'options': [
            {'pattern': '.*K(1|I|l)9', 'result': 'K19'},
            {'pattern': '.*K(Z|2)(0|O)', 'result': 'K20'},
        ]
    },
    {
        'bounds': [0.0240384615384615, 0.0285225328009127, 0.192307692307692, 0.0713063320022818],
        'options': [
            {'pattern': '.*K(1|I|l)(5|S)', 'result': 'K15'},
            {'pattern': '.*K(1|I|l)6', 'result': 'K16'},
        ]
    },
    {
        'bounds': [0.269230769230769, 0.220764403879064, 0.144230769230769, 0.0342270393610953],
        'options': [
            {'pattern': '.*WOB', 'result': 'WO(B) Amend'},
        ]
    },
    {
        'bounds': [0.807124, 0.214727, 0.15457, 0.109264],
        'options': [
            {'pattern': 'PAB', 'result': 'PA(B)'},
        ]
    },
    {
        'bounds': [0.268016, 0.190639, 0.137652, 0.055936],
        'options': [
            {'pattern': 'AMENDED.*WOB', 'result': 'WO(B) Amend'},
        ]
    }
]


def recognise(filename):
    image = Image.open(filename)

    text_log = []
    for item in image_data:
        left = int(image.width * item['bounds'][0])
        top = int(image.height * item['bounds'][1])
        width = int(image.width * item['bounds'][2])
        height = int(image.height * item['bounds'][3])
        cropped = image.crop((left, top, left + width, top + height))
        text = image_to_string(cropped)
        text = re.sub("\r?\n", "", text)
        text_log.append('Block: "' + text + '"')

        for option in item['options']:
            match = re.match(option['pattern'], text)
            if match is not None:
                logging.info("Identified " + option['result'])
                return option['result']

    for line in text_log:
        logging.debug(line)
    return "Unknown"
