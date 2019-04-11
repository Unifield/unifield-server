#-*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

import datetime
from osv import fields, osv
import pooler
import logging


class stock_production_lot(osv.osv):
    _inherit = 'stock.production.lot'
    _logger = logging.getLogger('------ BATCH MIGRATIONS ')

    def _get_date(dtype):
        """Return a function to compute the limit date for this type"""
        def calc_date(self, cr, uid, context=None):
            """Compute the limit date for a given date"""
            if context is None:
                context = {}
            if not context.get('product_id', False):
                date = False
            else:
                product = pooler.get_pool(cr.dbname).get('product.product').browse(
                    cr, uid, context['product_id'])
                duration = getattr(product, dtype)
                # set date to False when no expiry time specified on the product
                date = duration and (datetime.datetime.today()
                                     + datetime.timedelta(days=duration))
            return date and date.strftime('%Y-%m-%d %H:%M:%S') or False
        return calc_date

    _columns = {
        'life_date': fields.datetime('End of Life Date',
                                     help='The date on which the lot may become dangerous and should not be consumed.'),
        'use_date': fields.datetime('Best before Date',
                                    help='The date on which the lot starts deteriorating without becoming dangerous.'),
        'removal_date': fields.datetime('Removal Date',
                                        help='The date on which the lot should be removed.'),
        'alert_date': fields.datetime('Alert Date', help="The date on which an alert should be notified about the production lot."),
    }
    # Assign dates according to products data
    def create(self, cr, uid, vals, context=None):

        if self.violate_ed_unique(cr, uid, False, vals, context):
            raise osv.except_osv('Error', 'An expiry date with same date for this product exists already!.')

        newid = super(stock_production_lot, self).create(cr, uid, vals, context=context)
        obj = self.browse(cr, uid, newid, context=context)
        towrite = []
        for f in ('life_date', 'use_date', 'removal_date', 'alert_date'):
            if not getattr(obj, f):
                towrite.append(f)
        if context is None:
            context = {}
        context['product_id'] = obj.product_id.id
        self.write(cr, uid, [obj.id], self.default_get(cr, uid, towrite, context=context))
        return newid

    # US-838: this method is to check if the expiry date values are valid
    def violate_ed_unique(self, cr, uid, ids, vals, context):
        if not('product_id' in vals and 'life_date' in vals):
            return False

        prod_obj = self.pool.get('product.product')
        prod = prod_obj.browse(cr, uid, vals['product_id'], context=context)

        # In case it's a EP only product, then search for date and product, no need to search for batch name
        if prod.perishable and not prod.batch_management:
            search_arg = [('life_date', '=', vals['life_date']), ('type', '=', 'internal'), ('product_id', '=', prod.id)]

            if ids: # in case it's a write call, then exclude the current ids
                search_arg.append(('id', 'not in', ids))

            lot_ids = self.search(cr, uid, search_arg, context=context)
            if lot_ids:
                return True
        return False

    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # US-838: Check if the values are in conflict with the existing data
        if self.violate_ed_unique(cr, uid, ids, vals, context):
            raise osv.except_osv('Error', 'An expiry date with same date for this product exists already!')

        return super(stock_production_lot, self).write(cr, uid, ids, vals, context=context)

    # US-1469: Restore missing batches that have been wrongly deleted in US-838
    def us_1469_restore_deleted_batch(self, cr, uid, *a, **b):
        self._logger.info("\n\n______________________Start to restore batch objects for instance: %s\n", cr.dbname)

        # Reset the constraint just in case the previous update has changed again to the original
        cr.execute('''ALTER TABLE stock_production_lot DROP CONSTRAINT stock_production_lot_batch_name_uniq,
                ADD CONSTRAINT stock_production_lot_batch_name_uniq UNIQUE (name, product_id, life_date);''')

        list_table_fields = [
            ('stock_move', 'prodlot_id'),
        ]
        for element in list_table_fields:
            self.us_1469_restore_deleted_batch_for_table(cr, uid, element[0], element[1], 'expired_date')


        list_table_fields = [
            ('create_picking_move_processor', 'prodlot_id'),
            ('export_report_stock_inventory', 'prodlot_id'),
            ('export_report_stock_move', 'prodlot_id'),
            ('internal_move_processor', 'prodlot_id'),
            ('outgoing_delivery_move_processor', 'prodlot_id'),
            ('real_average_consumption_line', 'prodlot_id'),
            ('return_ppl_move_processor', 'prodlot_id'),
            ('stock_move_in_processor', 'prodlot_id'),
            ('stock_move_processor', 'prodlot_id'),
            ('unconsistent_stock_report_line', 'prodlot_id'),
            ('validate_move_processor', 'prodlot_id'),
            ('stock_inventory_line', 'prod_lot_id'),
            ('initial_stock_inventory_line', 'prod_lot_id'),
        ]
        for element in list_table_fields:
            self.us_1469_restore_deleted_batch_for_table(cr, uid, element[0], element[1], 'expiry_date')

        self._logger.info("______________________Finish the migration task on duplicate batch objects for instance: %s\n\n", cr.dbname)
        return True

    def us_1469_restore_deleted_batch_for_table(self, cr, uid, table_name, field_id, field_expiry_name):
        # For each table, search for the missing batch
        # 1. Table stock_move
        sql_x = 'select lot.name, move.product_id, move.' + field_expiry_name + ' as life_date from ' + table_name + ' move, stock_production_lot lot, product_product prod where move.'
        sql_x = sql_x + field_id + ' = lot.id and move.product_id != lot.product_id  and move.product_id = prod.id and '
        sql_x = sql_x + ' (prod.batch_management = \'t\' OR prod.perishable = \'t\') group by lot.name, move.product_id, move.' + field_expiry_name +'  order by lot.name;'  # not_a_user_entry

        cr.execute(sql_x)

        list_bn_prod = cr.dictfetchall()
        if len(list_bn_prod) == 0:
            self._logger.info("__________NOTHING to process for this table: %s! \n" % (table_name))
            return
        else:
            self._logger.info("__________Start to restore missing batch objects in table: %s _____ - for %s batches! \n %s" % (table_name, len(list_bn_prod), list_bn_prod))

        lot_obj = self.pool.get('stock.production.lot')
        prod_obj = self.pool.get('product.product')

        for bn_prod in list_bn_prod:
            batch_name = bn_prod.get('name')
            prod_id = bn_prod.get('product_id')
            life_date = bn_prod.get('life_date')

            self._logger.info("___Start to process the batch::::::: %s" % (batch_name))

            # 2. Search if this missing batch has been created in the mean time
            batch_id = lot_obj.search(cr, uid, [('name', '=', batch_name), ('product_id', '=', prod_id), ('life_date', '=', life_date)])
            if batch_id:
                batch_id = batch_id[0]

                sql_up = 'update ' + table_name + ' set ' + field_id + '=' + str(batch_id) + ' where id in (select move.id from ' + table_name
                sql_up = sql_up + ' move, stock_production_lot lot where move.' + field_id + " = lot.id and lot.name= '" + batch_name + "' and move.product_id = " + str(prod_id) + " and move." + field_expiry_name + "='" + life_date + "');"  # not_a_user_entry

                cr.execute(sql_up)
                self._logger.info("--- Step 3: Batch already created. Now assign all the ref lines of table %s with wrong batch references to the new batch: %s\n"%(table_name, batch_id))
            else:
                # not exist, now create a new one
                lots = lot_obj.search(cr, uid, [('name', '=', batch_name)])
                if not lots:
                    continue

                existing_batch = lot_obj.browse(cr, uid, lots[0])
                prod_type = prod_obj.read(cr, uid, prod_id, ['perishable', 'batch_management'])
                # US-1476: treat differently for internal batch. No need to create if same product and same date exists!
                if existing_batch.type == 'internal' or (prod_type['perishable'] and not prod_type['batch_management']):
                    batch_id = lot_obj.search(cr, uid, [('product_id', '=', prod_id), ('life_date', '=', life_date)])
                    if batch_id:
                        batch_id = batch_id[0]
                        self._logger.info("--- Step 2: Internal Batch existed.\n")
                    else:
                        # If the product is ED only, and no batch existed for it, create a new one
                        vals = {'name': existing_batch.name,'product_id': prod_id, 'date':existing_batch.date, 'life_date':life_date, 'type':'internal', 'sequence_id': 1}
                        batch_id = lot_obj.create(cr, uid, vals)
                        self._logger.info("--- Step 2: A new INTERNAL batch has been DUPLICATED from the batch %s, product_id: %s and expiry date %s!\n"%(batch_name, prod_id, life_date))

                if not batch_id:
                    # Prepare the new batch to create, with almost same values, except the product id
                    vals = {'name': existing_batch.name, 'product_id': prod_id, 'date':existing_batch.date, 'life_date':life_date, 'type':existing_batch.type}
                    batch_id = lot_obj.create(cr, uid, vals)
                    self._logger.info("--- Step 2: A new batch has been DUPLICATED from the batch %s, product_id: %s and expiry date %s!\n"%(batch_name, prod_id,life_date))

                # 3. Now search all the move lines that still have the reference to the wrong BN, assign them to the new batch_id
                self._logger.info("--- Step 3: Now assign all the ref lines of table %s with wrong batch references to the new batch: %s\n"%(table_name, batch_id))
                if batch_id:
                    sql_up = 'update ' + table_name + ' set ' + field_id + ' = ' + str(batch_id) + ' where product_id=' + str(prod_id) + ' and ' + field_id + '=' + str(existing_batch.id)
                    sql_up = sql_up + " and " + field_expiry_name + "='" + life_date + "';"  # not_a_user_entry
                    cr.execute(sql_up)

        self._logger.info("__________Finish the migration task on duplicate batch objects for table: %s\n", table_name)
        return True

    #US-838: migrate all the duplicated batch into single batch
    '''

        US-838: The 3 following methods will be moved to the patch call, it is called only when a patch is applied.
        Check the steps to be executed in the description, but basically it will migrate the references to the wrong BN in relevant objects
        to the lead BN, then delete these wrong BNs, and finally redefine the unique constraint on the table BN

        method to move: migrate_dup_batch, remap_reference_tables, update_table

    '''
    def us_838_migrate_dup_batch(self, cr, uid, *a, **b):
        '''
        Step to do:

        1. Search list of dup batches, that have the same name + product + xmlname values.
        2. Go through this list, for each element do the following:
            2.1. Get the 2 batch id of the same name, order by id ---> the smaller id will be kept, the other will be set as inactive
            2.2. Search all tables that refer to the bigger_id, then map them to the smaller_id
            2.3. Set the non-lead batches to become inactive
            2.4. Update ir_model_data
        3. Modify the unique constraint to be prod + BN + ED, and no more partner_name involved, because we will not use partner_name anymore

        4. For the messages in the pipeline ---> treated in sync message

        '''

        context = {}

        cr.execute('''select name, product_id, life_date from (select name, product_id, life_date, count(name) as amount_bn from stock_production_lot group by name, product_id, life_date) as foo_bn where amount_bn>1;''')
        all_dup_batches = cr.dictfetchall()
        self._logger.info("__________Start to migrate duplicate batch objects in instance: %s - with total of %s duplicate batches!\n" % (cr.dbname, len(all_dup_batches)))

        to_be_deleted = []
        for r in all_dup_batches:
            batch_ids = self.search(cr, uid, [('name', '=', r['name']), ('product_id', '=', r['product_id']), ('life_date', '=', r['life_date'])])

            lead_id = batch_ids[0]
            for wrong_id in range(1, len(batch_ids)):
                # Do step 2.2, search the following tables to replace the link to the
                self.remap_reference_tables(cr, uid, batch_ids[wrong_id], lead_id, r['name'], context)

                # 2.3: Add this wrong batch id into the list, then delete them at the end
                to_be_deleted.append(batch_ids[wrong_id])

        # 2.3 call to delete all the wrong batch objects
        if to_be_deleted:
            self._logger.info("Delete duplicate batch objects (%s batches - keep only the lead batch)\n" % len(to_be_deleted))
            self.unlink(cr, uid, to_be_deleted, context=context)
        else:
            self._logger.info("No duplicate batch found for this instance %s.\n", cr.dbname)

        self._logger.info("Last step: update the unique constraint for the table stock_production_lot.\n")
        # 3. Now alter the constraint unique of this table: first drop the current constraint, then create a new one with name+prod+life_date
        cr.execute('''ALTER TABLE stock_production_lot DROP CONSTRAINT stock_production_lot_batch_name_uniq,
                ADD CONSTRAINT stock_production_lot_batch_name_uniq UNIQUE (name, product_id, life_date);''')

        self._logger.info("__________Finish the migration task on duplicate batch objects for instance: %s\n", cr.dbname)
        return True

    def remap_reference_tables(self, cr, uid, wrong_id, lead_id, batch_name, context=None):
        '''
        -- with fkey = prodlot_id (total=13)
            TABLE "create_picking_move_processor" CONSTRAINT "create_picking_move_processor_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "export_report_stock_inventory" CONSTRAINT "export_report_stock_inventory_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "export_report_stock_move" CONSTRAINT "export_report_stock_move_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "internal_move_processor" CONSTRAINT "internal_move_processor_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "outgoing_delivery_move_processor" CONSTRAINT "outgoing_delivery_move_processor_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "real_average_consumption_line" CONSTRAINT "real_average_consumption_line_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "return_ppl_move_processor" CONSTRAINT "return_ppl_move_processor_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "stock_move_in_processor" CONSTRAINT "stock_move_in_processor_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "stock_move_processor" CONSTRAINT "stock_move_processor_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "stock_move" CONSTRAINT "stock_move_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "unconsistent_stock_report_line" CONSTRAINT "unconsistent_stock_report_line_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE CASCADE
            TABLE "validate_move_processor" CONSTRAINT "validate_move_processor_prodlot_id_fkey" FOREIGN KEY (prodlot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL

        -- with fkey = lot_id (2)
            TABLE "stock_production_lot_revision" CONSTRAINT "stock_production_lot_revision_lot_id_fkey" FOREIGN KEY (lot_id) REFERENCES stock_production_lot(id) ON DELETE CASCADE
            TABLE "product_likely_expire_report_item_line" CONSTRAINT "product_likely_expire_report_item_line_lot_id_fkey" FOREIGN KEY (lot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL

        -- with fkey = prod_lot_id (2)
            TABLE "stock_inventory_line" CONSTRAINT "stock_inventory_line_prod_lot_id_fkey" FOREIGN KEY (prod_lot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "initial_stock_inventory_line" CONSTRAINT "initial_stock_inventory_line_prod_lot_id_fkey" FOREIGN KEY (prod_lot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL

        -- with fkey = no common name (3)
            TABLE "claim_product_line" CONSTRAINT "claim_product_line_lot_id_claim_product_line_fkey" FOREIGN KEY (lot_id_claim_product_line) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "composition_kit" CONSTRAINT "composition_kit_composition_lot_id_fkey" FOREIGN KEY (composition_lot_id) REFERENCES stock_production_lot(id) ON DELETE SET NULL
            TABLE "wizard_import_in_line_simulation_screen" CONSTRAINT "wizard_import_in_line_simulation_screen_imp_batch_id_fkey" FOREIGN KEY (imp_batch_id) REFERENCES stock_production_lot(id) ON DELETE SET
        '''
        # Tables with foreign key prodlot_id (total 13 tables)
        self._logger.info("__ Migrating batch number:     %s\n", batch_name)
        list_table_fields = [
            ('create_picking_move_processor', 'prodlot_id'),
            ('export_report_stock_inventory', 'prodlot_id'),
            ('export_report_stock_move', 'prodlot_id'),
            ('internal_move_processor', 'prodlot_id'),
            ('outgoing_delivery_move_processor', 'prodlot_id'),
            ('real_average_consumption_line', 'prodlot_id'),
            ('return_ppl_move_processor', 'prodlot_id'),
            ('stock_move_in_processor', 'prodlot_id'),
            ('stock_move_processor', 'prodlot_id'),
            ('stock_move', 'prodlot_id'),
            ('unconsistent_stock_report_line', 'prodlot_id'),
            ('validate_move_processor', 'prodlot_id'),
            ('stock_production_lot_revision', 'lot_id'),
            ('product_likely_expire_report_item_line', 'lot_id'),
            ('stock_inventory_line', 'prod_lot_id'),
            ('initial_stock_inventory_line', 'prod_lot_id'),
            ('claim_product_line', 'lot_id_claim_product_line'),
            ('composition_kit', 'composition_lot_id')
        ]
        for element in list_table_fields:
            # Tables with foreign key prod_lot_id (total 2)
            self.update_table(cr, uid, element[0] , element[1], wrong_id, lead_id, batch_name)

    def update_table(self, cr, uid, table_name, field_id, wrong_id, lead_id, batch_name):
        cr.execute('select count(*) as amount from ' + table_name + ' where ' + field_id + ' =%s', (wrong_id,))  # not_a_user_entry
        count = cr.fetchone()[0]
        if count > 0: # Only update the table if wrong bn exists
            self._logger.info("Table %s has %s batch objects (%s) and will be-mapped.\n" %(table_name, count, batch_name,))
            if table_name == 'real_average_consumption_line':
                # Specific case for real.average.consumption.line that need to sum the quantity of old and new prodlot because of unicity constraint
                sql_update = """
                    UPDATE real_average_consumption_line
                    SET product_qty = (
                        SELECT sum(product_qty) FROM real_average_consumption_line WHERE prodlot_id IN (%s, %s))
                    WHERE prodlot_id = %s
                """
                cr.execute(sql_update, (lead_id, wrong_id, lead_id))
                del_sql_update = "DELETE FROM real_average_consumption_line WHERE prodlot_id = %s"
                cr.execute(del_sql_update, (wrong_id,))
            else:
                sql_update = "update " + table_name + " set " + field_id + "=%s" + " where " + field_id + "=%s"  # not_a_user_entry
                cr.execute(sql_update, (lead_id, wrong_id))
        else:
            self._logger.info("Table %s has NO duplicate batch (%s).\n" %(table_name, batch_name,))

    _defaults = {
        'life_date': _get_date('life_time'),
        'use_date': _get_date('use_time'),
        'removal_date': _get_date('removal_time'),
        'alert_date': _get_date('alert_time'),
    }
stock_production_lot()

class product_product(osv.osv):
    _inherit = 'product.product'
    _columns = {
        'life_time': fields.integer('Product Life Time',
                                    help='The number of days before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.integer('Product Use Time',
                                   help='The number of days before a production lot starts deteriorating without becoming dangerous.'),
        'removal_time': fields.integer('Product Removal Time',
                                       help='The number of days before a production lot should be removed.'),
        'alert_time': fields.integer('Product Alert Time', help="The number of days after which an alert should be notified about the production lot."),
    }
product_product()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
