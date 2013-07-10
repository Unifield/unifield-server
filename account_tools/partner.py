#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv

def get_partner_id_from_vals(self, cr, uid, vals, context=None):
    """
    Search for partner_id in given vals
    """
    # Prepare some values
    res = False
    # Do some checks
    if not vals:
        return res
    if not context:
        context = {}
    if vals.get('partner_id', False):
        res = vals.get('partner_id')
    elif vals.get('partner_type', False):
        p_type = vals.get('partner_type').split(',')
        if p_type[0] == 'res.partner' and p_type[1]:
            if isinstance(p_type[1], str):
                p_type[1] = int(p_type[1])
            res = p_type[1]
    return res

class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def get_partner_id_from_vals(self, cr, uid, vals, context=None):
        """
        Search for partner_id in given vals
        """
        return get_partner_id_from_vals(self, cr, uid, vals, context)

res_partner()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
