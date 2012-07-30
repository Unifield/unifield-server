#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
import re
from lxml import etree
from time import strftime

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'import_invoice_id': fields.many2one('account.invoice', string="From an import invoice", readonly=True),
        'move_lines': fields.one2many('account.move.line', 'invoice_line_id', string="Journal Item", readonly=True),
    }

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy an invoice line without its move lines
        """
        if default is None:
            default = {}
        default.update({'move_lines': False,})
        return super(account_invoice_line, self).copy_data(cr, uid, id, default, context)

    def move_line_get_item(self, cr, uid, line, context=None):
        """
        Add a link between move line and its invoice line
        """
        # some verification
        if not context:
            context = {}
        # update default dict with invoice line ID
        res = super(account_invoice_line, self).move_line_get_item(cr, uid, line, context=context)
        res.update({'invoice_line_id': line.id})
        return res

account_invoice_line()

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Fake method for 'ready_for_import_in_debit_note' field
        """
        res = {}
        for id in ids:
            res[id] = False
        return res

    def _search_ready_for_import_in_debit_note(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        account_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account and \
            self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account.id or False
        if not account_id:
            raise osv.except_osv(_('Error'), _('No default account for import invoice on Debit Note!'))
        dom1 = [
            ('account_id','=',account_id),
            ('reconciled','=',False), 
            ('state', '=', 'open'), 
            ('type', '=', 'out_invoice'), 
            ('journal_id.type', 'in', ['sale']),
            ('partner_id.partner_type', '=', 'section'),
        ]
        return dom1+[('is_debit_note', '=', False)]

    def _get_fake_m2o_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get many2one field content
        """
        res = {}
        name = field_name.replace("fake_", '')
        for i in self.browse(cr, uid, ids):
            res[i.id] = getattr(i, name, False) and getattr(getattr(i, name, False), 'id', False) or False
        return res

    _columns = {
        'is_debit_note': fields.boolean(string="Is a Debit Note?"),
        'is_inkind_donation': fields.boolean(string="Is an In-kind Donation?"),
        'is_intermission': fields.boolean(string="Is an Intermission Voucher?"),
        'ready_for_import_in_debit_note': fields.function(_get_fake, fnct_search=_search_ready_for_import_in_debit_note, type="boolean", 
            method=True, string="Can be imported as invoice in a debit note?",),
        'imported_invoices': fields.one2many('account.invoice.line', 'import_invoice_id', string="Imported invoices", readonly=True),
        'partner_move_line': fields.one2many('account.move.line', 'invoice_partner_link', string="Partner move line", readonly=True),
        'fake_account_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="account.account", string="Account", readonly="True"),
        'fake_journal_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="account.journal", string="Journal", readonly="True"),
        'fake_currency_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="res.currency", string="Currency", readonly="True"),
    }

    _defaults = {
        'is_debit_note': lambda obj, cr, uid, c: c.get('is_debit_note', False),
        'is_inkind_donation': lambda obj, cr, uid, c: c.get('is_inkind_donation', False),
        'is_intermission': lambda obj, cr, uid, c: c.get('is_intermission', False),
    }

    def log(self, cr, uid, id, message, secondary=False, context=None):
        """
        Change first "Invoice" word from message into "Debit Note" if this invoice is a debit note.
        Change it to "In-kind donation" if this invoice is an In-kind donation.
        """
        if not context:
            context = {}
        # Prepare some values
        # Search donation view and return it
        try:
            # try / except for runbot
            debit_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_debit_note_form')
            inkind_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_inkind_donation_form')
            intermission_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_intermission_form')
        except ValueError:
            return super(account_invoice, self).log(cr, uid, id, message, secondary, context)
        debit_view_id = debit_res and debit_res[1] or False
        debit_note_ctx = {'view_id': debit_view_id, 'type':'out_invoice', 'journal_type': 'sale', 'is_debit_note': True}
        # Search donation view and return it
        inkind_view_id = inkind_res and inkind_res[1] or False
        inkind_ctx = {'view_id': inkind_view_id, 'type':'in_invoice', 'journal_type': 'inkind', 'is_inkind_donation': True}
        # Search intermission view
        intermission_view_id = intermission_res and intermission_res[1] or False
        intermission_ctx = {'view_id': intermission_view_id, 'journal_type': 'intermission', 'is_intermission': True}
        for el in [('is_debit_note', 'Debit Note', debit_note_ctx), ('is_inkind_donation', 'In-kind Donation', inkind_ctx), ('is_intermission', 'Intermission Voucher', intermission_ctx)]:
            if self.read(cr, uid, id, [el[0]]).get(el[0], False) is True:
                pattern = re.compile('^(Invoice)')
                m = re.match(pattern, message)
                if m and m.groups():
                    message = re.sub(pattern, el[1], message, 1)
                context.update(el[2])
        return super(account_invoice, self).log(cr, uid, id, message, secondary, context)

    def onchange_partner_id(self, cr, uid, ids, type, partner_id,\
        date_invoice=False, payment_term=False, partner_bank_id=False, company_id=False, is_inkind_donation=False, is_intermission=False):
        """
        Update fake_account_id field regarding account_id result.
        Get default donation account for Donation invoices.
        Get default intermission account for Intermission Voucher IN/OUT invoices.
        """
        res = super(account_invoice, self).onchange_partner_id(cr, uid, ids, type, partner_id, date_invoice, payment_term, partner_bank_id, company_id)
        if is_inkind_donation and partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            account_id = partner and partner.donation_payable_account and partner.donation_payable_account.id or False
            res['value']['account_id'] = account_id
        if is_intermission and partner_id:
            intermission_default_account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
            account_id = intermission_default_account and intermission_default_account.id or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('Please configure a default intermission account in Company configuration.'))
            res['value']['account_id'] = account_id
        if res.get('value', False) and 'account_id' in res['value']:
            res['value'].update({'fake_account_id': res['value'].get('account_id')})
        return res

    def _refund_cleanup_lines(self, cr, uid, lines):
        """
        Remove useless fields
        """
        for line in lines:
            del line['move_lines']
            del line['import_invoice_id']
        res = super(account_invoice, self)._refund_cleanup_lines(cr, uid, lines)
        return res

    def button_debit_note_import_invoice(self, cr, uid, ids, context=None):
        """
        Launch wizard that permits to import invoice on a debit note
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all given invoices
        for inv in self.browse(cr, uid, ids):
            if inv.type != 'out_invoice' or inv.is_debit_note == False:
                raise osv.except_osv(_('Error'), _('You can only do import invoice on a Debit Note!'))
            w_id = self.pool.get('debit.note.import.invoice').create(cr, uid, {'invoice_id': inv.id, 'currency_id': inv.currency_id.id, 
                'partner_id': inv.partner_id.id})
            context.update({
                'active_id': inv.id,
                'active_ids': ids,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'debit.note.import.invoice',
                'name': 'Import invoice',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': w_id,
                'context': context,
                'target': 'new',
            }

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Copy global distribution and give it to new invoice
        """
        if not context:
            context = {}
        if default is None:
            default = {}
        default.update({'partner_move_line': False, 'imported_invoices': False})
        return super(account_invoice, self).copy(cr, uid, id, default, context)

    def finalize_invoice_move_lines(self, cr, uid, inv, line):
        """
        Hook that changes move line data before write them.
        Add a link between partner move line and invoice.
        """
        def is_partner_line(dico):
            if isinstance(dico, dict):
                if dico:
                    # In case where no amount_currency filled in, then take debit - credit for amount comparison
                    amount = dico.get('amount_currency', False) or (dico.get('debit', 0.0) - dico.get('credit', 0.0))
                    if amount == inv.amount_total and dico.get('partner_id', False) == inv.partner_id.id:
                        return True
            return False
        new_line = []
        for el in line:
            if el[2] and is_partner_line(el[2]):
                el[2].update({'invoice_partner_link': inv.id})
                new_line.append((el[0], el[1], el[2]))
            else:
                new_line.append(el)
        res = super(account_invoice, self).finalize_invoice_move_lines(cr, uid, inv, new_line)
        return res

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        """
        Add these field into invoice line:
        - invoice_line_id
        """
        if not context:
            context = {}
        res = super(account_invoice, self).line_get_convert(cr, uid, x, part, date, context)
        res.update({'invoice_line_id': x.get('invoice_line_id', False)})
        return res

    def action_reconcile_imported_invoice(self, cr, uid, ids, context=None):
        """
        Reconcile each imported invoice with its attached invoice line
        """
        # some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # browse all given invoices
        for inv in self.browse(cr, uid, ids):
            for invl in inv.invoice_line:
                if not invl.import_invoice_id:
                    continue
                imported_invoice = invl.import_invoice_id
                # reconcile partner line from import invoice with this invoice line attached move line
                import_invoice_partner_move_lines = self.pool.get('account.move.line').search(cr, uid, [('invoice_partner_link', '=', imported_invoice.id)])
                invl_move_lines = [x.id or None for x in invl.move_lines]
                rec = self.pool.get('account.move.line').reconcile_partial(cr, uid, [import_invoice_partner_move_lines[0], invl_move_lines[0]], 'auto', context=context)
                if not rec:
                    return False
        return True

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Launch reconciliation of imported invoice lines from a debit note invoice
        """
        # some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_invoice, self).action_open_invoice(cr, uid, ids, context, args)
        if res and not self.action_reconcile_imported_invoice(cr, uid, ids, context):
            res = False
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        """
        Rename Supplier/Customer to "Donor" if view_type == tree
        """
        if not context:
            context = {}
        res = super(account_invoice, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree' and (context.get('journal_type', False) == 'inkind' or context.get('journal_type', False) == 'intermission'):
            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//field[@name='partner_id']")
            name = _('Donor')
            if context.get('journal_type') == 'intermission':
                name = _('Partner')
            for node in nodes:
                node.set('string', name)
            res['arch'] = etree.tostring(doc)
        return res

    def action_cancel(self, cr, uid, ids, *args):
        """
        Reverse move if this object is a In-kind Donation. Otherwise do normal job: cancellation.
        """
        to_cancel = []
        for i in self.browse(cr, uid, ids):
            if i.is_inkind_donation:
                move_id = i.move_id.id
                tmp_res = self.pool.get('account.move').reverse(cr, uid, [move_id], strftime('%Y-%m-%d'))
                # If success change invoice to cancel and detach move_id
                if tmp_res:
                    self.write(cr, uid, [i.id], {'state': 'cancel', 'move_id':False})
                continue
            to_cancel.append(i.id)
        return super(account_invoice, self).action_cancel(cr, uid, to_cancel, args)

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
