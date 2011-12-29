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

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    _columns = {
        'intl_customer_ok': fields.boolean(string='International customer'),
    }

    def onchange_partner_id(self, cr, uid, ids, partner_id, *a, **b):
        '''
        Set the intl_customer_ok field if the partner is an ESC or an international partner
        '''
        res = super(sale_order, self).onchange_partner_id(cr, uid, ids, partner_id, *a, **b)

        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if partner.partner_type == 'esc' or partner.zone == 'international':
                res['value'].update({'intl_customer_ok': True})
            else:
                res['value'].update({'intl_customer_ok': False})
        else:
            res['value'].update({'intl_customer_ok': True})

        return res


sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
