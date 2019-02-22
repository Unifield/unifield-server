import psycopg2
import time

start_time = time.time()
db_conn = psycopg2.connect("dbname=uf8-0rc3_SYNC_SERVER_LIGHT_WITH_MASTER_1")
cr = db_conn.cursor()
ct = {'keep2': {}, 'delete': {}, 'single': {}}


# get id of HQ instances
cr.execute("select id from sync_server_entity where name in ('HQ_OCA', 'OCG_HQ', 'OCBHQ')")
hq_ids = tuple([x[0] for x in cr.fetchall()])
cr.execute('ANALYZE')

assert len(hq_ids) == 3

cr.execute("select min(last_sequence) from sync_server_entity where state != 'invalidated'")
min_seq = cr.fetchone()[0] - 1

print "Min seq", min_seq

# updates linked to inactive rules are dead
cr.execute("delete from sync_server_update where rule_id in (select id from sync_server_sync_rule where active='f')")
ct['inactive_rules'] = cr.rowcount

# delete update: delete previous updates
cr.execute("""select source, sdref, max(sequence), model from sync_server_update
where source in %s and
model in ('ir.translation', 'ir.model.access', 'msf_field_access_rights.field_access_rule_line', 'ir.rule', 'supplier.catalogue.line', 'product.list.line') and
is_deleted='t' and
sequence < %s
group by source, sdref, model""", (hq_ids, min_seq))
for x in cr.fetchall():
    ct['delete'].setdefault(x[3], 0)
    # keep the delete update: for records created by data.xml and update not yet pulled by instances
    if x[3] in ('supplier.catalogue.line', 'product.list.line'):
        # delete also the delete update, and all previous updates sent by all instances
        cr.execute("delete from sync_server_update where sdref=%s and sequence <= %s and model=%s", (x[1], x[2], x[3]))
    else:
        cr.execute("delete from sync_server_update where source=%s and sdref=%s and sequence < %s and model=%s", (x[0], x[1], x[2], x[3]))
    ct['delete'][x[3]] += cr.rowcount


# multiple updates for the same record: keep 1st (if other updates are linked to this one) and last
cr.execute("""select source, sdref, min(sequence), max(sequence), model from sync_server_update
where source in %s and
model in ('product.product', 'product.nomenclature', 'hr.employee', 'res.currency.rate') and
is_deleted='f' and
sequence < %s
group by source, sdref, model
having(count(*) >2)""", (hq_ids, min_seq))
for x in cr.fetchall():
    ct['keep2'].setdefault(x[4], 0)
    cr.execute("delete from sync_server_update where source=%s and sdref=%s and sequence not in (%s, %s) and model=%s and is_deleted='f' and sequence < %s", (x[0], x[1], x[2], x[3], x[4], min_seq))
    ct['keep2'][x[4]] += cr.rowcount

# multiple updates, keep only the last update as we know these xmlids are not used in other sync updates
cr.execute("""select source, sdref, max(sequence), model from sync_server_update where 
source in %s and
model in ('ir.translation', 'ir.model.access', 'msf_field_access_rights.field_access_rule_line', 'ir.rule', 'supplier.catalogue.line', 'product.list.line') and
is_deleted='f' and
sequence < %s
group by source, sdref, source, model
having(count(*) >1)""", (hq_ids, min_seq))
for x in cr.fetchall():
    ct['single'].setdefault(x[3], 0)
    cr.execute("delete from sync_server_update where source=%s and sdref=%s and sequence != %s and model=%s and sequence < %s", (x[0], x[1], x[2], x[3], min_seq))
    ct['single'][x[3]] += cr.rowcount


# delete not-masters updates older than 18 months
#cr.execute("""delete from sync_server_update u
#where u.rule_id in
#  (select id from sync_server_sync_rule where master_data='f')
#and u.create_date < now() - interval '18 months'
#""")
#ct['month18'] = cr.rowcount

# delete orphean "pulled by" records
#cr.execute("delete from sync_server_entity_rel where id in (select r.id from sync_server_entity_rel r left join sync_server_update u on u.id=r.update_id where u.id is null)")
#ct['pulled_by'] = cr.rowcount
print ct

#print '****** rollback'
#db_conn.rollback()
db_conn.commit()

print 'Time', time.time() - start_time
