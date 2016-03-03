# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras

locale.setlocale(locale.LC_ALL, '')
conn = psycopg2.connect("dbname=DAILY_SYNC_SERVER-COMPRESSED-20160303-073301")   # replace with your own DB

cr = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# here it takes already a lot of time...
cr.execute("""
SELECT * FROM
sync_server_update ORDER BY sequence, id
""")
to_continue = True
print 'Starting compressing the updates, this may take a while ...'
rows_already_seen = {}

# we will delete all the pulled update which are not master data and use active rule
# but it is safer to keep some safety margin by keeping some more updates
SEQUENCE_TO_REMOVE = 2000

# the objects with the folowing sdref will be ignored
SDREF_TO_EXCLUDE = [
]

MODEL_TO_EXCLUDE = [
]

deleted_update_ids = []

while to_continue:
    multiple_updates = cr.fetchmany(1000)
    if not multiple_updates:
        to_continue = False
        break

    for row in multiple_updates:
        if row['sdref'] in SDREF_TO_EXCLUDE or\
           row['model'] in MODEL_TO_EXCLUDE:
            continue
        key = row['sdref'], row['rule_id'], row['source']
        # we have never seen this row
        if key not in rows_already_seen:
            if row['is_deleted']:
                # it is better to always keep the last deleted update
                rows_already_seen[key] = row['id'] * -1  # if the updated
                # should be deleted, store the id as negative value
            else:
                rows_already_seen[key] = row['id']

        # we already seen this row, replace the last value with the new one
        else:
            if row['is_deleted']:
                # if the previous update was also a delete
                if rows_already_seen[key] < 0:
                    # delete the previous
                    cr2.execute('DELETE FROM sync_server_update WHERE id = %s',
                                (-1 * rows_already_seen[key],))
                    deleted_update_ids.append(-1 * rows_already_seen[key])
                    # and keep the current
                    rows_already_seen[key] = row['id'] * -1
            else:
                # replace the content of the previous update with the current
                items = filter(lambda x: x[0] not in ['session_id', 'id', 'sdref',
                                                      'rule_id', 'source', 'sequence',
                                                      'create_date', 'write_uid',
                                                      'create_uid'], list(row.iteritems()))

                fields_to_set = map(lambda x: x[0], items)
                values_to_set = map(lambda x: x[1], items)

                fields = ','.join(map(lambda x: '%s = %%s' % x, fields_to_set))
                sql_query = 'UPDATE sync_server_update SET %s WHERE id = %%s' % fields

                cr2.execute('DELETE FROM sync_server_update WHERE id = %s', (row['id'],))
                deleted_update_ids.append(row['id'])
                cr2.execute(sql_query, values_to_set + [rows_already_seen[key]])

            conn.commit()

print 'Compression finished. Update deleted : %s' % locale.format('%d', len(deleted_update_ids), 1)
cr.execute('SELECT MIN(last_sequence) FROM sync_server_entity WHERE last_sequence !=0', ())
smallest_last_sequence = cr.fetchone()[0]
smallest_last_sequence -= SEQUENCE_TO_REMOVE

cr.execute("SELECT id FROM sync_server_sync_rule WHERE active='t' AND master_data='f'", ())
no_master_data_active_rules = [x[0] for x in cr.fetchall()]

print 'Start deleting updates with active rules and not master_data where sequence is < %s ...' % smallest_last_sequence
cr.execute('SELECT id FROM sync_server_update WHERE sequence < %s and rule_id IN %s', (smallest_last_sequence, tuple(no_master_data_active_rules),))
update_no_master_ids = [x[0] for x in cr.fetchall()]
cr2.execute('DELETE FROM sync_server_update WHERE id IN %s',
            (tuple(update_no_master_ids),))
print '%s updates to delete' % locale.format('%d', len(update_no_master_ids), 1)

total_update_count = len(deleted_update_ids) + len(update_no_master_ids)
print '\n\nTotal updates deleted = %s' % locale.format('%d', total_update_count, 1)

print 'Starting delete of the related sync_server_entity_rel...'
cr.execute('SELECT COUNT(*) FROM sync_server_entity_rel WHERE update_id IN %s',
           (tuple(deleted_update_ids+update_no_master_ids),))
entity_count = cr.fetchone()[0]
cr2.execute('DELETE FROM sync_server_entity_rel WHERE update_id IN %s',
            (tuple(deleted_update_ids+update_no_master_ids),))
print 'sync_server_entity_rel deleted : %s' % locale.format('%d', entity_count, 1)
