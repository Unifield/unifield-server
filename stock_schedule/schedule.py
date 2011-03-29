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
from datetime import datetime

from mx.DateTime import *



WEEK_DAYS = [('sunday', 'Sunday'), ('monday', 'Monday'),
             ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
             ('thursday', 'Thursday'), ('friday', 'Friday'), 
             ('saturday', 'Saturday')]

FREQUENCY = [('each', 'Each'), ('first', 'The first'), ('second', 'The second'),
             ('third', 'The third'), ('fourth', 'The fourth'), ('fifth', 'The fifth'),
             ('last', 'The last')]

MONTHS = [('january', 'January'), ('february', 'February'), ('march','March'),
          ('april', 'April'), ('may', 'May'), ('june', 'June'),
          ('july', 'July'), ('august', 'August'), ('september', 'September'),
          ('october', 'October'), ('november', 'November'), ('december', 'December'),]

class stock_frequence(osv.osv):
    _name = 'stock.frequence'
    _description = 'Stock scheduler'
    
    def get_datetime_day(self, monthly_choose_day):
        '''
        Return the good DateTime value according to the type of the day param.
        '''
        # Get the day number of the selected day
        if monthly_choose_day == 'sunday':
            day = Sunday
        elif monthly_choose_day == 'monday':
            day = Monday
        elif monthly_choose_day == 'tuesday':
            day = Tuesday
        elif monthly_choose_day == 'wednesday':
            day = Wednesday
        elif monthly_choose_day == 'thursday':
            day = Thursday
        elif monthly_choose_day == 'friday':
            day = Friday
        elif monthly_choose_day == 'saturday':
            day = Saturday
        else:
            day = Sunday
            
        return day
    
    def check_data(self, data):
        '''
        Check if all required data aren't empty
        '''
        if data['name'] == 'daily':
            if (not 'daily_frequency_ok' in data or not data.get('daily_frequency_ok', False)) and \
               (not 'daily_working_days' in data or not data.get('daily_working_days', False)):
                raise osv.except_osv(_('Error'), _('You should make a choice for the Daily configuration'))
        elif data['name'] == 'weekly':
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
    
    def create(self, cr, uid, data, context={}):
        '''
        Check if all required data aren't empty
        '''
        self.check_data(data)
        
        return super(stock_frequence, self).create(cr, uid, data, context=context)
    
    def write(self, cr, uid, ids, data, context={}):
        '''
        Check if all required data aren't empty
        '''
        for field in self._columns:
            if field not in data:
                data[field] = self.read(cr, uid, ids, [field])[0][field]
        
        self.check_data(data)
        
        return super(stock_frequence, self).write(cr, uid, ids, data, context=context)
    
    def _compute_end_date(self, cr, uid, ids, field, arg, context={}):
        '''
        Compute the end date of the frequence according to the field of the object
        '''
        if isinstance(ids, (int, long)):
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
        if not isinstance(frequence_id, (int, long)):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_daily_date'))
        
        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'daily':
            return False
        else:
            if frequence.daily_working_days:
                # Check if the number of day is in working days
                if int(time.strftime('%w')) > 0 and int(time.strftime('%w')) < 6:
                    return time.strftime('%Y-%m-%d')
                else:
                    # Return the date of next Monday
                    if int(time.strftime('%w')) == 0:
                        return (datetime.today() + relativedelta(days=1)).strftime('%Y-%m-%d')
                    elif int(time.strftime('%w')) == 6:
                        return (datetime.today() + relativedelta(days=2)).strftime('%Y-%m-%d')
            elif frequence.daily_frequency_ok:
                # Return the next date matching with the frequency parameter
                next_date = datetime.strptime(frequence.start_date, '%Y-%m-%d')
                while next_date < datetime.today():
                    next_date = next_date + relativedelta(days=frequence.daily_frequency)
                return next_date.strftime('%Y-%m-%d')
        
        return False
        
    def _compute_next_weekly_date(self, cr, uid, frequence_id):
        '''
        Compute the next date when the frequence is a weekly frequence
        '''
        if not isinstance(frequence_id, (int, long)):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_weekly_date'))
        
        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'weekly':
            return False
        else:
            start_date = datetime.strptime(frequence.start_date, '%Y-%m-%d')
            next_date = DateTime(int(start_date.strftime('%Y')), 
                                 int(start_date.strftime('%m')), 
                                 int(start_date.strftime('%d')),
                                 23, 59, 59)
            while next_date < now():
                next_date = next_date + RelativeDateTime(weeks=+frequence.weekly_frequency)
            next_date = next_date + RelativeDateTime(days=-7)
            while next_date < now():
                next_date = next_date + RelativeDateTime(days=+1)
            test = False
            while not test:
                day = datetime.fromtimestamp(next_date).strftime('%w')
                # Check if the next_date matching with parameters
                if int(day) == 0 and frequence.weekly_sunday_ok:
                    test = True
                elif int(day) == 1 and frequence.weekly_monday_ok:
                    test = True
                elif int(day) == 2 and frequence.weekly_tuesday_ok:
                    test = True
                elif int(day) == 3 and frequence.weekly_wednesday_ok:
                    test = True
                elif int(day) == 4 and frequence.weekly_thursday_ok:
                    test = True
                elif int(day) == 5 and frequence.weekly_friday_ok:
                    test = True
                elif int(day) == 6 and frequence.weekly_saturday_ok:
                    test = True
                else:
                    next_date = next_date + RelativeDateTime(days=+1)
                    
            return datetime.fromtimestamp(next_date)
        
        return False
    
    def _compute_next_monthly_date(self, cr, uid, frequence_id):
        '''
        Compute the next date when the frequence is a monthly frequence
        '''
        if not isinstance(frequence_id, (int, long)):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_weekly_date'))
        
        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'monthly':
            return False
        else:
            next = datetime.strptime(frequence.start_date, '%Y-%m-%d')
            while next < datetime.today():
                next = next + relativedelta(months=frequence.monthly_frequency, day=1)
            
            # Create a DateTime object to compare
            y = int(next.strftime('%Y'))
            m = int(next.strftime('%m'))
            d = int(next.strftime('%d'))
            next_date = DateTime(y, m, d)
            
            if frequence.monthly_one_day:
                freq = 0
                day = self.get_datetime_day(frequence.monthly_choose_day)
                        
                # Get the value for the choose frequence
                i = 0
                for f in FREQUENCY:
                    if frequence.monthly_choose_freq == f[0]:
                        freq = i
                    i += 1
                # Return the value -1 if the choosen frequency is 'The last'
                if freq == 6:
                    freq = -1
                    
                # Search the next date according to the selected day and the selected frequency
                relative_date = next_date + RelativeDateTime(weekday=(day,freq))
                while relative_date < next_date:
                    relative_date = next_date + RelativeDateTime(months=+frequence.monthly_frequency, weekday=(day,freq))
                
                return datetime.fromtimestamp(relative_date)
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
                
                while int(next.strftime('%d')) not in days_ok:
                    next = next + relativedelta(days=1)
                    
                return next
                
        return False
        
    def _compute_next_yearly_date(self, cr, uid, frequence_id):
        '''
        Compute the next date when the frequence is a yearly frequence
        '''
        if not isinstance(frequence_id, (int, long)):
            raise osv.except_osv(_('Error'), _('You should pass a integer to the _compute_next_weekly_date'))
        
        frequence = self.browse(cr, uid, frequence_id)
        if frequence.name != 'yearly':
            return False
        else:
            next = datetime.strptime(frequence.start_date, '%Y-%m-%d')
            while next < datetime.today():
                next = next + relativedelta(months=frequence.yearly_frequency, day=1, month=1)
             # Create a DateTime object to compare
            y = int(next.strftime('%Y'))
            m = int(next.strftime('%m'))
            d = int(next.strftime('%d'))
            next_date = DateTime.DateTime(y, 1, 1)
            if frequence.yearly_day_ok:
                # Get month number
                month = 1
                i = 0
                for m in MONTHS:
                    if frequence.yearly_choose_month == m:
                        month = i
                    i += 1
                
                # Get the next date
                while next_date < DateTime.now():
                    next_date = next_date + DateTime.RelativeDatetTime(month=month, day=frequence.yearly_day)
                    
                return next_date
            elif frequence.yearly_date_ok:
                day = self.get_datetime_day(frequence.yearly_choose_day)
                
                freq = 0
                # Get the value for the choose frequence
                i = 0
                for f in FREQUENCY:
                    if frequence.yearly_choose_freq == f[0]:
                        freq = i
                    i += 1
                # Return the value -1 if the choosen frequency is 'The last'
                if freq == 6:
                    freq = -1
                
                # Get the month number
                month = 1
                i = 1
                for m in MONTHS:
                    if frequence.yearly_choose_month_freq == m:
                        month = i
                    i += 1
                    
                # Search the next date according to the selected day and the selected frequency
                relative_date = next_date + DateTime.RelativeDateTime(weekday=(day,freq))
                while relative_date < next_date:
                    relative_date = next_date + DateTime.RelativeDateTime(month=m, weekday=(day,freq), years=+frequence.yearly_frequency)
                
                return datetime.fromtimestamp(relative_date)
        
        return False
        
    def _compute_next_date(self, cr, uid, ids, field, arg, context={}):
        '''
        Compute the next date matching with the parameter of the frequency
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        res = {}
            
        for frequence in self.browse(cr, uid, ids):
            if frequence.calculated_end_date and datetime.strptime(frequence.calculated_end_date, '%Y-%m-%d') < datetime.now():
                res[frequence.id] = False
            else:
                if frequence.name == 'daily':
                    res[frequence.id]= self._compute_next_daily_date(cr, uid, frequence.id)
                elif frequence.name == 'weekly':
                    res[frequence.id]= self._compute_next_weekly_date(cr, uid, frequence.id)
                elif frequence.name == 'monthly':
                    res[frequence.id]= self._compute_next_monthly_date(cr, uid, frequence.id)
                elif frequence.name == 'yearly':
                    res[frequence.id]= self._compute_next_yearly_date(cr, uid, frequence.id)
                else:
                    res[frequence.id] = False
        
        return res
    
    _columns = {
        'name': fields.selection([('daily', 'Daily'), ('weekly', 'Weekly'),
                                  ('monthly', 'Monthly'), ('yearly', 'Yearly')],
                                  string='Frequence', required=True),
                                  
        # Daily configuration
        'daily_frequency_ok': fields.boolean(string='Frequence'),
        'daily_frequency': fields.integer(string='Each'),
        'daily_working_days': fields.boolean(string='Each working Days'),
        
        # Weekly configuration
        'weekly_frequency': fields.integer(string='Each'),
        'weekly_sunday_ok': fields.boolean(string="Sunday"),
        'weekly_monday_ok': fields.boolean(string="Monday"),
        'weekly_tuesday_ok': fields.boolean(string="Tuesday"),
        'weekly_wednesday_ok': fields.boolean(string="Wednesday"),
        'weekly_thursday_ok': fields.boolean(string="Thursday"),
        'weekly_friday_ok': fields.boolean(string="Friday"),
        'weekly_saturday_ok': fields.boolean(string="Saturday"),
        
        # Monthly configuration
        'monthly_frequency': fields.integer(string='Each'),
        'monthly_one_day': fields.boolean(string='One day'),
        'monthly_choose_freq': fields.selection(FREQUENCY, string='Choose frequence'),
        'monthly_choose_day': fields.selection(WEEK_DAYS,string='Choose days'),
        'monthly_repeating_ok': fields.boolean(string='Repeatition'),
        'monthly_day1': fields.boolean(string='1'),
        'monthly_day2': fields.boolean(string='2'),
        'monthly_day3': fields.boolean(string='3'),
        'monthly_day4': fields.boolean(string='4'),
        'monthly_day5': fields.boolean(string='5'),
        'monthly_day6': fields.boolean(string='6'),
        'monthly_day7': fields.boolean(string='7'),
        'monthly_day8': fields.boolean(string='8'),
        'monthly_day9': fields.boolean(string='9'),
        'monthly_day10': fields.boolean(string='10'),
        'monthly_day11': fields.boolean(string='11'),
        'monthly_day12': fields.boolean(string='12'),
        'monthly_day13': fields.boolean(string='13'),
        'monthly_day14': fields.boolean(string='14'),
        'monthly_day15': fields.boolean(string='15'),
        'monthly_day16': fields.boolean(string='16'),
        'monthly_day17': fields.boolean(string='17'),
        'monthly_day18': fields.boolean(string='18'),
        'monthly_day19': fields.boolean(string='19'),
        'monthly_day20': fields.boolean(string='20'),
        'monthly_day21': fields.boolean(string='21'),
        'monthly_day22': fields.boolean(string='22'),
        'monthly_day23': fields.boolean(string='23'),
        'monthly_day24': fields.boolean(string='24'),
        'monthly_day25': fields.boolean(string='25'),
        'monthly_day26': fields.boolean(string='26'),
        'monthly_day27': fields.boolean(string='27'),
        'monthly_day28': fields.boolean(string='28'),
        'monthly_day29': fields.boolean(string='29'),
        'monthly_day30': fields.boolean(string='30'),
        'monthly_day31': fields.boolean(string='31'),
        
        # Yearly configuration
        'yearly_frequency': fields.integer(string='Each'),
        'yearly_day_ok': fields.boolean(string='Days'),
        'yearly_day': fields.integer(string='Day'),
        'yearly_choose_month': fields.selection(MONTHS, string='Choose a month'),
        'yearly_date_ok': fields.boolean(string='Date'),
        'yearly_choose_freq': fields.selection(FREQUENCY, string='Choose frequence'),
        'yearly_choose_day': fields.selection(WEEK_DAYS, string='Choose day'),
        'yearly_choose_month_freq': fields.selection(MONTHS, string='Choose a month'),
        
        # Recurrence configuration
        'start_date': fields.date(string='Start date', required=True),
        'end_date_ok': fields.boolean(string='End date'),
        'end_date': fields.date(string='Repeat to'),
        'no_end_date': fields.boolean(string='No end date'),
        'recurrence_ok': fields.boolean(string='Reccurence'),
        'recurrence_nb': fields.integer(string='Continuing for'),
        'recurrence_type': fields.selection([('day', 'Day(s)'), ('week', 'Week(s)'),
                                             ('month', 'Month(s)'), ('year', 'Year(s)')],
                                             string='Type of reccurence'),
        'calculated_end_date': fields.function(_compute_end_date, method=True, type='date', string='End date', store=False),
        'next_date': fields.function(_compute_next_date, method=True, type='date', string='Next date', store=False),
    }
    
    _defaults = {
        'name': lambda *a: 'daily',
        'monthly_choose_freq': lambda *a: 'each',
        'monthly_choose_day': lambda *a: 'monday',
        'yearly_choose_month': lambda *a: 'january',
        'yearly_choose_freq': lambda *a: 'each',
        'yearly_choose_day': lambda *a: 'monday',
        'yearly_choose_month_freq': lambda *a: 'january',
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
    }
    
    def check_date_in_month(self, cr, uid, ids, date, field):
        '''
        Checks if the date in parameter is higher than 1 and smaller than 31 
        '''
        if date < 1 or date > 31:
            if date < 1:
                date = 1
            else:
                date = 31
            return {'warning': {'title': _('Error'),
                                'message': _('The entered number is not a valid number of day')},
                    'result': {field: date}}
        
        return {}
    
    def choose_daily_frequency(self, cr, uid, ids, daily_frequency_ok=False, daily_working_days=False):
        '''
        Uncheck automatically the other choose when one is choosing
        '''
        if daily_frequency_ok:
            return {'value': {'daily_working_days': False}}
        if daily_working_days:
            return {'value': {'daily_frequency_ok': False}}
        
        return {}
    
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