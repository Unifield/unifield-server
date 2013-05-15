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

from osv import osv, fields
import tools
import logging
from sync_common import MODELS_TO_IGNORE, XML_ID_TO_IGNORE

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
        GROUP BY ir_model_data.model, ir_model_data.res_id HAVING COUNT(%(table)s.id) = 0""" \
                % {'table':self.pool.get(model)._table}, [model, tuple(res_ids), tuple(ids)])
            for data_ids, exists in cr.fetchall():
                res.update(dict((id, not exists) for id in data_ids))
        return res

    def _set_is_deleted(self, cr, uid, ids, field, value, args, context=None):
        if not value or context.get('avoid_ir_data_deletion'): return True
        datas = {}
        for data in self.read(cr, uid, ids, ['model','res_id'], context=context):
            datas.setdefault(data['model'], set()).add(data['res_id'])
        for model, ids in datas.items():
            self.pool.get(model).unlink(cr, uid, list(ids))
        return True

    _columns={
        'sync_date':fields.datetime('Last Synchronization Date'),
        'version':fields.integer('Version'),
        'last_modification':fields.datetime('Last Modification Date'),
        'is_deleted' : fields.function(string='The record exists in database?', type='boolean',
            fnct=_get_is_deleted, fnct_inv=_set_is_deleted, fnct_search=_get_is_deleted, method=True),
    }

    _defaults={
        'version' : 1,
        'is_deleted' : False,
    }

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
UPDATE ir_model_data SET """+", ".join("%s = %%s" % k for k in rec.keys())+""" WHERE id = %s""", rec.values() + [id])
                cr.execute("""CREATE UNIQUE INDEX unique_sdref_constraint ON ir_model_data (model, res_id) WHERE module = 'sd'""")
                cr.commit()
                self._logger.info("%d sdref(s) deleted, %d kept." % (len(to_delete), len(to_write)))
            except:
                cr.execute("ROLLBACK TO SAVEPOINT make_sdref_constraint")
                raise
        # Make sd reference to every object
        ids = self.search(cr, 1, [('model', 'not in', MODELS_TO_IGNORE), ('module', '!=', 'sd'), ('name', 'not in', XML_ID_TO_IGNORE)], context=context)
        for rec in self.browse(cr, 1, ids):
            name = "%s_%s" % (rec.module, rec.name)
            res_ids = self.search(cr, 1, [('module','=','sd'),('res_id','=',rec.res_id)])
            if res_ids:
                continue
            args = {
                    'noupdate' : False, # don't set to True otherwise import won't work
                    'model' :rec.model,
                    'module' : 'sd',#model._module,
                    'name' : name,
                    'res_id' : rec.res_id,
                    }
            self.create(cr, 1, args)
        return res

    def create(self,cr,uid,values,context=None):
        if values['module'] == 'sd':
            old_xmlids = self.search(cr, uid, [('module','=','sd'),('model','=',values['model']),('res_id','=',values['res_id'])], context=context)
            self.unlink(cr, uid, old_xmlids, context=context)

        id = super(ir_model_data_sync, self).create(cr, uid, values, context=context)

        if not values['module'] == 'sd':
            xmlid = "%s_%s" % (values['module'], values['name'])
            sd_ids  = self.search(cr, uid, [('module', '=', 'sd'), ('name', '=', xmlid)], context=context)
            assert len(sd_ids) < 2, \
                   "Oops...! I already have multiple 'sd' xml_ids for this object id=%s" % xmlid

            args = {
                    'noupdate' : False, # don't set to True otherwise import won't work
                    'model' : values['model'],
                    'module' : 'sd',
                    'name' : xmlid,
                    'res_id' : values['res_id'],
                   }
            if sd_ids:
                data = self.browse(cr, uid, sd_ids, context=context)[0]
                assert data.res_id == values['res_id'], \
                       "Oops...! There is multiple resources for a unique xml_id! Expected: %s, got: %s" \
                       % (values['res_id'], data.res_id)
                self.write(cr, uid, sd_ids, args, context=context)
            else:
                self.create(cr, uid, args, context=context)

        return id

    # TODO replace this deprecated method with get_sd_ref(field='id') in your call
    # Beware that the result is a dict, not a list anymore
    def get(self, cr, uid, model, ids, context=None):
        if tools.config.options['log_level'] <= logging.DEBUG:
            raise DeprecationWarning("ir.model.data get() method should not be used anymore!")
        else:
            self._logger.warning("ir.model.data get() method should not be used anymore!")
        result = []
        for id in (ids if hasattr(ids, '__iter__') else [ids]):
            data_ids = self.search(cr, uid, [('model', '=', model._name), ('res_id', '=', id), ('module', '=', 'sd')], limit=1, context=context)
            result.append(data_ids[0] if data_ids else False)
        return result if isinstance(ids, (list, tuple)) else result[0]

    def update_sd_ref(self, cr, uid, sdrefs, context=None):
        """Update SD refs information. sdrefs should be dict of where values are update values of the sdref"""
        assert hasattr(sdrefs, 'items'), "Argument sdrefs should be a dictionary"
        for sdref, values in sdrefs.items():
            cr.execute("""\
UPDATE %s SET %s WHERE module = 'sd' AND name = %%s
""" % (self._table, ", ".join("%s = %%s" % k for k in values.keys())), values.values() + [sdref])

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
