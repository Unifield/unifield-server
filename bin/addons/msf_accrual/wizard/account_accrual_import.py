#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rights Reserved
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
from tempfile import NamedTemporaryFile
from base64 import b64decode
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from account.report import export_invoice
from datetime import datetime
import threading
import pooler
import logging
import tools


class account_accrual_import(osv.osv_memory):
    _name = 'account.accrual.import'

    _columns = {
        'file': fields.binary(string="File", filters='*.xls*', required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'progression': fields.float(string="Progression", readonly=True),
        'message': fields.char(string="Message", size=256, readonly=True),
        'state': fields.selection([('draft', 'Created'), ('inprogress', 'In Progress'), ('error', 'Error'), ('ad_error', 'AD Error'), ('done', 'Done')],
                                  string="State", readonly=True, required=True),
        'error_ids': fields.one2many('account.accrual.import.errors', 'wizard_id', "Errors", readonly=True),
        'accrual_id': fields.many2one('account.accrual.line', 'Accrual Line', required=True, readonly=True),
    }

    _defaults = {
        'progression': lambda *a: 0.0,
        'state': lambda *a: 'draft',
    }

    def create(self, cr, uid, vals, context=None):
        """
        Creation of the wizard using the realUid to allow the process for the non-admin users
        """
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        return super(account_accrual_import, self).create(cr, real_uid, vals, context=context)

    def _check_col_length(self, percent_col, cc_col, dest_col, fp_col, line_num, errors):
        return self.pool.get('account.invoice.import')._check_col_length(percent_col, cc_col, dest_col, fp_col, line_num, errors)

    def _check_percent_values(self, percent_col, line_num, errors):
        '''
        Check if the Percent Column values adds up to exactly 100
        '''
        return self.pool.get('account.invoice.import')._check_percent_values(percent_col, line_num, errors)

    def _is_ad_diff(self, current_ad, cc_ids, dest_ids, fp_ids, percentages):
        return self.pool.get('account.invoice.import')._is_ad_diff(current_ad, cc_ids, dest_ids, fp_ids, percentages)

    def _import(self, dbname, uid, ids, context=None):
        """
        Checks file data, and either updates the lines or displays the errors found
        """
        if context is None:
            context = {}
        return True

    def button_validate(self, cr, uid, ids, context=None):
        """
        Starts thread and returns the wizard with the state "inprogress"
        """
        if context is None:
            context = {}
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        self.write(cr, uid, ids, {'state': 'inprogress'}, context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.accrual.import',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'context': context,
            'target': 'new',
        }

    def button_update(self, cr, uid, ids, context=None):
        """
        Updates the view to follow the progression
        """
        return False

    def button_refresh_accrual(self, cr, uid, ids, context=None):
        """
        Closes the wizard and refreshes the accrual view
        """
        return {'type': 'ir.actions.act_window_close'}

    def export_template_file(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        return {'type': 'ir.actions.report.xml', 'report_name': 'accrual_import_template_xlsx', 'context': context}


account_accrual_import()


class account_accrual_import_errors(osv.osv_memory):
    _name = 'account.accrual.import.errors'

    _columns = {
        'name': fields.text("Description", readonly=True, required=True),
        'wizard_id': fields.many2one('account.accrual.import', "Wizard", required=True, readonly=True),
    }


account_accrual_import_errors()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
