# -*- coding: utf-8 -*-

import base64
import time
from dateutil.parser import parse
import math
import tools

import decimal_precision as dp
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

from osv import fields, osv
from tools.misc import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from tools.translate import _


PHYSICAL_INVENTORIES_STATES = (
    ('draft', _('Draft')),
    ('counting', _('Counting')),
    ('counted', _('Counted')),
    ('validated', _('Validated')),
    ('confirmed', _('Confirmed')),
    ('closed', _('Closed')),
    ('cancel', _('Cancelled'))
)


class NegativeValueError(ValueError):
    """Negative value Exception"""


class PhysicalInventory(osv.osv):
    _name = 'physical.inventory'
    _description = 'Physical Inventory'
    _order = "id desc, date desc"

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if context.get('button') in ('import_xls_discrepancy_report', 'import_counting_sheet') and '__last_update' in context:
            del context['__last_update']
        return super(PhysicalInventory, self).write(cr, uid, ids, vals, context)

    def _inventory_totals(self, cr, uid, ids, field_names, arg, context=None):
        context = context is None and {} or context
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)

        inventories = read_many("physical.inventory", ids, ["discrepancy_line_ids",
                                                            "counting_line_ids"])

        totals = {}
        for inventory in inventories:

            counting_lines = read_many("physical.inventory.counting",
                                       inventory["counting_line_ids"],
                                       ["quantity", "standard_price"])

            # Keep only non-ignored lines
            discrepancy_line_ids = search("physical.inventory.discrepancy",
                                          ['&',
                                           ('ignored', '!=', True),
                                           ("id", "in", inventory["discrepancy_line_ids"])])

            discrepancy_lines = read_many("physical.inventory.discrepancy",
                                          discrepancy_line_ids,
                                          ["discrepancy_value"])

            inventory_lines_value = 0
            inventory_lines_absvalue = 0
            for l in counting_lines:
                try:
                    inventory_lines_value += float(l["quantity"]) * float(l["standard_price"])
                    inventory_lines_absvalue += abs(float(l["quantity"])) * float(l["standard_price"])
                except:
                    # Most likely we couldnt parse the quantity / price...
                    pass

            discrepancy_lines_value = 0
            discrepancy_lines_absvalue = 0
            for l in discrepancy_lines:
                try:
                    discrepancy_lines_value += float(l["discrepancy_value"])
                    discrepancy_lines_absvalue += abs(float(l["discrepancy_value"]))
                except:
                    # Most likely we couldnt parse the quantity / price...
                    pass

            total = {
                'inventory_lines_number': len(counting_lines),
                'discrepancy_lines_number': len(discrepancy_lines),
                'inventory_lines_value': inventory_lines_value,
                'discrepancy_lines_value': discrepancy_lines_value,
                'inventory_lines_absvalue': inventory_lines_absvalue,
                'discrepancy_lines_absvalue':discrepancy_lines_absvalue
            }

            total['discrepancy_lines_percent'] = 100 * total['discrepancy_lines_number'] / total['inventory_lines_number'] if total['inventory_lines_number'] else 0.0
            total['discrepancy_lines_percent_value'] = 100 * total['discrepancy_lines_value'] / total['inventory_lines_value'] if total['inventory_lines_value'] else 0.0
            total['discrepancy_lines_percent_absvalue'] = 100 * total['discrepancy_lines_absvalue'] / total['inventory_lines_absvalue'] if total['inventory_lines_absvalue'] else 0.0

            totals[inventory["id"]] = total

        return totals

    def _get_products_added(self, cr, uid, ids, field_name, arg, context=None):
        if not ids:
            return False

        cr.execute("""
            SELECT pi.id, count(rel.product_id)
            FROM
                physical_inventory pi
            LEFT JOIN
                physical_inventory_product_rel rel ON rel.product_id = pi.id
            WHERE
                pi.id in %s
            GROUP BY pi.id
        """, (tuple(ids), ))
        ret = {}
        for x in cr.fetchall():
            ret[x[0]] = x[1] > 0

        return ret

    _columns = {
        'ref': fields.char('Reference', size=64, readonly=True, sort_column='id'),
        'name': fields.char('Name', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.datetime('Creation Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'responsible': fields.char('Responsible', size=128, required=False, states={'closed': [('readonly',True)], 'cancel': [('readonly',True)]}),
        'date_done': fields.datetime('Date done', readonly=True),
        'date_confirmed': fields.datetime('Date confirmed', readonly=True),
        # 'inventory_id' and 'product_id' seem to be inverted in product_ids
        'product_ids': fields.many2many('product.product', 'physical_inventory_product_rel',
                                        'product_id', 'inventory_id', string="Product selection", domain=[('type', 'not in', ['service_recep', 'consu'])], order_by="default_code"),
        'discrepancy_line_ids': fields.one2many('physical.inventory.discrepancy', 'inventory_id', 'Discrepancy lines',
                                                states={'closed': [('readonly', True)]}),
        'counting_line_ids': fields.one2many('physical.inventory.counting', 'inventory_id', 'Counting lines',
                                             states={'closed': [('readonly', True)]}),
        'location_id': fields.many2one('stock.location', 'Location', required=True, readonly=True,
                                       states={'draft': [('readonly', False)]}),
        'move_ids': fields.many2many('stock.move', 'physical_inventory_move_rel', 'inventory_id', 'move_id',
                                     'Created Moves', readonly=True, order_by="id"),
        'state': fields.selection(PHYSICAL_INVENTORIES_STATES, 'State', readonly=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True, select=True, required=True,
                                      states={'draft': [('readonly', False)]}),
        'full_inventory': fields.boolean('Full inventory', readonly=True),
        'type': fields.selection([('full', 'Full Inventory count (planned)'), ('partial', 'Partial Inventory count (planned)'),
                                  ('correction', 'Stock correction (unplanned)')], 'Inventory Type', required=True, select=True, add_empty=True),
        'hidden_type': fields.function(tools.misc.get_fake, method=True, internal="1", type='char', string="Hidden Type"),
        'discrepancies_generated': fields.boolean('Discrepancies Generated', readonly=True),
        'file_to_import': fields.binary(string='File to import', filters='*.xml'),
        'file_to_import2': fields.binary(string='File to import', filters='*.xml'),

        # Total for product
        'inventory_lines_number':             fields.function(_inventory_totals, multi="inventory_total", method=True, type='integer', string=_("Number of inventory lines")),
        'discrepancy_lines_number':           fields.function(_inventory_totals, multi="inventory_total", method=True, type='integer', string=_("Number of discrepancy lines")),
        'discrepancy_lines_percent':          fields.function(_inventory_totals, multi="inventory_total", method=True, type='float',   string=_("Percent of lines with discrepancies")),
        'inventory_lines_value':              fields.function(_inventory_totals, multi="inventory_total", method=True, type='float',   string=_("Total value of inventory")),
        'discrepancy_lines_value':            fields.function(_inventory_totals, multi="inventory_total", method=True, type='float',   string=_("Value of discrepancies")),
        'discrepancy_lines_percent_value':    fields.function(_inventory_totals, multi="inventory_total", method=True, type='float',   string=_("Percent of value of discrepancies")),
        'inventory_lines_absvalue':           fields.function(_inventory_totals, multi="inventory_total", method=True, type='float',   string=_("Absolute value of inventory")),
        'discrepancy_lines_absvalue':         fields.function(_inventory_totals, multi="inventory_total", method=True, type='float',   string=_("Absolute value of discrepancies")),
        'discrepancy_lines_percent_absvalue': fields.function(_inventory_totals, multi="inventory_total", method=True, type='float',   string=_("Percent of absolute value of discrepancies")),
        'bad_stock_msg': fields.text('Bad Stock', readonly=1),
        'has_bad_stock': fields.boolean('Has bad Stock', readonly=1),
        'max_filter_months': fields.integer('Months selected in "Products with recent movement at location" during Product Selection'),
        'multiple_filter_months': fields.boolean('Multiple Selection'),
        'products_added': fields.function(_get_products_added, method=True, type='boolean', string='Has products'),
    }

    _defaults = {
        'ref': False,
        'date': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'state': 'draft',
        'full_inventory': False,
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'physical.inventory', context=c),
        'has_bad_stock': False,
        'discrepancies_generated': False,
        'max_filter_months': -1,
        'multiple_filter_months': False,
        'products_added': False,
    }

    def create(self, cr, uid, values, context):
        context = context is None and {} or context
        values["ref"] = self.pool.get('ir.sequence').get(cr, uid, 'physical.inventory')

        if values and 'type' not in values and values.get('hidden_type'):
            values['type'] = values['hidden_type']

        new_id = super(PhysicalInventory, self).create(cr, uid, values, context=context)

        if self.search(cr, uid, [('id', '=', new_id), ('location_id.active', '=', False)]):
            raise osv.except_osv(_('Warning'), _("Location is inactive"))
        return new_id

    def write_web(self, cr, uid, ids, values, context=None):
        if values and 'type' not in values and values.get('hidden_type'):
            values['type'] = values['hidden_type']
        return super(PhysicalInventory, self).write_web(cr, uid, ids, values, context=context)

    def change_inventory_type(self, cr, uid, ids, inv_type, context=None):
        return {'value': {'hidden_type': inv_type}}

    def copy(self, cr, uid, id_, default=None, context=None):
        default = default is None and {} or default
        context = context is None and {} or context
        default = default.copy()

        default['state'] = 'draft'
        default['date'] = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        default['type'] = 'partial'
        fields_to_empty = ["ref",
                           "full_inventory",
                           "date_done",
                           "bad_stock_msg",
                           "has_bad_stock",
                           "file_to_import",
                           "file_to_import2",
                           "counting_line_ids",
                           "discrepancy_line_ids",
                           "discrepancies_generated",
                           "move_ids",
                           "multiple_filter_months",
                           "max_filter_months"]

        for field in fields_to_empty:
            default[field] = False

        return super(PhysicalInventory, self).copy(cr, uid, id_, default, context=context)

    def perm_write(self, cr, user, ids, fields, context=None):
        pass

    def onchange_products(self, cr, uid, ids, product_ids, context=None):
        res = {'value': {'products_added': product_ids != [(6, 0, [])]}}
        if product_ids == [(6, 0, [])]:
            res['value'].update({'max_filter_months': -1, 'multiple_filter_months': False})
        return res

    def action_select_products(self, cr, uid, ids, context=None):
        """
        Trigerred when clicking on the button "Products Select"

        Open the wizard to select the products according to specific filters..
        """
        context = context is None and {} or context
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def create(model, vals):
            return self.pool.get(model).create(cr, uid, vals, context=context)
        def view(module, view):
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, module, view)[1]

        # Prepare values to feed the wizard with
        assert len(ids) == 1
        inventory_id = ids[0]

        # Create the wizard, check if it is a full inventory
        wiz_model = 'physical.inventory.select.products'
        wiz_values = {
            "inventory_id": inventory_id,
            "full_inventory": read_single(self._name, inventory_id, 'type') == 'full'
        }
        wiz_id = create(wiz_model, wiz_values)
        context['wizard_id'] = wiz_id

        # Get the view reference
        view_id = view('stock', 'physical_inventory_select_products')

        # Return a description of the wizard view
        return {'type': 'ir.actions.act_window',
                'target': 'new',
                'res_model': wiz_model,
                'res_id': wiz_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'context': context}

    def generate_counting_sheet(self, cr, uid, ids, context=None):
        """
        Trigerred when clicking on the button "Generate counting sheet"

        Open the wizard to fill the counting sheet with selected products.
        Choose to include batch numbers / expiry date or not
        """
        context = context is None and {} or context

        # Prepare values to feed the wizard with
        assert len(ids) == 1
        inventory_id = ids[0]



        # Create the wizard
        wiz_model = 'physical.inventory.generate.counting.sheet'
        filter_months_data = self.read(cr, uid, inventory_id, ['max_filter_months', 'multiple_filter_months'], context=context)
        wiz_vals = {
            'inventory_id': inventory_id,
            'only_with_stock_level': filter_months_data['max_filter_months'] == -1,
            'only_with_pos_move': filter_months_data['max_filter_months'] != -1,
        }

        # Check if the 4th bool needs to be checked: if the 2 first are checked (default) and the recent filter has been used
        # If 'Moved in the last' has not been used ('first_filter_months' is 0), set 'only_with_stock_level' to True by default
        if filter_months_data['max_filter_months'] != -1:
            if filter_months_data['multiple_filter_months']:
                wiz_vals['recent_moves_months'] = _('Multiple selections up to: %s months') % (filter_months_data['max_filter_months'], )
            else:
                wiz_vals['recent_moves_months'] = _('Products moved in the last: %s month%s') % (filter_months_data['max_filter_months'], filter_months_data['max_filter_months'] > 1 and 's' or '')

        wiz_id = self.pool.get(wiz_model).create(cr, uid, wiz_vals, context=context)
        context['wizard_id'] = wiz_id

        # Get the view reference
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'physical_inventory_generate_counting_sheet')[1]

        # Return a description of the wizard view
        return {'type': 'ir.actions.act_window',
                'target': 'new',
                'res_model': wiz_model,
                'res_id': wiz_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'context': context}


    def generate_discrepancies(self, cr, uid, inventory_ids, context=None):
        """
        Trigerred when clicking on the button "Finish counting"

        Analyze the counted lines to look for discrepancy, and fill the
        'discrepancy lines' accordingly.
        """

        if context is None:
            context = {}

        # Get this inventory...
        assert len(inventory_ids) == 1
        inventory_id = inventory_ids[0]

        physical_inventory_obj = self.pool.get('physical.inventory')
        counting_obj = self.pool.get('physical.inventory.counting')

        # delete all previous discepancies
        physical_inventory_obj.write(cr, uid, inventory_id, {'discrepancy_line_ids': [(6, 0, [])], 'file_to_import2': False}, context=context)

        # Get the location and counting lines
        inventory = physical_inventory_obj.read(cr, uid, [inventory_id], [ "location_id",
                                                                           "discrepancy_line_ids",
                                                                           "counting_line_ids" ], context=context)[0]

        location_id = inventory["location_id"][0]
        counting_line_ids = inventory["counting_line_ids"]

        counting_lines = counting_obj.read(cr, uid,
                                           counting_line_ids,
                                           [ "line_no",
                                             "product_id",
                                             "product_uom_id",
                                             "standard_price",
                                             "currency_id",
                                             "batch_number",
                                             "expiry_date",
                                             "quantity"], context=context)

        # Extract the list of (unique) product ids
        product_ids = [ line["product_id"][0] for line in counting_lines ]
        product_ids = list(set(product_ids))

        # Fetch the theoretical quantities
        # This will be a dict like { (product_id_1, BN_string_1) : theo_qty_1,
        #                            (product_id_2, BN_string_2) : theo_qty_2 }
        theoretical_quantities = self.get_stock_for_products_at_location(cr, uid, product_ids, location_id, context=context)

        # Create a similar dictionnary for counted quantities
        counting_lines_per_product_batch_expirtydate = {}
        counted_quantities = {}
        max_line_no = 0
        available_line_no = {}
        duplicates = {}

        for line in counting_lines:

            product_batch_expirydate = (line["product_id"][0],
                                        line["batch_number"] or False,
                                        line["expiry_date"])

            qty = float(line["quantity"]) if line["quantity"] else False
            if line["quantity"] is False and product_batch_expirydate in duplicates:
                # ignore duplicates if qty is not set
                continue

            if qty is False:
                available_line_no.setdefault(line["product_id"][0], []).append(line["line_no"])

            if line["quantity"] is not False:
                duplicates.setdefault(product_batch_expirydate, []).append(line["line_no"])

            counted_quantities[product_batch_expirydate] = qty

            counting_lines_per_product_batch_expirtydate[product_batch_expirydate] = {
                "line_id": line["id"],
                "line_no": line["line_no"]
            }
            if line["line_no"] > max_line_no:
                max_line_no = line["line_no"]

        if duplicates:
            msg = []
            for k in duplicates:
                if len(duplicates[k]) > 1:
                    msg.append( '- %s' % ', '.join(['%s' % line_n for  line_n in duplicates[k]]))
            if msg:
                raise osv.except_osv(_('Warning'), _('You have duplicates ! Please set Quantity only on one of these lines:\n %s') % ("\n".join(msg)))

        ###################################################
        # Now, compare theoretical and counted quantities #
        ###################################################

        # First, create a unique set containing all product/batches
        all_product_batch_expirydate = set().union(theoretical_quantities,
                                                   counted_quantities)

        bn_ed_prod_ids = [x[0] for x in all_product_batch_expirydate if x[1] or x[2]]
        prod_info = {}
        for prod in self.pool.get('product.product').read(cr, uid, bn_ed_prod_ids, ['batch_management', 'perishable'], context=context):
            prod_info[prod['id']] = prod

        # filter the case we had an entry with BN when product is not (anymore) BN mandatory:
        attr_changed = []
        filtered_all_product_batch_expirydate = set()
        for prod_id, batch_n, exp_date in all_product_batch_expirydate:
            if batch_n and not prod_info[prod_id]['batch_management'] or exp_date and not prod_info[prod_id]['perishable']:
                line_number = counting_lines_per_product_batch_expirtydate.get((prod_id, batch_n or False, exp_date), {}).get('line_no', '')
                if batch_n:
                    attr_changed.append(_('Line %s, batch %s product is not BN anymore, please correct the line') % (line_number, batch_n))
                else:
                    attr_changed.append(_('Line %s, expiry %s product is not ED anymore, please correct the line') % (line_number, exp_date))
            elif not prod_info.get(prod_id) or \
                    (batch_n and prod_info[prod_id]['batch_management']) or (exp_date and prod_info[prod_id]['perishable']):
                filtered_all_product_batch_expirydate.add((prod_id, batch_n, exp_date))

        if attr_changed:
            raise osv.except_osv(_('Warning'), "\n".join(attr_changed))

        new_discrepancies = []
        counting_lines_with_no_discrepancy = []
        used_line_no = {}
        # For each of them, compare the theoretical and counted qty

        for product_batch_expirydate in filtered_all_product_batch_expirydate:
            # If the key is not known, assume 0
            theoretical_qty = theoretical_quantities.get(product_batch_expirydate, 0.0)
            counted_qty = counted_quantities.get(product_batch_expirydate, -1.0)

            # If no discrepancy, nothing to do
            # (Use a continue to save 1 indentation level..)
            if counted_qty is not False and counted_qty == theoretical_qty or (theoretical_qty == 0 and counted_qty == -1):
                if product_batch_expirydate in counting_lines_per_product_batch_expirtydate:
                    counting_line_id = counting_lines_per_product_batch_expirtydate[product_batch_expirydate]["line_id"]
                    counting_lines_with_no_discrepancy.append(counting_line_id)
                    used_line_no[counting_lines_per_product_batch_expirtydate[product_batch_expirydate]['line_no']] = True
                continue

            # If this product/batch is known in the counting line, use the existing line number
            if product_batch_expirydate in counting_lines_per_product_batch_expirtydate:
                this_product_batch_expirydate = counting_lines_per_product_batch_expirtydate[product_batch_expirydate]
                line_no = this_product_batch_expirydate["line_no"]
                used_line_no[line_no] = True
            else:  # Otherwise, we will try later to assign a line number that matched a C/S line
                line_no = False

            new_discrepancies.append(
                { "inventory_id": inventory_id,
                  "line_no": line_no,
                  "product_id": product_batch_expirydate[0],
                  "batch_number": product_batch_expirydate[1],
                  "expiry_date": product_batch_expirydate[2],
                  "theoretical_qty": theoretical_qty,
                  "counted_qty": counted_qty,
                  'counted_qty_is_empty': type(counted_qty) == type(False), # True if counted_qty is a boolean
                  })

        # assign line_no to lines
        for discrepancy in new_discrepancies:
            if not discrepancy['line_no']:
                line_no = False
                while available_line_no.get(discrepancy['product_id']):
                    line_no = available_line_no.get(discrepancy['product_id']).pop(0)
                    if line_no not in used_line_no:
                        break
                if not line_no:
                    max_line_no += 1
                    line_no = max_line_no
                discrepancy['line_no'] = line_no

        # Update discrepancy flags on counting lines
        counting_lines_with_discrepancy = [ l["id"] for l in counting_lines if  not l["id"] in counting_lines_with_no_discrepancy ]
        counting_obj.write(cr, uid, counting_lines_with_discrepancy,    {"discrepancy": True}, context=context)
        counting_obj.write(cr, uid, counting_lines_with_no_discrepancy, {"discrepancy": False}, context=context)

        # Sort discrepancies according to line number
        new_discrepancies = sorted(new_discrepancies, key=lambda d: d["line_no"])

        # Prepare the actual create/remove for discrepancy lines
        # 0 is for addition/creation

        create_discrepancy_lines = [ (0,0,discrepancy) for discrepancy in new_discrepancies ]

        # Do the actual write
        physical_inventory_obj.write(cr, uid, inventory_id, {'discrepancy_line_ids': create_discrepancy_lines, 'discrepancies_generated': False, 'has_bad_stock': False}, context=context)


        return self.resolve_discrepancies_anomalies(cr, uid, inventory_id, context=context)

    def re_generate_discrepancies(self, cr, uid, inventory_ids, context=None):
        return self.generate_discrepancies(cr, uid, inventory_ids, context=context)


    def resolve_discrepancies_anomalies(self, cr, uid, inventory_id, context=None):
        context = context if context else {}
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
        def product_identity_str(line, context=context):
            str_ = _("product '%s'") % line["product_id"][1]
            if line["batch_number"] or line["expiry_date"]:
                str_ += _(" with Batch number '%s' and Expiry date '%s'") % (line["batch_number"] or '', line["expiry_date"] or '')
            else:
                str_ += _(" (no batch number / expiry date)")
            return str_

        discrepancy_line_ids = read_single("physical.inventory", inventory_id, 'discrepancy_line_ids')

        discrepancy_lines = read_many('physical.inventory.discrepancy',
                                      discrepancy_line_ids,
                                      [ "line_no",
                                        "product_id",
                                        "batch_number",
                                        "expiry_date",
                                        "counted_qty",
                                        'counted_qty_is_empty',
                                        "ignored"])

        anomalies = []
        for line in discrepancy_lines:
            if line["ignored"]:
                continue
            anomaly = False
            if line["counted_qty_is_empty"]:
                anomaly = _("Quantity for line %s, %s is incorrect.") % (line["line_no"], product_identity_str(line))

            if line["counted_qty"] < 0.0:
                anomaly = _("A line for %s was expected but not found.") % product_identity_str(line, context=context)

            if anomaly:
                anomalies.append({"message": anomaly + _(" Ignore line or count as 0 ?"),
                                  "line_id": line["id"]})

        if anomalies:
            return self.pool.get('physical.inventory.import.wizard').action_box(cr, uid, 'Warning', anomalies, inventory_id=inventory_id)
        else:
            self.write(cr, uid, inventory_id, {'discrepancies_generated': True}, context=context)
            self._update_total_product(cr, uid, inventory_id, context=context)
            return {}

    def _update_total_product(self, cr, uid, inventory_id, context=None):
        """
        Remove Discrepancy lines with counted_qty and theoretical_qty at 0
        Then theoretical_qties and counted_qties are indexed with (product_id, batchnumber, expirydate)
        """
        discl_obj = self.pool.get('physical.inventory.discrepancy')
        discl_dom = [('inventory_id', '=', inventory_id), ('counted_qty', '=', 0), ('theoretical_qty', '=', 0)]
        disc_lines_ids = discl_obj.search(cr, uid, discl_dom, context=context)
        if disc_lines_ids:
            discl_obj.unlink(cr, uid, disc_lines_ids, context=context)

        cr.execute('update physical_inventory_discrepancy set total_product_theoretical_qty=0, total_product_counted_qty=0 where inventory_id = %s', (inventory_id, ))
        # theo qty of ignored lines must be counted as qty after inv
        cr.execute("select product_id, sum(theoretical_qty), sum(case when ignored='f' then counted_qty else theoretical_qty end) from physical_inventory_discrepancy where inventory_id = %s group by product_id", (inventory_id, ))
        for x in cr.fetchall():
            cr.execute('update physical_inventory_discrepancy set total_product_theoretical_qty=%s, total_product_counted_qty=%s where inventory_id = %s and product_id = %s', (x[1], x[2], inventory_id, x[0]))

    def pre_process_discrepancies(self, cr, uid, items, context=None):
        discrepancies = self.pool.get('physical.inventory.discrepancy')
        ignore_ids = [item['line_id'] for item in items if item['action'] == 'ignore']
        count_ids = [item['line_id'] for item in items if item['action'] == 'count']
        if ignore_ids:
            discrepancies.write(cr, uid, ignore_ids, {'counted_qty': 0.0, 'ignored': True})
        if count_ids:
            discrepancies.write(cr, uid, count_ids, {'counted_qty': 0.0, 'ignored': False})

    def get_stock_for_products_at_location(self, cr, uid, product_ids, location_id, context=None):
        if context is None:
            context = {}

        assert isinstance(product_ids, list)
        assert isinstance(location_id, int)

        move_obj = self.pool.get('stock.move')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

        default_uom = {}
        for prod in prod_obj.read(cr, uid, product_ids, ['uom_id'], context=context):
            default_uom[prod['id']] = prod['uom_id'][0]

        # Get all the moves for in/out of that location for the products
        move_for_products_at_location = ['&', '&', '|',
                                         ('location_id', 'in', [location_id]),
                                         ('location_dest_id', 'in', [location_id]),
                                         ("product_id", 'in', product_ids),
                                         ('product_qty', '!=', 0),
                                         ('state', '=', 'done')]

        moves_at_location_ids = move_obj.search(cr, uid, move_for_products_at_location, context=context)
        ftf = ["product_id", "product_qty", "prodlot_id", "expired_date", "location_id", "product_uom", "location_dest_id"]
        moves_at_location = move_obj.browse(cr, uid, moves_at_location_ids, fields_to_fetch=ftf, context=context)

        # Sum all lines to get a set of (product, batchnumber) -> qty
        stocks = {}
        for move in moves_at_location:

            product_id = move.product_id.id
            product_qty = move.product_qty
            batch_number = move.prodlot_id and move.prodlot_id.name or False
            expiry_date = move.expired_date

            if batch_number and move.prodlot_id.type == 'internal':
                batch_number = False

            product_batch_expirydate = (product_id, batch_number, expiry_date)

            # Init the quantity to 0 if batch is not present in dict yet
            # (NB: batch_id can be None, but that's not an issue for dicts ;))
            if not product_batch_expirydate in stocks.keys():
                stocks[product_batch_expirydate] = 0.0

            move_out = (move.location_id.id == location_id)
            move_in = (move.location_dest_id.id == location_id)

            if move_in and move_out:
                continue

            if move.product_uom and default_uom.get(product_id) and move.product_uom.id != default_uom[product_id]:
                product_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, product_qty, default_uom[product_id])

            if move_in:
                stocks[product_batch_expirydate] += product_qty
            elif move_out:
                stocks[product_batch_expirydate] -= product_qty

        return stocks

    def export_xls_counting_sheet(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'physical_inventory_counting_sheet_xls',
            'datas': {'ids': ids, 'target_filename': 'counting_sheet'},
            'nodestroy': True,
            'context': context,
        }

    def export_pdf_counting_sheet(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'physical_inventory_counting_sheet_pdf',
            'datas': {'ids': ids, 'target_filename': 'counting_sheet'},
            'nodestroy': True,
            'context': context,
        }

    def import_counting_sheet(self, cr, uid, ids, context=None):
        """
        Import an exported counting sheet
        """
        if not context:
            context = {}

        counting_sheet_header = {}
        counting_sheet_errors = []
        counting_sheet_warnings = []

        def add_error(message, file_row, file_col=None, is_warning=False):
            if file_col is not None:
                _msg = _('Cell %s%d: %s') % (chr(0x41 + file_col), file_row + 1, message)
            else:
                _msg = _('Line %d: %s') % (file_row + 1, message)
            if is_warning:
                counting_sheet_warnings.append(_msg)
            else:
                counting_sheet_errors.append(_msg)

        inventory_rec = self.browse(cr, uid, ids, context=context)[0]
        if not inventory_rec.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        counting_sheet_file = SpreadsheetXML(xmlstring=base64.decodestring(inventory_rec.file_to_import))

        product_obj = self.pool.get('product.product')
        product_uom_obj = self.pool.get('product.uom')
        counting_obj = self.pool.get('physical.inventory.counting')
        wizard_obj = self.pool.get('physical.inventory.import.wizard')

        line_items = []

        all_uom = {}
        uom_ids = product_uom_obj.search(cr, uid, [], context=context)
        for uom in product_uom_obj.read(cr, uid, uom_ids, ['name'], context=context):
            all_uom[uom['name'].lower()] = uom['id']

        context['import_in_progress'] = True
        result = False
        try:
            # Reset the qty of each CS line
            cr.execute("""UPDATE physical_inventory_counting SET quantity = NULL WHERE inventory_id = %s""", (inventory_rec.id,))

            for row_index, row in enumerate(counting_sheet_file.getRows()):
                # === Process header ===

                # ignore empty line
                if not row.cells:
                    continue

                if row_index == 2:
                    counting_sheet_header.update({
                        'inventory_counter_name': row.cells[2].data,  # Cell C3
                        'inventory_date': row.cells[5].data  # Cell F3
                    })
                elif row_index == 4:
                    inventory_reference = row.cells[2].data  # Cell C5
                    inventory_location = row.cells[5].data  # Cell F5
                    # Check location
                    if inventory_rec.location_id and inventory_rec.location_id.name != (inventory_location or '').strip():
                        add_error(_('Location is different to inventory location'), row_index, 5)

                    # Check reference
                    if inventory_rec.ref.lower() != (inventory_reference or '').strip().lower():
                        add_error(_('Reference is different to inventory reference'), row_index, 2)
                    counting_sheet_header.update({
                        'location_id': inventory_rec.location_id,
                        'inventory_reference': inventory_reference
                    })
                elif row_index == 6:
                    counting_sheet_header['inventory_name'] = row.cells[2].data  # Cell C7
                if row_index < 9:
                    continue

                # === Process lines ===

                # Check number of columns
                if len(row) != 10:
                    add_error(_("""The number of columns is incorrect, you should have exactly 10 columns in this order:
    Line #, Item Code, Description, UoM, Quantity counted, Batch number, Expiry date, Specification, BN Management, ED Management"""), row_index)
                    break

                # Check product_code and type
                product_code = row.cells[1].data
                product_ids = product_obj.search(cr, uid, [('default_code', '=ilike', product_code)], context=context)
                product_id = False
                if len(product_ids) == 1:
                    product_id = product_ids[0]
                    # Check if product is non-stockable
                    if product_obj.search_exist(cr, uid, [('id', '=', product_id), ('type', 'in', ['service_recep', 'consu'])]):
                        add_error("""Impossible to import non-stockable product %s""" % product_code, row_index, 1)
                else:
                    add_error(_("""Product %s not found""") % product_code, row_index, 1)

                # Check UoM
                product_uom_id = False
                product_uom = row.cells[3].data.lower()
                if product_uom not in all_uom:
                    add_error(_("""UoM %s unknown""") % product_uom, row_index, 3)
                else:
                    product_uom_id = all_uom[product_uom]

                # Check quantity
                quantity = row.cells[4].data
                if quantity is not None:
                    if isinstance(quantity, int) and quantity == 0:
                        quantity = '0'
                    try:
                        quantity = counting_obj.quantity_validate(cr, uid, quantity, product_uom_id)
                    except NegativeValueError:
                        add_error(_('Quantity %s is negative') % quantity, row_index, 4)
                        quantity = 0.0
                    except ValueError:
                        quantity = 0.0
                        add_error(_('Quantity %s is not valid') % quantity, row_index, 4)

                if product_id:
                    product_info = product_obj.read(cr, uid, product_id, ['batch_management', 'perishable', 'default_code', 'uom_id'])
                else:
                    product_info = {'batch_management': False, 'perishable': False, 'default_code': product_code, 'uom_id': False}

                if product_info['uom_id'] and product_uom_id and product_info['uom_id'][0] != product_uom_id:
                    add_error(_("""Product %s, UoM %s does not conform to that of product in stock""") % (product_info['default_code'], product_uom), row_index, 3)

                # Check batch number
                batch_name = row.cells[5].data
                if not batch_name and product_info['batch_management'] and quantity is not None:
                    add_error(_('Batch number is required'), row_index, 5)

                if batch_name and not product_info['batch_management']:
                    add_error(_("Product %s is not BN managed, BN ignored") % (product_info['default_code'], ), row_index, 5, is_warning=True)
                    batch_name = False

                # Check expiry date
                expiry_date = row.cells[6].data
                if expiry_date and not product_info['perishable']:
                    add_error(_("Product %s is not ED managed, ED ignored") % (product_info['default_code'], ), row_index, 6, is_warning=True)
                    expiry_date = False
                elif expiry_date:
                    expiry_date_type = row.cells[6].type
                    year = False
                    try:
                        if expiry_date_type == 'datetime':
                            expiry_date = expiry_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
                            year = row.cells[6].data.year
                        elif expiry_date_type == 'str':
                            expiry_date_dt = parse(expiry_date)
                            year = expiry_date_dt.year
                            expiry_date = expiry_date_dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                        else:
                            raise ValueError()
                    except ValueError:
                        if not year or year >= 1900:
                            add_error(_("""Expiry date %s is not valid""") % expiry_date, row_index, 6)

                    if year and year < 1900:
                        add_error(_('Expiry date: year must be after 1899'), row_index, 6)

                if not expiry_date and product_info['perishable'] and quantity is not None:
                    add_error(_('Expiry date is required'), row_index, 6)

                # Check duplicate line (Same product_id, batch_number, expirty_date)
                item = '%d-%s-%s' % (product_id or -1, batch_name or '', expiry_date or '')
                if item in line_items:
                    add_error(_("""Product %s, Duplicate line (same product, batch number and expiry date)""") % product_info['default_code'], row_index)
                elif quantity is not None:
                    line_items.append(item)

                data = {
                    'product_id': product_id,
                    'batch_number': batch_name,
                    'expiry_date': expiry_date,
                    'quantity': False,
                    'product_uom_id': product_uom_id,
                }

                if quantity is not None:
                    data['quantity'] = quantity
                # Check if line exist
                line_ids = counting_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id),
                                                         ('product_id', '=', product_id),
                                                         ('batch_number', '=', batch_name),
                                                         ('expiry_date', '=', expiry_date)], context=context)
                if not line_ids and (batch_name or expiry_date):  # Search for empty BN/ED lines
                    line_ids = counting_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id),
                                                             ('product_id', '=', product_id),
                                                             ('batch_number', '=', False),
                                                             ('expiry_date', '=', False)], context=context)

                if line_ids:
                    counting_obj.write(cr, uid, line_ids[0], data, context=context)
                else:
                    data['inventory_id'] = inventory_rec.id
                    counting_obj.create(cr, uid, data, context=context)

            # endfor

            if counting_sheet_errors:
                cr.rollback()
                # Errors found, open message box for explain
                #self.write(cr, uid, ids, {'file_to_import': False}, context=context)
                cr.execute('update physical_inventory set file_to_import = NULL where id = %s', (ids[0], ))
                if counting_sheet_warnings:
                    counting_sheet_errors.append("\n%s" % _("Warning"))
                    counting_sheet_errors += counting_sheet_warnings
                result = wizard_obj.message_box(cr, uid, title=_('Importation errors'), message='\n'.join(counting_sheet_errors))
            else:
                # No error found
                vals = {
                    'file_to_import': False,
                    'responsible': counting_sheet_header.get('inventory_counter_name'),
                }
                self.write(cr, uid, ids, vals, context=context)
                counting_sheet_warnings.insert(0, _('Counting sheet successfully imported.'))
                result = wizard_obj.message_box(cr, uid, title='Information', message='\n'.join(counting_sheet_warnings))
        except Exception as e:
            cr.rollback()
            result = wizard_obj.message_box(cr, uid, title='Information', message=_('An error occured: %s') % (e.message,))
        finally:
            context['import_in_progress'] = False
            return result

    def import_xls_discrepancy_report(self, cr, uid, ids, context=None):
        """Import an exported discrepancy report"""
        if not context:
            context = {}

        discrepancy_report_lines = []
        discrepancy_report_errors = []

        def add_error(message, file_row, file_col):
            discrepancy_report_errors.append(_('Cell %s%d: %s') % (chr(0x41 + file_col), file_row + 1, message))

        inventory_rec = self.browse(cr, uid, ids, context=context)[0]
        if not inventory_rec.file_to_import2:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        if not inventory_rec.discrepancies_generated:
            raise osv.except_osv(_('Error'), _('Page need to be refreshed - please press "F5"'))

        discrepancy_report_file = SpreadsheetXML(xmlstring=base64.decodestring(inventory_rec.file_to_import2))

        product_obj = self.pool.get('product.product')
        reason_type_obj = self.pool.get('stock.reason.type')
        discrepancy_obj = self.pool.get('physical.inventory.discrepancy')
        ids_seen = {}

        for row_index, row in enumerate(discrepancy_report_file.getRows()):
            if row_index < 10:
                continue
            if len(row) != 21:
                add_error(_("""The number of columns is incorrect, you should have exactly 20 columns in this order:
Line #, Family, Item Code, Description, UoM, Unit Price, currency (functional), Quantity Theorical, Quantity counted, Batch no, Expiry Date, Discrepancy, Discrepancy value, Total QTY before INV, Total QTY after INV, Total Value after INV, Discrepancy, Discrepancy Value, Adjustement type, Sub Reason Type, Comments / actions (in case of discrepancy)"""),
                          row_index, len(row))
                break

            product_code = row.cells[2].data
            line_no = row.cells[0].data
            # check if line number and product code are matching together
            product_id = product_obj.search(cr, uid, [('default_code', '=ilike', product_code)], context=context)
            disc_line_found = self.pool.get('physical.inventory.discrepancy').search(cr, uid, [
                ('inventory_id', '=', inventory_rec.id),
                ('line_no', '=', int(line_no)),
                ('product_id', 'in', product_id),
            ], context=context)
            if not disc_line_found:
                add_error(_("""Unable to update line #%s product %s: line not found in the discrepancy report""") % (line_no, product_code), row_index, 2)

            # Check if product is non-stockable
            if product_obj.search_exist(cr, uid, [('default_code', '=like', product_code),
                                                  ('type', 'in', ['service_recep', 'consu'])],
                                        context=context):
                add_error(_("""Impossible to import non-stockable product %s""") % product_code, row_index, 2)

            adjustment_type = row.cells[18].data
            if adjustment_type:
                adjustement_split = adjustment_type.split(' ')
                code = adjustement_split[0].split('.')[-1]
                reason_ids = []
                try:
                    int(code)
                    reason_ids = reason_type_obj.search(cr, uid, [('code', '=', code), ('name', '=', adjustement_split[-1].strip())], context=context)
                    if reason_ids:
                        adjustment_type = reason_ids[0]
                except ValueError:
                    reason_ids = []

                if not reason_ids:
                    add_error(_('Unknown adjustment type %s') % adjustment_type, row_index, 18)
                    adjustment_type = False

            sub_rt = row.cells[19].data
            sub_rt_index = False
            discr_rt_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
            if sub_rt:
                if adjustment_type == discr_rt_id:
                    sub_rt_select = self.pool.get('physical.inventory.discrepancy').fields_get(cr, uid, ['sub_reason_type'], context=context)
                    for x in sub_rt_select['sub_reason_type']['selection']:
                        if x[1] == sub_rt:
                            sub_rt_index = x[0]
                            break
                    if not sub_rt_index:
                        add_error(_('Unknown Sub Reason Type %s') % sub_rt, row_index, 19)
                else:
                    add_error(_('It is not possible to add a Sub Reason Type for this type of Adjustment'), row_index, 19)

            comment = row.cells[20].data

            line_id = False
            line_ids = discrepancy_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id), ('line_no', '=', line_no)])
            if len(line_ids) == 1:
                line_id = line_ids[0]
            elif len(line_ids) > 1:
                line_ids = discrepancy_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id), ('line_no', '=', line_no), ('product_id', '=', product_id)])
                if len(line_ids) == 1:
                    line_id = line_ids[0]
                else:
                    bn = row.cells[9].data or False
                    line_ids = discrepancy_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id), ('line_no', '=', line_no), ('product_id', '=', product_id), ('batch_number', '=', bn), ('ignored', '=', False)], order='id')
                    if len(line_ids) == 1:
                        line_id = line_ids[0]
                    else:
                        # pre-requisite: order of lines in the xls file is the same as in screen (don't want to block already created PI)
                        for l_id in line_ids:
                            if l_id not in ids_seen:
                                line_id = l_id
                                ids_seen[line_id] = True
                                break
            if not line_id:
                add_error(_('Unknown line no %s') % line_no, row_index, 0)
            else:
                if inventory_rec.state == 'confirmed':
                    # In case the imported line has Discr adj type + sub RT when og line has Other adj type
                    current_line_rt = discrepancy_obj.read(cr, uid, line_id, ['reason_type_id'], context=context)['reason_type_id']
                    if current_line_rt and current_line_rt[0] != discr_rt_id and sub_rt_index:
                        add_error(_('It is not possible to add a Sub Reason Type for this type of Adjustment on the Confirmed line')
                                  , row_index, 19)
                        sub_rt_index = False

                    disc_line = (1, line_id, {'sub_reason_type': sub_rt_index, 'comment': comment})
                else:
                    disc_line = (1, line_id, {'reason_type_id': adjustment_type, 'sub_reason_type': sub_rt_index, 'comment': comment})
                discrepancy_report_lines.append(disc_line)
        # endfor

        context['import_in_progress'] = True
        wizard_obj = self.pool.get('physical.inventory.import.wizard')
        if discrepancy_report_errors:
            # Errors found, open message box for exlain
            #self.write(cr, uid, ids, {'file_to_import2': False}, context=context)
            cr.execute('update physical_inventory set file_to_import2=NULL where id=%s', (ids[0], ))
            result = wizard_obj.message_box(cr, uid, title=_('Importation errors'),
                                            message='\n'.join(discrepancy_report_errors))
        else:
            # No error found. update comment and reason for discrepancies lines on Inventory
            vals = {'file_to_import2': False, 'discrepancy_line_ids': discrepancy_report_lines}
            self.write(cr, uid, ids, vals, context=context)
            result = wizard_obj.message_box(cr, uid, title='Information',
                                            message=_('Discrepancy report successfully imported.'))
        context['import_in_progress'] = False

        return result

    def export_xls_discrepancy_report(self, cr, uid, ids, context=None):
        if self.search_exist(cr, uid, [('id', 'in', ids), ('discrepancies_generated', '=', False)]):
            raise osv.except_osv(_('Error'), _('Page need to be refreshed - please press "F5"'))

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'physical_inventory_discrepancies_report_xls',
            'datas': {'ids': ids, 'target_filename': 'discrepancies'},
            'nodestroy': True,
            'context': context,
        }

    def action_counted(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        cr.execute('''select default_code, batch_number, expiry_date, array_agg(line_no) from physical_inventory_counting
            where quantity is not null and inventory_id in %s
            group by inventory_id, default_code, batch_number, expiry_date
            having count(*) > 1
        ''', (tuple(ids),))
        error = []
        for x in cr.fetchall():
            error.append(_('Product: %s, BN: %s, ED: %s : lines %s') % (x[0], x[1] or '-', x[2] or '-', ', '.join(['%s'%lin_n for lin_n in x[3]])))

        if error:
            wizard_obj = self.pool.get('physical.inventory.import.wizard')
            error.insert(0, _('Probably due to BN/ED changes on product, you have duplicates, please remove Qty on duplicated lines'))
            return wizard_obj.message_box(cr, uid, title=_('Error'), message='\n'.join(error))

        self.write(cr, uid, ids, {'state': 'counted'}, context=context)
        return {}

    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory"""
        if context is None:
            context = {}
        self.write(cr, uid, ids, {'state': 'closed', 'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)},
                   context=context)
        return {}

    def action_recount(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        discrep_line_obj = self.pool.get('physical.inventory.discrepancy')
        # Remove discrepancies and reset discrepancies_generated boolean
        for inv_id in ids:
            discrep_line_ids = discrep_line_obj.search(cr, uid, [('inventory_id', '=', inv_id)], context=context)
            if len(discrep_line_ids) > 0:
                discrep_line_obj.unlink(cr, uid, discrep_line_ids, context=context)
        self.write(cr, uid, ids, {'state': 'counting', 'discrepancies_generated': False}, context=context)
        return {}

    def check_discrepancies_constraint(self, cr, uid, ids, context=None):
        cr.execute('''
            select array_agg(disc.line_no), COALESCE(batch_number, ''), expiry_date, product_id, inventory_id
                from physical_inventory_discrepancy disc
                where
                    disc.ignored = 'f' and
                    disc.inventory_id in %s
                group by
                    inventory_id, product_id, COALESCE(batch_number, ''), expiry_date
                having count(*) > 1
        ''', (tuple(ids),))
        msg = []
        for x in cr.fetchall():
            msg.append(_(' - lines %s') % ',' .join(['%s'% ln for ln in x[0]]))
        return msg

    def action_validate(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if self.search_exist(cr, uid, [('id', 'in', ids), '|', ('state', '!=', 'counted'), ('discrepancies_generated', '=', False)], context=context):
            raise osv.except_osv(_('Error'), _('Page need to be refreshed - please press "F5"'))

        # Check if a line contains a non-stockable product
        dids = self.pool.get('physical.inventory.discrepancy').search(cr, uid, [('inventory_id', 'in', ids), ('product_id.type', 'in', ['service_recep', 'consu']), ('ignored', '!=', True)])
        if dids:
            error = []
            for disc in self.pool.get('physical.inventory.discrepancy').read(cr, uid, dids, ['line_no', 'product_id'], context=context):
                error.append('Line %s, product %s' % (disc['line_no'], disc['product_id'][1]))
            raise osv.except_osv(_('Error'),
                                 _("Please remove non-stockable from the discrepancy report to validate:\n%s") % ("\n".join(error),)
                                 )

        errors = self.check_discrepancies_constraint(cr, uid, ids, context=context)
        if errors:
            wizard_obj = self.pool.get('physical.inventory.import.wizard')
            errors.insert(0, _('Probably due to BN/ED changes on product, you have duplicates'))
            return wizard_obj.message_box(cr, uid, title=_('Error'), message='\n'.join(errors))

        for inv in self.browse(cr, uid, ids, fields_to_fetch=['name'], context=context):
            message = _('Physical Inventory') + " '" + inv.name + "' " + _("is validated.")
            self.log(cr, uid, inv.id, message)
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)
        return {}

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirm the inventory, close the stock moves and writes its finished date"""

        if context is None:
            context = {}

        # to perform the correct inventory corrections we need analyze stock location by
        # location, never recursively, so we use a special context
        product_context = dict(context, compute_child=False)

        product_obj = self.pool.get('product.product')
        product_tmpl_obj = self.pool.get('product.template')
        prod_lot_obj = self.pool.get('stock.production.lot')
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        product_dict = {}
        product_tmpl_dict = {}

        if self.search_exist(cr, uid, [('id', 'in', ids), '|', ('state', '!=', 'validated'), ('discrepancies_generated', '=', False)], context=context):
            raise osv.except_osv(_('Error'), _('Page need to be refreshed - please press "F5"'))

        errors = self.check_discrepancies_constraint(cr, uid, ids, context=context)
        if errors:
            wizard_obj = self.pool.get('physical.inventory.import.wizard')
            errors.insert(0, _('Probably due to BN/ED changes on product, you have duplicates'))
            return wizard_obj.message_box(cr, uid, title=_('Error'), message='\n'.join(errors))

        for inv in self.read(cr, uid, ids, ['counting_line_ids',
                                            'discrepancy_line_ids',
                                            'date', 'name', 'state'], context=context):
            if inv['state'] in ('confirmed', 'closed', 'cancel'):
                raise osv.except_osv(_('Error'), _('You cannot confirm an inventory which is %s') % inv['state'])
            move_ids = []

            # gather all information needed for the lines treatment first to do less requests
            counting_line_obj = self.pool.get('physical.inventory.counting')
            inv_line_obj = self.pool.get('physical.inventory.discrepancy')


            counting_lines_with_no_discrepancy_ids = counting_line_obj.search(cr, uid, [("inventory_id", '=', inv["id"]),
                                                                                        ("discrepancy", '=', False)],
                                                                              context=context)

            counting_lines_with_no_discrepancy = counting_line_obj.read(cr, uid, counting_lines_with_no_discrepancy_ids,
                                                                        ['product_id',
                                                                         'batch_number',
                                                                         'expiry_date'],
                                                                        context=context)

            line_read = inv_line_obj.read(cr, uid, inv['discrepancy_line_ids'],
                                          ['inventory_id', 'product_id', 'product_uom_id', 'batch_number', 'expiry_date', 'location_id',
                                           'discrepancy_qty', 'reason_type_id', 'comment', 'ignored', 'line_no'], context=context)

            product_id_list = [x['product_id'][0] for x in line_read if
                               x['product_id'][0] not in product_dict]
            product_id_list = list(set(product_id_list))
            product_read = product_obj.read(cr, uid, product_id_list,
                                            ['product_tmpl_id'], context=context)
            for product in product_read:
                product_id = product['id']
                product_dict[product_id] = {}
                product_dict[product_id]['p_tmpl_id'] = product['product_tmpl_id'][0]

            tmpl_ids = [x['p_tmpl_id'] for x in product_dict.values()]

            product_tmpl_id_list = [x for x in tmpl_ids if x not in product_tmpl_dict]
            product_tmpl_id_list = list(set(product_tmpl_id_list))
            product_tmpl_read = product_tmpl_obj.read(cr, uid,
                                                      product_tmpl_id_list, ['property_stock_inventory'],
                                                      context=context)
            product_tmpl_dict = dict((x['id'], x['property_stock_inventory'][0]) for x in product_tmpl_read)

            for product_id in product_id_list:
                product_tmpl_id = product_dict[product_id]['p_tmpl_id']
                stock_inventory = product_tmpl_dict[product_tmpl_id]
                product_dict[product_id]['stock_inventory'] = stock_inventory

            errors = []
            for line in line_read:
                if not line['ignored'] and not line['reason_type_id']:
                    errors.append(_('Line %d: Adjustement type missing') % line['line_no'])

            if errors:
                # Errors found, open message box for exlain
                wizard_obj = self.pool.get('physical.inventory.import.wizard')
                return wizard_obj.message_box(cr, uid, title=_('Confirmation errors'), message='\n'.join(errors))


            def get_prodlot_id(bn, ed):
                if not ed:
                    return False
                elif bn:
                    return picking_obj.retrieve_batch_number(cr, uid, pid, {'name': bn, 'life_date': ed}, context=context)[0]
                else:
                    return prod_lot_obj._get_prodlot_from_expiry_date(cr, uid, ed, pid)

            # For each counting lines which had no discrepancy, keep track of
            # the real batch number id
            for line in counting_lines_with_no_discrepancy:
                line_id = line['id']
                pid = line['product_id'][0]
                bn = line['batch_number']
                ed = line['expiry_date']

                lot_id = get_prodlot_id(bn, ed)

                counting_line_obj.write(cr, uid, [line_id], {"prod_lot_id": lot_id}, context=context)


            discrepancy_to_move = {}
            for line in line_read:
                if line['ignored']:
                    continue
                line_id = line['id']
                pid = line['product_id'][0]
                bn = line['batch_number']
                ed = line['expiry_date']

                change = line['discrepancy_qty']  # - amount

                # Ignore lines with no discrepancies (there shouldnt be any
                # by definition/construction of the discrepancy lines)
                if not change:
                    continue

                lot_id = get_prodlot_id(bn, ed)

                # lot_id = line['prod_lot_id'] and line['prod_lot_id'][0] or False
                product_context.update(uom=line['product_uom_id'][0],
                                       date=inv['date'], prodlot_id=lot_id)

                # amount = location_obj._product_get(cr, uid, line['location_id'][0], [pid], product_context)[pid]

                location_id = product_dict[line['product_id'][0]]['stock_inventory']
                value = {
                    'name': 'INV:' + tools.ustr(inv['id']) + ':' + inv['name'],
                    'product_id': line['product_id'][0],
                    'product_uom': line['product_uom_id'][0],
                    'prodlot_id': lot_id,
                    'date': inv['date'],
                    'not_chained': True,
                }
                if change > 0:
                    value.update({
                        'product_qty': change,
                        'location_id': location_id,
                        'location_dest_id': line['location_id'][0],
                    })
                else:
                    value.update({
                        'product_qty': -change,
                        'location_id': line['location_id'][0],
                        'location_dest_id': location_id,
                    })
                value.update({
                    'comment': line['comment'],
                    'reason_type_id': line['reason_type_id'][0],
                })
                move_id = self.pool.get('stock.move').create(cr, uid, value)
                move_ids.append(move_id)
                discrepancy_to_move[line_id] = move_id

            message = _('Physical Inventory') + " '" + inv['name'] + "' " + _("is confirmed.")
            self.log(cr, uid, inv['id'], message)
            self.write(cr, uid, [inv['id']], {
                'state': 'confirmed',
                'move_ids': [(6, 0, move_ids)],
                'date_confirmed': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            })
            for line_id, move_id in discrepancy_to_move.items():
                inv_line_obj.write(cr, uid, [line_id], {'move_id': move_id}, context=context)

            # Close the moves
            move_obj.action_done(cr, uid, move_ids, context=context)

        return True

    def action_cancel_draft(self, cr, uid, ids, context=None):
        """ Cancels the stock move and change inventory state to draft."""
        for inv in self.read(cr, uid, ids, ['move_ids'], context=context):
            self.pool.get('stock.move').action_cancel(cr, uid, inv['move_ids'], context=context)

        for inv in self.browse(cr, uid, ids, fields_to_fetch=['location_id'], context=context):
            if not inv.location_id.active:
                raise osv.except_osv(_('Warning'), _("Location %s is inactive") % (inv.location_id.name,))

        self.write(cr, uid, ids, {'state': 'draft', 'discrepancies_generated': False}, context=context)
        return {}

    def action_cancel_inventary(self, cr, uid, ids, context=None):
        """ Cancels both stock move and inventory"""
        move_obj = self.pool.get('stock.move')
        account_move_obj = self.pool.get('account.move')
        for inv in self.browse(cr, uid, ids, context=context):
            move_obj.action_cancel(cr, uid, [x.id for x in inv.move_ids], context=context)
            for move in inv.move_ids:
                account_move_ids = account_move_obj.search(cr, uid, [('name', '=', move.name)], order='NO_ORDER')
                if account_move_ids:
                    account_move_data_l = account_move_obj.read(cr, uid, account_move_ids, ['state'], context=context)
                    for account_move in account_move_data_l:
                        if account_move['state'] == 'posted':
                            raise osv.except_osv(_('UserError'),
                                                 _('You can not cancel inventory which has any account move with posted state.'))
                        account_move_obj.unlink(cr, uid, [account_move['id']], context=context)
            self.write(cr, uid, [inv.id], {'state': 'cancel'}, context=context)
            self.infolog(cr, uid, _("The Physical inventory id:%s (%s) has been cancelled") % (inv.id, inv.name))
        return {}

PhysicalInventory()


class PhysicalInventoryCounting(osv.osv):
    _name = 'physical.inventory.counting'
    _description = 'Physical Inventory Counting Line'
    _order = 'default_code, line_no, id'

    _columns = {
        # Link to inventory
        'inventory_id': fields.many2one('physical.inventory', _('Inventory'), ondelete='cascade', select=True),

        # Product
        'product_id': fields.many2one('product.product', _('Product'), required=True, select=True,
                                      domain=[('type', 'not in', ['service_recep', 'consu'])]),
        'default_code': fields.related('product_id', 'default_code',  type='char', size=64, readonly=True, select=True, write_relate=False, store=True),
        'product_uom_id': fields.many2one('product.uom', _('Product UOM'), required=True),
        'standard_price': fields.float(_("Unit Price"), readonly=True),
        'currency_id': fields.many2one('res.currency', "Currency", readonly=True),
        'is_bn': fields.related('product_id', 'batch_management', string='BN', type='boolean', readonly=True),
        'is_ed': fields.related('product_id', 'perishable', string='ED', type='boolean', readonly=True),
        'is_kc': fields.related('product_id', 'is_kc', string='CC', type='boolean', readonly=True),
        'is_dg': fields.related('product_id', 'is_dg', string='DG', type='boolean', readonly=True),
        'is_cs': fields.related('product_id', 'is_cs', string='CS', type='boolean', readonly=True),

        # Batch / Expiry date
        'batch_number': fields.char(_('Batch number'), size=64),
        'expiry_date': fields.date(string=_('Expiry date')),
        # Specific to inventory
        'line_no': fields.integer(string=_('Line #'), readonly=True, select=1),
        'quantity': fields.char(_('Quantity'), size=15),
        'discrepancy': fields.boolean('Discrepancy found', readonly=True),

        # Actual batch number id, filled after the inventory switches to done
        'prod_lot_id': fields.many2one('stock.production.lot', 'Production Lot', readonly=True)
    }

    _sql_constraints = [
    ]

    def _auto_init(self, cr, context=None):
        res = super(PhysicalInventoryCounting, self)._auto_init(cr, context)
        # constraint already checked on file import and on generate disc.
        # deactivated because of BN/ED switch
        # inital constraint was incorrect bc not applied on ED prod (i.e when batch_name is null)
        cr.drop_constraint_if_exists('physical_inventory_counting', 'physical_inventory_counting_line_uniq')
        return res

    def create(self, cr, user, vals, context=None):
        # Compute line number
        if not vals.get('line_no'):
            cr.execute("""SELECT MAX(line_no) FROM physical_inventory_counting WHERE inventory_id=%s""",
                       (vals.get('inventory_id'),))
            vals['line_no'] = (cr.fetchone()[0] or 0) + 1  # Last line number + 1

        if (not vals.get('product_uom_id')
            or  not vals.get('standard_price')
                or  not vals.get('currency_id')):

            product_id = vals.get('product_id')
            product = self.pool.get("product.product").read(cr, user,
                                                            [product_id],
                                                            ["uom_id",
                                                             "standard_price",
                                                             "currency_id"],
                                                            context=context)[0]

            vals['product_uom_id'] = product['uom_id'][0]
            vals['standard_price'] = product['standard_price']
            vals['currency_id'] = product['currency_id'][0]

        return super(PhysicalInventoryCounting, self).create(cr, user, vals, context)

    def quantity_validate(self, cr, uid, quantity, uom_id=False):
        """Return a valide quantity or raise ValueError exception"""
        if quantity:
            float_width, float_prec = dp.get_precision('Product UoM')(cr)
            quantity = float(quantity)
            if quantity < 0:
                raise NegativeValueError()
            if math.isnan(quantity):
                raise ValueError()
            if uom_id:
                float_prec = int(abs(math.log10(self.pool.get('product.uom').read(cr, uid, uom_id, ['rounding'])['rounding'])))

            quantity = '%.*f' % (float_prec, quantity)
        return quantity

    def on_change_quantity(self, cr, uid, ids, quantity, uom_id=False):
        """Check and format quantity."""
        if quantity:
            try:
                quantity = self.quantity_validate(cr, uid, quantity, uom_id)
            except NegativeValueError:
                return {'value': {'quantity': False},
                        'warning': {'title': 'warning', 'message': 'Negative quantity is not permit.'}}
            except ValueError:
                return {'value': {'quantity': False},
                        'warning': {'title': 'warning', 'message': 'Enter a valid quantity.'}}
        return {'value': {'quantity': quantity}}

    def on_change_product_id(self, cr, uid, ids, product_id, uom=False):
        """Changes UoM and quantity if product_id changes."""
        bn = False
        ed = False
        if product_id and not uom:
            product_rec = self.pool.get('product.product').browse(cr, uid, product_id)
            uom = product_rec.uom_id and product_rec.uom_id.id
            bn = product_rec.batch_management
            ed = product_rec.perishable
        return {'value': {'quantity': False, 'product_uom_id': product_id and uom, 'is_bn': bn, 'is_ed': ed}}

    def perm_write(self, cr, user, ids, fields, context=None):
        pass


PhysicalInventoryCounting()


class PhysicalInventoryDiscrepancy(osv.osv):
    _name = 'physical.inventory.discrepancy'
    _description = 'Physical Inventory Discrepancy Line'
    _order = "default_code, line_no, id"

    def _discrepancy(self, cr, uid, ids, field_names, arg, context=None):
        context = context is None and {} or context
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        lines = read_many("physical.inventory.discrepancy", ids, ["theoretical_qty",
                                                                  "counted_qty",
                                                                  "standard_price"])

        discrepancies = {}
        for line in lines:
            discrepancy_qty = line["counted_qty"] - line["theoretical_qty"]
            discrepancy_value = discrepancy_qty * line["standard_price"]
            discrepancies[line["id"]] = { "discrepancy_qty": discrepancy_qty,
                                          "discrepancy_value": discrepancy_value }

        return discrepancies

    def _is_discrepancy_rt(self, cr, uid, ids, name, args,  context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        discr_rt_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
        for discr_line in self.browse(cr, uid, ids, fields_to_fetch=['reason_type_id'], context=context):
            res[discr_line.id] = discr_line.reason_type_id and discr_line.reason_type_id.id == discr_rt_id or False
        return res

    def _total_product_qty_and_values(self, cr, uid, ids, field_names, arg, context=None):
        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        discrepancy_lines = read_many(self._name, ids, ["product_id",
                                                        "standard_price",
                                                        "total_product_theoretical_qty",
                                                        "total_product_counted_qty" ])

        total_product_qty_and_values = {}
        for line in discrepancy_lines:
            id_ = line["id"]
            theo = line["total_product_theoretical_qty"]
            counted = line["total_product_counted_qty"]
            price = line["standard_price"]
            total_product_qty_and_values[id_] = {
                'total_product_counted_value': counted * price,
                'total_product_discrepancy_qty': counted - theo,
                'total_product_discrepancy_value': (counted - theo) * price
            }

        return total_product_qty_and_values

    _columns = {
        # Link to inventory
        'inventory_id': fields.many2one('physical.inventory', 'Inventory', ondelete='cascade'),
        'location_id': fields.related('inventory_id', 'location_id', type='many2one', relation='stock.location',  string='location_id', readonly=True),
        'inv_state': fields.related('inventory_id', 'state', type='char', size=64, string='Inventory state', readonly=True),

        # Product
        'product_id': fields.many2one('product.product', 'Product', required=True, readonly=True),
        'default_code': fields.related('product_id', 'default_code',  type='char', size=64, readonly=True, select=True, write_relate=False, store=True),

        'product_uom_id': fields.many2one('product.uom', 'UOM', required=True, readonly=True),

        'nomen_manda_2': fields.related('product_id', 'nomen_manda_2', string="Family",
                                        relation="product.nomenclature", type='many2one', readonly=True),

        'standard_price': fields.float(_("Unit Price"), readonly=True),
        'currency_id': fields.many2one('res.currency', "Currency", readonly=True),

        # BN / ED
        'batch_number': fields.char(_('Batch number'), size=64, readonly=True),
        'expiry_date': fields.date(string=_('Expiry date'), readonly=True),

        # Count
        'line_no': fields.integer(string=_('Line #'), readonly=True, select=1),
        'theoretical_qty': fields.float('Theoretical Quantity', digits_compute=dp.get_precision('Product UoM'), readonly=True, related_uom='product_uom_id'),
        'counted_qty': fields.float('Counted Quantity', digits_compute=dp.get_precision('Product UoM'), related_uom='product_uom_id'),
        'counted_qty_is_empty': fields.boolean('False qty', readonly=True, help=_('Has field counted_qty been filled or is it empty ? (internal use)')),
        'discrepancy_qty': fields.function(_discrepancy, multi="discrepancy", method=True, type='float', string=_("Discrepancy Quantity"), related_uom='product_uom_id'),
        'discrepancy_value': fields.function(_discrepancy, multi="discrepancy", method=True, type='float', string=_("Discrepancy Value")),

        # Discrepancy analysis
        'reason_type_id': fields.many2one('stock.reason.type', string='Adjustment type', select=True),
        'sub_reason_type': fields.selection([('encoding_err', 'Encoding Error'), ('process_err', 'Process Error'),  ('pick_err', 'Picking Error'), ('recep_err', 'Reception Error'),
                                             ('bn_err', 'Batch Number related Error'), ('unexpl_err', 'Unjustified/Unexplained Error')], string='Sub Reason type'),
        'comment': fields.char(size=128, string='Comment'),
        'discrepancy_rt': fields.function(_is_discrepancy_rt, type='boolean', string='The Adjustment type is Discrepancy', method=True, store=False),

        # Total for product
        'total_product_theoretical_qty': fields.float('Total Theoretical Quantity for product', digits_compute=dp.get_precision('Product UoM'), readonly=True, related_uom='product_uom_id'),
        'total_product_counted_qty': fields.float('Total Counted Quantity for product', digits_compute=dp.get_precision('Product UoM'), readonly=True, related_uom='product_uom_id'),
        'total_product_counted_value': fields.function(_total_product_qty_and_values, multi="total_product", method=True, type='float', string=_("Total Counted Value for product")),
        'total_product_discrepancy_qty': fields.function(_total_product_qty_and_values, multi="total_product", method=True, type='float', string=_("Total Discrepancy for product"), related_uom='product_uom_id'),
        'total_product_discrepancy_value': fields.function(_total_product_qty_and_values, multi="total_product", method=True, type='float', string=_("Total Discrepancy Value for product")),
        'ignored': fields.boolean('Ignored', readonly=True),
        'move_id': fields.integer(readonly=True)
    }


    def create(self, cr, user, vals, context=None):
        context = context is None and {} or context

        if (not vals.get('product_uom_id')
            or  not vals.get('standard_price')
                or  not vals.get('currency_id')):

            product_id = vals.get('product_id')
            product = self.pool.get("product.product").read(cr, user,
                                                            [product_id],
                                                            ["uom_id",
                                                             "standard_price",
                                                             "currency_id"],
                                                            context=context)[0]

            vals['product_uom_id'] = product['uom_id'][0]
            vals['standard_price'] = product['standard_price']
            vals['currency_id'] = product['currency_id'][0]

        return super(PhysicalInventoryDiscrepancy, self).create(cr, user, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        context = context is None and {} or context

        move_obj = self.pool.get("stock.move")
        for line in self.read(cr, uid, ids, ['reason_type_id', 'move_id'], context=context):
            reason_type_id = vals.get('reason_type_id', line['reason_type_id'] and line['reason_type_id'][0] or False)
            if reason_type_id != self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]:
                vals['sub_reason_type'] = False
            super(PhysicalInventoryDiscrepancy, self).write(cr, uid, [line['id']], vals, context=context)

            if not line["move_id"]:
                continue
            to_update = {}
            if reason_type_id:
                to_update["reason_type_id"] = reason_type_id
            if 'comment' in vals:
                to_update["comment"] = vals['comment']

            if to_update:
                if '__last_update' in context:
                    context['__last_update'] = {}
                move_obj.write(cr, uid, [line["move_id"]], to_update, context=context)

        return True

    def onchange_reason_type(self, cr, uid, ids, reason_type_id, context=None):
        if context is None:
            context = {}
        res = {'value': {'reason_type_id': reason_type_id}}
        discr_rt_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
        if reason_type_id != discr_rt_id:
            res['value'].update({'sub_reason_type': False, 'discrepancy_rt': False})
        else:
            res['value'].update({'discrepancy_rt': True})
        return res

    def perm_write(self, cr, user, ids, fields, context=None):
        pass


PhysicalInventoryDiscrepancy()
