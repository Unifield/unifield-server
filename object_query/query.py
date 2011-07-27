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
        'group_by_ids': fields.many2many('ir.model.fields', 'query_fields_group', 
                                          'query_id', 'field_id', string='Group by fields'),
        'result_ids': fields.one2many('object.query.result.fields', 'object_id', 
                                      string='Result fields'),
        'model_ids': fields.function(_get_model_ids, method=True, type='many2many', 
                                     relation='ir.model', string='Models'),
        'search_view_id': fields.many2one('ir.ui.view', string='Search View'),
        'tree_view_id': fields.many2one('ir.ui.view', string='Tree View'),
        
    }
    
    _defaults = {
        'user_id': lambda obj, cr, uid, context: uid,
    }
    
    def _get_inherits_model(self, cr, uid, model_name):
        '''
        Get all inherited objects
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
        res = {'model_ids': []}
        
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
            search_filters = ''
            search_group = ''
            tree_fields = ''
            tree_field_ids = []
            
            for filter in query.selection_ids:
                search_filters += "<field name='%s' />" % (filter.name)
                search_filters += "\n"
                
            for result in query.result_ids:
                tree_fields += "<field name='%s' />" % (result.field_id.name)
                tree_fields += "\n"
                tree_field_ids.append(result.field_id.id)
            
            for group in query.group_by_ids:
                search_group += "<filter context=\"{'group_by': '%s'}\" string='%s' domain=\"[]\" />" % (group.name, group.field_description)
                search_group += "\n"
                if group not in tree_field_ids:
                    tree_fields += "<field name='%s' invisible=\"1\" />" % (group.name)

                
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
                                'xmd_id': 'object_query.query_search_%s_%s' %(query.object_id.model_id.model, query.id)}
            
            tree_view_data = {'name': 'query.tree.%s.%s' %(query.object_id.model_id.model, query.id),
                              'model': query.object_id.model_id.model,
                              'priority': 250,
                              'type': 'tree',
                              'arch': tree_arch,
                              'xmd_id': 'object_query.query_tree_%s_%s' %(query.object_id.model_id.model, query.id)}
            
            # Create views
            search_view_id = view_obj.create(cr, uid, search_view_data, context=context)
            tree_view_id = view_obj.create(cr, uid, tree_view_data, context=context)
            
            self.write(cr, uid, query.id, {'search_view_id': search_view_id,
                                           'tree_view_id': tree_view_id}, context=context)
            
            return {'type': 'ir.actions.act_window',
                    'res_model': query.object_id.model_id.model,
                    'search_view_id': [search_view_id],
                    'view_id': [tree_view_id],
                    'view_mode': 'tree,form',
                    'view_type': 'form'}
        
        return {'type': 'ir.actions.act_window_close'}
    
object_query()


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
        'object_id': fields.many2one('object.query', string='Object', required=True),
        'field_id': fields.many2one('ir.model.fields', string='Field', required=True),
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
    
    _columns = {
        'model_search_id': fields.function(_get_model_search,
                                           fnct_search=_search_model_search,
                                           method=True,
                                           type='many2one', relation='ir.model',
                                           string='Model'),
    }
    
ir_fields()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: