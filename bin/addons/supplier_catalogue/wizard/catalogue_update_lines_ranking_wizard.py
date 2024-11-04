# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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


class catalogue_update_lines_ranking_wizard(osv.osv_memory):
    _name = 'catalogue.update.lines.ranking.wizard'
    _description = 'Update the Ranking of all/selected Catalogue lines'

    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
        'selected': fields.boolean(string='Lines are selected'),
        'ranking': fields.selection([(1, '1st choice'), (2, '2nd choice'), (3, '3rd choice'), (4, '4th choice'),
                                     (5, '5th choice'), (6, '6th choice'), (7, '7th choice'), (8, '8th choice'),
                                     (9, '9th choice'), (10, '10th choice'), (11, '11th choice'), (12, '12th choice')], string='Ranking'),
    }

    def update_lines_ranking_selected(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        return self.update_lines_ranking(cr, uid, ids, context=context, selected=True)

    def update_lines_ranking(self, cr, uid, ids, context=None, selected=None):
        '''
        Update the ranking of the selected/all supplier catalogue lines
        '''
        if not context:
            context = {}

        cat_line_obj = self.pool.get('supplier.catalogue.line')

        for wiz in self.read(cr, uid, ids, ['catalogue_id', 'ranking'], context=context):
            domain = [('catalogue_id', '=', wiz['catalogue_id'])]
            if selected and context.get('button_selected_ids'):
                domain.append(('id', 'in', context['button_selected_ids']))
            cat_line_ids = cat_line_obj.search(cr, uid, domain, context=context)
            if cat_line_ids:
                cat_line_obj.write(cr, uid, cat_line_ids, {'ranking': wiz['ranking']}, context=context)

        return {'type': 'ir.actions.act_window_close'}


catalogue_update_lines_ranking_wizard()
