# -*- coding: UTF-8 -*-
import os
import base64
import json
import datetime
from datetime import timedelta
import time
import subprocess
import flask
from flask import Flask, request, render_template, redirect, url_for,session
from shotgun_api3 import Shotgun
import requests
from datetime import timedelta
import logging, logging.config
import yaml
from logging import StreamHandler
from flask_socketio import SocketIO, emit
from flask_cors import CORS, cross_origin
from random import random
from threading import Thread, Event
from apis.entity_handler import *
from apis.transcode_handler import *

################################################################################
################      Initialize and Setup           ###########################
################################################################################

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my super secret key'.encode('utf8')

cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins='*', logger=True, engineio_logger=True)

config = {}
ui = {}
################################################################################
################      Setup default language         ###########################
################################################################################
with open(r'./i18n.yml') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    i18n = yaml.load(file, Loader=yaml.FullLoader)
    print("i18n: ",i18n, flush=True)


ui = i18n[i18n["default"]]
################################################################################
################      Shotgun setup and endpoints    ###########################
################################################################################

with open(r'./configure.yml') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    configure = yaml.load(file, Loader=yaml.FullLoader)
    print("config: ",configure, flush=True)

config['media_type'] = configure['shotgun']['media_type']
config['vod_url'] = "{}{}".format(configure['vod']['site']['ssl'],configure['vod']['site']['url'])
config['data_folder'] = configure['vod']['site']['data_folder']

################################################################################
################            Flask Route              ###########################
################################################################################
@app.route("/", methods = ['GET', 'POST'])
def home():
    '''
    Show introduction
    '''
    if request.method == 'POST':
        print("request form: ", request.form, flush = True)
        data = {}
        data['entity_type'] = request.form.get('entity_type', None)
        data['entity_id'] = request.form.get('selected_ids', None)
        data['project_name'] = request.form.get('project_name', None)
        data['project_id'] = request.form.get('project_id', None)

        try:
            sg = Shotgun("{}{}".format(configure['shotgun']['site']['ssl'],\
                                        request.form.get("server_hostname", None)), \
                                        configure['shotgun']['site']['script_name'] , \
                                        configure['shotgun']['site']['script_key'], \
                                        request.form.get("user_login", None))
            config["sg"] = sg
            print("config: ", config, flush=True)
        except Exception as e:
            return render_template('%s.html' % 'message', message = ui['message']['auth_error'])
        if len(data['entity_id'].split(",")) == 1:

            entityhandler = entity_handler(config, data)

            if data["entity_type"] != "Task":
                data['tasks'] = entityhandler.get_tasks()
                print("Tasks: ", data['tasks'], flush=True)

            data['entity_name'] = entityhandler.get_entity_name()
            return render_template('%s.html' % 'index', data = data, i18n=ui["index"])
        else:
            message = ui['message']['select_error'].format(len(data['entity_id'].split(",")))
            return render_template('%s.html' % 'message', message = message)
    else:
        return render_template('%s.html' % 'message', message = ui['message']['server_up'])

@app.route("/upload", methods = ['POST'])
def upload():
    if request.method == 'POST':
        print("request form: ", request.form, flush=True)
        print("request files: ", request.files, flush=True)

        transcoder = transcode_handler(config, request.form, request.files)

        if transcoder.validate_file() == False:
            return render_template('%s.html' % 'message', message = ui['message']['no_media_file'])

        if transcoder.validate_ext():
            transcoder.upload_media()
            return ''
        else:
            return render_template('%s.html' % 'message', message = ui['message']['ext_not_allowed'])

################################################################################
################                   Main              ###########################
################################################################################

if __name__ == "__main__":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    from gevent import monkey
    monkey.patch_all()

    # socketio.run(host="0.0.0.0", debug = True, policy_server=False, transports='websocket, xhr-polling, xhr-multipart')
    server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    server.serve_forever()
    # Setup logging
    # gunicorn_logger = logging.getLogger('gunicorn.error')
    # app.logger.handlers = gunicorn_logger.handlers
    # app.logger.handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - level=%(levelname)s - request_id=%(request_id)s - %(message)s"))
    # app.logger.handler.addFilter(RequestIDLogFilter())  # << Add request id contextual filter
    # logging.getLogger().addHandler(app.logger.handler)
    logging.basicConfig(level=logging.DEBUG)
    gunicorn_logger = logging.getLogger('gunicorn.error')
    # gunicorn_logger.setLevel(level=logging.DEBUG)
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)