# -*- mode: ruby -*-
# vi: set ft=ruby :
Vagrant.configure(2) do |config|
  config.vm.box = "debian/contrib-jessie64"
  # config.vm.box_version = "8.2.0"

  config.vm.network "forwarded_port", guest: 80, host: 8000
  config.vm.network "forwarded_port", guest: 5432, host: 15432
  config.vm.network "forwarded_port", guest: 8080, host: 8080
  config.vm.network "private_network", type: "dhcp"

  config.vm.synced_folder ".", "/home/vagrant/buildmap", type: "nfs"
  config.vm.synced_folder "../gis-2016", "/home/vagrant/gis-2016", type: "nfs"
  config.vm.synced_folder "../map.emfcamp.org", "/home/vagrant/map.emfcamp.org", type: "nfs"

  config.vm.provision "shell", inline: <<-SHELL
     echo "-------------------- Update OS"
     sudo apt-get update -qq
     sudo apt-get upgrade -q -y
     echo "-------------------- Install packages"
     sudo apt-get install -q -y nginx postgresql-9.4 postgresql-9.4-postgis-2.1 gdal-bin vim ttf-mscorefonts-installer
     sudo apt-get install -q -y python-jinja2 python-mapscript python-mapnik python-psycopg2 python-pip runit rsync python-gdal
     sudo pip install -r /home/vagrant/buildmap/requirements.txt
     echo "-------------------- Nginx config"
     rm -f /etc/nginx/sites-enabled/default
     cp /home/vagrant/buildmap/etc/nginx-config /etc/nginx/sites-enabled/map.emfcamp.org
     service nginx reload
     echo "-------------------- Postgres config"
     sudo -u postgres bash -c \"psql -c \\"CREATE USER vagrant WITH PASSWORD 'vagrant';\\"\"
     sudo -u postgres bash -c \"createdb -O vagrant -EUNICODE buildmap"
     sudo -u postgres bash -c \"psql -d buildmap -c \\"CREATE EXTENSION postgis;\\"\"
     sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/9.4/main/postgresql.conf
     sudo sed -i 's|^local|local buildmap vagrant trust\\nlocal|' /etc/postgresql/9.4/main/pg_hba.conf
     sudo sh -c "echo 'host all all 0.0.0.0/0  trust' >> /etc/postgresql/9.4/main/pg_hba.conf"
     service postgresql restart
     echo "-------------------- Install magnacarto"
     wget --progress=bar:force https://download.omniscale.de/magnacarto/rel/dev-20160406-012a66a/magnacarto-dev-20160406-012a66a-linux-amd64.tar.gz
     tar zxf magnacarto-dev-20160406-012a66a-linux-amd64.tar.gz
     sudo cp magnacarto-dev-20160406-012a66a-linux-amd64/magnacarto /usr/bin
     echo "-------------------- Set up runit for tilestache"
     sudo rsync -av /home/vagrant/buildmap/etc/tilestache-runit /etc/sv/tilestache
     sudo ln -s /etc/sv/tilestache /etc/service/
     echo "-------------------- Done"
SHELL

end
