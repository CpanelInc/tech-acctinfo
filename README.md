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

Once downloaded to your /root folder (or /root/bin), you can call it with the
following options: 

# ./acctinfo --help
acctinfo - Version: 1.3
Usage: ./acctinfo [options] domainname.tld or cPUsername

Example: ./acctinfo --listdbs cpanel.net
    Lists any MySQL databases (and their sizes) for cpanel.net
./acctinfo --listsubs cptestdo
    Lists all sub domains under the cptestdo user name.
./acctinfo --listaddons cptestdomain.net
    Lists all addon domains under the cptestdomain.net domain name.
./acctinfo --listparked cptestdomain.net
    Lists all parked domains under the cptestdomain.net domain name.
./acctinfo --listreseller cptestdo
    Lists reseller information and domains under the cptestdo user name.
./acctinfo --listssls cptestdomain.net
    Lists any SSL's under the cptestdomain.net domain name.


ENJOY!

