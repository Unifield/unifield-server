# -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
import tools
import time
import base64
import threading
import pooler
from msf_doc_import import GENERIC_MESSAGE
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from msf_doc_import.wizard import COLUMNS_HEADER_FOR_PRODUCT_LINE_IMPORT as columns_header_for_product_line_import
from msf_doc_import.wizard import COLUMNS_FOR_PRODUCT_LINE_IMPORT as columns_for_product_line_import


class product_mass_update(osv.osv):
    _name = 'product.mass.update'
    _description = 'Product Mass Update'

    _order = 'id desc'

    def _get_percent_completed(self, cr, uid, ids, field_names, arg, context=None):
        if context is None:
            context = {}

        upd_progress_obj = self.pool.get('product.mass.update.progressbar')

        res = {}
        for p_mass_upd in self.browse(cr, uid, ids, fields_to_fetch=['state'], context=context):
            if p_mass_upd.state == 'done':
                res[p_mass_upd.id] = 100
            else:
                upd_progress_ids = upd_progress_obj.search(cr, uid, [('p_mass_upd_id', '=', p_mass_upd.id)], context=context)
                if upd_progress_ids:
                    res[p_mass_upd.id] = round(upd_progress_obj.browse(cr, uid, upd_progress_ids[0], context=context).percent_completed, 0) or 0

        return res

    _columns = {
        'name': fields.char(size=64, string='Update Reference'),
        'state': fields.selection(selection=[('draft', 'Draft'), ('in_progress', 'In Progress'), ('error', 'Error'), ('done', 'Done'), ('cancel', 'Cancelled')], string='Status', readonly=True),
        'date_done': fields.datetime(string='Date of the update', readonly=True),
        'user_id': fields.many2one('res.users', string='User who Updated', readonly=True),
        'import_in_progress': fields.boolean(string='Import in progress'),
        'percent_completed': fields.function(_get_percent_completed, method=True, string='% completed', type='integer', readonly=True),
        'message': fields.text(string='Message', readonly=True),
        'product_ids': fields.many2many('product.product', 'prod_mass_update_product_rel', 'product_id',
                                        'prod_mass_update_id', string="Product selection", order_by="default_code",
                                        domain=[('active', 'in', ['t', 'f'])]),
        'not_deactivated_product_ids': fields.one2many('product.mass.update.errors', 'p_mass_upd_id',
                                                       string="Product(s) that can not be deactivated"),
        'has_not_deactivable': fields.boolean(string='Document has non-deactivable product(s)', readonly=True),
        'not_activated_product_ids': fields.one2many('product.mass.update.errors', 'p_mass_upd_id',
                                                     string="Product(s) that can not be deactivated"),
        'has_not_activable': fields.boolean(string='Document has non-activable product(s)', readonly=True),
        # Fields
        'active_product': fields.selection(selection=[('no', 'No'), ('yes', 'Yes')], string='Active', help="If the active field is set to False, it allows to hide the nomenclature without removing it."),
        'dangerous_goods': fields.selection(selection=[('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Dangerous Goods'),
        'heat_sensitive_item': fields.selection(selection=[('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Temperature sensitive item'),
        'single_use': fields.selection(selection=[('no', 'No'), ('yes', 'Yes'), ('no_know', 'tbd')], string='Single Use'),
        'short_shelf_life': fields.selection(selection=[('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Short Shelf Life'),
        'alert_time': fields.char(string='Product Alert Time', size=32, help="The number of months after which an alert should be notified about the production lot."),
        'life_time': fields.char('Product Life Time', size=32, help='The number of months before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.char('Product Use Time', size=32, help='The number of months before a production lot starts deteriorating without becoming dangerous.'),
        'procure_delay': fields.char(string='Procurement Lead Time', size=32,
                                     help='It\'s the default time to procure this product. This lead time will be used on the Order cycle procurement computation'),
        'procure_method': fields.selection([('make_to_stock', 'Make to Stock'), ('make_to_order', 'Make to Order')], 'Procurement Method',
                                           help="If you encode manually a Procurement, you probably want to use a make to order method."),
        'product_state': fields.selection([('valid', 'Valid'), ('phase_out', 'Phase Out'), ('forbidden', 'Forbidden'), ('archived', 'Archived')], 'Status', help="Tells the user if he can use the product or not."),
        'sterilized': fields.selection(selection=[('no', 'No'), ('yes', 'Yes'), ('no_know', 'tbd')], string='Sterile'),
        'supply_method': fields.selection([('produce', 'Produce'), ('buy', 'Buy')], 'Supply Method',
                                          help="Produce will generate production order or tasks, according to the product type. Purchase will trigger purchase orders when requested."),
        'seller_id': fields.many2one('res.partner', 'Default Partner'),
        'property_account_income': fields.many2one('account.account', string='Income Account',
                                                   help='This account will be used for invoices instead of the default one to value sales for the current product'),
        'property_account_expense': fields.many2one('account.account', string='Expense Account',
                                                    help='This account will be used for invoices instead of the default one to value expenses for the current product'),
        'empty_status': fields.boolean(string='Set Status as empty (obsolete)', readonly=True),
        'empty_inc_account': fields.boolean(string='Set Income Account as empty'),
        'empty_exp_account': fields.boolean(string='Set Expense Account as empty'),
        'type_of_ed_bn': fields.selection([('no_bn_no_ed', 'No BN/No ED'), ('bn', 'BN+ED'), ('ed', 'ED Only')], string='Target Attributes'),
        'product_history_ids': fields.one2many('product.ed_bn.mass.update.history', 'p_mass_upd_id', 'History'),
    }

    _defaults = {
        'state': 'draft',
        'import_in_progress': False,
        'message': '',
        'active_product': '',
        'dangerous_goods': '',
        'heat_sensitive_item': '',
        'single_use': '',
        'short_shelf_life': '',
        'procure_method': '',
        'sterilized': '',
        'supply_method': '',
        'type_of_ed_bn': False,
    }

    def create(self, cr, uid, vals, context=None):
        '''
        override create method
        '''
        if context is None:
            context = {}

        # Prevent creation of BN/ED mass update when trying to update with 0 products while editing newly created doc
        if context.get('button', False) == 'change_bn_ed' and vals.get('type_of_ed_bn') and \
                vals.get('product_ids', False) == [(6, 0, [])]:
            raise osv.except_osv(_('Warning'), _('Please add at least 1 product before proceeding.'))

        return super(product_mass_update, self).create(cr, uid, vals, context)

    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method
        '''
        if context is None:
            context = {}

        if context.get('button') == 'dummy' and '__last_update' in context:
            del context['__last_update']

        if not ids:
            return True

        if 'empty_inc_account' in vals and vals['empty_inc_account']:
            vals['property_account_income'] = False
        if 'empty_exp_account' in vals and vals['empty_exp_account']:
            vals['property_account_expense'] = False

        return super(product_mass_update, self).write(cr, user, ids, vals, context)

    def copy(self, cr, uid, id, default=None, context=None):
        if context is None:
            context = {}

        if default is None:
            default = {}

        default.update({
            'user_id': False,
            'date_done': False,
            'message': '',
            'not_deactivated_product_ids': [(6, 0, [])],
            'has_not_deactivable': False,
            'not_activated_product_ids': [(6, 0, [])],
            'has_not_activable': False,
            'empty_status': False,
            'empty_inc_account': False,
            'empty_exp_account': False,
            'product_history_ids': [],
        })

        return super(product_mass_update, self).copy(cr, uid, id, default=default, context=context)

    def onchange_inc_check(self, cr, uid, ids, empty_inc_account):
        if empty_inc_account:
            return {'value': {'property_account_income': False}}
        return {'value': {}}

    def onchange_exp_check(self, cr, uid, ids, empty_exp_account):
        if empty_exp_account:
            return {'value': {'property_account_expense': False}}
        return {'value': {}}

    def delete_products(self, cr, uid, ids, context=None):
        '''
        Delete the selected products
        '''
        if context is None:
            context = {}
        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning'),  _('Please select at least one line'))

        self.write(cr, uid, ids, {'product_ids': [(3, x) for x in context['button_selected_ids']]}, context=context)

        return True

    def cancel_update(self, cr, uid, ids, context=None):
        '''
        Cancel the current Product Mass Update
        '''
        if context is None:
            context = {}

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

        return True

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, int):
            ids = [ids]

        return True

    def reset_update(self, cr, uid, ids, context=None):
        """
        This button is only for resetting the update
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        # Unlink existing errors
        upd_errors_obj = self.pool.get('product.mass.update.errors')
        errors_ids = upd_errors_obj.search(cr, uid, [('p_mass_upd_id', 'in', ids)], context=context)
        upd_errors_obj.unlink(cr, uid, errors_ids, context=context)

        vals = {
            'state': 'draft',
            'message': '',
            'has_not_deactivable': False,
            'has_not_activable': False,
        }
        self.write(cr, uid, ids, vals, context=context)

        return True

    def launch_update(self, cr, uid, ids, context=None):
        '''
        Launch a thread for update
        '''
        if not ids:
            return True

        data_obj = self.pool.get('ir.model.data')
        p_state_obj = self.pool.get('product.status')

        p_mass_upd = self.browse(cr, uid, ids[0], context=context)
        if not p_mass_upd.product_ids:
            raise osv.except_osv(_('Error'), _('You can not apply an update on no products.'))

        vals = {}
        if p_mass_upd.dangerous_goods:
            vals.update({'dangerous_goods': p_mass_upd.dangerous_goods})
        if p_mass_upd.heat_sensitive_item:
            heat_attr = p_mass_upd.heat_sensitive_item == 'True' and 'heat_yes' or p_mass_upd.heat_sensitive_item == 'False' and 'heat_no' \
                or p_mass_upd.heat_sensitive_item == 'tbd' and 'heat_no_know' or False
            heat_id = data_obj.get_object_reference(cr, uid, 'product_attributes', heat_attr)[1]
            if heat_id:
                vals.update({'heat_sensitive_item': heat_id})
        if p_mass_upd.short_shelf_life:
            vals.update({'short_shelf_life': p_mass_upd.short_shelf_life})
        if p_mass_upd.alert_time:
            try:
                alert_time = int(p_mass_upd.alert_time)
                vals.update({'alert_time': alert_time})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Alert Time must be an integer.'))
        if p_mass_upd.life_time:
            try:
                life_time = int(p_mass_upd.life_time)
                vals.update({'life_time': life_time})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Life Time must be an integer.'))
        if p_mass_upd.use_time:
            try:
                use_time = int(p_mass_upd.use_time)
                vals.update({'use_time': use_time})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Use Time must be an integer.'))
        if p_mass_upd.procure_delay:
            try:
                procure_delay = float(p_mass_upd.procure_delay)
                vals.update({'procure_delay': procure_delay})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Procurement Lead Time must be a float.'))
        if p_mass_upd.procure_method:
            vals.update({'procure_method': p_mass_upd.procure_method})
        if p_mass_upd.single_use:
            vals.update({'single_use': p_mass_upd.single_use})
        if p_mass_upd.product_state:
            p_state_ids = p_state_obj.search(cr, uid, [('code', '=', p_mass_upd.product_state)], context=context)
            if p_state_ids:
                vals.update({'state': p_state_ids[0]})
        if p_mass_upd.sterilized:
            vals.update({'sterilized': p_mass_upd.sterilized})
        if p_mass_upd.supply_method:
            vals.update({'supply_method': p_mass_upd.supply_method})
        if p_mass_upd.property_account_income:
            vals.update({'property_account_income': p_mass_upd.property_account_income.id})
        elif p_mass_upd.empty_inc_account:
            vals.update({'property_account_income': False})
        if p_mass_upd.property_account_expense:
            vals.update({'property_account_expense': p_mass_upd.property_account_expense.id})
        elif p_mass_upd.empty_exp_account:
            vals.update({'property_account_expense': False})

        thread = threading.Thread(target=self.apply_update, args=(cr, uid, ids, vals, context))
        thread.start()

        msg_to_return = _("Update in progress, please leave this window open and press the button 'Update' when you think that the update is done. Otherwise, you can continue to use Unifield.")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def apply_update(self, cr, uid, ids, vals, context=None):
        '''
        Apply the current Product Mass Update
        '''
        if context is None:
            context = {}

        # New cursor
        cr = pooler.get_db(cr.dbname).cursor()

        prod_obj = self.pool.get('product.product')
        p_suppinfo_obj = self.pool.get('product.supplierinfo')
        upd_progress_obj = self.pool.get('product.mass.update.progressbar')
        upd_errors_obj = self.pool.get('product.mass.update.errors')

        p_mass_upd = self.browse(cr, uid, ids[0], context=context)
        instance_level = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.level
        try:
            # For the progress bar
            upd_progress_ids = upd_progress_obj.search(cr, uid, [('p_mass_upd_id', '=', p_mass_upd.id)], context=context)
            if upd_progress_ids:
                upd_progress_id = upd_progress_ids[0]
            else:
                upd_progress_id = upd_progress_obj.create(cr, uid, {'p_mass_upd_id': p_mass_upd.id}, context=context)

            num_prod = 0
            not_activated = []
            not_deactivated = []
            for prod in p_mass_upd.product_ids:
                # Check procurement method
                if p_mass_upd.procure_method and prod.type in ('consu', 'service', 'service_recep') and \
                        p_mass_upd.procure_method != 'make_to_order':
                    raise osv.except_osv(_('Error'), _('You must select on order procurement method for %s products.')
                                         % (prod.type == 'consu' and 'Non-stockable' or 'Service'))
                # Deactivation
                if p_mass_upd.seller_id and not p_suppinfo_obj.search(cr, uid, [('product_id', '=', prod.product_tmpl_id.id), ('name', '=', p_mass_upd.seller_id.id)], context=context):
                    p_suppinfo_obj.create(cr, uid, {'product_id': prod.product_tmpl_id.id, 'name': p_mass_upd.seller_id.id, 'sequence': 0}, context=context)
                if p_mass_upd.active_product:
                    if not prod.active and p_mass_upd.active_product == 'yes':
                        if instance_level in ['project', 'coordo'] and prod.standard_ok == 'non_standard_local':
                            not_activated.append(prod.id)
                        else:
                            prod_obj.reactivate_product(cr, uid, [prod.id], context=context)
                    elif prod.active and p_mass_upd.active_product == 'no':
                        deactivated = prod_obj.deactivate_product(cr, uid, [prod.id], context=context)
                        if deactivated != True:  # If doesn't return True, the product has not been deactivated
                            not_deactivated.append(deactivated.get('res_id'))
                num_prod += 1
                percent_completed = float(num_prod) / float(len(p_mass_upd.product_ids)) * 100.0
                upd_progress_obj.write(cr, uid, upd_progress_id, {'percent_completed': percent_completed}, context=context)

            p_mass_upd_vals = {}
            msg = ''
            if not_deactivated or not_activated:
                cr.rollback()  # Rollback deactivation and product seller creation
                if not_deactivated:
                    for wiz_prod_error in self.pool.get('product.deactivation.error').browse(cr, uid, not_deactivated):
                        err_vals = {
                            'p_mass_upd_id': p_mass_upd.id,
                            'product_id': wiz_prod_error.product_id.id,
                            'stock_exist': wiz_prod_error.stock_exist,
                            'open_documents': wiz_prod_error.error_lines and ', '.join([x.doc_ref for x in wiz_prod_error.error_lines if x.doc_ref]) or '',
                            'not_deactivable': True,
                        }
                        upd_errors_obj.create(cr, uid, err_vals, context=context)

                    msg += _('Some products could not be deactivated. No product will be changed until all of them can be deactivated.\n')
                    p_mass_upd_vals.update({'has_not_deactivable': True})
                if not_activated:
                    for prod_id in not_activated:
                        err_vals = {
                            'p_mass_upd_id': p_mass_upd.id,
                            'product_id': prod_id,
                            'not_activable': True,
                        }
                        upd_errors_obj.create(cr, uid, err_vals, context=context)

                    msg += _('Some NSL (Non-standard Local) products could not be activated to ensure that there is no duplicate “Local” product. No product will be changed and those NSL products should be activated manually.\n')
                    p_mass_upd_vals.update({'has_not_activable': True})

                msg += _('Please check the corresponding tab.')
                p_mass_upd_vals.update({
                    'message': msg,
                    'state': 'error',
                })
                self.write(cr, uid, p_mass_upd.id, p_mass_upd_vals, context=context)

            if not not_deactivated and not not_activated:
                prod_obj.write(cr, uid, [prod.id for prod in p_mass_upd.product_ids], vals, context=context)
                real_user = hasattr(uid, 'realUid') and uid.realUid or uid

                # Unlink existing errors
                errors_ids = upd_errors_obj.search(cr, uid, [('p_mass_upd_id', '=', p_mass_upd.id)], context=context)
                upd_errors_obj.unlink(cr, uid, errors_ids, context=context)

                p_mass_upd_vals = {
                    'has_not_deactivable': False,
                    'has_not_activable': False,
                    'date_done': time.strftime('%Y-%m-%d %H:%M'),
                    'user_id': real_user,
                    'state': 'done',
                    'message': '',
                }
                self.write(cr, uid, p_mass_upd.id, p_mass_upd_vals, context=context)
        except Exception as e:
            cr.rollback()
            error = e
            if hasattr(e, 'value'):
                error = e.value
            err = _('An error has occured during the update:\n%s') % tools.ustr(error)
            self.write(cr, uid, p_mass_upd.id, {'state': 'error', 'message': err}, context=context)
        finally:
            cr.commit()
            cr.close(True)

        return True

    def change_bn_ed(self, cr, uid, ids, context=None):
        prod_obj = self.pool.get('product.product')

        wiz = self.browse(cr, uid, ids[0], context=context)
        prod_ids = prod_obj.search(cr, uid, [('id', 'in', [x.id for x in wiz.product_ids]), ('expected_prod_creator', '=', 'bned'), ('active', 'in', ['t', 'f'])], context=context)
        if not prod_ids:
            raise osv.except_osv(_('Warning'), _('Please add at least 1 product before proceeding.'))
        if len(prod_ids) > 500:
            raise osv.except_osv(_('Warning'), _('Please limit your query to a maximum of 500 products.'))

        self.pool.get('product.mass.update.progressbar').create(cr, uid,  {'p_mass_upd_id': ids[0]}, context=context)
        thread = threading.Thread(target=self.change_bn_ed_thread, args=(cr, uid, ids[0], prod_ids, context))
        thread.start()

        thread.join(5)
        if thread.is_alive():
            msg_to_return = _("Update in progress, please leave this window open and press the button 'Update' when you think that the update is done. Otherwise, you can continue to use Unifield.")
            self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)
        return True

    def change_bn_ed_thread(self, new_cr, uid, _id, product_ids, context):
        real_user = hasattr(uid, 'realUid') and uid.realUid or uid
        prod_obj = self.pool.get('product.product')
        history_obj = self.pool.get('product.ed_bn.mass.update.history')
        progress_obj = self.pool.get('product.mass.update.progressbar')
        cr = pooler.get_db(new_cr.dbname).cursor()
        try:
            wiz = self.browse(cr, uid, _id, context=context)
            progress_ids = progress_obj.search(cr, uid, [('p_mass_upd_id', '=', _id)], context=context)
            split = 0
            steps = 50
            while split < len(product_ids):
                prod_ids = product_ids[split:split+steps]
                split += steps

                for x in prod_obj.search(cr, uid, [('id', 'in', prod_ids), ('perishable', '=', False), ('batch_management', '=', False)], context=context):
                    history_obj.create(cr, uid, {'product_id': x, 'p_mass_upd_id': _id, 'old_bn': False, 'old_ed': False}, context=context)

                for x in prod_obj.search(cr, uid, [('id', 'in', prod_ids), ('perishable', '=', True), ('batch_management', '=', False)], context=context):
                    history_obj.create(cr, uid, {'product_id': x, 'p_mass_upd_id': _id, 'old_bn': False, 'old_ed': True}, context=context)

                for x in prod_obj.search(cr, uid, [('id', 'in', prod_ids), ('perishable', '=', True), ('batch_management', '=', True)], context=context):
                    history_obj.create(cr, uid, {'product_id': x, 'p_mass_upd_id': _id, 'old_bn': True, 'old_ed': True}, context=context)

                if wiz.type_of_ed_bn == 'no_bn_no_ed':
                    prod_obj.set_as_nobn_noed(cr, uid, prod_ids, context=context)
                elif wiz.type_of_ed_bn == 'bn':
                    prod_obj.set_as_bned(cr, uid, prod_ids, context=context)
                elif wiz.type_of_ed_bn == 'ed':
                    prod_obj.set_as_edonly(cr, uid, prod_ids, context=context)
                progress_obj.write(cr, uid, progress_ids, {'percent_completed': (split-steps)/ float(len(product_ids)) * 100.0}, context=context)

            self.write(cr, uid, _id, {'state': 'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S'), 'user_id': real_user}, context=context)

        except Exception as e:
            cr.rollback()
            error = e
            if hasattr(e, 'value'):
                error = e.value
            err = _('An error has occured during the update:\n%s') % tools.ustr(error)
            self.write(cr, uid, _id, {'state': 'error', 'message': err}, context=context)
        finally:
            cr.commit()
            cr.close(True)
        return True


    def wizard_import_products(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_product_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.product.line').create(cr, uid, {
            'file': file,
            'filename_template': 'template.xls',
            'filename': 'Lines_Not_Imported.xls',
            'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in columns_for_product_line_import]), ),
            'product_mass_upd_id': ids[0],
            'state': 'draft',
        }, context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.product.line',
            'res_id': export_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'crush',
            'context': context,
        }

    def export_product_errors(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'product_mass_update_export_xls',
            'datas': {'ids': ids, 'target_filename': _('Product Mass Update Errors')},
            'nodestroy': True,
            'context': context,
        }


product_mass_update()


class product_mass_update_progressbar(osv.osv_memory):
    _name = 'product.mass.update.progressbar'
    _description = 'Product Mass Update Progress Bar'

    _columns = {
        'p_mass_upd_id': fields.many2one('product.mass.update', 'Product Mass Update'),
        'percent_completed': fields.integer(string='% completed', readonly=True),
    }

    _default = {
        'p_mass_upd_id': False,
        'percent_completed': 0,
    }


product_mass_update_progressbar()


class product_mass_update_errors(osv.osv):
    _name = 'product.mass.update.errors'
    _description = 'Product Mass Update Errors'

    _order = 'product_id'

    _columns = {
        'p_mass_upd_id': fields.many2one('product.mass.update', 'Product Mass Update', ondelete='cascade'),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'stock_exist': fields.boolean(string='Stock Exist'),
        'open_documents': fields.char(string='Open Documents', size=256),
    }

    _default = {
        'stock_exist': False,
        'open_documents': '',
    }


product_mass_update_errors()


class product_ed_bn_mass_update_history(osv.osv):
    _name = 'product.ed_bn.mass.update.history'
    _description = 'List of change'

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'p_mass_upd_id': fields.many2one('product.mass.update', 'Product Mass Update', ondelete='cascade'),
        'old_bn': fields.boolean('Old BN'),
        'old_ed': fields.boolean('Old ED'),
    }


product_ed_bn_mass_update_history()
