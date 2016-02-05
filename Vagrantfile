# -*- mode: ruby -*-
# vi: set ft=ruby :
Vagrant.configure(2) do |config|
  config.vm.box = "debian/jessie64"
  config.vm.box_version = "8.2.0"

  config.vm.network "forwarded_port", guest: 80, host: 8000
  config.vm.network "private_network", type: "dhcp"

  config.vm.synced_folder ".", "/home/vagrant/buildmap", type: "nfs"
  config.vm.synced_folder "../gis-2016", "/home/vagrant/gis-2016", type: "nfs"
  config.vm.synced_folder "../map.emfcamp.org", "/home/vagrant/map.emfcamp.org", type: "nfs"

  config.vm.provision "shell", inline: <<-SHELL
     sudo apt-get update
     sudo apt-get upgrade -y
     sudo apt-get install -y nginx postgresql-9.4 postgresql-9.4-postgis-2.1 gdal-bin tilecache
     sudo apt-get install -y python-jinja2 python-mapscript
     rm -f /etc/nginx/sites-enabled/000-default
     cp /home/vagrant/buildmap/etc/nginx-config /etc/nginx/sites-enabled/map.emfcamp.org
     service nginx reload
   SHELL
end
