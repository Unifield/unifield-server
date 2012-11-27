#!/usr/bin/env perl

use strict;
use warnings;

use Data::Dumper;
use XML::RPC;

die "Please enter host, port and database\n" if @ARGV < 3;

my($host,$port,$db) = @ARGV;
my($username,$password) = ('admin', 'admin');
my $uid;

my $url = "http://$host:$port/xmlrpc";

my $common_proxy = XML::RPC->new($url.'/common') or die $!;
my $object_proxy = XML::RPC->new($url.'/object') or die $!;

sub execute { $object_proxy->call('execute', $db, $uid, $password, @_) }

# 0. Parse command-line args
my($line_count) = @ARGV[3..$#ARGV];
die "Please specify number of move lines to create!\n" unless $line_count;

# 1. Login
$uid = $common_proxy->call('login', $db, $username, $password);
print "Logged in as $username (uid: $uid)\n";

# 2. Pick account_id
my $account_ids = execute('account.account', 'search', ['!', ['type','in',[qw/view closed/]]]);
die Dumper($account_ids) unless ref $account_ids eq 'ARRAY';
die "No account found!" unless @$account_ids;
my $account_picked = shift(@$account_ids);
print "account.account picked: $account_picked\n";

# 3. Pick period_id
my $period_ids = execute('account.period', 'search', [[qw/state = draft/]]);
die Dumper($period_ids) unless ref $period_ids eq 'ARRAY';
die "No period found!" unless @$period_ids;
my $period_picked = shift(@$period_ids);
print "account.period picked: $period_picked\n";

# 4. Pick journal_id
my $journal_ids = execute('account.journal', 'search', []);
die Dumper($journal_ids) unless ref $journal_ids eq 'ARRAY';
die "No journal found!" unless @$journal_ids;
my $journal_picked = shift(@$journal_ids);
print "account.journal picked: $journal_picked\n";

# 5. Pick instance_id
my $instance_ids = execute('msf.instance', 'search', [['parent_id.instance','=',$db]]);
die Dumper($instance_ids) unless ref $instance_ids eq 'ARRAY';
die "No instance found!" unless @$instance_ids;
my $instance_picked = shift(@$instance_ids);
print "msf.instance picked: $instance_picked\n";

# 6. Create move_id
my $move_id;
$move_id = execute('account.move', 'create',
    {   name => 'TEST',
        period_id => $period_picked,
        journal_id => $journal_picked,
        state => 'draft',
        date => '2010-10-10 10:10:10.010',
    });
die Dumper($move_id) if ref $move_id;
print "account.move picked: $move_id\n";

# 6. Create account.move.line's
my @created_line_ids;
print "Creating $line_count records...\n";
for my $i (1..$line_count) {
    my $line_id = execute('account.move.line', 'create',
        {   name => 'LOAD_'.$i,
            account_id => $account_picked,
            period_id => $period_picked,
            journal_id => $journal_picked,
            instance_id => $instance_picked,
            move_id => $move_id,
        });
    die Dumper($line_id) if ref $line_id;
    push @created_line_ids, $line_id;
}
print "account.move.line created: ".scalar(@created_line_ids)."\n";

# 7. Post move_id
print "set account.move id=$move_id to posted\n";
execute('account.move', 'write', [$move_id], {state => 'posted'});
