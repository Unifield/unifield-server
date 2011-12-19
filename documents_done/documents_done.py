# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

import tools

from osv import osv
from osv import fields
from tools.translate import _

class documents_done_wizard(osv.osv):
    _name = 'documents.done.wizard'
    _description = 'Documents not \'Done\''
    _auto = False
    
    def _get_state(self, cr, uid, ids, field_name, args, context={}):
        return {}
    
    def _search_state(self, cr, uid, ):
    
    _columns = {
        'name': fields.char(size=256, string='Name', readonly=True),
        'doc_type': fields.selection([('sale.order', 'Sale Order'),
                                      ('purchase.order', 'Purchase Order'),
                                      ('internal.request', 'Internal Request'),
                                      ('rfq', 'Request for Quotation'),
                                      ('tender', 'Tender')], string='Doc. Type', readonly=True),
        'creation_date': fields.date(string='Creation date', readonly=True),
        'expected_date': fields.date(string='Expected date', readonly=True),
        'partner_id': fields.many2one('res.partner', string='Partner', readonly=True),
        'state': fields.char(size=64, string='State', readonly=True),
        'display_state': fields.function(_get_state, fnct_search=_search_state, type='selection', selection=_get_selection,
                                         method=True, store=False, readonly=True),
    }
    
    def init(self, cr):
        '''
        Create the view
        '''
        tools.drop_view_if_exists(cr, 'documents_done_wizard')
        cr.execute("""CREATE OR REPLACE VIEW documents_done_wizard AS (
                SELECT
                    row_number() OVER(ORDER BY name) AS id,
                    dnd.name,
                    dnd.doc_type,
                    dnd.state,
                    dnd.creation_date,
                    dnd.expected_date,
                    dnd.partner_id
                FROM
                    ((SELECT
                        so.name AS name,
                        'sale.order' AS doc_type,
                        so.state AS state,
                        so.date_order AS creation_date,
                        so.delivery_requested_date AS expected_date,
                        so.partner_id AS partner_id
                    FROM
                        sale_order so
                    WHERE
                        state NOT IN ('done', 'cancel')
                      AND
                        procurement_request = False)
                UNION
                    (SELECT
                        ir.name AS name,
                        'internal.request' AS doc_type,
                        ir.state AS state,
                        ir.date_order AS creation_date,
                        ir.delivery_requested_date AS expected_date,
                        NULL AS partner_id
                    FROM
                        sale_order ir
                    WHERE
                        state NOT IN ('procurement_done', 'procurement_cancel')
                      AND
                        procurement_request = True)
                UNION
                    (SELECT
                        po.name AS name,
                        'purchase.order' AS doc_type,
                        po.state AS state,
                        po.date_order AS creation_date,
                        po.delivery_requested_date AS expected_date,
                        po.partner_id AS partner_id
                    FROM
                        purchase_order po
                    WHERE
                        state NOT IN ('done', 'cancel')
                      AND
                        rfq_ok = False)
                UNION
                    (SELECT
                        rfq.name AS name,
                        'rfq' AS doc_type,
                        rfq.state AS state,
                        rfq.date_order AS creation_date,
                        rfq.delivery_requested_date AS expected_date,
                        rfq.partner_id AS partner_id
                    FROM
                        purchase_order rfq
                    WHERE
                        state NOT IN ('done', 'cancel')
                      AND
                        rfq_ok = True)
                UNION
                    (SELECT
                        t.name AS name,
                        'tender' AS doc_type,
                        t.state AS state,
                        t.creation_date AS creation_date,
                        t.requested_date AS expected_date,
                        NULL AS partner_id
                    FROM
                        tender t
                    WHERE
                        state NOT IN ('done', 'cancel'))) AS dnd
        );""")
    
documents_done_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
