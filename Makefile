./env/requirements.built: requirements.txt env
	./env/bin/pip install -r ./requirements.txt && cp ./requirements.txt ./env/requirements.built

env:
	virtualenv ./env
