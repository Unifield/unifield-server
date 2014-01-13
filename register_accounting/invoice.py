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
import time

import netsvc

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def button_dummy_compute_total(self, cr, uid, ids, context=None):
        return True

    def _get_virtual_fields(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get fields in order to transform them into 'virtual fields" (kind of field duplicity):
         - currency_id
         - account_id
         - supplier
        """
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = {'virtual_currency_id': inv.currency_id.id or False, 'virtual_account_id': inv.account_id.id or False, 
            'virtual_partner_id': inv.partner_id.id or False}
        return res

    def _is_direct_invoice(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        If this invoice is linked to a register line with "register_line_ids", so this is a direct invoice.
        Otherwise return False
        """
        if not context:
            context = {}
        res = {}
        for inv in self.browse(cr, uid, ids):
            res[inv.id] = False
            if inv.register_line_ids:
                res[inv.id] = True
        return res

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
        'register_line_ids': fields.one2many('account.bank.statement.line', 'invoice_id', string="Register Lines"),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=False, 
            states={'draft':[('readonly',False)]}),
        'virtual_currency_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Currency", 
            type='many2one', relation="res.currency", readonly=True),
        'virtual_account_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Account",
            type='many2one', relation="account.account", readonly=True),
        'virtual_partner_id': fields.function(_get_virtual_fields, method=True, store=False, multi='virtual_fields', string="Supplier",
            type='many2one', relation="res.partner", readonly=True),
        'is_direct_invoice': fields.boolean("Is direct invoice?", readonly=True),
        'register_posting_date': fields.date(string="Register posting date for Direct Invoice", required=False),
        'imported_state': fields.function(_get_imported_state, fnct_search=_search_imported_state, method=True, store=False, type='selection', selection=[('none', 'None'), ('imported', 'Imported'), ('not', 'Not Imported'), ('partial', 'Partially Imported')], string='Imported Status'),
        'down_payment_ids': fields.function(_get_down_payment_ids, type="one2many", obj='account.move.line', method=True, string='Down payments'),
    }

    _defaults = {
        'is_direct_invoice': lambda *a: False,
    }

    def action_reconcile_direct_invoice(self, cr, uid, ids, context=None):
        """
        Reconcile move line if invoice is a Direct Invoice
        NB: In order to define that an invoice is a Direct Invoice, we need to have register_line_ids not null
        """
        for inv in self.browse(cr, uid, ids):
            # Verify that this invoice is linked to a register line and have a move
            if inv.move_id and inv.register_line_ids:
                ml_obj = self.pool.get('account.move.line')
                # First search move line that becomes from invoice
                res_ml_ids = ml_obj.search(cr, uid, [('move_id', '=', inv.move_id.id), ('account_id', '=', inv.account_id.id)])
                if len(res_ml_ids) > 1:
                    raise osv.except_osv(_('Error'), _('More than one journal items found for this invoice.'))
                invoice_move_line_id = res_ml_ids[0]
                # Then search move line that corresponds to the register line
                reg_line = inv.register_line_ids[0]
                reg_ml_ids = ml_obj.search(cr, uid, [('move_id', '=', reg_line.move_ids[0].id), ('account_id', '=', reg_line.account_id.id)])
                if len(reg_ml_ids) > 1:
                    raise osv.except_osv(_('Error'), _('More than one journal items found for this register line.'))
                register_move_line_id = reg_ml_ids[0]
                # Finally do reconciliation
                ml_reconcile_id = ml_obj.reconcile_partial(cr, uid, [invoice_move_line_id, register_move_line_id])
        return True

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

    def invoice_open(self, cr, uid, ids, context=None):
        """
        No longer fills the date automatically, but requires it to be set
        """
        # Some verifications
        if not context:
            context = {}

            
        # Prepare workflow object
        wf_service = netsvc.LocalService("workflow")
        for inv in self.browse(cr, uid, ids):
            values = {}
            curr_date = time.strftime('%Y-%m-%d')
            if not inv.date_invoice and not inv.document_date:
                values.update({'date': curr_date, 'document_date': curr_date, 'state': 'date'})
            elif not inv.date_invoice:
                values.update({'date': curr_date, 'document_date': inv.document_date, 'state': 'date'})
            elif not inv.document_date:
                values.update({'date': inv.date_invoice, 'document_date': curr_date, 'state': 'date'})
            if inv.type in ('in_invoice', 'in_refund') and abs(inv.check_total - inv.amount_total) >= (inv.currency_id.rounding/2.0):
                state = values and 'both' or 'amount'
                values.update({'check_total': inv.check_total , 'amount_total': inv.amount_total, 'state': state})
            if values:
                values['invoice_id'] = inv.id
                wiz_id = self.pool.get('wizard.invoice.date').create(cr, uid, values, context)
                return {
                    'name': "Missing Information",
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.invoice.date',
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_id': wiz_id,
                    }
            
            wf_service.trg_validate(uid, 'account.invoice', inv.id, 'invoice_open', cr)
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
        res = super(account_invoice, self).action_open_invoice(cr, uid, ids, context)
        for inv in self.browse(cr, uid, ids):
            # Create down payments for invoice that come from a purchase
            if inv.purchase_ids:
                self.check_down_payments(cr, uid, inv.id)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete register line if this invoice is a Direct Invoice
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for inv in self.browse(cr, uid, ids):
            if inv.is_direct_invoice and inv.register_line_ids:
                if not context.get('from_register', False):
                    self.pool.get('account.bank.statement.line').unlink(cr, uid, [x.id for x in inv.register_line_ids], {'from_direct_invoice': True})
        return super(account_invoice, self).unlink(cr, uid, ids, context)

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _get_product_code(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Give product code for each invoice line
        """
        res = {}
        for inv_line in self.browse(cr, uid, ids, context=context):
            if inv_line.product_id:
                res[inv_line.id] = inv_line.product_id.default_code
        return res

    _columns = {
        'product_code': fields.function(_get_product_code, method=True, store=False, string="Product Code", type='string'),
    }

    def create(self, cr, uid, vals, context=None):
        """
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """
        if not context:
            context = {}
        res = super(account_invoice_line, self).create(cr, uid, vals, context)
        if vals.get('invoice_id', False):
            invoice = self.pool.get('account.invoice').browse(cr, uid, vals.get('invoice_id'))
            if invoice and invoice.is_direct_invoice and invoice.state == 'draft':
                amount = 0.0
                for l in invoice.invoice_line:
                    amount += l.price_subtotal
                amount += vals.get('price_unit', 0.0) * vals.get('quantity', 0.0)
                self.pool.get('account.invoice').write(cr, uid, [invoice.id], {'check_total': amount}, context)
                self.pool.get('account.bank.statement.line').write(cr, uid, [x.id for x in invoice.register_line_ids], {'amount': -1 * amount}, context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_invoice_line, self).write(cr, uid, ids, vals, context)
        for invl in self.browse(cr, uid, ids):
            if invl.invoice_id and invl.invoice_id.is_direct_invoice and invl.invoice_id.state == 'draft':
                amount = 0.0
                for l in invl.invoice_id.invoice_line:
                    amount += l.price_subtotal
                self.pool.get('account.invoice').write(cr, uid, [invl.invoice_id.id], {'check_total': amount}, context)
                self.pool.get('account.bank.statement.line').write(cr, uid, [x.id for x in invl.invoice_id.register_line_ids], {'amount': -1 * amount}, context)
        return res
    
 
        

    def unlink(self, cr, uid, ids, context=None):
        """
        If invoice is a Direct Invoice and is in draft state:
         - compute total amount (check_total field)
         - write total to the register line
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Fetch all invoice_id to check
        direct_invoice_ids = []
        abst_obj = self.pool.get('account.bank.statement.line')
        for invl in self.browse(cr, uid, ids):
            if invl.invoice_id and invl.invoice_id.is_direct_invoice and invl.invoice_id.state == 'draft':
                direct_invoice_ids.append(invl.invoice_id.id)
                # find account_bank_statement_lines and used this to delete the account_moves and associated records
                absl_ids = abst_obj.search(cr, uid, [('invoice_id','=',invl.invoice_id.id)])
                if absl_ids:
                    abst_obj.unlink_moves(cr, uid, absl_ids, context)
      
        
        # Normal behaviour
        res = super(account_invoice_line, self).unlink(cr, uid, ids, context)
        # See all direct invoice
        for inv in self.pool.get('account.invoice').browse(cr, uid, direct_invoice_ids):
            amount = 0.0
            for l in inv.invoice_line:
                amount += l.price_subtotal
            self.pool.get('account.invoice').write(cr, uid, [inv.id], {'check_total': amount}, context)
            self.pool.get('account.bank.statement.line').write(cr, uid, [x.id for x in inv.register_line_ids], {'amount': -1 * amount}, context)
        return res

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
