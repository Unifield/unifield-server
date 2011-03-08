#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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


import wizard
import pooler
import time

from osv import osv
from osv import fields


def _launch_wizard(self, cr, uid, data, context={}):
    """
    Open the Request for Quotation list of RfQ related to
    the procurement list
    """
    list_obj = pooler.get_pool(cr.dbname).get('procurement.list')
    l_ids = list_obj.browse(cr, uid, data ['ids'], context=context)
    rfq_ids = []

    for l in l_ids:
        rfq_ids.append(l.order_ids)

    return {
        'type': 'ir.actions.act_window',
        'res_model': 'purchase.order',
        'view_mode': 'tree,form',
        'view_type': 'form',
        'domain': [('id', 'in', rfq_ids), ('state', '=', 'draft')],
    }


class wizard_to_rfq(wizard.interface):

    states = {
        'init': {
            'actions': [],
            'result': {'type': 'action',
                       'action': _launch_wizard,
                       'state': 'end'}
        }
    }

wizard_to_rfq('procurement_list_to_rfq')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

