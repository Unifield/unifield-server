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
from tools.translate import _
import logging
import time


class account_invoice_sync(osv.osv):
    _inherit = 'account.invoice'
    _logger = logging.getLogger('------sync.account.invoice')

    _columns = {
        'synced': fields.boolean("Synchronized document"),
    }

    _defaults = {
        'synced': lambda *a: False,
    }

    def create_invoice_from_sync(self, cr, uid, source, invoice_data, context=None):
        """
        Creates automatic counterpart invoice at synchro time.
        Intermission workflow: an IVO sent generates an IVI
        Intersection workflow: an STV sent generates an SI
        """
        self._logger.info("+++ Create an account.invoice in %s matching the one sent by %s" % (cr.dbname, source))
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        currency_obj = self.pool.get('res.currency')
        partner_obj = self.pool.get('res.partner')
        invoice_dict = invoice_data.to_dict()
        # the counterpart instance must exist and be active
        partner_ids = partner_obj.search(cr, uid, [('name', '=', source), ('active', '=', True)], limit=1, context=context)
        if not partner_ids:
            raise osv.except_osv(_('Error'), _("The partner %s doesn't exist or is inactive.") % source)
        partner_id = partner_ids[0]
        partner = partner_obj.browse(cr, uid, partner_ids[0], fields_to_fetch=['property_account_payable'], context=context)
        account_id = partner.property_account_payable and partner.property_account_payable.id
        if not account_id:
            raise osv.except_osv(_('Error'), _("Impossible to retrieve the account code."))
        journal_type = invoice_dict.get('journal_id', {}).get('type', '')
        if not journal_type or journal_type not in ('sale', 'intermission'):
            raise osv.except_osv(_('Error'), _("Impossible to retrieve the journal type, or the journal type found is incorrect."))
        currency_name = invoice_dict.get('currency_id', {}).get('name', '')
        if not currency_name:
            raise osv.except_osv(_('Error'), _("Impossible to retrieve the currency."))
        currency_ids = currency_obj.search(cr, uid, [('name', '=', currency_name), ('currency_table_id', '=', False)], limit=1, context=context)
        if not currency_ids:
            raise osv.except_osv(_('Error'), _("Currency %s not found.") % currency_name)
        currency_id = currency_ids[0]
        number = invoice_dict.get('number', '')
        doc_date = invoice_dict.get('document_date', time.strftime('%Y-%m-%d'))
        posting_date = invoice_dict.get('date_invoice', time.strftime('%Y-%m-%d'))
        description = invoice_dict.get('name', '')
        source_doc = invoice_dict.get('origin', '')
        inv_lines = invoice_dict.get('invoice_line', [])
        vals = {}
        if journal_type == 'sale':
            # STV in sending instance should generate an SI in the receiving instance
            pur_journal_ids = journal_obj.search(cr, uid, [('type', '=', 'purchase'), ('is_current_instance', '=', True)], limit=1, context=context)
            if not pur_journal_ids:
                raise osv.except_osv(_('Error'), _("No Purchase Journal found for the current instance."))
            vals.update(
                {
                    'journal_id': pur_journal_ids[0],
                    'type': 'in_invoice',
                    'is_direct_invoice': False,
                    'is_inkind_donation': False,
                    'is_debit_note': False,
                    'is_intermission': False,
                }
            )
        elif journal_type == 'intermission':
            # IVO in sending instance should generate an IVI in the receiving instance
            int_journal_ids = journal_obj.search(cr, uid, [('type', '=', 'intermission'), ('is_current_instance', '=', True)], limit=1, context=context)
            if not int_journal_ids:
                raise osv.except_osv(_('Error'), _("No Intermission Journal found for the current instance."))
            vals.update(
                {
                    'journal_id': int_journal_ids[0],
                    'type': 'in_invoice',
                    'is_inkind_donation': False,
                    'is_debit_note': False,
                    'is_intermission': True,
                }
            )
        vals.update(
            {
                'partner_id': partner_id,
                'currency_id': currency_id,
                'account_id': account_id,
                'document_date': doc_date,
                'date_invoice': posting_date,
            }
        )
        inv_id = self.create(cr, uid, vals, context=context)
        if inv_id and journal_type == 'sale':
            self._logger.info("SI No. %s created successfully." % inv_id)
        elif inv_id and journal_type == 'intermission':
            self._logger.info("IVI No. %s created successfully." % inv_id)


account_invoice_sync()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
