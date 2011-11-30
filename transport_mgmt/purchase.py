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


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'display_intl_transport_ok': fields.boolean(string='Displayed intl transport'),
        'intl_supplier_ok': fields.boolean(string='International Supplier'),
        'transport_mode': fields.selection([('regular_air', 'Air regular'), ('express_air', 'Air express'), 
                                            ('ffc_air', 'Air FFC'), ('sea', 'Sea'),
                                            ('road', 'Road'), ('hand', 'Hand carry'),], string='Transport mode'),
        'transport_cost': fields.float(digits=(16,2), string='Transport cost'),
        'transport_currency_id': fields.many2one('res.currency', string='Currency'),
    }

    _defaults = {
        'display_intl_transport_ok': lambda *a: False,
        'intl_supplier_ok': lambda *a: False,
    }

    def display_transport_line(self, cr, uid, ids, context={}):
        '''
        Set the visibility of the transport line to True
        '''
        for order in self.browse(cr, uid, ids, context=context):
            if order.display_intl_transport_ok:
                self.write(cr, uid, [order.id], {'display_intl_transport_ok': False}, context=context)
            else:
                self.write(cr, uid, [order.id], {'display_intl_transport_ok': True}, context=context)
        
        return True

    def onchange_partner_id(self, cr, uid, ids, partner_id):
        '''
        Display or not the line of international transport costs
        '''
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, partner_id)

        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if partner.partner_type == 'esc' or partner.zone == 'international':
                res['value'].update({'display_intl_transport_ok': True, 'intl_supplier_ok': True})
            else:
                res['value'].update({'display_intl_transport_ok': False, 'intl_supplier_ok': False})
        else:
            res['value'].update({'display_intl_transport_ok': False, 'intl_supplier_ok': False})

        return res


purchase_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
