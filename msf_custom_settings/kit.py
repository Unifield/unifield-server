#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF, Smile. All Rights Reserved
#    All Rigts Reserved
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
from tools.translate import _

class composition_kit(osv.osv):
    _inherit = 'composition.kit'
    _name = 'composition.kit'
    
    def action_cancel(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        kit_obj = self.pool.get('composition.kit')
        if not kit_obj.read(cr, uid, ids, ['state'], context=context)[0]['state'] == 'in_production':
            self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        else:
            raise osv.except_osv(_('Warning !'), _('You cannot cancel a composition list if it is in production.'))
        return True

composition_kit()