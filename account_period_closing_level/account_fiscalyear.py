#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import fields, osv
from tools.translate import _
import datetime
from dateutil.relativedelta import relativedelta
from account_period_closing_level import ACCOUNT_FY_STATE_SELECTION


class account_fiscalyear(osv.osv):
    _name = "account.fiscalyear"
    _inherit = "account.fiscalyear"

    def _get_is_closable(self, cr, uid, ids, field_names, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]

        level = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.instance_id.level
        ayec_obj = self.pool.get('account.year.end.closing')

        # check matching of:
        # - instance level
        # - FY state
        # - periods, with special ones too except those for year end closing
        for fy in self.browse(cr, uid, ids, context=context):
            # check previous FY closed
            # check next FY exists (we need FY+1 Period 0 for initial balances)
            mission = False
            hq = False

            prev_fy_id = ayec_obj._get_next_fy_id(cr, uid, fy,
                get_previous=True, context=context)
            if prev_fy_id:
                prev_fy = self.browse(cr, uid, prev_fy_id, context=context)
                prev_fy_ok = False
                if level == 'coordo':
                    prev_fy_ok = prev_fy.state in ('mission-closed', 'done', )
                elif level == 'section':
                    prev_fy_ok = prev_fy.state in ('done', )
            else:
                prev_fy_ok = True

            if prev_fy_ok:
                mission = level == 'coordo' and fy.state == 'draft' \
                    and all([ p.state in ('mission-closed', 'done') \
                        for p in fy.period_ids if 0 < p.number < 16 ]) \
                    or False
                hq = level == 'section' and fy.state in ('draft', 'mission-closed') \
                    and all([ p.state == 'done' \
                        for p in fy.period_ids if 0 < p.number < 16 ]) \
                    or False

            res[fy.id] = {
                'is_mission_closable': mission,
                'is_hq_closable': hq,
                'can_reopen_mission': level == 'coordo' \
                    and fy.state == 'mission-closed' or False,
            }
        return res

    _columns = {
        'state': fields.selection(ACCOUNT_FY_STATE_SELECTION, 'State',
            readonly=True),
        'is_mission_closable': fields.function(_get_is_closable, type='boolean',
            method=True, multi="closable",
            string='Mission Closable ? (all periods Mission closed)'),
        'is_hq_closable': fields.function(_get_is_closable, type='boolean',
            method=True, multi="closable",
            string='HQ Closable ? (all periods HQ closed)'),
        'can_reopen_mission': fields.function(_get_is_closable, type='boolean',
            method=True, multi="closable",
            string='Mission reopen available ?'),
    }

    _defaults = {
        'is_mission_closable': False,
        'is_hq_closable': False,
        'can_reopen_mission': False,
    }

    def create_period(self,cr, uid, ids, context=None, interval=1):
        for fy in self.browse(cr, uid, ids, context=context):
            ds = datetime.datetime.strptime(fy.date_start, '%Y-%m-%d')
            i = 0
            while ds.strftime('%Y-%m-%d')<fy.date_stop:
                i += 1
                de = ds + relativedelta(months=interval, days=-1)

                if de.strftime('%Y-%m-%d')>fy.date_stop:
                    de = datetime.datetime.strptime(fy.date_stop, '%Y-%m-%d')

                self.pool.get('account.period').create(cr, uid, {
                    'name': ds.strftime('%b %Y'),
                    'code': ds.strftime('%b %Y'),
                    'date_start': ds.strftime('%Y-%m-%d'),
                    'date_stop': de.strftime('%Y-%m-%d'),
                    'fiscalyear_id': fy.id,
                    'special': False,
                    'number': i,
                })
                ds = ds + relativedelta(months=interval)

            ds = datetime.datetime.strptime(fy.date_stop, '%Y-%m-%d')
            for period_nb in (13, 14, 15):
                self.pool.get('account.period').create(cr, uid, {
                    'name': 'Period %d' % (period_nb),
                    'code': 'Period %d' % (period_nb),
                    'date_start': '%d-12-01' % (ds.year),
                    'date_stop': '%d-12-31' % (ds.year),
                    'fiscalyear_id': fy.id,
                    'special': True,
                    'number': period_nb,
                })
        return True

    def create(self, cr, uid, vals, context=None):
        """
        When creating new fiscalyear, we should add a new sequence for each journal. This is to have the right sequence number on journal items lines, etc.
        """
        # Check some elements
        if context is None:
            context = {}
        # First default behaviour
        res = super(account_fiscalyear, self).create(cr, uid, vals, context=context)

        # update fiscalyear state
        self.pool.get('account.fiscalyear.state').update_state(cr, uid, [res],
            context=context)

        # Prepare some values
        current_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        name = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.name
        # Then sequence creation on all journals
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('instance_id', '=', current_instance_id)])
        for journal in self.pool.get('account.journal').browse(cr, uid, journal_ids, context=context):
            self.pool.get('account.journal').create_fiscalyear_sequence(cr, uid, res, name, "journal_%s"%(journal.id), vals['date_start'], journal.sequence_id and journal.sequence_id.id or False, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return False
        if isinstance(ids, (int, long, )):
            ids = [ids]
        if context is None:
            context = {}

        res = super(account_fiscalyear, self).write(cr, uid, ids, vals,
            context=context)

        # update fiscalyear state
        self.pool.get('account.fiscalyear.state').update_state(cr, uid, ids,
            context=context)

        return res

    def _close_fy(self, cr, uid, ids, context=None):
        res = {}
        if not ids:
            return res
        if context is None:
            context = {}
        fy_id = ids[0]  # active form's FY

        # open year end wizard
        context['fy_id'] = fy_id
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid,
            'account_period_closing_level',
            'wizard_view_account_year_end_closing')[1]
        return {
			'name': 'Close the fiscal year',
			'type': 'ir.actions.act_window',
			'res_model': 'wizard.account.year.end.closing',
			'view_type': 'form',
			'view_mode': 'form',
            'view_id': [view_id],
			'target': 'new',
			'context': context,
        }

    def btn_mission_close(self, cr, uid, ids, context=None):
        return self._close_fy(cr, uid, ids, context=context)

    def btn_hq_close(self, cr, uid, ids, context=None):
        return self._close_fy(cr, uid, ids, context=context)

    def btn_mission_reopen(self, cr, uid, ids, context=None):
        if not ids:
            return
        if isinstance(ids, (int, long, )):
            ids = [ids]
        fy_id = ids[0]
        ayec_obj = self.pool.get('account.year.end.closing')

        ayec_obj.delete_year_end_entries(cr, uid, fy_id, context=context)
        ayec_obj.update_fy_state(cr, uid, fy_id, reopen=True, context=context)
        return {}

account_fiscalyear()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
