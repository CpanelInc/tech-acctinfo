#/usr/bin/bash

# Check for plugin.tgz file and extract
if [ -f plugin.tgz ]
    then
    echo "Uncompressing..."
    tar xzf plugin.tgz
fi

echo "Installing acctinfo plugin..."

# Check for and create the directory for plugin and AppConfig files.
# Should almost never have to do this, but for sanity, we'll keep this in place just in case.
if [ ! -d /var/cpanel/apps ]
    then
    mkdir /var/cpanel/apps
    chmod 755 /var/cpanel/apps
fi

# Check for and create the directory for plugin CGI files.
if [ ! -d /usr/local/cpanel/whostmgr/docroot/cgi/acctinfo ]
  then
    mkdir /usr/local/cpanel/whostmgr/docroot/cgi/acctinfo
    chmod 755 /usr/local/cpanel/whostmgr/docroot/cgi/acctinfo
fi

# Check for and create the directory for plugin template files.
if [ ! -d /usr/local/cpanel/whostmgr/docroot/templates ]
  then
    mkdir /usr/local/cpanel/whostmgr/docroot/templates
    chmod 755 /usr/local/cpanel/whostmgr/docroot/templates/
fi

# Register the plugin with AppConfig.
echo "Registering acctiinfo plugin..."
/usr/local/cpanel/bin/register_appconfig acctinfo_plugin/acctinfo.conf

# Copy plugin files to their locations and update permissions.
echo "Copyng acctinfo.cgi..."
/bin/cp acctinfo_plugin/cgi/acctinfo.cgi /usr/local/cpanel/whostmgr/docroot/cgi/acctinfo
echo "Copyng acctinfo.css..."
/bin/cp acctinfo_plugin/cgi/acctinfo.css /usr/local/cpanel/whostmgr/docroot/cgi/acctinfo
echo "Setting permissions..."
chmod 755 /usr/local/cpanel/whostmgr/docroot/cgi/acctinfo/acctinfo.cgi
echo "Copying templates..."
/bin/cp -R -f acctinfo_plugin/templates/* /usr/local/cpanel/whostmgr/docroot/templates/
echo "Copying images..."
/bin/cp acctinfo_plugin/acctinfo_logo.png /usr/local/cpanel/whostmgr/docroot/addon_plugins
echo "Done - acctinfo plugin has been installed"

