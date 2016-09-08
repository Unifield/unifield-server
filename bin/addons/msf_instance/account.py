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

    def _get_child_mission_closed(self, cr, uid, ids, name, args, context=None):
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

    def _search_child_mission_closed(self, cr, uid, obj, name, args, context=None):
        '''
        Returns a domain corresponding to mission-closed periods
        - if in HQ: the periods must be "mission-closed" in all the coordos of the section (the status in HQ doesn't matter)
        - else: the periods must be "mission-closed" in the current instance
        '''
        res = []
        period_ids = []
        period_state_obj = self.pool.get('account.period.state')
        user_obj = self.pool.get('res.users')

        if not len(args):
            return res
        if len(args) != 1:
            msg = _("Domain %s not supported") % args
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] != '=':
            msg = _("Operator %s not supported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)
        if args[0][0] != 'child_mission_closed' or not args[0][2]:
            return res

        user = user_obj.browse(cr, uid, uid, context=context)
        # if the current instance is an HQ...
        instance_id = user.company_id.instance_id
        if instance_id and instance_id.level == 'section':
            # ... get the coordo instances...
            coordo_ids = [c.id for c in instance_id.child_ids if c.level == 'coordo']
            if coordo_ids:
                # ... get the periods that are mission-closed for all these instances
                for period in self.search(cr, uid, [], order='NO_ORDER', context=context):
                    domain = [
                        ('period_id', '=', period),
                        ('instance_id', 'in', coordo_ids),
                        ('state', '=', 'mission-closed'),
                    ]
                    period_count = period_state_obj.search(cr, uid, domain, order='NO_ORDER', context=context, count=True)
                    if period_count == len(coordo_ids):
                        period_ids.append(period)
                res.append(('id', 'in', period_ids))
        else:
            res.append(('state', '=', 'mission-closed'))
        return res

    _columns = {
        'child_mission_closed': fields.function(_get_child_mission_closed, method=True, store=False,
                                              string='Child Mission Closed',
                                              help='In HQ, check the periods being mission-closed in all coordos',
                                              type='boolean',
                                              fnct_search=_search_child_mission_closed),
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
