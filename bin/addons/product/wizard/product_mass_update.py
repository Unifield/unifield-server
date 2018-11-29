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

from osv import osv, fields
from tools.translate import _
import time
import base64
import threading
import pooler
from msf_doc_import import GENERIC_MESSAGE
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
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
        'state': fields.selection(selection=[('draft', 'Draft'), ('in_progress', 'In Progress'), ('error', 'Error'), ('done', 'Done')], string='Status', readonly=True),
        'date_done': fields.datetime(string='Date of the update'),
        'log': fields.char(string='Information', size=128, readonly=True),
        'import_in_progress': fields.boolean(string='Import in progress'),
        'percent_completed': fields.function(_get_percent_completed, method=True, string='% completed', type='integer', readonly=True),
        'message': fields.text(string='Message', readonly=True),
        'product_ids': fields.many2many('product.product', 'prod_mass_update_product_rel', 'product_id',
                                        'prod_mass_update_id', string="Product selection", order_by="default_code",
                                        domain=[('expected_prod_creator', '=', 'True'), '|', ('active', '=', True), ('active', '=', False)]),
        'not_deactivated_product_ids': fields.many2many('product.product', 'not_deactivated_prod_mass_update_product_rel', 'product_id',
                                                        'not_deactivated_prod_mass_update_id', string="Product(s) that can not be deactivated",
                                                        order_by="default_code"),
        'has_not_deactivable': fields.boolean(string='Document has non-deactivable product(s)', readonly=True),
        # Fields
        'active_product': fields.selection(selection=[('', ''), ('no', 'No'), ('yes', 'Yes')], string='Active', help="If the active field is set to False, it allows to hide the nomenclature without removing it."),
        'dangerous_goods': fields.selection(selection=[('', ''), ('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Dangerous goods'),
        'heat_sensitive_item': fields.selection(selection=[('', ''), ('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Temperature sensitive item'),
        'single_use': fields.selection(selection=[('', ''), ('yes', 'Yes'), ('no', 'No'), ('no_know', 'tbd')], string='Single Use'),
        'short_shelf_life': fields.selection(selection=[('', ''), ('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Short Shelf Life'),
        'alert_time': fields.char(string='Product Alert Time', size=32, help="The number of days after which an alert should be notified about the production lot."),
        'life_time': fields.char('Product Life Time', size=32, help='The number of months before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.char('Product Use Time', size=32, help='The number of months before a production lot starts deteriorating without becoming dangerous.'),
        'procure_delay': fields.char(string='Procurement Lead Time', size=32,
                                     help='It\'s the default time to procure this product. This lead time will be used on the Order cycle procurement computation'),
        'procure_method': fields.selection([('', ''), ('make_to_stock', 'from stock'), ('make_to_order', 'on order')], 'Procurement Method',
                                           help="If you encode manually a Procurement, you probably want to use a make to order method."),
        'product_state': fields.selection([('', ''), ('valid', 'Valid'), ('phase_out', 'Phase Out'), ('stopped', 'Stopped'), ('archived', 'Archived'), ('status1', 'Status 1'), ('status2', 'Status 2'), ], 'Status', help="Tells the user if he can use the product or not."),
        'sterilized': fields.selection(selection=[('', ''), ('yes', 'Yes'), ('no', 'No'), ('no_know', 'tbd')], string='Sterile'),
        'supply_method': fields.selection([('', ''), ('produce', 'Produce'), ('buy', 'Buy')], 'Supply method',
                                          help="Produce will generate production order or tasks, according to the product type. Purchase will trigger purchase orders when requested."),
        'seller_id': fields.many2one('res.partner', 'Default Partner'),
        'property_account_income': fields.many2one('account.account', string='Income Account',
                                                   help='This account will be used for invoices instead of the default one to value sales for the current product'),
        'property_account_expense': fields.many2one('account.account', string='Expense Account',
                                                    help='This account will be used for invoices instead of the default one to value expenses for the current product'),
    }

    _defaults = {
        'state': 'draft',
        'import_in_progress': False,
        'active_product': '',
        'dangerous_goods': '',
        'heat_sensitive_item': '',
        'single_use': '',
        'short_shelf_life': '',
        'procure_method': '',
        'sterilized': '',
        'supply_method': '',
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if context is None:
            context = {}

        if default is None:
            default = {}

        default.update({
            'log': '',
            'date_done': False,
            'not_deactivated_product_ids': [(6, 0, [])],
            'has_not_deactivable': False,
        })

        return super(product_mass_update, self).copy(cr, uid, id, default=default, context=context)

    def cancel_update(self, cr, uid, ids, context=None):
        '''
        Delete the current Product Mass Update
        '''
        if context is None:
            context = {}

        self.unlink(cr, uid, ids, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.mass.update',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'target': 'crush',
        }

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        return True

    def reset_update(self, cr, uid, ids, context=None):
        """
        This button is only for resetting the update
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        vals = {
            'state': 'draft',
            'message': '',
            'not_deactivated_product_ids': [(6, 0, [])],
            'has_not_deactivable': False,
        }
        self.write(cr, uid, ids, vals, context=context)

        return True

    def launch_update(self, cr, uid, ids, context=None):
        '''
        Launch a thread for update
        '''
        if not ids:
            return True

        heat_obj = self.pool.get('product.heat_sensitive')
        p_state_obj = self.pool.get('product.status')

        p_mass_upd = self.browse(cr, uid, ids[0], context=context)
        if not p_mass_upd.product_ids:
            raise osv.except_osv(_('Error'), _('You can not apply an update on no products.'))

        vals = {}
        if p_mass_upd.dangerous_goods:
            vals.update({'dangerous_goods': p_mass_upd.dangerous_goods})
        if p_mass_upd.heat_sensitive_item:
            heat_ids = heat_obj.search(cr, uid, [('code', '=', p_mass_upd.heat_sensitive_item)], context=context)
            if heat_ids:
                vals.update({'heat_sensitive_item': heat_ids[0]})
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
        if p_mass_upd.property_account_expense:
            vals.update({'property_account_expense': p_mass_upd.property_account_expense.id})

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

        p_mass_upd = self.browse(cr, uid, ids[0], context=context)
        try:
            # For the progress bar
            upd_progress_ids = upd_progress_obj.search(cr, uid, [('p_mass_upd_id', '=', p_mass_upd.id)], context=context)
            if upd_progress_ids:
                upd_progress_id = upd_progress_ids[0]
            else:
                upd_progress_id = upd_progress_obj.create(cr, uid, {'p_mass_upd_id': p_mass_upd.id}, context=context)

            num_prod = 0
            not_deactivated = []
            for prod in p_mass_upd.product_ids:
                if p_mass_upd.seller_id and not p_suppinfo_obj.search(cr, uid, [('product_id', '=', prod.id), ('name', '=', p_mass_upd.seller_id.id)], context=context):
                    p_suppinfo_obj.create(cr, uid, {'product_id': prod.id, 'name': p_mass_upd.seller_id.id, 'sequence': 1}, context=context)
                if p_mass_upd.active_product:
                    if not prod.active and p_mass_upd.active_product == 'yes':
                        prod_obj.reactivate_product(cr, uid, [prod.id], context=context)
                    elif prod.active and p_mass_upd.active_product == 'no':
                        deactivated = prod_obj.deactivate_product(cr, uid, [prod.id], context=context)
                        if deactivated != True:  # If doesn't return True, the product has not been deactivated
                            not_deactivated.append(prod.id)
                num_prod += 1
                percent_completed = float(num_prod) / float(len(p_mass_upd.product_ids)) * 100.0
                upd_progress_obj.write(cr, uid, upd_progress_id, {'percent_completed': percent_completed}, context=context)

            if not_deactivated:
                cr.rollback()  # Rollback deactivation and product seller creation
                p_mass_upd_vals = {
                    'not_deactivated_product_ids': [(6, 0, not_deactivated)],
                    'has_not_deactivable': True,
                    'state': 'draft',
                }
                self.write(cr, uid, ids[0], p_mass_upd_vals, context=context)
            else:
                prod_obj.write(cr, uid, [prod.id for prod in p_mass_upd.product_ids], vals, context=context)
                user = self.pool.get('res.users').browse(cr, uid, uid, context=context).name
                log = _('Modification of %s product(s) the %s done by %s') % \
                      (len(p_mass_upd.product_ids), time.strftime('%d/%m/%Y'), user)
                p_mass_upd_vals = {
                    'not_deactivated_product_ids': [(6, 0, [])],
                    'has_not_deactivable': False,
                    'date_done': time.strftime('%Y-%m-%d %H:%M'),
                    'log': log,
                    'state': 'done',
                }
                self.write(cr, uid, ids[0], p_mass_upd_vals, context=context)
        except Exception as e:
            self.write(cr, uid, p_mass_upd.id, {'state': 'error', 'message': e}, context=context)
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
        if isinstance(ids, (int, long)):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_for_product_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
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
