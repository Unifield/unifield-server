# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras
import time
import oerplib
import traceback

start_time = time.time()
intermediate_time = start_time

DELETE_NO_MASTER=True
DELETE_INACTIVE_RULES=True
COMPACT_UPDATE=True
DELETE_ENTITY_REL=True  # not recommanded to change it to False because it can
                        # remove delete only entity_rel related to currently
                        # deleted updates
UPDATE_TO_FETCH = 1000

# we will delete all the pulled update which are not master data and use active rule
# but it is safer to keep some safety margin by keeping some more updates
SAFE_MARGIN_SEQUENCE_TO_KEEP = 2000

# the objects with the folowing sdref will be ignored
SDREF_TO_EXCLUDE = [
]

# the objects with the folowing model will be ignored
MODEL_TO_EXCLUDE = [
        'financing.contract.contract', # maybe this problem need to be
                                       # examinated with Duy
]

DB_NAME = 'DAILY_SYNC_SERVER-COMPRESSED-9-20160303-073301'   # replace with your own DB

locale.setlocale(locale.LC_ALL, '')
conn = psycopg2.connect("dbname=%s" % DB_NAME)

cr = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr3 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

oerp = oerplib.OERP('127.0.0.1', DB_NAME, protocol='netrpc', port='10131', timeout=3600)
oerp.login('admin', 'admin', DB_NAME)

rows_already_seen = {}
deleted_update_ids = []
not_deleted_update = 0
sync_server_update = oerp.get('sync.server.update')
current_cursor = 0
total_update_ids = set()
cr2.execute("""SELECT COUNT(*) FROM sync_server_update""", ())
number_of_update = cr2.fetchone()[0]

def print_time_elapsed(start_time, stop_time, step=''):
    elapsed_time = stop_time - start_time
    minute, second = divmod(elapsed_time, 60)
    hour, minute = divmod(minute, 60)
    print "%s Elapsed time : %d:%02d:%02d" % (step, hour, minute, second)

if DELETE_NO_MASTER:
    intermediate_time = time.time()
    # start by deleting the the update with active rules and no master_data
    # then there will be much less updates to parse with heaver code after
    cr2.execute("""SELECT MIN(last_sequence) FROM sync_server_entity
                WHERE last_sequence !=0""", ())
    smallest_last_sequence = cr2.fetchone()[0]
    smallest_last_sequence -= SAFE_MARGIN_SEQUENCE_TO_KEEP
    print '1/4 Start deleting updates with active rules and not master_data'\
          ' where sequence is < %s ...' % smallest_last_sequence
    cr2.execute("SELECT id FROM sync_server_sync_rule WHERE active='t' AND master_data='f'", ())
    no_master_data_active_rules = [x[0] for x in cr2.fetchall()]
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE sequence < %s and rule_id IN %s""",
                (smallest_last_sequence, tuple(no_master_data_active_rules),))
    to_continue = True
    update_no_master_ids = []
    while to_continue:
        multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
        if not multiple_updates:
            to_continue = False
            break
        update_no_master_ids = [x[0] for x in multiple_updates]
        cr3.execute('DELETE FROM sync_server_update WHERE id IN %s',
                    (tuple(update_no_master_ids),))
        conn.commit()
        total_update_ids = total_update_ids.union(update_no_master_ids)
    print '1/4 %s updates deleted.' % locale.format('%d', cr2.rowcount, 1)
    print_time_elapsed(intermediate_time, time.time(), '1/4')
    del multiple_updates
    del update_no_master_ids

if DELETE_INACTIVE_RULES:
    intermediate_time = time.time()
    print '2/4 Start deleting the updates related to inactive rules...'
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE rule_id IN
                (SELECT id FROM sync_server_sync_rule WHERE active='f')""")
    update_inactive_rules_count = cr2.rowcount
    to_continue = True
    update_inactive_rules = []
    while to_continue:
        multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
        if not multiple_updates:
            to_continue = False
            break
        update_inactive_rules = [x[0] for x in multiple_updates]
        cr3.execute('DELETE FROM sync_server_update WHERE id IN %s',
                    (tuple(update_inactive_rules),))
        conn.commit()
        total_update_ids = total_update_ids.union(update_inactive_rules)
    print '2/4 %s updates related to inactive rules deleted.' % locale.format('%d', update_inactive_rules_count, 1)
    print_time_elapsed(intermediate_time, time.time(), '2/4')
    del multiple_updates
    del update_inactive_rules

