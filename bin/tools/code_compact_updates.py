# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras

locale.setlocale(locale.LC_ALL, '')
conn = psycopg2.connect("dbname=DAILY_SYNC_SERVER-COMPRESSED-2-20160303-073301")   # replace with your own DB

cr = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# here it takes already a lot of time...
cr.execute("""
SELECT * FROM
sync_server_update ORDER BY sequence, id
""")
to_continue = True
print '1/4 Start compressing the updates, this may take a while ...'
rows_already_seen = {}

# we will delete all the pulled update which are not master data and use active rule
# but it is safer to keep some safety margin by keeping some more updates
SEQUENCE_MORE_TO_KEEP = 2000

# the objects with the folowing sdref will be ignored
SDREF_TO_EXCLUDE = [
]

# the objects with the folowing model will be ignored
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
        # this row has never been seen
        if key not in rows_already_seen:
            if row['is_deleted']:
                # it is better to always keep the last deleted update
                # if the updated should be deleted, store the id as negative
                # value
                rows_already_seen[key] = row['id'] * -1
            else:
                rows_already_seen[key] = row['id']

        # this row has already been seen, replace the last value with the new one
        else:
            if row['is_deleted']:
                if rows_already_seen[key] < 0:  # the previous update was also a delete
                    # so delete the previous update to keep only the last one
                    cr2.execute('DELETE FROM sync_server_update WHERE id = %s',
                                (-1 * rows_already_seen[key],))
                    deleted_update_ids.append(-1 * rows_already_seen[key])
                    # and keep the current
                    rows_already_seen[key] = row['id'] * -1
                else:   # the previous was not a delete, the current and the
                        # previous should be deleted
                    cr2.execute('DELETE FROM sync_server_update WHERE id in %s',
                                ((rows_already_seen[key], row['id']),))
                    deleted_update_ids.append(rows_already_seen[key])
                    deleted_update_ids.append(row['id'])
                    # remove the already seen key
                    rows_already_seen.pop(key)
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

                # delete the update
                cr2.execute('DELETE FROM sync_server_update WHERE id = %s', (row['id'],))
                deleted_update_ids.append(row['id'])
                cr2.execute(sql_query, values_to_set + [rows_already_seen[key]])

            conn.commit()

print '1/4 Compression finished. %s update deleted.' % locale.format('%d', len(deleted_update_ids), 1)
cr2.execute('SELECT MIN(last_sequence) FROM sync_server_entity WHERE last_sequence !=0', ())
smallest_last_sequence = cr2.fetchone()[0]
smallest_last_sequence -= SEQUENCE_MORE_TO_KEEP

cr2.execute("SELECT id FROM sync_server_sync_rule WHERE active='t' AND master_data='f'", ())
no_master_data_active_rules = [x[0] for x in cr2.fetchall()]

print '2/4 Start deleting updates with active rules and not master_data where sequence is < %s ...' % smallest_last_sequence
cr2.execute('SELECT id FROM sync_server_update WHERE sequence < %s and rule_id IN %s', (smallest_last_sequence, tuple(no_master_data_active_rules),))
update_no_master_ids = [x[0] for x in cr2.fetchall()]
# split the list has it may be huge
for chunk in [update_no_master_ids[x:x+1000] for x in xrange(0, len(update_no_master_ids), 1000)]:
    cr2.execute('DELETE FROM sync_server_update WHERE id IN %s',
                (tuple(chunk),))
    conn.commit()
print '2/4 %s updates deleted.' % locale.format('%d', len(update_no_master_ids), 1)

print '3/4 Start deleting the updates related to inactive rules...'
cr2.execute("SELECT id FROM sync_server_sync_rule WHERE active='f'", ())
inactive_rules = [x[0] for x in cr2.fetchall()]
cr2.execute('SELECT id FROM sync_server_update WHERE rule_id IN %s', (tuple(inactive_rules),))
update_inactive_rules = [x[0] for x in cr2.fetchall()]
# split the list has it may be huge
for chunk in [update_inactive_rules[x:x+1000] for x in xrange(0, len(update_inactive_rules), 1000)]:
    cr2.execute('DELETE FROM sync_server_update WHERE id IN %s',
                (tuple(chunk),))
    conn.commit()
print '3/4 %s updates related to inactive rules deleted.' % len(update_inactive_rules)

total_update_ids = deleted_update_ids + update_no_master_ids + update_inactive_rules
total_update_count = len(total_update_ids)
print '\n\nTotal updates deleted = %s\n\n' % locale.format('%d', total_update_count, 1)

if total_update_ids:
    print '4/4 Start deleting of the related sync_server_entity_rel...'
    cr2.execute('SELECT id FROM sync_server_entity_rel WHERE update_id IN %s',
                (tuple(total_update_ids),))
    entity_ids = [x[0] for x in cr2.fetchall()]
    entity_count = len(entity_ids)
    # split the list has it may be huge
    for chunk in [entity_ids[x:x+1000] for x in xrange(0, len(entity_ids), 1000)]:
        cr2.execute('DELETE FROM sync_server_entity_rel WHERE id IN %s',
                    (tuple(chunk),))
        conn.commit()
    print '4/4 sync_server_entity_rel deleted : %s' % locale.format('%d', entity_count, 1)
