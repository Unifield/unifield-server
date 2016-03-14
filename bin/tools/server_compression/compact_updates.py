# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras
import time
import sys
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
        'financing.contract.contract',
        # in formating_line.py when write is done in a context of
        # synchronization, the write is ignored. This lead to somes problems in
        # compactation as many writes are compacted in only one create
        'financing.contract.format.line',
]

DB_NAME = 'DAILY_SYNC_SERVER-COMPRESSED-23-20160303-073301'   # replace with your own DB

locale.setlocale(locale.LC_ALL, '')
conn = psycopg2.connect("dbname=%s" % DB_NAME)

cr = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr3 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

rows_already_seen = {}
deleted_update_ids = []
update_inactive_rules = []
update_no_master_ids = []
not_deleted_update = 0
total_update_ids = set()
cr2.execute("""SELECT COUNT(*) FROM sync_server_update""", ())
number_of_update = cr2.fetchone()[0]


def update_progress(progress, deleted):
    '''Displays or updates a console progress bar
    '''
    bar_length = 50 # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    elif progress < 0:
        progress = 0
        status = "Halt...\r\n"
    elif progress >= 1:
        progress = 1
        status = "Done...\r\n"
    block = int(round(bar_length * progress))
    progress = round(progress, 3)
    text = "\rPercent: [{0}] {1}% {2} ({3} deleted)".format( "#"*block +
            "-"*(bar_length - block), progress * 100, status, deleted)
    sys.stdout.write(text)
    sys.stdout.flush()

def print_time_elapsed(start_time, stop_time, step=''):
    ''' print elapsed time in a human readable format
    '''
    elapsed_time = stop_time - start_time
    minute, second = divmod(elapsed_time, 60)
    hour, minute = divmod(minute, 60)
    print "%s Elapsed time : %d:%02d:%02d" % (step, hour, minute, second)

print 'working on db %s' % DB_NAME

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
    while True:
        multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
        if not multiple_updates:
            break
        update_no_master_ids = [x[0] for x in multiple_updates]
        cr3.execute('DELETE FROM sync_server_update WHERE id IN %s',
                    (tuple(update_no_master_ids),))
        conn.commit()
        total_update_ids = total_update_ids.union(update_no_master_ids)
    print '1/4 %s updates deleted.' % locale.format('%d', cr2.rowcount, 1)
    print_time_elapsed(intermediate_time, time.time(), '1/4')
    del multiple_updates

