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

    def _get_distribution_line_count(self, cr, uid, ids, name, args, context={}):
        """
        Return analytic distribution line count (given by analytic distribution)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse given invoices
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = inv.analytic_distribution_id and inv.analytic_distribution_id.lines_count or 'None'
        return res

    _columns = {
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
    }

    def _hook_fields_for_refund(self, cr, uid, *args):
        """
        Add these fields to result:
         - analytic_distribution_id
        """
        res = super(account_invoice, self)._hook_fields_for_refund(cr, uid, args)
        res.append('analytic_distribution_id')
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
                # Give false order_line_id in order not to give an error
                if 'order_line_id' in el[2]:
                    el[2]['order_line_id'] = el[2].get('order_line_id', False) and el[2]['order_line_id'][0] or False
        return res

    def refund(self, cr, uid, ids, date=None, period_id=None, description=None, journal_id=None):
        """
        Reverse lines for given invoice
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        for inv in self.browse(cr, uid, ids):
            ana_line_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id', 'in', [x.id for x in inv.move_id.line_id])])
            self.pool.get('account.analytic.line').reverse(cr, uid, ana_line_ids)
        return super(account_invoice, self).refund(cr, uid, ids, date, period_id, description, journal_id)

    def copy(self, cr, uid, id, default={}, context={}):
        """
        Copy global distribution and give it to new invoice
        """
        if not context:
            context = {}
        inv = self.browse(cr, uid, [id], context=context)[0]
        if inv.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, inv.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(account_invoice, self).copy(cr, uid, id, default, context)

    def action_open_invoice(self, cr, uid, ids, context={}, *args):
        """
        Add verification on all lines for analytic_distribution_id to be present and valid !
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse invoice and all invoice lines to detect a non-valid line
        for inv in self.browse(cr, uid, ids, context=context):
            for invl in inv.invoice_line:
                if inv.from_yml_test or invl.from_yml_test:
                    continue
                if invl.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Error'), _('Analytic distribution is not valid for "%s"') % invl.name)
        # FIXME: copy invoice analytic distribution header if valid and no analytic_distribution_id
        # FIXME: what about analytic accountancy?
        return super(account_invoice, self).action_open_invoice(cr, uid, ids, context, args)

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _get_distribution_state(self, cr, uid, ids, name, args, context={}):
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
                res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line.analytic_distribution_id.id, line.invoice_id.analytic_distribution_id.id, line.account_id.id)
        return res

    def _get_distribution_line_count(self, cr, uid, ids, name, args, context={}):
        """
        Return analytic distribution line count (given by analytic distribution)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse given invoices
        for invl in self.browse(cr, uid, ids, context=context):
            res[invl.id] = invl.analytic_distribution_id and invl.analytic_distribution_id.lines_count or ''
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context={}):
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

    _columns = {
        'analytic_distribution_line_count': fields.function(_get_distribution_line_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection', 
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], 
            string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean', 
            string='Header Distrib.?'),
        'newline': fields.boolean('New line'),
    }
    
    _defaults = {
        'newline': lambda *a: True,
        'have_analytic_distribution_from_header': lambda *a: True,
    }

    def create(self, cr, uid, vals, context={}):
        vals['newline'] = False
        return super(account_invoice_line, self).create(cr, uid, vals, context)

    def copy_data(self, cr, uid, id, default={}, context={}):
        """
        Copy global distribution and give it to new invoice line
        """
        # Some verifications
        if not context:
            context = {}
        # Copy analytic distribution
        invl = self.browse(cr, uid, [id], context=context)[0]
        if invl.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, invl.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                default.update({'analytic_distribution_id': new_distrib_id})
        return super(account_invoice_line, self).copy_data(cr, uid, id, default, context)

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
