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
        'functional_id': fields.many2one('res.currency', string='Functional currency', domain=[('active', 'in', ('t', 'f'))]),
        'esc_ids': fields.many2many('res.currency', 'esc_currency_rel', 'wiz_id', 'currency_id',
                                    string='ESC Currencies', domain=[('active', 'in', ('t', 'f'))],
                                    help="Currencies used by the ESC"),
        'section_ids': fields.many2many('res.currency', 'section_currency_rel', 'wiz_id', 'currency_id',
                                    string='Section Currencies', domain=[('active', 'in', ('t', 'f'))],
                                    help="Currencies used by the Sections"),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for delivery process
        '''
        currency_obj = self.pool.get('res.currency')
        
        res = super(currency_setup, self).default_get(cr, uid, fields, context=context)
        
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        esc_ids = currency_obj.search(cr, uid, [('is_esc_currency', '=', True)], context=context)
        section_ids = currency_obj.search(cr, uid, [('is_section_currency', '=', True)], context=context)
        
        res['functional_id'] = company_id.currency_id.id
        res['esc_ids'] = [(6, 0, esc_ids)]
        res['section_ids'] = [(6, 0, section_ids)] 
        
        return res
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        currency_obj = self.pool.get('res.currency')
        
        if payload.functional_id:
            company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
            self.pool.get('res.company').write(cr, uid, [company_id], {'currency_id': payload.functional_id.id}, context=context)
            
        esc_ids = currency_obj.search(cr, uid, [('is_esc_currency', '=', True)], context=context)
        section_ids = currency_obj.search(cr, uid, [('is_section_currency', '=', True)], context=context)
        
        # Remove the flag on all currencies
        currency_obj.write(cr, uid, esc_ids, {'is_esc_currency': False}, context=context)
        currency_obj.write(cr, uid, section_ids, {'is_section_currency': False}, context=context)
        
        new_esc_ids = []
        new_section_ids = []
        
        for esc in payload.esc_ids:
            new_esc_ids.append(esc.id)
            
        for section in payload.section_ids:
            new_section_ids.append(section.id)
        
        currency_obj.write(cr, uid, new_esc_ids, {'is_esc_currency': True}, context=context)
        currency_obj.write(cr, uid, new_section_ids, {'is_section_currency': True}, context=context)
        
currency_setup()