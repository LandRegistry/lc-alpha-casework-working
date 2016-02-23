from flask import Flask, g
import os
from log.logger import setup_logging


app = Flask(__name__)
app.config.from_object('config.Config')

setup_logging(app.config)
