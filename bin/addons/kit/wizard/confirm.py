# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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
import decimal_precision as dp

import netsvc


class confirm(osv.osv_memory):
    '''
    wizard called to confirm an action
    '''
    _name = "confirm"
    _columns = {'question': fields.text(string='Question', readonly=True),
                'display_close_confirm': fields.boolean(string='Display Close Button', readonly=True),
                'display_back_confirm': fields.boolean(string='Display Back Button', readonly=True),
                }
    
    _defaults = {'question': lambda s, cr, uid, c: c.get('question', False),
                 'display_close_confirm': lambda s, cr, uid, c: c.get('display_close_confirm', True), # by default, we display close
                 'display_back_confirm': lambda s, cr, uid, c: c.get('display_back_confirm', False), # by default, we do not display back
                 }

    def back_step(self, cr, uid, ids, context=None):
        '''
        call back step wizard
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        
        wiz_obj = self.pool.get('wizard')
        # no data for type 'back'
        return wiz_obj.open_wizard(cr, uid, context['active_ids'], w_type='back', context=context)

    def do_action(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # clazz
        clazz = context['callback']['clazz']
        obj = self.pool.get(clazz)
        # function
        func = context['callback']['func']
        # args
        args = context['callback']['args']
        # kwargs
        kwargs = context['callback']['kwargs']
        # callback
        res = getattr(obj, func)(cr, uid, *args, context=context, **kwargs)
        # return result from callback function
        return res
    
confirm()
