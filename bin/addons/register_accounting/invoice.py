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
            # Fetch second args (type of import)
            s = args[0][2]
            if s == 'not':
                # (US-1275) Display only the invoices "draft", or "open" but not yet partially or fully imported
                sql = """SELECT id FROM
                    (
                      SELECT id FROM account_invoice
                      WHERE state = 'draft'
                      UNION
                        SELECT inv.id
                        FROM account_invoice inv
                        INNER JOIN account_move am ON inv.move_id = am.id
                        INNER JOIN account_move_line aml ON aml.move_id = am.id
                        WHERE inv.state = 'open'
                        AND ABS(aml.amount_residual_import_inv - inv.amount_total) < 0.001
                        AND aml.is_counterpart = 't'
                        AND aml.account_id = inv.account_id
                        AND aml.move_id = inv.move_id
                    ) AS draft_and_not_imported
                    ORDER BY id;"""
            else:
                # Search all imported invoices
                sql = """SELECT INV_ID, INV_TOTAL, RESIDUAL
                    FROM (
                        SELECT inv.id AS INV_ID, inv.amount_total AS INV_TOTAL, aml.id AS AML, aml.amount_residual_import_inv AS RESIDUAL
                        FROM account_invoice inv
                        INNER JOIN account_move am ON inv.move_id = am.id
                        INNER JOIN account_move_line aml ON aml.move_id = am.id
                        WHERE inv.state = 'open'
                        AND aml.is_counterpart = 't'
                        AND aml.account_id = inv.account_id
                        AND aml.move_id = inv.move_id
                        ORDER BY inv.id
                    ) AS move_lines, imported_invoice imp
                    WHERE imp.move_line_id = move_lines.AML
                    GROUP BY INV_ID, INV_TOTAL, RESIDUAL"""
                # Complete SQL query if needed
                having = ''
                if s == 'imported':
                    having = ' HAVING RESIDUAL <= 0.001'
                elif s == 'partial':
                    having = ' HAVING RESIDUAL > 0.001 AND RESIDUAL < INV_TOTAL'
                # finish SQL query
                sql = ''.join((sql, having, ' ORDER BY INV_ID;'))
            # execution
            cr.execute(sql)
            sql_res = cr.fetchall()
            res = [('id', 'in', [x and x[0] for x in sql_res])]
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
        acc_ml_obj = self.pool.get('account.move.line')
        acc_obj = self.pool.get('account.account')
        acc_list = acc_obj.search(cr, uid, [('type', 'in', ['payable', 'receivable'])])
        for inv in self.browse(cr, uid, ids, context):
            res[inv.id] = 'none'
            if inv.move_id:
                absl_ids = self.pool.get('account.bank.statement.line').search(cr, uid, [('imported_invoice_line_ids', 'in', [x.id for x in inv.move_id.line_id])], context=context)
                account = inv.account_id
                if absl_ids and account and (account.id in acc_list):
                    res[inv.id] = 'imported'
                    acc_ml_id = acc_ml_obj.search(cr, uid, [('account_id', '=', account.id),
                                                            ('is_counterpart', '=', True),
                                                            ('move_id', '=', inv.move_id.id)], context=context)
                    acc_ml = acc_ml_obj.browse(cr, uid, acc_ml_id, context)
                    if acc_ml:
                        residual = acc_ml[0].amount_residual_import_inv
                        if residual and abs(residual - inv.amount_total) < 0.001:
                            res[inv.id] = 'not'
                        elif residual and residual < inv.amount_total and residual > 0.001:
                            res[inv.id] = 'partial'
                    else:
                        res[inv.id] = 'not'
                else:
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

    def create_down_payments(self, cr, uid, ids, context=None):
        """
        Create down payments for given invoices
        """
        # Some verifications
        if isinstance(ids, int):
            ids = [ids]
        res = []
        for inv in self.browse(cr, uid, ids):
            remaining_amount = inv.amount_total
            to_use = [] # should contains tuple with: down payment line id, amount

            # Create down payment until given amount is reached
            # browse all invoice purchase, then all down payment attached to purchases
            for po in inv.purchase_ids:
                # Order by id all down payment in order to have them in creation order
                dp_ids = self.pool.get('account.move.line').search(cr, uid, [('down_payment_id', '=', po.id), ('reconcile_id', '=', False)], order='amount_currency, date ASC, id ASC')
                for dp in self.pool.get('account.move.line').browse(cr, uid, dp_ids):
                    # verify that total is not superior to demanded amount
                    if remaining_amount <= 0:
                        break

                    # down_payment_amount: amount already allocated on an invoice
                    # amount_currency: down payment amount
                    if abs(abs(dp.amount_currency) - abs(dp.down_payment_amount)) > 0.001:

                        # compute remaining amount on this dp
                        if remaining_amount > dp.amount_currency - dp.down_payment_amount:
                            allocated = dp.amount_currency - dp.down_payment_amount
                        else:
                            allocated = remaining_amount

                        # Have a tuple containing line id and amount to use for create a payment on invoice
                        to_use.append((dp.id, allocated))

                        remaining_amount -= allocated
            # Create counterparts and reconcile them
            for el in to_use:
                # create down payment counterpart on dp account
                dp_info = self.pool.get('account.move.line').browse(cr, uid, el[0])
                # first create the move
                vals = {
                    'journal_id': inv.journal_id and inv.journal_id.id or False,
                    'period_id': inv.period_id.id,
                    'date': inv.date_invoice,
                    'partner_id': inv.partner_id.id,
                    'ref': '%s:%s' % (inv.name or '',
                                      ':'.join(['%s' % (x.name or '') for x in inv.purchase_ids],), ),
                }
                move_id = self.pool.get('account.move').create(cr, uid, vals)
                # then 2 lines for this move
                vals.update({
                    'move_id': move_id,
                    'partner_type_mandatory': True,
                    'currency_id': inv.currency_id.id,
                    # US-738/UC4: check note below
                    'name': 'Down payment for ' + ':'.join(['%s' % (x.name or '') for x in inv.purchase_ids]),
                    'is_downpayment': True,  # US-738/UC4
                    'document_date': inv.document_date,
                })

                # create dp counterpart line
                dp_account = dp_info and dp_info.account_id and dp_info.account_id.id or False
                debit = 0.0
                credit = el[1]
                if el[1] < 0:
                    credit = 0.0
                    debit = abs(el[1])
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
        if isinstance(ids, int):
            ids = [ids]
        # Browse all invoice and check PO
        for inv in self.browse(cr, uid, ids):
            # Check that no register lines not hard posted are linked to these PO
            st_lines = self.pool.get('account.bank.statement.line').search(cr, uid, [('state', 'in', ['draft', 'temp']), ('down_payment_id', 'in', [x.id for x in inv.purchase_ids])])
            if st_lines:
                raise osv.except_osv(_('Warning'), _('You cannot validate the invoice because some related down payments are not hard posted.'))
            self.create_down_payments(cr, uid, inv.id)
        return True

    def _direct_invoice_updated(self, cr, uid, ids, context=None):
        """
        User has updated the direct invoice. The (parent) statement line needs to be updated, and then
        the move lines deleted and re-created. Ticket utp917.
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
        # the regline ref should match the DI reference if any, else the DI number
        new_ref = direct_invoice.reference or direct_invoice.number
        if new_ref != absl.ref:
            account_bank_statement_line.write(cr, uid, [absl.id], {'ref': new_ref}, context=context)
        # Delete moves
        # existing seqnums are saved into context here. utp917
        account_bank_statement_line.unlink_moves(cr, uid, [absl.id], context=context)
        # Re-create moves and temp post them.
        # account_bank_statement_line.write(cr, uid, [absl.id], {'state': 'draft'}, context=context)
        account_bank_statement_line.button_temp_posting(cr, uid, [absl.id], context=context)
        # remove seqnums from context
        context.pop("seqnums",None)

        # fix the reference UFTP-167
        self.fix_aal_aml_reference(cr, uid, ids[0], context=context)

        return True

    def fix_aal_aml_reference(self, cr, uid, id, context=None):
        # fix the reference UFTP-167, uftp331 and utp-1041

        aml_obj = self.pool.get('account.move.line')
        aal_obj = self.pool.get('account.analytic.line')
        absl_obj = self.pool.get('account.bank.statement.line')

        inv_header = self.browse(cr, uid, id, context=context)
        inv_number = inv_header.number
        inv_header_ref = inv_header.reference

        # 1. find the moves associated with the invoice - account_invoice.move_id
        move_id = self.browse(cr, uid, id, context=context).move_id.id

        # 2. get all the move_lines for that move_id with an account_move_line.invoice_line_id <> null
        aml_ids = aml_obj.search(cr, uid, [('move_id', '=', move_id),('invoice_line_id','!=',False)], context=context)
        move_lines = aml_obj.browse(cr, uid, aml_ids, context=context)

        # 3. get the bank statement line
        absl_ids = absl_obj.search(cr, uid, [('invoice_id','=',inv_header.id)],context=context)
        absl = absl_obj.browse(cr, uid, absl_ids,context=context)[0]
        move_lines.extend(absl.move_ids[0].line_id)

        # 4. get the corresponding invoice_line
        for move_line in move_lines:
            ail = move_line.invoice_line_id

            if ail.reference in (False,None) and inv_header_ref in (False,None):
                # all lines are populated with the invoice number
                # must write to 'reference' to have 'ref' update: very confusing.
                aml_obj.write(cr, uid, move_line.id, {'reference': inv_number}, context=context)
                # update analytic lines. move_id is actually move_line_id
                aal_ids = aal_obj.search(cr, uid, [('move_id','=',move_line.id)], context=context)
                aal_obj.write(cr, uid, aal_ids, {'reference': inv_number}, context=context)

            if ail.reference in (None,False) and inv_header_ref:
                # all lines are populated with the header ref
                aml_obj.write(cr, uid, move_line.id, {'reference': inv_header_ref}, context=context)
                aal_ids = aal_obj.search(cr, uid, [('move_id','=',move_line.id)], context=context)
                aal_obj.write(cr, uid, aal_ids, {'reference': inv_header_ref}, context=context)

            if ail.reference and inv_header_ref in (None,False):
                # move_line.account_id.type == other is the actually the 'expense' account
                if move_line.account_id.type == 'other' and move_line.journal_id.type == 'purchase':
                    reference = ail.reference
                else:
                    reference = inv_number
                # all lines are populated with the header ref
                aml_obj.write(cr, uid, move_line.id, {'reference': reference}, context=context)

            if ail.reference and inv_header_ref:
                # move_line.account_id.type == other is the actually the 'expense' account
                if move_line.account_id.type == 'other' and move_line.journal_id.type == 'purchase':
                    reference = ail.reference
                else:
                    reference = inv_header_ref
                # all lines are populated with the header ref
                aml_obj.write(cr, uid, move_line.id, {'reference': reference}, context=context)
                aal_ids = aal_obj.search(cr, uid, [('move_id','=',move_line.id)], context=context)
                aal_obj.write(cr, uid, aal_ids, {'reference': reference}, context=context)
        return True

    def _check_empty_account(self, cr, uid, ids, context=None):
        """
        Raises an error if one of the invoice lines has no account.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for inv in self.browse(cr, uid, ids, fields_to_fetch=['invoice_line'], context=context):
            for invl in inv.invoice_line:
                if not invl.account_id:
                    raise osv.except_osv(_('Error'), _('The account is missing on the line No. %s.') % invl.line_number)
        return True

    def _check_asset_line(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        if not self.pool.get('unifield.setup.configuration').get_config(cr, uid, key='fixed_asset_ok'):
            return True
        for invoice in self.browse(cr, uid, ids, fields_to_fetch=['doc_type'], context=context):
            if invoice.doc_type in ('si', 'isi', 'ivi'):
                cr.execute("""
                    select
                        l.line_number
                    from
                        account_invoice_line l, account_account a, account_account_type t
                    where
                        a.id = l.account_id
                        and a.user_type = t.id
                        and ( t.code != 'asset' or a.type != 'other' )
                        and l.is_asset='t'
                        and l.invoice_id in %s
                        limit 5
                """, (tuple(ids) ,))
                lines = ['%s'%x[0] for x in cr.fetchall()]
                if lines:
                    raise osv.except_osv(_('Error'), _('Asset line(s) %s must have an asset account.') % ', '.join(lines))
        return True


    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Add down payment check after others verifications
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Browse invoice and all invoice lines to detect a non-valid line
        self._check_empty_account(cr, uid, ids, context=context)
        self._check_asset_line(cr, uid, ids, context=context)
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
        if isinstance(ids, int):
            ids = [ids]
        context['direct_invoice_view'] = 1
        self._check_analytic_distribution_state(cr, uid, ids, context)
        self._direct_invoice_updated(cr, uid, ids, context)

        if context.get('from_register', False):
            return {'type': 'ir.actions.act_window_close'}
        return True

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check that all register lines are updated if this invoice is a direct invoice.
        """
        if not ids:
            return True
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        # UFTP-312: Update register line after any changes on the direct invoice
        authorized_list_for_update = ['ref', 'account_id', 'partner_id', 'document_date', 'amount_out']
        do_changes = False
        for field in authorized_list_for_update:
            if field in vals and vals.get(field, False):
                do_changes = True
                break
        if do_changes:
            absl_obj = self.pool.get('account.bank.statement.line')
            for inv in self.read(cr, uid, ids, ['is_direct_invoice', 'reference', 'account_id', 'partner_id', 'document_date', 'invoice_amount', 'check_total', 'st_lines'], context=context):
                if inv.get('is_direct_invoice', False):
                    # search the statement line
                    if inv.get('st_lines', False):
                        # update it with some values: reference, document date, account and partner
                        vals = {
                            'ref': inv.get('reference', ''),
                            'account_id': inv.get('account_id', False) and inv.get('account_id')[0] or False,
                            'partner_id': inv.get('partner_id', False) and inv.get('partner_id')[0] or False,
                            'document_date': inv.get('document_date', False),
                            'amount_out': inv.get('check_total', False),
                        }
                        # add specific context to avoid problem from
                        absl_obj.write(cr, uid, inv.get('st_lines'), vals, context=context)
        return res

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
