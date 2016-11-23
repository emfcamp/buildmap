# encoding=utf-8
import os
import re
import subprocess
import config


def sanitise_layer(name):
    name = re.sub(r'[- (\.\.\.)]+', '_', name.lower())
    name = re.sub(r'[\(\)]', '', name)
    return name


def runCommands(commands):
    processes = {}
    while len(commands) > 0 or len(processes) > 0:
        if len(commands) > 0 and len(processes) < config.threads:
            process = subprocess.Popen(commands[0], shell=True)
            del commands[0]
            processes[process.pid] = process
        if len(commands) == 0 or len(processes) >= config.threads:
            (pid, status) = os.wait()
            if pid in processes:
                del processes[pid]


def write_file(name, data):
    with open(name, 'w') as fp:
        fp.write(data)
