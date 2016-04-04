# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras
import time
import sys
import oerplib

start_time = time.time()
intermediate_time = start_time

DB_NAME = 'SYNC_SERVER-20160321-163301-zip_2'   # replace with your own DB

DELETE_NO_MASTER = True
DELETE_INACTIVE_RULES = True
COMPACT_UPDATE = True
DELETE_ENTITY_REL = True  # not recommanded to change it to False because it
                          # can remove delete only entity_rel related to
                          # currently deleted updates
UPDATE_TO_FETCH = 10000

# updates with mast_data='f' and active_rule after this date will not been deleted
NOT_DELETE_DATE = '2016-01-01'

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


    # This is due to the create method of res.partner.address which delete
    # empty address before adding new one. This behaviour is difficult to
    # handle with compaction because many creation/modification of one
    # res.partner.address will result in only one update but the res_id might
    # not be consistent with not compacted server.
    # in final for SYNC_SERVER-20160321-163301, this exclusion mean 1510 more
    # updates than without the exclusion which is not so much.
    'res.partner.address',
]

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

# we will delete all the pulled update which are not master data and use
# active rule but it is safer to keep some safety margin by keeping some more
# updates this is redondant with NOT_DELETE_DATE. Both rules will be applied,
# so the more restrive will win
SAFE_MARGIN_SEQUENCE_TO_KEEP = 2000

# get the smallest last sequence pulled
cr2.execute("""SELECT MIN(last_sequence) FROM sync_server_entity
            WHERE last_sequence !=0""", ())
