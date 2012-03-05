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

from tools.translate import _
from dateutil.relativedelta import relativedelta
from datetime import datetime

class date_tools(osv.osv):
    '''
    date related tools for msf project
    '''
    _name = 'date.tools'
    
    def get_date_format(self, cr, uid, context=None):
        '''
        get the date format for the uid specified user
        
        from msf_order_date module
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_format(cr, uid, 'date', context=context)
    
    def get_db_date_format(self, cr, uid, context=None):
        '''
        return constant value
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_db_format(cr, uid, 'date', context=context)
    
    def get_time_format(self, cr, uid, context=None):
        '''
        get the time format for the uid specified user
        
        from msf_order_date module
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_format(cr, uid, 'time', context=context)
    
    def get_db_time_format(self, cr, uid, context=None):
        '''
        return constant value
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_db_format(cr, uid, 'time', context=context)
    
    def get_datetime_format(self, cr, uid, context=None):
        '''
        get the datetime format for the uid specified user
        '''
        return self.get_date_format(cr, uid, context=context) + ' ' + self.get_time_format(cr, uid, context=context)
    
    def get_db_datetime_format(self, cr, uid, context=None):
        '''
        return constant value
        '''
        return self.get_db_date_format(cr, uid, context=context) + ' ' + self.get_db_time_format(cr, uid, context=context)
    
    def get_date_formatted(self, cr, uid, d_type='date', datetime=time.strftime('%Y-%m-%d'), context={}):
        '''
        Return the datetime in the format of the user
        @param d_type: 'date' or 'datetime' : determines which is the out format
        @param datetime: date to format 
        '''
        assert d_type in ('date', 'datetime'), 'Give only \'date\' or \'datetime\' as type parameter'
        
        if d_type == 'date':
            d_format = self.get_date_format(cr, uid)
            date = time.strptime(datetime, '%Y-%m-%d')
            return time.strftime(d_format, date)
        elif d_type == 'datetime':
            d_format = self.get_datetime_format(cr, uid)
            date = time.strptime(datetime, '%Y-%m-%d %H:%M:%S')
            return time.strftime(d_format, date)
    
date_tools()


class fields_tools(osv.osv):
    '''
    date related tools for msf project
    '''
    _name = 'fields.tools'
    
    def get_field_from_company(self, cr, uid, object=False, field=False, context=None):
        '''
        return the value for field from company for object 
        '''
        # field is required for value
        if not field:
            return False
        # object
        company_obj = self.pool.get('res.company')
        # corresponding company
        company_id = company_obj._company_default_get(cr, uid, object, context=context)
        # get the value
        res = company_obj.read(cr, uid, [company_id], [field], context=context)[0][field]
        return res
    
fields_tools()
    