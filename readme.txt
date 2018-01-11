
The acctinfo script can provide you lots of information for an account on your 
cPanel server.  

This includes any addon domains, sub domains, parked domains, databases, 
SSL Certificates.  It will list the package the account has, whether it has a 
dedicated or is using the servers shared IP address, when the user last logged in, 
whether or not they are a reseller, how long they have been a customer, etc...

It also tells you what IP address the DNS currently resolves to. You can pass it
either a cPanel user name or a domain name.  (Any domain name, even parked or addons).

It can come in very handy when you need to quickly find out information on a
particular account or domain.

You can either download it to your /root/bin folder or you can run it from the 
command line.  I created an alias in my .bashrc file that looks like this.

alias acctinfo="/usr/local/cpanel/3rdparty/bin/perl <(curl -s https://raw.githubusercontent.com/cPanelInc/tech-acctinfo/master/acctinfo)"

So you can call it as follows: 

# acctinfo --listdbs cptestdomain.net

or by username

# acctinfo --listaddons cptestdo

The following options are available: 

--help 
    Lists basic help information

-q
    Clears the screen (default is to not clear the screen)

--listdbs somedomain.net
    Lists any MySQL and PosgGreSQL databases (and their sizes) for somedomain.net

--listsubs cptestdo
    Lists all sub domains under the cptestdo user name.

--listaddons cptestdomain.net
    Lists all addon domains under the cptestdomain.net domain name.

--listparked cptestdomain.net
    Lists all parked domains under the cptestdomain.net domain name.

--listreseller cptestdo
    Lists reseller information and domains under the cptestdo user name.

--listssls cptestdomain.net
    Lists any SSL's under the cptestdomain.net domain name.

--all cptestdomain.net
   Lists all settings for the cptestdomain.net domain name. 

--cruft cptestdo
   Do a cruft check of all files for that user name (or domain name).  

--mail cptestdomain.net
   Lists mail accounts, aliases/forwarders, filters (both user and global), does some sanity 
   checking on MX records and rDNS and mail delivery (/etc/localdomains vs /etc/remotedomains).

--scan cptestdo
   Run a small scan of the /home/cptestdo directory and grep for known phrases that have been 
   found in various hacked scripts.  NOTE: THIS CAN HAVE FALSE POSITIVES SO EACH RESULT MUST
   BE INVESTIGATED BY THE SERVER OWNER!!! - DO NOT REMOVE ANY FILE THAT IS REPORTED!

