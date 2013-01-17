#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Max Mumford
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

class view_config(osv.osv_memory):
    _name = 'msf_access_rights.view_config'
    _inherit = 'res.config' 

    def execute(self, cr, uid, ids, context=None):
        """
        Perform a write (With no updated values) on each view in the database to trigger the Button Access Rule creation process
        """
        view_pool = self.pool.get('ir.ui.view')
        view_ids = view_pool.search(cr, uid, [])
        for id in view_ids:
            view_pool.write(cr, uid, id, {})
        
view_config()