#!/bin/sh

if [ -d /var/cpanel/apps/acctinfo.conf ]
    then
    echo "Removing acctinfo plugin"
    cd ~
    rm -rf /usr/local/cpanel/whostmgr/docroot/cgi/acctinfo
    rm -f /usr/local/cpanel/whostmgr/docroot/templates/acctinfo.tmpl
    rm -f /usr/local/cpanel/whostmgr/docroot/addon_plugins/acctinfo_logo.png
    /usr/local/cpanel/bin/unregister_appconfig /var/cpanel/apps/acctinfo.conf
    echo "Done"
    exit
fi
echo "acctinfo plugin not installed!"

