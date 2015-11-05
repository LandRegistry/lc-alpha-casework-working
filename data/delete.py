import requests
import os

url = os.getenv('CASEWORK_API_URI', 'http://localhost:5006')
requests.delete(url + '/workitems')
