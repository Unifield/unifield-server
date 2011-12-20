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
from osv import fields
from lxml import etree

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    _columns = {
        'user_validated': fields.boolean(string="User validated?", help="Is this line validated by a user in a OpenERP field instance?", readonly=True),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Update tree view to display 'user_validated' field for HQ Entries View
        """
        if not context:
            context = {}
        view = super(account_move_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type=='tree' and context.get('from', False) == 'hq_entries':
            tree = etree.fromstring(view['arch'])
            fields = tree.xpath('/tree/field[@name="ref"]')
            if fields:
                field = fields[0]
                parent = field.getparent()
                parent.insert(parent.index(field)+1, etree.XML('<field name="user_validated"/>\n'))
                view['fields'].update(self.fields_get(cr, uid, fields=['user_validated'], context=context))
                view['arch'] = etree.tostring(tree)
        return view

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
