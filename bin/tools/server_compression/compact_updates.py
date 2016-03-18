# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras
import time
import sys
import oerplib

start_time = time.time()
intermediate_time = start_time

DELETE_NO_MASTER = False #True
DELETE_INACTIVE_RULES = False #True
COMPACT_UPDATE = True
DELETE_ENTITY_REL = True  # not recommanded to change it to False because it
                          # can remove delete only entity_rel related to
                          # currently deleted updates
UPDATE_TO_FETCH = 10000

# we will delete all the pulled update which are not master data and use active rule
# but it is safer to keep some safety margin by keeping some more updates
SAFE_MARGIN_SEQUENCE_TO_KEEP = 2000

RULE_TYPE = {
    'USB': 1,
    'OC': 2,
    'MISSION': 3,
    'COORDINATIONS': 4,
    'HQ + MISSION': 5,
}

# the objects with the folowing sdref will be ignored
SDREF_TO_EXCLUDE = [
]

# the objects with the folowing model will be ignored
MODEL_TO_EXCLUDE = [
    'ir.cron',
    'deleted.object',
    'financing.contract.contract',
    # in formating_line.py when write is done in a context of
    # synchronization, the write is ignored. This lead to somes problems in
    # compactation as many writes are compacted in only one create
    'financing.contract.format.line',
]

DB_NAME = 'SYNC_SERVER-20160316-163301-zip4'   # replace with your own DB
DB_PORT = '11031'

locale.setlocale(locale.LC_ALL, '')
conn = psycopg2.connect("dbname=%s" % DB_NAME)
total_update_count = 0
cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr2.execute("""SELECT COUNT(*) FROM sync_server_update""", ())
number_of_update = cr2.fetchone()[0]
time_stamp = time.strftime("%Y%m%d-%H%M%S")
file_name = 'compact_updates_%s.txt' % time_stamp
result_file = open(file_name, "a")

PRINT_SCREEN = True
PRINT_FILE = True
def print_file_and_screen(string):
    if PRINT_FILE:
        result_file.write(string+'\n')
        result_file.flush()
    if PRINT_SCREEN:
        print string

def update_progress(progress, deleted):
    '''Displays or updates a console progress bar
    '''
    bar_length = 50  # Modify this to change the length of the progress bar
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
    text = "\rProgress: [{0}] {1}% {2} ({3} deleted)".format("#"*block +
            "-"*(bar_length - block), progress * 100, status, deleted)
    sys.stdout.write(text)
    sys.stdout.flush()

def print_time_elapsed(start_time, stop_time=None, step=''):
    ''' print elapsed time in a human readable format
    '''
    if not stop_time:
        stop_time = time.time()
    elapsed_time = stop_time - start_time
    minute, second = divmod(elapsed_time, 60)
    hour, minute = divmod(minute, 60)
    print_file_and_screen("%s Elapsed time : %d:%02d:%02d" % (step, hour, minute, second))

def delete_related_entity_rel(update_id_list, step=''):
    '''delete all sync_server_entity_rel object related to the update_id
    in parameter'''
    if DELETE_ENTITY_REL and update_id_list:
        intermediate_time = time.time()
        print_file_and_screen('%s/6 Start deleting of the related sync_server_entity_rel...' % step)
        cr3 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cr3.execute("""DELETE FROM sync_server_entity_rel
        WHERE id IN
        (SELECT id FROM sync_server_entity_rel WHERE update_id IN %s)""",
                    (tuple(update_id_list),))
        entity_count = cr3.rowcount
        print_file_and_screen('%s/6 sync_server_entity_rel deleted : %s' % (step, locale.format('%d', entity_count, 1)))
        print_time_elapsed(intermediate_time, step='%s/6' % step)
        conn.commit()

print_file_and_screen('Working on db %s' % DB_NAME)

