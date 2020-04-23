# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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


class tender_change_currency(osv.osv_memory):
    _name = 'tender.change.currency'

    _columns = {
        'tender_id': fields.many2one('tender', string='Tender', required=True),
        'old_currency_id': fields.many2one('res.currency', string='Old currency', required=True, readonly=True),
        'new_currency_id': fields.many2one('res.currency', string='New currency', required=True),
    }

    def cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        return {'type': 'ir.actions.act_window_close'}

    def apply_to_lines(self, cr, uid, ids, context=None):
        '''
        Apply the conversion on lines
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        c = context.copy()
        c.update({'update_merge': True})

        currency_obj = self.pool.get('res.currency')
        tender_obj = self.pool.get('tender')
        line_obj = self.pool.get('tender.line')

        for wiz in self.browse(cr, uid, ids, context=context):
            tender_obj.write(cr, uid, wiz.tender_id.id, {'currency_id': wiz.new_currency_id.id}, context=context)
            self.infolog(cr, uid, _('The currency of the Tender id:%s (%s) has been changed from id:%s (%s) to id:%s (%s)') % (
                wiz.tender_id.id, wiz.tender_id.name, wiz.old_currency_id.id, wiz.old_currency_id.name,
                wiz.new_currency_id.id, wiz.new_currency_id.name,
            ))

        return {'type': 'ir.actions.act_window_close'}


tender_change_currency()
