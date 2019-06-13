#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2019 TeMPO Consulting, MSF. All Rights Reserved
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
import logging
import time


class account_invoice_sync(osv.osv):
    _inherit = 'account.invoice'
    _logger = logging.getLogger('------sync.account.invoice')

    _columns = {
        'synced': fields.boolean("Sent or received via synchro"),
    }

    _defaults = {
        'synced': lambda *a: False,
    }

    def create_invoice_from_sync(self, cr, uid, source, invoice_data, context=None):
        self._logger.info("+++ Create an account.invoice at %s matching the one sent by %s" % (cr.dbname, source))
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        currency_obj = self.pool.get('res.currency')
        partner_obj = self.pool.get('res.partner')
        invoice_dict = invoice_data.to_dict()
        number = invoice_dict.get('number', '')
        doc_date = invoice_dict.get('document_date', time.strftime('%Y-%m-%d'))
        posting_date = invoice_dict.get('date_invoice', time.strftime('%Y-%m-%d'))
        journal_type = invoice_dict.get('journal_id', {}).get('type', '')
        currency_name = invoice_dict.get('currency_id', {}).get('name', '')
        description = invoice_dict.get('name', '')
        source_doc = invoice_dict.get('origin', '')
        inv_lines = invoice_dict.get('invoice_line', [])
        journal_ids = []
        if journal_type == 'sale':
            journal_ids = journal_obj.search(cr, uid, [('type', '=', 'purchase'), ('is_current_instance', '=', True)], limit=1, context=context)
        elif journal_type == 'intermission':
            journal_ids = journal_obj.search(cr, uid, [('type', '=', 'intermission'), ('is_current_instance', '=', True)], limit=1, context=context)
        currency_ids = currency_obj.search(cr, uid, [('name', '=', currency_name), ('currency_table_id', '=', False)], limit=1, context=context)
        partner_ids = partner_obj.search(cr, uid, [('name', '=', source)], limit=1, context=context)
        partner = partner_obj.browse(cr, uid, partner_ids[0], fields_to_fetch=['property_account_payable'], context=context)
        account_id = partner.property_account_payable.id
        vals = {
            'journal_id': journal_ids[0],
            'partner_id': partner_ids[0],
            'currency_id': currency_ids[0],
            'account_id': account_id,
        }
        if journal_type == 'sale':
            vals.update(
                {
                    'type': 'in_invoice',
                    'is_direct_invoice': False,
                    'is_inkind_donation': False,
                    'is_debit_note': False,
                    'is_intermission': False,
                }
            )
        self.create(cr, uid, vals, context=context)


account_invoice_sync()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
