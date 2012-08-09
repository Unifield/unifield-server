#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tools.translate import _

class account_subscription(osv.osv):
    _name = "account.subscription"
    _inherit = "account.subscription" 
    
    _columns = {
        'period_nbr': fields.integer('Periodicity', required=True, help="This field will determine how often entries will be generated: if the period type is 'month' and the periodicity '2' then entries will be generated every 2 months"),
    }
    
account_subscription()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
 