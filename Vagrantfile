# -*- mode: ruby -*-
# vi: set ft=ruby :
Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/xenial64"

  config.vm.provider "virtualbox" do |v|
    v.memory = 2048
    v.cpus = 2
  end

  config.vm.network "forwarded_port", guest: 80, host: 8000
  config.vm.network "forwarded_port", guest: 5432, host: 15432
  config.vm.network "forwarded_port", guest: 8080, host: 8080
  config.vm.network "private_network", type: "dhcp"

  config.vm.synced_folder ".", "/home/vagrant/buildmap", type: "nfs"
  config.vm.synced_folder "../gis", "/home/vagrant/gis", type: "nfs"
  config.vm.synced_folder "../map-web", "/home/vagrant/map-web", type: "nfs"

  config.vm.provision "shell", inline: <<-SHELL
     export BUILDMAP=/home/vagrant/buildmap
     export MAGNACARTO_VER=dev-20180115-39b3cd9

     echo "-------------------- Update OS"
     sudo apt-get update -qq
     sudo apt-get upgrade -q -y
     echo "-------------------- Install packages"
     echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | sudo debconf-set-selections
     sudo apt-get install -q -y nginx postgis gdal-bin vim ttf-mscorefonts-installer python-dev
     sudo apt-get install -q -y python-mapnik python-psycopg2 python-pip python-gdal python-cairocffi
     sudo pip install pipenv
     cd $BUILDMAP; sudo pipenv install --system
     echo "-------------------- Nginx config"
     rm -f /etc/nginx/sites-enabled/default
     cp $BUILDMAP/etc/nginx-config /etc/nginx/sites-enabled/map-web
     service nginx reload
     echo "-------------------- Postgres config"
     sudo -u postgres bash -c \"psql -c \\"CREATE USER vagrant WITH PASSWORD 'vagrant';\\"\"
     sudo -u postgres bash -c \"createdb -O vagrant buildmap"
     sudo -u postgres bash -c \"psql -d buildmap -c \\"CREATE EXTENSION postgis;\\"\"
     sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/9.5/main/postgresql.conf
     sudo sed -i 's|^local|local buildmap all trust\\nhost all all 0.0.0.0/0  trust\\nlocal|' /etc/postgresql/9.5/main/pg_hba.conf
     service postgresql restart
     echo "-------------------- Install magnacarto"
     cd /tmp
     export MAGNACARTO_TAR=magnacarto-$MAGNACARTO_VER-linux-amd64.tar.gz
     wget --progress=bar:force https://download.omniscale.de/magnacarto/rel/$MAGNACARTO_VER/$MAGNACARTO_TAR
     tar zxf $MAGNACARTO_TAR
     sudo cp magnacarto-$MAGNACARTO_VER-linux-amd64/magnacarto /usr/bin
     rm -f $MAGNACARTO_TAR
     echo "-------------------- Set up systemd for tilestache"
     sudo cp $BUILDMAP/etc/tilestache.service /etc/systemd/system/
     sudo systemctl daemon-reload
     sudo systemctl enable tilestache
     sudo systemctl start tilestache
     echo "-------------------- Done"
SHELL

end
