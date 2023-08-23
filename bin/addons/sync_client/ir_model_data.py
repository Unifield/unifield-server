# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging

from osv import osv, fields
import tools

from sync_common import WHITE_LIST_MODEL, normalize_sdref


class ir_module_module(osv.osv):
    _name = 'ir.module.module'
    _inherit = 'ir.module.module'

    @tools.read_cache(prefetch=[], context=[], timeout=8000, size=2000)
    def _read_flat(self, cr, user, ids, fields_to_read, context=None, load='_classic_read'):
        return super(ir_module_module, self)._read_flat(cr, user, ids, fields_to_read, context, load)

    def _clean_cache(self, dbname):
        super(ir_module_module, self)._clean_cache(dbname)
        # radical but this doesn't frequently happen
        self._read_flat.clear_cache(dbname)

    def check(self, cr, uid, ids, context=None):
        if ids and \
            self.search_exist(cr, uid,
                              [('id', 'in', ids),
                               ('name', 'in', ['sync_client', 'sync_so', 'update_client']),
                                  ('state', 'in', ['to install', 'to upgrade'])]):
            self.pool.get('ir.model.data').create_all_sdrefs(cr)
        return super(ir_module_module, self).check(cr, uid, ids, context=context)

ir_module_module()

class ir_model_data_sync(osv.osv):
    """ ir_model_data with sync date """

    _inherit = "ir.model.data"
    _logger = logging.getLogger('ir.model.data')


    def _get_is_deleted(self, cr, uid, ids, field, args, context=None):
        datas = {}
        for data in self.read(cr, uid, ids, ['model','res_id'], context=context):
            datas.setdefault(data['model'], set()).add(data['res_id'])
        res = dict.fromkeys(ids, False)
        for model, res_ids in datas.items():
            if self.pool.get(model) is None: continue
            cr.execute("""
SELECT ARRAY_AGG(ir_model_data.id), COUNT(%(table)s.id) > 0
    FROM ir_model_data
    LEFT JOIN %(table)s ON %(table)s.id = ir_model_data.res_id
        WHERE ir_model_data.model = %%s AND ir_model_data.res_id IN %%s AND ir_model_data.id IN %%s
        GROUP BY ir_model_data.model, ir_model_data.res_id HAVING COUNT(%(table)s.id) = 0""" % {'table':self.pool.get(model)._table}, [model, tuple(res_ids), tuple(ids)])  # not_a_user_entry
            for data_ids, exists in cr.fetchall():
                res.update(dict((id, not exists) for id in data_ids))
        return res

    _columns={
        'sync_date':fields.datetime('Last Synchronization Date'),
        'version':fields.integer('Version'),
        'last_modification':fields.datetime('Last Modification Date'),
        'is_deleted' : fields.function(string='The record exists in database?', type='boolean',
                                       fnct=_get_is_deleted, fnct_search=_get_is_deleted, method=True),
        'touched' : fields.text("Which records has been touched"),
        'force_recreation' : fields.boolean("Force record re-creation"),
        'resend': fields.boolean('Received but pushed', help='Update received but must be pushed in the same sync: if true do not reset touch on update execution', select=1),
    }

    _defaults={
        'version' : 1,
        'force_recreation' : False,
        'touched' : '[]',
    }

    def mark_resend(self, cr, uid, model, res_id, context=None):
        cr.execute("update ir_model_data set resend='t' where module='sd' and model=%s and res_id=%s", (model, res_id))
        return True


    def create_all_sdrefs(self, cr):
        """
        Gets all records for all not ignored models and calls get_sd_ref, thereby creating sdrefs that dont exist
        """
        # loop on objects that don't match the models to ignore domain in sync common
        result = set()
        for model in WHITE_LIST_MODEL:
            obj = self.pool.get(model)
            if obj is None:
                self._logger.warn('Could not get object %s while creating all missing sdrefs' % model)
                continue

            # ignore wizard objects
            if isinstance(obj, osv.osv_memory):
                continue

            # ignore objects who inherit another object, and use their table
            # too, but a different name (would lead to attempted sd ref
            # duplication)
            if hasattr(obj, '_inherit') and obj._name != obj._inherit and \
               (hasattr(obj._inherit, '__iter__') or self.pool.get(obj._inherit)._table == obj._table):
                continue

            # Ignore SQL view records UF-2542
            if not getattr(obj, '_auto', True):
                continue

            # get all records for the object
            cr.execute("""\
                SELECT distinct r.id
                FROM %s r
                    LEFT JOIN ir_model_data data ON data.module = 'sd' AND
                        data.model = %%s AND r.id = data.res_id
                WHERE data.res_id IS NULL;""" % obj._table, [obj._name])  # not_a_user_entry
            record_ids = map(lambda x: x[0], cr.fetchall())

            # if we have some records that doesn't have an sdref
            if record_ids:
                # call get_sd_ref with their ids, therefore creating sdref's
                # that don't exist
                sdref = obj.get_sd_ref(cr, 1, record_ids)
                result.update( map(lambda sdref: (obj._name, sdref), sdref.values()) )

        return result

    @normalize_sdref
    def _auto_init(self,cr,context=None):
        res = super(ir_model_data_sync, self)._auto_init(cr,context=context)
        # Drop old sync.client.write_info table
        cr.execute("""SELECT relname FROM pg_class WHERE relname='sync_client_write_info'""")
        if cr.fetchone():
            self._logger.info("Dropping deprecated table sync_client_write_info...")
            cr.execute("""DROP TABLE sync_client_write_info""")
        # Check existence of unique_sdref_constraint
        cr.execute("""\
SELECT i.relname
FROM pg_class t,
     pg_class i,
     pg_index ix
WHERE t.oid = ix.indrelid
      AND i.oid = ix.indexrelid
      AND t.relkind = 'r'
      AND t.relname = 'ir_model_data'
      AND i.relname = 'unique_sdref_constraint'""")
        # If there is not, we will migrate and create it after
        if not cr.fetchone():
            self._logger.info("Remove duplicated sdrefs and create a constraint...")
            assert self._order.strip().lower() == 'id desc', "Sorry, this migration script works only if default ir.model.data order is 'id desc'"
            cr.execute("SAVEPOINT make_sdref_constraint")
            try:
                cr.execute("""\
SELECT ARRAY_AGG(id),
       ARRAY_AGG(name),
       MAX(sync_date),
       MAX(last_modification),
       MAX(version)
FROM ir_model_data
WHERE module = 'sd'
GROUP BY module, model, res_id
    HAVING COUNT(*) > 1""")
                row = cr.fetchone()
                to_delete = []
                to_write = []
                while row:
                    ids, names, sync_date, last_modification, version = row
                    sdrefs = sorted(zip(ids, names))
                    taken_id, taken_sdref = sdrefs.pop(-1)
                    sdrefs = dict(sdrefs)
                    to_delete.extend(sdrefs.keys())
                    to_write.append((taken_id, {
                        'sync_date' : sync_date,
                        'last_modification' : last_modification,
                        'version' : version,
                    }))
                    row = cr.fetchone()
                if to_delete:
                    cr.execute("""\
DELETE FROM ir_model_data WHERE id IN %s""", [tuple(to_delete)])
                for id, rec in to_write:
                    cr.execute("""\
UPDATE ir_model_data SET """+", ".join("%s = %%s" % k for k in rec.keys())+""" WHERE id = %s""", rec.values() + [id])  # not_a_user_entry
                cr.execute("""CREATE UNIQUE INDEX unique_sdref_constraint ON ir_model_data (model, res_id) WHERE module = 'sd'""")
                cr.commit()
                self._logger.info("%d sdref(s) deleted, %d kept." % (len(to_delete), len(to_write)))
            except:
                cr.execute("ROLLBACK TO SAVEPOINT make_sdref_constraint")
                raise

        return res

    '''
    Create manually a record in this table for a given sdref and res_id, currently used in RW
    '''
    def manual_create_sdref(self, cr, uid, obj, sdref, res_id, context=None):
        if res_id and sdref:
            self.create(cr, uid, {
                'noupdate' : False, # don't set to True otherwise import won't work
                'module' : 'sd',
                'last_modification' : fields.datetime.now(),
                'model' : obj._name,
                'res_id' : res_id,
                'version' : 1,
                'name' : sdref,
            }, context=context)
            return True
        return False

    def create(self, cr, uid, values, context=None):
        context = dict(context or {})

        # Silently purge old sdrefs for replacement
        if values['module'] == 'sd':
            cr.execute("""\
                DELETE FROM ir_model_data
                WHERE module = 'sd' AND model = %s AND res_id = %s""",
                       [values['model'], values['res_id']])

        # idem for xmlids
        # different res_id means re-creation
        cr.execute("""\
            DELETE FROM ir_model_data
            WHERE module = %s AND name = %s""",
                   [values['module'], values['name']])
        if cr._obj.rowcount and values['module'] == 'sd':
            values['force_recreation'] = not context.get('sync_update_execution', False)

        id = super(ir_model_data_sync, self).create(cr, uid, values, context=context)

        # when a module load a specific xmlid, the sdref is updated according
        # that xmlid
        if values['model'] in WHITE_LIST_MODEL and \
           values['module'] not in ('sd', '__export__') and \
           not (values['module'] == 'base' and values['name'].startswith('main_')):
            sdref_name = "%(module)s_%(name)s" % values
            # specific case when sdref already exists
            # that means there is a re-creation from a module
            cr.execute("""\
                DELETE FROM ir_model_data
                WHERE
                    module = 'sd' AND name = %s AND
                    model = %s AND res_id != %s""",
                       [sdref_name, values['model'], values['res_id']])
            values['force_recreation'] = cr._obj.rowcount > 0 \
                and not context.get('sync_update_execution', False)
            cr.execute("""\
                UPDATE ir_model_data sdref
                SET
                    name = %s,
                    force_recreation = %s
                WHERE
                    sdref.module = 'sd' AND
                    sdref.model = %s AND sdref.res_id = %s""",
                       [sdref_name, values['force_recreation'],
                        values['model'], values['res_id']])
            assert cr.rowcount > 0, "Nothing to update"

        return id

    # TODO replace this deprecated method with get_sd_ref(field='id') in your call
    # Beware that the result is a dict, not a list anymore
    def get(self, cr, uid, model, ids, context=None):
        # Just add the warning into log file, and not raise Exception to stop the process
        self._logger.warning("ir.model.data get() method should not be used anymore!")
        result = []
        for id in (ids if hasattr(ids, '__iter__') else [ids]):
            data_ids = self.search(cr, uid, [('model', '=', model._name), ('res_id', '=', id), ('module', '=', 'sd')], limit=1, context=context)
            result.append(data_ids[0] if data_ids else False)
        return result if isinstance(ids, (list, tuple)) else result[0]

    def update_sd_ref(self, cr, uid, sdref, vals, consider_resend=False, context=None):
        """Update a SD ref information. Raise ValueError if sdref doesn't exists."""
        domain = [('module','=','sd'),('name','=',sdref)]

        if consider_resend:
            domain.append(('resend', '=', False))

        ids = self.search(cr, uid, domain, order='NO_ORDER', context=context)
        if not ids:
            raise ValueError("Cannot find sdref %s!" % sdref)

        if context.get('offline_synchronization', False) and 'touched' in vals:
            del vals['touched']

        self.write(cr, uid, ids, vals, context=context)
        return True

    def is_deleted(self, cr, uid, module, xml_id, context=None):
        """
        Return True if record exists, False otherwise.

        Raise ValueError if ref module.xml_id doesn't exists.
        """
        data_id = self._get_id(cr, uid, module, xml_id)
        res = self.read(cr, uid, data_id, ['is_deleted'], context=context)
        return res['is_deleted']

    _order = 'id desc'

ir_model_data_sync()
