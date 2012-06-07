#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

class res_company(osv.osv):
    _name = 'res.company'
    _inherit = 'res.company'

    _columns = {
        'instance_id': fields.many2one('msf.instance', string="Proprietary Instance", 
            help="Representation of the current instance"),
    }
    
    def _refresh_objects(self, cr, uid, object_name, old_instance_id, new_instance_id, context=None):
        object_ids = self.pool.get(object_name).search(cr,
                                                       uid,
                                                       [('instance_id', '=', old_instance_id)],
                                                       context=context)
        self.pool.get(object_name).write(cr,
                                         uid,
                                         object_ids,
                                         {'instance_id': new_instance_id},
                                         context=context)
        return
    
    def write(self, cr, uid, ids, vals, context=None):
        instance_obj = self.pool.get('msf.instance')
        if 'instance_id' in vals:
            # only one company (unicity)
            if len(ids) != 1:
                raise osv.except_osv(_('Error'), _("Only one company per instance!") or '')
            company = self.browse(cr, uid, ids[0], context=context)
            if not company.instance_id:
                # An instance was not set; add DB name and activate it
                instance_obj.write(cr, uid, [vals['instance_id']], {'instance': cr.dbname,
                                                                    'state': 'active'}, context=context)
            else:
                # An instance was already set
                old_instance_id = company.instance_id.id
                # Deactivate the instance
                instance_obj.write(cr, uid, [old_instance_id], {'state': 'inactive'}, context=context)
                # add DB name and activate it
                instance_obj.write(cr, uid, [vals['instance_id']], {'instance': cr.dbname,
                                                                    'state': 'active'}, context=context)
                # refresh all objects
                for object in ['account.analytic.journal', 'account.journal', 'account.analytic.line', 'account.move', 'account.move.line', 'account.bank.statement']:
                    self._refresh_objects(cr, uid, object, old_instance_id, vals['instance_id'], context=context)
                
res_company()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
