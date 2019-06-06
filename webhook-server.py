"""An example github webhook server to update the map. This will need tweaking for your needs. """
import os
import threading
import subprocess
from flask import Flask
from flask.ext.hookserver import Hooks

script_location = os.path.dirname(os.path.abspath(__file__))

thread = None
app = Flask(__name__)
app.config['VALIDATE_IP'] = False
app.config['VALIDATE_SIGNATURE'] = False
hooks = Hooks(app, url='/')


def regenerate_worker():
    os.chdir('/home/russ/gis')
    subprocess.check_call(['git', 'pull'])
    os.chdir(script_location)
    subprocess.check_call(['python', './buildmap.py', '../gis/map.json', './local.conf.json'])
    os.chdir("/home/russ/docker/buildmap")
    subprocess.check_call(['sudo', 'docker-compose', 'down'])
    subprocess.check_call(['sudo', 'docker-compose', 'up', '-d'])


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


app.run()
