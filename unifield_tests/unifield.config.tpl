[Server]
url: localhost
port: 8069

[DB]
db_prefix: us-8_
# when dbs are coming from a given RB, set the INSTANCE prefix to retrieve
# prop instances correctly (not matching db names)
# comment it if instance prefix same as db_prefix
instance_prefix: us-8_
username: admin
password: admin
# If tempo_mkdb is True, it means you use mkdb from OpenERP to create DB. If not, you use tempo's one.
tempo_mkdb: 1
# RW give the SUFFIX of Remote Warehouse database. DO NOT USE PREFIX
RW: 
project_level: 2
