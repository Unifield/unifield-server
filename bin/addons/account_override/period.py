#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

def get_period_from_date(self, cr, uid, date=False, context=None):
    """
    Get period in which this date could go into, otherwise return last open period.
    By default: Do not select special periods (Period 13, 14 and 15).
    except if extend_december to True in context
    """
    if context is None:
        context = {}
    if not date:
        return False
        
    limit = 1
    if context.get('extend_december', False) and date[5:7] == '12':
        # extend search to periods 12, 13, 14, 15 for december date
        limit = 4
        
    # Search period in which this date come from
    period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date), ('number', '!=', 16)], limit=limit,
        order='date_start asc, name asc', context=context) or []
    # Get last period if no period found
    if not period_ids:
        period_ids = self.pool.get('account.period').search(cr, uid, [('state', '=', 'open'), ('number', '!=', 16)], limit=limit,
            order='date_stop desc, name desc', context=context) or []
    if isinstance(period_ids, (int, long)):
        period_ids = [period_ids]
    return period_ids

def get_date_in_period(self, cr, uid, date=None, period_id=None, context=None):
    """
    Permit to return a date included in period :
     - if given date is included in period, return the given date
     - else return the date_stop of given period
    """
    if context is None:
        context = {}
    if not date or not period_id:
        return False
    period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
    if date < period.date_start or date > period.date_stop:
        return period.date_stop
    return date

class account_period(osv.osv):
    _name = 'account.period'
    _inherit = 'account.period'

    def get_period_from_date(self, cr, uid, date=False, context=None):
        return get_period_from_date(self, cr, uid, date, context)

    def get_date_in_period(self, cr, uid, date=None, period_id=None, context=None):
        return get_date_in_period(self, cr, uid, date, period_id, context)

account_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
