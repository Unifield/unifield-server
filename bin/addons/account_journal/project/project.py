#!/usr/bin/env python
#-*- encoding:utf-8 -*-

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

class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _description = 'Analytic Journal'
    _inherit = 'account.analytic.journal'

    def get_journal_type(self, cr, uid, context=None):
        """
        Get all analytic journal type
        """
        return [
            ('cash','Cash'),
            ('correction', 'Correction Auto'),
            ('correction_hq', 'Correction HQ'),
            ('correction_manual', 'Correction Manual'),
            ('cur_adj', 'Currency Adjustment'),
            ('engagement', 'Engagement'),
            ('general', 'Accrual'),  # US-8023: the old type "General" was in fact used for Accruals only
            ('hq', 'HQ'),
            ('hr', 'HR'),
            ('inkind', 'In-kind Donation'),
            ('intermission', 'Intermission'),
            ('migration', 'Migration'),
            ('extra', 'OD-Extra Accounting'),
            ('purchase','Purchase'),
            ('revaluation', 'Revaluation'),
            ('sale','Sale'),
            ('situation','Situation'),
            ('depreciation', 'Depreciation'),
        ]

    def _get_has_ajis(self, cr, uid, ids, field_name, arg, context=None):
        """
        Returns a dict with key = analytic_journal_id,
        and value = True if at least one AJI is booked on the journal, or False otherwise.
        """
        res = {}
        if not ids:
            return res
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        aal_obj = self.pool.get('account.analytic.line')
        for journal_id in ids:
            res[journal_id] = aal_obj.search_exist(cr, uid, [('journal_id', '=', journal_id)], context=context) or False
        return res

    _columns = {
        'type': fields.selection(get_journal_type, 'Type', size=32, required=True, help="Gives the type of the analytic journal. When it needs for a document \
(eg: an invoice) to create analytic entries, OpenERP will look for a matching journal of the same type."),
        'code': fields.char('Journal Code', size=8, required=True),
        'has_ajis': fields.function(_get_has_ajis, type='boolean', method=True, string='Has Analytic Journal Items', store=False),
    }

    _defaults = {
        'type': lambda *a: 'purchase',
    }

    def name_get(self, cr, user, ids, context=None):
        """
        Get code for Journals
        """
        result = self.read(cr, user, ids, ['code'])
        res = []
        for rs in result:
            txt = rs.get('code', '')
            res += [(rs.get('id'), txt)]
        return res

    def copy(self, cr, uid, journal_id, default=None, context=None):
        """
        Analytic journal duplication: don't copy the link with analytic lines
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'line_ids': [],
        })
        return super(account_analytic_journal, self).copy(cr, uid, journal_id, default, context=context)

    def _check_code_duplication(self, cr, uid, vals, current_id=None, context=None):
        """
        Raises a warning if the Analytic Journal Code is already in use in the current instance.
        This check is not done during the synchronization process where we can receive journals from other instances.
        """
        if context is None:
            context = {}
        if vals.get('code') and not context.get('sync_update_execution'):
            journal_domain = [('code', '=ilike', vals['code']), ('is_current_instance', '=', True)]
            if current_id:
                # exclude the current journal being modified
                journal_domain.append(('id', '!=', current_id))
            if self.search_exist(cr, uid, journal_domain, context=context):
                raise osv.except_osv(_('Warning'),
                                     _('An analytic journal with the code %s already exists in the current instance.') % vals['code'].upper())

    def _adapt_od_type(self, cr, uid, vals, context):
        """
        For corr. journals created before US-6692: at the first synchro ONLY, related to Master Data, if an analytic
        journal other than OD has the type "Correction Auto", change it to "Correction Manual".
        """
        if context and vals and context.get('sync_update_execution') and \
                not bool(self.pool.get('res.users').get_browse_user_instance(cr, uid)):
            if vals.get('type', '') == 'correction' and vals.get('code', '') != 'OD':
                vals.update({'type': 'correction_manual'})
        return True

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        self._check_code_duplication(cr, uid, vals, context=context)
        if 'instance_id' not in vals:
            # Prop. instance by default at creation time is the current one: add it in vals to make it appear in the Track Changes
            vals['instance_id'] = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.instance_id.id
        self._adapt_od_type(cr, uid, vals, context)
        return super(account_analytic_journal, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        for journal_id in self.browse(cr, uid, ids, fields_to_fetch=['is_current_instance'], context=context):
            if not journal_id.is_current_instance and not context.get('sync_update_execution'):
                raise osv.except_osv(_('Warning'), _("You can't edit an Analytic Journal that doesn't belong to the current instance."))
            self._check_code_duplication(cr, uid, vals, current_id=journal_id.id, context=context)
        self._adapt_od_type(cr, uid, vals, context)
        return super(account_analytic_journal, self).write(cr, uid, ids, vals, context=context)

account_analytic_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
