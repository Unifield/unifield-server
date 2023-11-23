# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv


class related_sourcing(osv.osv):
    """
    This object is used to link sourcing lines on a same PO to the same
    supplier. If most sourcing lines are sourced to the same supplier but
    have different related.sourcing, one PO per related.sourcing will be
    created with all lines linked to this related.sourcing.
    """
    _name = 'related.sourcing'
    _description = 'Sourcing group'

    _columns = {
        'name': fields.char(
            size=128,
            string='Name',
            required=True,
        ),
        'description': fields.text(
            string='Description',
        ),
    }

    def create(self, cr, uid, vals, context=None):
        """
        Format the name value
        """
        vals['name'] = ''.join(filter(str.isalnum, vals.get('name', ''))).upper()
        return super(related_sourcing, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Format the name value
        """
        if not ids:
            return True
        vals['name'] = ''.join(filter(str.isalnum, vals.get('name', ''))).upper()
        return super(related_sourcing, self).write(cr, uid, ids, vals, context=context)


related_sourcing()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
