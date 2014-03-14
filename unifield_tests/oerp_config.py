#!/usr/bin/env python
#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF. All Rights Reserved
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
from osv import fields

class oerp_config(osv.osv):
    _name = "unifield.test"
    _description = "List of Unifield tests"

    _columns = {
        'name': fields.char('Name', size=512, required=True, translate=False),
        'active': fields.boolean('Active?', readonly=True),
    }

    _defaults = {
        'active': lambda *a: True,
    }

    _sql_constraints = [
        ('unifield_test_name_uniq', 'unique (name)', 'You cannot have 2 unifield test with the same name!')
    ]

oerp_config()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
