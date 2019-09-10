# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv
from tools.translate import _
import netsvc

class account_invoice_refund(osv.osv_memory):

    """Refunds invoice"""

    _name = "account.invoice.refund"
    _description = "Invoice Refund"

    def _get_filter_refund(self, cr, uid, context=None):
        """
        Returns the selectable Refund Types (no simple "Refund" in case of an IVO/IVI)
        """
        if context is None:
            context = {}
        if context.get('is_intermission', False):
            return [('modify', 'Modify'), ('cancel', 'Cancel')]
        return [('modify', 'Modify'), ('refund', 'Refund'), ('cancel', 'Cancel')]

    _columns = {
        'date': fields.date('Operation date', help='This date will be used as the invoice date for Refund Invoice and Period will be chosen accordingly!'),
        'period': fields.many2one('account.period', 'Force period'),
        'journal_id': fields.many2one('account.journal', 'Refund Journal', hide_default_menu=True,
                                      help='You can select here the journal to use for the refund invoice that will be created. If you leave that field empty, it will use the same journal as the current invoice.'),
        'description': fields.char('Description', size=128, required=True),
        'filter_refund': fields.selection(_get_filter_refund, "Refund Type", required=True, help='Refund invoice based on this type. You can not Modify and Cancel if the invoice is already reconciled'),
    }

    def _get_journal(self, cr, uid, context=None):
        obj_journal = self.pool.get('account.journal')
        if context is None:
            context = {}
        journal = obj_journal.search(cr, uid, [('type', '=', 'sale_refund')])
        if context.get('type', False):
            if context['type'] in ('in_invoice', 'in_refund'):
                journal = obj_journal.search(cr, uid, [('type', '=', 'purchase_refund')])
        return journal and journal[0] or False

    _defaults = {
        'journal_id': _get_journal,
        'filter_refund': 'modify',
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        journal_obj = self.pool.get('account.journal')
        res = super(account_invoice_refund,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        type = context.get('journal_type', 'sale_refund')
        if type in ('sale', 'sale_refund'):
            type = 'sale_refund'
        else:
            type = 'purchase_refund'
        for field in res['fields']:
            if field == 'journal_id':
                journal_select = journal_obj._name_search(cr, uid, '', [('type', '=', type)], context=context, limit=None, name_get_uid=1)
                res['fields'][field]['selection'] = journal_select
        return res

    def _hook_fields_for_modify_refund(self, cr, uid, *args):
        """
        Permits to change values that are taken from initial invoice to new invoice(s)
        """
        res = ['name', 'type', 'number', 'reference', 'comment', 'date_due', 'partner_id', 'address_contact_id', 'address_invoice_id',
               'partner_insite', 'partner_contact', 'partner_ref', 'payment_term', 'account_id', 'currency_id', 'invoice_line', 'tax_line',
               'journal_id', 'period_id']
        return res

    def _hook_fields_m2o_for_modify_refund(self, cr, uid, *args):
        """
        Permits to change values for m2o fields taken from initial values to new invoice(s)
        """
        res = ['address_contact_id', 'address_invoice_id', 'partner_id', 'account_id', 'currency_id', 'payment_term', 'journal_id']
        return res

    def _hook_create_invoice(self, cr, uid, data, form, *args):
        """
        Permits to adapt invoice creation
        """
        res = self.pool.get('account.invoice').create(cr, uid, data, {})
        return res

    def _hook_create_refund(self, cr, uid, inv_ids, date, period, description, journal_id, form, context=None):
        """
        Permits to adapt refund creation
        """
        return self.pool.get('account.invoice').refund(cr, uid, inv_ids, date, period, description, journal_id, context=context)

    def _hook_get_period_from_date(self, cr, uid, invoice_id, date=False, period=False):
        """
        Permit to change date regarding other constraints
        """
        return period

    def _get_reconcilable_amls(self, aml_list, to_reconcile_dict):
        """
        Fill in to_reconcile_dict with the aml from aml_list having a reconcilable account
        key = tuple with (account id, partner_id, is_counterpart)
        value = list of aml ids
        """
        for ml in aml_list:
            if ml.account_id.reconcile:
                key = (ml.account_id.id, ml.partner_id and ml.partner_id.id, ml.is_counterpart)
                to_reconcile_dict.setdefault(key, []).append(ml.id)

    def compute_refund(self, cr, uid, ids, mode='refund', context=None):
        """
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: the account invoice refund’s ID or list of IDs

        """
        inv_obj = self.pool.get('account.invoice')
        reconcile_obj = self.pool.get('account.move.reconcile')
        account_m_line_obj = self.pool.get('account.move.line')
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        wf_service = netsvc.LocalService('workflow')
        inv_tax_obj = self.pool.get('account.invoice.tax')
        inv_line_obj = self.pool.get('account.invoice.line')
        res_users_obj = self.pool.get('res.users')
        if context is None:
            context = {}

        for form in  self.read(cr, uid, ids, context=context):
            created_inv = []
            date = False
            period = False
            description = False
            company = res_users_obj.browse(cr, uid, uid, context=context).company_id
            journal_id = form.get('journal_id', False)
            # in case of a DI refund from a register line use the dir_invoice_id in context
            invoice_ids = context.get('dir_invoice_id') and [context['dir_invoice_id']] or context.get('active_ids')
            for inv in inv_obj.browse(cr, uid, invoice_ids, context=context):
                if inv.state in ['draft', 'proforma2', 'cancel']:
                    raise osv.except_osv(_('Error !'), _('Can not %s draft/proforma/cancel invoice.') % (mode))
                if mode in ('cancel', 'modify') and not inv.account_id.reconcile:
                    raise osv.except_osv(_('Error !'), _("Cannot Cancel / Modify if the account can't be reconciled."))
                if mode in ('cancel', 'modify') and inv_obj.has_one_line_reconciled(cr, uid, [inv.id], context=context):
                    if inv.is_intermission:
                        # error specific to IVO/IVI for which there is no simple refund option
                        raise osv.except_osv(_('Error !'), _('Cannot %s an Intermission Voucher which is already reconciled, it should be unreconciled first.') % _(mode))
                    if inv.state == 'inv_close':
                        raise osv.except_osv(_('Error !'), _('Can not %s invoice which is already reconciled, invoice should be unreconciled first.') % (mode))
                    else:
                        raise osv.except_osv(_('Error !'), _('Can not %s invoice which is already reconciled, invoice should be unreconciled first. You can only Refund this invoice') % (mode))

                if mode == 'refund' and inv.state == 'inv_close':
                    raise osv.except_osv(_('Error !'), _('It is not possible to refund a Closed invoice'))

                if form['period']:
                    period = form['period']
                else:
                    period = inv.period_id and inv.period_id.id or False

                if not journal_id:
                    journal_id = inv.journal_id.id

                if form['date']:
                    date = form['date']
                    if not form['period']:
                        cr.execute("select name from ir_model_fields \
                                        where model = 'account.period' \
                                        and name = 'company_id'")
                        result_query = cr.fetchone()
                        if result_query:
                            cr.execute("""select p.id from account_fiscalyear y, account_period p where y.id=p.fiscalyear_id \
                                and date(%s) between p.date_start AND p.date_stop and y.company_id = %s limit 1""", (date, company.id,))
                        else:
                            cr.execute("""SELECT id
                                    from account_period where date(%s)
                                    between date_start AND  date_stop  \
                                    limit 1 """, (date,))
                        res = cr.fetchone()
                        if res:
                            period = res[0]
                        period = self._hook_get_period_from_date(cr, uid, inv.id, date, period)
                else:
                    date = inv.date_invoice
                if form['description']:
                    description = form['description']
                else:
                    description = inv.name

                if not period:
                    raise osv.except_osv(_('Data Insufficient !'), \
                                         _('No Period found on Invoice!'))

                context.update({'refund_mode': mode})
                refund_id = self._hook_create_refund(cr, uid, [inv.id], date, period, description, journal_id, form, context=context)
                del context['refund_mode']  # ignore it for the remaining process (in particular for the SI created in a refund modify...)
                refund = inv_obj.browse(cr, uid, refund_id[0], context=context)
                # for Intermission Vouchers OUT: at standard creation time there is no "check_total" entered manually,
                # its value is always 0.0 => use the "amount_total" value for the IVI generated so it won't block at validation step
                if inv.is_intermission and inv.type == 'out_invoice':
                    check_total = inv.amount_total or 0.0
                else:
                    check_total = inv.check_total
                inv_obj.write(cr, uid, [refund.id], {'date_due': date,
                                                     'check_total': check_total})

                created_inv.append(refund_id[0])
                if mode in ('cancel', 'modify'):
                    movelines = inv.move_id.line_id
                    for line in movelines:
                        if type(line.reconcile_id) != osv.orm.browse_null:
                            reconcile_obj.unlink(cr, uid, line.reconcile_id.id)
                    wf_service.trg_validate(uid, 'account.invoice', \
                                            refund.id, 'invoice_open', cr)
                    refund = inv_obj.browse(cr, uid, refund_id[0], context=context)

                    # get all invoice and refund lines with reconcilable account, and store them in "to_reconcile"
                    to_reconcile = {}
                    self._get_reconcilable_amls(movelines, to_reconcile)
                    self._get_reconcilable_amls(refund.move_id.line_id, to_reconcile)
                    # reconcile the lines grouped by account
                    for account_id, partner_id, is_counterpart in to_reconcile:
                        account_m_line_obj.reconcile(cr, uid, to_reconcile[(account_id, partner_id, is_counterpart)],
                                                     writeoff_period_id=period,
                                                     writeoff_journal_id = inv.journal_id.id,
                                                     writeoff_acc_id=account_id
                                                     )
                    if mode == 'modify':
                        invoice = inv_obj.read(cr, uid, inv.id, self._hook_fields_for_modify_refund(cr, uid), context=context)
                        del invoice['id']
                        invoice_lines = inv_line_obj.read(cr, uid, invoice['invoice_line'], context=context)
                        invoice_lines = inv_obj._refund_cleanup_lines(cr, uid, invoice_lines, is_account_inv_line=True, context=context)
                        tax_lines = inv_tax_obj.read(cr, uid, invoice['tax_line'], context=context)
                        tax_lines = inv_obj._refund_cleanup_lines(cr, uid, tax_lines, context=context)
                        source_doc = invoice.get('number', False)
                        invoice.update({
                            'type': inv.type,
                            'date_invoice': date,
                            'state': 'draft',
                            'number': False,
                            'invoice_line': invoice_lines,
                            'tax_line': tax_lines,
                            'period_id': False,
                            'name': description,
                            'origin': source_doc,
                            'is_intermission': inv.is_intermission,
                        })
                        for field in self._hook_fields_m2o_for_modify_refund(cr, uid):
                            invoice[field] = invoice[field] and invoice[field][0]
                        inv_id = self._hook_create_invoice(cr, uid, invoice, form)
                        if inv.payment_term.id:
                            data = inv_obj.onchange_payment_term_date_invoice(cr, uid, [inv_id], inv.payment_term.id, date)
                            if 'value' in data and data['value']:
                                inv_obj.write(cr, uid, [inv_id], data['value'])
                        created_inv.append(inv_id)

                    # Refund cancel/modify: set the invoice JI/AJIs as Corrected by the system so that they can't be
                    # corrected manually. This must be done at the end of the refund process to handle the right AJI ids
                    # get the list of move lines excluding invoice header
                    ml_list = [ml.id for ml in movelines if not ml.is_counterpart]
                    account_m_line_obj.set_as_corrected(cr, uid, ml_list, manual=False, context=None)
                    # all JI lines of the SI and SR (including header) should be not corrigible, no matter if they
                    # are marked as corrected, reversed...
                    ji_ids = []
                    ji_ids.extend([si_ji.id for si_ji in movelines])
                    ji_ids.extend([sr_ji.id for sr_ji in refund.move_id.line_id])
                    # write on JIs without recreating AJIs
                    account_m_line_obj.write(cr, uid, ji_ids, {'is_si_refund': True}, context=context, check=False, update_check=False)

            if context.get('is_intermission', False):
                module = 'account_override'
                if inv.type == 'in_invoice':
                    xml_id = 'action_intermission_out'
                else:
                    xml_id = 'action_intermission_in'
            else:
                module = 'account'
                if inv.type in ('out_invoice', 'out_refund'):
                    xml_id = 'action_invoice_tree3'
                else:
                    xml_id = 'action_invoice_tree4'
            result = mod_obj.get_object_reference(cr, uid, module, xml_id)
            id = result and result[1] or False
            result = act_obj.read(cr, uid, id, context=context)
            invoice_domain = eval(result['domain'])
            invoice_domain.append(('id', 'in', created_inv))
            result['domain'] = invoice_domain
            return result

    def invoice_refund(self, cr, uid, ids, context=None):
        data_refund = self.read(cr, uid, ids[0], ['filter_refund'], context=context)['filter_refund']
        return self.compute_refund(cr, uid, ids, data_refund, context=context)


account_invoice_refund()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
