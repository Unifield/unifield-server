# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from os import path
from tools.translate import _

from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from msf_doc_import.wizard import AUTO_SUPPLY_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_auto_supply
from msf_doc_import.wizard import AUTO_SUPPLY_LINE_COLUMNS_FOR_IMPORT as columns_for_auto_supply
from msf_doc_import.wizard import ORDER_CYCLE_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_order_cycle
from msf_doc_import.wizard import ORDER_CYCLE_LINE_COLUMNS_FOR_IMPORT as columns_for_order_cycle
from msf_doc_import.wizard import THRESHOLD_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_threshold
from msf_doc_import.wizard import THRESHOLD_LINE_COLUMNS_FOR_IMPORT as columns_for_threshold
from msf_doc_import.wizard import STOCK_WAREHOUSE_ORDERPOINT_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_stock_warehouse_orderpoint
from msf_doc_import.wizard import STOCK_WAREHOUSE_ORDERPOINT_LINE_COLUMNS_FOR_IMPORT as columns_for_stock_warehouse_orderpoint
from msf_doc_import import GENERIC_MESSAGE

import base64


class automatic_supply_rule(osv.osv):
    """
    We override the class for import of Automatic supply rule lines
    """
    _inherit = 'stock.warehouse.automatic.supply'

    def wizard_import_auto_supply_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        # Objects
        wiz_obj = self.pool.get('wizard.import.auto.supply.line')

        context = context is None and {} or context

        if isinstance(ids, (int, long)):
            ids = [ids]

        context.update({'active_id': ids[0]})

        rule = self.browse(cr, uid, ids[0], context=context)
        header_cols = columns_header_for_auto_supply
        cols = columns_for_auto_supply

        columns_header = [(_(f[0]), f[1]) for f in header_cols]
        default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = wiz_obj.create(cr, uid, {'file': file,
                                             'filename_template': 'Auto Supply template.xls',
                                             'filename': 'Lines_Not_Imported.xls',
                                             'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in cols])),
                                             'rule_id': ids[0],
                                             'state': 'draft',}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.auto.supply.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

automatic_supply_rule()


class order_cycle_rule(osv.osv):
    """
    We override the class for import of Order cycle rule lines
    """
    _inherit = 'stock.warehouse.order.cycle'

    def wizard_import_order_cycle_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        # Objects
        wiz_obj = self.pool.get('wizard.import.order.cycle.line')

        context = context is None and {} or context

        if isinstance(ids, (int, long)):
            ids = [ids]

        context.update({'active_id': ids[0]})

        rule = self.browse(cr, uid, ids[0], context=context)
        header_cols = columns_header_for_order_cycle
        cols = columns_for_order_cycle

        columns_header = [(_(f[0]), f[1]) for f in header_cols]
        default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = wiz_obj.create(cr, uid, {'file': file,
                                             'filename_template': 'Order Cycle template.xls',
                                             'filename': 'Lines_Not_Imported.xls',
                                             'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in cols])),
                                             'rule_id': ids[0],
                                             'state': 'draft',}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.order.cycle.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

order_cycle_rule()


class threshold_value_rule(osv.osv):
    """
    We override the class for import of Threshold value rule lines
    """
    _inherit = 'threshold.value'

    def wizard_import_threshold_value_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        # Objects
        wiz_obj = self.pool.get('wizard.import.threshold.value.line')

        context = context is None and {} or context

        if isinstance(ids, (int, long)):
            ids = [ids]

        context.update({'active_id': ids[0]})

        rule = self.browse(cr, uid, ids[0], context=context)
        header_cols = columns_header_for_threshold
        cols = columns_for_threshold

        columns_header = [(_(f[0]), f[1]) for f in header_cols]
        default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = wiz_obj.create(cr, uid, {'file': file,
                                             'filename_template': 'Threshold value template.xls',
                                             'filename': 'Lines_Not_Imported.xls',
                                             'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in cols])),
                                             'rule_id': ids[0],
                                             'state': 'draft',}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.threshold.value.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

threshold_value_rule()


class stock_warehouse_orderpoint_rule(osv.osv):
    """
    We override the class for import of Automatic supply rule lines
    """
    _inherit = 'stock.warehouse.orderpoint'

    def wizard_import_stock_warehouse_line(self, cr, uid, ids, context=None):
        """
        Launches the wizard to import lines from a file
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Objects
        wiz_obj = self.pool.get('wizard.import.stock.warehouse.orderpoint.line')

        context.update({'active_id': ids[0]})

        rule = self.browse(cr, uid, ids[0], context=context)
        header_cols = columns_header_for_stock_warehouse_orderpoint
        cols = columns_for_stock_warehouse_orderpoint

        columns_header = [(_(f[0]), f[1]) for f in header_cols]
        default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = wiz_obj.create(cr, uid, {'file': file,
                                             'filename_template': 'Minimum Stock Rules template.xls',
                                             'filename': 'Lines_Not_Imported.xls',
                                             'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in cols])),
                                             'rule_id': ids[0],
                                             'state': 'draft',}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.stock.warehouse.orderpoint.line',
            'res_id': export_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'crush',
            'context': context,
        }

stock_warehouse_orderpoint_rule()
