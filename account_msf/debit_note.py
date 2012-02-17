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
    }

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
            ('journal_id.type', 'in', ['sale']) 
        ]
        return dom1+[('is_debit_note', '=', False)]

    _columns = {
        'is_debit_note': fields.boolean(string="Is a Debit Note?"),
        'ready_for_import_in_debit_note': fields.function(_get_fake, fnct_search=_search_ready_for_import_in_debit_note, type="boolean", 
            method=True, string="Can be imported as invoice in a debit note?",),
        'imported_invoices': fields.one2many('account.invoice.line', 'import_invoice_id', string="Imported invoices", readonly=True),
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
            w_id = self.pool.get('debit.note.import.invoice').create(cr, uid, {'invoice_id': inv.id, 'currency_id': inv.currency_id.id})
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

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
