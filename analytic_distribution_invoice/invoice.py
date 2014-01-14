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

from osv import osv
from osv import fields
from tools.translate import _

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the Purchase order contains a line with an inactive products
        '''
        inactive_lines = self.pool.get('account.invoice.line').search(cr, uid, [
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
                if inv.from_yml_test or invl.from_yml_test:
                    continue
                if invl.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Error'), _('Analytic distribution is not valid for "%s"') % invl.name)
        return True

    def button_close_direct_invoice(self, cr, uid, ids, context=None):
        """
        Check analytic distribution before closing pop-up
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._check_analytic_distribution_state(cr, uid, ids, context)
        if context.get('from_register', False):
            return {'type': 'ir.actions.act_window_close'}
        return True

    def _hook_fields_for_refund(self, cr, uid, *args):
        """
        Add these fields to result:
         - analytic_distribution_id
        """
        res = super(account_invoice, self)._hook_fields_for_refund(cr, uid, args)
        res.append('analytic_distribution_id')
        res.append('document_date')
        return res

    def _hook_fields_m2o_for_refund(self, cr, uid, *args):
        """
        Add these fields to result:
         - analytic_distribution_id
        """
        res = super(account_invoice, self)._hook_fields_m2o_for_refund(cr, uid, args)
        res.append('analytic_distribution_id')
        return res

    def _hook_refund_data(self, cr, uid, data, *args):
        """
        Copy analytic distribution for refund invoice
        """
        if not data:
            return False
        if 'analytic_distribution_id' in data:
            if data.get('analytic_distribution_id', False):
                data['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, data.get('analytic_distribution_id'), {}) or False
            else:
                data['analytic_distribution_id'] = False
        return data

    def _refund_cleanup_lines(self, cr, uid, lines):
        """
        Add right analytic distribution values on each lines
        """
        res = super(account_invoice, self)._refund_cleanup_lines(cr, uid, lines)
        for el in res:
            if el[2]:
                # Give analytic distribution on line
                if 'analytic_distribution_id' in el[2]:
                    if el[2].get('analytic_distribution_id', False) and el[2].get('analytic_distribution_id')[0]:
                        distrib_id = el[2].get('analytic_distribution_id')[0]
                        el[2]['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, distrib_id, {}) or False
                    else:
                        # default value
                        el[2]['analytic_distribution_id'] = False
                # Give false analytic lines for 'line' in order not to give an error
                if 'analytic_line_ids' in el[2]:
                    el[2]['analytic_line_ids'] = False
                # Give false for (because not needed):
                # - order_line_id
                # - sale_order_line_id
                for field in ['order_line_id', 'sale_order_line_id']:
                    if field in el[2]:
                        el[2][field] = el[2].get(field, False) and el[2][field][0] or False
        return res

    def refund(self, cr, uid, ids, date=None, period_id=None, description=None, journal_id=None, document_date=None):
        """
        Reverse lines for given invoice
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        for inv in self.browse(cr, uid, ids):
            # Check for dates (refund must be done after invoice)
            if date and date < inv.date_invoice:
                raise osv.except_osv(_('Error'), _("Posting date for the refund is before the invoice's posting date!"))
            if document_date and document_date < inv.document_date:
                raise osv.except_osv(_('Error'), _("Document date for the refund is before the invoice's document date!"))
        new_ids = super(account_invoice, self).refund(cr, uid, ids, date, period_id, description, journal_id)
        # add document date
        if document_date:
            self.write(cr, uid, new_ids, {'document_date': document_date})
        return new_ids

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new invoice
        """
        if not context:
            context = {}
        if not default:
            default = {}
        inv = self.browse(cr, uid, [id], context=context)[0]
        if inv.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, inv.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(account_invoice, self).copy(cr, uid, id, default, context)

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Add verification on all lines for analytic_distribution_id to be present and valid !
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse invoice and all invoice lines to detect a non-valid line
        self._check_analytic_distribution_state(cr, uid, ids)
        return super(account_invoice, self).action_open_invoice(cr, uid, ids, context, args)

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
            if line.from_yml_test:
                res[line.id] = 'valid'
            else:
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
                res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line_distribution_id, invoice_distribution_id, line_account_id)
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
            if not invl.is_allocatable:
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
            for ml in invl.move_lines or []:
                if ml.analytic_lines:
                    res[invl.id] = self.pool.get('account.analytic.line').get_corrections_history(cr, uid, [x.id for x in ml.analytic_lines])
        return res

    _columns = {
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection', 
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], 
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
        vals.update({'newline': False,})
        return super(account_invoice_line, self).create(cr, uid, vals, context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new invoice line
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Copy analytic distribution
        invl = self.browse(cr, uid, [id], context=context)[0]
        if invl.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, invl.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(account_invoice_line, self).copy_data(cr, uid, id, default, context)

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
