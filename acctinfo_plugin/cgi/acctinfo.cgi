#!/usr/local/cpanel/3rdparty/bin/perl
# SCRIPT: acctinfo                                                                    #
# PURPOSE: Get as much information for a username or domain entered at command line   #
# as possible.                                                                        #
# AUTHOR: Peter Elsner <peter.elsner@cpanel.net>                                      #
#######################################################################################

use strict;
my $VERSION = "2.1";
use lib '/usr/local/cpanel';
require Cpanel::Form;
require Cpanel::Config;
require Whostmgr::ACLS;
require Cpanel::Template;
use Whostmgr::HTMLInterface ();
use Cpanel::Sys::Hostname           ();
use Cpanel::Config::LoadCpUserFile  ();
use Cpanel::Config::Users           ();
use Cpanel::Config::LoadWwwAcctConf ();
use Cpanel::Config::LoadCpConf      ();
use Cpanel::PwCache           		();
use Cpanel::PwCache::Get      		();
use Cpanel::LoginDefs         		();
use Cpanel::SafeRun::Timed          ();
use Cpanel::MysqlUtils;
use Cpanel::Locale                 ('en');
use Time::Piece;
use Time::Seconds;
use DateTime;
use Date::Parse;
use Net::DNS;
use Socket;
use Cpanel::MysqlUtils::MyCnf::Basic     ();
use integer;

our $stderr;
our $stdout;
our $result;
our $acct_over_quota=0;
our $ProfileNode="";
our $DOMAIN="";
our $TAB="&ensp;&ensp;&ensp;&ensp;";
our %FORM;
our $OPT_TIMEOUT;
our $skipMySQLCruft = 0;
our $CPVersion = `cat /usr/local/cpanel/version`;
our ( $images, %FORM);
our @SUBDOMAINS = undef;
our @ADDONDOMAINS = undef;
our @PARKEDDOMAINS = undef;
our @OtherDomains = undef;
our $MainDomainCnt;
our $subcnt = @SUBDOMAINS;
our $addoncnt = @ADDONDOMAINS;
our $parkcnt = @PARKEDDOMAINS;
chomp($CPVersion);

my $HOSTNAME  = Cpanel::Sys::Hostname::gethostname();
my $conf      = Cpanel::Config::LoadWwwAcctConf::loadwwwacctconf();
my $sslsyscertdir = "/var/cpanel/ssl/apache_tls";
my $is_acct;
my $HOMEDIR   = $conf->{'HOMEDIR'};
my $HOMEMATCH = $conf->{'HOMEMATCH'};
my $cpconf    = Cpanel::Config::LoadCpConf::loadcpconf();
my ($addoncnt,$subcnt,$parkcnt);
my $bootstrapcss = "<link rel='stylesheet' href='$images/bootstrap/css/bootstrap.min.css'>";
my $acctinfocss = "<link rel='stylesheet' type='text/css' href='acctinfo.css'>";
#my $jqueryjs = "<script src='$images/jquery.min.js'></script>";
#my $bootstrapjs = "<script src='$images/bootstrap/js/bootstrap.min.js'></script>";
my $jqueryjs = "<script src='jquery.min.js'></script>";
my $bootstrapjs = "<script src='bootstrap/js/bootstrap.min.js'></script>";
my $thisapp = "acctinfo";
my $chk_cph_blocks=1;
my $emailPopCnt=0;

Whostmgr::ACLS::init_acls();

print "Content-type: text/html\r\n\r\n";

if ( !Whostmgr::ACLS::hasroot() ) {
    print <<'EOM';

<div><h1>Permission denied</h1></div>

EOM
    Whostmgr::HTMLInterface::deffooter();

    exit;
}

%FORM = Cpanel::Form::parseform();
my $QUERY=$FORM{'query'};
my $selection=$FORM{'optname'};
my $templatehtml;
my $SCRIPTOUT;
open($SCRIPTOUT, '>', \$templatehtml);
select $SCRIPTOUT;

	print <<EOF;
        <!-- $bootstrapcss -->
        $acctinfocss
        $jqueryjs
        $bootstrapjs

EOF

close ($SCRIPTOUT);
select STDOUT;

my $IS_USERNAME = 1;
if ( index( $QUERY, '.' ) != -1 ) {
	$IS_USERNAME = 0;
}
my ($MAINDOMAIN,$username)=(split(/: /,qx[ grep $QUERY /etc/trueuserdomains ]));
chomp($username);
chomp($MAINDOMAIN);

our $RealHome = Cpanel::PwCache::gethomedir($username);
our $RealShell = Cpanel::PwCache::Get::getshell($username);
our $UID       = Cpanel::PwCache::Get::getuid($username);
our $GID       = Cpanel::Config::CpUser::get_cpgid($username);
our $UID_MIN   = Cpanel::LoginDefs::get_uid_min();
our $GID_MIN   = Cpanel::LoginDefs::get_gid_min();

sub get_all_domain_data {
	my $DomainInfoJSON = get_whmapi1('get_domain_info');
	my $DomainInfoLines;
	for $DomainInfoLines ( @{ $DomainInfoJSON->{data}->{domains} } ) {
		if ( $DomainInfoLines->{user} eq $username ) {
       		if ( $DomainInfoLines->{domain_type} eq "sub" ) {
				$is_acct=1;
           		push( @SUBDOMAINS,   $DomainInfoLines->{domain} );
       		}
       		if ( $DomainInfoLines->{domain_type} eq "addon" ) {
				$is_acct=1;
           		push( @ADDONDOMAINS, $DomainInfoLines->{domain} );
       		}
       		if ( $DomainInfoLines->{domain_type} eq "parked" ) {
				$is_acct=1;
           		push( @PARKEDDOMAINS, $DomainInfoLines->{domain} ) unless ( $DomainInfoLines->{domain} =~ m/cprapid.com/ );
       		}
			if ( $DomainInfoLines->{domain_type} eq "main" ) {
				push( @OtherDomains, $DomainInfoLines->{domain} );
			}
   		}
	}

	shift @SUBDOMAINS;
	shift @ADDONDOMAINS;
	shift @PARKEDDOMAINS;
	shift @OtherDomains;
	$subcnt = @SUBDOMAINS;
	$addoncnt = @ADDONDOMAINS;
	$parkcnt = @PARKEDDOMAINS;
	$MainDomainCnt = @OtherDomains;
}

if (!$QUERY or !$selection) {
	Cpanel::Template::process_template( 'whostmgr', { "template_file" => "acctinfo.tmpl", "${thisapp}_output" => $templatehtml, "print" => 1, });
	Whostmgr::HTMLInterface::deffooter();
	exit;
}