if DELETE_INACTIVE_RULES:
    intermediate_time = time.time()
    print '2/4 Start deleting the updates related to inactive rules...'
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE rule_id IN
                (SELECT id FROM sync_server_sync_rule WHERE active='f')""")
    update_inactive_rules_count = cr2.rowcount
    while True:
        multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
        if not multiple_updates:
            break
        update_inactive_rules = [x[0] for x in multiple_updates]
        cr3.execute('DELETE FROM sync_server_update WHERE id IN %s',
                    (tuple(update_inactive_rules),))
        conn.commit()
        total_update_ids = total_update_ids.union(update_inactive_rules)
    print '2/4 %s updates related to inactive rules deleted.' % locale.format('%d', update_inactive_rules_count, 1)
    print_time_elapsed(intermediate_time, time.time(), '2/4')
    del multiple_updates

if COMPACT_UPDATE:
    oerp = oerplib.OERP('127.0.0.1', DB_NAME, protocol='netrpc', port='10251', timeout=3600)
    oerp.login('admin', 'admin', DB_NAME)
    sync_server_update = oerp.get('sync.server.update')
    intermediate_time = time.time()
    down_direction_count = 0
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

    # create a dict of rule direction, to avoid browsing on each update
    cr2.execute("""SELECT id, direction FROM sync_server_sync_rule""", ())
    rule_direction_dict = dict(cr2.fetchall())

    cr.execute("""
    SELECT * FROM
    sync_server_update ORDER BY sequence, id
    """)
    total_updates = cr.rowcount
    multiple_updates = cr.fetchall()
    current_cursor = 0
    print '3/4 Start compressing the updates, this may take a while ...'
    for row in multiple_updates:
        current_cursor += 1
        if row['sdref'] in SDREF_TO_EXCLUDE or\
           row['model'] in MODEL_TO_EXCLUDE:
            continue
        key = row['sdref'], row['rule_id'], entity_branch_name[row['source']]
        if key not in rows_already_seen:
            rows_already_seen[key] = {'id': row['id'],
                                      'is_deleted': row['is_deleted'],
                                      'sequence': row['sequence'],
                                      'source': row['source'],
                                      'values': row['values'] and eval(row['values']) or [],
                                      }
        else:
            if row['is_deleted']:
                if rows_already_seen[key]['is_deleted']:
                    # the previous update was also a delete
                    # so delete the previous update to keep only the last one
                    cr2.execute('DELETE FROM sync_server_update WHERE id = %s',
                                (rows_already_seen[key]['id'],))
                    deleted_update_ids.append(rows_already_seen[key]['id'])
                    # and keep the current
                    rows_already_seen[key] = {'id': row['id'],
                                              'is_deleted': row['is_deleted'],
                                              'sequence': row['sequence'],
                                              'source': row['source'],
                                              'values': row['values'] and eval(row['values']) or [],
                                              }
                else:   # the previous was not a delete, the current and the
                        # previous should be deleted
                    cr2.execute('DELETE FROM sync_server_update WHERE id IN %s',
                                ((rows_already_seen[key]['id'], row['id']),))
                    deleted_update_ids.append(rows_already_seen[key]['id'])
                    deleted_update_ids.append(row['id'])
                    # remove the already seen key
                    del rows_already_seen[key]
                conn.commit()
            else:
                # check no reference to other object change between the
                # previous update and the current
                old_update_source = rows_already_seen[key]['source']
                current_upadte_source = row['source']
                previous_values = rows_already_seen[key]['values']
                current_values = eval(row['values'])
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

                    sequence_to_moved_on = rows_already_seen[key]['sequence']
                    cr2.execute('''SELECT id
                                FROM sync_server_update
                                WHERE sequence > %s AND sdref IN %s AND
                                is_deleted='f' LIMIT 1''',
                                (sequence_to_moved_on, tuple(ref_diff)))
                    if cr2.fetchone():
                        rows_already_seen[key] = {'id': row['id'],
                                                  'is_deleted': row['is_deleted'],
                                                  'sequence': row['sequence'],
                                                  'source': row['source'],
                                                  'values': row['values'] and eval(row['values']) or [],
                                                  }
                        not_deleted_update += 1
                        continue  # if anything is matching, do not compress

                # replace the content of the previous update with the current
                items = filter(lambda x: x[0] not in ['session_id', 'id', 'sdref',
                                                      'rule_id', 'sequence', 'source',
                                                      'owner',
                                                      'create_date', 'write_uid',
                                                      'create_uid'], list(row.iteritems()))
                # if sources are different and direction of the rule is
                # down, it is required to keep this updates
                if old_update_source != current_upadte_source:
                    rule_direction = rule_direction_dict[row['rule_id']]
                    if rule_direction in ('down', 'bi-private'):
                        down_direction_count += 1
                        continue
                    else:
                        # set the highest parent as source
                        items.append(('source', entity_branch_name[row['source']]))

                fields_to_set = [x[0] for x in items]
                values_to_set = [x[1] for x in items]

                # delete the update
                cr2.execute('DELETE FROM sync_server_update WHERE id = %s', (row['id'],))
                deleted_update_ids.append(row['id'])
                conn.commit()

                fields = ','.join(map(lambda x: '%s = %%s' % x, fields_to_set))
                sql_query = 'UPDATE sync_server_update SET %s WHERE id = %%s' % fields

                cr2.execute(sql_query, values_to_set + [rows_already_seen[key]['id']])

            conn.commit()
        progress = current_cursor/float(total_updates)
        update_progress(progress, len(deleted_update_ids))
        #print "%s/%s updates parsed (%s updates deleted)" % (current_cursor, total_updates, len(deleted_update_ids))

    # free memory
    del multiple_updates
    del rows_already_seen
    print '%s not deleted updates.' % not_deleted_update
    print '%s down direction update kept' % down_direction_count
    print '3/4 Compression finished. %s update deleted.' % locale.format('%d', len(deleted_update_ids), 1)
    print_time_elapsed(intermediate_time, time.time(), '3/4')
    total_update_ids = total_update_ids.union(deleted_update_ids)

total_update_count = len(total_update_ids)
print '\n\nTotal updates deleted = %s/%s\n\n' % (locale.format('%d',
    total_update_count, 1), locale.format('%d', number_of_update, 1))

if DELETE_ENTITY_REL:
    if total_update_ids:
        intermediate_time = time.time()
        print '4/4 Start deleting of the related sync_server_entity_rel...'
        cr3.execute("""DELETE FROM sync_server_entity_rel
        WHERE id IN
        (SELECT id FROM sync_server_entity_rel WHERE update_id IN %s)""",
                    (tuple(total_update_ids),))
        entity_count = cr3.rowcount
        print '4/4 sync_server_entity_rel deleted : %s' % locale.format('%d', entity_count, 1)
        print_time_elapsed(intermediate_time, time.time(), '4/4')
        conn.commit()

cr.close()
cr2.close()
cr3.close()
print_time_elapsed(start_time, time.time(), 'Total')
del deleted_update_ids
del update_inactive_rules
del update_no_master_ids
