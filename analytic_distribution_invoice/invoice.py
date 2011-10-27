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
                if invl.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Error'), _('Analytic distribution is not valid for "%s"' % invl.name))
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
            # Default value is invalid
            res[line.id] = 'invalid'
            # Search MSF Private Fund element, because it's valid with all accounts
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                'analytic_account_msf_private_funds')[1]
            # Verify that the distribution is compatible with line account
            if line.analytic_distribution_id:
                total = 0.0
                for fp_line in line.analytic_distribution_id.funding_pool_lines:
                    # If fp_line is MSF Private Fund, all is ok
                    if fp_line.analytic_id.id == fp_id:
                        total += 1
                        continue
                    # If account don't be on ONLY ONE funding_pool, then continue
                    if line.account_id.id not in [x.id for x in fp_line.analytic_id.account_ids]:
                        continue
                    else:
                        total += 1
                if total and total == len(line.analytic_distribution_id.funding_pool_lines):
                    res[line.id] = 'valid'
            # If no analytic_distribution on invoice line, check with invoice distribution
            elif line.invoice_id.analytic_distribution_id:
                total = 0.0
                for fp_line in line.invoice_id.analytic_distribution_id.funding_pool_lines:
                    # If fp_line is MSF Private Fund, all is ok
                    if fp_line.analytic_id.id == fp_id:
                        total += 1
                        continue
                    # If account don't be on ONLY ONE funding_pool, then continue
                    if line.account_id.id not in [x.id for x in fp_line.analytic_id.account_ids]:
                        continue
                    else:
                        total += 1
                if total and total == len(line.invoice_id.analytic_distribution_id.funding_pool_lines):
                    res[line.id] = 'valid'
            # If no analytic distribution on invoice line and on invoice, then give 'none' state
            else:
                # no analytic distribution on invoice line or invoice => 'none'
                res[line.id] = 'none'
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
    }

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
