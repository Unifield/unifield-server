#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
from tools.translate import _

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _description = 'Account invoice'

    _inherit = 'account.invoice'

    _columns = {
        'purchase_ids': fields.many2many('purchase.order', 'purchase_invoice_rel', 'invoice_id', 'purchase_id', 'Purchases', 
            help="Purchases that generate these invoices."),
    }

    def button_split_invoice(self, cr, uid, ids, context={}):
        """
        Launch the split invoice wizard to split an invoice in two elements.
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some value
        wiz_lines_obj = self.pool.get('wizard.split.invoice.lines')
        inv_lines_obj = self.pool.get('account.invoice.line')
        # Creating wizard
        wizard_id = self.pool.get('wizard.split.invoice').create(cr, uid, {'invoice_id': ids[0]}, context=context)
        # Add invoices_lines into the wizard
        invoice_line_ids = self.pool.get('account.invoice.line').search(cr, uid, [('invoice_id', '=', ids[0])], context=context)
        # Some other verifications
        if not len(invoice_line_ids):
            raise osv.except_osv(_('Error'), _('No invoice line in this invoice or not enough elements'))
        for invl in inv_lines_obj.browse(cr, uid, invoice_line_ids, context=context):
            wiz_lines_obj.create(cr, uid, {'invoice_line_id': invl.id, 'product_id': invl.product_id.id, 'quantity': invl.quantity, 
                'price_unit': invl.price_unit, 'description': invl.name, 'wizard_id': wizard_id}, context=context)
        # Return wizard
        if wizard_id:
            return {
                'name': "Split Invoice",
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.split.invoice',
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': [wizard_id],
                'context':
                {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'wizard_id': wizard_id,
                }
            }
        return False

account_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
