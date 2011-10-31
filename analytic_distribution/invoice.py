# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import osv, fields
from tools.translate import _

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        res = super(account_invoice, self).line_get_convert(cr, uid, x, part, date, context=context)
        res['analytic_distribution_id'] = x.get('analytic_distribution_id', False)
        return res

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard on an invoice
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        invoice = self.browse(cr, uid, ids[0], context=context)
        amount = 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = invoice.currency_id and invoice.currency_id.id or company_currency
        for line in invoice.invoice_line:
            amount += line.price_subtotal
        # Get analytic_distribution_id
        distrib_id = invoice.analytic_distribution_id and invoice.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'invoice_id': invoice.id,
            'currency_id': currency or False,
            'state': 'dispatch',
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
    }

    def button_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Launch analytic distribution wizard on an invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No invoice line given. Please save your invoice line before.'))
        # Prepare some values
        invoice_line = self.browse(cr, uid, ids[0], context=context)
        distrib_id = False
        negative_inv = False
        amount = invoice_line.price_subtotal or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = invoice_line.invoice_id.currency_id and invoice_line.invoice_id.currency_id.id or company_currency
        # Change amount sign if necessary
        if invoice_line.invoice_id.type in ['out_invoice', 'in_refund']:
            negative_inv = True
        if negative_inv:
            amount = -1 * amount
        # Get analytic distribution id from this line
        distrib_id = invoice_line and invoice_line.analytic_distribution_id and invoice_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'invoice_line_id': invoice_line.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': invoice_line.account_id and invoice_line.account_id.id or False,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'analytic.distribution.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [wiz_id],
                'context': context,
        }

    def move_line_get_item(self, cr, uid, line, context={}):
        """
        Give right analytic distribution when creating move lines
        """
        # Some verifications
        if not context:
            context = {}
        # Default result
        res = super(account_invoice_line, self).move_line_get_item(cr, uid, line, context=context)
        # Update result by copying analytic distribution from invoice line
        ana_obj = self.pool.get('analytic.distribution')
        if line.analytic_distribution_id:
            new_distrib_id = ana_obj.copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                res['analytic_distribution_id'] = new_distrib_id
        # If no distribution on invoice line, take those from invoice and copy it!
        elif line.invoice_id and line.invoice_id.analytic_distribution_id:
            new_distrib_id = ana_obj.copy(cr, uid, line.invoice_id.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                res['analytic_distribution_id'] = new_distrib_id
        return res

account_invoice_line()
