# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras
import time
import sys
import oerplib

start_time = time.time()
intermediate_time = start_time

DB_NAME = 'fm-sp-231_SYNC_SERVER-20160401'   # replace with your own DB name

DELETE_NO_MASTER = True
DELETE_INACTIVE_RULES = True
DELETE_ENTITY_REL = True  # not recommanded to change it to False because it
                          # can remove delete only entity_rel related to
                          # currently deleted updates
UPDATE_TO_FETCH = 10000

# updates with mast_data='f' and active_rule after this date will not been deleted
NOT_DELETE_DATE = '2016-01-01'

# we will delete all the pulled update which are not master data and use
# active rule but it is safer to keep some safety margin by keeping some more
# updates this is redondant with NOT_DELETE_DATE. Both rules will be applied,
# so the more restrive will win
SAFE_MARGIN_SEQUENCE_TO_KEEP = 2000

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
        print_file_and_screen('%s/4 Start deleting of the related sync_server_entity_rel...' % step)
        cr3 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cr3.execute("""DELETE FROM sync_server_entity_rel
        WHERE id IN
        (SELECT id FROM sync_server_entity_rel WHERE update_id IN %s)""",
                    (tuple(update_id_list),))
        entity_count = cr3.rowcount
        print_file_and_screen('%s/4 sync_server_entity_rel deleted : %s' % (step, locale.format('%d', entity_count, 1)))
        print_time_elapsed(intermediate_time, step='%s/4' % step)
        conn.commit()

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
    print_file_and_screen('1/4 Start deleting updates with active rules and not master_data'
          ' where sequence is < %s ...' % smallest_last_sequence)
    cr2.execute("SELECT id FROM sync_server_sync_rule WHERE active='t' AND master_data='f'", ())
    no_master_data_active_rules = [x[0] for x in cr2.fetchall()]
    cr2.execute("""SELECT id FROM sync_server_update
                WHERE sequence < %s AND rule_id IN %s
                AND create_date < %s""",
                (smallest_last_sequence, tuple(no_master_data_active_rules), NOT_DELETE_DATE))
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
    print_file_and_screen('1/4 %s updates deleted.' % locale.format('%d', cr2.rowcount, 1))
    print_time_elapsed(intermediate_time, step='1/4')
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
                (SELECT id FROM sync_server_sync_rule WHERE active='f')""")
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


print_file_and_screen('Working on db %s' % DB_NAME)
if DELETE_NO_MASTER:
    total_update_count += delete_no_master()
if DELETE_INACTIVE_RULES:
    total_update_count += delete_inactive_rules()

print_file_and_screen('\n\nTotal updates deleted = %s/%s\n\n' %
                      (locale.format('%d', total_update_count, 1),
                       locale.format('%d', number_of_update, 1)))

print_time_elapsed(start_time, time.time(), 'Total')
result_file.close()