if COMPACT_UPDATE:
    intermediate_time = time.time()
    # create a dict of the entity branch id
    # the highest parent will be considered as branch id (ie. OCBHQ id)
    sync_server_entity = oerp.get('sync.server.entity')
    cr2.execute("""SELECT id FROM sync_server_entity""", ())
    sync_server_entity_id_list = [x[0] for x in cr2.fetchall()]
    entity_branch_name = {}
    def get_recursive_parent(entity_id):
        entity = sync_server_entity.browse(entity_id)
        if entity.parent_id:
            return get_recursive_parent(entity.parent_id.id)
        else:
            return entity.id

    for entity_id in sync_server_entity_id_list:
        highest_parent = get_recursive_parent(entity_id)
        entity_branch_name[entity_id]=highest_parent

    # here it takes already a lot of time...
    cr.execute("""
    SELECT * FROM
    sync_server_update ORDER BY sequence, id
    """)
    total_updates = cr.rowcount
    to_continue = True
    print '3/4 Start compressing the updates, this may take a while ...'
    while to_continue:
        multiple_updates = cr.fetchmany(UPDATE_TO_FETCH)
        current_cursor += UPDATE_TO_FETCH
        if not multiple_updates:
            to_continue = False
            break

        for row in multiple_updates:
            if row['sdref'] in SDREF_TO_EXCLUDE or\
               row['model'] in MODEL_TO_EXCLUDE:
                continue
            #key = row['sdref'], row['rule_id'], row['source']
            key = row['sdref'], row['rule_id'], entity_branch_name[row['source']]
            # this row has never been seen
            if key not in rows_already_seen:
                if row['is_deleted']:
                    # it is better to always keep the last deleted update
                    # if the updated should be deleted, store the id as negative
                    # value
                    rows_already_seen[key] = (row['id'], -1, row['sequence'])
                else:
                    rows_already_seen[key] = (row['id'], 1, row['sequence'])

            # this row has already been seen, replace the last value with the new one
            else:
                previous_update_id = rows_already_seen[key][0]
                if row['is_deleted']:
                    if rows_already_seen[key][1] < 0:  # the previous update was also a delete
                        # so delete the previous update to keep only the last one
                        cr2.execute('DELETE FROM sync_server_update WHERE id = %s',
                                    (rows_already_seen[key][0],))
                        deleted_update_ids.append(rows_already_seen[key][0])
                        # and keep the current
                        rows_already_seen[key] = (row['id'], -1, row['sequence'])
                    else:   # the previous was not a delete, the current and the
                            # previous should be deleted
                        cr2.execute('DELETE FROM sync_server_update WHERE id in %s',
                                    ((rows_already_seen[key][0], row['id']),))
                        deleted_update_ids.append(rows_already_seen[key][0])
                        deleted_update_ids.append(row['id'])
                        # remove the already seen key
                        del rows_already_seen[key]
                else:
                    # check no reference to other object change between the
                    # previous update and the current
                    old_update = sync_server_update.browse(previous_update_id)
                    previous_values = not old_update.is_deleted and eval(old_update.values) or []
                    current_values = eval(sync_server_update.browse(row['id']).values)
                    diff = set(current_values).difference(previous_values)
                    ref_diff = [x.split('sd.')[1] for x in diff if
                            isinstance(x, (str,unicode)) and  x.startswith('sd.')]

                    # before to do any replacement, check that the object in this
                    # update is not pointing to other object created after the
                    # update where it will moved to.
                    if ref_diff:
                        # if the sequence number where the update will be moved is
                        # smaller thant the sequence number of the refered object,
                        # the update will not be compressed

                        sequence_to_moved_on = rows_already_seen[key][2]
                        cr2.execute('''SELECT id
                                    FROM sync_server_update
                                    WHERE sequence > %s AND sdref IN %s''',
                                    (sequence_to_moved_on, tuple(ref_diff)))
                        if cr2.fetchone():
                            rows_already_seen[key] = (row['id'], 1, row['sequence'])
                            not_deleted_update += 1
                            continue  # if anything is matching, do not compress

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
                    cr2.execute(sql_query, values_to_set + [rows_already_seen[key][0]])

                conn.commit()

    # free memory
    cr.close()
    del multiple_updates
    del rows_already_seen
    print '%s not deleted updates.' % not_deleted_update
    print '3/4 Compression finished. %s update deleted.' % locale.format('%d', len(deleted_update_ids), 1)
    print_time_elapsed(intermediate_time, time.time(), '3/4')
    total_update_ids = total_update_ids.union(deleted_update_ids)
    del deleted_update_ids

total_update_count = len(total_update_ids)
print '\n\nTotal updates deleted = %s/%s\n\n' % (locale.format('%d',
    total_update_count, 1), locale.format('%d', number_of_update, 1))

if DELETE_ENTITY_REL:
    to_continue = True
    if total_update_ids:
        intermediate_time = time.time()
        print '4/4 Start deleting of the related sync_server_entity_rel...'
        cr2.execute('SELECT id FROM sync_server_entity_rel WHERE update_id IN %s',
                    (tuple(total_update_ids),))
        entity_count = cr2.rowcount
        # split the list has it may be huge
        while to_continue:
            multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
            if not multiple_updates:
                to_continue = False
                break

            entity_ids = [x[0] for x in multiple_updates]
            cr3.execute('DELETE FROM sync_server_entity_rel WHERE id IN %s',
                        (tuple(entity_ids),))
            conn.commit()
        print '4/4 sync_server_entity_rel deleted : %s' % locale.format('%d', entity_count, 1)
        print_time_elapsed(intermediate_time, time.time(), '4/4')

cr2.close()
cr3.close()
print_time_elapsed(start_time, time.time(), 'Total')
