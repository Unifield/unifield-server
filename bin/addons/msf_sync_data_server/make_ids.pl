#!/usr/bin/env perl
#
#  This small script add column 'id' to CSV files based on column 'name'
#
#  Usage: ./make_ids.pl <csv_file1> <csv_file2> ...
#

use strict;
use warnings;

## Small helpful function to split lines into rows
## Accept only these formats:
##   - value1,value2,value3
##   - "value1","value2","value3"
sub csv_split {
    local $_ = @_ ? shift() : $_;
    s/\v+$//;
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

## Parse CSV file
while( $_ = shift @ARGV ) {
    open IN,$_ or die "Cannot open $_: $!\n";
    my %f = (datas => [], file => $_);
    $_ = <IN>;
    $f{header} = [csv_split($_)];
    if( grep {$_ eq 'id'} @{$f{header}} ) {
        warn "The file `$f{file}' already have a column id, I will re-calculate it.\n";
    }
    my $cols = $#{$f{header}};
    while( <IN> ) {
        my @line = csv_split;
        push @{$f{datas}}, {map {$f{header}->[$_], $line[$_]} 0..$cols};
    }
    push @files, \%f;
}

## Create column 'id' and write back to the file
for my $f (@files) {
    my %known;
    for my $data (@{$f->{datas}}) {
        $_ = lc($data->{name} or $data->{sequence});
        tr/ ./__/;
        s/[^a-z0-9_-]//g;
        s/__+/_/g;
        $data->{id} = $_;
        die "This tag already exists: $_\n" if exists $known{$_};
        $known{$_} = 1;
    }
    unshift @{$f->{header}}, 'id' unless grep {$_ eq 'id'} @{$f->{header}};
    open OUT,'>',$f->{file} or die "Cannot write to `$f->{file}': $!\n";
    print OUT join(',', map {s/"/""/;"\"$_\""} @{$f->{header}})."\n";
    for my $data (@{$f->{datas}}) {
        $_ = join(',', map {s/"/""/;"\"$data->{$_}\""} @{$f->{header}})."\n";
        print OUT;
    }
}

