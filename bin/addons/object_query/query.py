# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
import time
from datetime import datetime
from tools.translate import _


class object_query_object(osv.osv):
    _name = 'object.query.object'
    _description = 'Object for query'

    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'model_id': fields.many2one('ir.model', string='Model', required=True),
    }

object_query_object()


class object_query(osv.osv):
    _name = 'object.query'
    _description = 'Object query'

    def _get_model_ids(self, cr, uid, ids, field, arg, context=None):
        res = {}
        model_obj = self.pool.get('ir.model')
        for query in self.browse(cr, uid, ids, context=context):
            res[query.id] = []
            if not query.object_id:
                continue
            for model_name in self._get_inherits_model(cr, uid, query.object_id.model_id.model):
                model_id = model_obj.search(cr, uid, [('model', '=', model_name)])
                if model_id:
                    res[query.id].append(model_id[0])

                # Insert the base model in the tab
                if query.object_id.model_id.id not in res[query.id]:
                    res[query.id].append(query.object_id.model_id.id)
        return res


    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'user_id': fields.many2one('res.users', string='Creator', required=True),
        'object_id': fields.many2one('object.query.object', string='Object'),
        'selection_ids': fields.many2many('ir.model.fields', 'query_fields_sel',
                                          'query_id', 'field_id', string='Search Fields'),
        'selection_data': fields.one2many('object.query.selection_data', 'query_id', 'Values'),
        'group_by_ids': fields.many2many('ir.model.fields', 'query_fields_group',
                                         'query_id', 'field_id', string='Group by fields'),
        'result_simple_ids': fields.many2many('ir.model.fields', 'result_simple_rel', 'query_id', 'field_id',
                                              string='Result fields'),
        'result_ids': fields.one2many('object.query.result.fields', 'object_id',
                                      string='Result order'),
        'model_ids': fields.function(_get_model_ids, method=True, type='many2many',
                                     relation='ir.model', string='Models'),
        'search_view_id': fields.many2one('ir.ui.view', string='Search View'),
        'tree_view_id': fields.many2one('ir.ui.view', string='Tree View'),
        'export_id': fields.many2one('ir.exports', string='Export'),
        'newquery': fields.boolean('New Query', readonly=1),

    }

    _defaults = {
        'user_id': lambda obj, cr, uid, context: uid,
        'newquery': lambda *a: True,
    }

    def dummy(self, cr, uid, ids, context):
        return True

    def reset_search_values(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        sel_date = self.pool.get('object.query.selection_data')
        r1 = sel_date.search(cr, uid, [('query_id', 'in', ids)])
        if r1:
            sel_date.unlink(cr, uid, r1)
        return True

    def change_object(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        result = self.pool.get('object.query.result.fields')
        r1 = result.search(cr, uid, [('object_id', 'in', ids)])
        if r1:
            result.unlink(cr, uid, r1)

        self.reset_search_values(cr, uid, ids, context)

        self.write(cr, uid, ids, {
            'object_id': False,
            'selection_ids': [(6, 0, [])],
            'group_by_ids': [(6, 0, [])],
            'result_simple_ids': [(6, 0, [])],
            'newquery': True,
        })
        return True

    def _get_inherits_model(self, cr, uid, model_name):
        '''
        Get all inherited ir.model of an object
        '''
        res = []

        model = self.pool.get(model_name)

        if model._inherits:
            for table in list(model._inherits.keys()):
                for name in self._get_inherits_model(cr, uid, table):
                    res.append(name)
        else:
            res.append(model_name)

        return res


    def create_view(self, cr, uid, ids, context=None):
        '''
        Construct the view according to the user choices
        '''
        view_obj = self.pool.get('ir.ui.view')
        export_line_obj = self.pool.get('ir.exports.line')
        export_obj = self.pool.get('ir.exports')
        self.set_sequence(cr, uid, ids)
        for query in self.browse(cr, uid, ids, context=context):
            search_view_id = query.search_view_id and query.search_view_id.id or False
            tree_view_id = query.tree_view_id and query.tree_view_id.id or False

            search_filters = ''
            search_group = ''
            tree_fields = ''
            tree_field_ids = []

            if query.export_id:
                export_obj.unlink(cr, uid, query.export_id.id)

            export_id = export_obj.create(cr, uid, {'name': query.name,
                                                    'resource': query.object_id.model_id.model,})
            self.write(cr, uid, [query.id], {'export_id': export_id})

            forced_values = []
            domain = []
            default_search = {}
            for filter_v in query.selection_data:
                if filter_v.field_id.state == 'deprecated':
                    continue
                dom = False
                forced_values.append(filter_v.field_id.id)

                if filter_v.field_id.ttype in ('date', 'datetime', 'integer', 'float'):
                    if filter_v.value1:
                        domain.append((filter_v.field_id.name, '>=', filter_v.value1))
                    if filter_v.value2:
                        domain.append((filter_v.field_id.name, '<=', filter_v.value2))
                    continue
                elif filter_v.field_id.ttype == 'boolean':
                    if filter_v.value1 == 't':
                        dom = (filter_v.field_id.name, '=', True)
                    elif filter_v.value1 == 'f':
                        dom = (filter_v.field_id.name, '=', False)
                elif filter_v.field_id.ttype == 'many2one':
                    dom = (filter_v.field_id.name, 'in', [int(filter_v.value1)])
                else:
                    dom = (filter_v.field_id.name, 'ilike', filter_v.value1)

                if dom:
                    if not filter_v.forced:
                        search_filters += "<field name='%s' />" % (filter_v.field_id.name)
                        default_search['search_default_%s'%(dom[0], )] = dom[2]
                        if filter_v.value1 == 'f':
                            # OpenERP bug
                            default_search['search_default_%s'%(dom[0], )] = '0'
                        elif isinstance(dom[2], list):
                            default_search['search_default_%s'%(dom[0], )] = dom[2][0]

                    else:
                        domain.append(dom)
            for filter in query.selection_ids:
                if filter.state == 'deprecated':
                    continue
                if filter.id not in forced_values:
                    search_filters += "<field name='%s' />" % (filter.name)
                    search_filters += "\n"

            for result in query.result_ids:
                if result.field_id.state == 'deprecated':
                    continue
                tree_fields += "<field name='%s' />" % (result.field_id.name)
                tree_fields += "\n"
                tree_field_ids.append(result.field_id.id)
                export_line_obj.create(cr, uid, {'name': result.field_id.name, 'export_id': export_id})

            for group in query.group_by_ids:
                if group.state == 'deprecated':
                    continue
                search_group += "<filter context=\"{'group_by': '%s'}\" string='%s' domain=\"[]\" />" % (group.name, group.field_description)
                search_group += "\n"
                if group.id not in tree_field_ids:
                    tree_fields += "<field name='%s' invisible=\"1\" />" % (group.name)
                    tree_fields += "\n"


            search_arch = '''<search string='%s'>
            %s
            <newline/>
            <group expand="1" string="Group By...">
            %s
            </group>
            </search>
            ''' % (query.object_id.model_id.name, search_filters, search_group)

            tree_arch = '''<tree string='%s' hide_new_button='1' hide_delete_button='1' noteditable="1">
            %s
            </tree>
            ''' % (query.object_id.model_id.name, tree_fields)

            search_view_data = {'name': 'query.search.%s.%s' %(query.object_id.model_id.model, query.id),
                                'model': query.object_id.model_id.model,
                                'priority': 2500 + query.id,
                                'type': 'search',
                                'arch': search_arch,
                                'xmd_id': 'object_query.query_search_%s_%s' %(query.object_id.model_id.model, query.id)}

            tree_view_data = {'name': 'query.tree.%s.%s' %(query.object_id.model_id.model, query.id),
                              'model': query.object_id.model_id.model,
                              'priority': 2500 + query.id,
                              'type': 'tree',
                              'arch': tree_arch,
                              'xmd_id': 'object_query.query_tree_%s_%s' %(query.object_id.model_id.model, query.id)}
            # Create or update views
            if search_view_id:
                view_obj.write(cr, uid, search_view_id, search_view_data, context=context)
            else:
                search_view_id = view_obj.create(cr, uid, search_view_data, context=context)

            if tree_view_id:
                view_obj.write(cr, uid, tree_view_id, tree_view_data, context=context)
            else:
                tree_view_id = view_obj.create(cr, uid, tree_view_data, context=context)

            self.write(cr, uid, query.id, {'search_view_id': search_view_id,
                                           'tree_view_id': tree_view_id}, context=context)

            default_search.update(disable_cache=time.time())
            return {'type': 'ir.actions.act_window',
                    'res_model': query.object_id.model_id.model,
                    'search_view_id': [search_view_id],
                    'view_id': [tree_view_id],
                    'view_mode': 'tree,form',
                    'view_type': 'form',
                    'domain': domain,
                    'context': default_search
                    }

        return {'type': 'ir.actions.act_window_close'}

    def populate_result(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids):
            existing = {}
            for field in obj.result_simple_ids:
                existing[field.id] = True
            to_create = []
            for search in obj.selection_ids:
                if search.id not in existing:
                    to_create.append((4, search.id))
            if to_create:
                self.write(cr, uid, obj.id, {'result_simple_ids': to_create })
        return True

    def set_sequence(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids):
            existing = {}
            max_seq = 0
            for ex in obj.result_ids:
                existing[ex.field_id.id] = ex.id
                max_seq = max(ex.sequence, max_seq)
            max_seq += 1
            values = []
            for field in obj.result_simple_ids:
                if field.id not in existing:
                    values.append((0, 0, {'sequence': max_seq, 'field_id': field.id}))
                    max_seq += 1
                else:
                    del(existing[field.id])

            if existing:
                for to_del in existing:
                    values.append((2, existing[to_del]))

            if values:
                self.write(cr, uid, [obj.id], {'result_ids':values})
        return True

    def open_wizard(self, cr, uid, ids, context=None):
        return {
            'name': 'Search Values',
            'type': 'ir.actions.act_window',
            'res_model': 'object.query.wizard.values',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': [],
            'context': {'disable_cache': time.time(), 'query_id': ids[0]}
        }

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]

        todel = []
        for obj in self.browse(cr, uid, ids):
            if obj.search_view_id:
                todel.append(obj.search_view_id.id)
            if obj.tree_view_id:
                todel.append(obj.tree_view_id.id)
        if todel:
            self.pool.get('ir.ui.view').unlink(cr, uid, todel, context=context)
        return super(object_query, self).unlink(cr, uid, ids, context)

    def _coherence_search_value(self, cr, uid, ids, context=None):
        if isinstance(id, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids):
            if obj.selection_ids:
                search = [x.id for x in obj.selection_ids]
                to_del = []
                if obj.selection_data:
                    to_del = [ x.id for x in obj.selection_data  if x.field_id.id not in search]
                if to_del:
                    self.pool.get('object.query.selection_data').unlink(cr, uid, to_del)
            if obj.object_id:
                cr.execute("update "+self._table+" set newquery='f'");  # not_a_user_entry
        return True

    _constraints = [
        (_coherence_search_value, 'Always True', []),
    ]

object_query()


class object_query_selection_data(osv.osv):
    _name = 'object.query.selection_data'
    _description = 'Search Values'
    _rec_name = 'field_id'

    def _get_text(self, cr, uid, ids, field, arg, context=None):
        if context is None:
            context = {}
        ret = {}
        user_obj = self.pool.get('res.users')
        lang_obj = self.pool.get('res.lang')
        user_lang = user_obj.read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
        lang_id = lang_obj.search(cr, uid, [('code','=',user_lang)])
        date_format = lang_id and lang_obj.read(cr, uid, lang_id[0], ['date_format'], context=context)['date_format'] or '%m/%d/%Y'
        time_format = lang_id and lang_obj.read(cr, uid, lang_id[0], ['time_format'], context=context)['time_format'] or '%H:%M'

        from_format = {'date': '%Y-%m-%d', 'datetime': '%Y-%m-%d %H:%M:%S'}
        to_format = {'date': date_format, 'datetime': '%s %s'%(date_format, time_format)}

        if isinstance(ids, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids):
            ret[obj.id] = ''
            if obj.field_id.ttype in ('date', 'datetime', 'integer', 'float'):
                if obj.value1:
                    if obj.field_id.ttype in ('date', 'datetime'):
                        obj.value1 = datetime.strptime(obj.value1, from_format[obj.field_id.ttype]).strftime(to_format[obj.field_id.ttype])
                    ret[obj.id] = "%s <= x"%(obj.value1,)
                else:
                    ret[obj.id] ="x"
                if obj.value2:
                    if obj.field_id.ttype in ('date', 'datetime'):
                        obj.value2 = datetime.strptime(obj.value2, from_format[obj.field_id.ttype]).strftime(to_format[obj.field_id.ttype])
                    ret[obj.id] += "<= %s"%(obj.value2,)
            elif obj.field_id.ttype == 'many2one':
                if obj.value1:
                    relation = self.pool.get(obj.field_id.model_id.model)._columns[obj.field_id.name]._obj
                    ret[obj.id] = self.pool.get(relation).name_get(cr, uid, [int(obj.value1)])[0][1]
            elif obj.field_id.ttype == 'selection':
                selection = self.pool.get(obj.field_id.model_id.model)._columns[obj.field_id.name].selection
                ret[obj.id] = dict(selection).get(obj.value1, '')
            elif obj.field_id.ttype == 'boolean':
                if obj.value1 == 't':
                    ret[obj.id] = _('Yes')
                if obj.value1 == 'f':
                    ret[obj.id] =  _('No')
            else:
                ret[obj.id] = obj.value1

        return ret

    _columns = {
        'query_id': fields.many2one('object.query', 'Query', required=True, ondelete='cascade'),
        'field_id': fields.many2one('ir.model.fields', 'Fields', required=True, ondelete='cascade'),
        'value1': fields.char('Value', size=2048),
        'value2': fields.char('Value2', size=2048),
        'forced': fields.boolean('Forced value'),
        'text': fields.function(_get_text, type='char', method=True, string='Filtre'),
    }
object_query_selection_data()


class object_query_result_fields(osv.osv):
    _name = 'object.query.result.fields'
    _description = 'Result fields'
    _rec_name = 'field_id'
    _order = 'sequence'

    def _get_model_ids(self, cr, uid, ids, field, arg, context=None):
        res = {}

        for result in self.browse(cr, uid, ids, context=context):
            res[result.id] = [x.id for x in result.object_id.model_ids]
        return res

    _columns = {
        'object_id': fields.many2one('object.query', string='Object', required=True, ondelete='cascade'),
        'field_id': fields.many2one('ir.model.fields', string='Field', required=True, ondelete='cascade'),
        'sequence': fields.integer(string='Sequence', required=True),
        'model_ids': fields.function(_get_model_ids, method=True, type='many2many',
                                     relation='ir.model', string='Models'),
    }

object_query_result_fields()


class ir_fields(osv.osv):
    _name = 'ir.model.fields'
    _inherit = 'ir.model.fields'

    def _get_model_search(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the attached module
        '''
        res = {}

        for field in self.browse(cr, uid, ids, context=context):
            res[field.id] = field.model_id.id

        return res

    def _search_model_search(self, cr, uid, obj, name, args, context=None):
        '''
        Return the domain according to the filter
        '''
        if not args:
            return []

        model_ids = []

        for a in args:
            if a[0] == 'model_search_id' and a[1] == 'in' and a[2]:
                for arg in a[2]:
                    if arg[0] == 6:
                        for model_id in arg[2]:
                            model_ids.append(model_id)

            return [('model_id', 'in', model_ids), ('state', '!=', 'deprecated')]

        return [('id', '=', 0)]

    def _is_function(self, cr, uid, ids, field_name, args, context=None):
        '''
        Determines if the field is a function or not
        '''
        res = {}

        for field in self.browse(cr, uid, ids, context=context):
            res[field.id] = False
            if self.pool.get(field.model_id.model)._columns[field.name]._properties:
                res[field.id] = True

        return res


    def _search_function(self, cr, uid, obj, name, args, context=None):
        '''
        Return all fields which are a function field
        '''
        if not args:
            return []
        if context is None:
            context = {}
        for a in args:
            if a[0] in ['is_function', 'is_unsearchable']:
                field_ids = []
                all_fields_ids = []
                model_ids = context.get('model_ids', [(6,0,[])])[0][2]

                if not model_ids:
                    return [('id', '=', 0)]
                    #model_ids = self.pool.get('ir.model').search(cr, uid, [], context=context)

                for obj in self.pool.get('ir.model').browse(cr, uid, model_ids, context=context):
                    model_obj = self.pool.get(obj.model)
                    for field in obj.field_id:
                        all_fields_ids.append(field.id)
                        col = model_obj._columns.get(field.name)
                        if col and hasattr(col, '_properties') and col._properties and not col.store:
                            if a[0] == 'is_function':
                                field_ids.append(field.id)
                            elif not isinstance(col, fields.related):
                                # only allow fnct_search on product.sdref to prevent traceback: "Filter not implemented'
                                if obj.model != 'product.product' or field.name != 'sdref':
                                    field_ids.append(field.id)

                if (a[1] == '=' and a[2] == False) or (a[1] == '!=' and a[2] == True):
                    return [('id', 'not in', field_ids)]
                else:
                    return [('id', 'in', field_ids)]

        return []

    def _get_help(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if isinstance(ids, int):
            ids = [ids]

        for obj in self.browse(cr, uid, ids):
            res[obj.id] = False
            target_obj = self.pool.get(obj.model_id.model)
            if target_obj and obj.name in target_obj._columns:
                res[obj.id] = target_obj._columns[obj.name].help
        return res


    _columns = {
        'help': fields.function(_get_help, method=True, type='char', size='10000', string='Help'),
        'model_search_id': fields.function(_get_model_search,
                                           fnct_search=_search_model_search,
                                           method=True,
                                           type='many2one', relation='ir.model',
                                           string='Model'),
        'is_function': fields.function(_is_function,
                                       fnct_search=_search_function,
                                       method=True,
                                       type='boolean', string='Is function ?'),
        'is_unsearchable': fields.function(_is_function,
                                           fnct_search=_search_function,
                                           method=True,
                                           type='boolean', string='Is searchable ?'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Call the view on context if there is.
        '''
        if context is None:
            context = {}
        if view_type == 'tree' and context and 'special_tree_id' in context:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'object_query', context.get('special_tree_id'))[1]
        if view_type == 'search' and context and 'special_search_id' in context:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'object_query', context.get('special_search_id'))[1]

        return super(ir_fields, self).fields_view_get(cr, uid,
                                                      view_id=view_id,
                                                      view_type=view_type,
                                                      context=context,
                                                      toolbar=toolbar,
                                                      submenu=submenu)


    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}
        if 'special_search_id' in context:
            # remove duplicate fields name and reference in product
            exclude_prod = ['code', 'name_template', 'nomen_ids']
            exclude_templ = ['nomen_manda_0_s', 'nomen_manda_1_s', 'nomen_manda_2_s', 'nomen_manda_3_s', 'nomen_sub_0_s', 'nomen_sub_1_s', 'nomen_sub_2_s', 'nomen_sub_3_s', 'nomen_sub_4_s', 'nomen_sub_5_s']
            ids_to_remove = self.search(cr, uid, [('name', 'in', exclude_prod), ('model_id', '=', 'product.product')]) + \
                self.search(cr, uid, [('name', 'in', exclude_templ), ('model_id', '=', 'product.template')])
            if ids_to_remove:
                args.append(('id', 'not in', ids_to_remove))

        return super(ir_fields, self).search(cr, uid, args, offset, limit,
                                             order, context, count)

ir_fields()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
