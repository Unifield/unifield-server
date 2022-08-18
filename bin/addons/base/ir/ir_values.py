# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from osv import osv,fields
from osv.orm import except_orm
import json
import tools

EXCLUDED_FIELDS = set((
    'report_sxw_content', 'report_rml_content', 'report_sxw', 'report_rml',
    'report_sxw_content_data', 'report_rml_content_data', 'search_view', ))

class ir_values(osv.osv):
    _name = 'ir.values'

    @tools.read_cache(prefetch=[], context=['lang', 'client', 'tz', 'department_id', 'active_model', '_terp_view_name', 'active_ids', 'active_id'], timeout=8000, size=2000)
    def _read_flat(self, cr, user, ids, fields_to_read, context=None, load='_classic_read'):
        return super(ir_values, self)._read_flat(cr, user, ids, fields_to_read, context, load)

    def _clean_cache(self, dbname):
        super(ir_values, self)._clean_cache(dbname)
        # radical but this doesn't frequently happen
        self._read_flat.clear_cache(dbname)

    def _real_unpickle(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for ir_value in self.read(cr, uid, ids, ['value'], context=context):
            res[ir_value['id']] = False
            if ir_value['value']:
                try:
                    res[ir_value['id']] = json.loads(ir_value['value'])
                except:
                    pass
        return res

    def _value_unpickle(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            value = report[name[:-9]]
            if not report.object and value:
                try:
                    value = json.loads(value)
                except:
                    pass
            res[report.id] = value
        return res

    def _value_pickle(self, cursor, user, id, name, value, arg, context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        if self.CONCURRENCY_CHECK_FIELD in ctx:
            del ctx[self.CONCURRENCY_CHECK_FIELD]
        if not self.browse(cursor, user, id, context=context).object:
            value = json.dumps(value)
        self.write(cursor, user, id, {name[:-9]: value}, context=ctx)

    def onchange_object_id(self, cr, uid, ids, object_id, context={}):
        if not object_id: return {}
        act = self.pool.get('ir.model').browse(cr, uid, object_id, context=context)
        return {
            'value': {'model': act.model}
        }

    def onchange_action_id(self, cr, uid, ids, action_id, context={}):
        if not action_id: return {}
        act = self.pool.get('ir.actions.actions').browse(cr, uid, action_id, context=context)
        return {
            'value': {'value_unpickle': act.type+','+str(act.id)}
        }

    _columns = {
        'name': fields.char('Name', size=128),
        'model_id': fields.many2one('ir.model', 'Object', size=128,
                                    help="This field is not used, it only helps you to select a good model."),
        'model': fields.char('Object Name', size=128, select=True),
        'action_id': fields.many2one('ir.actions.actions', 'Action',
                                     help="This field is not used, it only helps you to select the right action."),
        'value': fields.text('Value'),
        'value_unpickle': fields.function(_value_unpickle, fnct_inv=_value_pickle,
                                          method=True, type='text', string='Value'),
        'real_value':  fields.function(_real_unpickle, method=True, type='text', string='Value'),
        'object': fields.boolean('Is Object'),
        'key': fields.selection([('action','Action'),('default','Default')], 'Type', size=128, select=True),
        'key2' : fields.char('Event Type',help="The kind of action or button in the client side that will trigger the action.", size=128, select=True),
        'meta': fields.text('Meta Datas'),
        'meta_unpickle': fields.function(_value_unpickle, fnct_inv=_value_pickle,
                                         method=True, type='text', string='Metadata'),
        'res_id': fields.integer('Object ID', help="Keep 0 if the action must appear on all resources.", select=True),
        'user_id': fields.many2one('res.users', 'User', ondelete='cascade', select=True),
        'company_id': fields.many2one('res.company', 'Company', select=True),
        'sequence': fields.integer('Sequence'),
        'view_ids': fields.many2many('ir.ui.view', 'actions_view_rel', 'action_id', 'view_id', 'Linked views'),
    }
    _defaults = {
        'key': lambda *a: 'action',
        'key2': lambda *a: 'tree_but_open',
        'company_id': lambda *a: False,
        'sequence':  lambda *a: 100,
    }

    def _auto_init(self, cr, context=None):
        super(ir_values, self)._auto_init(cr, context)
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = \'ir_values_key_model_key2_res_id_user_id_idx\'')
        if not cr.fetchone():
            cr.execute('CREATE INDEX ir_values_key_model_key2_res_id_user_id_idx ON ir_values (key, model, key2, res_id, user_id)')

    def set(self, cr, uid, key, key2, name, models, value, replace=True, isobject=False, meta=False, preserve_user=False, company=False, view_ids=False):
        if not isobject:
            value = json.dumps(value)
        if key != 'default' and meta:
            meta = json.dumps(meta)
        ids_res = []

        uid_access = uid
        if key == 'default' and uid != 1 and (preserve_user or self.pool.get('res.users').get_admin_profile(cr, uid)):
            uid_access = 1

        for model in models:
            if isinstance(model, (list, tuple)):
                model,res_id = model
            else:
                res_id=False
            if replace:
                search_criteria = [
                    ('key', '=', key),
                    ('key2', '=', key2),
                    ('model', '=', model),
                    ('res_id', '=', res_id),
                    ('user_id', '=', preserve_user and uid)
                ]
                if key in ('meta', 'default'):
                    search_criteria.append(('name', '=', name))
                else:
                    search_criteria.append(('value', '=', value))

                self.unlink(cr, uid_access, self.search(cr, uid, search_criteria))
            vals = {
                'name': name,
                'value': value,
                'model': model,
                'object': isobject,
                'key': key,
                'key2': key2 and key2[:200],
                'meta': meta,
                'user_id': preserve_user and uid,
            }

            if view_ids:
                vals['view_ids'] = [(6, 0, view_ids)]
            if preserve_user and key == 'default':
                vals['sequence'] = 50

            if company:
                cid = self.pool.get('res.users').browse(cr, uid, uid, context={}).company_id.id
                vals['company_id']=cid
            if res_id:
                vals['res_id']= res_id

            ids_res.append(self.create(cr, uid_access, vals))
        return ids_res

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True, view_id=False):
        if context is None:
            context = {}
        result = []
        for m in models:
            if isinstance(m, (list, tuple)):
                m, res_id = m
            else:
                res_id=False

            where = ['key=%s','model=%s']
            join = ''
            params = [key, str(m)]
            if key2:
                where.append('key2=%s')
                params.append(key2[:200])
            elif key2_req and not meta:
                where.append('key2 is null')
            if res_id_req and (models[-1][0]==m):
                if res_id:
                    where.append('res_id=%s')
                    params.append(res_id)
                else:
                    where.append('(res_id is NULL)')
            elif res_id:
                if (models[-1][0]==m):
                    where.append('(res_id=%s or (res_id is null))')
                    params.append(res_id)
                else:
                    where.append('res_id=%s')
                    params.append(res_id)

            if key == 'action' and view_id:
                join = 'left join actions_view_rel r on r.action_id=ir_values.id'
                where.append('(view_id is NULL or view_id=%s)')
                params.append(view_id)
            if key == 'default':
                if meta != 'web':
                    where.append("coalesce(meta,'')!='web'")
                if context.get('sync_update_execution') or context.get('sync_message_execution'):
                    where.append('user_id IS NULL order by sequence,id')
                else:
                    where.append('(user_id=%s or (user_id IS NULL)) order by sequence,id')
                    params.append(uid)
            else:
                where.append('(user_id=%s or (user_id IS NULL)) order by sequence,id')
                params.append(uid)
            clause = ' and '.join(where)

            cr.execute('select id,name,value,object,meta, key from ir_values '+ join +' where ' + clause, params)  # not_a_user_entry
            result = cr.fetchall()
            if result:
                break

        # for the admin only add the "Update Sent / Received" links in the menu on the right for all synched objects
        if key == 'action' and key2 == 'client_action_relate' and uid == 1 and self.pool.get('update.link') and models:
            obj_model = models[0][0]
            act_to_add = []
            if self.pool.get('sync.client.rule').search_exist(cr, uid, [('model', '=', obj_model), ('type', '!=', 'USB')]):
                act_sent_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sync_client', 'action_open_updates_sent')[1]
                act_to_add.append((act_sent_id, 'Updates_Sent', 'ir.actions.server,%d' % act_sent_id, True, None, 'action'))
                act_rcv_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sync_client', 'action_open_updates_received')[1]
                act_to_add.append((act_rcv_id, 'Updates_Received', 'ir.actions.server,%d' % act_rcv_id, True, None, 'action'))

                if obj_model == 'product.product':
                    # on product updates links are not at the end
                    new_res = []
                    for x in result:
                        new_res.append(x)
                        if x[1] == 'View_log_product.product':
                            new_res += act_to_add
                    result = new_res
                else:
                    result += act_to_add

        if not result:
            return []

        def _result_get(x, keys):
            if x[1] in keys:
                return False
            keys.append(x[1])
            if x[3]:
                model,id = x[2].split(',')
                # FIXME: It might be a good idea to opt-in that kind of stuff
                # FIXME: instead of arbitrarily removing random fields
                fields = [
                    field
                    for field in self.pool.get(model).fields_get_keys(cr, uid)
                    if field not in EXCLUDED_FIELDS]

                try:
                    datas = self.pool.get(model).read(cr, uid, [int(id)], fields, context)
                except except_orm:
                    return False
                datas = datas and datas[0]
                if not datas:
                    return False
            else:
                datas = json.loads(x[2])
            if meta and meta != 'web':
                return (x[0], x[1], datas, json.loads(x[4]))
            return (x[0], x[1], datas)
        keys = []
        res = [_f for _f in [_result_get(x, keys) for x in result] if _f]
        res2 = res[:]
        for r in res:
            if isinstance(r[2], dict) and r[2].get('type') in ('ir.actions.report.xml','ir.actions.act_window','ir.actions.wizard'):
                groups = r[2].get('groups_id')
                if groups:
                    cr.execute('SELECT COUNT(1) FROM res_groups_users_rel WHERE gid IN %s AND uid=%s',(tuple(groups), uid))
                    cnt = cr.fetchone()[0]
                    if not cnt:
                        res2.remove(r)
                    if r[1] == 'Menuitem' and not res2:
                        raise osv.except_osv('Error !','You do not have the permission to perform this operation !!!')
        return res2

ir_values()
