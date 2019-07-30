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
from tools.translate import _

# xml parser
from lxml import etree

class stock_partial_picking(osv.osv_memory):
    _name = 'stock.partial.picking'
    _inherit = 'stock.partial.picking'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)

        if not picking_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result

        # is it possible to register a claim - internal + chained picking from incoming shipment
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            register_ok = pick.chained_from_in_stock_picking

        if register_ok:
            # load the xml tree
            root = etree.fromstring(result['arch'])
            # get the original empty separator ref and hide it
            # set the separator as invisible
            list = ['//separator[@string=""]']
            fields = []
            for xpath in list:
                fields = root.xpath(xpath)
                if not fields:
                    raise osv.except_osv(_('Warning !'), _('Element %s not found.') % xpath)
                for field in fields:
                    field.set('string', 'Register a Claim to the Supplier for selected products.')
            # get separator index within xml tree
            separator_index = root.index(fields[0])
            # new view structure
            new_tree_txt = '''
                            <notebook colspan="4">
                            <page string="Claim">
                            <field name="register_a_claim_partial_picking"/><field name="in_has_partner_id_partial_picking" invisible="True" />
                            <field name="partner_id_partial_picking" attrs="{\'readonly\': ['|', (\'register_a_claim_partial_picking\', \'=\', False), (\'in_has_partner_id_partial_picking\', \'=\', True)]}"
                                    context="{'search_default_supplier': True}"/>
                            <field name="claim_type_partial_picking" attrs="{\'readonly\': [(\'register_a_claim_partial_picking\', \'=\', False)]}"/>
                            <field name="replacement_picking_expected_partial_picking" attrs="{\'invisible\': [(\'claim_type_partial_picking\', \'not in\', ('return', 'surplus'))]}"/>
                            </page>
                            <page string="Claim Description">
                            <field name="description_partial_picking" colspan="4" nolabel="True"/>
                            </page>
                            </notebook>
                            '''
            # generate xml tree
            new_tree = etree.fromstring(new_tree_txt)
            # insert new tree just after separator index position
            root.insert(separator_index + 1, new_tree)
            # generate xml back to string
            result['arch'] = etree.tostring(root)

        return result


stock_partial_picking()
