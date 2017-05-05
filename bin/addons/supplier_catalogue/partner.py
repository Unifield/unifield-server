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

from tools.translate import _


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def _get_bool_cat(self, cr, uid, ids, field, arg, context=None):
        res = {}
        for part in self.browse(cr, uid, ids, context=context):
            if part.catalogue_ids:
                res[part.id] = 'Yes'
            else:
                res[part.id] = 'No'
        return res
    
    _columns = {
        'catalogue_ids': fields.one2many('supplier.catalogue', 'partner_id', string='Catalogues', readonly=True),
        'catalogue_bool': fields.function(_get_bool_cat, type='char', method=True, string='Catalogue'),
    }

    def copy(self, cr, uid, partner_id, defaults=None, context=None):
        if not defaults:
            defaults = {}
        defaults['catalogue_ids'] = []

        return super(res_partner, self).copy(cr, uid, partner_id, defaults, context=context)
    
res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