def delete_no_master():
    '''Delete updates that have active rule and no master_data if all instances
    already pull them.
    To check that, get the smallest last_sequence pulled, decrease this number
    for security (SAFE_MARGIN_SEQUENCE_TO_KEEP) : ie. in case a backup is
    restored and need to pull old updates.
    '''
    chunk_update_no_master_ids = []
    update_count = 0
    update_no_master_ids = set()
    cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cr3 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    intermediate_time = time.time()
    cr2.execute("""SELECT MIN(last_sequence) FROM sync_server_entity
                WHERE last_sequence !=0""", ())
    smallest_last_sequence = cr2.fetchone()[0]
    smallest_last_sequence -= SAFE_MARGIN_SEQUENCE_TO_KEEP
    print_file_and_screen('1/6 Start deleting updates with active rules and not master_data'
          ' where sequence is < %s ...' % smallest_last_sequence)
    cr2.execute("SELECT id FROM sync_server_sync_rule WHERE active='t' AND master_data='f'", ())
    no_master_data_active_rules = [x[0] for x in cr2.fetchall()]
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE sequence < %s and rule_id IN %s""",
                (smallest_last_sequence, tuple(no_master_data_active_rules),))
    while True:
        multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
        if not multiple_updates:
            break
        chunk_update_no_master_ids = [x[0] for x in multiple_updates]
        cr3.execute('DELETE FROM sync_server_update WHERE id IN %s',
                    (tuple(chunk_update_no_master_ids),))
        conn.commit()
        update_count += len(chunk_update_no_master_ids)
        update_no_master_ids = update_no_master_ids.union(chunk_update_no_master_ids)
    print_file_and_screen('1/6 %s updates deleted.' % locale.format('%d', cr2.rowcount, 1))
    print_time_elapsed(intermediate_time, step='1/6')
    delete_related_entity_rel(list(update_no_master_ids), step='2')
    del chunk_update_no_master_ids
    del update_no_master_ids
    del multiple_updates
    cr2.close()
    cr3.close()
    return update_count

def delete_inactive_rules():
    '''Delete all updates related to inactive rules
    (it was mannualy checked that the update related to inactive rules are not
    pulled anymore)
    '''
    chunk_update_inactive_rules = []
    update_count = 0
    update_inactive_rules = set()
    cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cr3 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    intermediate_time = time.time()
    print_file_and_screen('3/6 Start deleting the updates related to inactive rules...')
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE rule_id IN
                (SELECT id FROM sync_server_sync_rule WHERE active='f')""")
    update_inactive_rules_count = cr2.rowcount
    while True:
        multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
        if not multiple_updates:
            break
        chunk_update_inactive_rules = [x[0] for x in multiple_updates]
        cr3.execute('DELETE FROM sync_server_update WHERE id IN %s',
                    (tuple(chunk_update_inactive_rules),))
        conn.commit()
        update_count += len(chunk_update_inactive_rules)
        update_inactive_rules = update_inactive_rules.union(chunk_update_inactive_rules)
    print_file_and_screen('3/6 %s updates related to inactive rules deleted.' % locale.format('%d', update_inactive_rules_count, 1))
    print_time_elapsed(intermediate_time, step='3/6')
    delete_related_entity_rel(list(update_inactive_rules), step='4')
    del chunk_update_inactive_rules
    del update_inactive_rules
    del multiple_updates
    cr2.close()
    cr3.close()
    return update_count

