## Dev environment setup for SHA2017

Assuming you have vagrant/virtualbox/etc:

Make sure you have the following repos checked out in the same
directory, with the correct directory names so Vagrant will find
them (symlinks might work):

    buildmap/   # (this repo)
    gis/        # (the map data repo - https://github.com/redlizard/sha2017-map)
    map-web/    # (the map website repo - https://github.com/russss/sha2017-map-web)

Then, in the `buildmap` directory:

* Copy `config.py-sha` to `config.py`
* `vagrant up --provider=virtualbox`
* `vagrant ssh` to log in
* `cd buildmap; python ./buildmap.py` to generate the data
* `rm -Rf /tmp/stache; sudo sv restart tilestache` to clear cache
* Visit http://localhost:8000 to view the map.
