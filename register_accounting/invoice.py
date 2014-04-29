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
    _inherit = 'account.invoice'

    def _search_imported_state(self, cr, uid, ids, name, args, context=None):
        """
        Search invoice regarding their imported_state field. Check _get_imported_state for more information.
        """
        res = [('id', 'not in', [])]
        if args and args[0] and len(args[0]) == 3:
            if args[0][1] != '=':
                raise osv.except_osv(_('Error'), _('Operator not supported yet!'))
            # Search all imported invoice
            sql = """SELECT INV_ID, INV_TOTAL, abs(SUM(absl.amount))
                FROM (
                    SELECT inv.id AS INV_ID, inv.amount_total AS INV_TOTAL, aml.id AS AML
                    FROM account_invoice inv, account_move_line aml, account_move am
                    WHERE inv.move_id = am.id
                    AND aml.move_id = am.id
                    AND inv.state = 'open'
                    ORDER BY inv.id
                ) AS move_lines, imported_invoice imp, account_bank_statement_line absl
                WHERE imp.move_line_id = move_lines.AML
                AND imp.st_line_id = absl.id
                GROUP BY INV_ID, INV_TOTAL"""
            # Fetch second args (type of import)
            s = args[0][2]
            # Complete SQL query if needed
            if s == 'imported':
                sql += """ HAVING INV_TOTAL = abs(SUM(absl.amount))"""
            elif s == 'partial':
                sql += """ HAVING INV_TOTAL != abs(SUM(absl.amount))"""
            # finish SQL query
            sql += """ ORDER BY INV_ID;"""
            # execution
            cr.execute(sql)
            sql_res = cr.fetchall()
            # process regarding second args
            if s in ['partial', 'imported']:
                res = [('id', 'in', [x and x[0] for x in sql_res])]
            else:
                res = [('id', 'not in', [x and x[0] for x in sql_res])]
        return res

    def _get_imported_state(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Different states:
        - imported: imported_invoice_line_ids exists for this invoice (so register lines are linked to it) and invoice state is paid
        - partial: imported_invoice_line_ids exists for this invoice (so that register lines are linked to it) and invoice state is open (so not totally paid)
        - not: no imported_invoice_line_ids on this invoice (so no link to a register)
        - unknown: default state
        """
        if not context:
            context = {}
        res = {}
        for inv in self.browse(cr, uid, ids, context):
            res[inv.id] = 'none'
            if inv.move_id:
                absl_ids = self.pool.get('account.bank.statement.line').search(cr, uid, [('imported_invoice_line_ids', 'in', [x.id for x in inv.move_id.line_id])])
                if absl_ids:
                    res[inv.id] = 'imported'
                    if isinstance(absl_ids, (int, long)):
                        absl_ids = [absl_ids]
                    if inv.amount_total != sum([x and abs(x.amount) or 0.0 for x in self.pool.get('account.bank.statement.line').browse(cr, uid, absl_ids)]):
                        res[inv.id] = 'partial'
                    continue
                res[inv.id] = 'not'
        return res

    def _get_down_payment_ids(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Search down payment journal items for given invoice
        """
        # Some checks
        if not context:
            context = {}
        res = {}
        for inv in self.browse(cr, uid, ids):
            res[inv.id] = []
            for p in inv.purchase_ids:
                res[inv.id] += [x and x.id for x in p.down_payment_ids]
        return res

    _columns = {
        'imported_state': fields.function(_get_imported_state, fnct_search=_search_imported_state, method=True, store=False, type='selection', selection=[('none', 'None'), ('imported', 'Imported'), ('not', 'Not Imported'), ('partial', 'Partially Imported')], string='Imported Status'),
        'down_payment_ids': fields.function(_get_down_payment_ids, type="one2many", obj='account.move.line', method=True, string='Down payments'),
    }

    def create_down_payments(self, cr, uid, ids, amount, context=None):
        """
        Create down payments for given invoices
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not amount:
            raise osv.except_osv(_('Warning'), _('Amount for Down Payment is missing!'))
        # Prepare some values
        res = []
        # Browse all elements
        for inv in self.browse(cr, uid, ids):
            # some verification
            if amount > inv.amount_total:
                raise osv.except_osv(_('Error'), _('Given down payment amount is superior to given invoice. Please check both.'))
            # prepare some values
            total = 0.0
            to_use = [] # should contains tuple with: down payment line id, amount

            # Create down payment until given amount is reached
            # browse all invoice purchase, then all down payment attached to purchases
            for po in inv.purchase_ids:
                # Order by id all down payment in order to have them in creation order
                dp_ids = self.pool.get('account.move.line').search(cr, uid, [('down_payment_id', '=', po.id)], order='date ASC, id ASC')
                for dp in self.pool.get('account.move.line').browse(cr, uid, dp_ids):
                    # verify that total is not superior to demanded amount
                    if total >= amount:
                        continue
                    diff = 0.0
                    # Take only line that have a down_payment_amount not superior or equal to line amount
                    if not dp.down_payment_amount > dp.amount_currency:
                        if amount > (abs(dp.amount_currency) - abs(dp.down_payment_amount)):
                            diff = (abs(dp.amount_currency) - abs(dp.down_payment_amount))
                        else:
                            diff = amount
                        # Have a tuple containing line id and amount to use for create a payment on invoice
                        to_use.append((dp.id, diff))
                    # Increment processed total
                    total += diff
            # Create counterparts and reconcile them
            for el in to_use:
                # create down payment counterpart on dp account
                dp_info = self.pool.get('account.move.line').browse(cr, uid, el[0])
                # first create the move
                vals = {
                    'journal_id': dp_info.statement_id and dp_info.statement_id.journal_id and dp_info.statement_id.journal_id.id or False,
                    'period_id': inv.period_id.id,
                    'date': inv.date_invoice,
                    'partner_id': inv.partner_id.id,
                    'ref': ':'.join(['%s' % (x.name or '') for x in inv.purchase_ids]),
                }
                move_id = self.pool.get('account.move').create(cr, uid, vals)
                # then 2 lines for this move
                vals.update({
                    'move_id': move_id,
                    'partner_type_mandatory': True,
                    'currency_id': inv.currency_id.id,
                    'name': 'Down payment for ' + ':'.join(['%s' % (x.name or '') for x in inv.purchase_ids]),
                    'document_date': inv.document_date,
                })
                # create dp counterpart line
                dp_account = dp_info and dp_info.account_id and dp_info.account_id.id or False
                debit = 0.0
                credit = el[1]
                if amount < 0:
                    credit = 0.0
                    debit = el[1]
                vals.update({
                    'account_id': dp_account or False,
                    'debit_currency': debit,
                    'credit_currency': credit,
                })
                dp_counterpart_id = self.pool.get('account.move.line').create(cr, uid, vals)
                # create supplier line
                vals.update({
                    'account_id': inv.account_id.id,
                    'debit_currency': credit, # opposite of dp counterpart line
                    'credit_currency': debit, # opposite of dp counterpart line
                })
                supplier_line_id = self.pool.get('account.move.line').create(cr, uid, vals)
                # post move
                self.pool.get('account.move').post(cr, uid, [move_id])
                # and reconcile down payment counterpart
                self.pool.get('account.move.line').reconcile_partial(cr, uid, [el[0], dp_counterpart_id], type='manual')
                # and reconcile invoice and supplier_line
                to_reconcile = [supplier_line_id]
                for line in inv.move_id.line_id:
                    if line.account_id.id == inv.account_id.id:
                        to_reconcile.append(line.id)
                if not len(to_reconcile) > 1:
                    raise osv.except_osv(_('Error'), _('Did not achieve invoice reconciliation with down payment.'))
                self.pool.get('account.move.line').reconcile_partial(cr, uid, to_reconcile)
                # add amount of invoice down_payment line on purchase order to keep used amount
                current_amount = self.pool.get('account.move.line').read(cr, uid, el[0], ['down_payment_amount']).get('down_payment_amount')
                self.pool.get('account.move.line').write(cr, uid, [el[0]], {'down_payment_amount': current_amount + el[1]})
                # add payment to result
                res.append(dp_counterpart_id)
        return res

    def check_down_payments(self, cr, uid, ids, context=None):
        """
        Verify that PO have down payments.
        If not, check that no Down Payment in temp state exists in registers.
        If yes, launch down payment creation and attach it to invoice.
        """
        # Some verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all invoice and check PO
        for inv in self.browse(cr, uid, ids):
            total_payments = 0.0
            # Check that no register lines not hard posted are linked to these PO
            st_lines = self.pool.get('account.bank.statement.line').search(cr, uid, [('state', 'in', ['draft', 'temp']), ('down_payment_id', 'in', [x.id for x in inv.purchase_ids])])
            if st_lines:
                raise osv.except_osv(_('Warning'), _('You cannot validate the invoice because some related down payments are not hard posted.'))
            for po in inv.purchase_ids:
                for dp in po.down_payment_ids:
                    if abs(dp.down_payment_amount) < abs(dp.amount_currency):
                        total_payments += (dp.amount_currency - dp.down_payment_amount)
            if total_payments == 0.0:
                continue
            elif (inv.amount_total - total_payments) > 0.0:
                # Attach a down payment to this invoice
                self.create_down_payments(cr, uid, inv.id, total_payments)
            elif (inv.amount_total - total_payments) <= 0.0:
                # In this case, down payment permits to pay entirely invoice, that's why the down payment equals invoice total
                self.create_down_payments(cr, uid, inv.id, inv.amount_total)
        return True

    def _direct_invoice_updated(self, cr, uid, ids, context=None):
        """
        User has updated the direct invoice. The (parent) statement line needs to be updated, and then
        the move lines deleted and re-created. Ticket utp917. Sheer madness.
        """
        # get object handles
        account_bank_statement_line = self.pool.get('account.bank.statement.line')  #absl
        direct_invoice = self.browse(cr, uid, ids, context=context)[0]
        # get statement line id
        absl = direct_invoice.register_line_ids[0]
        if (direct_invoice.document_date != absl.document_date) or (direct_invoice.partner_id != absl.partner_id):
            account_bank_statement_line.write(cr, uid, [absl.id], {'document_date': direct_invoice.document_date, \
                                                                   'partner_id': direct_invoice.partner_id.id , \
                                                                   'account_id': direct_invoice.account_id.id}, # UFTP-166: Saved also the account change to reg line
                                                                   context=context)
        # Delete moves
        # existing seqnums are saved into context here. utp917
        account_bank_statement_line.unlink_moves(cr, uid, [absl.id], context=context)
        # Re-create moves and temp post them.
        # account_bank_statement_line.write(cr, uid, [absl.id], {'state': 'draft'}, context=context)
        account_bank_statement_line.button_temp_posting(cr, uid, [absl.id], context=context)
        # remove seqnums from context
        context.pop("seqnums",None)
        return True

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Add down payment check after others verifications
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse invoice and all invoice lines to detect a non-valid line
        self._check_analytic_distribution_state(cr, uid, ids)
        # Default behaviour
        res = super(account_invoice, self).action_open_invoice(cr, uid, ids, context)
        to_check = []
        for inv in self.read(cr, uid, ids, ['purchase_ids']):
            # Create down payments for invoice that come from a purchase
            if inv.get('purchase_ids', []):
                to_check.append(inv.get('id'))
        self.check_down_payments(cr, uid, to_check)
        return res

    def button_close_direct_invoice(self, cr, uid, ids, context=None):
        """
        Check analytic distribution before closing pop-up
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._check_analytic_distribution_state(cr, uid, ids, context)
        self._direct_invoice_updated(cr, uid, ids, context)

        if context.get('from_register', False):
            return {'type': 'ir.actions.act_window_close'}
        return True

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
