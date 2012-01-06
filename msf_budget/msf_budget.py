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

from osv import fields, osv

class msf_budget(osv.osv):
    _name = "msf.budget"
    
    _columns={
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', required=True),
        'state': fields.selection([('draft','Draft'),('validate','Validated'),('done','Done')], 'State', select=True, required=True),
        'cost_center_id': fields.many2one('account.analytic.account', 'Cost Center', domain=[('category', '=', 'OC'), ('type', '=', 'normal')], required=True),
        'decision_moment': fields.char('Decision Moment', size=32, required=True),
        'version': fields.integer('Version',required=True),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'latest_version': fields.boolean('Latest version')
    }
    
    _defaults = {
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'version': 1,
        'state': 'draft',
    }
    
    def unlink(self, cr, uid, ids, context=None):
        # if a "latest version" budget is deleted, set the flag on the previous budget (if existing)
        for budget in self.browse(cr, uid, ids, context=context):
            previous_budget_ids =  self.search(cr,
                                               uid,
                                               [('code','=',budget.code),
                                                ('name','=',budget.name),
                                                ('fiscalyear_id','=',budget.fiscalyear_id.id),
                                                ('cost_center_id','=',budget.cost_center_id.id),
                                                ('version','=',budget.version - 1)],
                                               context=context)
            if len(previous_budget_ids) > 0:
                self.write(cr, uid, [previous_budget_ids[0]], {'latest_version': True}, context=context)
        return super(msf_budget, self).unlink(cr, uid, ids, context=context)

msf_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
