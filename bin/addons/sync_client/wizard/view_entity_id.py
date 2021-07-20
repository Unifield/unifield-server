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
from tools.translate import _


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
            entity = self.pool.get("sync.client.entity").get_entity(cr, uid, context=context)
            hw_id = entity._hardware_id or ''
            last_seq = entity.update_last or ''

            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//p[@id='name']")
            if nodes:
                nodes[0].text = 'Hardware ID: %s' % hw_id
            nodes = doc.xpath("//p[@id='sequence']")
            if nodes:
                nodes[0].text = _('Last update sequence pulled: %s') % last_seq

            last_update_match = None
            try:
                conn = self.pool.get("sync.client.sync_server_connection")
                conn.get_connection_from_config_file(cr, uid, context=context)
                proxy = conn.get_connection(cr, uid, "sync.server.entity")
                last_upd = proxy.get_last_update(entity.identifier, context)
                if last_upd and last_upd[0]:
                    # does not work if multiple pulled aborted ....
                    last_update_match = last_upd[1] == last_seq or last_upd[1] + 1 == last_seq  # +1 if last sync upd pull aborted
            except:
                pass

            status = {
                None: ('/openerp/static/images/warning-orange-48.png', _('Unable to retrieve the update sequence from the sync server, please check the Connection Manager.')),
                True: ('/openerp/static/images/green-48.png', _('Last update sequence pulled by this instance matches the sequence on the sync server.')),
                False: ('/openerp/static/images/warning-red-48.png', _('Last update sequence pulled by this instance does not match the sequence on the sync server. Please do not use this instance and contact UF Support.')),
            }
            img = doc.xpath("//img")
            img[0].set('src', status[last_update_match][0])
            msg = doc.xpath("//span[@id='sync-text']")
            msg[0].text = status[last_update_match][1]

            res['arch'] = etree.tostring(doc)

        return res

view_entity_id()
