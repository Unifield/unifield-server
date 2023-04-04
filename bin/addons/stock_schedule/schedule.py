# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import time
import re

from tools.translate import _
from dateutil.relativedelta import relativedelta
from dateutil.relativedelta import SU, MO, TU, WE, TH, FR, SA
from datetime import datetime


WEEK_DAYS = [('sunday', 'Sunday'), ('monday', 'Monday'),
             ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
             ('thursday', 'Thursday'), ('friday', 'Friday'),
             ('saturday', 'Saturday')]

FREQUENCY = [(1, 'The first'), (2, 'The second'),
             (3, 'The third'), (4, 'The fourth'), (5, 'The fifth'),
             (-1, 'The last')]

MONTHS = [(1, 'January'), (2, 'February'), (3,'March'),
          (4, 'April'), (5, 'May'), (6, 'June'),
          (7, 'July'), (8, 'August'), (9, 'September'),
          (10, 'October'), (11, 'November'), (12, 'December'),]


class stock_frequence(osv.osv):
    _name = 'stock.frequence'
    _description = 'Stock scheduler'

    def get_selection(self, cr, uid, o, field, context=None):
        """
        Returns the field.selection label
        """
        if not context:
            context = {}

        sel = self.pool.get(o._name).fields_get(cr, uid, [field])
        res = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
        name = '%s,%s' % (o._name, field)
        tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', res), ('lang', '=', context.get('lang'))])
        if tr_ids:
            return self.pool.get('ir.translation').read(cr, uid, tr_ids, ['value'])[0]['value']
        else:
            return res

    def get_datetime_day(self, monthly_choose_day):
        '''
        Return the good Date value according to the type of the day param.
        '''
        # Get the day number of the selected day
        data = {'sunday': SU, 'monday': MO, 'tuesday': TU, 'wednesday': WE, 'thursday': TH, 'friday': FR, 'saturday': SA}
        return data.get(monthly_choose_day, 6)

    def check_data(self, data):
        '''
        Check if all required data aren't empty
        '''
        if data['name'] == 'weekly':
            if (not 'weekly_sunday_ok' in data or not data.get('weekly_sunday_ok', False)) and \
               (not 'weekly_monday_ok' in data or not data.get('weekly_monday_ok', False)) and \
               (not 'weekly_tuesday_ok' in data or not data.get('weekly_tuesday_ok', False)) and \
               (not 'weekly_wednesday_ok' in data or not data.get('weekly_wednesday_ok', False)) and \
               (not 'weekly_thursday_ok' in data or not data.get('weekly_thursday_ok', False)) and \
               (not 'weekly_friday_ok' in data or not data.get('weekly_friday_ok', False)) and \
               (not 'weekly_saturday_ok' in data or not data.get('weekly_saturday_ok', False)):
                raise osv.except_osv(_('Error'), _('You should choose at least one day of week !'))
        elif data['name'] == 'monthly':
            if (not 'monthly_one_day' in data or not data.get('monthly_one_day', False)) and \
               (not 'monthly_repeating_ok' in data or not data.get('monthly_repeating_ok', False)):
                raise osv.except_osv(_('Error'), _('You should make a choice for the Monthly configuration'))
            elif 'monthly_repeating_ok' in data and data.get('monthly_repeating_ok', False):
                # Check if at least one day of month is selected
                test = False
                i = 0
                while i < 32 and not test:
                    i += 1
                    if i <10:
                        field = 'monthly_day0%s' %str(i)
                    else:
                        field = 'monthly_day%s' %str(i)
                    if field in data and data.get(field, False):
                        test = True
                if not test:
                    raise osv.except_osv(_('Error'), _('You should select at least one day of the month !'))
        elif data['name'] == 'yearly':
            if (not 'yearly_day_ok' in data or not data.get('yearly_day_ok', False)) and \
               (not 'yearly_date_ok' in data or not data.get('yearly_date_ok', False)):
                raise osv.except_osv(_('Error'), _('You should make a choice for the Yearly configuration'))

        if (not 'no_end_date' in data or not data.get('no_end_date', False)) and \
           (not 'end_date_ok' in data or not data.get('end_date_ok', False)) and \
           (not 'recurrence_ok' in data or not data.get('recurrence_ok', False)):
            raise osv.except_osv(_('Error'), _('You should make a choice for the Replenishment repeating !'))

        return

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['last_run'] = False
        return super(stock_frequence, self).copy(cr, uid, id, default, context)

    def create(self, cr, uid, data, context=None):
        '''
        Check if all required data aren't empty
        '''
        self.check_data(data)

        return super(stock_frequence, self).create(cr, uid, data, context=context)

    def write(self, cr, uid, ids, data, context=None):
        '''
        Check if all required data aren't empty
        '''
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]

        data_bis = data.copy()

        for field in self._columns:
            if field not in data_bis:
                data_bis[field] = self.read(cr, uid, ids, [field])[0][field]

        self.check_data(data_bis)

        return super(stock_frequence, self).write(cr, uid, ids, data, context=context)

    def _compute_end_date(self, cr, uid, ids, field, arg, context=None):
        '''
        Compute the end date of the frequence according to the field of the object
        '''
        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for obj in self.browse(cr, uid, ids):
            res[obj.id] = False
            if obj.end_date_ok:
                res[obj.id] = obj.end_date
            if obj.recurrence_ok:
                start_date = datetime.strptime(obj.start_date, '%Y-%m-%d')
                if obj.recurrence_type == 'day':
                    res[obj.id] = (start_date + relativedelta(days=obj.recurrence_nb)).strftime('%Y-%m-%d')
                elif obj.recurrence_type == 'week':
                    res[obj.id] = (start_date + relativedelta(weeks=obj.recurrence_nb)).strftime('%Y-%m-%d')
                elif obj.recurrence_type == 'month':
                    res[obj.id] = (start_date + relativedelta(months=obj.recurrence_nb)).strftime('%Y-%m-%d')
                elif obj.recurrence_type == 'year':
                    res[obj.id] = (start_date + relativedelta(years=obj.recurrence_nb)).strftime('%Y-%m-%d')

        return res

    def _compute_next_daily_date(self, cr, uid, frequence_id):
        '''
        Compute the next date when the frequence is a daily frequence
        '''
        if not isinstance(frequence_id, int):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_daily_date'))

        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'daily':
            return False
        else:
            start_date = datetime.strptime(frequence.start_date, '%Y-%m-%d')
            if start_date > datetime.today():
                return start_date

            if not frequence.last_run:
                return datetime.today()
                #numdays = (today() - start_date).day
                #modulo = math.ceil(numdays/frequence.daily_frequency_ok)*frequence.daily_frequency_ok
                #return start_date+RelativeDate(days=modulo)
            return max(datetime.today(), datetime.strptime(frequence.last_run, '%Y-%m-%d')+relativedelta(days=frequence.daily_frequency))

    def _compute_next_weekly_date(self, cr, uid, frequence_id):
        '''
        Compute the next date when the frequence is a weekly frequence
        '''
        if not isinstance(frequence_id, int):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_weekly_date'))

        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'weekly':
            return False
        else:
            data = ['monday','tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

            if not frequence.weekly_sunday_ok and not frequence.weekly_monday_ok and not frequence.weekly_tuesday_ok \
                    and not frequence.weekly_wednesday_ok and not frequence.weekly_thursday_ok and not frequence.weekly_friday_ok \
                    and not frequence.weekly_saturday_ok:
                raise osv.except_osv(_('Error'), _('You should choose at least one day of week !'))

            if not frequence.last_run:
                start_date = datetime.strptime(frequence.start_date, '%Y-%m-%d')
                if start_date < datetime.today():
                    start_date = datetime.today()
                while True:
                    i = start_date.weekday()
                    if getattr(frequence, 'weekly_%s_ok'%(data[i])):
                        return start_date
                    start_date += relativedelta(days=1)

            next_date = datetime.strptime(frequence.last_run, '%Y-%m-%d')+relativedelta(days=1)
            while True:
                if getattr(frequence, 'weekly_%s_ok'%(data[next_date.weekday()])):
                    return max(datetime.today(), next_date)
                next_date += relativedelta(days=1)
                if next_date.weekday() == 0:
                    next_date += relativedelta(weeks=frequence.weekly_frequency-1)

        return False

    def _compute_next_monthly_date(self, cr, uid, frequence_id):
        '''
        Compute the next date when the frequence is a monthly frequence
        '''
        if not isinstance(frequence_id, int):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_weekly_date'))

        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'monthly':
            return False
        else:
            if frequence.monthly_one_day:
                day = self.get_datetime_day(frequence.monthly_choose_day)
                if frequence.last_run:
                    from_date = datetime.strptime(frequence.last_run, '%Y-%m-%d')
                    return max(datetime.today(), from_date + relativedelta(months=+frequence.monthly_frequency, weekday=day(frequence.monthly_choose_freq)))
                else:
                    start_date = datetime.strptime(frequence.start_date, '%Y-%m-%d')
                    if start_date < datetime.today():
                        start_date = datetime.today()
                    next_date = start_date + relativedelta(weekday=day(frequence.monthly_choose_freq))
                    while next_date < start_date:
                        next_date = next_date + relativedelta(months=1, weekday=day(frequence.monthly_choose_freq))
                    return next_date

            elif frequence.monthly_repeating_ok:
                days_ok = []
                # Get all fields for choosen days
                fields = []
                for col in self._columns:
                    if re.match('^monthly_day[0-9]', col):
                        fields.append(col)
                frequence_read = self.read(cr, uid, [frequence_id], fields)[0]
                for f in fields:
                    if frequence_read[f]:
                        days_ok.append(int(f[-2:]))
                days_ok.sort()

                if frequence.last_run:
                    from_date = datetime.strptime(frequence.last_run, '%Y-%m-%d')+relativedelta(days=1)
                    force = True
                else:
                    from_date = datetime.strptime(frequence.start_date, '%Y-%m-%d')
                    if from_date < datetime.today():
                        from_date = datetime.today()
                    force = False

                if from_date.day > days_ok[-1]:
                    # switch to next month
                    if force:
                        from_date += relativedelta(day=days_ok[0], months=frequence.monthly_frequency)
                        return max(datetime.today(), from_date)
                    else:
                        from_date += relativedelta(day=days_ok[0], months=1)
                        return from_date

                days = [a for a in days_ok if a>=from_date.day]
                from_date += relativedelta(day=days[0])
                if force:
                    return max(datetime.today(), from_date)
                return from_date

        return False

    def _compute_next_yearly_date(self, cr, uid, frequence_id):
        '''
        Compute the next date when the frequence is a yearly frequence
        '''
        if not isinstance(frequence_id, int):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_weekly_date'))

        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'yearly':
            return False
        else:
            start_date = datetime.strptime(frequence.start_date, '%Y-%m-%d')
            if start_date < datetime.today():
                start_date = datetime.today()
            if not frequence.last_run:
                if frequence.yearly_day_ok:
                    next_date = start_date + relativedelta(month=frequence.yearly_choose_month, day=frequence.yearly_day)
                    if next_date < start_date:
                        return start_date + relativedelta(month=frequence.yearly_choose_month, day=frequence.yearly_day, years=1)
                    return next_date
                if frequence.yearly_date_ok:
                    day = self.get_datetime_day(frequence.yearly_choose_day)
                    next_date = start_date + relativedelta(month=frequence.yearly_choose_month_freq, weekday=day(frequence.yearly_choose_freq))
                    if next_date < start_date:
                        return start_date + relativedelta(years=1, month=frequence.yearly_choose_month_freq, weekday=day(frequence.yearly_choose_freq))
                    return next_date

            next_date = datetime.strptime(frequence.last_run, '%Y-%m-%d')
            if frequence.yearly_day_ok:
                next_date += relativedelta(years=frequence.yearly_frequency, month=frequence.yearly_choose_month, day=frequence.yearly_day)
            else:
                day = self.get_datetime_day(frequence.yearly_choose_day)
                next_date += relativedelta(years=frequence.yearly_frequency, month=frequence.yearly_choose_month_freq, weekday=day(frequence.yearly_choose_freq))
            return max(datetime.today(), next_date)

        return False

    def _compute_next_date(self, cr, uid, ids, field, arg, context=None):
        '''
        Compute the next date matching with the parameter of the frequency
        '''
        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for frequence in self.browse(cr, uid, ids):
            if frequence.calculated_end_date and datetime.strptime(frequence.calculated_end_date, '%Y-%m-%d') < datetime.now():
                res[frequence.id] = False
            else:
                if frequence.name == 'daily':
                    next_date = self._compute_next_daily_date(cr, uid, frequence.id).strftime('%Y-%m-%d')
                elif frequence.name == 'weekly':
                    next_date = self._compute_next_weekly_date(cr, uid, frequence.id).strftime('%Y-%m-%d')
                elif frequence.name == 'monthly':
                    next_date = self._compute_next_monthly_date(cr, uid, frequence.id).strftime('%Y-%m-%d')
                elif frequence.name == 'yearly':
                    next_date = self._compute_next_yearly_date(cr, uid, frequence.id).strftime('%Y-%m-%d')
                else:
                    res[frequence.id] = False

                if frequence.calculated_end_date and datetime.strptime(next_date, '%Y-%m-%d') >= datetime.strptime(frequence.calculated_end_date, '%Y-%m-%d'):
                    res[frequence.id] = False
                else:
                    res[frequence.id] = next_date

        return res

    def choose_frequency(self, cr, uid, ids, context=None):
        '''
        Empty method. Override this method to implement your own features
        '''
        if context is None:
            context = {}
        if context.get('active_model') == 'replenishment.location.config' and context.get('active_id'):
            freq = self.read(cr, uid, ids[0], ['next_date'], context=context)
            self.pool.get('replenishment.location.config').write(cr, uid, context['active_id'], {'next_scheduler': freq['next_date']}, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def name_get(self, cr, uid, ids, context=None):
        '''
        Returns a description of the frequence
        '''
        if not context:
            context = {}

        res = super(stock_frequence, self).name_get(cr, uid, ids, context=context)

        # TODO: Modif of name_get method to return a comprehensive name for frequence
        res = []

        for freq in self.browse(cr, uid, ids):
            if freq.name == 'daily':
                if freq.daily_frequency_ok:
                    title = _('Every %d day(s)') % (freq.daily_frequency,)
            if freq.name == 'weekly':
                sunday = monday = tuesday = wednesday = thursday = friday = saturday = ''
                if freq.weekly_sunday_ok:
                    sunday = 'sunday '
                if freq.weekly_monday_ok:
                    monday = 'monday '
                if freq.weekly_tuesday_ok:
                    tuesday = 'tuesday '
                if freq.weekly_wednesday_ok:
                    wednesday = 'wednesday '
                if freq.weekly_thursday_ok:
                    thursday = 'thursday '
                if freq.weekly_friday_ok:
                    friday = 'friday '
                if freq.weekly_saturday_ok:
                    saturday = 'saturday '
                title = _('Every %d week(s) on %s%s%s%s%s%s%s') %(freq.weekly_frequency, sunday, monday, tuesday, \
                                                                  wednesday, thursday, \
                                                                  friday, saturday)
            if freq.name == 'monthly':
                if freq.monthly_one_day:
                    choose_freq = self.get_selection(cr, uid, freq, 'monthly_choose_freq', context=context)
                    choose_day = self.get_selection(cr, uid, freq, 'monthly_choose_day', context=context)
                    title = _('%s %s - Every %s month(s)') % (choose_freq, choose_day, freq.monthly_frequency)
                elif freq.monthly_repeating_ok:
                    title = _('On ')
                    i = 1
                    # For each days
                    while i < 32:
                        day_f = 'th'
                        field = i < 10 and '0%s' %i or '%s' %i
                        if i in (1, 21, 31):
                            day_f = 'st'
                        elif i in (2, 22):
                            day_f = 'nd'
                        elif i in (3, 23):
                            day_f = 'rd'
                        day_ok = self.read(cr, uid, [freq.id], ['monthly_day%s' %field])[0]['monthly_day%s' %field]
                        title += day_ok and 'the %s%s, ' %(i, day_f) or ''
                        i += 1
                    # Remove the last comma
                    title = title[:-2]
                    title += _(' - Every %s month(s)') % (freq.monthly_frequency,)
            if freq.name == 'yearly':
                if freq.yearly_day_ok:
                    month = self.get_selection(cr, uid, freq, 'yearly_choose_month', context=context)
                    day_f = 'th'
                    if freq.yearly_day in (1, 21, 31):
                        day_f = 'st'
                    elif freq.yearly_day in (2, 22):
                        day_f = 'nd'
                    elif freq.yearly_day in (3, 23):
                        day_f = 'rd'
                    title = _('All %s, the %s%s') %(month, freq.yearly_day, day_f)
                elif freq.yearly_date_ok:
                    frequence = self.get_selection(cr, uid, freq, 'yearly_choose_freq', context=context)
                    day = self.get_selection(cr, uid, freq, 'yearly_choose_day', context=context)
                    month = self.get_selection(cr, uid, freq, 'yearly_choose_month_freq', context=context)
                    title = _('All %s %s in %s') % (frequence, day, month)
                title += _(' - Every %s year(s)') %(freq.yearly_frequency)

            res.append((freq.id, title))

        return res

    _columns = {
        'name': fields.selection([('daily', 'Daily'), ('weekly', 'Weekly'),
                                  ('monthly', 'Monthly'), ('yearly', 'Yearly')],
                                 string='Frequence', required=True),

        # Daily configuration
        'daily_frequency_ok': fields.boolean(string='Frequence'),
        'daily_frequency': fields.integer(string='Every'),

        # Weekly configuration
        'weekly_frequency': fields.integer(string='Every'),
        'weekly_sunday_ok': fields.boolean(string="Sunday"),
        'weekly_monday_ok': fields.boolean(string="Monday"),
        'weekly_tuesday_ok': fields.boolean(string="Tuesday"),
        'weekly_wednesday_ok': fields.boolean(string="Wednesday"),
        'weekly_thursday_ok': fields.boolean(string="Thursday"),
        'weekly_friday_ok': fields.boolean(string="Friday"),
        'weekly_saturday_ok': fields.boolean(string="Saturday"),

        # Monthly configuration
        'monthly_frequency': fields.integer(string='Every'),
        'monthly_one_day': fields.boolean(string='One day'),
        'monthly_choose_freq': fields.selection(FREQUENCY, string='Choose frequence', size=-1),
        'monthly_choose_day': fields.selection(WEEK_DAYS,string='Choose days'),
        'monthly_repeating_ok': fields.boolean(string='Repeatition'),
        'monthly_day01': fields.boolean(string='1st'),
        'monthly_day02': fields.boolean(string='2nd'),
        'monthly_day03': fields.boolean(string='3rd'),
        'monthly_day04': fields.boolean(string='4th'),
        'monthly_day05': fields.boolean(string='5th'),
        'monthly_day06': fields.boolean(string='6th'),
        'monthly_day07': fields.boolean(string='7th'),
        'monthly_day08': fields.boolean(string='8th'),
        'monthly_day09': fields.boolean(string='9th'),
        'monthly_day10': fields.boolean(string='10th'),
        'monthly_day11': fields.boolean(string='11th'),
        'monthly_day12': fields.boolean(string='12th'),
        'monthly_day13': fields.boolean(string='13th'),
        'monthly_day14': fields.boolean(string='14th'),
        'monthly_day15': fields.boolean(string='15th'),
        'monthly_day16': fields.boolean(string='16th'),
        'monthly_day17': fields.boolean(string='17th'),
        'monthly_day18': fields.boolean(string='18th'),
        'monthly_day19': fields.boolean(string='19th'),
        'monthly_day20': fields.boolean(string='20th'),
        'monthly_day21': fields.boolean(string='21st'),
        'monthly_day22': fields.boolean(string='22nd'),
        'monthly_day23': fields.boolean(string='23rd'),
        'monthly_day24': fields.boolean(string='24th'),
        'monthly_day25': fields.boolean(string='25th'),
        'monthly_day26': fields.boolean(string='26th'),
        'monthly_day27': fields.boolean(string='27th'),
        'monthly_day28': fields.boolean(string='28th'),
        'monthly_day29': fields.boolean(string='29th'),
        'monthly_day30': fields.boolean(string='30th'),
        'monthly_day31': fields.boolean(string='31st'),

        # Yearly configuration
        'yearly_frequency': fields.integer(string='Every'),
        'yearly_day_ok': fields.boolean(string='Days'),
        'yearly_day': fields.integer(string='Day'),
        'yearly_choose_month': fields.selection(MONTHS, string='Choose a month', size=-1),
        'yearly_date_ok': fields.boolean(string='Date'),
        'yearly_choose_freq': fields.selection(FREQUENCY, string='Choose frequence', size=-1),
        'yearly_choose_day': fields.selection(WEEK_DAYS, string='Choose day'),
        'yearly_choose_month_freq': fields.selection(MONTHS, string='Choose a month', size=-1),

        # Recurrence configuration
        'start_date': fields.date(string='Start date', required=True),
        'end_date_ok': fields.boolean(string='End date'),
        'end_date': fields.date(string='Until'),
        'no_end_date': fields.boolean(string='No end date'),
        'recurrence_ok': fields.boolean(string='Reccurence'),
        'recurrence_nb': fields.integer(string='Continuing for'),
        'recurrence_type': fields.selection([('day', 'Day(s)'), ('week', 'Week(s)'),
                                             ('month', 'Month(s)'), ('year', 'Year(s)')],
                                            string='Type of reccurence'),

        'last_run': fields.date(string='Last run'),
        'calculated_end_date': fields.function(_compute_end_date, method=True, type='date', string='End date', store=False),
        'next_date': fields.function(_compute_next_date, method=True, type='date', string='Next date', store=False),
    }

    _defaults = {
        'name': lambda *a: 'daily',
        'monthly_choose_freq': lambda *a: 1,
        'monthly_choose_day': lambda *a: 'monday',
        'yearly_choose_month': lambda *a: 1,
        'yearly_choose_freq': lambda *a: 1,
        'yearly_choose_day': lambda *a: 'monday',
        'yearly_choose_month_freq': lambda *a: 1,
        'daily_frequency': lambda *a: 1,
        'weekly_frequency': lambda *a: 1,
        'monthly_frequency': lambda *a: 1,
        'yearly_frequency': lambda *a: 1,
        'yearly_day': lambda *a: 1,
        'recurrence_nb': lambda *a: 1,
        'recurrence_type': lambda *a: 'day',
        'no_end_date': lambda *a: True,
        'yearly_day_ok': lambda *a: True,
        'monthly_one_day': lambda *a: True,
        'daily_frequency_ok': lambda *a: True,
        'weekly_monday_ok': lambda *a: True,
        'start_date': lambda *a: time.strftime('%Y-%m-%d'),
        'last_run': lambda *a: False,
    }

    def check_date_in_month(self, cr, uid, ids, day, month):
        '''
        Checks if the date in parameter is higher than 1 and smaller than 31 
        '''
        warn = {}

        if day < 1:
            day = 1
        elif month == 2 and day > 29:
            day = 28
        elif month in [4, 6, 9, 11] and day > 30:
            day = 30
        elif day > 31:
            day = 31
        elif month == 2 and day == 29:
            warn = {'title': _('Warning'),
                    'message': _('You have selected February, the 29th as shedule date. For non leap years, the action will be run on March, the 1st !')}

#        if warning:
#            warn = {'title': _('Error'),
#                    'message': _('The entered number is not a valid number of day')}
#
        return {'warning': warn, 'value': {'yearly_day': day}}


    def monthly_freq_change(self, cr, uid, ids, monthly_one_day=False, monthly_repeating_ok=False):
        '''
        Uncheck automatically the other choose when one is choosing
        '''
        if monthly_one_day:
            return {'value': {'monthly_repeating_ok': False}}
        if monthly_repeating_ok:
            return {'value': {'monthly_one_day': False}}

        return {}

    def yearly_freq_change(self, cr, uid, ids, yearly_day_ok=False, yearly_date_ok=False):
        '''
        Uncheck automatically the other choose when one is choosing
        '''
        if yearly_day_ok:
            return {'value': {'yearly_date_ok': False}}
        if yearly_date_ok:
            return {'value': {'yearly_day_ok': False}}

        return {}

    def change_recurrence(self, cr, uid, ids, field, no_end_date=False, end_date_ok=False, recurrence_ok=False):
        '''
        Uncheck automatically the other choose when one is choosing
        '''
        if no_end_date and field == 'no_end_date':
            return {'value': {'end_date_ok': False, 'recurrence_ok': False}}
        if end_date_ok and field == 'end_date_ok':
            return {'value': {'no_end_date': False, 'recurrence_ok': False}}
        if recurrence_ok and field == 'recurrence_ok':
            return {'value': {'end_date_ok': False, 'no_end_date': False}}

        return {}

stock_frequence()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
