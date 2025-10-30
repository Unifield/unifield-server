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
from tools.translate import _
from time import strptime




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
    if context.get('from_correction', False):
        # US-945 AJI correction are never processed on special periods
        number_criteria = ('number', '<', 13)
    else:
        number_criteria = ('number', '!=', 16)

    # Search period in which this date come from
    period_ids = self.pool.get('account.period').search(cr, uid, [
        ('date_start', '<=', date),
        ('date_stop', '>=', date),
        number_criteria,
    ], limit=limit,
        order='date_start asc, number asc', context=context) or []

    if isinstance(period_ids, int):
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

def get_next_period_id(self, cr, uid, period_id, context=None):
    """
    Returns the id of the next period if it exists (ignores special periods), else returns False
    """
    if context is None:
        context = {}
    period = self.browse(cr, uid, period_id, fields_to_fetch=['date_stop'], context=context)
    next_period_ids = self.search(cr, uid, [('date_start', '>', period.date_stop), ('special', '=', False)],
                                  order='date_start', limit=1, context=context)
    return next_period_ids and next_period_ids[0] or False

def get_next_period_id_at_index(self, cr, uid, period_id, index, context=None):
    """
    Returns the id of the period N+index, or False if it doesn't exist (ignores special periods)
    Ex: Nov.2017 + index 2 => Jan.2018
    """
    if context is None:
        context = {}
    for i in range(index):
        period_id = period_id and get_next_period_id(self, cr, uid, period_id, context=context)
    return period_id or False


def get_previous_period_id(self, cr, uid, period_id, context=None):
    """
    Returns the id of the previous regular period if it exists (no special period), else returns False.
    For the special periods, its returns the related regular period (Period 13 to 16 N ==> Dec. N).
    """
    if context is None:
        context = {}
    period = self.browse(cr, uid, period_id, fields_to_fetch=['date_start'], context=context)
    previous_period_ids = self.search(cr, uid, [('date_start', '<=', period.date_start),
                                                ('special', '=', False),
                                                ('id', '!=', period_id)],
                                      order='date_start DESC', limit=1, context=context)
    return previous_period_ids and previous_period_ids[0] or False


def _get_middle_years(self, cr, uid, fy1, fy2, context=None):
    """
    Returns the list of the FY ids included between both Fiscal Years in parameter.
    (e.g.: FY2015, FY2018 ==> FY2016, FY2017)
    """
    if context is None:
        context = {}
    middle_years = []
    fy_obj = self.pool.get('account.fiscalyear')
    y1 = strptime(fy1.date_start, '%Y-%m-%d').tm_year
    y2 = strptime(fy2.date_start, '%Y-%m-%d').tm_year
    if y2 > y1+1:  # non-successive years
        year_numbers = []
        year = y1+1
        while year < y2:
            year_numbers.append(year)
            year += 1
        for year_number in year_numbers:
            date_start = '%s-01-01' % year_number
            fy_ids = fy_obj.search(cr, uid, [('date_start', '=', date_start)], context=context, limit=1)
            if fy_ids:
                middle_years.append(fy_ids[0])
    return middle_years


def get_period_range(self, cr, uid, period_from_id, period_to_id, context=None):
    """
    Returns the ids of all the periods included between 2 other periods.
    Special periods 13 to 16 are included, period 0 is excluded.
    """
    if context is None:
        context = {}
    field_list = ['number', 'fiscalyear_id', 'date_start']
    initial_period = self.browse(cr, uid, period_from_id, fields_to_fetch=field_list, context=context)
    final_period = self.browse(cr, uid, period_to_id, fields_to_fetch=field_list, context=context)
    initial_fy_id = initial_period.fiscalyear_id.id
    initial_number = initial_period.number
    final_fy_id = final_period.fiscalyear_id.id
    final_number = final_period.number
    same_fy = initial_fy_id == final_fy_id
    if (final_period.date_start < initial_period.date_start) or \
            (same_fy and final_period.number < initial_period.number):  # e.g. Period 13 2018 precedes Period 14 2018
        raise osv.except_osv(_('Error'), _("The End period can't precede the Start period."))
    if same_fy:  # all the periods are within the same Fiscal Year
        period_dom = [
            ('number', '!=', 0),
            ('number', '>=', initial_number),
            ('number', '<=', final_number),
            ('fiscalyear_id', '=', initial_fy_id)]
    else:
        # check if there are "middle" years to include completely (e.g. Nov. 2018 to Jan. 2020 => all FY2019 periods should be included)
        middle_years = _get_middle_years(self, cr, uid, initial_period.fiscalyear_id, final_period.fiscalyear_id, context=context)
        if middle_years:
            period_dom = [
                ('number', '!=', 0),
                '|', '|',
                '&', ('number', '>=', initial_number), ('fiscalyear_id', '=', initial_fy_id),
                ('fiscalyear_id', 'in', middle_years),
                '&', ('number', '<=', final_number), ('fiscalyear_id', '=', final_fy_id)]
        else:
            # e.g.: from Nov. 2018 to Jan. 2019 => Nov 2018 / Dec 2018 / Periods 13->16 2018 / Jan 2019
            period_dom = [
                ('number', '!=', 0),
                '|',
                '&', ('number', '>=', initial_number), ('fiscalyear_id', '=', initial_fy_id),
                '&', ('number', '<=', final_number), ('fiscalyear_id', '=', final_fy_id)]
    period_ids = self.search(cr, uid, period_dom, order='id', context=context)
    return period_ids


class account_period(osv.osv):
    _name = 'account.period'
    _inherit = 'account.period'

    def get_period_from_date(self, cr, uid, date=False, context=None):
        return get_period_from_date(self, cr, uid, date, context)

    def get_date_in_period(self, cr, uid, date=None, period_id=None, context=None):
        return get_date_in_period(self, cr, uid, date, period_id, context)

    def get_next_period_id(self, cr, uid, period_id, context=None):
        return get_next_period_id(self, cr, uid, period_id, context)

    def get_next_period_id_at_index(self, cr, uid, period_id, index, context=None):
        return get_next_period_id_at_index(self, cr, uid, period_id, index, context)

    def get_previous_period_id(self, cr, uid, period_id, context=None):
        return get_previous_period_id(self, cr, uid, period_id, context)

    def get_period_range(self, cr, uid, period_from_id, period_to_id, context=None):
        return get_period_range(self, cr, uid, period_from_id, period_to_id, context=context)

    def get_open_period_from_date(self, cr, uid, date, check_extra_config, context=None):
        if not date:
            return False

        max_p_num = 12
        if check_extra_config and self.pool.get('res.company').extra_period_config(cr) in ('other', 'other_no_is'):
            max_p_num = 15

        period_ids = self.pool.get('account.period').search(cr, uid, [
            ('date_start', '<=', date),
            ('date_stop', '>=', date),
            ('state', '=', 'draft'),
            ('number', '>', 0),
            ('number', '<=', max_p_num)
        ], limit=1,
            order='date_start asc, number asc', context=context)
        return period_ids and period_ids[0] or False


account_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
