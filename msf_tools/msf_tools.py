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

class lang(osv.osv):
    '''
    define getter for date / time / datetime formats
    '''
    _inherit = 'res.lang'
    
    def _get_format(self, cr, uid, type, context=None):
        '''
        generic function
        '''
        if context is None:
            context = {}
        type = type + '_format'
        assert type in self._columns, 'Specified format field does not exist'
        user_obj = self.pool.get('res.users')
        # get user context lang
        user_lang = user_obj.read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
        # get coresponding id
        lang_id = self.search(cr, uid, [('code','=',user_lang)])
        # return format value or from default function if not exists
        format = lang_id and self.read(cr, uid, lang_id[0], [type], context=context)[type] or getattr(self, '_get_default_%s'%type)(cr, uid, context=context)
        return format
    
    def _get_db_format(self, cr, uid, type, context=None):
        '''
        generic function - for now constant values
        '''
        if context is None:
            context = {}
        if type == 'date':
            return '%Y-%m-%d'
        if type == 'time':
            return '%H:%M:%S'
        # default value
        return '%Y-%m-%d'
lang()


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
    
    def get_date_formatted(self, cr, uid, d_type='date', datetime=None, context=None):
        '''
        Return the datetime in the format of the user
        @param d_type: 'date' or 'datetime' : determines which is the out format
        @param datetime: date to format 
        '''
        assert d_type in ('date', 'datetime'), 'Give only \'date\' or \'datetime\' as type parameter'

        if not datetime:
            datetime = time.strftime('%Y-%m-%d')
        
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
    

class data_tools(osv.osv):
    '''
    data related tools for msf project
    '''
    _name = 'data.tools'
    
    def load_common_data(self, cr, uid, ids, context=None):
        '''
        load common data into context
        '''
        if context is None:
            context = {}
        context.setdefault('common', {})
        # objects
        date_tools = self.pool.get('date.tools')
        obj_data = self.pool.get('ir.model.data')
        comp_obj = self.pool.get('res.company')
        # date format
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        context['common']['db_date_format'] = db_date_format
        date_format = date_tools.get_date_format(cr, uid, context=context)
        context['common']['date_format'] = date_format
        # date is today
        date = time.strftime(db_date_format)
        context['common']['date'] = date
        # default company id
        company_id = comp_obj._company_default_get(cr, uid, 'stock.picking', context=context)
        context['common']['company_id'] = company_id
        # kit reason type
        reason_type_id = obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_kit')[1]
        context['common']['reason_type_id'] = reason_type_id
        # kitting location
        kitting_id = obj_data.get_object_reference(cr, uid, 'stock', 'location_production')[1]
        context['common']['kitting_id'] = kitting_id
        
        return True

data_tools()


class sequence_tools(osv.osv):
    '''
    sequence tools
    '''
    _name = 'sequence.tools'
    
    def reset_next_number(self, cr, uid, seq_ids, value=1, context=None):
        '''
        reset the next number of the sequence to value, default value 1
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(seq_ids, (int, long)):
            seq_ids = [seq_ids]
            
        # objects
        seq_obj = self.pool.get('ir.sequence')
        seq_obj.write(cr, uid, seq_ids, {'number_next': value}, context=context)
        return True
    
    def create_sequence(self, cr, uid, vals, name, code, prefix='', padding=0, context=None):
        '''
        create a new sequence
        '''
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')
        
        assert name, 'create sequence: missing name'
        assert code, 'create sequence: missing code'

        types = {'name': name,
                 'code': code
                 }
        seq_typ_pool.create(cr, uid, types)

        seq = {'name': name,
               'code': code,
               'prefix': prefix,
               'padding': padding,
               }
        return seq_pool.create(cr, uid, seq)
    
sequence_tools()
