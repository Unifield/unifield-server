#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
from osv import fields

class wizard_down_payment(osv.osv_memory):
    _name = 'wizard.down.payment'
    _description = 'Down payment'

    _columns = {
        'register_line_id': fields.many2one('account.bank.statement.line', string="Register line", readonly=True, required=True),
        'purchase_id': fields.many2one('purchase.order', string="Purchase Order", readonly=True, required=False, 
            states={'draft': [('readonly', False), ('required', True)]}),
        'state': fields.selection([('draft', 'Draft'), ('closed', 'Closed')], string="State", required=True),
        'currency_id': fields.many2one('res.currency', string="Register line currency", required=True, readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'closed',
    }

    def button_validate(self, cr, uid, ids, context={}):
        """
        Validate the wizard to remember which PO have been selected from this register line.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all wizards
        for wiz in self.browse(cr, uid, ids, context=context):
            self.pool.get('account.bank.statement.line').write(cr, uid, [wiz.register_line_id.id], {'down_payment_id': wiz.purchase_id.id}, context=context)
        return {'type' : 'ir.actions.act_window_close'}

wizard_down_payment()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
