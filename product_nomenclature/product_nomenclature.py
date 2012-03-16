# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
from tools.translate import _
import decimal_precision as dp
import math
import re
import tools
from os import path
import logging

# maximum depth of level
_LEVELS = 4
# numbers of sub levels (optional levels)
_SUB_LEVELS = 6

#----------------------------------------------------------
# Nomenclatures
#----------------------------------------------------------
class product_nomenclature(osv.osv):

    def init(self, cr):
        """
        Load product_nomenclature_data.xml brefore product
        """
        if hasattr(super(product_nomenclature, self), 'init'):
            super(product_nomenclature, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'product_nomenclature')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module product_nomenclature: loading product_nomenclature_data.xml')
            pathname = path.join('product_nomenclature', 'product_nomenclature_data.xml')
            file = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'product_nomenclature', file, {}, mode='init', noupdate=False)

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        if context is None:
            context = {}
        fields = ['name','parent_id']
        if context.get('withnum') == 1:
            fields.append('number_of_products')
        reads = self.read(cr, uid, ids, fields, context=context)
        res = []
        for record in reads:
            name = record['name']
            if not context.get('nolevel') and record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            if context.get('withnum') == 1:
                name = "%s (%s)"%(name, record['number_of_products'])
            res.append((record['id'], name))
        return res

    
    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)
    
    def _returnConstants(self):
        '''
        return contants of product_nomenclature object
        '''
        return {'levels':_LEVELS, 'sublevels':_SUB_LEVELS}
    
    def _getDefaultLevel(self, cr, uid, context=None):
        '''
        Return the default level for the created object.
        Default value is equal to 1
        cannot be modified by the user (not displayed on screen)
        '''
        # default level is 1 if no parent it is a root
        result = 0
        
        #test = self._columns.get('parent_id')
        #test = self._columns['name']
        #print test
        
        # get the parent object's level + 1
        #result = self.browse(cr, uid, self.parent_id, context).level + 1
        
        return result
    
    def _getDefaultSequence(self, cr, uid, context=None):
        '''
        not use presently. the idea was to use the sequence
        in order to sort nomenclatures in the tree view
        '''
        return 0
        
    def onChangeParentId(self, cr, uid, id, type, parentId):
        '''
        parameters:
        - type : the selected type for nomenclature
        - parentId : the id of newly selected parent nomenclature
        
        onChange method called when the parent nomenclature changes updates the parentLevel value from the parent object
        
        improvement :
        
        '''
        value = {'level': 0}
        result = {'value': value, 'warning': {}}
        
        # empty field
        if not parentId:
            return result
        
        parentLevel = self.browse(cr, uid, parentId).level
        level = parentLevel + 1
        
        # level check - parent_id : False + error message
        if level > _LEVELS:
            result['value'].update({'parent_id': False})
            result['warning'].update({'title': _('Error!'), 'message': _('The selected nomenclature should not be proposed.')})
            return result
        
        if level == _LEVELS:
            # this nomenclature must be of type optional
            if type != 'optional':
                result['value']['parent_id'] = False
                result['warning'].update({
                    'title': _('Warning!'),
                    'message': _("You selected a nomenclature of the last mandatory level as parent, the new nomenclature's type must be 'optional'."),
                    })
                return result
            
        # selected parent ok
        result['value']['level'] = level
        
        return result
    
    def _nomenclatureCheck(self, vals):
        '''
        Integrity function for creation and update of nomenclature
        
        check level value and type value
        '''
        if ('level' in vals) and ('type' in vals):
            level = vals['level']
            type = vals['type']
            # level test
            if level > _LEVELS:
                raise osv.except_osv(_('Error'), _('Level (%s) must be smaller or equal to %s'%(level,_LEVELS)))
            # type test
            if (level == _LEVELS) and (type != 'optional'):
                raise osv.except_osv(_('Error'), _('The type (%s) must be equal to "optional" to inherit from leaves'%(type)))
    
    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method to check the validity of selected
        parent
        '''
        self._nomenclatureCheck(vals)

        # save the data to db
        return super(product_nomenclature, self).write(cr, user, ids, vals, context)
    
    def create(self, cr, user, vals, context=None):
        '''
        override create method to check the validity of selected parent
        '''
        self._nomenclatureCheck(vals)

        # save the data to db
        return super(product_nomenclature, self).create(cr, user, vals, context)
    
    def _getNumberOfProducts(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the number of products for the nomenclature
        '''
        res = {}
        
        for nomen in self.browse(cr, uid, ids, context=context):
            name = ''
            if nomen.type == 'mandatory':
                name = 'nomen_manda_%s'%nomen.level
            if nomen.type == 'optional':
                name = 'nomen_sub_%s'%nomen.sub_level
            products = self.pool.get('product.product').search(cr, uid, [(name, '=', nomen.id)], context=context)
            if not products:
                res[nomen.id] = 0
            else:
                res[nomen.id] = len(products)
            
        return res
    
    def _search_complete_name(self, cr, uid, obj, name, args, context={}):
        if not args:
            return []
        if args[0][1] != "=":
            raise osv.except_osv(_('Error !'), 'Filter not implemented on %s'%(name,))

        parent_ids = None
        for path in args[0][2].split('/'):
            dom = [('name', '=ilike', path.strip())]
            if parent_ids is None:
                dom.append(('parent_id', '=', False))
            else:
                dom.append(('parent_id', 'in', parent_ids))
            ids = self.search(cr, uid, dom)
            if not ids:
                return [('id', '=', 0)]
            parent_ids = ids

        return [('id', 'in', ids)]

    _name = "product.nomenclature"
    _description = "Product Nomenclature"
    _columns = {
        'name': fields.char('Name', size=64, required=True, select=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Name', fnct_search=_search_complete_name),
        # technic fields - tree management
        'parent_id': fields.many2one('product.nomenclature','Parent Nomenclature', select=True),
        # TODO try to display child_ids on screen. which result ?
        'child_id': fields.one2many('product.nomenclature', 'parent_id', string='Child Nomenclatures'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of product nomenclatures."),
        'level': fields.integer('Level', size=256, select=1),
        'type': fields.selection([('mandatory','Mandatory'), ('optional','Optional')], 'Nomenclature Type', select=1),
        # corresponding level for optional levels, must be string, because integer 0 is treated as False, and thus required test fails
        'sub_level': fields.selection([('0', '1'), ('1', '2'), ('2', '3'), ('3', '4'), ('4', '5'), ('5', '6')], 'Sub-Level', size=256),
        'number_of_products': fields.function(_getNumberOfProducts, type='integer', method=True, store=False, string='Number of Products', readonly=True),
    }

    _defaults = {
                 'level' : _getDefaultLevel, # no access to actual new values, use onChange function instead
                 'type' : lambda *a : 'mandatory',
                 'sub_level': lambda *a : '0',
                 'sequence': _getDefaultSequence,
    }

    _order = "sequence, id"
    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from product_nomenclature where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive nomenclature.', ['parent_id'])
    ]
    def child_get(self, cr, uid, ids):
        return [ids]
    
    def get_nomen(self, cr, uid, obj, id, field, context={}):
        if context is None:
            context = {}
        context['nolevel'] = 1
        parent = {'nomen_manda_1': 'nomen_manda_0', 'nomen_manda_2': 'nomen_manda_1', 'nomen_manda_3': 'nomen_manda_2'}
        level = {'nomen_manda_1': 1, 'nomen_manda_2': 2, 'nomen_manda_3': 3}
        p_id = obj.read(cr, uid, id, [parent[field]])[parent[field]]
        # when dealing with osv_memory, the read method for many2one returns the id and not the tuple (id, name) as for osv.osv
        if p_id and isinstance(p_id, int):
            name = self.name_get(cr, uid, [p_id], context=context)[0]
            p_id = name
        dom = [('level', '=',  level.get(field)), ('type', '=', 'mandatory'), ('parent_id', '=', p_id and p_id[0] or 0)]
        return self._name_search(cr, uid, '', dom, limit=None, name_get_uid=1, context=context)
    
    def get_sub_nomen(self, cr, uid, obj, id, field):
        parent = ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3']
        level = {'nomen_sub_0': '0', 'nomen_sub_1': '1', 'nomen_sub_2': '2', 'nomen_sub_3': '3', 'nomen_sub_4': '4', 'nomen_sub_5': '5'}
        read = parent + level.keys()
        nom = obj.read(cr, uid, id, read)
        parent_id = [False]
        for p in parent:
            if nom[p]:
                parent_id.append(nom[p][0])
        sub = []
        for p in level.keys():
            if p != field and nom[p]:
                sub.append(nom[p][0])
        dom = [('type', '=', 'optional'), ('parent_id', 'in', parent_id), ('sub_level', '=', level.get(field)),  ('id', 'not in', sub)]
        return [('','')]+self._name_search(cr, uid, '', dom, limit=None, name_get_uid=1, context={'nolevel':1})

product_nomenclature()

#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):
    
    _inherit = "product.template"
    _description = "Product Template"

    def _get_nomen_s(self, cr, uid, ids, fields, *a, **b):
        value = {}
        for f in fields:
            value[f] = False

        ret = {}
        for id in ids:
            ret[id] = value
        return ret
    
    def _search_nomen_s(self, cr, uid, obj, name, args, context={}):

        if not args:
            return []
        narg = []
        for arg in args:
            el = arg[0].split('_')
            el.pop()
            narg=[('_'.join(el), arg[1], arg[2])]
        
        return narg

    ### EXACT COPY-PASTE TO order_nomenclature
    _columns = {
                # mandatory nomenclature levels
                'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', required=True, select=1),
                'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', required=True, select=1),
                'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', required=True, select=1),
                'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', required=True, select=1),

                # optional nomenclature levels
                'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1', select=1),
                'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2', select=1),
                'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3', select=1),
                'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4', select=1),
                'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5', select=1),
                'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6', select=1),
                
