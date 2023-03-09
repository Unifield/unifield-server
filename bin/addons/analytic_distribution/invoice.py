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

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the Purchase order contains a line with an inactive products
        '''
        if self._name and self._name == 'wizard.account.invoice':
            invoice_line = self.pool.get('wizard.account.invoice.line')
        else:
            invoice_line = self.pool.get('account.invoice.line')

        inactive_lines = invoice_line.search(cr, uid, [
            ('product_id.active', '=', False),
            ('invoice_id', 'in', ids),
            ('invoice_id.state', 'not in', ['draft', 'cancel', 'done'])
        ], context=context)

        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')
            p_plural = len(inactive_lines) == 1 and _('this inactive product') or _('those inactive products')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the %s containing %s (see red %s of the document)') % (plural, l_plural, p_plural, l_plural))
            return False
        return True

    _constraints = [
        (_check_active_product, "You cannot validate this invoice because it contains a line with an inactive product", ['invoice_line', 'state'])
    ]

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution', select="1"), # select: optimisation purpose
    }

    def _check_analytic_distribution_state(self, cr, uid, ids, context=None):
        """
        Check if analytic distribution is valid
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for inv in self.browse(cr, uid, ids, context=context):
            for invl in inv.invoice_line:
                if invl.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Error'), _('Analytic distribution is not valid for "%s"') % invl.name)
        return True

    def button_analytic_distribution(self, cr, uid, ids, context=None):
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
            # Since US-9996, for the total_amount in global AD wizard, only take into account only amounts from lines
            # with analytic-addicted accounts that require an AD
            if line.account_id.is_analytic_addicted:
                amount += line.price_subtotal
        # Get analytic_distribution_id
        distrib_id = invoice.analytic_distribution_id and invoice.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'invoice_id': invoice.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'posting_date': invoice.date_invoice,
            'document_date': invoice.document_date,
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
            'name': _('Global analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def button_reset_distribution(self, cr, uid, ids, context=None):
        """
        Reset analytic distribution on all invoice lines.
        To do this, just delete the analytic_distribution id link on each invoice line.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        invl_obj = self.pool.get(self._name + '.line') # PAY ATTENTION to wizard.account.invoice.line
        # Search invoice lines
        to_reset = invl_obj.search(cr, uid, [('invoice_id', 'in', ids)])
        invl_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False})
        return True

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the invoice line, then "valid"
         - if no distribution, take a tour of invoice distribution, if compatible, then "valid"
         - if no distribution on invoice line and invoice, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            # UF-2115: test for elements
            line_distribution_id = False
            invoice_distribution_id = False
            line_account_id = False
            if line.analytic_distribution_id:
                line_distribution_id = line.analytic_distribution_id.id
            if line.invoice_id and line.invoice_id.analytic_distribution_id:
                invoice_distribution_id = line.invoice_id.analytic_distribution_id.id
            if line.account_id:
                line_account_id = line.account_id.id
            res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line_distribution_id,
                                                                                          invoice_distribution_id, line_account_id,
                                                                                          amount=line.price_subtotal or 0.0)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If invoice have an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = True
            if inv.analytic_distribution_id:
                res[inv.id] = False
        return res

    def _get_is_allocatable(self, cr, uid, ids, name, arg, context=None):
        """
        If analytic-a-holic account, then this account is allocatable.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for invl in self.browse(cr, uid, ids):
            res[invl.id] = True
            if invl.account_id and not invl.account_id.is_analytic_addicted:
                res[invl.id] = False
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Get a recap from analytic distribution state and if it come from header or not.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for invl in self.browse(cr, uid, ids):
            res[invl.id] = ''
            if not invl.is_allocatable or (invl.allow_no_account and not invl.account_id):
                continue
            from_header = ''
            if invl.have_analytic_distribution_from_header:
                from_header = _(' (from header)')
            res[invl.id] = '%s%s' % (self.pool.get('ir.model.fields').get_browse_selection(cr, uid, invl, 'analytic_distribution_state', context), from_header)
        return res

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.invoice_id and line.invoice_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {
                    'inactive_product': True,
                    'inactive_error': _('The product in line is inactive !')
                }
        return res

    def _get_analytic_lines(self, cr, uid, ids, field_name, arg, context=None):
        """
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        for invl in self.browse(cr, uid, ids):
            res[invl.id] = []
            for ml in (invl.move_lines or []):
                if ml.analytic_lines:
                    res[invl.id] = self.pool.get('account.analytic.line').get_corrections_history(cr, uid, [x.id for x in ml.analytic_lines])
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution', select="1"), # select is for optimisation purposes
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
                                                       selection=[('none', 'None'), ('valid', 'Valid'),
                                                                  ('invalid', 'Invalid'), ('invalid_small_amount', 'Invalid')],
                                                       string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean',
                                                                  string='Header Distrib.?'),
        'newline': fields.boolean('New line'),
        'is_allocatable': fields.function(_get_is_allocatable, method=True, type='boolean', string="Is allocatable?", readonly=True, store=False),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, type='char', size=30,
                                                             string="Distribution",
                                                             help="Informs you about analaytic distribution state among 'none', 'valid', 'invalid', from header or not, or no analytic distribution"),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Comment', store=False, multi='inactive'),
        'analytic_lines': fields.function(_get_analytic_lines, method=True, type='one2many', relation='account.analytic.line', store=False, string='Analytic lines', help='Give all analytic lines linked to this invoice line. With correction ones.'),
    }

    _defaults = {
        'newline': lambda *a: True,
        'have_analytic_distribution_from_header': lambda *a: True,
        'is_allocatable': lambda *a: True,
        'analytic_distribution_state_recap': lambda *a: '',
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def create(self, cr, uid, vals, context=None):
        """
        Set newline field to False.
        """
        vals.update({'newline': False,})
        return super(account_invoice_line, self).create(cr, uid, vals, context)

    def copy_data(self, cr, uid, l_id, default=None, context=None):
        """
        Copy global distribution and give it to new invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Copy analytic distribution
        invl = self.browse(cr, uid, [l_id], context=context)[0]
        if invl.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, invl.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(account_invoice_line, self).copy_data(cr, uid, l_id, default, context)

    def button_analytic_distribution(self, cr, uid, ids, context=None):
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
            'posting_date': invoice_line.invoice_id.date_invoice,
            'document_date': invoice_line.invoice_id.document_date,
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
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
