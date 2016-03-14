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

class debit_note_import_invoice(osv.osv_memory):
    _name = 'debit.note.import.invoice'
    _description = 'Debit Note Import Invoice'

    _columns = {
        'invoice_id': fields.many2one('account.invoice', string='', required=True, readonly=True),
        'line_ids': fields.many2many('account.invoice', 'debit_note_import_invoice', 'wizard_id', 'invoice_id', string="Invoices"),
        'currency_id': fields.many2one('res.currency', required=True, readonly=True),
        'partner_id': fields.many2one('res.partner', required=True, readonly=True),
    }

    def button_validate(self, cr, uid, ids, context=None):
        """
        Check elements and write them to the given invoice (invoice_id field)
        """
        # some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # browse all wizard
        for w in self.browse(cr, uid, ids):
            if not w.line_ids:
                raise osv.except_osv(_('Warning'), _('Please add some invoices!'))
            # add lines to given invoice
            for line in w.line_ids:
                self.pool.get('account.invoice.line').create(cr, uid, {
                    'name': line.name or '',
                    'quantity': 1.0,
                    'account_id': line.account_id and line.account_id.id,
                    'price_unit': line.amount_total,
                    'invoice_id': w.invoice_id and w.invoice_id.id,
                    'partner_id': line.partner_id and line.partner_id.id,
                    'company_id': line.company_id and line.company_id.id or False,
                    'import_invoice_id': line.id,
                })
        return {'type': 'ir.actions.act_window_close', }

debit_note_import_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
