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

import time

from tools.translate import _
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class account_partner_balance_tree(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(account_partner_balance_tree, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'lines': self.lines,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journal': self._get_journal,
            'get_filter': self._get_filter,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_target_move': self._get_target_move,
        })

    def set_context(self, objects, data, ids, report_type=None):
        self.display_partner = data['form'].get('display_partner', 'non-zero_balance')
        self.result_selection = data['form'].get('result_selection')
        self.target_move = data['form'].get('target_move', 'all')

        if (self.result_selection == 'customer' ):
            self.ACCOUNT_TYPE = ('receivable',)
        elif (self.result_selection == 'supplier'):
            self.ACCOUNT_TYPE = ('payable',)
        else:
            self.ACCOUNT_TYPE = ('payable', 'receivable')
            
        """
        # output currency
        self.output_currency_id = data['form']['output_currency']
        self.output_currency_code = ''
        if self.output_currency_id:
            ouput_cur_r = self.pool.get('res.currency').read(self.cr,
                                            self.uid,
                                            [self.output_currency_id],
                                            ['name'])
            if ouput_cur_r and ouput_cur_r[0] and ouput_cur_r[0]['name']:
                self.output_currency_code = ouput_cur_r[0]['name']
                
        # proprietary instances filter
        self.instance_ids = data['form']['instance_ids'] 
        if self.instance_ids:
            # we add instance filter in clauses 'self.query/self.init_query' 
            instance_ids_in = "l.instance_id in(%s)" % (",".join(map(str, self.instance_ids)))
            if not self.query:
                self.query = instance_ids_in
            else:
                self.query += ' AND ' + instance_ids_in
            if not self.init_query:
                self.init_query = instance_ids_in
            else:
                self.init_query += ' AND ' + instance_ids_in
        """

        return super(account_partner_balance_tree, self).set_context(objects, data, ids, report_type=report_type)

    def lines(self):
        return []

class account_partner_balance_tree_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_partner_balance_tree_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(account_partner_balance_tree_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
account_partner_balance_tree_xls('report.account.partner.balance.tree_xls', 'account.partner.balance.tree', 'account_partner_balance_tree_xls.mako', parser=account_partner_balance_tree, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