SMALLEST_LAST_SEQUENCE = cr2.fetchone()[0]
SMALLEST_LAST_SEQUENCE -= SAFE_MARGIN_SEQUENCE_TO_KEEP

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
    block = int(round(bar_length * progress))
    progress = round(progress, 3)
    text = "\rProgress: [{0}] {1}% ({2} deleted)".format("#"*block +
            "-"*(bar_length - block), progress * 100, deleted)
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
    intermediate_time = time.time()
    print_file_and_screen('%s/4 Start deleting of the related sync_server_entity_rel...' % step)
    chunk_size = 1000
    i = 0
    entity_count = 0
    while i < len(update_id_list)+chunk_size:
        chunk = update_id_list[i-chunk_size:i]
        if not chunk:
            i += chunk_size
            continue
        cr3 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cr3.execute("""DELETE FROM sync_server_entity_rel
        WHERE id IN
        (SELECT id FROM sync_server_entity_rel WHERE update_id IN %s)""",
            (tuple(chunk),))
        entity_count += cr3.rowcount
        conn.commit()
        i += chunk_size
    print_file_and_screen('%s/4 sync_server_entity_rel deleted : %s' % (step, locale.format('%d', entity_count, 1)))
    print_time_elapsed(intermediate_time, step='%s/4' % step)

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
    print_file_and_screen('1/4 Start deleting updates with active rules and not master_data'
          ' where sequence is < %s and create_date > %s ...' %
          (SMALLEST_LAST_SEQUENCE, NOT_DELETE_DATE))
    cr2.execute("SELECT id FROM sync_server_sync_rule WHERE active='t' AND master_data='f'", ())
    no_master_data_active_rules = [x[0] for x in cr2.fetchall()]
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE sequence < %s AND rule_id IN %s
                AND create_date < %s""",
                (SMALLEST_LAST_SEQUENCE, tuple(no_master_data_active_rules), NOT_DELETE_DATE))
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
    print_file_and_screen('3/4 Start deleting the updates related to inactive rules...')
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE rule_id IN
                (SELECT id FROM sync_server_sync_rule WHERE active='f') AND
                sequence < %s""", (SMALLEST_LAST_SEQUENCE,))
    update_inactive_rules_count = cr2.rowcount
    while True:
        multiple_updates = cr2.fetchmany(UPDATE_TO_FETCH)
        if not multiple_updates:
            break
        chunk_update_inactive_rules = [x[0] for x in multiple_updates]
        cr3.execute('DELETE FROM sync_server_update WHERE id IN %s AND create_date < %s',
                    (tuple(chunk_update_inactive_rules), NOT_DELETE_DATE))
        conn.commit()
        update_count += len(chunk_update_inactive_rules)
        update_inactive_rules = update_inactive_rules.union(chunk_update_inactive_rules)
    print_file_and_screen('3/4 %s updates related to inactive rules deleted.' % locale.format('%d', update_inactive_rules_count, 1))
    print_time_elapsed(intermediate_time, step='3/4')
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
    intermediate_time = time.time()
    oerp = oerplib.OERP('localhost', DB_NAME, protocol='netrpc',
                               port='11031', timeout=300)
    oerp.login('admin', 'admin', DB_NAME)
    cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # build a dict of groups for each instances
    cr2.execute("""SELECT id FROM sync_server_entity""", ())
    instance_list = [x[0] for x in cr2.fetchall()]
    instance_group_dict = {}
    for instance_id in instance_list:
        instance_group_dict[instance_id] = {}
        for group_id in RULE_TYPE.values():
            # get the group of this instance if any
            cr2.execute("""SELECT name
            FROM sync_entity_group_rel inner join sync_server_entity_group on group_id=id
            WHERE type_id=%s and entity_id=%s""" % (group_id, instance_id), ())
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
    WHERE model NOT IN %s AND
    sequence < %s AND create_date < %s
    ORDER BY sequence, id
    """, (tuple(MODEL_TO_EXCLUDE), SMALLEST_LAST_SEQUENCE, NOT_DELETE_DATE))
    total_updates = cr.rowcount
    multiple_updates = cr.fetchall()
    cr.close()
    current_cursor = 0
    bi_privatet_up_down = 0
    print_file_and_screen('5/6 Start compressing the updates, this may take a while (%s updates to parse)' % total_updates)
    for row in multiple_updates:

        current_cursor += 1
        if row['sdref'] in SDREF_TO_EXCLUDE:
            continue

        # generate a key according to the group concerned by the update
        # ie. group_name='OCA_MISSION_BD1' or group_name='OCA_COORDINATION'
        rule_direction = rule_direction_dict[row['rule_id']]
        group_name = instance_group_dict[row['source']][rule_type_dict[row['rule_id']]]

        # if sources are different and direction of the rule is
        # down, bi-private or up it's needed to use the source and not group
        if rule_direction in ('down', 'bi-private', 'up'):
            key = row['sdref'], row['rule_id'], row['source']
            bi_privatet_up_down += 1
        elif group_name:
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
                'count': 1,
            }
        else:
            if row['is_deleted']:
                # delete the previous update to keep only the last one
                cr2.execute('DELETE FROM sync_server_update WHERE id = %s',
                            (rows_already_seen[key]['id'],))
                deleted_update_ids.append(rows_already_seen[key]['id'])
                # and keep the current
                rows_already_seen[key] = {
                    'id': row['id'],
                    'is_deleted': row['is_deleted'],
                    'sequence': row['sequence'],
                    'source': row['source'],
                    'count': rows_already_seen[key]['count'] + 1,
                }
                conn.commit()
            else:
                current_count = rows_already_seen[key]['count']
                # for more safety, the first and last update will be kept
                if current_count == 1:
                    rows_already_seen[key] = {'id': row['id'],
                                              'is_deleted': row['is_deleted'],
                                              'sequence': row['sequence'],
                                              'source': row['source'],
                                              'count': current_count + 1,
                                              }
                    not_deleted_update += 1
                    continue

                # delete the previous update
                cr2.execute('DELETE FROM sync_server_update WHERE id = %s',
                        (rows_already_seen[key]['id'],))
                deleted_update_ids.append(rows_already_seen[key]['id'])
                rows_already_seen[key] = {'id': row['id'],
                                          'is_deleted': row['is_deleted'],
                                          'sequence': row['sequence'],
                                          'source': row['source'],
                                          'count': current_count + 1,
                                          }
                conn.commit()
            conn.commit()
        if current_cursor % 100 == 0:
            progress = current_cursor/float(total_updates)
            update_progress(progress, len(deleted_update_ids))

    # free memory
    del multiple_updates
    del rows_already_seen
    print_file_and_screen('\n%s not deleted updates.' % not_deleted_update)
    print_file_and_screen('%s updates have no group.' % no_group_count)
    print_file_and_screen('%s updates are bi-private, up or down.' % bi_privatet_up_down)
    print_file_and_screen('5/6 Compression finished. %s update deleted.' % locale.format('%d', len(deleted_update_ids), 1))
    print_time_elapsed(intermediate_time, step='5/6')
    update_count += len(deleted_update_ids)
    delete_related_entity_rel(deleted_update_ids, step='6')
    del deleted_update_ids
    cr2.close()
    return update_count

print_file_and_screen('Working on db %s' % DB_NAME)
if DELETE_NO_MASTER:
    total_update_count += delete_no_master()
if DELETE_INACTIVE_RULES:
    total_update_count += delete_inactive_rules()
if COMPACT_UPDATE:
    current_count = None
    while current_count != 0:
        current_count = compact_updates()
        total_update_count += current_count

print_file_and_screen('\n\nTotal updates deleted = %s/%s\n\n' %
                      (locale.format('%d', total_update_count, 1),
                       locale.format('%d', number_of_update, 1)))

print_time_elapsed(start_time, time.time(), 'Total')
result_file.close()
