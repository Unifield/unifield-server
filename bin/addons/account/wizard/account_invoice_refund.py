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
import time

class account_invoice_refund(osv.osv_memory):

    """Refunds invoice"""

    _name = "account.invoice.refund"
    _description = "Invoice Refund"

    def _get_filter_refund(self, cr, uid, context=None):
        """
        Returns the selectable Refund Types (no simple "Refund" in case of an IVO/IVI or STV, only Refund/Cancel in case of an ISI)
        """
        if context is None:
            context = {}
        refund_types = [('modify', 'Modify'), ('refund', 'Refund'), ('cancel', 'Cancel')]
        if context.get('is_intermission', False) or context.get('doc_type', '') == 'stv':
            refund_types = [('modify', 'Modify'), ('cancel', 'Cancel')]
        elif context.get('doc_type', '') == 'isi':
            # note: Refund Cancel is allowed only if the counterpart invoice is closed (handled directly in ISI form)
            refund_types = [('cancel', 'Cancel')]
        return refund_types

    def _get_journal(self, cr, uid, context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        obj_journal = self.pool.get('account.journal')
        obj_inv = self.pool.get('account.invoice')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if context is None:
            context = {}
        args = [('type', '=', 'sale_refund')]
        # in case of a DI refund from a register line use the dir_invoice_id in context
        doc_to_refund_id = context.get('dir_invoice_id', False) or (context.get('active_ids') and context['active_ids'][0])
        if doc_to_refund_id:
            source = obj_inv.read(cr, uid, doc_to_refund_id, ['type', 'is_intermission', 'doc_type', 'journal_id'], context=context)
            if source['doc_type'] == 'stv':
                if source['journal_id']:
                    # by default use the same journal for the refund
                    args = [('id', '=', source['journal_id'][0])]
                else:
                    args = [('type', '=', 'sale')]
            elif source['doc_type'] == 'isi':
                args = [('type', '=', 'purchase'), ('code', '=', 'ISI')]
            elif source['is_intermission']:
                args = [('type', '=', 'intermission')]
            elif source['type'] in ('in_invoice', 'in_refund'):
                args = [('type', '=', 'purchase_refund')]
        if user.company_id.instance_id:
            args.append(('is_current_instance','=',True))
        args.append(('is_active', '=', True))
        # get the first journal created matching with the defined criteria
        journal = obj_journal.search(cr, uid, args, order='id', limit=1, context=context)
        return journal and journal[0] or False

    def _get_document_date(self, cr, uid, context=None):
        if context is None:
            context = {}
        invoice_id = context.get('dir_invoice_id') or (context.get('active_ids') and context['active_ids'][0])
        if invoice_id:
            invoice_module = self.pool.get('account.invoice')
            doc_date = invoice_module.read(cr, uid, invoice_id, ['document_date'],
                                           context=context)['document_date']
            return doc_date
        return time.strftime('%Y-%m-%d')


    _columns = {
        'date': fields.date('Posting date'),
        'period': fields.many2one('account.period', 'Force period'),
        'journal_id': fields.many2one('account.journal', 'Refund Journal', hide_default_menu=True,
                                      help='You can select here the journal to use for the refund invoice that will be created. If you leave that field empty, it will use the same journal as the current invoice.'),
        'description': fields.char('Description', size=128, required=True),
        'filter_refund': fields.selection(_get_filter_refund, "Refund Type", required=True, help='Refund invoice based on this type. You can not Modify and Cancel if the invoice is already reconciled'),
        'document_date': fields.date('Document Date', required=True),
        'is_intermission': fields.boolean("Wizard opened from an Intermission Voucher", readonly=True),
        'is_stv': fields.boolean("Wizard opened from a Stock Transfer Voucher", readonly=True),
        'is_isi': fields.boolean("Wizard opened from an Intersection Supplier Invoice", readonly=True),
    }

    def _get_refund(self, cr, uid, context=None):
        """
        Returns the default value for the 'filter_refund' field depending on the context
        """
        if context is None:
            context = {}
        if context.get('is_intermission', False) or context.get('doc_type', '') == 'stv':
            return 'modify'
        elif context.get('doc_type', '') == 'isi':
            return 'cancel'
        return 'refund'  # note that only the "Refund" option is available in DI

    def _get_is_intermission(self, cr, uid, context=None):
        """
        Returns True if the wizard has been opened from an Intermission Voucher
        """
        if context is None:
            context = {}
        return context.get('is_intermission', False)

    def _get_is_stv(self, cr, uid, context=None):
        """
        Returns True if the wizard has been opened from a Stock Transfer Voucher
        """
        if context is None:
            context = {}
        return context.get('doc_type', '') == 'stv'

    def _get_is_isi(self, cr, uid, context=None):
        """
        Returns True if the wizard has been opened from an Intersection Supplier Invoice
        """
        if context is None:
            context = {}
        return context.get('doc_type', '') == 'isi'

    _defaults = {
        'document_date': _get_document_date,
        'filter_refund': _get_refund,
        'journal_id': _get_journal,  # US-193
        'is_intermission': _get_is_intermission,
        'is_stv': _get_is_stv,
        'is_isi': _get_is_isi,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = super(account_invoice_refund,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if context.get('doc_type', '') in ('ivo', 'ivi'):
            # only the first Intermission journal created (INT, always active because it is one of the default journals created)
            int_journal_id = self.pool.get('account.invoice')._get_int_journal_for_current_instance(cr, uid, context=context)
            journal_domain = [('id', '=', int_journal_id)]
        else:
            if context.get('doc_type', '') == 'stv':
                jtype = 'sale'
            elif context.get('doc_type', '') == 'isi':
                jtype = 'purchase'
            else:
                jtype = 'sale_refund'
                if context.get('journal_type'):
                    jtype = isinstance(context['journal_type'], list) and context['journal_type'][0] or context['journal_type']
                if jtype in ('sale', 'sale_refund'):
                    jtype = 'sale_refund'
                else:
                    jtype = 'purchase_refund'
            journal_domain = [('type', '=', jtype), ('is_current_instance', '=', True), ('is_active', '=', True)]
        if context.get('doc_type', '') == 'isi':
            journal_domain.append(('code', '=', 'ISI'))
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        for field in res['fields']:
            if field == 'journal_id' and user.company_id.instance_id:
                journal_select = journal_obj._name_search(cr, uid, '', journal_domain, context=context, limit=None, name_get_uid=1)
                res['fields'][field]['selection'] = journal_select
                res['fields'][field]['domain'] = journal_domain
        return res


    def _hook_fields_for_modify_refund(self, cr, uid, *args):
        """
        Permits to change values that are taken from initial invoice to new invoice(s)
        """
        res = ['name', 'type', 'number', 'reference', 'comment', 'date_due', 'partner_id', 'address_contact_id', 'address_invoice_id',
               'partner_insite', 'partner_contact', 'partner_ref', 'payment_term', 'account_id', 'currency_id', 'invoice_line', 'tax_line',
               'journal_id', 'period_id', 'analytic_distribution_id']
        return res

    def _hook_fields_m2o_for_modify_refund(self, cr, uid, *args):
        """
        Permits to change values for m2o fields taken from initial values to new invoice(s)
        """
        res = ['address_contact_id', 'address_invoice_id', 'partner_id', 'account_id', 'currency_id', 'payment_term', 'journal_id', 'analytic_distribution_id']
        return res

    def _get_invoice_context(self, context):
        """
        Gets the context to be used in _hook_create_invoice

        US-8585: for now only "from_refund_button" is handled, the context is otherwise empty in order not to break the current behavior.
        """
        if context and context.get('from_refund_button'):
            inv_context = {'from_refund_button': True}
        else:
            inv_context = {}
        return inv_context

    def _hook_create_invoice(self, cr, uid, data, form, context=None):
        """
        Permits to adapt invoice creation
        """
        if form.get('document_date', False) and form.get('date', False):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               form['document_date'], form['date'])
            data.update({'document_date': form['document_date']})
        inv_context = self._get_invoice_context(context)
        res = self.pool.get('account.invoice').create(cr, uid, data, context=inv_context)
        return res

    def _hook_create_refund(self, cr, uid, inv_ids, date, period, description, journal_id, form, context=None):
        """
        Permits to adapt refund creation
        """
        if form.get('document_date', False):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               form['document_date'], date)
            return self.pool.get('account.invoice').refund(cr, uid, inv_ids, date, period, description, journal_id, form['document_date'], context=context)

        return self.pool.get('account.invoice').refund(cr, uid, inv_ids, date, period, description, journal_id, context=context)

    def _hook_get_period_from_date(self, cr, uid, invoice_id, date=False, period=False):
        """
        Get period regarding given date
        """
        res = period
        if date:
            period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, date)
            if period_ids and isinstance(period_ids, list):
                res = period_ids[0]
        return res

    def _get_reconcilable_amls(self, aml_list, to_reconcile_dict):
        """
        Fill in to_reconcile_dict with the aml from aml_list having a reconcilable account
        key = tuple with (account id, partner_id, is_counterpart)
        value = list of aml ids
        """
        for ml in aml_list:
            if ml.account_id.reconcile:
                key = (ml.account_id.id, ml.partner_id and ml.partner_id.id or False, ml.is_counterpart)
                to_reconcile_dict.setdefault(key, []).append(ml.id)

    def compute_refund(self, cr, uid, ids, mode='refund', context=None):
        """
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: the account invoice refund’s ID or list of IDs

        """
        if mode == 'modify' or mode == 'cancel':
            invoice_obj = self.pool.get('account.invoice')
            inv_ids = context.get('dir_invoice_id') and [context['dir_invoice_id']] or context.get('active_ids', [])
            invoices = invoice_obj.browse(cr, uid, inv_ids, context=context)
            for invoice in invoices:
                if invoice.imported_state == 'partial':
                    raise osv.except_osv(_('Error !'), _('You can not refund-modify nor refund-cancel an invoice partially imported in a register.'))

        inv_obj = self.pool.get('account.invoice')
        reconcile_obj = self.pool.get('account.move.reconcile')
        account_m_line_obj = self.pool.get('account.move.line')
        act_obj = self.pool.get('ir.actions.act_window')
        wf_service = netsvc.LocalService('workflow')
        inv_tax_obj = self.pool.get('account.invoice.tax')
        inv_line_obj = self.pool.get('account.invoice.line')
        res_users_obj = self.pool.get('res.users')
        aal_obj = self.pool.get('account.analytic.line')
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
                    if inv.state == 'inv_close' or inv.is_intermission or inv.doc_type in ('stv', 'isi'):
                        # error msg specific to UC where there is no simple refund option
                        raise osv.except_osv(_('Error !'), _('Cannot %s an invoice which is already reconciled, '
                                                             'it should be unreconciled first.') % _(mode))
                    else:
                        raise osv.except_osv(_('Error !'), _('Cannot %s an invoice which is already reconciled, '
                                                             'it should be unreconciled first. You can only Refund this invoice.') % _(mode))
                if mode == 'refund' and inv.state == 'inv_close':
                    raise osv.except_osv(_('Error !'), _('It is not possible to refund a Closed invoice'))
                if mode == 'modify' and not inv.journal_id.is_active:
                    raise osv.except_osv(_('Error !'), _('The journal %s is inactive. Refunds of type "Modify" are not allowed.') %
                                         inv.journal_id.code)

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
                if (inv.is_intermission and inv.type == 'out_invoice') or inv.doc_type == 'isi':
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
                        invoice.update({'refunded_invoice_id': invoice['id'], 'signature_id': False})
                        del invoice['id']
                        invoice_lines = inv_line_obj.read(cr, uid, invoice['invoice_line'], context=context)
                        invoice_lines = inv_obj._refund_cleanup_lines(cr, uid, invoice_lines, is_account_inv_line=True, context=context)
                        tax_lines = inv_tax_obj.read(cr, uid, invoice['tax_line'], context=context)
                        tax_lines = inv_obj._refund_cleanup_lines(cr, uid, tax_lines, context=context)
                        source_doc = invoice.get('number', False)
                        invoice.update({
                            'type': inv.type,
                            'real_doc_type': inv.doc_type or '',
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
                        inv_id = self._hook_create_invoice(cr, uid, invoice, form, context=context)
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
                    # blocks the refund Cancel or Modify in case the AD of one of the related AJI has been updated
                    # Note that the case where REV/COR have been generated is handled in "set_as_corrected", which is also used out of refunds.
                    for ml_id in ml_list:
                        if aal_obj.search_exist(cr, uid, [('move_id', '=', ml_id), ('ad_updated', '=', True)], context=context):
                            move_name = account_m_line_obj.browse(cr, uid, ml_id, fields_to_fetch=['move_id'], context=context).move_id.name
                            raise osv.except_osv(_('Error'), _('The Analytic Distribution linked to the entry %s has '
                                                               'been updated since the invoice validation.\n'
                                                               'Refunds of type "Modify" and "Cancel" are not allowed.')
                                                 % move_name)
                    # all JI lines of the SI and SR (including header) should be not corrigible, no matter if they
                    # are marked as corrected, reversed...
                    ji_ids = []
                    ji_ids.extend([si_ji.id for si_ji in movelines])
                    ji_ids.extend([sr_ji.id for sr_ji in refund.move_id.line_id])
                    # write on JIs without recreating AJIs
                    account_m_line_obj.write(cr, uid, ji_ids, {'is_si_refund': True}, context=context, check=False, update_check=False)
            # return to a tree view containing the refund generated
            from_doc_type = context.get('doc_type', '')
            if from_doc_type == 'stv':
                return_doc_type = 'str'
            elif from_doc_type == 'ivo':
                return_doc_type = 'ivi'
            elif from_doc_type == 'ivi':
                return_doc_type = 'ivo'
            elif from_doc_type == 'isi':
                return_doc_type = 'isr'
            else:  # i.e. si, di
                return_doc_type = 'sr'
            action_act_window = inv_obj._invoice_action_act_window[return_doc_type]
            result = act_obj.open_view_from_xmlid(cr, uid, action_act_window, new_tab=True, context=context)
            invoice_domain = eval(result['domain'])
            invoice_domain.append(('id', 'in', created_inv))
            result['domain'] = invoice_domain
            return result

    def invoice_refund(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context.update({'from_refund_button': True})
        data_refund = self.read(cr, uid, ids[0], ['filter_refund'], context=context)['filter_refund']
        return self.compute_refund(cr, uid, ids, data_refund, context=context)


account_invoice_refund()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
