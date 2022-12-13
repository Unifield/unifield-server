# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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
from tools.translate import _


class modify_expiry_date(osv.osv_memory):
    '''
    wizard called to confirm an action
    '''
    _name = "modify.expiry.date"
    _columns = {'kit_id': fields.many2one('composition.kit', string='Composition List', readonly=True),
                'date': fields.date(string='Date', readonly=True),
                'new_date': fields.date(string='New Date', help="When using automatic computation, if no date are found in the kit components, the default value is 01/Jan/9999."),
                }

    _defaults = {'kit_id': lambda s, cr, uid, c: c.get('kit_id', False),
                 'date': lambda s, cr, uid, c: c.get('date', False)}

    def compute_date(self, cr, uid, ids, context=None):
        '''
        compute the date from items and write it to the wizard
        '''
        if context is None:
            context = {}
        # objects
        kit_obj = self.pool.get('composition.kit')
        kit_ids = context['active_ids']
        new_date = kit_obj._compute_expiry_date(cr, uid, kit_ids, context=context)
        self.write(cr, uid, ids, {'new_date': new_date}, context=context)
        return True

    def do_modify_expiry_date(self, cr, uid, ids, context=None):
        '''
        create a purchase order line for each kit item and delete the selected kit purchase order line
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        kit_obj = self.pool.get('composition.kit')
        data_obj = self.pool.get('ir.model.data')
        kit_ids = context['active_ids']
        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.new_date:
                raise osv.except_osv(_('Warning !'), _('You need to specify a new date.'))
            kit_obj.write(cr, uid, kit_ids, {'composition_exp': obj.new_date}, context=context)

        view_id = data_obj.get_object_reference(cr, uid, 'kit', 'view_composition_kit_real_form')[1]
        tree_view_id = data_obj.get_object_reference(cr, uid, 'kit', 'view_composition_kit_real_tree')[1]
        return {'type': 'ir.actions.act_window',
                'res_model': 'composition.kit',
                'view_id': [view_id, tree_view_id],
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': kit_ids[0],
                'target': 'crunch',
                'context': context}


modify_expiry_date()
