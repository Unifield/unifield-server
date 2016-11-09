# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

class wizard_valid_line(osv.osv_memory):
    _name = 'wizard.valid.line'

    _columns = {
        'mrc_id': fields.many2one('monthly.review.consumption', string='MRC'),
        'line_ids': fields.many2many('monthly.review.consumption.line', 'wizard_review_line_rel',
				     'wizard_id', 'line_id', string='Lines',),
    }

    def select_all_lines(self, cr, uid, ids, context=None):
        '''
        Select all lines of the selected report
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

	for wiz in self.browse(cr, uid, ids, context=context):
            line_ids = []
            for line in wiz.mrc_id.line_ids:
                if not line.valid_ok:
                    line_ids.append(line.id)

            self.write(cr, uid, [wiz.id], {'line_ids': [(6,0,line_ids)]}, context=context)

	return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.valid.line',
                'res_id': ids[0],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def valid_lines(self, cr, uid, ids, context=None):
        '''
        Valid all lines
        '''
        if not context:
            context = {}

        if isinstance(ids, (int,long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.line_ids:
                self.pool.get('monthly.review.consumption.line').valid_line(cr, uid, line.id, context=context)
              
	return {'type': 'ir.actions.act_window',
                'res_model': 'monthly.review.consumption',
                'res_id': wiz.mrc_id.id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'dummy',
                'context': context}

wizard_valid_line()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
