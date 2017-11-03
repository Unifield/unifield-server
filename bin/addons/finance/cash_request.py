#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 TeMPO Consulting, MSF. All Rights Reserved
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
from datetime import datetime


class cash_request(osv.osv):
    _name = 'cash.request'
    _description = 'Cash Request'

    _columns = {
        'name': fields.char(size=128, string='Name', readonly=True, required=True),
        'prop_instance_id': fields.many2one('msf.instance', 'Proprietary instance', readonly=True, required=True),
        'mission': fields.related('prop_instance_id', 'mission', string='Mission', type='char', store=False, readonly=True),
        'month_period_id': fields.many2one('account.period', 'Month', required=True),
        'request_date': fields.date('Request Date', required=True),
        'consolidation_currency_id': fields.many2one('res.currency', 'Consolidation Currency', required=True, readonly=True),
        'transfer_account_id': fields.many2one('account.account', 'Transfer Account Code'),
        'bank_journal_id': fields.many2one('account.journal', 'Bank', required=True),
    }

    _defaults = {
        'request_date': lambda *a: datetime.today(),
    }

    _order = 'request_date'


cash_request()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
