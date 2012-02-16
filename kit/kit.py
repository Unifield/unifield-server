# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import netsvc
import logging
import tools
from os import path

KIT_COMPOSITION_STATE = [('draft', 'Draft'),
                         ('completed', 'Completed'),
                         ('explosed', 'Explosed'),
                         ]

KIT_COMPOSITION_TYPE = [('theoretical', 'Theoretical'),
                        ('real', 'Real'),
                        ]

class composition_kit(osv.osv):
    '''
    kit composition class, representing both theoretical composition and actual ones
    '''
    _name = 'composition.kit'

    _columns = {'name': fields.char(string='Reference', size=1024),
                'composition_type': fields.selection(KIT_COMPOSITION_TYPE, string='Composition Type', readonly=True),
                'composition_description': fields.text(string='Composition Description'),
                }
    
    _defaults = {}
     
composition_kit()