def compact_updates():
    '''Delete some updates if they are modifying the same object (sdref),
    applied on the same rule (rule_id) and concern the same group of instance
    (group_name).
    This is the more complex part, there is many special cases to handle
    '''
    rows_already_seen = {}
    deleted_update_ids = []
    not_deleted_update = 0
    update_count = 0
    no_group_count = 0
    oerp = oerplib.OERP('127.0.0.1', DB_NAME, protocol='netrpc', port=DB_PORT, timeout=3600)
    oerp.login('admin', 'admin', DB_NAME)
    intermediate_time = time.time()
    down_direction_count = 0

    # build a dict of groups for each instances
    cr2.execute("""SELECT id FROM sync_server_entity""", ())
    instance_list = [x[0] for x in cr2.fetchall()]
    instance_group_dict = {}
    for instance_id in instance_list:
        instance_group_dict[instance_id] = {}
        for group_name, group_id in RULE_TYPE.items():
            # get the group of this instance if any
            cr2.execute("""SELECT name
            FROM sync_entity_group_rel inner join sync_server_entity_group on group_id=id
            WHERE type_id=%s and entity_id=%s""" % (RULE_TYPE[group_name], instance_id), ())
            res = [x[0] for x in cr2.fetchall()]
            if len(res) > 1:
                instance_group_dict[instance_id][group_id] = ''.join(sorted(res))
            else:
                instance_group_dict[instance_id][group_id] = res and res[0] or None

    # create a dict of rule direction, to avoid browsing on each update
    cr2.execute("""SELECT id, direction FROM sync_server_sync_rule""", ())
    rule_direction_dict = dict(cr2.fetchall())

    # create a dict of rule type to be able to compress all source in a same oc
    cr2.execute("""SELECT id, type_id FROM sync_server_sync_rule""", ())
    rule_type_dict = dict(cr2.fetchall())

    cr = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cr.execute("""
    SELECT * FROM sync_server_update
    WHERE model NOT IN %s
    ORDER BY sequence, id
    """, (tuple(MODEL_TO_EXCLUDE),))
    total_updates = cr.rowcount
    multiple_updates = cr.fetchall()
    cr.close()
    current_cursor = 0
    print_file_and_screen('5/6 Start compressing the updates, this may take a while (%s updates to parse)' % total_updates)
    for row in multiple_updates:
        current_cursor += 1
        if row['sdref'] in SDREF_TO_EXCLUDE:
            continue

        # generate a key according to the group concerned by the update
        # ie. group_name='OCA_MISSION_BD1' or group_name='OCA_COORDINATION'
        group_name = instance_group_dict[row['source']][rule_type_dict[row['rule_id']]]
        if group_name:
            key = row['sdref'], row['rule_id'], group_name
        else:
            key = row['sdref'], row['rule_id'], row['source']
            no_group_count += 1
        if key not in rows_already_seen:
            rows_already_seen[key] = {
                'id': row['id'],
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
                    rows_already_seen[key] = {
                        'id': row['id'],
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
                previous_values = rows_already_seen[key]['values']
                current_values = eval(row['values'])
                diff = set(current_values).difference(previous_values)
                ref_diff = False
                if row['model'] == 'ir.translation':
                    # if the reference changes
                    xml_id = current_values[-2]
                    if xml_id and xml_id in diff:
                        # special handling for ir_translation as they are refering
                        # to product using product_ instead of sd.
                        ref_diff = [xml_id]
                else:
                    ref_diff = [x.split('sd.')[1] for x in diff if
                                isinstance(x, (str, unicode)) and x.startswith('sd.')]

                # before to do any replacement, check that the object in this
                # update is not pointing to other object created after the
                # update where it will be moved to.
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
                field_list_to_remove = [
                    'session_id', 'id', 'sdref', 'rule_id', 'sequence',
                    'source', 'owner', 'create_date', 'write_uid',
                    'create_uid']
                items = [x for x in row.iteritems() if x[0] not in
                         field_list_to_remove]
                # if sources are different and direction of the rule is
                # down, it is required to keep this updates
                if rows_already_seen[key]['source'] != row['source']:
                    rule_direction = rule_direction_dict[row['rule_id']]
                    if rule_direction in ('down', 'bi-private'):
                        down_direction_count += 1
                        continue

                fields_to_set = [x[0] for x in items]
                values_to_set = [x[1] for x in items]

                # delete the update
                cr2.execute('DELETE FROM sync_server_update WHERE id = %s', (row['id'],))
                deleted_update_ids.append(row['id'])
                conn.commit()

                # update the previous one with the current values
                fields = ','.join(['%s = %%s' % x for x in fields_to_set])
                sql_query = 'UPDATE sync_server_update SET %s WHERE id = %%s' % fields
                cr2.execute(sql_query, values_to_set + [rows_already_seen[key]['id']])

            conn.commit()
        progress = current_cursor/float(total_updates)
        update_progress(progress, len(deleted_update_ids))

    # free memory
    del multiple_updates
    del rows_already_seen
    print_file_and_screen('%s not deleted updates.' % not_deleted_update)
    print_file_and_screen('%s updates have no_group.' % no_group_count)
    print_file_and_screen('%s down direction update kept' % down_direction_count)
    print_file_and_screen('5/6 Compression finished. %s update deleted.' % locale.format('%d', len(deleted_update_ids), 1))
    print_time_elapsed(intermediate_time, step='5/6')
    update_count += len(deleted_update_ids)
    delete_related_entity_rel(deleted_update_ids, step='6')
    del deleted_update_ids
    cr2.close()
    return update_count

if DELETE_NO_MASTER:
    total_update_count += delete_no_master()
if DELETE_INACTIVE_RULES:
    total_update_count += delete_inactive_rules()
if COMPACT_UPDATE:
    total_update_count += compact_updates()

print_file_and_screen('\n\nTotal updates deleted = %s/%s\n\n' %
                      (locale.format('%d', total_update_count, 1),
                       locale.format('%d', number_of_update, 1)))

print_time_elapsed(start_time, time.time(), 'Total')
result_file.close()
