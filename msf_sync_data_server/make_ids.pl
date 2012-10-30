#!/usr/bin/env perl

use strict;
use warnings;
use Data::Dumper;

sub csv_split { #split /,/, @_ ? shift() : $_ }
    local $_ = @_ ? shift() : $_;
    chomp;
    $_ .= ',';
    my @r;
    while( s/^([^",][^,]*),|"((?:[^"]*|"")*)",|^,// ) {
        my $v = ($1 or $2 or '');
        $v =~ s/""/"/g if $2;
        push @r, $v;
    }
    return @r;
}

my @files;

while( $_ = shift @ARGV ) {
    open IN,$_ or die "Cannot open $_: $!\n";
    my %f = (datas => [], file => $_);
    $_ = <IN>;
    $f{header} = [csv_split($_)];
    if( grep {$_ eq 'id'} @{$f{header}} ) {
        warn "Skipping file `$f{file}'\n";
        next;
    }
    my $cols = $#{$f{header}};
    while( <IN> ) {
        my @line = csv_split;
        push @{$f{datas}}, {map {$f{header}->[$_], $line[$_]} 0..$cols};
        #warn join('###', @line)."\n";
    }
    push @files, \%f;
    #warn Dumper($f{header});
}

for my $f (@files) {
    my %known;
    for my $data (@{$f->{datas}}) {
        #die Dumper($data);
        $_ = lc($data->{name} or $data->{sequence});
        tr/ ./__/;
        s/[^a-z0-9-_]//g;
        s/__+/_/g;
        $data->{id} = $_;
        die "This tag already exists: $_\n" if exists $known{$_};
        $known{$_} = 1;
    }
    unshift @{$f->{header}}, 'id';
    open OUT,'>',$f->{file} or die "Cannot write to `$f->{file}': $!\n";
    print OUT join(',', map {s/"/""/;"\"$_\""} @{$f->{header}})."\n";
    for my $data (@{$f->{datas}}) {
        $_ = join(',', map {s/"/""/;"\"$data->{$_}\""} @{$f->{header}})."\n";
        print OUT;
    }
    #warn Dumper(\%known);
}

#warn Dumper(@files);

