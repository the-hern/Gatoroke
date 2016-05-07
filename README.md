# Gatoroke
Gatoroake python pygame based karaoke server


Requires:
sudo apt-get install apache2 python-pygame python-imaging python-pykaraoke libapache2-mod-python alsa-base

Add the following to the Apache2 config file

<Directory />
Options Indexes FollowSymLinks MultiViews
AllowOverride All
Order allow,deny
allow from all
AddHandler mod_python .py
PythonHandler mod_python.publisher | .py
AddHandler mod_python .psp .psp_
PythonHandler mod_python.psp | .psp .psp_
PythonDebug On
</Directory>


Put psp/* into /var/www/html

mkdir /var/www/songqueue
chmod 777 /var/www/songqueue

