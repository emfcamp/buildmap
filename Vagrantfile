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
     echo "-------------------- Update OS"
     sudo apt-get update -qq
     sudo apt-get upgrade -q -y
     echo "-------------------- Install packages"
     sudo apt-get install -q -y nginx postgis gdal-bin vim ttf-mscorefonts-installer python-dev
     sudo apt-get install -q -y python-jinja2 python-mapscript python-mapnik python-psycopg2 python-pip
     sudo apt-get install -q -y runit rsync python-gdal python-virtualenv python-cairocffi
     sudo pip install -r /home/vagrant/buildmap/requirements.txt
     echo "-------------------- Nginx config"
     rm -f /etc/nginx/sites-enabled/default
     cp /home/vagrant/buildmap/etc/nginx-config /etc/nginx/sites-enabled/map-web
     service nginx reload
     echo "-------------------- Postgres config"
     sudo -u postgres bash -c \"psql -c \\"CREATE USER vagrant WITH PASSWORD 'vagrant';\\"\"
     sudo -u postgres bash -c \"createdb -O vagrant buildmap"
     sudo -u postgres bash -c \"psql -d buildmap -c \\"CREATE EXTENSION postgis;\\"\"
     sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/9.5/main/postgresql.conf
     sudo sed -i 's|^local|local buildmap vagrant trust\\nhost all all 0.0.0.0/0  trust\\nlocal|' /etc/postgresql/9.5/main/pg_hba.conf
     service postgresql restart
     echo "-------------------- Install magnacarto"
     wget --progress=bar:force https://download.omniscale.de/magnacarto/rel/dev-20160406-012a66a/magnacarto-dev-20160406-012a66a-linux-amd64.tar.gz
     tar zxf magnacarto-dev-20160406-012a66a-linux-amd64.tar.gz
     sudo cp magnacarto-dev-20160406-012a66a-linux-amd64/magnacarto /usr/bin
     echo "-------------------- Set up runit for tilestache"
     sudo rsync -av /home/vagrant/buildmap/etc/tilestache-runit/ /etc/sv/tilestache
     sudo ln -s /etc/sv/tilestache /etc/service/
     echo "-------------------- Done"
SHELL

end
