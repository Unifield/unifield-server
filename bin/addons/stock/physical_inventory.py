# -*- coding: utf-8 -*-

import base64
import time
from dateutil.parser import parse
import math

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


    _columns = {
        'ref': fields.char('Reference', size=64, readonly=True),
        'name': fields.char('Name', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.datetime('Creation Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'responsible': fields.char('Responsible', size=128, required=False),
        'date_done': fields.datetime('Date done', readonly=True),
        'date_confirmed': fields.datetime('Date confirmed', readonly=True),
        'product_ids': fields.many2many('product.product', 'physical_inventory_product_rel',
                                        'product_id', 'inventory_id', string="Product selection", order_by="default_code"),
        'discrepancy_line_ids': fields.one2many('physical.inventory.discrepancy', 'inventory_id', 'Discrepancy lines',
                                                states={'closed': [('readonly', True)]}),
        'counting_line_ids': fields.one2many('physical.inventory.counting', 'inventory_id', 'Counting lines',
                                             states={'closed': [('readonly', True)]}),
        'location_id': fields.many2one('stock.location', 'Location', required=True, readonly=True,
                                       states={'draft': [('readonly', False)]}),
        'move_ids': fields.many2many('stock.move', 'physical_inventory_move_rel', 'inventory_id', 'move_id',
                                     'Created Moves', readonly=True),
        'state': fields.selection(PHYSICAL_INVENTORIES_STATES, 'State', readonly=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True, select=True, required=True,
                                      states={'draft': [('readonly', False)]}),
        'full_inventory': fields.boolean('Full inventory', readonly=True),
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
    }

    _defaults = {
        'ref': False,
        'date': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'state': 'draft',
        'full_inventory': False,
        'company_id': lambda self, cr, uid,
        c: self.pool.get('res.company')._company_default_get(cr, uid, 'physical.inventory', context=c)
    }

    _order = "ref desc, date desc"

    def create(self, cr, uid, values, context):
        context = context is None and {} or context
        values["ref"] = self.pool.get('ir.sequence').get(cr, uid, 'physical.inventory')

        return super(PhysicalInventory, self).create(cr, uid, values, context=context)


    def copy(self, cr, uid, id_, default=None, context=None):
        default = default is None and {} or default
        context = context is None and {} or context
        default = default.copy()

        default['state'] = 'draft'
        default['date'] = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        fields_to_empty = ["ref",
                           "full_inventory",
                           "date_done",
                           "file_to_import",
                           "file_to_import2",
                           "counting_line_ids",
                           "discrepancy_line_ids",
                           "move_ids"]

        for field in fields_to_empty:
            default[field] = False

        return super(PhysicalInventory, self).copy(cr, uid, id_, default, context=context)


    def perm_write(self, cr, user, ids, fields, context=None):
        pass


    def set_full_inventory(self, cr, uid, ids, context=None):
        context = context is None and {} or context

        # Set full inventory as true and unlink all products already selected
        self.write(cr, uid, ids, {'full_inventory': True,
                                  'product_ids': [(5)]}, context=context)
        return {}


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

        # Is it a full inventory ?
        full_inventory = read_single(self._name, inventory_id, 'full_inventory')

        # Create the wizard
        wiz_model = 'physical.inventory.select.products'
        wiz_values = {"inventory_id": inventory_id,
                      "full_inventory": full_inventory }
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
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def create(model, vals):
            return self.pool.get(model).create(cr, uid, vals, context=context)
        def view(module, view):
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, module, view)[1]

        # Prepare values to feed the wizard with
        assert len(ids) == 1
        inventory_id = ids[0]

        # Create the wizard
        wiz_model = 'physical.inventory.generate.counting.sheet'
        wiz_values = {"inventory_id": inventory_id}
        wiz_id = create(wiz_model, wiz_values)
        context['wizard_id'] = wiz_id

        # Get the view reference
        view_id = view('stock', 'physical_inventory_generate_counting_sheet')

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
        context = context if context else {}
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
        def write(model, id_, vals):
            return self.pool.get(model).write(cr, uid, [id_], vals, context=context)
        def write_many(model, ids, vals):
            return self.pool.get(model).write(cr, uid, ids, vals, context=context)

        # Get this inventory...
        assert len(inventory_ids) == 1
        inventory_id = inventory_ids[0]

        # Get the location and counting lines
        inventory = read_many(self._name, [inventory_id], [ "location_id",
                                                            "discrepancy_line_ids",
                                                            "counting_line_ids" ])[0]

        location_id = inventory["location_id"][0]
        counting_line_ids = inventory["counting_line_ids"]

        counting_lines = read_many('physical.inventory.counting',
                                   counting_line_ids,
                                   [ "line_no",
                                     "product_id",
                                     "product_uom_id",
                                     "standard_price",
                                     "currency_id",
                                     "batch_number",
                                     "expiry_date",
                                     "quantity"])

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
        for line in counting_lines:

            product_batch_expirydate = (line["product_id"][0],
                                        line["batch_number"] or False,
                                        line["expiry_date"])

            qty = float(line["quantity"]) if line["quantity"] else False
            counted_quantities[product_batch_expirydate] = qty

            counting_lines_per_product_batch_expirtydate[product_batch_expirydate] = {
                "line_id": line["id"],
                "line_no": line["line_no"]
            }

        # Create a similar dictionnary for existing discrepancies
        previous_discrepancy_line_ids = inventory["discrepancy_line_ids"]
        previous_discrepancy_lines = read_many('physical.inventory.discrepancy',
                                               previous_discrepancy_line_ids,
                                               [ "product_id",
                                                   "batch_number",
                                                   "expiry_date",
                                                   "ignored" ])

        previous_discrepancies = {}
        for line in previous_discrepancy_lines:
            product_batch_expirydate = (line["product_id"][0],
                                        line["batch_number"] or False,
                                        line["expiry_date"])
            previous_discrepancies[product_batch_expirydate] = {
                "id": line["id"],
                "ignored": line["ignored"],
                "todelete": True
            }

        ###################################################
        # Now, compare theoretical and counted quantities #
        ###################################################

        # First, create a unique set containing all product/batches
        all_product_batch_expirydate = set().union(theoretical_quantities,
                                                   counted_quantities)

        new_discrepancies = []
        update_discrepancies = {}
        counting_lines_with_no_discrepancy = []

        # For each of them, compare the theoretical and counted qty
        for product_batch_expirydate in all_product_batch_expirydate:

            # If the key is not known, assume 0
            theoretical_qty = theoretical_quantities.get(product_batch_expirydate, 0.0)
            counted_qty = counted_quantities.get(product_batch_expirydate, -1.0)

            # If no discrepancy, nothing to do
            # (Use a continue to save 1 indentation level..)
            if counted_qty == theoretical_qty:
                if product_batch_expirydate in counting_lines_per_product_batch_expirtydate:
                    counting_line_id = counting_lines_per_product_batch_expirtydate[product_batch_expirydate]["line_id"]
                    counting_lines_with_no_discrepancy.append(counting_line_id)
                continue

            # If this product/batch is known in the counting line, use
            # the existing line number
            if product_batch_expirydate in counting_lines_per_product_batch_expirtydate:
                this_product_batch_expirydate = counting_lines_per_product_batch_expirtydate[product_batch_expirydate]
                line_no = this_product_batch_expirydate["line_no"]

            # Otherwise, create additional line numbers starting from
            # the total of existing lines
            else:
                # FIXME : propably does not guarrantee uniqueness and
                # 'incremenctaliness' of line_no in some edge cases when
                # discrepancy report is regenerated multiple times...
                line_no = len(counted_quantities) + 1 + len(new_discrepancies)

            if product_batch_expirydate in previous_discrepancies:
                previous_discrepancies[product_batch_expirydate]["todelete"] = False
                existing_id = previous_discrepancies[product_batch_expirydate]["id"]
                update_discrepancies[existing_id] = {
                    "line_no": line_no,
                    "counted_qty": counted_qty
                }
            else:
                new_discrepancies.append( \
                    { "inventory_id": inventory_id,
                      "line_no": line_no,
                      "product_id": product_batch_expirydate[0],
                      "batch_number": product_batch_expirydate[1],
                      "expiry_date": product_batch_expirydate[2],
                      "theoretical_qty": theoretical_qty,
                      "counted_qty": counted_qty
                      })

        # Update discrepancy flags on counting lines
        counting_lines_with_discrepancy = [ l["id"] for l in counting_lines if  not l["id"] in counting_lines_with_no_discrepancy ]
        write_many("physical.inventory.counting", counting_lines_with_discrepancy,    {"discrepancy": True})
        write_many("physical.inventory.counting", counting_lines_with_no_discrepancy, {"discrepancy": False})

        # Sort discrepancies according to line number
        new_discrepancies = sorted(new_discrepancies, key=lambda d: d["line_no"])

        # Prepare the actual create/remove for discrepancy lines
        # 0 is for addition/creation
        # 1 is for update
        # 2 is the code for removal/deletion

        create_discrepancy_lines = [ (0,0,discrepancy) for discrepancy in new_discrepancies ]
        update_discrepancy_lines = [ (1,id_,values) for id_, values in update_discrepancies.items() ]
        delete_discrepancy_lines = [ (2,line["id"]) for line in previous_discrepancies.values() if line["todelete"] ]

        todo = []
        todo.extend(delete_discrepancy_lines)
        todo.extend(update_discrepancy_lines)
        todo.extend(create_discrepancy_lines)

        # Do the actual write
        write("physical.inventory", inventory_id, {'discrepancy_line_ids': todo, 'discrepancies_generated': True})


        self._update_total_product(cr, uid, inventory_id,
                                   theoretical_quantities,
                                   counted_quantities,
                                   context=context)

        return self.resolve_discrepancies_anomalies(cr, uid, inventory_id, context=context)


    def resolve_discrepancies_anomalies(self, cr, uid, inventory_id, context=None):
        context = context if context else {}
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
        def product_identity_str(line):
            str_ = "product '%s'" % line["product_id"][1]
            if line["batch_number"] or line["expiry_date"]:
                str_ += " with Batch number '%s' and Expiry date '%s'"  % (line["batch_number"] or '', line["expiry_date"] or '')
            else:
                str_ += " (no batch number / expiry date)"
            return str_

        discrepancy_line_ids = read_single("physical.inventory", inventory_id, 'discrepancy_line_ids')

        discrepancy_lines = read_many('physical.inventory.discrepancy',
                                      discrepancy_line_ids,
                                      [ "line_no",
                                        "product_id",
                                        "batch_number",
                                        "expiry_date",
                                        "counted_qty",
                                        "ignored"])

        anomalies = []
        for line in discrepancy_lines:
            if line["ignored"]:
                continue
            anomaly = False
            if line["counted_qty"] == False:
                anomaly = "Quantity for line %s, %s is incorrect." % (line["line_no"], product_identity_str(line))
            if line["counted_qty"] < 0.0:
                anomaly = "A line for %s was expected but not found." % product_identity_str(line)

            if anomaly:
                anomalies.append({"message": anomaly + " Ignore line or count as 0 ?",
                                  "line_id": line["id"]})

        if anomalies:
            return self.pool.get('physical.inventory.import.wizard').action_box(cr, uid, 'Warning', anomalies)
        else:
            return {}


    def _update_total_product(self, cr, uid, inventory_id, theoretical_qties, counted_qties, context=None):
        """
        theoretical_qties and counted_qties are indexed with (product_id, batchnumber, expirydate)
        """
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
        def write(model, id_, vals):
            return self.pool.get(model).write(cr, uid, [id_], vals, context=context)

        discrepancy_line_ids = read_single("physical.inventory",
                                           inventory_id,
                                           'discrepancy_line_ids')

        discrepancy_lines = read_many("physical.inventory.discrepancy",
                                      discrepancy_line_ids,
                                      ["product_id"])

        all_product_ids = set([ l["product_id"][0] for l in discrepancy_lines ])

        total_product_theoretical_qties = {}
        total_product_counted_qties = {}
        for product_id in all_product_ids:

            # FIXME : how to not take into account ignored lines in the count ? :/
            total_product_theoretical_qties[product_id] = sum([ qty for k, qty in theoretical_qties.items() if k[0] == product_id ])
            total_product_counted_qties[product_id] = sum([ qty for k, qty in counted_qties.items() if k[0] == product_id ])

        update_discrepancy_lines = {}
        for line in discrepancy_lines:
            id_ = line["id"]
            product_id = line["product_id"][0]
            update_discrepancy_lines[id_] = {
                'total_product_theoretical_qty': total_product_theoretical_qties[product_id],
                'total_product_counted_qty': total_product_counted_qties[product_id]
            }

        todo = [(1, idu, values) for idu, values in update_discrepancy_lines.items()]

        write("physical.inventory", inventory_id, {'discrepancy_line_ids':todo})


    def pre_process_discrepancies(self, cr, uid, items, context=None):
        discrepancies = self.pool.get('physical.inventory.discrepancy')
        ignore_ids = [item['line_id'] for item in items if item['action'] == 'ignore']
        count_ids = [item['line_id'] for item in items if item['action'] == 'count']

        if ignore_ids:
            discrepancies.write(cr, uid, ignore_ids, {'counted_qty': 0.0, 'ignored': True})
        if count_ids:
            discrepancies.write(cr, uid, count_ids, {'counted_qty': 0.0, 'ignored': False})

    def get_stock_for_products_at_location(self, cr, uid, product_ids, location_id, context=None):
        context = context if context else {}

        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)

        assert isinstance(product_ids, list)
        assert isinstance(location_id, int)

        # Get all the moves for in/out of that location for the products
        move_for_products_at_location = ['&', '&', '|',
                                         ('location_id', 'in', [location_id]),
                                         ('location_dest_id', 'in', [location_id]),
                                         ("product_id", 'in', product_ids),
                                         ('state', '=', 'done')]

        moves_at_location_ids = search("stock.move", move_for_products_at_location)
        moves_at_location = read_many("stock.move",
                                      moves_at_location_ids,
                                      ["product_id",
                                       "product_qty",
                                       "prodlot_id",
                                       "expired_date",
                                       "location_id",
                                       "location_dest_id"])

        # Sum all lines to get a set of (product, batchnumber) -> qty
        stocks = {}
        for move in moves_at_location:

            product_id = move["product_id"][0]
            product_qty = move["product_qty"]
            batch_number = move["prodlot_id"][1] if move["prodlot_id"] else False
            expiry_date = move["expired_date"]

            # Dirty hack to ignore/hide internal batch numbers ("MSFBN")
            if batch_number and batch_number.startswith("MSFBN"):
                batch_number = False

            product_batch_expirydate = (product_id, batch_number, expiry_date)

            # Init the quantity to 0 if batch is not present in dict yet
            # (NB: batch_id can be None, but that's not an issue for dicts ;))
            if not product_batch_expirydate in stocks.keys():
                stocks[product_batch_expirydate] = 0.0

            move_out = (move["location_id"][0] == location_id)
            move_in = (move["location_dest_id"][0] == location_id)

            if move_in:
                stocks[product_batch_expirydate] += product_qty
            elif move_out:
                stocks[product_batch_expirydate] -= product_qty
            else:
                # This shouldnt happen
                pass

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
        counting_sheet_lines = []
        counting_sheet_errors = []

        def add_error(message, file_row, file_col=None):
            if file_col is not None:
                _msg = 'Cell %s%d: %s' % (chr(0x41 + file_col), file_row + 1, message)
            else:
                _msg = 'Line %d: %s' % (file_row + 1, message)
            counting_sheet_errors.append(_msg)

        inventory_rec = self.browse(cr, uid, ids, context=context)[0]
        if not inventory_rec.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        counting_sheet_file = SpreadsheetXML(xmlstring=base64.decodestring(inventory_rec.file_to_import))

        product_obj = self.pool.get('product.product')
        product_uom_obj = self.pool.get('product.uom')
        counting_obj = self.pool.get('physical.inventory.counting')

        line_list = []
        line_items = []

        for row_index, row in enumerate(counting_sheet_file.getRows()):
            # === Process header ===

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
                if inventory_rec.ref != (inventory_reference or '').strip():
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
                add_error(_("""Reference is different to inventory reference, you should have exactly 10 columns in this order:
Line #, Item Code, Description, UoM, Quantity counted, Batch number, Expiry date, Specification, BN Management, ED Management"""), row_index)
                break

            # Check line number
            line_no = row.cells[0].data
            if line_no is not None:
                try:
                    line_no = int(line_no)
                    if line_no in line_list:
                        add_error("""Line number is duplicate. If you added a line, please keep the line number empty.""", row_index, 0)
                    line_list.append(line_no)
                except ValueError:
                    line_no = None
                    add_error("""Invalid line number""", row_index, 0)

            # Check product_code
            product_code = row.cells[1].data
            product_ids = product_obj.search(cr, uid, [('default_code', '=like', product_code)], context=context)
            product_id = False
            if len(product_ids) == 1:
                product_id = product_ids[0]
            else:
                add_error("""Product %s not found""" % product_code, row_index, 1)

            # Check UoM
            product_uom_id = False
            product_uom = row.cells[3].data
            product_uom_ids = product_uom_obj.search(cr, uid, [('name', '=like', product_uom)])
            if len(product_uom_ids) == 1:
                product_uom_id = product_uom_ids[0]
            else:
                add_error("""UoM %s unknown""" % product_uom, row_index, 3)

            # Check quantity
            quantity = row.cells[4].data
            try:
                quantity = counting_obj.quantity_validate(cr, quantity)
            except NegativeValueError:
                add_error('Quantity %s is negative' % quantity, row_index, 4)
                quantity = 0.0
            except ValueError:
                quantity = 0.0
                add_error('Quantity %s is not valide' % quantity, row_index, 4)

            product_info = product_obj.read(cr, uid, product_id, ['batch_management', 'perishable'])

            # Check batch number
            batch_name = row.cells[5].data
            if not batch_name and product_info['batch_management'] and float(quantity or 0) > 0:
                add_error('Batch number is required', row_index, 5)

            # Check expiry date
            expiry_date = row.cells[6].data
            if expiry_date:
                expiry_date_type = row.cells[6].type
                try:
                    if expiry_date_type == 'datetime':
                        expiry_date = expiry_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    elif expiry_date_type == 'str':
                        expiry_date = parse(expiry_date).strftime(DEFAULT_SERVER_DATE_FORMAT)
                    else:
                        raise ValueError()
                except ValueError:
                    add_error("""Expiry date %s is not valide""" % expiry_date, row_index, 6)
            if not expiry_date and product_info['perishable'] and float(quantity or 0) > 0:
                add_error('Expiry date is required', row_index, 6)

            # Check duplicate line (Same product_id, batch_number, expirty_date)
            item = '%d-%s-%s' % (product_id or -1, batch_name or '', expiry_date or '')
            if item in line_items and (batch_name or expiry_date):
                add_error("""Duplicate line (same product, batch number and expiry date)""", row_index)
            else:
                line_items.append(item)

            data = {
                'line_no': line_no,
                'product_id': product_id,
                'batch_number': batch_name,
                'expiry_date': expiry_date,
                'quantity': quantity,
                'product_uom_id': product_uom_id,
            }

            # Check if line exist
            if line_no:
                line_ids = counting_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id), ('line_no', '=', line_no)])
            else:
                line_ids = counting_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id),
                                                         ('product_id', '=', product_id),
                                                         ('batch_number', '=', batch_name),
                                                         ('expiry_date', '=', expiry_date)])
                if line_ids:
                    del data["line_no"]

            if len(line_ids) > 0:
                counting_sheet_lines.append((1, line_ids[0], data))
            else:
                counting_sheet_lines.append((0, 0, data))

        # endfor

        context['import_in_progress'] = True
        wizard_obj = self.pool.get('physical.inventory.import.wizard')
        if counting_sheet_errors:
            # Errors found, open message box for exlain
            self.write(cr, uid, ids, {'file_to_import': False}, context=context)
            result = wizard_obj.message_box(cr, uid, title='Importation errors', message='\n'.join(counting_sheet_errors))
        else:
            # No error found. Write counting lines on Inventory
            vals = {
                'file_to_import': False,
                'responsible': counting_sheet_header.get('inventory_counter_name'),
                'counting_line_ids': counting_sheet_lines
            }
            self.write(cr, uid, ids, vals, context=context)
            result = wizard_obj.message_box(cr, uid, title='Information', message='Counting sheet successfully imported.')
        context['import_in_progress'] = False

        return result

    def import_xls_discrepancy_report(self, cr, uid, ids, context=None):
        """Import an exported discrepancy report"""
        if not context:
            context = {}

        discrepancy_report_lines = []
        discrepancy_report_errors = []

        def add_error(message, file_row, file_col):
            discrepancy_report_errors.append('Cell %s%d: %s' % (chr(0x41 + file_col), file_row + 1, message))

        inventory_rec = self.browse(cr, uid, ids, context=context)[0]
        if not inventory_rec.file_to_import2:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        discrepancy_report_file = SpreadsheetXML(xmlstring=base64.decodestring(inventory_rec.file_to_import2))

        # product_obj = self.pool.get('product.product')
        # product_uom_obj = self.pool.get('product.uom')
        # counting_obj = self.pool.get('physical.inventory.counting')
        reason_type_obj = self.pool.get('stock.reason.type')
        discrepancy_obj = self.pool.get('physical.inventory.discrepancy')

        for row_index, row in enumerate(discrepancy_report_file.getRows()):
            if row_index < 10:
                continue
            if len(row) != 20:
                add_error(_("""Reference is different to inventory reference, you should have exactly 20 columns in this order:
Line #, Family, Item Code, Description, UoM, Unit Price, currency (functional), Quantity Theorical, Quantity counted, Batch no, Expiry Date, Discrepancy, Discrepancy value, Total QTY before INV, Total QTY after INV, Total Value after INV, Discrepancy, Discrepancy Value, Adjustement type, Comments / actions (in case of discrepancy)"""),
                          row_index, len(row))
                break
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
                    add_error('Unknown adjustment type %s' % adjustment_type, row_index, 18)
                    adjustment_type = False

            comment = row.cells[19].data

            line_no = row.cells[0].data
            line_ids = discrepancy_obj.search(cr, uid, [('inventory_id', '=', inventory_rec.id), ('line_no', '=', line_no)])
            if line_ids:
                line_no = line_ids[0]
            else:
                add_error('Unknown line no %s' % line_no, row_index, 0)
                line_no = False

            discrepancy_report_lines.append((1, line_no, {'reason_type_id': adjustment_type, 'comment': comment}))
        # endfor

        context['import_in_progress'] = True
        wizard_obj = self.pool.get('physical.inventory.import.wizard')
        if discrepancy_report_errors:
            # Errors found, open message box for exlain
            self.write(cr, uid, ids, {'file_to_import2': False}, context=context)
            result = wizard_obj.message_box(cr, uid, title='Importation errors',
                                            message='\n'.join(discrepancy_report_errors))
        else:
            # No error found. update comment and reason for discrepancies lines on Inventory
            vals = {'file_to_import2': False, 'discrepancy_line_ids': discrepancy_report_lines}
            self.write(cr, uid, ids, vals, context=context)
            result = wizard_obj.message_box(cr, uid, title='Information',
                                            message='Discrepancy report successfully imported.')
        context['import_in_progress'] = False

        return result

    def export_xls_discrepancy_report(self, cr, uid, ids, context=None):
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

    def action_validate(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)
        return {}

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirm the inventory, close the stock moves and writes its finished date"""

        if context is None:
            context = {}

        # to perform the correct inventory corrections we need analyze stock location by
        # location, never recursively, so we use a special context
        product_context = dict(context, compute_child=False)

        # location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        product_tmpl_obj = self.pool.get('product.template')
        prod_lot_obj = self.pool.get('stock.production.lot')
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        product_dict = {}
        product_tmpl_dict = {}

        for inv in self.read(cr, uid, ids, ['counting_line_ids',
                                            'discrepancy_line_ids',
                                            'date',
                                            'name'], context=context):
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
                    errors.append('Line %d: Adjustement type missing' % line['line_no'])

            if errors:
                # Errors found, open message box for exlain
                wizard_obj = self.pool.get('physical.inventory.import.wizard')
                return wizard_obj.message_box(cr, uid, title='Confirmation errors', message='\n'.join(errors))


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
                    'name': 'INV:' + str(inv['id']) + ':' + inv['name'],
                    'product_id': line['product_id'][0],
                    'product_uom': line['product_uom_id'][0],
                    'prodlot_id': lot_id,
                    'date': inv['date'],
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

            message = _('Inventory') + " '" + inv['name'] + "' " + _("is validated.")
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


    def action_cancel_draft(self, cr, uid, ids, context=None):
        """ Cancels the stock move and change inventory state to draft."""
        for inv in self.read(cr, uid, ids, ['move_ids'], context=context):
            self.pool.get('stock.move').action_cancel(cr, uid, inv['move_ids'], context=context)
        self.write(cr, uid, ids, {'state': 'draft'}, context=context)
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
            self.infolog(cr, uid, "The Physical inventory id:%s (%s) has been cancelled" % (inv.id, inv.name))
        return {}


PhysicalInventory()


class PhysicalInventoryCounting(osv.osv):
    _name = 'physical.inventory.counting'
    _description = 'Physical Inventory Counting Line'

    _columns = {
        # Link to inventory
        'inventory_id': fields.many2one('physical.inventory', _('Inventory'), ondelete='cascade', select=True),

        # Product
        'product_id': fields.many2one('product.product', _('Product'), required=True, select=True,
                                      domain=[('type', '<>', 'service')]),
        'product_uom_id': fields.many2one('product.uom', _('Product UOM'), required=True),
        'standard_price': fields.float(_("Unit Price"), readonly=True),
        'currency_id': fields.many2one('res.currency', "Currency", readonly=True),
        'is_bn': fields.related('product_id', 'batch_management', string='BN', type='boolean', readonly=True),
        'is_ed': fields.related('product_id', 'perishable', string='ED', type='boolean', readonly=True),
        'is_kc': fields.related('product_id', 'is_kc', string='KC', type='boolean', readonly=True),
        'is_dg': fields.related('product_id', 'is_dg', string='DG', type='boolean', readonly=True),
        'is_cs': fields.related('product_id', 'is_cs', string='CS', type='boolean', readonly=True),

        # Batch / Expiry date
        'batch_number': fields.char(_('Batch number'), size=30),
        'expiry_date': fields.date(string=_('Expiry date')),

        # Specific to inventory
        'line_no': fields.integer(string=_('Line #'), readonly=True),
        'quantity': fields.char(_('Quantity'), size=15),
        'discrepancy': fields.boolean('Discrepancy found', readonly=True),

        # Actual batch number id, filled after the inventory switches to done
        'prod_lot_id': fields.many2one('stock.production.lot', 'Production Lot', readonly=True)
    }

    _sql_constraints = [
        ('line_uniq', 'UNIQUE(inventory_id, product_id, batch_number, expiry_date)', _('The line product, batch number and expiry date must be unique!')),
    ]

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

    @staticmethod
    def quantity_validate(cr, quantity):
        """Return a valide quantity or raise ValueError exception"""
        if quantity:
            float_width, float_prec = dp.get_precision('Product UoM')(cr)
            quantity = float(quantity)
            if quantity < 0:
                raise NegativeValueError()
            if math.isnan(quantity):
                raise ValueError()
            quantity = '%.*f' % (float_prec, quantity)
        return quantity

    def on_change_quantity(self, cr, uid, ids, quantity):
        """Check and format quantity."""
        if quantity:
            try:
                quantity = self.quantity_validate(cr, quantity)
            except NegativeValueError:
                return {'value': {'quantity': False},
                        'warning': {'title': 'warning', 'message': 'Negative quantity is not permit.'}}
            except ValueError:
                return {'value': {'quantity': False},
                        'warning': {'title': 'warning', 'message': 'Enter a valid quantity.'}}
        return {'value': {'quantity': quantity}}

    def on_change_product_id(self, cr, uid, ids, product_id, uom=False):
        """Changes UoM and quantity if product_id changes."""
        if product_id and not uom:
            product_rec = self.pool.get('product.product').browse(cr, uid, product_id)
            uom = product_rec.uom_id and product_rec.uom_id.id
        return {'value': {'quantity': False, 'product_uom_id': product_id and uom}}

    def perm_write(self, cr, user, ids, fields, context=None):
        pass


PhysicalInventoryCounting()


class PhysicalInventoryDiscrepancy(osv.osv):
    _name = 'physical.inventory.discrepancy'
    _description = 'Physical Inventory Discrepancy Line'


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

        # Product
        'product_id': fields.many2one('product.product', 'Product', required=True),

        'product_uom_id': fields.many2one('product.uom', 'UOM', required=True, readonly=True),

        'nomen_manda_2': fields.related('product_id', 'nomen_manda_2', string="Family",
                                        relation="product.nomenclature", type='many2one', readonly=True),

        'standard_price': fields.float(_("Unit Price"), readonly=True),
        'currency_id': fields.many2one('res.currency', "Currency", readonly=True),

        # BN / ED
        'batch_number': fields.char(_('Batch number'), size=30, readonly=True),
        'expiry_date': fields.date(string=_('Expiry date')),

        # Count
        'line_no': fields.integer(string=_('Line #'), readonly=True),
        'theoretical_qty': fields.float('Theoretical Quantity', digits_compute=dp.get_precision('Product UoM'), readonly=True),
        'counted_qty': fields.float('Counted Quantity', digits_compute=dp.get_precision('Product UoM')),
        'discrepancy_qty': fields.function(_discrepancy, multi="discrepancy", method=True, type='float', string=_("Discrepancy Quantity")),
        'discrepancy_value': fields.function(_discrepancy, multi="discrepancy", method=True, type='float', string=_("Discrepancy Value")),

        # Discrepancy analysis
        'reason_type_id': fields.many2one('stock.reason.type', string='Adjustment type', select=True),
        'comment': fields.char(size=128, string='Comment'),

        # Total for product
        'total_product_theoretical_qty': fields.float('Total Theoretical Quantity for product', digits_compute=dp.get_precision('Product UoM'), readonly=True),
        'total_product_counted_qty': fields.float('Total Counted Quantity for product', digits_compute=dp.get_precision('Product UoM'), readonly=True),
        'total_product_counted_value': fields.function(_total_product_qty_and_values, multi="total_product", method=True, type='float', string=_("Total Counted Value for product")),
        'total_product_discrepancy_qty': fields.function(_total_product_qty_and_values, multi="total_product", method=True, type='float', string=_("Total Discrepancy for product")),
        'total_product_discrepancy_value': fields.function(_total_product_qty_and_values, multi="total_product", method=True, type='float', string=_("Total Discrepancy Value for product")),
        'ignored': fields.boolean('Ignored', readonly=True),
        'move_id': fields.integer(readonly=True)
    }

    _order = "product_id asc, line_no asc"

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

        r = super(PhysicalInventoryDiscrepancy, self).write(cr, uid, ids, vals, context=context)
        move_obj = self.pool.get("stock.move")

        lines = self.read(cr, uid, ids, ["move_id", "comment"], context=context)

        for line in lines:
            if not line["move_id"]:
                continue
            reason_type_id = vals.get("reason_type_id", False)
            comment = vals.get("comment", False)
            to_update = {}
            if reason_type_id:
                to_update["reason_type_id"] = reason_type_id
            if comment:
                to_update["comment"] = comment
            if to_update:
                move_obj.write(cr, uid, [line["move_id"]], to_update, context=context)

        return r


    def perm_write(self, cr, user, ids, fields, context=None):
        pass


PhysicalInventoryDiscrepancy()
