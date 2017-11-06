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
import time


class cash_request(osv.osv):
    _name = 'cash.request'
    _description = 'Cash Request'

    _columns = {
        'name': fields.char(size=128, string='Name', readonly=True, required=True),
        'prop_instance_id': fields.many2one('msf.instance', 'Proprietary instance', readonly=True, required=True),
        'mission': fields.related('prop_instance_id', 'mission', string='Mission', type='char', store=False, readonly=True, required=True),
        'month_period_id': fields.many2one('account.period', 'Month', required=True, domain=[('date_stop', '>=', time.strftime('%Y-%m-%d')), ('special', '=', False)]),
        'request_date': fields.date('Request Date', required=True),
        'consolidation_currency_id': fields.many2one('res.currency', 'Consolidation Currency', required=True, readonly=True),
        'transfer_account_id': fields.many2one('account.account', 'Transfer Account Code', domain=[('type', '=', 'other'), ('user_type_code', '=', 'cash')]),
        'transfer_currency_ids': fields.one2many('transfer.currency', 'cash_request_id', 'Currency of Transfers', required=True),
        'bank_journal_id': fields.many2one('account.journal', 'Bank', required=True, domain=[('type', '=', 'bank')]),
        'state': fields.selection(
            [('draft', 'Draft'), ('validated', 'Validated'), ('done', 'Done')], 'State',
            required=True, readonly=True),
        'instance_ids': fields.many2many('msf.instance', 'cash_request_instance_rel', 'cash_request_id', 'instance_id',
                                         string='Mission Settings', readonly=True),
    }

    def _get_company(self, cr, uid, context=None):
        """
        Returns the company as a browse record
        """
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        company = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id
        return company

    def _get_prop_instance(self, cr, uid, context=None):
        """
        Returns the current instance as a browse_record if in coordo
        (= level where the Cash Request should always be created), else False
        """
        if context is None:
            context = {}
        company = self._get_company(cr, uid, context=context)
        if company.instance_id and company.instance_id.level == 'coordo':
            return company.instance_id
        return False

    def _get_prop_instance_id(self, cr, uid, context=None):
        """
        Returns the current instance_id if in coordo
        """
        if context is None:
            context = {}
        instance = self._get_prop_instance(cr, uid, context=context)
        return instance and instance.id or False

    def _get_mission(self, cr, uid, context=None):
        """
        Returns the value of Coordo Prop. instance Mission field
        """
        if context is None:
            context = {}
        instance = self._get_prop_instance(cr, uid, context=context)
        return instance and instance.mission or ''

    def _get_consolidation_currency_id(self, cr, uid, context=None):
        """
        Returns the id of the functional currency
        """
        if context is None:
            context = {}
        company = self._get_company(cr, uid, context=context)
        return company.currency_id.id

    def _get_instance_ids(self, cr, uid, context=None):
        """
        Returns the list of ids of the instances within the mission
        """
        if context is None:
            context = {}
        instance_ids = []
        instance_obj = self.pool.get('msf.instance')
        mission = self._get_mission(cr, uid, context=context)
        instance_ids.extend(instance_obj.search(cr, uid, [('mission', '=', mission), ('level', '!=', 'section')],
                                                order='level, code', context=context))
        return instance_ids

    _defaults = {
        'request_date': lambda *a: datetime.today(),
        'prop_instance_id': _get_prop_instance_id,
        'mission': _get_mission,
        'consolidation_currency_id': _get_consolidation_currency_id,
        'state': 'draft',
    }

    _order = 'request_date desc'

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every Cash Request
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')
        name = 'Cash Request'
        code = 'cash.request'
        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)
        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 4,
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        """
        Creates the Cash Request and automatically fills in the values for the following fields:
        name, instance_ids
        """
        if context is None:
            context = {}
        # build the Cash Request name (Mission code_Cash_request-X)
        mission = self._get_mission(cr, uid, context)
        self.create_sequence(cr, uid, vals, context=context)
        seq = self.pool.get('ir.sequence').get(cr, uid, 'cash.request')
        name = mission and seq and "%s_Cash_request - %s" % (mission, seq) or ""
        vals.update({'name': name})
        # fill in the list of Prop. Instances
        vals.update({'instance_ids': [(6, 0, self._get_instance_ids(cr, uid, context=context))]})
        return super(cash_request, self).create(cr, uid, vals, context=context)


cash_request()


class transfer_currency(osv.osv):
    _name = 'transfer.currency'
    _rec_name = 'currency_id'
    _description = 'Currency of Transfers for a Cash Request'

    _columns = {
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'percentage': fields.float(digits=(16, 2), string='%'),
        'cash_request_id': fields.many2one('cash.request', 'Cash Request', invisible=True, ondelete='cascade'),
    }


transfer_currency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
