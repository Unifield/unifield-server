# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import osv, fields

class wizard_add_cost_centers(osv.osv_memory):
    _name = 'wizard.add.cost.centers'
    _description = 'Add Cost Centers'

    _columns = {
        'cost_center_ids': fields.many2many('account.analytic.account', 'wizard_add_cost_centers', 'wizard_id', 'cost_center_id', string='Cost Centers To Synchronize', domain="[('category', '=', 'OC'), ('is_instance_registered', '=', True)]", required=True),
    }

    def add_cost_centers(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        instance_obj = self.pool.get('msf.instance')
        # create vals
        for wizard in self.browse(cr, uid, ids, context=context):
            target_cost_center_values = []
            for cost_center in wizard.cost_center_ids:
                self.pool.get('account.target.costcenter').create(cr, uid, {'instance_id': context['active_id'],
                                                                            'cost_center_id': cost_center.id,
                                                                            'target': False}, context=context)
        return {'type' : 'ir.actions.act_window_close'}
        
wizard_add_cost_centers()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
