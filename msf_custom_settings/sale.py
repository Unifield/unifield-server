#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
#    Developer: Olivier DOSSMANN
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

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def onchange_order_type(self, cr, uid, id, order_type=None, partner_id=None, context=None):
        """
        """
        res = {}
        if not order_type:
            return res
        domain = [('customer','=',True)]
        if order_type in ['regular', 'donation_st', 'loan']:
            res['domain'] = {'partner_id': [('partner_type', 'in', ['internal', 'intermission', 'section', 'external'])] + domain}
        elif order_type in ['donation_exp']:
            res['domain'] = {'partner_id': [('partner_type', 'in', ['internal', 'intermission', 'section'])] + domain}
        else:
            pass


        if partner_id and order_type:
            res.update({'value': {'order_policy': 'picking'}})
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if order_type != 'regular' or (order_type == 'regular' and partner.partner_type == 'internal'):
                res.update({'value': {'order_policy': 'manual'}})

        return res

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
