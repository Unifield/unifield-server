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
    
    def _get_model_ids(self, cr, uid, ids, field, arg, context={}):
        res = {}
        
        for query in self.browse(cr, uid, ids, context=context):
            tmp = self.on_change_object(cr, uid, query.id, query.object_id.id)
            res[query.id] = tmp['value']['model_ids']
            
        return res
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'user_id': fields.many2one('res.users', string='Creator', required=True),
        'object_id': fields.many2one('object.query.object', string='Object', required=True),
        'selection_ids': fields.many2many('ir.model.fields', 'query_fields_sel', 
                                          'query_id', 'field_id', string='Selection fields'),
        'selection_data': fields.one2many('object.query.selection_data', 'query_id', 'Values'), 
        'group_by_ids': fields.many2many('ir.model.fields', 'query_fields_group', 
                                          'query_id', 'field_id', string='Group by fields'),
        'result_ids': fields.one2many('object.query.result.fields', 'object_id', 
                                      string='Result fields'),
        'model_ids': fields.function(_get_model_ids, method=True, type='many2many', 
                                     relation='ir.model', string='Models'),
        'search_view_id': fields.many2one('ir.ui.view', string='Search View'),
        'tree_view_id': fields.many2one('ir.ui.view', string='Tree View'),
        'export_id': fields.many2one('ir.exports', string='Export')
        
    }
    
    _defaults = {
        'user_id': lambda obj, cr, uid, context: uid,
    }
    
    def _get_inherits_model(self, cr, uid, model_name):
        '''
        Get all inherited ir.model of an object
        '''
        res = []
        
        model = self.pool.get(model_name)
        
        if model._inherits:
            for table in model._inherits.keys():
                for name in self._get_inherits_model(cr, uid, table):
                    res.append(name)
        else:
            res.append(model_name)
                
        return res
    
    def on_change_object(self, cr, uid, ids, object_id):
        '''
        Change the value of model_id when the object changes
        '''
        res = {'selection_ids': [], 'model_ids': [],
               'group_by_ids': [],'result_ids': []}
        
        obj = self.pool.get('object.query.object')
        model_obj = self.pool.get('ir.model')
        
        if object_id:
            model = obj.browse(cr, uid, object_id)
            for model_name in self._get_inherits_model(cr, uid, model.model_id.model):
                model_id = model_obj.search(cr, uid, [('model', '=', model_name)])
                if model_id:
                    res['model_ids'].append(model_id[0])
                    
            # Insert the base model in the tab
            if model.model_id.id not in res['model_ids']:
                res['model_ids'].append(model.model_id.id)
            
        return {'value': res}
    
    def create_view(self, cr, uid, ids, context={}):
        '''
        Construct the view according to the user choices
        '''
        view_obj = self.pool.get('ir.ui.view')
        
        for query in self.browse(cr, uid, ids, context=context):
            search_view_id = query.search_view_id and query.search_view_id.id or False
            tree_view_id = query.tree_view_id and query.tree_view_id.id or False

            search_filters = ''
            search_group = ''
            tree_fields = ''
            tree_field_ids = []
            export_line_obj = self.pool.get('ir.exports.line')
            
            export_id = self.pool.get('ir.exports').create(cr, uid, {'name': query.name,
                                                                     'resource': query.object_id.model_id.model,})
    

            forced_values = []
            domain = []
            for filter_v in query.selection_data:
                forced_values.append(filter_v.field_id.id)
                if filter_v.field_id.ttype in ('date', 'datetime', 'int', 'float'):
                    if filter_v.value1:
                        domain.append((filter_v.field_id.name, '>=', filter_v.value1))
                    if filter_v.value2:
                        domain.append((filter_v.field_id.name, '<=', filter_v.value2))
                elif filter_v.field_id.ttype == 'boolean':
                    if filter_v.value1 == 't':
                        domain.append((filter_v.field_id.name, '=', 't'))
                    elif filter_v.value1 == 'f':
                        domain.append((filter_v.field_id.name, '=', 'f'))
                elif filter_v.field_id.ttype == 'many2one':
                    domain.append((filter_v.field_id.name, 'in', [int(filter_v.value1)]))
                else:
                    domain.append((filter_v.field_id.name, '=', filter_v.value1))
            
            for filter in query.selection_ids:
                if filter.id not in forced_values:
                    search_filters += "<field name='%s' />" % (filter.name)
                    search_filters += "\n"
                
            for result in query.result_ids:
                tree_fields += "<field name='%s' />" % (result.field_id.name)
                tree_fields += "\n"
                tree_field_ids.append(result.field_id.id)
                export_line_obj.create(cr, uid, {'name': result.field_id.name, 'export_id': export_id})
            
            for group in query.group_by_ids:
                search_group += "<filter context=\"{'group_by': '%s'}\" string='%s' domain=\"[]\" />" % (group.name, group.field_description)
                search_group += "\n"
                if group.id not in tree_field_ids:
                    tree_fields += "<field name='%s' invisible=\"1\" />" % (group.name)
                    tree_fields += "\n"

                
            search_arch = '''<search string='%s'>
            %s
            <newline/>
            <group expand="1" string="Group By..." groups="base.group_extended">
            %s
            </group>
            </search>
            ''' % (query.object_id.model_id.name, search_filters, search_group)
            
            tree_arch = '''<tree string='%s'>
            %s
            </tree>
            ''' % (query.object_id.model_id.name, tree_fields)
            
            search_view_data = {'name': 'query.search.%s.%s' %(query.object_id.model_id.model, query.id),
                                'model': query.object_id.model_id.model,
                                'priority': 250,
                                'type': 'search',
                                'arch': search_arch,
                                'context': "{'search_default_create_date': '2011-01-01', 'search_default_name': 'oo'}",
                                'xmd_id': 'object_query.query_search_%s_%s' %(query.object_id.model_id.model, query.id)}
            
            tree_view_data = {'name': 'query.tree.%s.%s' %(query.object_id.model_id.model, query.id),
                              'model': query.object_id.model_id.model,
                              'priority': 250,
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
           
            return {'type': 'ir.actions.act_window',
                    'res_model': query.object_id.model_id.model,
                    'search_view_id': [search_view_id],
                    'view_id': [tree_view_id],
                    'view_mode': 'tree,form',
                    'view_type': 'form',
                    'domain': domain,
                    'context': {'disable_cache': time.time()}}
        
        return {'type': 'ir.actions.act_window_close'}

    def open_wizard(self, cr, uid, ids, context={}):
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

    def unlink(self, cr, uid, ids, context={}):
        if isinstance(ids, (long, int)):
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

    def _coherence_search_value(self, cr, uid, ids, context={}):
        if isinstance(id, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids):
            if obj.selection_ids:
                search = [x.id for x in obj.selection_ids]
                to_del = []
                if obj.selection_data:
                    to_del = [ x.id for x in obj.selection_data  if x.field_id.id not in search]
                if to_del:
                    self.pool.get('object.query.selection_data').unlink(cr, uid, to_del)
        return True

    _constraints = [
        (_coherence_search_value, 'Always True', []),
    ]

object_query()


class object_query_selection_data(osv.osv):
    _name = 'object.query.selection_data'
    _description = 'Selection Values'
    _rec_name = 'field_id'

    def _get_text(self, cr, uid, ids, field, arg, context={}):
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

        if isinstance(ids, (long, int)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids):
            ret[obj.id] = ''
            if obj.field_id.ttype in ('date', 'datetime', 'int', 'float'):
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
        'text': fields.function(_get_text, type='char', method=True, string='Filtre'),
    }
