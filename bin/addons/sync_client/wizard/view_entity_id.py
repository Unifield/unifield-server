# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
from lxml import etree


class view_entity_id(osv.osv_memory):
    _name = "sync.client.view_entity_id"

    _columns = {
        'name':fields.char('Entity Id', size=256, required=True),
    }

    _defaults = {
        'name' : lambda self, *a : self.pool.get("sync.client.entity")._hardware_id,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        res = super(view_entity_id, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            hw_id = self.pool.get("sync.client.entity")._hardware_id or ''

            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//label[@string]")
            if nodes:
                nodes[0].set('string', hw_id)
            res['arch'] = etree.tostring(doc)

        return res

view_entity_id()
