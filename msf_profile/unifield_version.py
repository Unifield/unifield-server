# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import release


class unifield_version(osv.osv_memory):
    _name = 'unifield.version'
    _rec_name = 'version'

    def default_get(self, cr, uid, field_list=[], context=None):
        res = super(unifield_version, self).default_get(cr, uid, field_list, context=context)
        revisions = self.pool.get('sync_client.version')
        currev = revisions._get_last_revision(cr, uid, context=context)
        res['version']=currev.name
        return res

    _columns = {
        'version': fields.char(
            size=128,
            string='Version',
            readonly=True,
        ),
    }

unifield_version()