object_query_selection_data()


class object_query_result_fields(osv.osv):
    _name = 'object.query.result.fields'
    _description = 'Result fields'
    _rec_name = 'field_id'
    
    def _get_model_ids(self, cr, uid, ids, field, arg, context={}):
        res = {}
        
        for result in self.browse(cr, uid, ids, context=context):
            res[result.id] = result.object_id.model_ids
            
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
    
    def _get_model_search(self, cr, uid, ids, field_name, args, context={}):
        '''
        Return the attached module
        '''
        res = {}
        
        for field in self.search(cr, uid, ids, context=context):
            res[field.id] = field.model_id.id
            
        return res
    
    def _search_model_search(self, cr, uid, obj, name, args, context={}):
        '''
        Return the domain according to the filter
        '''
        if not args:
            return []
        
        model_ids = []
        res_ids = []
        
        for a in args:        
            if a[0] == 'model_search_id' and a[1] == 'in' and a[2]:
                for arg in a[2]:
                    if arg[0] == 6:
                        for model_id in arg[2]:
                            model_ids.append(model_id)
            
            res_ids = self.search(cr, uid, [('model_id', 'in', model_ids)]) 
        
        return [('id', 'in', res_ids)]
    
    def _is_function(self, cr, uid, ids, field_name, args, context={}):
        '''
        Determines if the field is a function or not
        '''
        res = {}
        
        for field in self.browse(cr, uid, ids, context=context):
            res[field.id] = False
            if self.pool.get(field.model_id.model)._columns[field.name]._properties:
                res[field.id] = True
                
        return res
                
        
    def _search_function(self, cr, uid, obj, name, args, context={}):
        '''
        Return all fields which are a function field
        '''
        if not args:
            return []
        
        for a in args:
            if a[0] == 'is_function':
                field_ids = []
                all_fields_ids = []
                model_ids = context.get('model_ids', [(6,0,[])])[0][2]
                
                if not model_ids:
                    model_ids = self.pool.get('ir.model').search(cr, uid, [], context=context)
                    
                for obj in self.pool.get('ir.model').browse(cr, uid, model_ids, context=context):
                    for field in obj.field_id:
                        all_fields_ids.append(field.id)
                        if self.pool.get(obj.model)._columns[field.name]._properties:
                            field_ids.append(field.id)
                
                if (a[1] == '=' and a[2] == False) or (a[1] == '!=' and a[2] == True):
                    return [('id', 'not in', field_ids)]
                else:
                    return [('id', 'in', field_ids)]
            
        
        return []
        
    
    _columns = {
        'model_search_id': fields.function(_get_model_search,
                                           fnct_search=_search_model_search,
                                           method=True,
                                           type='many2one', relation='ir.model',
                                           string='Model'),
        'is_function': fields.function(_is_function, 
                                       fnct_search=_search_function, 
                                       method=True,
                                       type='boolean', string='Is function ?'),
    }
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        '''
        Call the view on context if there is.
        '''
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
        
    
ir_fields()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
