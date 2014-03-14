# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv


class purchase_order(osv.osv):
    """
    override for workflow modification
    """
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'customer_id': fields.many2one('res.partner', string='Customer', domain=[('customer', '=', True)]),
    }

    def create(self, cr, uid, vals, context=None):
        '''
        override for debugging purpose
        '''
        return super(purchase_order, self).create(cr, uid, vals, context)

    def _check_order_type_and_partner(self, cr, uid, ids, context=None):
        """
        Check order type and partner type compatibilities.
        """
        compats = {
            'regular':       ['internal', 'intermission', 'section', 'external', 'esc'],
            'donation_st':   ['internal', 'intermission', 'section'],
            'loan':          ['internal', 'intermission', 'section', 'external'],
            'donation_exp':  ['internal', 'intermission', 'section'],
            'in_kind':       ['external', 'esc'],
            'direct':        ['external', 'esc'],
            'purchase_list': ['external'],
        }
        # Browse PO
        for po in self.browse(cr, uid, ids):
            if po.order_type not in compats or po.partner_id.partner_type not in compats[po.order_type]:
                return False
        return True

    _constraints = [
        (
            _check_order_type_and_partner,
            "Partner type and order type are incompatible! Please change either order type or partner.",
            ['order_type', 'partner_id'],
        ),
    ]

purchase_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
