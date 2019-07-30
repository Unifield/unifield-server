import functools
import logging

_logger = logging.getLogger('sync_migration_script')



def translate_column(column, rel_table, rel_column, rel_column_type):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, cr, context=None):
            cr.execute("""\
SELECT
    tc.constraint_name, tc.table_name, kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
WHERE constraint_type = 'FOREIGN KEY' AND tc.table_name=%s AND ccu.table_name=%s AND kcu.column_name=%s""", [self._table, rel_table, column])
            foreign_key_exists = bool( cr.fetchone() )
            if foreign_key_exists:
                format_keys = {
                    'table' : self._table,
                    'rel_table' : rel_table,
                    'rel_column' : rel_column,
                    'column' : column,
                    'column_type' : rel_column_type,
                }
                cr.execute("""\
ALTER TABLE %(table)s ADD COLUMN new_%(column)s %(column_type)s;
UPDATE %(table)s
    SET new_%(column)s = %(rel_table)s.%(rel_column)s
    FROM %(rel_table)s
    WHERE %(table)s.%(column)s = %(rel_table)s.id;
ALTER TABLE %(table)s DROP COLUMN %(column)s;
ALTER TABLE %(table)s RENAME COLUMN new_%(column)s TO %(column)s;
COMMIT;""" % format_keys)  # not_a_user_entry
            return fn(self, cr, context=context)
        return wrapper
    return decorator



def add_sdref_column(fn):
    @functools.wraps(fn)
    def wrapper(self, cr, context=None):
        cr.execute("""\
SELECT column_name 
  FROM information_schema.columns 
  WHERE table_name=%s AND column_name='sdref';""", [self._table])
        column_sdref_exists = bool( cr.fetchone() )
        result = fn(self, cr, context=context)
        if not column_sdref_exists:
            cr.execute("SELECT COUNT(*) FROM %s" % self._table)  # not_a_user_entry
            count = cr.fetchone()[0]
            if count > 0:
                cr.commit()
                cr_read = cr._cnx.cursor()
                _logger.info("Populating column sdref for model %s, %d records to update... This operation can take a lot of time, please wait..." % (self._name, count))
                cr_read.execute("SELECT id, fields, values FROM %s" % self._table)
                i, row = 1, cr_read.fetchone()
                while row:
                    id, fields, values = row
                    cr.execute("SAVEPOINT make_sdref")
                    try:
                        data = dict(zip(eval(fields), eval(values)))
                        assert 'id' in data, "Cannot find column 'id' on model=%s id=%d" % (self._name, id)
                        raise Exception('Wrong Way')
                        #sdref = xmlid_to_sdref(data['id'])
                        #cr.execute("UPDATE %s SET sdref = %%s WHERE id = %%s" % self._table, [sdref, id])  # not_a_user_entry
                    except AssertionError, e:
                        _logger.error("Cannot find SD ref on model=%s id=%d: %s" % (self._name, id, e.message))
                        cr.execute("ROLLBACK TO SAVEPOINT make_sdref")
                    except:
                        _logger.exception("Cannot find SD ref on model=%s id=%d" % (self._name, id))
                        cr.execute("ROLLBACK TO SAVEPOINT make_sdref")
                    else:
                        cr.execute("RELEASE SAVEPOINT make_sdref")
                    if i % 20000 == 0:
                        _logger.info("Intermittent commit, %d/%d (%d%%) SD refs created" % (i, count, int(100.0 * i / count)))
                        cr.commit()
                    i, row = i + 1, cr_read.fetchone()
                cr_read.close()
                cr.commit()
        return result
    return wrapper



def migrate_sequence_to_sequence_number(fn):
    @functools.wraps(fn)
    def wrapper(self, cr, context=None):
        cr.execute("""\
SELECT 1
FROM information_schema.columns c1
    LEFT JOIN information_schema.columns c2
    ON c2.table_name = c1.table_name AND c2.column_name = 'sequence_number'
WHERE c1.table_name = %s AND c1.column_name = 'sequence' AND c2.column_name IS NULL;""", (self._table,))  # not_a_user_entry
        if cr.fetchone():
            _logger.info("Replacing column sequence by sequence_number for table %s..." % self._table)
            cr.execute("""\
ALTER TABLE %(table)s ADD COLUMN "sequence_number" INTEGER;
UPDATE %(table)s SET sequence_number = sequence;
ALTER TABLE %(table)s DROP COLUMN "sequence";
""" % {'table':self._table})  # not_a_user_entry
        return fn(self, cr, context=context)
    return wrapper



def normalize_sdref(fn):
    """
    Migrate and add sdref constraint to prevent commas in the xmlid name
    """
    @functools.wraps(fn)
    def wrapper(self, cr, context=None):
        result = fn(self, cr, context=context)
        cr.execute("""\
SELECT 1 FROM pg_constraint WHERE conname = 'normalized_sdref_constraint';""")
        # If there is not, we will migrate and create it after
        if not cr.fetchone():
            _logger.info("Replace commas in sdrefs and create a constraint...")
            cr.execute("SAVEPOINT make_sdref_constraint")
            try:
                cr.execute("""\
UPDATE ir_model_data SET name = replace(name, ',', '_') WHERE name LIKE '%,%';""")
                records_updated = cr._obj.rowcount
                cr.commit()
                _logger.info("%d sdref(s) have been updated" % records_updated)
            except:
                cr.execute("ROLLBACK TO SAVEPOINT make_sdref_constraint")
                raise
            else:
                cr.execute("""
ALTER TABLE ir_model_data ADD CONSTRAINT normalized_sdref_constraint CHECK(module != 'sd' OR name ~ '^[^,]*$');""")
        return result
    return wrapper
