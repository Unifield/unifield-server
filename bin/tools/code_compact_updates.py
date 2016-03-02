# encoding=utf-8
import psycopg2
import psycopg2.extras

conn = psycopg2.connect("dbname=fm-sp-222_SYNC_SERVER_COMPRESSED2")   # replace with your own DB

cr = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# here it takes already a lot of time...
cr.execute("""
SELECT * FROM
sync_server_update ORDER BY sequence, id
""")
to_continue = True
print 'Starting compressing the updates, this may take a while ...'
update_deleted_count = 0
rows_already_seen = {}

# the objects with the folowing sdref will be ignored
SDREF_TO_EXCLUDE = [
]

MODEL_TO_EXCLUDE = [
    'res.currency.rate',
]

while to_continue:
    multiple_updates = cr.fetchmany(1000)
    if not multiple_updates:
        to_continue = False
        break

    for row in multiple_updates:
        if row['sdref'] in SDREF_TO_EXCLUDE or\
           row['model'] in MODEL_TO_EXCLUDE:
            continue
        key = row["sdref"], row["rule_id"], row["source"]
        # we have never seen this row
        if key not in rows_already_seen:
            if row['is_deleted']:
                cr2.execute("DELETE FROM sync_server_update WHERE id = %s",
                            (row['id'],))
                update_deleted_count += 1
            else:
                rows_already_seen[key] = row['id']
            continue
        # we already seen this row, replace the last value with the new one
        else:
            if row['is_deleted']:
                # delete this update and all the previous ones
                cr2.execute("DELETE FROM sync_server_update WHERE id = %s",
                            (row['id'],))
                cr2.execute("DELETE FROM sync_server_update WHERE id = %s",
                            (rows_already_seen[key],))
                update_deleted_count += 1
                rows_already_seen.pop(key)
            else:
                items = filter(lambda x: x[0] not in ['session_id', 'id', 'sdref',
                                                      'rule_id', 'source', 'sequence',
                                                      'create_date', 'write_uid',
                                                      'create_uid'], list(row.iteritems()))

                fields_to_set = map(lambda x: x[0], items)
                values_to_set = map(lambda x: x[1], items)

                fields = ','.join(map(lambda x: '%s = %%s' % x, fields_to_set))
                sql_query = 'UPDATE sync_server_update SET %s WHERE id = %%s' % fields

                cr2.execute("DELETE FROM sync_server_update WHERE id = %s", (row['id'],))
                update_deleted_count += 1
                cr2.execute(sql_query, values_to_set + [rows_already_seen[key]])
        conn.commit()
print 'Compression finished. Update deleted : %s' % update_deleted_count
