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
import csv
from tempfile import TemporaryFile

class account_line_csv_export(osv.osv_memory):
    _name = 'account.line.csv.export'
    _description = 'Account Entries CSV Export'

    _columns = {
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }

    def _account_move_line_to_csv(self, cr, uid, ids, writer, currency_id, context=None):
        """
        Take account_move_line and return a csv string
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not writer:
            raise osv.except_osv(_('Error'), _('An error occured. Please contact an administrator to resolve this problem.'))
        # Prepare some value
        currency_name = ""
        if currency_id:
            currency_obj = self.pool.get('res.currency')
            currency_name = currency_obj.read(cr, uid, [currency_id], ['name'], context=context)[0].get('name', False)
        # Prepare csv head
        head = ['Proprietary Instance', 'Journal Code', 'Entry Sequence', 'Description', 'Reference', 'Posting Date', 'Document Date', 'Period', 'Account Code', 'Account Description', 'Third party', 
            'Book. Debit', 'Book. Credit', 'Book. currency']
        if not currency_id:
            head += ['Func. Debit', 'Func. Credit', 'Func. Currency']
        else:
            head += ['Output Debit', 'Output Credit', 'Output Currency']
        head += ['Reconcile', 'State']
        writer.writerow(head)
        # Sort items
        ids.sort()
        # Then write lines
        for ml in self.pool.get('account.move.line').browse(cr, uid, ids, context=context):
            csv_line = []
            #instance_id (Proprietary Instance)
            csv_line.append(ml.instance_id and ml.instance_id.code and ml.instance_id.code.encode('utf-8') or '')
            # journal_id
            csv_line.append(ml.journal_id and ml.journal_id.code and ml.journal_id.code.encode('utf-8') or '')
            #move_id (Entry Sequence)
            csv_line.append(ml.move_id and ml.move_id.name and ml.move_id.name.encode('utf-8') or '')
            #name
            csv_line.append(ml.name and ml.name.encode('utf-8') or '')
            #ref
            csv_line.append(ml.ref and ml.ref.encode('utf-8') or '')
            #date
            csv_line.append(ml.date or '')
            #document_date
            csv_line.append(ml.document_date or '')
            #period_id
            csv_line.append(ml.period_id and ml.period_id.name and ml.period_id.name.encode('utf-8') or '')
            #account_id code
            csv_line.append(ml.account_id and ml.account_id.code and ml.account_id.code.encode('utf-8') or '')
            #account_id name
            csv_line.append(ml.account_id and ml.account_id.name and ml.account_id.name.encode('utf-8') or '')
            #partner_txt
            csv_line.append(ml.partner_txt.encode('utf-8') or '')
            #debit_currency
            csv_line.append(ml.debit_currency or 0.0)
            #credit_currency
            csv_line.append(ml.credit_currency or 0.0)
            #currency_id
            csv_line.append(ml.currency_id and ml.currency_id.name and ml.currency_id.name.encode('utf-8') or '')
            if not currency_id:
                #debit
                csv_line.append(ml.debit or 0.0)
                #credit
                csv_line.append(ml.credit or 0.0)
                #functional_currency_id
                csv_line.append(ml.functional_currency_id and ml.functional_currency_id.name and ml.functional_currency_id.name.encode('utf-8') or '')
            else:
                #output amount (debit/credit) regarding booking currency
                amount = currency_obj.compute(cr, uid, ml.currency_id.id, currency_id, ml.amount_currency, round=True, context=context)
                if amount < 0.0:
                    csv_line.append(0.0)
                    csv_line.append(abs(amount) or 0.0)
                else:
                    csv_line.append(abs(amount) or 0.0)
                    csv_line.append(0.0)
                #output currency
                csv_line.append(currency_name.encode('utf-8') or '')
            #reconcile_total_partial_id
            csv_line.append(ml.reconcile_total_partial_id and ml.reconcile_total_partial_id.name and ml.reconcile_total_partial_id.name.encode('utf-8') or '')
            #state
            csv_line.append(ml.state.encode('utf-8') or '')
            # Write line
            writer.writerow(csv_line)
            
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
            #                res+= ustr(getattr(ml, field, ''))
            #            res+= '\n'
            #############################
        return True

    def _account_analytic_line_to_csv(self, cr, uid, ids, writer, currency_id, context=None):
        """
        Take account_analytic_line and return a csv string
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Is funding pool column needed?
        display_fp = context.get('display_fp', False)
        if not writer:
            raise osv.except_osv(_('Error'), _('An error occured. Please contact an administrator to resolve this problem.'))
        # Prepare some value
        currency_name = ""
        if currency_id:
            currency_obj = self.pool.get('res.currency')
            currency_name = currency_obj.read(cr, uid, [currency_id], ['name'], context=context)[0].get('name', False)
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        company_currency = user and user.company_id and user.company_id.currency_id and user.company_id.currency_id.name or ""
        # Prepare csv head
        head = ['Proprietary Instance', 'Journal Code', 'Entry Sequence', 'Description', 'Reference', 'Posting Date', 'Document Date', 
            'Period', 'General Account']
        if display_fp:
            head += ['Funding Pool', 'Cost Center']
        else:
            head += ['Analytic Account']
        head += ['Third Party', 'Book. Amount', 'Book. Currency', 'Func. Amount', 'Func. Currency']
        if currency_id:
            head += ['Output amount', 'Output currency']
        head+= ['Reversal Origin']
        writer.writerow(head)
        # Sort items
        ids.sort()
        # Then write lines
        for al in self.pool.get('account.analytic.line').browse(cr, uid, ids, context=context):
            csv_line = []
            #instance_id
            csv_line.append(al.instance_id and al.instance_id.code and al.instance_id.code.encode('utf-8') or '')
            # journal_id
            csv_line.append(al.journal_id and al.journal_id.code and al.journal_id.code.encode('utf-8') or '')
            #sequence
            csv_line.append(al.move_id and al.move_id.move_id and al.move_id.move_id.name and al.move_id.move_id.name.encode('utf-8') or '')
            #name (description)
            csv_line.append(al.name and al.name.encode('utf-8') or '')
            #ref
            csv_line.append(al.ref and al.ref.encode('utf-8') or '')
            #date
            csv_line.append(al.date or '')
            #document_date
            csv_line.append(al.document_date or '')
            #period
            csv_line.append(al.period_id and al.period_id.name and al.period_id.name.encode('utf-8') or '')
            #general_account_id (general account)
            csv_line.append(al.general_account_id and al.general_account_id.code and al.general_account_id.code.encode('utf-8') or '')
            #account_id name (analytic_account)
            csv_line.append(al.account_id and al.account_id.name and al.account_id.name.encode('utf-8') or '')
            if display_fp:
                #cost_center_id
                csv_line.append(al.cost_center_id and al.cost_center_id.name and al.cost_center_id.name.encode('utf-8') or '')
            #third party
            csv_line.append(al.partner_txt and al.partner_txt.encode('utf-8') or '')
            #amount_currency
            csv_line.append(al.amount_currency or 0.0)
            #currency_id
            csv_line.append(al.currency_id and al.currency_id.name and al.currency_id.name.encode('utf-8') or '')
            #amount
            csv_line.append(al.amount or 0.0)
            #company currency
            csv_line.append(company_currency.encode('utf-8') or '')
            if currency_id:
                #output amount
                amount = currency_obj.compute(cr, uid, al.currency_id.id, currency_id, al.amount_currency, round=True, context=context)
                csv_line.append(amount or 0.0)
                #output currency
                csv_line.append(currency_name.encode('utf-8') or '')
            csv_line.append(al.reversal_origin and al.reversal_origin.name and al.reversal_origin.name.encode('utf-8') or '')
            # Write Line
            writer.writerow(csv_line)
        return True

    def export_to_csv(self, cr, uid, ids, currency_id, model, context=None):
        """
        Return a CSV file containing all given line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not model:
            raise osv.except_osv(_('Error'), _('No model found.'))
        # Prepare some values
        today = strftime('%Y-%m-%d_%H-%M-%S')
        mtype = model.split('.')[1]
        name = '_'.join(['mcdb', mtype, 'result', today])
        ext = '.csv'
        filename = str(name + ext)
        
        outfile = TemporaryFile('w+')
        writer = csv.writer(outfile, quotechar='"', delimiter=',')
        
        # Take string regarding model
        if model == 'account.move.line':
            self._account_move_line_to_csv(cr, uid, ids, writer, currency_id, context=context) or ''
        elif model == 'account.analytic.line':
            self._account_analytic_line_to_csv(cr, uid, ids, writer, currency_id, context=context) or ''
        
        outfile.seek(0)
        file = encodestring(outfile.read())
        outfile.close()
        
        export_id = self.create(cr, uid, 
            {
                'file': file,
                'filename': filename,
                'message': "The list has been exported. Please click on 'Save As' button to download the file.",
        })
        
        # Search view
        suffix = 'csv_export_form'
        view = '_'.join([model.replace('.', '_'), suffix])
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_mcdb', view)
        view_id = view_id and view_id[1] or False
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.line.csv.export',
            'res_id': export_id,
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'target': 'new',
        }

account_line_csv_export()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