if ($selection eq "mail") {
    Cpanel::Template::process_template('whostmgr', {
        'print' => 1,
        'template_file' => '_defheader.tmpl',
        'theme' => "yui",
        'skipheader' => 0,
        'breadcrumbdata' => {
            'previous' => [{
                'name' => 'Home',
                'url' => "/scripts/command?PFILE=main",
            }, {
                'name' => "Plugins",
                'url' => "/scripts/command?PFILE=Plugins",
            }],
        },
    });
    print "<table border=0>\n";
    print " $acctinfocss\n";
	if ($acct_over_quota) {
        border();
        print "<span class='status-warn'>[WARN] - Account $username is over quota - Cannot list email data!</span><br>\n";
        border();
#        return;
    }
    print "<h1>Mail Information</h1>\n";
    print "<span class='text-black font-normal'>Mail information for domain: <span class='text-darkblue'>" . $MAINDOMAIN . "<span class='text-green'> (" . $username . ")</span></span><br>\n";
	my $ProfileNodeJSON = get_whmapi1('get_current_profile');
    $ProfileNode = $ProfileNodeJSON->{data}->{code};
	print "<span class='status-warn'>[WARN] - WPSquared (WP2) not supported!</span><br>\n" if ($ProfileNode eq "WP2");
	exit if ($ProfileNode eq "WP2");
	print "<span class='status-warn'>This server is not running on a standard node</span><br>\n" if ($ProfileNode ne "STANDARD");
    exit if ($ProfileNode ne "STANDARD");
	# IF MAILNODE limit some of the output below (passwd/shadow files, smtpF0x/AnonymousF0x, shadow.roottn hacks, & any $RealHome path info).
	print "<span class='status-warn'>$ProfileNode has no mail capabilities!</span><br>\n" if ($ProfileNode eq "DNSNODE");
	exit if ($ProfileNode eq "DNSNODE");

    if ($IS_USERNAME) {
        $DOMAIN = $MAINDOMAIN;
    }
    else {
        $DOMAIN = $QUERY;
    }

    my @sortedPops;
    my $emailacctline;
    my $qused;
    my $qlimit;
    my $qpercent;
    my $localpart;
    my $emailPopCnt = 0;
    my $emailacctline;
    my @sortedPops;
    my $ListPopsJSON;

    $ListPopsJSON = get_uapi( 'Email', 'list_pops_with_disk', "--user=$username", "domain=$DOMAIN");
	# Check for suspended/held outgoing email
    chk_mail_suspend( $username );
    chk_mail_hold( $username );

    smborder();

    my @listPops;

    for my $EmailPop ( @{ $ListPopsJSON->{result}->{data} } ) {
        $emailacctline = $EmailPop->{email};
        $qused = ( $EmailPop->{humandiskused} eq 'None' ) ? $EmailPop->{diskused} : $EmailPop->{humandiskused};
        $qlimit = ( $EmailPop->{humandiskquota} eq 'None' ) ? "Unlimited/None" : $EmailPop->{humandiskquota};
        $qpercent  = $EmailPop->{diskusedpercent20};
        $localpart = $EmailPop->{user};
        push( @listPops, "$emailacctline||$qused||$qlimit||$qpercent||$localpart\n" );
    }

    @sortedPops  = sort(@listPops);
    $emailPopCnt = @sortedPops;

	if ( $ProfileNode =~ m/STANDARD|UNKNOWN/ ) {
        #Check for variants of the shadow.roottn.bak hack
        my $shadow_roottn_baks = qx[ find $RealHome/etc/$DOMAIN/ -name 'shadow\.*' -print ] unless ( !-e ("$RealHome/etc/$DOMAIN") );
        if ($shadow_roottn_baks) {
            chomp($shadow_roottn_baks);
            print "<span class='text-red font-small sans-indent'>\\_ [WARN] - Possible variant of the shadow.roottn.bak hack found in $RealHome/etc/$DOMAIN/</span><br>\n";
            print "<span class='text-red font-small' sans-indent>\\_ $shadow_roottn_baks</span><br>\n";
            print "<span class='text-red font-small' sans-indent>\\_ Account may have been compromised!</span><br>\n";
        }

        # Check for AnonymousF0x/smtpF0x hacks
        my $hassmtpF0x = qx[ find $RealHome/etc/* -name 'shadow' -print | xargs grep -liE 'anonymousfox-|smtpf0x-|anonymousfox|smtpf' ];
        chomp($hassmtpF0x);
        my @hassmtpF0x = split "\n", $hassmtpF0x;
        if (@hassmtpF0x) {
            print "<span class='text-red font-small' sans-indent>\\_ [WARN] - Found evidence of the AnonymousF0x/smtpF0x hack in the following:</span><br>\n";
            my $foundsmtpF0x;
            foreach $foundsmtpF0x (@hassmtpF0x) {
                print "<span class='text-red font-small' sans-indent>\\_ $foundsmtpF0x</span><br>\n";
            }
        }
    }
    # check mail and etc directories for PHP files (there should never be any php files in these directories) - CX-1103
    my @dirs=qw( etc mail );
    foreach my $dir(@dirs) {
        if ( -d "$RealHome/$dir") {
            opendir my $dh, "$RealHome/$dir"; 
            my @files = readdir( $dh );
            closedir( $dh );
            my $showHead=0;
            foreach my $file(@files) {
                next if ( $file eq "." or $file eq ".." );
                next unless( $file =~ m{.php} );
                print "<span class='text-red>[WARNING] - Suspicious PHP file found within the $RealHome/$dir directory!</span><br>\n" unless( $showHead);
                $showHead=1;
                print "<span class='text-red sans-indent'>\\_ $file</span><br>\n";
            }
        }
    }

	# Check for /etc/manualmx file
    if ( -s '/etc/manualmx' ) {
        my $manual_mx_entry = Cpanel::SafeRun::Timed::timedsaferun( 5, 'grep', '-E', "^$DOMAIN", '/etc/manualmx' );
        print "<span class='text-green'>[INFO] - $DOMAIN has an entry in /etc/manualmx.<br>\n<span class='sans-indent'>\\_ $manual_mx_entry</span><br>\n" unless ( !$manual_mx_entry );
    }

    # Check for the domain being in /etc/vdomainaliases/ directory.
    if ( -s ("/etc/vdomainaliases/$DOMAIN") ) {
        print "<span class='text-green'>[INFO] - $DOMAIN is listed in the /etc/vdomainaliases/ directory.<br>\n<span class='sans-indent'>\\_ Existing accounts/autoresponders will NOT forward!</span><br>\n"; 
	}

    print "$DOMAIN has $emailPopCnt Email accounts: \n\n";
    foreach my $EmailPop (@sortedPops) {
        chomp($EmailPop);
        ( $emailacctline, $qused, $qlimit, $qpercent, $localpart ) = ( split( /\|\|/, $EmailPop ) );
    	my $over_quota_warn = "";
    	$over_quota_warn = "<span class='text-red'>[ OVER QUOTA ]" unless( $qpercent < 100 );
        print "$emailacctline<br>\n";
        print "<span class='sans-indent'>\\_ [Quota Used " . $qused . " of " . $qlimit . " (" . $qpercent . "%)] $over_quota_warn<br>\n";

        if ( $ProfileNode =~ m/STANDARD|UNKNOWN/ ) {
            # Check for .boxtrapperenable touch file - enabled if it exists.
            if ( -e ("$RealHome/etc/$DOMAIN/$localpart/.boxtrapperenable") ) {
                print "<span class='sans-indent'>\\_ Spam Boxtrapper Enabled<br>\n";
            }

            # Check for default webmail app
            my $DefWebMailApp;
            if ( -e ( "$RealHome/.cpanel/nvdata/$emailacctline\_default_webmail_app")) {
                $DefWebMailApp = qx[ cat "$RealHome/.cpanel/nvdata/$emailacctline\_default_webmail_app" ];
                $DefWebMailApp = ucfirst($DefWebMailApp);
                print "<span class='sans-indent'>\\_ Default Webmail Client: $DefWebMailApp\n";
            }

           # Check for mailbox_format.cpanel file. Display contents if it exists
            if ( -e ("$RealHome/mail/$DOMAIN/$localpart/mailbox_format.cpanel") ) {
                my $mbformat = qx [ cat "$RealHome/mail/$DOMAIN/$localpart/mailbox_format.cpanel" ];
                chomp($mbformat);
                print "<span class='sans-indent'>\\_ Account is using the $mbformat format.\n";
            }

            # check for mail hold/suspended/incoming email suspended, login disabled/suspended
            chk_mail_suspend( "$emailacctline" );
            chk_mail_hold( "$emailacctline" );
            chk_login_disabled( "$RealHome/etc/$DOMAIN", $localpart );
            chk_suspended_mail( "$RealHome/etc/$DOMAIN/$localpart" );

            # Check rcube.db for corruption
            if ( -e ("$RealHome/etc/$DOMAIN/$localpart.rcube.db") ) {
                my $rcubechk = SQLiteDBChk("$RealHome/etc/$DOMAIN/$localpart.rcube.db");
                print "<span class='text-red sans-indent'>\\_ $RealHome/etc/$DOMAIN/$localpart.rcube.db might be corrupted.</span><br>\n" unless ( $rcubechk =~ m/ok/ );
            }

            # Check for dovecot-acl file
            my $dovecotACL = timed_run( 4, 'find', "$RealHome/mail/$DOMAIN/$localpart", '-name', 'dovecot-acl' );
            chomp($dovecotACL);
            if ($dovecotACL) {
                print "<span class='text-red' sans-indent>\\_ [WARN] - Found $dovecotACL - can cause odd permission issues.</span><br>\n" unless ( !-s $dovecotACL );
            }

            # Check for dovecot-uidlist.lock file
            if ( -e ( "$RealHome/mail/$DOMAIN/$emailacctline/dovecot-uidlist.lock")) {
                print "<span class='text-red' sans-indent>\\_ [WARN] - Found dovecot-uidlist.lock file in $RealHome/mail/$DOMAIN/$emailacctline/<br>\n<span class='sans-indent'>Webmail acting strangely? - remove it and see if resolved.</span><br>\n";
            }
        }
    }

    # Check for cphulkd blocks (if --cphulkblocks flag was passed)
    my $BlockCnt            = 0;
    my $isCPHulkEnabledJSON = get_whmapi1('cphulk_status');
    my $isCPHulkEnabled     = $isCPHulkEnabledJSON->{data}->{is_enabled};
    if ( $isCPHulkEnabled and $chk_cph_blocks ) {
        my $cPHBlock = timed_run( 3, 'whmapi1', 'get_cphulk_failed_logins' );
        my @cPHBlocks    = split( / /, $cPHBlock );
        my $cPHBlockLine = "";
        foreach $cPHBlockLine (@cPHBlocks) {
            if ( $cPHBlockLine =~ m/$emailacctline/ ) {
                $BlockCnt++;
            }
        }
        if ( $BlockCnt > 0 ) {
            print "<span class='sans-indent'>\\_ [WARN] - $emailacctline has at least $BlockCnt brute force blocks detected via cPHulkd<br>\n";
        }
    }
	# user level mail filters
    my $UserFilterJSON = get_uapi( 'Email', 'list_filters', "--user=$username", "account=$localpart%40$DOMAIN");
    my $ShowHeader = 0;
    for my $UserFilter ( @{ $UserFilterJSON->{result}->{data} } ) {
        print "<span class='sans-indent text-darkorange font-normal'>\\_ has the following user level filters<br>\n" unless ($ShowHeader);
        $ShowHeader = 1;
        print "<span class='sans-indent'>\\_ $UserFilter->{filtername}</span><br>\n";
    }

	# Check for missing passwd and/or shadow files
    if ( $ProfileNode =~ m/STANDARD|UNKNOWN/ ) {
        if ( !-e "$RealHome/etc/$DOMAIN/passwd" && $emailPopCnt > 0 ) {
            print "<span class='text-darkred'>[WARN] - $RealHome/etc/$DOMAIN/passwd file is missing!</span><br>\n";
        }
        if ( !-e "$RealHome/etc/$DOMAIN/shadow" && $emailPopCnt > 0 ) {
            print "<span class='text-darkred'>[WARN] - $RealHome/etc/$DOMAIN/shadow file is missing!</span><br>\n";
        }

        my $passwdCnt = 0;
        my $shadowCnt = 0;
        if ( -e "$RealHome/etc/$DOMAIN/passwd" ) {
            ($passwdCnt) = ( split( /\s+/, qx[ wc -l $RealHome/etc/$DOMAIN/passwd ] ) )[0];
        }
        if ( -e "$RealHome/etc/$DOMAIN/shadow" ) {
            ($shadowCnt) = ( split( /\s+/, qx[ wc -l $RealHome/etc/$DOMAIN/shadow ] ) )[0];
        }
        if ( $passwdCnt ne $shadowCnt || $passwdCnt ne $emailPopCnt || $shadowCnt ne $emailPopCnt ) {
            print "<span class='text-darkred'>[WARN] - passwd/shadow count does not equal total Email accounts</span><br>\n";
            print "<span class='text-darkblue sans-indent'>\\_ passwd: $passwdCnt / shadow: $shadowCnt / Email: $emailPopCnt</span><br>\n";
        }
        # Check for weak MD5 hash in shadow files
        my $md5cnt = timed_run( 0, 'grep', '-c', '\$1\$', "$RealHome/etc/$DOMAIN/shadow" );
        chomp($md5cnt);
        print "<span class='text-darkred'>[WARN] * </span>" . "<span class='text-darkblue'>There is/are </span><span class='text-brown'>" . $md5cnt . "</span><span class='text-darkblue'> accounts in the </span><span class='text-darkmagenta'>$RealHome/etc/$DOMAIN/shadow</span><span class='text-darkblue'> file that are using a weak (MD5) hash.</span><br>\n<span class='sans-indent'>\\_ Use <span class='text-darkcyan'>grep '\\\$1\\\$' $RealHome/etc/$DOMAIN/shadow</span><span class='text-darkblue'> to list them.</span><br>\n" if ( $md5cnt > 0 );
        smborder();
    }

	# Now let's get the MX record and make sure the A record for it points to this server.
    print "Checking MX records for $DOMAIN...<br>\n";
    my @MXRecords = getMXrecord($DOMAIN);
    my $skipMXchk = 0;
    foreach my $myline (@MXRecords) {
        chomp($myline);
        if ( $myline eq "NONE" ) {
            $skipMXchk = 1;
            last;
        }
    }
    my $IsRemote = 0;
    my $Is_IP_OnServer;
    if ( !$skipMXchk ) {
        if (@MXRecords) {
            foreach my $MXRecord (@MXRecords) {
                chomp($MXRecord);
                my $ARecordForMX;
                my @ARecordForMX = getArecords($MXRecord);
                foreach $ARecordForMX (@ARecordForMX) {
                    chomp($ARecordForMX);
                    my $IS_NAT = check_for_nat($ARecordForMX);
                    if ($IS_NAT) {    ## NAT IP ADDRESS RETURNED!
                        $Is_IP_OnServer = qx[ ip addr | grep '$IS_NAT' ];
                        if ($Is_IP_OnServer) {
                            print "<span class='sans-indent text-darkblue'>\\_ $MXRecord resolves to $ARecordForMX => $IS_NAT (Configured on this server)</span><br>\n";

                            # Check reverse
                            my $ReverseOfMX = getptr($MXRecord);
                            if ( $ReverseOfMX eq $MXRecord ) {
                                print "<span class='text-green sans-indent'>\\_ [OK] - $ARecordForMX reverses back to the MX: $MXRecord</span><br>\n";
                            }
                            elsif ( $ReverseOfMX eq $HOSTNAME ) {
                                print "<span class='text-green sans-indent'>\\_ [OK] - $ARecordForMX reverses back to the hostname: $HOSTNAME</span><br>\n";
                            }
                            elsif ( $ReverseOfMX eq "mail.$MXRecord" ) {
                                print "<span class='text-green sans-indent'>\\_ [OK] - $ARecordForMX reverses back to: mail.$MXRecord</span><br>\n";
                            }
                            else {
                                $ReverseOfMX = "[NXDOMAIN]" if ( $ReverseOfMX eq "" );
                            }
                            print "<span class='text-darkred sans-indent'>\\_ [WARN] - $ARecordForMX reverses back to: $ReverseOfMX\n";
                        }
                        else {
                            print "<span class='text-darkorange sans-indent'>\\_ $MXRecord resolves to $ARecordForMX (NOT configured on this server)</span><br>\n";
                            $IsRemote = 1;
                        }
                    }
                    else {    ## NO NAT FOUND!
                        $Is_IP_OnServer = qx[ ip addr | grep '$ARecordForMX' ];
                        if ($Is_IP_OnServer) {
                            print "<span class='text-green sans-indent'>\\_ $MXRecord resolves to $ARecordForMX (Configured on this server)</span><br>\n";

                            # Check reverse
                            my $ReverseOfMX = getptr($MXRecord);
                            if ( $ReverseOfMX eq $MXRecord ) {
                                print "<span class='text-green sans-indent'>\\_ [OK] - $ARecordForMX reverses back to the MX: $MXRecord</span><br>\n";
                            }
                            elsif ( $ReverseOfMX eq $HOSTNAME ) {
                                print "<span class='text-green sans-indent'>\\_ [OK] - $ARecordForMX reverses back to the hostname $HOSTNAME</span><br>\n";
                            }
                            elsif ( $ReverseOfMX eq "mail.$MXRecord" ) {
                                print "<span class='text-green sans-indent'>\\_ [OK] - $ARecordForMX reverses back to mail.$MXRecord</span><br>\n";
                            }
                            else {
                                $ReverseOfMX = "[NXDOMAIN]" if ( $ReverseOfMX eq "" );
                            }
                            print "<span class='text-darkred sans-indent'>\\_ [WARN] - $ARecordForMX reverses back to $ReverseOfMX</span><br>\n";
                        }
                        else {
                            print "<span class='text-brown sans-indent'>\\_ $MXRecord resolves to $ARecordForMX (NOT configured on this server)</span><br>\n";
                            $IsRemote = 1;
                        }
                    }
                    print "<span class='text-darkred sans-indent'>\\_ [WARN] - MX Record should not be an IP address (violates RFC-1035)</span><br>\n" unless ( !Cpanel::Validate::IP::is_valid_ip($MXRecord) );
                }
            }
        }
    }
    else {
        print "<span class='text-darkcyan sans-indent'>\\_ None</span><br>\n";
    }


	# RIGHT HERE

	# KEEP CHANGES ABOVE THIS COMMENT!!!
	print "<tr><td><p><form action='acctinfo.cgi' method='post'>";
	print "<input type=submit value='Return' class='form-button'>";
	print "</form></td></tr>";
}

if ($selection eq "ssl") {
	Cpanel::Template::process_template('whostmgr', {
   		'print' => 1,
   		'template_file' => '_defheader.tmpl',
   		'theme' => "yui",
   		'skipheader' => 0,
   		'breadcrumbdata' => {
       		'previous' => [{
           		'name' => 'Home',
           		'url' => "/scripts/command?PFILE=main",
       		}, {
           		'name' => "Plugins",
           		'url' => "/scripts/command?PFILE=Plugins",
       		}],
   		},
	});


	if ( $IS_USERNAME ) {
		$username=$QUERY;
	}
	else {
		my $DataJSON = get_whmapi1( 'getdomainowner', "domain=$QUERY" );
    	$username = $DataJSON->{data}->{user};
	}
	chomp($username);
	($MAINDOMAIN)=(split(/: /,qx[ grep $username /etc/trueuserdomains ]))[0];
	chomp($MAINDOMAIN);

	if ( ! $username && ! $MAINDOMAIN ) {
		print "<tr><td>No information found on $QUERY</td></tr>\n";
		print "<tr><td><p><form action='acctinfo.cgi' method='post'>";
		print "<input type=submit value='Return'>";
		print "</form></td></tr>";
		exit;
	}

	print "<table border=0>\n";
	print " $acctinfocss\n";
   	print "<h1>SSL LIST</h1>\n";
    print "<span class='text-black font-normal'>SSL Certificates installed under main domain: <span class='text-darkblue'>" . $MAINDOMAIN . "<span class='text-green'> (" . $username . ")</span></span><br>\n";
    dispSSLdata($MAINDOMAIN);
	get_all_domain_data();

    print "<span class='sans-indent'>========= Subdomains =========<br>\n";
    foreach my $SUB (@SUBDOMAINS) {
        chomp($SUB);
        dispSSLdata($SUB);
    }

	sub dispSSLdata {
    	my $tcDomain = shift;
    	chomp($tcDomain);
    	print $tcDomain . "<br>\n";
    	if ( -e ("$sslsyscertdir/$tcDomain/certificates") ) {
        	my $sslsubject = Cpanel::SafeRun::Timed::timedsaferun( 3, 'openssl', 'x509', '-in', "$sslsyscertdir/$tcDomain/certificates", '-subject', '-noout' );
        	my $startdate = Cpanel::SafeRun::Timed::timedsaferun( 3, 'openssl', 'x509', '-in', "$sslsyscertdir/$tcDomain/certificates", '-startdate', '-noout' );
        	my $expiredate = Cpanel::SafeRun::Timed::timedsaferun( 3, 'openssl', 'x509', '-in', "$sslsyscertdir/$tcDomain/certificates", '-enddate', '-noout' );
        	chomp($startdate);
        	chomp($expiredate);
        	($startdate)  = ( split( /=/, $startdate ) )[1];
        	($expiredate) = ( split( /=/, $expiredate ) )[1];
        	my $EpochExpire = str2time($expiredate);
        	my $isExpired;
        	my $time_now  = time;
        	my $timeDiff  = $EpochExpire - $time_now;
        	my $isExpired = "<span class='status-valid font-small'>[VALID]</span>";

        	if ( $timeDiff < 0 ) {
            	$isExpired = "<span class='status-expired font-small'>[EXPIRED]</span>";
        	}
        	print "$TAB\\_ <span class='text-darkblue font-small'>Not Before: " . $startdate . "</span><br>\n";
        	print "$TAB\\_ <span class='text-darkblue font-small'>Not After : " . $expiredate . " " . $isExpired . "</span><br>\n";
        	my ($SSLSubject) = ( split( /\= /, Cpanel::SafeRun::Timed::timedsaferun( 4, 'openssl', 'x509', '-in', "$sslsyscertdir/$tcDomain/certificates", '-subject', '-noout')))[1];
        	my ($SSLIssuer) = ( split( /\= /, Cpanel::SafeRun::Timed::timedsaferun( 4, 'openssl', 'x509', '-in', "$sslsyscertdir/$tcDomain/certificates", '-issuer', '-noout')))[1];
        	chomp($SSLSubject);
        	chomp($SSLIssuer);
        	my $isSelfSigned = ( $SSLSubject eq $SSLIssuer ) ? 1 : 0;

        	if ( $isSelfSigned == 1 ) {
            	print "$TAB\\_ <span class='status-self-signed'>[WARN] " . "- Self-Signed Certificate!</span><br>\n";
        	}
        	else {
            	my $SSLIssuer1 = Cpanel::SafeRun::Timed::timedsaferun( 4, 'openssl', 'x509', '-in', "$sslsyscertdir/$tcDomain/certificates", '-issuer', '-noout');
            	my ($SSLIssuer2) = ( split( /O=|O = /, $SSLIssuer1 ))[1];
            	my ($SSLIssuer) = ( split( /\//, $SSLIssuer2 ))[0];
            	$SSLIssuer =~ s/\"//g;
            	print "<span class='status-ca-signed font-small'>$TAB\\_ [CA SIGNED] " . "Issued by: $SSLIssuer</span><br>\n";
        	}
        	print "<p><span class='text-darkmagenta font-small'>Protecting the following Subject Alternative Names:</span><br>\n";
        	my $getSANS = Cpanel::SafeRun::Timed::timedsaferun( 3, 'openssl', 'x509', '-in', "$sslsyscertdir/$tcDomain/certificates", '-noout', '-ext' ,'subjectAltName' );
        	my @getSANS = split "\n", $getSANS;
        	foreach my $SAN ( @getSANS ) {
            	chomp($SAN);
            	next unless( $SAN =~ m/DNS:/);
            	$SAN =~ s/\s+//g;
            	$SAN =~ s/DNS://g;
            	$SAN =~ s/\,/<br>$TAB\\_ /g;
            	print "<span class='text-black font-small'>$TAB\\_ " . $SAN . "</span><br>\n";
        	}
    	}
    	else {
        	print "<span class='text-darkblue font-small'>$TAB\\_ No SSL certificates found.</span><br>\n";
    	}
	}
	print "<tr><td><p><form action='acctinfo.cgi' method='post'>";
	print "<input type=submit value='Return' class='form-button'>";
	print "</form></td></tr>";
}

if ($selection eq "cruft") {
	Cpanel::Template::process_template('whostmgr', {
   		'print' => 1,
   		'template_file' => '_defheader.tmpl',
   		'theme' => "yui",
   		'skipheader' => 0,
   		'breadcrumbdata' => {
       		'previous' => [{
           		'name' => 'Home',
           		'url' => "/scripts/command?PFILE=main",
       		}, {
           		'name' => "Plugins",
           		'url' => "/scripts/command?PFILE=Plugins",
       		}],
   		},
	});
	print "<table border=0>\n";
	print " $acctinfocss\n";
   	print "<h1>CRUFT CHECK</h1>\n";

    my $file2search    = "";
    my $TheStatus      = "";
    my $filestatus     = "";
    my $isTerminated   = 0;
    my $termdate       = "";
    my $createdate     = "";
    my @temp           = undef;
    my $DNSLinesCnt    = 0;
    my $TotalDomainCnt = 0;

	my $isReserved;
	if ( $IS_USERNAME ) {
		my $ValUserJSON=get_whmapi1( 'validate_system_user', "user=$QUERY" );
		$isReserved  = $ValUserJSON->{data}->{reserved};
	}
	else {
		my $DataJSON = get_whmapi1( 'getdomainowner', "domain=$QUERY" );
    	$username = $DataJSON->{data}->{user};
		my $ValUserJSON=get_whmapi1( 'validate_system_user', "user=$username" );
		$isReserved  = $ValUserJSON->{data}->{reserved};
	}

	if ( $isReserved || $QUERY eq $HOSTNAME ) {
        print "<span class='status-warn'>[WARN] - $QUERY is a system user or is the same as hostname $HOSTNAME!</span><br>\n";
		print "<tr><td><p><form action='acctinfo.cgi' method='post'>";
		print "<input type=submit value='Return' class='form-button'>";
		print "</form></td></tr>";
		exit;
	}

    my $isActive;
    my $is_acct;

	border();
    print "<tr><td><span class='font-normal' >From your query of <span class='text-magenta'>"
      . $QUERY
      . "<span class='text-blue'> I have determined:</span></span><br></span>\n";

	my $acctlogfile='/var/cpanel/accounting.log';
	my @acctdata;
	my $username;
	my $MAINDOMAIN;
	my $isActive=0;
	open( my $fh, '<', $acctlogfile ) or die ($!);
	while ( <$fh> ) {
    	chomp;
    	if ( $_ =~ m{$QUERY} ) {
			$is_acct = 1;
        	my ( $day, $mon, $date, $time, $year ) = ( split( /\s+/, $_ ))[0,1,2,3,4];
        	my ( $onlyyear ) = ( split( /:/, $year ) )[0];
        	my $fulldate = $day . " " . $mon . " " . $date . " " . $time . " " . $onlyyear;
        	my ( $cmd, $owner1, $owner2, $other1, $other2, $other3 ) = ( split( /\:/, $_ ))[3,4,5,6,7,8];
        	next unless( $cmd =~ m{CREATE|REMOVE|CREATERESELLERWITHOUTDOMAIN} );
        	if ( $cmd eq 'CREATE' ) {
            	push @acctdata, "<span class='text-green font-small'>Domain: $other1 with username $other3 was created on $fulldate.</span><br>\n";
            	$isActive=1;
            	$isTerminated=0;
            	$username=$other3;
            	$MAINDOMAIN=$other1;
        	}
        	if ( $cmd eq 'REMOVE' ) {
            	push @acctdata, "<span class='text-red font-small'>Domain: $other1 with username $other2 was terminated on $fulldate.</span><br>\n";
            	$isActive=0;
            	$isTerminated=1;
            	$username=$other2;
            	$MAINDOMAIN=$other1;
        	}
        	if ( $cmd eq 'CREATERESELLERWITHOUTDOMAIN' ) {
            	push @acctdata, "<span class='text-green font-small'>$other1 is a domainless reseller account and was created on $fulldate.</span><br>\n";
            	$isActive=1;
            	$isTerminated=0;
            	$username=$other3;
            	$MAINDOMAIN=$other1;
        	}
    	}
	}
	close( $fh );

	if ( ! $IS_USERNAME ) {
		my $DataJSON = get_whmapi1( 'getdomainowner', "domain=$QUERY" );
		if ( $DataJSON->{data}->{user} ) {
   			$username = $DataJSON->{data}->{user};
		}
	}
	else {
		$username=$QUERY;
	}

	get_all_domain_data();

	if ( $IS_USERNAME ) {
    	$username=$QUERY;
	}
	else {
    	$MAINDOMAIN=$QUERY;
	}
	my $DataJSON = get_whmapi1( 'accountsummary', "user=$username" );
	my $UserSuspended = $DataJSON->{data}->{acct}->[0]->{suspended};
	my $quotaJSON = get_whmapi1( 'accountsummary', "user=$username" );
	my $quotaused = $quotaJSON->{data}->{acct}->[0]->{diskused};
	my $maxquota  = $quotaJSON->{data}->{acct}->[0]->{disklimit};
	my $inodeslimit = $quotaJSON->{data}->{acct}->[0]->{inodeslimit};
	my $inodesused = $quotaJSON->{data}->{acct}->[0]->{inodesused};
	if ( $quotaused > $maxquota ) {
    	$acct_over_quota = 1 unless ( $maxquota eq "unlimited" );
	}
	if ( $inodesused > $inodeslimit ) {
    	$acct_over_quota = 1 unless ( $inodeslimit eq "unlimited" );
	}
	$skipMySQLCruft=1 if ( $UserSuspended );

	foreach my $line(@acctdata) {
    	chomp($line);
    	print $line . "\n";
	}

    my $NOGrep = 0;
    if ($isTerminated) {
        $NOGrep         = 1;
        $skipMySQLCruft = 1;
    }
    if ($isActive) {
        if ( $addoncnt > 0 ) {
            print "<span class='text-magenta font-small'>It has <span class='text-blue'>$addoncnt <span class='text-magenta'>Addon domains </span>";
        }
        if ( $subcnt > 0 ) {
            print "<span class='text-magenta font-small'>It has <span class='text-blue'>$subcnt <span class='text-magenta'>Sub domains </span>";
        }
        if ( $parkcnt > 0 ) {
            print "<span class='text-magenta font-small'>It has <span class='text-blue'>$parkcnt <span class='text-magenta'>Aliased (parked) domains</span>";
        }
        print "</td></tr>\n";
    }

    if ( $username and -e "/etc/passwd" ) {
        my $UID     = Cpanel::PwCache::Get::getuid($username);
        my $GID     = Cpanel::Config::CpUser::get_cpgid($username);
        my $UID_MIN = Cpanel::LoginDefs::get_uid_min();
        my $GID_MIN = Cpanel::LoginDefs::get_gid_min();
        if ( $UID < $UID_MIN or $GID < $GID_MIN ) {
            print "<span class='status-warn font-small'>[WARN] - UID/GID for $username is less than $UID_MIN/$GID_MIN as set in /etc/login.defs</span><br>\n"
              unless ( $UID == 0 or $GID == 0 );
        }
    }

    $TotalDomainCnt=0;
    $TotalDomainCnt = $MainDomainCnt + $addoncnt + $subcnt + $parkcnt;
    open( USERS, "/var/cpanel/users/$username" );
    my @USERFILE = <USERS>;
    close(USERS);
    my $DNSLinesCnt  = 0;
    my @DNSLinesOnly = "";

    foreach my $userline (@USERFILE) {
        chomp($userline);
        next unless ( $userline =~ m/^DNS/ );
        my ($dnsdomain) = ( split( /=/, $userline ) )[1];
        push @DNSLinesOnly, $dnsdomain;
        $DNSLinesCnt++;
    }
    if (    !$isActive
        and !$is_acct
        and !$isTerminated )
    {
        print "<span class='text-darkred font-small'>No data found for your query of: $QUERY in /var/cpanel/accounting.log</span><br>\n";
        print "<span class='text-darkorange font-small'>Continuing search for <span class='text-darkblue'>$QUERY...</span></span>\n";
		$skipMySQLCruft=1;
    }
    my $isAddon;
    my $isSub;
    my $isParked;
    my $SubDomain;
    my $TheAddonDomain;
    if ( !$isActive ) {
        $isAddon = qx[ grep '^$QUERY:' /etc/userdatadomains | grep '==addon==' ];
        if ($isAddon) {
            $TheAddonDomain = qx[ grep '^$QUERY:' /etc/userdatadomains | grep '==addon==' | cut -d = -f7 ];
            chomp($TheAddonDomain);
            ($username) = ( split( /\s+/, $isAddon ) )[1];
            ($username) = ( split( /==/,  $username ) );
            ($isAddon)  = ( split( /:/,   $isAddon ) );
            print "<tr><td><span class='text-teal font-small'>$QUERY has an entry in /etc/userdatadomains as an addon domain under the <span class='text-darkblue'>"
              . $username
              . "<span class='text-teal font-small'> user</span></td></tr>\n";
        }
        $isSub = qx[ grep '^$QUERY:' /etc/userdatadomains | grep '==sub==' ];
        if ($isSub) {
            ($username) = ( split( /\s+/, $isSub ) )[1];
            ($username) = ( split( /==/,  $username ) );
            ($isSub)    = ( split( /:/,   $isSub ) );
            print "<tr><td><span class='text-teal font-small'>$QUERY has an entry in /etc/userdatadomains as a sub domain under the <span class='text-darkblue'>"
              . $username
              . "<span class='text-teal font-small'> user</span></td></tr>\n"
              unless ($isAddon);
        }
        $isParked =
          qx[ grep '^$QUERY:' /etc/userdatadomains | grep '==parked==' | grep -v 'cprapid.com' ];
        if ($isParked) {
            ($username) = ( split( /\s+/, $isParked ) )[1];
            ($username) = ( split( /==/,  $username ) );
            ($isParked) = ( split( /:/,   $isParked ) );
            print "<tr><td><span class='text-teal font-small'>$QUERY has an entry in /etc/userdatadomains as an aliased (parked) domain under the <span class='text-darkblue'>"
              . $username
              . "<span class='text-teal font-small'> user</span></td></tr>\n";
        }
        if ( !$MAINDOMAIN and $username ) {
            ($MAINDOMAIN) = ( split( /:/, qx[ grep '$username' /etc/trueuserdomains ] ) )[0];
            chomp($MAINDOMAIN);
        }
    }
	border();

    my @FILES2SEARCHUSER = qw(
      /etc/passwd
      /etc/group
      /etc/shadow
      /etc/gshadow
      /etc/quota.conf
      /etc/dbowners
      /etc/trueuserowners
      /var/cpanel/databases/users.db
      /etc/userdatadomains.json
      /var/cpanel/quotawarned
      /etc/nocgiusers
      /etc/userips
      /etc/userbwlimits
      /var/cpanel/resellers
    );

    my @FILES2SEARCH = qw(
      /etc/userdomains
      /etc/trueuserdomains
      /etc/userdatadomains
      /etc/domainusers
      /etc/domainips
      /etc/localdomains
      /etc/remotedomains
      /etc/demousers
      /etc/email_send_limits
      /etc/demoids
      /etc/manualmx
      /etc/demodomains
      /etc/ssldomains
      /var/cpanel/moddirdomains
      /var/cpanel/domainmap
    );

    my $file2searchu;
    if ($username) {
        if ( $username ne "nobody" ) {
            print "<tr><td><span class='text-darkblue font-large'>Searching the following files for user: "
              . $username . "</span></td></tr>\n";
            foreach $file2searchu (@FILES2SEARCHUSER) {
                chomp($file2searchu);
                if ( !( -s ($file2searchu) ) ) {
                    my $filestat =
                      $file2searchu . " is either empty or missing";
                    my $fileskip = "<span class='status-skipping font-small'>[SKIPPING]</span>";
                    print_output( $filestat, $fileskip );
                    next;
                }
                $filestatus = check_file_existance( $file2searchu, $username );
                if   ($filestatus) { $filestatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
                else               { $filestatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
                print_output( $file2searchu, $filestatus );
            }
        }
    }

    if ($IS_USERNAME) {
        $username = $QUERY;
    }
    else {
        $MAINDOMAIN = $QUERY;
    }
    if ($MAINDOMAIN) {
     	print "<tr><td><span class='text-darkblue font-large'><br>Searching the following files for domain: "
          . $MAINDOMAIN . "</span></td></tr>\n";
        foreach $file2search (@FILES2SEARCH) {
            chomp($file2search);
            if ( !( -s ($file2search) ) ) {
                my $filestat = $file2search . " is either empty or missing";
                my $fileskip = "<span class='status-skipping font-small'>[SKIPPING]</span>";
                print_output( $filestat, $fileskip );
                next;
            }

            $filestatus = check_file_existance( $file2search, $MAINDOMAIN );

            if   ($filestatus) { $filestatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else               { $filestatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( $file2search, $filestatus );
        }
    }
    if ($username) {

        my $hmCnt;
        my $dirstatus = check_dir("$HOMEDIR/$username");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "$HOMEDIR/$username", $dirstatus );
        if ( $dirstatus =~ m/EXISTS/ ) {
            my @FoundHere = qw( etc mail public_html ssl tmp );
            my $FoundHere;
            foreach $FoundHere (@FoundHere) {
                chomp($FoundHere);
                my $dirstatus = check_dir("$HOMEDIR/$username/$FoundHere");
                if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>EXISTS</span>"; }
                else              { $dirstatus = "<span class='status-missing font-small'>MISSING</span>"; }
                print "<tr><td><span class='font-small' >$TAB \\_ " . $FoundHere . " - " . $dirstatus . "</span></td></tr>\n";
            }
        }

        my $dirstatus = check_dir("/var/cpanel/userdata/$username");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/userdata/$username", $dirstatus );
        if ( $dirstatus =~ m/EXISTS/ ) {
            my @FoundHere =
qx[ egrep -srliw '$QUERY|$MAINDOMAIN' /var/cpanel/userdata/$username/* | grep -v 'cache' ];
            my $FoundHere;
            foreach $FoundHere (@FoundHere) {
                chomp($FoundHere);
                print "<tr><td><span class='font-small' >$TAB \\_ " . $FoundHere . "</span></td></tr>\n";
            }
        }

        my $dirstatus = check_dir("/var/cpanel/users/$username");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/users/$username", $dirstatus );
		my @OtherDomains;
        if ( -e ("/var/cpanel/users/$username") ) {
            if ( $DNSLinesCnt != $TotalDomainCnt ) {
                if ( $DNSLinesCnt > $TotalDomainCnt ) {
                    print "<tr><td>$TAB \\_ <span class='status-warn font-small'>[WARN]: There may be extra DNS lines in this file! [DNS: $DNSLinesCnt / Cnt: $TotalDomainCnt]</span></td></tr>\n";
                }
                if ( $DNSLinesCnt < $TotalDomainCnt ) {
                    print "<tr><td>$TAB \\_ <span class='status-warn font-small'>[WARN]: One or more DNS lines may be missing from this file! [DNS: $DNSLinesCnt / Cnt: $TotalDomainCnt]</span></td></tr>\n";
                }
                shift @DNSLinesOnly;
                my %y     = map { $_ => 1 } @DNSLinesOnly;
                my @diff1  = grep( !defined $y{$_}, @OtherDomains );
                my %x     = map { $_ => 1 } @OtherDomains;
                my @diff2 = grep( !defined $x{$_}, @DNSLinesOnly );
                my $d1cnt=@diff1;
                my $d2cnt=@diff2;
                my @diff;
                if ( $d1cnt > 0 ) {
                    @diff=@diff1;
                }
                else {
                    @diff=@diff2;
                }
                if ( $DNSLinesCnt > $TotalDomainCnt ) {
                    print "<tr><td>$TAB \\_ The following domains should probably not be listed in /var/cpanel/users/$username:</td></tr>\n";
                }
                if ( $DNSLinesCnt < $TotalDomainCnt ) {
                    print "<tr><td>$TAB \\_ The following domains might be missing from /var/cpanel/users/$username:</td></tr>\n";
                }
                foreach my $diff (@diff) {
                    chomp($diff);
                    print "<tr><td>$TAB $TAB \\_ <span class='text-purple font-small'>" . $diff . "</span></td></tr>\n";
                }
            }
        }

        my $dirstatus = check_dir("/var/cpanel/overquota/$username");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/overquota/$username", $dirstatus );

        my $dirstatus = check_dir("/var/cpanel/authn/api_tokens_v2/whostmgr/$username.json");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/authn/api_tokens_v2/whostmgr/$username.json", $dirstatus );

        my $dirstatus = check_dir("/var/cpanel/mainips/$username");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/mainips/$username", $dirstatus );

        my $dirstatus =
          check_dir("/var/cpanel/databases/grants_$username.yaml");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/databases/grants_$username.yaml",
            $dirstatus );

        my $yaml_json = (
            Cpanel::Version::compare(
                Cpanel::Version::getversionnumber(),
                '<', '11.50'
            )
        ) ? "yaml" : "json";
        my $dirstatus = check_dir("/var/cpanel/databases/$username.$yaml_json");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/databases/$username.$yaml_json",
            $dirstatus );
        my $dbindex = "/var/cpanel/databases/dbindex.db.json";
        my $dirstatus = check_file_existance( $dbindex, $username );
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( $dbindex, $dirstatus );
        my $dirstatus = check_dir("/etc/proftpd/$username");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/proftpd/$username", $dirstatus );

        my $dirstatus = check_dir("/var/cpanel/bandwidth/$username.sqlite");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/bandwidth/$username.sqlite", $dirstatus );

        if ($username) {
            my $dirstatus = check_dir("/var/cpanel/bwlimited/$username");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/var/cpanel/bwlimited/$username", $dirstatus );
        }

        if ($MAINDOMAIN) {
            my $dirstatus = check_dir("/var/cpanel/bwlimited/$MAINDOMAIN");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/var/cpanel/bwlimited/$MAINDOMAIN", $dirstatus );
        }
    }
    if ($IS_USERNAME) {
        if ($MAINDOMAIN) {
            my $dirstatus = check_dir("/etc/valiases/$MAINDOMAIN");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/etc/valiases/$MAINDOMAIN", $dirstatus );
        }
        else {
            print_output( "/etc/valiases", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
        }

        if ($MAINDOMAIN) {
            my $dirstatus = check_dir("/etc/vfilters/$MAINDOMAIN");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/etc/vfilters/$MAINDOMAIN", $dirstatus );
        }
        else {
            print_output( "/etc/vfilters", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
        }

        my $dirstatus = check_dir("/etc/vdomainaliases/$QUERY");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/vdomainaliases/$QUERY", $dirstatus );

        if ( $MAINDOMAIN ) {
            my $dirstatus = check_dir("/var/cpanel/ssl/apache_tls/$MAINDOMAIN");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/var/cpanel/ssl/apache_tls/$MAINDOMAIN", $dirstatus );
        }
        else {
            print_output( "/var/cpanel/ssl/apache_tls/$QUERY", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
        }

        if ($MAINDOMAIN) {
            my $dirstatus = check_dir("/var/named/$MAINDOMAIN.db");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/var/named/$MAINDOMAIN.db", $dirstatus );
        }
        else {
            print_output( "/var/named/", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
        }

        if ($MAINDOMAIN) {
            my $dirstatus = check_file_existance( '/etc/named.conf',
                'zone "' . $MAINDOMAIN . '"' );
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/etc/named.conf", $dirstatus );
        }
        else {
            print_output( "/etc/named.conf", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
        }

        if ($isAddon) {
            my $SubDomain = ( split( /\./, $QUERY ) )[0] . "." . $MAINDOMAIN;
            chomp($SubDomain);
            my $dirstatus = check_dir("/etc/apache2/logs/domlogs/$SubDomain");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/etc/apache2/logs/domlogs/$SubDomain", $dirstatus );
        }
        else {
            if ($MAINDOMAIN) {
                my $dirstatus =
                  check_dir("/etc/apache2/logs/domlogs/$MAINDOMAIN");
                if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
                else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
                print_output( "/etc/apache2/logs/domlogs/$MAINDOMAIN", $dirstatus );
                my $dirstatus = check_dir( "/etc/apache2/logs/domlogs/$QUERY-ssl_log" );
                if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
                else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
                print_output( "/etc/apache2/logs/domlogs/$QUERY-ssl_log", $dirstatus );
                my $dirstatus = check_dir( "/etc/apache2/logs/domlogs/$QUERY-bytes_log" );
                if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
                else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
                print_output( "/etc/apache2/logs/domlogs/$QUERY-bytes_log", $dirstatus );
            }
            else {
                print_output( "/etc/apache2/logs/domlogs/", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
            }
        }

        if ($MAINDOMAIN) {
            my $dirstatus =
              check_file_existance( "/etc/apache2/conf/httpd.conf", $MAINDOMAIN );
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/etc/apache2/conf/httpd.conf", $dirstatus );
            my $dirstatus = check_dir( "/etc/apache2/logs/domlogs/$MAINDOMAIN-ssl_log" );
            if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/etc/apache2/logs/domlogs/$MAINDOMAIN-ssl_log", $dirstatus );
            my $dirstatus = check_dir( "/etc/apache2/logs/domlogs/$MAINDOMAIN-bytes_log" );
            if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/etc/apache2/logs/domlogs/$MAINDOMAIN-bytes_log", $dirstatus );
        }
        else {
            print_output( "/etc/apache2/logs/domlogs/", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
        }

        if ($isAddon) {
            my $SubDomain = ( split( /\./, $QUERY ) )[0] . "." . $MAINDOMAIN;
            chomp($SubDomain);
            my $dirstatus = check_dir("/var/log/nginx/domains/$SubDomain");
            if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
            else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
            print_output( "/var/log/nginx/domains/$SubDomain", $dirstatus );
        }
        else {
            if ($MAINDOMAIN) {
                my $dirstatus =
                  check_dir("/var/log/nginx/domains/$MAINDOMAIN");
                if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
                else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
                print_output( "/var/log/nginx/domains/$MAINDOMAIN", $dirstatus );
                my $dirstatus = check_dir( "/var/log/nginx/domains/$QUERY-ssl_log" );
                if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
                else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
                print_output( "/var/log/nginx/domains/$QUERY-ssl_log", $dirstatus );
                my $dirstatus = check_dir( "/var/log/nginx/domains/$QUERY-bytes_log" );
                if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
                else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
                print_output( "/var/log/nginx/domains/$QUERY-bytes_log", $dirstatus );
            }
            else {
                print_output( "/var/log/nginx/domains/", "<span class='status-skipping font-small'>[SKIPPING]</span>" );
            }
        }
    }
    else {
        my $dirstatus = check_dir("/etc/valiases/$QUERY");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/valiases/$QUERY", $dirstatus );

        my $dirstatus = check_dir("/etc/vfilters/$QUERY");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/vfilters/$QUERY", $dirstatus );

        my $dirstatus = check_dir("/etc/vdomainaliases/$QUERY");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/vdomainaliases/$QUERY", $dirstatus );

        my $SubDomain = ( split( /\./, $QUERY ) )[0] . "." . $MAINDOMAIN;
        chomp($SubDomain);
        my $dirstatus=0;
        if ( $isAddon ) {
            $dirstatus = check_dir("/var/cpanel/ssl/apache_tls/$SubDomain");
        }
        else {
            $dirstatus = check_dir("/var/cpanel/ssl/apache_tls/$QUERY");
        }
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/cpanel/ssl/apache_tls/$QUERY", $dirstatus );

        my $dirstatus = check_dir("/var/named/$QUERY.db");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/var/named/$QUERY.db", $dirstatus );

        my $dirstatus = check_dir("/etc/apache2/logs/domlogs/$QUERY");
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/apache2/logs/domlogs/$QUERY", $dirstatus );
        my $dirstatus = check_dir( "/etc/apache2/logs/domlogs/$QUERY-ssl_log" );
        if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/apache2/logs/domlogs/$QUERY-ssl_log", $dirstatus );
        my $dirstatus = check_dir( "/etc/apache2/logs/domlogs/$QUERY-bytes_log" );
        if ( $dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/apache2/logs/domlogs/$QUERY-bytes_log", $dirstatus );

        my $dirstatus =
          check_file_existance( '/etc/named.conf', 'zone "' . $QUERY . '"' );
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/named.conf", $dirstatus );

        my $dirstatus = check_file_existance( "/etc/apache2/conf/httpd.conf", $MAINDOMAIN );
        if   ($dirstatus) { $dirstatus = "<span class='status-exists font-small'>[EXISTS]</span>"; }
        else              { $dirstatus = "<span class='status-missing font-small'>[MISSING]</span>"; }
        print_output( "/etc/apache2/conf/httpd.conf", $dirstatus );
    }

    if ( -e "/var/cpanel/useclusteringdns" ) {
        print "Found DNS Cluster - checking...\n";
        opendir( CLUSTERS, "/var/cpanel/cluster/root/config" );
        my @DNSCLUSTERS = readdir(CLUSTERS);
        closedir(CLUSTERS);
        my ( $dnscluster, $QueryCluster );
        foreach $dnscluster (@DNSCLUSTERS) {
            chomp($dnscluster);
            if (   $dnscluster eq "."
                or $dnscluster eq ".."
                or $dnscluster =~ m/dnsrole/
                or $dnscluster =~ m/json/
                or $dnscluster =~ m/error_log/
                or $dnscluster =~ m/.cache/
                or $dnscluster =~ m/CDN/ )
            {
                next;
            }
            if ($IS_USERNAME) {
                $QueryCluster =
                  qx[ dig +tries=2 +time=5 \@$dnscluster $MAINDOMAIN +short ];
                if ($QueryCluster) {
                    print "<tr><td>$TAB \\_ <span class='text-blue font-small'>$MAINDOMAIN </span>"
                          . "was found in "
                          . $dnscluster
                          . "</td></tr>\n";
                }
                else {
                    print "<tr><td>$TAB \\_ <span class='text-blue font-small'>$MAINDOMAIN </span>"
                          . "NOT found in "
                          . $dnscluster
                          . "</td></tr>\n";
                }
            }
            elsif ($TheAddonDomain) {
                $QueryCluster = qx[ dig +tries=2 +time=5 \@$dnscluster $TheAddonDomain +short ];
                if ($QueryCluster) {
                    print "<tr><td>$TAB \\_ $TheAddonDomain "
                          . "was found in "
                          . $dnscluster
                          . "</td></tr>\n";
                }
                else {
                    print "<tr><td>$TAB \\_ $TheAddonDomain "
                          . "NOT found in "
                          . $dnscluster
                          . "</td></tr>\n";
                }
            }
        }
    }
    	if ( $skipMySQLCruft == 0 ) {
        	my $UserDbsJSON = get_uapi( 'Mysql', 'list_databases', "--user=$username" );
        	print "<tr><td><span class='text-black font-small'>MySQL Databases:</span></td></tr>\n";
        	if ( $UserDbsJSON->{result}->{errors}->[0] ) {
            	print "<tr><td>$TAB <span class='status-missing font-small'>$UserDbsJSON->{result}->{errors}->[0]</span></td></tr>\n";
        	}
        	my $DBCnt = 0;
        	for my $UserDb ( @{ $UserDbsJSON->{result}->{data} } ) {
            	$DBCnt++;
            	print "<tr><td><span class='text-blue font-small'>$TAB \\_ " . $UserDb->{database} . "</span></td></tr>\n";
        	}
        	if ( $DBCnt == 0 ) {
            	print "<tr><td><span class='text-blue font-small'>$TAB \\_ None Found</span></td></tr>\n";
        	}
    	}
    	print "<tr><td><span class='text-blue font-small'>Checking for any MySQL users in mysql.user table</span></td></tr>\n";
	my $dbpassword = Cpanel::MysqlUtils::MyCnf::Basic::getmydbpass('root');
   	my $DBusername = Cpanel::SafeRun::Timed::timedsaferun( 0, 'mysql', 'mysql', '--user=root', "--password=$dbpassword", '-BNe', "SELECT DISTINCT User FROM mysql.user WHERE User LIKE '%$username\\_%'");
   	$DBusername .= Cpanel::SafeRun::Timed::timedsaferun( 0, 'mysql', 'mysql', '--user=root', "--password=$dbpassword", '-BNe', "SELECT DISTINCT User FROM mysql.user WHERE User = '$username'" );
   	my @DBusernames = split( '\n', $DBusername );
   	my $DBUserCnt = @DBusernames;
   	if ( $DBUserCnt > 0 ) {
       	foreach my $NewDBUser (@DBusernames) {
           	chomp($NewDBUser);
           	print "<tr><td><span class='font-small'>$TAB \\_ " . $NewDBUser . "</td></tr>\n";
       	}
   	}
   	else {
       	print "<tr><td><span class='font-small'>$TAB \\_ None</td></tr>\n";
   	}

   	print "<tr><td><span class='text-blue font-small'>Checking for any MySQL users and databases in mysql.db table</span></td></tr>\n";
   	my $DBusername = Cpanel::SafeRun::Timed::timedsaferun( 3, 'mysql', 'mysql', '--user=root', "--password=$dbpassword", '-BNe', "SELECT DISTINCT User,Db FROM mysql.db WHERE User LIKE '%$username\\_%'");
   	$DBusername .= Cpanel::SafeRun::Timed::timedsaferun( 3, 'mysql', 'mysql', '--user=root', "--password=$dbpassword", '-BNe', "SELECT DISTINCT User,Db FROM mysql.db WHERE User = '$username'" );
   	my @DBusernames = split( '\n', $DBusername );
   	my $DBUserCnt   = @DBusernames;
   	if ( $DBUserCnt >= 1 ) {
       	foreach my $NewDBUser (@DBusernames) {
           	chomp($NewDBUser);
			my ( $dbuser, $dbname ) = (split ( /\s+/, $NewDBUser ));
			$dbname =~ s/\\\\//g;
           	print "<tr><td><span class='text-darkblue font-small'>$TAB \\_ DBUser: <span class='text-darkmagenta'>" . $dbuser . " <span class='text-darkblue'> DBName: <span class='text-darkmagenta'>" . $dbname . "</span></td></tr>\n";
       	}
   	}
   	else {
       	print "<tr><td><span class='font-small'>$TAB \\_ None</td></tr>\n";
   	}

   	my $psql_runningJSON = get_whmapi1( 'servicestatus', "service=postgresql" );
   	my $psql_running     = $psql_runningJSON->{data}->{service}->[0]->{running};
   	if ( $skipMySQLCruft == 0 and $psql_running ) {
       	my $UserDbsJSON = get_cpapi2( 'Postgres', 'listdbs', "--user=$username" );
       	my $UserDb;
       	my $DBCnt = 0;
        print "<tr><td><span class='text-black font-small'>PostGreSQL Databases:</span></td></tr>\n";
       	for my $UserDb ( @{ $UserDbsJSON->{cpanelresult}->{data} } ) {
           	for my $DbUser ( @{ $UserDb->{userlist} } ) {
               	$DBCnt++;
               	print "<tr><td><span class='font-small'>$TAB \\_ " . $UserDb->{db} . "</td></tr>\n";
           	}
       	}
       	if ( $DBCnt == 0 ) {
           	print "<tr><td><span class='font-small'>$TAB \\_ None Found</td></tr>\n";
       	}
    	}
    	border();
	print "</table>";
	print "<tr><td><p><form action='acctinfo.cgi' method='post'>";
	print "<input type=submit value='Return' class='form-button'>";
	print "</form></td></tr>";
}

exit;

sub check_file_existance {
    my $TheFile         = $_[0];
    my $TheSearchString = $_[1];
    my @TheFileData     = undef;
    my $DataLine        = "";

    my $FoundLine = "";
    if ( -e ($TheFile) ) {

        $FoundLine = qx[ grep -w '$TheSearchString' $TheFile ];
        if   ($FoundLine) { return 1; }
        else              { return 0; }
    }
}

sub print_output {
    my $DisplayName = $_[0];
    my $TheStatus   = $_[1];
	my $StatColor = ( $TheStatus =~ m/EXISTS/ ) ? "text-darkgreen" : "text-darkred";
	print "<tr><td><span class='text-black font-large'>$DisplayName</span></td>";
	print "<td><span class='$StatColor font-small'>$TheStatus</span></td></tr>\n";
}

sub check_dir() {
    my $Dir2Check = $_[0];
    if ( -e ($Dir2Check) ) {
        return 1;
    }
    else {
        return 0;
    }
}

sub uniq {
    my %seen;
    grep !$seen{$_}++, @_;
}

sub chk_mail_suspend {
    my $tcAccount = shift;
    my $SMTPUserSusp = qx[ grep '^$tcAccount' /etc/outgoing_mail_suspended_users ];
    if ($SMTPUserSusp) {
        print RED "<span class='text-redThe $tcAccount account is suspended from sending email.</span><br>\n";
    }
}

sub chk_mail_hold {
    my $tcAccount = shift;
    my $SMTPUserSusp = qx[ grep '^$tcAccount' /etc/outgoing_mail_hold_users ];
    if ($SMTPUserSusp) {
        print RED "<span class='text-redThe $tcAccount account is on hold from sending email.</span><br>\n";
    }
}

sub chk_login_disabled {
    my $shadow_file = shift;
    my $tcLocalPart = shift;
    my $localpart = $tcLocalPart . ":!!";
    if ( -s "$shadow_file/shadow" ) {
        open( my $fh, '<', "$shadow_file/shadow" ) or die( $! );
        while( <$fh> ) {
            if ( $_ =~ m/^$localpart$/ ) {
                print "<span class='text-red sans-indent'>\\_ Login for this account has been disabled/suspended\n";
            }
        }
        close( $fh );
    }
}

sub chk_suspended_mail {
    my $filter_file = shift;
    if ( -s "$filter_file/filter" ) {
        open( my $fh, '<', "$filter_file/filter" ) or die( $! );
        while( <$fh> ) {
            if ( $_ =~ m/SUSPEND RECEPTION OF NEW MESSAGES/ ) {
                print "<span class='text-red sans-indent'>\\_ Receiving mail for this account has been suspended\n";
            }
        }
        close( $fh );
    }
}


sub alltrim() {
    my $string2trim = $_[0];
    $string2trim =~ s/^\s*(.*?)\s*$/$1/;
    return $string2trim;
}

sub border {
    print "<tr><td><span class='text-blue'>===================================================================================</span></td></tr>\n";
    return;
}

sub smborder {
    print "<span class='text-darkcyan'>-----------------------------------------------------------------------------------</span><br>\n";
    return;
}

sub get_json_from_command {
    my @cmd = @_;
    return Cpanel::JSON::Load(
        Cpanel::SafeRun::Timed::timedsaferun( 30, @cmd ) );
}

sub get_whmapi1 {
    return get_json_from_command( 'whmapi1', '--output=json', @_ );
}

sub get_uapi {
    return get_json_from_command( 'uapi', '--output=json', @_ );
}

sub get_cpapi2 {
    return get_json_from_command( 'cpapi2', '--output=json', @_ );
}

sub timed_run {
    my ( $timer, @PROGA ) = @_;
    return _timedsaferun( $timer, 0, @PROGA );
}

sub timed_run_noerr {
    my ( $timer, @PROGA ) = @_;
    return _timedsaferun( $timer, 1, @PROGA );
}

sub getMXrecord {
    my $tcDomain = shift;
    my $rr;
    my @NEWMX;
    my $res = Net::DNS::Resolver->new;
    my @mx  = mx( $res, $tcDomain );
    if (@mx) {
        foreach $rr (@mx) {
            push( @NEWMX, $rr->exchange );
        }
        return @NEWMX;
    }
    else {
        return "NONE";
    }
}

sub _timedsaferun {
    my ( $timer, $stderr_to_stdout, @PROGA ) = @_;
    return '' if ( substr( $PROGA[0], 0, 1 ) eq '/' && !-x $PROGA[0] );
    $timer = $timer       ? $timer       : 25;
    $timer = $OPT_TIMEOUT ? $OPT_TIMEOUT : $timer;
    my $output;
    my $complete = 0;
    my $pid;
    my $fh;
    eval {
        local $SIG{'__DIE__'} = 'DEFAULT';
        local $SIG{'ALRM'}    = sub {
            $output = '';
            print 'Timeout while executing: ' . join( ' ', @PROGA ) . "\n";
            die;
        };
        alarm($timer);
        if ( $pid = open( $fh, '-|' ) ) {
            local $/;
            $output = readline($fh);
            close($fh);
        }
        elsif ( defined $pid ) {
            open( STDIN, '<', '/dev/null' );
            if ($stderr_to_stdout) {
                open( STDERR, '>&', 'STDOUT' );
            }
            else {
                open( STDERR, '>', '/dev/null' );
            }
            exec(@PROGA) or exit 1;
        }
        else {
            print 'Error while executing: [ ' . join( ' ', @PROGA ) . ' ]: ' . $! . "\n";
            alarm 0;
            die;
        }
        $complete = 1;
        alarm 0;
    };
    alarm 0;
    if ( !$complete && $pid && $pid > 0 ) {
        kill( 15, $pid );
        sleep(2);
        kill( 9, $pid );
    }
    return defined $output ? $output : '';
}
