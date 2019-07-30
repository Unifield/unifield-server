# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from osv import osv, fields
from tools.translate import _

class account_period(osv.osv):
    _name = 'account.period'
    _inherit = 'account.period'

    def _get_child_state(self, cr, uid, ids, name, args, context=None):
        """
        Fake method / always returns False
        """
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _search_child_states(self, cr, uid, obj, name, args, period_states=None, context=None):
        """
        Returns a domain corresponding to periods having specific states for the selected fiscal year.
        The period states:
        - correspond to: the tuple of period_states given in parameter, or mission-closed by default
        - if in HQ: are those from the selected coordo
        - else: are those from the current instance
        """
        res = []
        period_ids = []
        user_obj = self.pool.get('res.users')
        if not len(args):
            return res
        if len(args) != 1:
            msg = _("Domain %s not supported") % args
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] != '=':
            msg = _("Operator %s not supported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)
        if not args[0][2]:
            return res
        # if no fiscal year selected: don't display any periods
        fy = args[0][2][1]
        if not fy:
            return [('id', 'in', [])]
        if not period_states:
            period_states = ('mission-closed',)
        # if the current instance is an HQ
        instance_id = user_obj.browse(cr, uid, uid, context=context).company_id.instance_id
        if instance_id and instance_id.level == 'section':
            # if no proprietary instance selected: don't display any periods
            prop_inst = args[0][2][0]
            if not prop_inst:
                return [('id', 'in', [])]
            # else get the periods having the required state(s)
            sql_get_periods = """
                  SELECT ps.period_id
                  FROM account_period_state ps
                  INNER JOIN account_period p
                  ON ps.period_id = p.id
                  WHERE ps.state in %s
                  AND ps.instance_id = %s
                  AND p.fiscalyear_id = %s;"""
            cr.execute(sql_get_periods, (period_states, prop_inst, fy))
            for line in cr.fetchall():
                period_ids.append(line[0])
            res.append(('id', 'in', period_ids))
        else:
            # if not in HQ
            res.extend([('state', 'in', period_states), ('fiscalyear_id', '=', fy)])
        return res

    def _search_child_mission_closed(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain with mission-closed periods for the selected FY & coordo (or for the current inst. if not in HQ)
        """
        return self._search_child_states(cr, uid, obj, name, args, context=context)

    def _search_child_mission_hq_closed(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain with mission-closed or HQ-closed periods for the selected FY & coordo (or for the current inst. if not in HQ)
        """
        states = ('mission-closed', 'done',)
        return self._search_child_states(cr, uid, obj, name, args, period_states=states, context=context)

    _columns = {
        'child_mission_closed': fields.function(_get_child_state, method=True, store=False,
                                                string='Child Mission Closed',
                                                help='In HQ, check the periods being mission-closed in the selected coordo',
                                                type='boolean',
                                                fnct_search=_search_child_mission_closed),
        'child_mission_hq_closed': fields.function(_get_child_state, method=True, store=False,
                                                   string='Child Mission or HQ Closed',
                                                   help='In HQ, checks the periods being mission or HQ-closed in the selected coordo',
                                                   type='boolean',
                                                   fnct_search=_search_child_mission_hq_closed),
    }

    def action_set_state(self, cr, uid, ids, context=None):
        """
        Check that all hq entries from the given period are validated.
        This check is only done on COORDO level!
        """
        # Some verifications
        if not context:
            context = {}
        # Are we in coordo level?
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user and user.company_id and user.company_id.instance_id and user.company_id.instance_id.level and user.company_id.instance_id.level == 'coordo':
            # Check hq entries
            period_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')])
            if isinstance(period_ids, (int, long)):
                period_ids = [period_ids]
            hq_ids = self.pool.get('hq.entries').search(cr, uid, [('period_id', 'in', period_ids), ('user_validated', '=', False)])
            if hq_ids:
                raise osv.except_osv(_('Warning'), _('Some HQ entries are not validated in this period. Please validate them before field-closing this period.'))
        return super(account_period, self).action_set_state(cr, uid, ids, context)

account_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
