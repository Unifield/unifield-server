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
        'second_time': fields.boolean('Config. Wizard launched for the second time'),
        'partner_name': fields.char(size=64, string='Partner name'),
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

    def default_get(self, cr, uid, fields, context=None):
        '''
        Get the current address of the main partner and fill the form
        '''
        res = super(project_addresses, self).default_get(cr, uid, fields, context=context)

        if not 'company_id' in res:
            return res
        company = self.pool.get('res.company').browse(cr, uid, res['company_id'], context=context)
        company_id = company.partner_id.id
        addresses = self.pool.get('res.partner').address_get(cr, uid, company_id, ['invoice', 'delivery', 'default'])
        default_id = addresses.get('default', False)
        delivery_id = addresses.get('delivery', False) != default_id and addresses.get('delivery', False)
        bill_id = addresses.get('invoice', False) != default_id and addresses.get('invoice', False)

        res['partner_name'] = company.instance_id.instance
        res['name'] = company.instance_id.instance
        res['second_time'] = True

        if default_id:
            address = self.pool.get('res.partner.address').browse(cr, uid, default_id, context=context)
            for field in ['street','street2','zip','city','email','phone']:
                res[field] = address[field]
            for field in ['country_id','state_id']:
                if address[field]:
                    res[field] = address[field].id
            if address.name:
                res['contact_name'] = address['name']

        if delivery_id:
            address = self.pool.get('res.partner.address').browse(cr, uid, delivery_id, context=context)
            for field in ['street','street2','zip','city','email','phone']:
                res['ship_%s' % field] = address[field]
            for field in ['country_id','state_id']:
                if address[field]:
                    res['ship_%s' % field] = address[field].id

        if bill_id:
            address = self.pool.get('res.partner.address').browse(cr, uid, bill_id, context=context)
            for field in ['street','street2','zip','city','email','phone']:
                res['bill_%s' % field] = address[field]
            for field in ['country_id','state_id']:
                if address[field]:
                    res['bill_%s' % field] = address[field].id

        return res

    def execute(self, cr, uid, ids, context=None):
        '''
        Create project's addresses
        '''
        if not context:
            context = {}

        res = super(project_addresses, self).execute(cr, 1, ids, context=context)

        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        if not getattr(payload, 'company_id', None):
            raise ValueError('Case where no default main company is setup '
                             'not handled yet')

        # TODO: quick fix
        self.pool.get('res.users').write(cr, uid, [uid], {'view': 'extended'}, context=context)

        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        address_obj = self.pool.get('res.partner.address')

        if payload.ship_street or payload.ship_street2 or payload.ship_zip or payload.ship_city \
           or payload.ship_email or payload.ship_phone or payload.ship_country_id:
            ship_address_data = {
                'type': 'delivery',
                'name':company.instance_id.instance,
                'street':payload.ship_street,
                'street2':payload.ship_street2,
                'zip':payload.ship_zip,
                'city':payload.ship_city,
                'email':payload.ship_email,
                'phone':payload.ship_phone,
                'country_id':int(payload.ship_country_id),
                'state_id':int(payload.ship_state_id),
            }

            ship_address = address_obj.search(cr, uid, [('type', '=', 'delivery'), ('partner_id', '=', company.partner_id.id)], context=context)
            if ship_address:
                address_obj.write(cr, uid, ship_address[0], ship_address_data, context=context)
            else:
                address_obj.create(cr, uid, dict(ship_address_data, partner_id=int(company.partner_id)),
                                   context=context)
        else:
            ship_address = address_obj.search(cr, uid, [('type', '=', 'delivery'), ('partner_id', '=', company.partner_id.id)], context=context)
            if ship_address:
                address_obj.unlink(cr, uid, ship_address[0], context=context)

        if payload.bill_street or payload.bill_street2 or payload.bill_zip or payload.bill_city \
           or payload.bill_email or payload.bill_phone or payload.bill_country_id:    
            bill_address_data = {
                'type': 'invoice',
                'name':company.instance_id.instance,
                'street':payload.bill_street,
                'street2':payload.bill_street2,
                'zip':payload.bill_zip,
                'city':payload.bill_city,
                'email':payload.bill_email,
                'phone':payload.bill_phone,
                'country_id':int(payload.bill_country_id),
                'state_id':int(payload.bill_state_id),
            }

            bill_address = address_obj.search(cr, uid, [('type', '=', 'invoice'), ('partner_id', '=', company.partner_id.id)], context=context)
            if bill_address:
                address_obj.write(cr, uid, bill_address[0], bill_address_data, context=context)
            else:
                address_obj.create(cr, uid, dict(bill_address_data, partner_id=int(company.partner_id)),
                                   context=context)
        else:
            bill_address = address_obj.search(cr, uid, [('type', '=', 'invoice'), ('partner_id', '=', company.partner_id.id)], context=context)
            if bill_address:
                address_obj.unlink(cr, uid, bill_address[0], context=context)

        if company.instance_id:
            self.pool.get('res.company').write(cr, 1, [company.id], {'name': company.instance_id.instance}, context=context)

            c = context.copy()
            c.update({'from_config': True})
            self.pool.get('res.partner').write(cr, uid, [company.partner_id.id], {'name': company.instance_id.instance,
                                                                                  'partner_type': 'internal'}, context=c)

        data_obj = self.pool.get('ir.model.data')
        warehouse_obj = self.pool.get('stock.warehouse')
        user_obj = self.pool.get('res.users')

        instance_name = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.name

        # Rename the warehouse with the name of the company
        warehouse_id = data_obj.get_object_reference(cr, uid, 'stock', 'warehouse0')[1]
        warehouse_obj.write(cr, uid, [warehouse_id], {'name': 'MSF %s' % instance_name}, context=context)

        return res

project_addresses()
