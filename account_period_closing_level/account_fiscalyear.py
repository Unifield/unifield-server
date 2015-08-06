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

class account_fiscalyear(osv.osv):
    _name = "account.fiscalyear"
    _inherit = "account.fiscalyear"

    def _get_is_closable(self, cr, uid, ids, field_names, args, context=None):
        # US-131: closable if all periods HQ closed (special ones too)
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]

        level = self.pool.get('res.users').browse(cr, uid, [uid],
            context=context)[0].company_id.instance_id.level
        if level != 'section':
            # not at HQ level: FY not closable
            for id in ids:
                res[id] = False
            return res

        # check:
        # - FY is not already closed
        # - all FY's periods are HQ closed (state 'done') (special ones too)
        for br in self.browse(cr, uid, ids, context=context):
            closable = False

            if br.state != 'done':
                closable = all([ True if p.state == 'done' else False \
                    for p in br.period_ids ])

            res[br.id] = closable

        return res

    _columns = {
        # US-131
        'is_closable': fields.function(_get_is_closable, type='boolean',
            method=True, string='Closable ? (all periods HQ closed)'),
    }

    _defaults = {
        'is_closable': False,
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
        # Prepare some values
        current_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        name = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.name
        # Then sequence creation on all journals
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('instance_id', '=', current_instance_id)])
        for journal in self.pool.get('account.journal').browse(cr, uid, journal_ids, context=context):
            self.pool.get('account.journal').create_fiscalyear_sequence(cr, uid, res, name, journal.code.lower(), vals['date_start'], journal.sequence_id and journal.sequence_id.id or False, context=context)
        return res

    def uf_close_fy(self, cr, uid, ids, context=None):
        """
        US-131: Close FY(s) at HQ level: just set state to 'done'
        (to prevent use of FY(s) in many2one fields)
        """
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]

        for r in self.read(cr, uid, ids, ['is_closable', ], context=context):
            if not r['is_closable']:
                raise osv.except_osv(_("Warning"),
                    _("Fiscal Year can not be closed. Aborted." \
                        " (All periods must be HQ closed)"))

        self.write(cr, uid, ids, { 'state': 'done' }, context=context)
        return res

account_fiscalyear()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
