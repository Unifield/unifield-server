# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2012 MSF, TeMPO Consulting, Smile
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

class stock_location(osv.osv):
    '''
    override stock location to add:
    - cross_docking location (checkbox - boolean)
    '''
    _inherit = 'stock.location'
    
    _columns = {'cross_docking_location_ok': fields.boolean(string='Cross Docking Location', readonly=True, help="There is only one Cross Docking Location"),
                }
    
    #Check that the location cross docking exists only once
    _sql_constraints = [('unique_cross_docking', 'unique(cross_docking_location_ok)','Cross docking location must be unique')]
    
    def unlink(self, cr, uid, ids, context=None):
        cross_docking_location = self.search(cr, uid, [('name', 'ilike', 'Cross docking'), ('cross_docking_location_ok', '=', True) ], context=context)[0]
        if self.read(cr,uid, ids, ['id'], context=context)[0]['id'] == cross_docking_location:
            raise osv.except_osv(_('Warning !'), _('You cannot delete this cross docking location because it should be the only one that exists.'))
        return super(stock_location, self).unlink(cr, uid, ids, context)

stock_location()
