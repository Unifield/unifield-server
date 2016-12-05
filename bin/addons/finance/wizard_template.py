#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 TeMPO Consulting, MSF. All Rights Reserved
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


class wizard_template(osv.osv):
    _name = 'wizard.template'
    _description = 'Wizard Template'

    _columns = {
        'name': fields.char('Template name', size=128, required=True),
        'user_id': fields.many2one('res.users', string='User', ondelete='cascade', required=True),
        'wizard_name': fields.char('Wizard name', size=256, required=True),
        'values': fields.text('Values', help='Values from the wizard, stored as a dictionary'),
    }


wizard_template()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
