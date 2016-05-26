# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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


class res_company(osv.osv):
    _inherit = 'res.company'

    _columns = {
        'sync_lock': fields.boolean(
            string='Synchronization locked',
        ),
    }

    _defaults = {
        'sync_lock': False,
    }

    def lock(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'sync_lock': True}, context=context)

    def unlock(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'sync_lock': False}, context=context)

res_company()