# for search view :(
                'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),

                'nomen_sub_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 1', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 2', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 3', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 4', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_4_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 5', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_5_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 6', fnct_search=_search_nomen_s, multi="nom_s"),

                # concatenation of nomenclature in a visible way
                'nomenclature_description': fields.char('Nomenclature', size=1024),
    }
    ### END OF COPY

    def _get_default_nom(self, cr, uid, context={}):
        res = {}
        toget = [('nomen_manda_0', 'nomen_med'), ('nomen_manda_1', 'nomen_med_drugs'), 
            ('nomen_manda_2', 'nomen_med_drugs_infusions'), ('nomen_manda_3', 'nomen_med_drugs_infusions_dex')]

        for field, xml_id in toget:
            nom = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_nomenclature', xml_id)
            res[field] = nom[1]
        return res

    def create(self, cr, uid, vals, context={}):
        '''
        Set default values for datas.xml and tests.yml
        '''

        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            required = ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3']
            has_required = False
            for req in required:
                if  req in vals:
                    has_required = True
                    break
            if not has_required:
                logging.getLogger('init').info('Loading default values for product.template')
                vals.update(self._get_default_nom(cr, uid, context))
        return super(product_template, self).create(cr, uid, vals, context)

    _defaults = {
    }

product_template()

class product_product(osv.osv):
    
    _inherit = "product.product"
    _description = "Product"
    
    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field)
    
    def get_sub_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_sub_nomen(cr, uid, self, id, field)

    def create(self, cr, uid, vals, context=None):
        '''
        override to complete nomenclature_description
        '''
        sale = self.pool.get('sale.order.line')
        sale._setNomenclatureInfo(cr, uid, vals, context)
        
        return super(product_product, self).create(cr, uid, vals, context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        override to complete nomenclature_description
        '''
        sale = self.pool.get('sale.order.line')
        sale._setNomenclatureInfo(cr, uid, vals, context)
        
        return super(product_product, self).write(cr, uid, ids, vals, context)
    
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        '''
        the nomenclature selection search changes
        '''
        if context is None:
            context = {}

        mandaName = 'nomen_manda_%s'
        optName = 'nomen_sub_%s'
        # selected value
        selected = eval('nomen_manda_%s'%position)
        # if selected value is False, the first False value -1 is used as selected
        if not selected:
            mandaVals = [i for i in range(_LEVELS) if not eval('nomen_manda_%s'%i)]
            if mandaVals[0] == 0:
                # first drop down, initialization 
                selected = False
                position = -1
            else:
                # the first drop down with False value -1
                position = mandaVals[0]-1
                selected = eval('nomen_manda_%s'%position)
        
        values = {}
        result = {'value': values}
        
        # clear upper levels mandatory
        for i in range(position+1, _LEVELS):
            values[mandaName%(i)] = [()]
            
        # clear all optional level
        for i in range(_SUB_LEVELS):
            values[optName%(i)] = [()]
        
        # nomenclature object
        nomenObj = self.pool.get('product.nomenclature')
        # product object
        prodObj = self.pool.get('product.product')
        
        # loop through children nomenclature of mandatory type
        shownum = num or context.get('withnum') == 1
        if position < 3:
            nomenids = nomenObj.search(cr, uid, [('type', '=', 'mandatory'), ('parent_id', '=', selected)], order='name', context=context)
            if nomenids:
                for n in nomenObj.read(cr, uid, nomenids, ['name'] + (shownum and ['number_of_products'] or []), context=context):
                    # get the name and product number
                    id = n['id']
                    name = n['name']
                    if shownum:
                        number = n['number_of_products']
                        values[mandaName%(position+1)].append((id, name + ' (%s)'%number))
                    else:
                        values[mandaName%(position+1)].append((id, name))
        
        # find the list of optional nomenclature related to products filtered by mandatory nomenclatures
        optionalList = []
        if not selected:
            optionalList.extend(nomenObj.search(cr, uid, [('type', '=', 'optional'), ('parent_id', '=', False)], order='name', context=context))
        else:
            optionalList = nomenObj.search(cr, uid, [('type', '=', 'optional'), ('parent_id', 'in', [nomen_manda_0,nomen_manda_1,nomen_manda_2,nomen_manda_3,False])])
#            pids = prodObj.search(cr, uid, [(mandaName%position, '=', selected)], context=context)
#            if pids:
#                for p in prodObj.read(cr, uid, pids, ['nomen_sub_%s'%x for x in range(_SUB_LEVELS)], context=context):
#                    optionalList.extend([eval("p['nomen_sub_%s'][0]"%x, {'p':p}) for x in range(_SUB_LEVELS) if eval("p['nomen_sub_%s']"%x, {'p':p}) and eval("p['nomen_sub_%s'][0]"%x, {'p':p}) not in optionalList])
            
        # sort the optional nomenclature according to their id
        optionalList.sort()
        if optionalList:
            for n in nomenObj.read(cr, uid, optionalList, ['name', 'sub_level'] + (num and ['number_of_products'] or []), context=context):
                # get the name and product number
                id = n['id']
                name = n['name']
                sublevel = n['sub_level']
                if num:
                    number = n['number_of_products']
                    values[optName%(sublevel)].append((id, name + ' (%s)'%number))
                else:
                    values[optName%(sublevel)].append((id, name))
        if num:
            newval = {}
            for x in values:
                newval['%s_s'%x] = values[x]
            result['value'] = newval
        return result
    
    def _resetNomenclatureFields(self, values):
        '''
        reset all nomenclature's fields
        because the dynamic domain for product_id is not
        re-computed at windows opening.
        '''
        for x in range(_LEVELS):
            values.update({'nomen_manda_%s'%x:False})
            
        for x in range(_SUB_LEVELS):
            values.update({'nomen_sub_%s'%x:False})
    
    def _generateValueDic(self, cr, uid, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, *optionalList):
        '''
        generate original dictionary
        all values are placed in the update dictionary
        to ease the generation of dynamic domain in order_nomenclature
        '''
        result = {}
        
        # mandatory levels values
        for i in range(_LEVELS):
            name = 'nomen_manda_%i'%(i)
            value = eval(name)
            
            result.update({name:value})
            
        # optional levels values
        for i in range(_SUB_LEVELS):
            name = 'nomen_sub_%i'%(i)
            value = optionalList[i]
            
            result.update({name:value})
        
        return result
    
    def _clearFieldsBelow(self, cr, uid, level, optionalList, result):
        '''
        Clear fields below (hierarchically)
        
        possible improvement:
        
        '''
        levels = range(_LEVELS)
        
        # level not of interest
        if level not in levels:
            raise osv.except_osv(_('Error'), _('Level (%s) must be smaller or equal to %s'%(level, levels)))
        
        
        for x in levels[level+1:]:
            result['value'].update({'nomen_manda_%s'%x:False})

        # always update all sub levels
        for x in range(_SUB_LEVELS):
            # clear optional fields with level below 'level'
            subId = optionalList[x]
            if subId:
                subNomenclature = self.pool.get('product.nomenclature').browse(cr, uid, subId)
                subNomenclatureLevel = subNomenclature.level
                if subNomenclatureLevel > level:
                    result['value'].update({'nomen_sub_%s'%x:False})
            
        return result
    
    def nomenChange(self, cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                    nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        for mandatory types, level (nomenclature object)
        and fieldNumber (field) are directly linked
        
        for optional types, the fields can contain nomenclature
        of any level, they are not directly linked. in this case,
        we make a clear distinction between fieldNumber and level
        
        when a nomenclature field changes:
        1. if the nomenclature is of newType "mandatory", we reset
           below levels and codes.
        2. we update the corresponding newCode (whatever the newType)
        
        possible improvement:
        - if a selected level contains only one sub level, update
          the sub level with that unique solution
        '''
        assert context, 'No context, error on function call'
        # values to be updated
        result = {}
        if 'result' in context:
            result = context['result']
        else:
            result = {'value':{}, 'warning':{}}
            context['result'] = result
        
        # all values are updated, ease dynamic domain generation in order_nomenclature
        allValues = self._generateValueDic(cr, uid, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, *optionalList)
        result['value'].update(allValues)
        
        # retrieve selected nomenclature object
        if nomenclatureId:
            selectedNomenclature = self.pool.get('product.nomenclature').browse(cr, uid, nomenclatureId)
            newId = nomenclatureId
            newType = selectedNomenclature.type
            newLevel = selectedNomenclature.level
            # converted to int, because string from selection
            newSubLevel = int(selectedNomenclature.sub_level)
            # newType check
            if nomenclatureType != newType:
                result['warning'].update({'title': _('Error!'),
                                          'message': _("The selected nomenclature's type is '%s'. Must be '%s' (field's type)."%(newType,nomenclatureType)),
                                          })
                newId = False
                newType = nomenclatureType
                
                
            # level check
            if  newType == 'mandatory':
                if fieldNumber != newLevel:
                    result['warning'].update({'title': _('Error!'),
                                          'message': _("The selected nomenclature's level is '%s'. Must be '%s' (field's level)."%(newLevel,fieldNumber)),
                                          })
                    newId = False
                    
            elif newType == 'optional':
                if fieldNumber != newSubLevel:
                    ### NOTE adapt level to user level for warning message (+1)
                    result['warning'].update({'title': _('Error!'),
                                          'message': _("The selected nomenclature's level is '%s'. Must be '%s' (field's level)."%(newSubLevel+1,fieldNumber+1)),
                                          })
                    newId = False
                    
        else:
            # the field has been cleared, we simply want to clear the code field as well
            newId = False
            newType = nomenclatureType
            
        
        if newType == 'mandatory':
            # clear all below (from fieldNumber+1) mandatory levels
            # all optional
            self._clearFieldsBelow(cr, uid, level=fieldNumber, optionalList=optionalList, result=result)

            # update selected level
            result['value'].update({'nomen_manda_%s'%fieldNumber:newId})
            
        if newType == 'optional':
            
            # update selected level
            result['value'].update({'nomen_sub_%s'%fieldNumber:newId})
            
        result = context['result']
        
        # correction of bug when we select the nomenclature with a mouse click
        # the nomenclature was reset to False
        # this is due to the fact that onchange is called twice when we use the mouse click
        # the first time with the selected value to False. This value was set to False
        # at the first call which reset the selected value.
        #
        # in product_nomenclature > product_nomenclature.py > product_product > nomenChange
        #
        if not nomenclatureId:
            # we remove the concerned field if it is equal to False
            if nomenclatureType == 'mandatory':
                nameToRemove = 'nomen_manda_%i'%fieldNumber
                result['value'].pop(nameToRemove, False)
                
            elif nomenclatureType == 'optional':
                nameToRemove = 'nomen_sub_%i'%fieldNumber
                result['value'].pop(nameToRemove, False)
    
        return result
        
product_product()


class act_window(osv.osv):
    _name = 'ir.actions.act_window'
    '''
    inherit act_window to extend domain size, as the size for screen sales>product by nomenclature is longer than 250 character
    '''
    _inherit = 'ir.actions.act_window'
    _columns = {
        'domain': fields.char('Domain Value', size=1024,
            help="Optional domain filtering of the destination data, as a Python expression"),
    }

act_window()
