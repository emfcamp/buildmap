# coding=utf-8
from __future__ import division, absolute_import, print_function, unicode_literals
import os
import subprocess
from flask import Flask
from flask.ext.hookserver import Hooks
import config

script_location = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
#app.config['VALIDATE_IP'] = False
app.config['VALIDATE_SIGNATURE'] = False
hooks = Hooks(app, url='/hooks/')


@hooks.hook('ping')
def ping(data, guid):
    return 'PONG'


@hooks.hook('push')
def push(data, guid):
    for dirname in config.source_files.values():
        os.chdir(os.path.join(script_location, dirname))
        subprocess.check_call(['git', 'pull'])
    os.chdir(script_location)
    subprocess.check_call(['./buildmap.py'])
    return 'OK'

app.run()
