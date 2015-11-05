import requests
import json
import os

stock_data = [
    {"date": "2015-11-05 13:45:49", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 12},
    {"date": "2015-11-05 13:45:49", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 13},
    {"date": "2015-11-05 13:45:49", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 14},
    {"date": "2015-11-05 13:45:50", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 15},
    {"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 26},
    {"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 27},
    {"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 28},
    {"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 29},
    {"date": "2015-11-05 13:45:52", "work_type": "cancel", "application_type": "WO(B)", "document_id": 31},
    {"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 33},
    {"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 35},
    {"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 37},
    {"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 39},
    {"date": "2015-11-05 13:45:54", "work_type": "cancel", "application_type": "WO(B)", "document_id": 41},
    {"date": "2015-11-05 13:45:54", "work_type": "amend", "application_type": "WO(B)", "document_id": 44},
    {"date": "2015-11-05 13:45:54", "work_type": "amend", "application_type": "WO(B)", "document_id": 47},
    {"date": "2015-11-05 13:45:55", "work_type": "amend", "application_type": "WO(B)", "document_id": 50},
    {"date": "2015-11-05 13:45:55", "work_type": "amend", "application_type": "WO(B)", "document_id": 53},
    {"date": "2015-11-05 13:45:56", "work_type": "amend", "application_type": "WO(B)", "document_id": 56},
    {"date": "2015-11-05 13:45:56", "work_type": "amend", "application_type": "WO(B)", "document_id": 59},
    {"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Full Search", "document_id": 60},
    {"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Full Search", "document_id": 61},
    {"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Search", "document_id": 62},
    {"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Search", "document_id": 63},
    {"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Full Search", "document_id": 64},
    {"date": "2015-11-05 13:45:57", "work_type": "search", "application_type": "Search", "document_id": 65}
]

url = os.getenv('CASEWORK_API_URI', 'http://localhost:5006')
response = requests.post(url + '/workitem/bulk',
                         data=json.dumps(stock_data),
                         headers={'Content-Type': 'application/json'})
