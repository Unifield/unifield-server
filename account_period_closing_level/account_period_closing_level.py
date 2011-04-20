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

from osv import fields, osv
import logging

class account_period_closing_level(osv.osv):
    _inherit = "account.period"
    
    # To avoid issues with existing OpenERP code (account move line for example),
    # the state are:
    #  - 'created' for Draft
    #  - 'draft' for Open
    #  - 'done' for HQ-Closed
    def _get_state(self, cursor, user_id, context=None):
        return (('created','Draft'), \
                ('draft', 'Open'), \
                ('field-closed', 'Field-Closed'), \
                ('mission-closed', 'Mission-Closed'), \
                ('done', 'HQ-Closed'))
    
    def action_set_state(self, cr, uid, ids, context):
        
        if context['state']:
            state = context['state']
            if state == 'done':
                journal_state = 'done'
            else:
                journal_state = 'draft'
            for id in ids:
                cr.execute('update account_journal_period set state=%s where period_id=%s', (journal_state, id))
                cr.execute('update account_period set state=%s where id=%s', (state, id))
        return True

    _columns = {
        'special': fields.boolean('Opening/Closing Period', size=12,
            help="These periods can overlap.", readonly=True),
        'state': fields.selection(_get_state, 'State', readonly=True,
            help='HQ opens a monthly period. After validation, it will be closed by the different levels.'),
    }
   
    def create(self, cr, uid, vals, context={}):
        if not context:
            context = {}

        if context.get('update_mode') in ['init', 'update'] and 'state' not in vals:
            logging.getLogger('init').info('Loading default draft state for account.period')
            vals['state'] = 'draft'

        return super(account_period_closing_level, self).create(cr, uid, vals, context=context)

    _defaults = {
        'state': 'created'
    }

account_period_closing_level()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
