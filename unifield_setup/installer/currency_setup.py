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

from osv import osv
from osv import fields

from tools.translate import _


class currency_setup(osv.osv_memory):
    _name = 'currency.setup'
    _inherit = 'res.config'
    
    _columns = {
        'functional_id': fields.selection([('eur', 'EUR'), ('chf', 'CHF')], string='Functional currency', 
                                         required=True),
        'esc_id': fields.many2one('res.currency', string="ESC Currency", readonly=True),
        'section_id': fields.selection([('eur', 'EUR'), ('chf', 'CHF')], string='Section currency', 
                                         readonly=True),
    }
    
    def functional_on_change(self, cr, uid, ids, currency_id, context=None):
        return {'value': {'section_id': currency_id}}
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for delivery process
        '''
        res = super(currency_setup, self).default_get(cr, uid, fields, context=context)
        
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        esc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'EUR')[1]
        
        if company_id.currency_id.id == esc_id:
            res['functional_id'] = 'eur'
        else:
            res['functional_id'] = 'chf' 
        res['esc_id'] = esc_id
        res['section_id'] = res['functional_id']
        
        return res
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        if payload.functional_id == 'eur':
            cur_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'EUR')[1]
        else:
            cur_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'CHF')[1]
            
        if not self.pool.get('res.currency').read(cr, uid, cur_id, ['active'], context=context)['active']:
            self.pool.get('res.currency').write(cr, uid, cur_id, {'active': True}, context=context)
        
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        self.pool.get('res.company').write(cr, uid, [company_id], {'currency_id': cur_id}, context=context)
        
currency_setup()