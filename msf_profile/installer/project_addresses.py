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


class project_addresses(osv.osv_memory):
    _name = 'base.setup.company'
    _inherit = 'base.setup.company'
    
    def _get_all_states(self, cr, uid, context=None):
        return super(project_addresses, self)._get_all_states(cr, uid, context=context)
    
    def _get_all_countries(self, cr, uid, context=None):
        return super(project_addresses, self)._get_all_countries(cr, uid, context=context)
    
    _columns = {
        'ship_street':fields.char('Street', size=128),
        'ship_street2':fields.char('Street 2', size=128),
        'ship_zip':fields.char('Zip Code', size=24),
        'ship_city':fields.char('City', size=128),
        'ship_state_id':fields.selection(_get_all_states, 'Fed. State'),
        'ship_country_id':fields.selection(_get_all_countries, 'Country'),
        'ship_email':fields.char('E-mail', size=64),
        'ship_phone':fields.char('Phone', size=64),
        'bill_street':fields.char('Street', size=128),
        'bill_street2':fields.char('Street 2', size=128),
        'bill_zip':fields.char('Zip Code', size=24),
        'bill_city':fields.char('City', size=128),
        'bill_state_id':fields.selection(_get_all_states, 'Fed. State'),
        'bill_country_id':fields.selection(_get_all_countries, 'Country'),
        'bill_email':fields.char('E-mail', size=64),
        'bill_phone':fields.char('Phone', size=64),
    }
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Create project's addresses
        '''
        res = super(project_addresses, self).execute(cr, uid, ids, context=context)
        
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        if not getattr(payload, 'company_id', None):
            raise ValueError('Case where no default main company is setup '
                             'not handled yet')
        company = payload.company_id
        partner_obj = self.pool.get('res.partner')
        address_obj = self.pool.ges('res.address')
        
        ship_address_data = {
            'name':payload.name,
            'street':payload.ship_street,
            'street2':payload.ship_street2,
            'zip':payload.ship_zip,
            'city':payload.ship_city,
            'email':payload.ship_email,
            'phone':payload.ship_phone,
            'country_id':int(payload.ship_country_id),
            'state_id':int(payload.ship_state_id),
        }

        ship_address = partner_obj.address_get(cr, uid, company.partner_id.id, ['delivery'])
        if ship_address:
            address_obj.write(cr, uid, ship_address[0], ship_address_data, context=context)
        else:
            address_obj.create(cr, uid, dict(ship_address_data, partner_id=int(company.partner_id)),
                    context=context)
            
        bill_address_data = {
            'name':payload.name,
            'street':payload.bill_street,
            'street2':payload.bill_street2,
            'zip':payload.bill_zip,
            'city':payload.bill_city,
            'email':payload.bill_email,
            'phone':payload.bill_phone,
            'country_id':int(payload.bill_country_id),
            'state_id':int(payload.bill_state_id),
        }

        bill_address = partner_obj.address_get(cr, uid, company.partner_id.id, ['invoice'])
        if bill_address:
            address_obj.write(cr, uid, bill_address[0], bill_address_data, context=context)
        else:
            address_obj.create(cr, uid, dict(bill_address_data, partner_id=int(company.partner_id)),
                    context=context)
            
        return res
    
project_addresses()