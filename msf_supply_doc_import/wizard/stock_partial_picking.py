
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF
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

from osv import fields, osv
from tools.translate import _
# xml parser
from lxml import etree

class stock_partial_picking(osv.osv_memory):
    """
    Enables to choose the location for IN (selection of destination for incoming shipment)
    and OUT (selection of the source for delivery orders and picking ticket)
    """
    _inherit = "stock.partial.picking"

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml, *.xls',
                                        help="""* You can use the template of the export for the format that you need to use.
                                                * The file should be in XML Spreadsheet 2003 format."""),
        'file_error': fields.binary(string='Lines not imported',
                                    help="""* This file caught the line that were not imported."""),
        'import_error_ok': fields.boolean(string='Error at import', readonly=True),
    }

    def import_file(self, cr, uid, ids, context=None):
        return

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add the field "file_to_import" for the wizard 'incoming shipment' with the button "import_file"
        '''
        if not context:
            context = {}
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type='form', context=context, toolbar=toolbar, submenu=submenu)
        picking_obj = self.pool.get('stock.picking')
        picking_id = context.get('active_ids')
        if view_type == 'form' and picking_id:
            form = etree.fromstring(result['arch'])
            picking_id = picking_id[0]
            data = picking_obj.read(cr, uid, [picking_id], ['type'], context=context)
            picking_type = data[0]['type']
            new_field_txt = """
            <newline/>
            <group name="import_file_lines" string="Import Lines" colspan="4" col="8">
            <field name="file_to_import"/>
            <button name="import_file" string="Import the file" icon="gtk-execute" colspan="2" type="object" />
            <field name="file_error" attrs="{'invisible':[('import_error_ok', '=', True)]}"/>
            <field name="import_error_ok" invisible="0"/>
            </group>
            """
            # add field in arch
            arch = result['arch']
            l = arch.split('<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>')
            arch = l[0]
            arch += '<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>' + new_field_txt + l[1]
            print arch
            result['arch'] = arch
                
        return result

stock_partial_picking()