# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals
import os
import threading
import subprocess
from flask import Flask
from flask.ext.hookserver import Hooks
import config

script_location = os.path.dirname(os.path.abspath(__file__))

thread = None
app = Flask(__name__)
# app.config['VALIDATE_IP'] = False
app.config['VALIDATE_SIGNATURE'] = False
hooks = Hooks(app, url='/hooks/')


def regenerate_worker():
    for filename in config.source_files.values():
        os.chdir(os.path.abspath(os.path.dirname(os.path.join(script_location, filename))))
        subprocess.check_call(['git', 'pull'])
    os.chdir(script_location)
    subprocess.check_call(['python', './buildmap.py'])
    subprocess.check_call(['sudo', 'sv', 'stop', 'tilestache'])
    subprocess.check_call(['rm', '-Rf', '/tmp/stache/*'])
    subprocess.check_call(['sudo', 'sv', 'start', 'tilestache'])


@hooks.hook('ping')
def ping(data, guid):
    return 'PONG'


@hooks.hook('push')
def push(data, guid):
    global thread
    if thread is None or not thread.is_alive():
        thread = threading.Thread(name='worker', target=regenerate_worker)
        thread.start()
    return 'OK'
