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

from osv import osv, fields

class stock_location_confirm_deactivation(osv.osv_memory):
    _name = 'stock.location.confirm.deactivation'

    _columns = {
        'location_id': fields.many2one('stock.location', string='Stock location to deactive'),
        'message': fields.text('Message'),
    }

    def confirm_deactivation(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            self.pool.get('stock.location').write(cr, uid, [wiz.location_id.id], {'active': False}, context=context)

        return {'type': 'ir.actions.act_window_close'}


    def close_wizard(self, cr, uid, ids, context=None):
        '''
        Just close the wizard
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        return {'type': 'ir.actions.act_window_close'}


stock_location_confirm_deactivation()
