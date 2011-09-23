# -*- coding: utf-8 -*-
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

import logging
from os import path
import math
import re
import tools

class stock_reason_type(osv.osv):
    _name = 'stock.reason.type'
    _description = 'Reason Types Moves'
    
    def init(self, cr):
        """
        Load reason_type_data.xml brefore product
        """
        if hasattr(super(stock_reason_type, self), 'init'):
            super(stock_reason_type, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'reason_types_moves')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module reason_types_moves: loading reason_type_data.xml')
            pathname = path.join('reason_types_moves', 'reason_type_data.xml')
            file = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'reason_types_moves', file, {}, mode='init', noupdate=False)
    
    def return_level(self, cr, uid, type, level=0):
        if type.parent_id:
            level += 1
            self.return_level(cr, uid, type.parent_id, level)
        
        return level
    
    def _get_level(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Returns the level of the reason type
        '''
        res = {}
        
        for type in self.browse(cr, uid, ids, context=context):
            res[type.id] = self.return_level(cr, uid, type)
        
        return res
    
    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            name = record.name
            code = record.code
            if record.parent_id:
                name = record.parent_id.name + ' / ' + name
                code = str(record.parent_id.code) + '.' + str(code)
            res.append((record.id, '%s %s' % (code, name)))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'code': fields.integer(string='Code', required=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Name'),
        'parent_id': fields.many2one('stock.reason.type', string='Parent reason'),
        'level': fields.function(_get_level, method=True, type='integer', string='Level', readonly=True),
    }
    
stock_reason_type()


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
        
    def _get_default_reason(self, cr, uid, context={}):
        res = {}
        toget = [('reason_type_id', 'reason_type_external_supply')]

        for field, xml_id in toget:
            nom = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', xml_id)
            res[field] = nom[1]
        return res
    
    def create(self, cr, uid, vals, context={}):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            required = ['reason_type_id']
            has_required = False
            for req in required:
                if  req in vals:
                    has_required = True
                    break
            if not has_required:
                logging.getLogger('init').info('Loading default values for stock.picking')
                vals.update(self._get_default_reason(cr, uid, context))
        return super(stock_picking, self).create(cr, uid, vals, context)
    
    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True),
    }
    
stock_picking()


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'
    
    def hook__create_chained_picking(self, cr, uid, pick_values, picking):
        if not 'reason_type_id' in pick_values:
            pick_values.update({'reason_type_id': picking.reason_type_id.id})
            
        return pick_values
    
    def _get_default_reason(self, cr, uid, context={}):
        res = {}
        toget = [('reason_type_id', 'reason_type_external_supply')]

        for field, xml_id in toget:
            nom = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', xml_id)
            res[field] = nom[1]
        return res
    
    def create(self, cr, uid, vals, context={}):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            required = ['reason_type_id']
            has_required = False
            for req in required:
                if  req in vals:
                    has_required = True
                    break
            if not has_required:
                logging.getLogger('init').info('Loading default values for stock.picking')
                vals.update(self._get_default_reason(cr, uid, context))
        return super(stock_move, self).create(cr, uid, vals, context)
    
    _columns = {
        #'reason_type_id': fields.related('picking_id', 'reason_type_id', type='many2one', relation='stock.reason.type', readonly=True),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True),
    }
    
    _defaults = {
        'reason_type_id': lambda obj, cr, uid, context={}: context.get('reason_type_id', False) and context.get('reason_type_id') or False,
    }
    
stock_move()


class stock_return_picking(osv.osv_memory):
    _name = 'stock.return.picking'
    _inherit = 'stock.return.picking'

    def _hook_default_return_data(self, cr, uid, ids, context={}, 
                                  *args, **kwargs):
        '''
        Hook to allow user to modify the value for the stock move copy method
        '''
        default_value = super(stock_return_picking, self).\
                        _hook_default_return_data(cr, uid, ids, 
                                      context=context, 
                                      default_value=kwargs['default_value'])

        reason_type_id = self.pool.get('ir.model.data').\
                         get_object_reference(cr, uid, 'reason_types_moves', 
                                          'reason_type_return_from_unit')[1]

        default_value.update({'reason_type_id': reason_type_id})

        return default_value

stock_return_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
