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

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'import_invoice_id': fields.many2one('account.invoice', string="From an import invoice", readonly=True),
        'move_lines': fields.one2many('account.move.line', 'invoice_line_id', string="Journal Item", readonly=True),
    }

    def move_line_get_item(self, cr, uid, line, context={}):
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

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Fake method for 'ready_for_import_in_debit_note' field
        """
        res = {}
        for id in ids:
            res[id] = False
        return res

    def _search_ready_for_import_in_debit_note(self, cr, uid, obj, name, args, context={}):
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

    _columns = {
        'is_debit_note': fields.boolean(string="Is a Debit Note?"),
        'ready_for_import_in_debit_note': fields.function(_get_fake, fnct_search=_search_ready_for_import_in_debit_note, type="boolean", 
            method=True, string="Can be imported as invoice in a debit note?",),
        'imported_invoices': fields.one2many('account.invoice.line', 'import_invoice_id', string="Imported invoices", readonly=True),
        'partner_move_line': fields.one2many('account.move.line', 'invoice_partner_link', string="Partner move line", readonly=True),
    }

    _defaults = {
        'is_debit_note': lambda obj, cr, uid, c: c.get('is_debit_note', False),
    }

    def button_debit_note_import_invoice(self, cr, uid, ids, context={}):
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

    def copy(self, cr, uid, id, default={}, context={}):
        """
        Copy global distribution and give it to new invoice
        """
        if not context:
            context = {}
        default.update({'partner_move_line': False})
        return super(account_invoice, self).copy(cr, uid, id, default, context)

    def finalize_invoice_move_lines(self, cr, uid, inv, line):
        """
        Hook that changes move line data before write them.
        Add a link between partner move line and invoice.
        """
        def is_partner_line(dico):
            if isinstance(dico, dict):
                if dico:
                    amount = dico.get('debit', 0.0) - dico.get('credit', 0.0)
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

    def line_get_convert(self, cr, uid, x, part, date, context={}):
        """
        Add these field into invoice line:
        - invoice_line_id
        """
        if not context:
            context = {}
        res = super(account_invoice, self).line_get_convert(cr, uid, x, part, date, context)
        res.update({'invoice_line_id': x.get('invoice_line_id', False)})
        return res

    def action_reconcile_imported_invoice(self, cr, uid, ids, context={}):
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

    def action_open_invoice(self, cr, uid, ids, context={}, *args):
        """
        Launch reconciliation of imported invoice lines from a debit note invoice
        """
        # some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_invoice, self).action_open_invoice(cr, uid, ids, context, args)
        if res and self.action_reconcile_imported_invoice(cr, uid, ids, context):
            return True
        return False

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
