#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from base64 import encodestring
from time import strftime
from tools import ustr

class account_move_line_csv_export(osv.osv_memory):
    _name = 'account.move.line.csv.export'
    _description = 'Account Entries CSV Export'

    _columns = {
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }

    def _account_move_line_to_csv(self, cr, uid, ids, currency_id, context={}):
        """
        Take account_move_line and return a csv string
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not currency_id:
            raise osv.except_osv(_('Error'), _('No currency. Please choose one.'))
        # Prepare some value
        string = ""
        currency_obj = self.pool.get('res.currency')
        currency_name = currency_obj.read(cr, uid, [currency_id], ['name'], context=context)[0].get('name', False)
        # String creation
        # Prepare csv head
        string += "Journal Code;Sequence;Instance;Reference;Posting date;Period;Name;Account Code;Account Description;Third party;Book. Debit;Book. Credit;Book. currency;Func. Debit;"
        string += "Func. Credit;Func. currency;Output amount;Output currency;State;Reconcile\n"
        for ml in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            # journal_id
            string += ustr(ml.journal_id and ml.journal_id.code or '')
            #move_id
            string += ';' + ustr(ml.move_id and ml.move_id.name or '')
            #instance
            string += ';' + ustr(ml.instance or '')
            #ref
            string += ';' + ustr(ml.ref or '')
            #date
            string += ';' + ustr(ml.date or '')
            #period_id
            string += ';' + ustr(ml.period_id and ml.period_id.name or '')
            #name
            string += ';' + ustr(ml.name or '')
            #account_id code
            string += ';' + ustr(ml.account_id and ml.account_id.code or '')
            #account_id name
            string += ';' + ustr(ml.account_id and ml.account_id.name or '')
            #partner_txt
            string += ';' + ustr(ml.partner_txt or '')
            #debit_currency
            string += ';' + ustr(ml.debit_currency or 0.0)
            #credit_currency
            string += ';' + ustr(ml.credit_currency or 0.0)
            #currency_id
            string += ';' + ustr(ml.currency_id and ml.currency_id.name or '')
            #debit
            string += ';' + ustr(ml.debit or 0.0)
            #credit
            string += ';' + ustr(ml.credit or 0.0)
            #functional_currency_id
            string += ';' + ustr(ml.functional_currency_id and ml.functional_currency_id.name or '')
            #output amount regarding booking currency
            amount = currency_obj.compute(cr, uid, currency_id, ml.currency_id.id, ml.amount_currency, round=True, context=context)
            string += ';' + ustr(amount or 0.0)
            #output currency
            string += ';' + ustr(currency_name or '')
            #state
            string += ';' + ustr(ml.state or '')
            #reconcile_total_partial_id
            string += ';' + ustr(ml.reconcile_total_partial_id and ml.reconcile_total_partial_id.name or '')
            # EOL
            string += '\n'
            #############################
            ###
            # This function could be used with a fields parameter in this method in order to create a CSV with field that could change
            ###
            #        for i, field in enumerate(fields):
            #            if i != 0:
            #                res += ';'
            #            res += str(field)
            #        res+= '\n'
            #        for ml in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            #            for i, field in enumerate(fields):
            #                if i != 0:
            #                    res += ';'
            #                print field
            #                res+= ustr(getattr(ml, field, ''))
            #            res+= '\n'
            #############################
        return ustr(string)

    def export_to_csv(self, cr, uid, ids, context={}):
        """
        Return a CSV file containing all given move line
        """
        # Some verifications
        if not context or not context.get('active_ids', False) or not context.get('output_currency_id', False):
            raise osv.except_osv(_('Error'), _('No entry selected or no currency given!'))
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        ml_ids = context.get('active_ids')
        currency_id = context.get('output_currency_id')
        today = strftime('%Y-%m-%d_%H-%M-%S')
        name = 'mcdb_result' + '_' + today
        ext = '.csv'
        filename = str(name + ext)
        
        string = self._account_move_line_to_csv(cr, uid, ml_ids, currency_id, context=context) or ''
        
        # String unicode tranformation then to file
        file = encodestring(string.encode("utf-8"))
        
        export_id = self.create(cr, uid, 
            {
                'file': file,
                'filename': filename,
                'message': "The list has been exported. Please click on 'Save As' button to download the file.",
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line.csv.export',
            'res_id': export_id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }

account_move_line_csv_export()


class account_analytic_line_csv_export(osv.osv_memory):
    _name = 'account.analytic.line.csv.export'
    _description = 'Account Analytic Lines CSV Export'

    _columns = {
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }

    def _account_analytic_line_to_csv(self, cr, uid, ids, context={}):
        """
        Take account_analytic_line and return a csv string
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not fields:
            raise osv.except_osv(_('Error'), _('No export fields. Please add them to the code.'))
        # Prepare some value
        string = ""
        # String creation
        # Prepare csv head
        string += "Journal Code;Date;Instance;Description;Reference;Amount;Amount currency;Currency;Analytic Account\n"
        for al in self.pool.get('account.analytic.line').browse(cr, uid, ids, context=context):
            # journal_id
            string += ustr(al.journal_id and al.journal_id.code or '')
            #date
            string += ';' + ustr(al.date or '')
            #instance
            string += ';' + ustr(al.company_id and al.company_id.name or '')
            #name
            string += ';' + ustr(al.name or '')
            #ref
            string += ';' + ustr(al.ref or '')
            #amount
            string += ';' + ustr(al.amount or 0.0)
            #amount_currency
            string += ';' + ustr(al.amount_currency or 0.0)
            #currency_id
            string += ';' + ustr(al.currency_id and al.currency_id.name or '')
            #account_id name
            string += ';' + ustr(al.account_id and al.account_id.name or '')
            # EOL
            string += '\n'
            #############################
            ###
            # This function could be used with a fields parameter in this method in order to create a CSV with field that could change
            ###
            #        for i, field in enumerate(fields):
            #            if i != 0:
            #                res += ';'
            #            res += str(field)
            #        res+= '\n'
            #        for ml in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            #            for i, field in enumerate(fields):
            #                if i != 0:
            #                    res += ';'
            #                print field
            #                res+= ustr(getattr(ml, field, ''))
            #            res+= '\n'
            #############################
        return ustr(string)

    def export_to_csv(self, cr, uid, ids, context={}):
        """
        Return a CSV file containing all given analytic line
        """
        # Some verifications
        if not context or not context.get('active_ids', False):
            raise osv.except_osv(_('Error'), _('No entry selected!'))
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        ml_ids = context.get('active_ids')
        today = strftime('%Y-%m-%d_%H-%M-%S')
        name = 'mcdb_analytic_result' + '_' + today
        ext = '.csv'
        filename = str(name + ext)
        
        string = self._account_analytic_line_to_csv(cr, uid, ml_ids, context=context) or ''
        
        # String unicode tranformation then to file
        file = encodestring(string.encode("utf-8"))
        
        export_id = self.create(cr, uid, 
            {
                'file': file,
                'filename': filename,
                'message': "The list has been exported. Please click on 'Save As' button to download the file.",
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line.csv.export',
            'res_id': export_id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }

account_analytic_line_csv_export()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
