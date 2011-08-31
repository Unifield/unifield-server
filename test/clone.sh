#!/bin/sh

# Quick workaround to speedup test databases (re)initialization

set -x

dropdb msf_c2
dropdb msf_c3
dropdb msf_p1
dropdb msf_p2
dropdb msf_p3

createdb msf_c2
createdb msf_c3
createdb msf_p1
createdb msf_p2
createdb msf_p3

pg_dump --no-owner msf_c1 > msf_c1.dump
#dropdb msf_c1
#createdb msf_c1
#psql msf_c1 < msf_c1.dump > msf_c1.log

psql msf_c2 < msf_c1.dump > msf_c2.log
psql msf_c3 < msf_c1.dump > msf_c3.log
psql msf_p1 < msf_c1.dump > msf_p1.log
psql msf_p2 < msf_c1.dump > msf_p2.log
psql msf_p3 < msf_c1.dump > msf_p3.log

set +x

