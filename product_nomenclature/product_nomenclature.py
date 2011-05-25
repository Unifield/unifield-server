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
        logging.getLogger('init').info('HOOK: module product_nomenclature: loading product_nomenclature_data.xml')
        pathname = path.join('product_nomenclature', 'product_nomenclature_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'product_nomenclature', file, {}, mode='init', noupdate=False)

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
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

    _name = "product.nomenclature"
    _description = "Product Nomenclature"
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Name'),
        'code': fields.char('Code', size=64, required=True),
        # technic fields - tree management
        'parent_id': fields.many2one('product.nomenclature','Parent Nomenclature', select=True),
        # TODO try to display child_ids on screen. which result ?
        'child_id': fields.one2many('product.nomenclature', 'parent_id', string='Child Nomenclatures'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of product nomenclatures."),
        'level': fields.integer('Level', size=256),
        'type': fields.selection([('mandatory','Mandatory'), ('optional','Optional')], 'Nomenclature Type'),
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

product_nomenclature()

#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):
    
    _inherit = "product.template"
    _description = "Product Template"

    ### EXACT COPY-PASTE TO order_nomenclature
    _columns = {
                # mandatory nomenclature levels
                'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', required=True),
                'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', required=True),
                'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', required=True),
                'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', required=True),
                # codes
                'nomen_c_manda_0': fields.char('C1', size=32),
                'nomen_c_manda_1': fields.char('C2', size=32),
                'nomen_c_manda_2': fields.char('C3', size=32),
                'nomen_c_manda_3': fields.char('C4', size=32),
                # optional nomenclature levels
                'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
                'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
                'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
                'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
                'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
                'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),
                # codes
                'nomen_c_sub_0': fields.char('C5', size=128),
                'nomen_c_sub_1': fields.char('C6', size=128),
                'nomen_c_sub_2': fields.char('C7', size=128),
                'nomen_c_sub_3': fields.char('C8', size=128),
                'nomen_c_sub_4': fields.char('C9', size=128),
                'nomen_c_sub_5': fields.char('C10', size=128),
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
    
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None):
        '''
        the nomenclature selection search changes
        '''
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
        for id in nomenObj.search(cr, uid, [('type', '=', 'mandatory'), ('parent_id', '=', selected)], order='name', context=context):
            # get the name and product number
            n = nomenObj.browse(cr, uid, id, context=context)
            code = n.code
            name = n.name
            number = n.number_of_products
            values[mandaName%(position+1)].append((id, name + ' (%s)'%number))
        
        # find the list of optional nomenclature related to products filtered by mandatory nomenclatures
        optionalList = []
        if not selected:
            optionalList.extend(nomenObj.search(cr, uid, [('type', '=', 'optional'), ('parent_id', '=', False)], order='code', context=context))
        else:
            for id in prodObj.search(cr, uid, [(mandaName%position, '=', selected)], context=context):
                p = prodObj.browse(cr, uid, id, context)
                optionalList.extend([eval('p.nomen_sub_%s.id'%x, {'p':p}) for x in range(_SUB_LEVELS) if eval('p.nomen_sub_%s.id'%x, {'p':p}) and eval('p.nomen_sub_%s.id'%x, {'p':p}) not in optionalList])
        
        # sort the optional nomenclature according to their id
        optionalList.sort()
        for id in optionalList:
            # get the name and product number
            n = nomenObj.browse(cr, uid, id, context=context)
            code = n.code
            name = n.name
            number = n.number_of_products
            values[optName%(n.sub_level)].append((id, name + ' (%s)'%number))

        return result
    
    def _resetNomenclatureFields(self, values):
        '''
        reset all nomenclature's fields
        because the dynamic domain for product_id is not
        re-computed at windows opening.
        '''
        for x in range(_LEVELS):
            values.update({'nomen_manda_%s'%x:False})
            values.update({'nomen_c_manda_%s'%x:False})
            
        for x in range(_SUB_LEVELS):
            values.update({'nomen_sub_%s'%x:False})
            values.update({'nomen_c_sub_%s'%x:False})
    
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
            result['value'].update({'nomen_c_manda_%s'%x:False})
        # always update all sub levels
        for x in range(_SUB_LEVELS):
            # clear optional fields with level below 'level'
            subId = optionalList[x]
            if subId:
                subNomenclature = self.pool.get('product.nomenclature').browse(cr, uid, subId)
                subNomenclatureLevel = subNomenclature.level
                if subNomenclatureLevel > level:
                    result['value'].update({'nomen_sub_%s'%x:False})
                    result['value'].update({'nomen_c_sub_%s'%x:False})
            
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
            newCode = selectedNomenclature.code
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
                newCode = False
                newType = nomenclatureType
                
                
            # level check
            if  newType == 'mandatory':
                if fieldNumber != newLevel:
                    result['warning'].update({'title': _('Error!'),
                                          'message': _("The selected nomenclature's level is '%s'. Must be '%s' (field's level)."%(newLevel,fieldNumber)),
                                          })
                    newId = False
                    newCode = False
                    
            elif newType == 'optional':
                if fieldNumber != newSubLevel:
                    ### NOTE adapt level to user level for warning message (+1)
                    result['warning'].update({'title': _('Error!'),
                                          'message': _("The selected nomenclature's level is '%s'. Must be '%s' (field's level)."%(newSubLevel+1,fieldNumber+1)),
                                          })
                    newId = False
                    newCode = False
                    
        else:
            # the field has been cleared, we simply want to clear the code field as well
            newId = False
            newCode = False
            newType = nomenclatureType
            
        
        if newType == 'mandatory':
            # clear all below (from fieldNumber+1) mandatory levels
            # all optional
            self._clearFieldsBelow(cr, uid, level=fieldNumber, optionalList=optionalList, result=result)

            # update selected level
            result['value'].update({'nomen_manda_%s'%fieldNumber:newId})
            result['value'].update({'nomen_c_manda_%s'%fieldNumber:newCode})
            
        if newType == 'optional':
            
            # update selected level
            result['value'].update({'nomen_sub_%s'%fieldNumber:newId})
            result['value'].update({'nomen_c_sub_%s'%fieldNumber:newCode})
            
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

    def codeChange(self, cr, uid, id, fieldNumber, code, nomenclatureType,
            nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        the code changes
        - select the corresponding nomenclature and update the field
        - clear below fields
        
        if the selected code does not exist, nomenclature and code are set to False
        
        possible improvement:
        - context management with context= in xml view. maybe some fields in context.
          breakpoint in osv line 167 for test
        
        '''
        assert context, 'No context, error on function call'
        
        result={}
        # values to be updated
        result.update({'value':{}, 'warning':{}})
        context['result']=result
        
        if code:
            # fetch nomenclatureIds of corresponding nomenclatures# mandatory : the parent_id must be equal to top level
            domainList = [('code', '=', code.upper())]
            if nomenclatureType == 'mandatory':
                # mandatory : the parent_id must be equal to top level id and type must be 'mandatory'
                domainList.append(('type', '=', 'mandatory'))
                
                if  fieldNumber != 0:
                    domainList.append(('parent_id', '=', eval('nomen_manda_%i'%(fieldNumber-1))))
                    
            elif nomenclatureType == 'optional':
                # optional : the parent_id must be in the mandatory fields and type must be 'optional'
                domainList.append(('type', '=', 'optional'))
                ### NOTE added False in order to have main optional levels available
                domainList.append(('parent_id', 'in', [nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False]))
                
            nomenclatureIds = self.pool.get('product.nomenclature').search(cr, uid, domainList)
            
            # check on nomenclatureIds length
            if len(nomenclatureIds) > 1:
                # too much nomenclatures
                newId = False
                result['warning'].update({'title': _('Error!'),
                                          'message': _("Received %s different nomenclatures : %s. Nomenclature codes must be unique."%(len(nomenclatureIds), nomenclatureIds)),
                                          })
            
            elif not nomenclatureIds:
                # no corresponding nomenclature
                newId = False
                result['warning'].update({'title': _('Error!'),
                                          'message': _("No nomenclature found with selected code (%s)."%(code)),
                                          })
            
            else:
                # found one nomenclature
                newId = nomenclatureIds[0]
            
        else:
            # the field has been cleared, we simply want to clear the code field as well, no warning messages
            newId = False
        
        # arguments unpacking for optionalList
        self.nomenChange(cr, uid, id, fieldNumber, newId, nomenclatureType,
                                nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)
        
        result = context['result']
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
