# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
import base64
from os.path import join as opj
from tools.translate import _
import tools
import os
import logging
from threading import Lock
import time
import xmlrpclib
import netsvc
import traceback
#import re

from msf_field_access_rights.osv_override import _get_instance_level
import cStringIO
import csv

class patch_scripts(osv.osv):
    _name = 'patch.scripts'
    _logger = logging.getLogger('patch_scripts')

    _columns = {
        'model': fields.text(string='Model', required=True),
        'method': fields.text(string='Method', required=True),
        'run': fields.boolean(string='Is ran ?'),
    }

    _defaults = {
        'model': lambda *a: 'patch.scripts',
    }

    def launch_patch_scripts(self, cr, uid, *a, **b):
        ps_obj = self.pool.get('patch.scripts')
        ps_ids = ps_obj.search(cr, uid, [('run', '=', False)])
        for ps in ps_obj.read(cr, uid, ps_ids, ['model', 'method']):
            method = ps['method']
            model_obj = self.pool.get(ps['model'])
            try:
                getattr(model_obj, method)(cr, uid, *a, **b)
                self.write(cr, uid, [ps['id']], {'run': True})
            except Exception as e:
                err_msg = 'Error with the patch scripts %s.%s :: %s' % (ps['model'], ps['method'], e)
                self._logger.error(err_msg)
                raise osv.except_osv(
                    'Error',
                    err_msg,
                )

    # UF13.1
    def us_6128_delete_auto_group(self, cr, uid, *a, **b):
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance_id:
            return True
        if instance_id.level == 'section':
            login_to_del = ['sup_consumption_management', 'sup_consumption_only', 'sup_demand_manager', 'sup_fin_read', 'sup_med_read', 'sup_product_manager', 'sup_product_mgr_coordo', 'sup_purchase_cr', 'sup_purchase_manager', 'sup_purchase_officer', 'sup_purchase_sup', 'sup_read_all', 'sup_request_sourcing', 'sup_request_validator', 'sup_requester', 'sup_store_keeper', 'sup_supply_config', 'sup_supply_system_administrator', 'sup_transport_manager', 'sup_valid_line_fo', 'sup_valid_line_ir', 'sup_valid_line_po', 'sup_warehouse_cr', 'sup_warehouse_manager', 'sync_config', 'sync_manual', 'user_manager', 'fin_accounting_entries_act', 'fin_accounting_entries_consult', 'fin_accounting_reports', 'fin_advanced_accounting', 'fin_bnk_chk_registers', 'fin_bnk_chk_responsible_access', 'fin_budget', 'fin_cash_registers', 'fin_cash_responsible_access', 'fin_config_admin_mission', 'fin_config_coordo', 'fin_config_full', 'fin_config_hq', 'fin_config_project', 'fin_consult_sup', 'fin_grant_mgt', 'fin_hard_posting', 'fin_hq_entries', 'fin_hr', 'fin_invoicing_advanced', 'fin_local_payroll', 'fin_register_project_responsible', 'fin_supplier_invoices', 'fin_supplier_invoices_validation', 'auditor_read']

            cr.execute('delete from res_users where login in %s', (tuple(login_to_del),))
            self._logger.warn('%d users deleted' % (cr.rowcount, ))

        return True

    # UF13.0
    def us_5771_allow_all_cc_in_default_dest(self, cr, uid, *a, **b):
        """
        Set the default created destinations (OPS/EXP/SUP/NAT) as "Allow all Cost Centers"
        """
        update_dests = """
            UPDATE account_analytic_account
            SET allow_all_cc = 't'
            WHERE category = 'DEST' 
            AND id IN (SELECT res_id FROM ir_model_data WHERE module='analytic_distribution' AND name IN (
                'analytic_account_destination_operation',
                'analytic_account_destination_expatriates',
                'analytic_account_destination_support',
                'analytic_account_destination_national_staff'));
        """
        cr.execute(update_dests)
        return True

    # UF12.1
    def us_5199_fix_cancel_partial_move_sol_id(self, cr, uid, *a, **b):
        '''
        Set the correct sale_line_id on moves post SLL that were cancelled after the original line was partially processed
        '''
        move_obj = self.pool.get('stock.move')
        sol_obj = self.pool.get('sale.order.line')

        move_domain = [
            ('state', '=', 'cancel'),
            ('type', '=', 'out'),
            ('picking_id.subtype', '=', 'standard'),
            ('picking_id.type', '=', 'out'),
            ('sale_line_id.order_id.procurement_request', '=', True),
            ('sale_line_id.state', '=', 'done'),
        ]
        moves_ids = move_obj.search(cr, uid, move_domain)
        impacted_ir = []
        for move in self.pool.get('stock.move').browse(cr, uid, moves_ids):
            split_sol_ids = sol_obj.search(cr, uid, [
                ('order_id', '=', move.sale_line_id.order_id.id),
                ('id', '!=', move.sale_line_id.id),
                ('line_number', '=', move.sale_line_id.line_number),
                ('is_line_split', '=', True),
                ('state', '=', 'cancel'),
                ('product_uom_qty', '=', move.product_qty),
            ])
            if split_sol_ids:
                impacted_ir.append('%s #%s' % (move.sale_line_id.order_id.name, move.sale_line_id.line_number))
                move_obj.write(cr, uid, [move.id], {'sale_line_id': split_sol_ids[0]})

        if impacted_ir:
            self._logger.warn('%d IR cancelled lines linked to cancelled OUT: %s' % (len(impacted_ir), ', '.join(impacted_ir)))
        return True


    def us_5785_set_ocg_price_001(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance:
            return True

        if instance.instance.startswith('OCG'):
            cr.execute("""select p.id, tmpl.id, p.default_code from
                product_template tmpl, product_product p
                where
                    p.product_tmpl_id = tmpl.id and
                    standard_price=0
                """)
            prod = cr.fetchall()
            if prod:
                cr.execute('update product_template set standard_price=0.01, list_price=0.01 where id in %s', (tuple([x[1] for x in prod]), ))
                self._logger.warn('Change price to 0.01 on %d products: %s' % (cr.rowcount,', '.join([x[2] for x in prod])))
                for prod_i in prod:
                    cr.execute("""insert into standard_price_track_changes ( create_uid, create_date, old_standard_price, new_standard_price, user_id, product_id, change_date, transaction_name) values
                            (1, NOW(), 0.00, 0.01, 1, %s, date_trunc('second', now()::timestamp), 'Patch US-5785')
                            """,  (prod_i[0], ))
                if instance.level == 'section' and instance.code == 'CH':
                    cr.execute('''update ir_model_data set touched='[''default_code'']', last_modification=NOW() where model='product.product' and res_id in %s and module='sd' ''', (tuple([x[0] for x in prod]), ))
                    self._logger.warn('Tigger price sync update on %d products' % (cr.rowcount,))
        return True

    def us_5667_remove_contract_workflow(self, cr, uid, *a, **b):
        """
        Deletes the workflow related to Financing Contracts (not used anymore)
        """
        delete_wkf_transition = """
            DELETE FROM wkf_transition
            WHERE signal IN ('contract_open', 'contract_soft_closed', 'contract_hard_closed', 'contract_reopen')
            AND act_from IN 
                (SELECT id FROM wkf_activity WHERE wkf_id = 
                    (SELECT id FROM wkf WHERE name='wkf.financing.contract' AND osv='financing.contract.contract')
                );
        """
        delete_wkf_workitem = """
            DELETE FROM wkf_workitem WHERE act_id IN
                (SELECT id FROM wkf_activity WHERE wkf_id = 
                    (SELECT id FROM wkf WHERE name='wkf.financing.contract' AND osv='financing.contract.contract')
                );
        """
        delete_wkf_activity = """
            DELETE FROM wkf_activity 
            WHERE wkf_id = (SELECT id FROM wkf WHERE name='wkf.financing.contract' AND osv='financing.contract.contract');
        """
        delete_wkf = """
            DELETE FROM wkf WHERE name='wkf.financing.contract' AND osv='financing.contract.contract';
        """
        cr.execute(delete_wkf_transition)
        cr.execute(delete_wkf_workitem)
        cr.execute(delete_wkf_activity)
        cr.execute(delete_wkf)  # will also delete data in wkf_instance because of the ONDELETE 'cascade'
        return True

    # UF12.0
    def us_5724_set_previous_fy_dates_allowed(self, cr, uid, *a, **b):
        """
        Sets the field "previous_fy_dates_allowed" to True in the UniField Setup Configuration for all OCB and OCP instances
        """
        user_obj = self.pool.get('res.users')
        current_instance = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance and (current_instance.name.startswith('OCB') or current_instance.name.startswith('OCP')):
            cr.execute("UPDATE unifield_setup_configuration SET previous_fy_dates_allowed = 't';")
        return True

    def us_5746_rename_products_with_new_lines(self, cr, uid, *a, **b):
        """
        Remove the "new line character" from the description of products and their translation
        """
        cr.execute("""
            UPDATE product_template
            SET name = regexp_replace(name, '^\\s+', '', 'g' )
            WHERE name ~ '^\\s.*';
            """)
        self._logger.warn('Update description on %d products' % (cr.rowcount,))
        cr.execute("""
            UPDATE ir_translation
            SET src = regexp_replace(src, '^\\s+', '', 'g' ), value = regexp_replace(value, '^\\s+', '', 'g' )
            WHERE name = 'product.template,name' AND (src ~ '^\\s.*' OR value ~ '^\\s.*');
            """)
        self._logger.warn('Update src and/or value on %d products translations' % (cr.rowcount,))
        return True

    def us_2896_volume_ocbprod(self, cr, uid, *a, **b):
        ''' OCBHQ: volume has not been converted to dm3 on instances '''
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if instance and instance.name == 'OCBHQ':
            cr.execute('''update ir_model_data set last_modification=NOW(), touched='[''volume'']' where module='sd' and name in ('product_TVECZTF0058','product_TVECZTF0051','product_TVECZBE0175','product_TVEAZTF0086','product_TVEAZTF0057','product_STRYZ597044S','product_STRYZ597004S','product_STRYZ596001S','product_STRYZ33625100','product_STRYZ33625080','product_SCTDZBE0102','product_SCTDZBE0090','product_PTOOZBE0502','product_PTOOPLIE01E','product_PSAFZBE0109','product_PSAFZBE0076','product_PPAIZBE0010','product_PIDEZTF0073','product_PHYGZBE0022','product_PELEZBE1287','product_PELEZBE1279','product_PCOOZTF0014','product_PCOOZBE0039','product_PCOOZBE0038','product_PCOMZBE0518','product_L028AIDG01E','product_KADMZBE0031','product_EPHYCRUT1C-','product_EMEQBOTP01-','product_ELAEZTF0809','product_ELAEZBE0941','product_ELAEZBE0898','product_EHOEZBE1052','product_EHOEZBE0907','product_EDIMZBE0103','product_EDIMZBE0102','product_EDIMZBE0101','product_EDIMZBE0099','product_EDIMZBE0061','product_EANEZTF0081','product_EANEZTF0079','product_EANEZBE0167','product_DEXTZBE0031','product_ALIFZTF0029','product_ADAPZBE0460','product_41400-35031')''')
            self._logger.warn('Trigger sync updates on %d products' % (cr.rowcount,))
        return True

    def us_5507_set_synchronize(self, cr, uid, *a, **b):
        try:
            sync_id = self.pool.get('ir.model.data').get_object_reference(cr, 1, 'base', 'user_sync')[1]
        except:
            return True
        cr.execute("update res_users set synchronize='t' where create_uid=%s", (sync_id,))
        self._logger.warn('Set synchronize on  %s users.' % (cr.rowcount,))
        return True

    def us_5480_correct_partner_fo_default_currency(self, cr, uid, *a, **b):
        """
        Sets FO default currency = PO default currency for all external partners where these currencies are different
        """
        partner_obj = self.pool.get('res.partner')
        pricelist_obj = self.pool.get('product.pricelist')
        partner_ids = partner_obj.search(cr, uid, [('partner_type', '=', 'external'), ('active', 'in', ['t', 'f'])])
        partner_count = 0
        sync = 0
        for partner in partner_obj.browse(cr, uid, partner_ids,
                                          fields_to_fetch=['property_product_pricelist_purchase',
                                                           'property_product_pricelist',
                                                           'locally_created']):
            if partner.property_product_pricelist_purchase and partner.property_product_pricelist \
                    and partner.property_product_pricelist_purchase.currency_id.id != partner.property_product_pricelist.currency_id.id:
                # search for the "Sale" pricelist having the same currency as the "Purchase" pricelist currently used
                pricelist_dom = [('type', '=', 'sale'),
                                 ('currency_id', '=', partner.property_product_pricelist_purchase.currency_id.id)]
                pricelist_ids = pricelist_obj.search(cr, uid, pricelist_dom, limit=1)
                if pricelist_ids:
                    sql = """
                          UPDATE ir_property
                          SET value_reference = %s
                          WHERE name = 'property_product_pricelist'
                          AND res_id = %s;
                          """
                    cr.execute(sql, ('product.pricelist,%s' % pricelist_ids[0], 'res.partner,%s' % partner.id))
                    if partner.locally_created:
                        cr.execute("update ir_model_data set last_modification=NOW(), touched='[''property_product_pricelist'']' where model='res.partner' and module='sd' and res_id = %s", (partner.id,))
                        sync += 1
                    partner_count += 1
        self._logger.warn('FO default currency modified for %s partner(s), %s sync generated' % (partner_count, sync))
        return True

    # UF11.1
    def us_5559_set_pricelist(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity'):
            # new instance nothing to fix
            return True

        data_obj = self.pool.get('ir.model.data')
        po_id = data_obj.get_object_reference(cr, uid, 'purchase', 'list0')[1]
        so_id = data_obj.get_object_reference(cr, uid, 'product', 'list0')[1]

        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        if c.currency_id and c.currency_id.name =='CHF':
            ch_po_id = data_obj.get_object_reference(cr, uid, 'sd', 'CHF_purchase')[1]
            ch_so_id = data_obj.get_object_reference(cr, uid, 'sd', 'CHF_sale')[1]
            to_fix = [(po_id, so_id, ['section']), (ch_po_id, ch_so_id, ['intermission'])]
        else:
            to_fix = [(po_id, so_id, ['section', 'intermission'])]

        partner = self.pool.get('res.partner')


        for pl_po_id, pl_so_id, domain in to_fix:
            partner_ids = partner.search(cr, uid, [('active', 'in', ['t', 'f']), ('partner_type', 'in', domain)])


            if partner_ids:
                po_pricelist = 'product.pricelist,%s' % pl_po_id
                cr.execute('''update ir_property set value_reference=%s where name='property_product_pricelist_purchase' and value_reference!=%s and res_id in %s''', (po_pricelist, po_pricelist, tuple(['res.partner,%s'%x for x in partner_ids]),))
                self._logger.warn('PO Currency changed on %d partners' % (cr.rowcount,))


                so_pricelist = 'product.pricelist,%s' % pl_so_id
                cr.execute('''update ir_property set value_reference=%s where name='property_product_pricelist' and value_reference!=%s and res_id in %s''', (so_pricelist, so_pricelist, tuple(['res.partner,%s'%x for x in partner_ids]),))
                self._logger.warn('FO Currency changed on %d partners' % (cr.rowcount,))

        return True

    def us_5425_reset_amount_currency(self, cr, uid, *a, **b):
        """
        Sets to zero the JI "amount_currency" which wrongly have a value
        Note: it fixes only the reval and FX entries where we forced the booking values to be exactly 0.00
        """
        update_ji_booking = """
                    UPDATE account_move_line
                    SET amount_currency = 0.0
                    WHERE (debit_currency = 0.0 OR debit_currency IS NULL) 
                    AND (credit_currency = 0.0 OR credit_currency IS NULL) 
                    AND (amount_currency != 0.0 AND amount_currency IS NOT NULL)
                    AND journal_id IN (SELECT id FROM account_journal WHERE type IN ('cur_adj', 'revaluation'));
                """
        cr.execute(update_ji_booking)
        self._logger.warn('amount_currency reset in %s JI.' % (cr.rowcount,))

    def us_5398_reset_ud_cost_price(self, cr, uid, *a, **b):
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance_id:
            return True
        if instance_id.level == 'section' and instance_id.code == 'CH':
            self.pool.get('sync.trigger.something').create(cr, uid, {'name': 'us-5398-product-price'})
        return True

    # UF11.0
    def us_5356_reset_ud_prod(self, cr, uid, *a, **b):
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance_id:
            return True
        if instance_id.level == 'section':
            self.pool.get('sync.trigger.something').create(cr, uid, {'name': 'clean_ud_fff'})
        return True


    def us_4996_bck_beforepatch(self, cr, uid, *a, **b):
        if self.pool.get('backup.config'):
            cr.execute("update backup_config set beforepatching='t'")
        return True

    def testfield_missing_updates_on_sync(self, cr, uid, *a, **b):
        if cr.dbname.endswith('HQ1') and self.pool.get('sync.client.entity'):
            entity = self.pool.get('sync.client.entity')._get_entity(cr)
            if entity.identifier == 'a1d9db61-024f-11e6-856f-480fcf273a8d' and entity.update_last == 304:
                cr.execute('''update ir_model_data set last_modification=NOW(), touched='[''name'', ''id'']' where
                    name in (
                        select sdref from sync_client_update_to_send where session_id='7ff7242e-7f6f-11e6-b415-0cc47a3516aa' and model in ('hr.payment.method', 'ir.translation', 'product.nomenclature', 'product.product', 'sync.trigger.something')
                    )''')
        return True

    def us_4541_stock_mission_recompute_cu_qty(self, cr, uid, *a, **b):
        """
        rest cu_qty and central_qty
        """
        trigger_up = self.pool.get('sync.trigger.something.up')
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance_id:
            return True

        central_loc = self.pool.get('stock.location').search(cr, uid, [('central_location_ok', '=', 't')])
        if not central_loc:
            cr.execute("update stock_mission_report_line set central_qty=0,central_val=0 where mission_report_id in (select id from stock_mission_report where instance_id = %s and full_view='f')", (instance_id.id,))
            if cr.rowcount:
                trigger_up.create(cr, uid, {'name': 'clean_mission_stock_central', 'args': instance_id.code})

        cu_loc = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal'), ('location_category', '=', 'consumption_unit')])
        if not cu_loc:
            cr.execute("update stock_mission_report_line set cu_qty=0, cu_val=0 where mission_report_id in (select id from stock_mission_report where instance_id = %s and full_view='f')", (instance_id.id,))
            if cr.rowcount:
                trigger_up.create(cr, uid, {'name': 'clean_mission_stock_cu', 'args': instance_id.code})
        return True

    def us_4375_build_xmlid_admin_acl(self, cr, uid, *a, **b):
        '''
            some system acl don't have any sdref, recreate a clean unique sdref for all system acl
        '''
        access_obj = self.pool.get('ir.model.access')
        if not self.pool.get('sync.client.entity') or self.pool.get('sync.server.message'):
            return True

        access_ids = access_obj.search(cr, uid, [('name', '=', 'admin'), ('group_id', '=', False)])
        if access_ids:
            access_obj.write(cr, uid, access_ids, {'name': 'user read', 'from_system': True})

        admin_acl_ids = access_obj.search(cr, uid, [('name', '=', 'admin')])
        access_obj.write(cr, uid, admin_acl_ids, {'from_system': True})

        access_ids += admin_acl_ids
        if access_ids:
            cr.execute("delete from ir_model_data where model='ir.model.access' and res_id in %s", (tuple(access_ids),))
            access_obj.get_sd_ref(cr, uid, access_ids)

        return True


    # UF10.0
    def us_3427_update_third_parties_in_gl_selector(self, cr, uid, *a, **b):
        """
        Third Parties in G/L selector (partners / employees / journals) become many2many fields
        Updates the existing selectors accordingly
        (note: selectors aren't synched for now)
        """
        selector_obj = self.pool.get('account.mcdb')
        selector_ids = selector_obj.search(cr, uid, [('model', '=', 'account.move.line')])
        for selector in selector_obj.browse(cr, uid, selector_ids,
                                            fields_to_fetch=['partner_id', 'employee_id', 'transfer_journal_id']):
            partner_ids, employee_ids, transfer_journal_ids = [], [], []
            display_partner = display_employee = display_transfer_journal = False
            if selector.partner_id:
                partner_ids = [selector.partner_id.id]
                display_partner = True
            if selector.employee_id:
                employee_ids = [selector.employee_id.id]
                display_employee = True
            if selector.transfer_journal_id:
                transfer_journal_ids = [selector.transfer_journal_id.id]
                display_transfer_journal = True
            vals = {
                # old fields not used anymore: to set to False in any cases
                'partner_id': False,
                'employee_id': False,
                'transfer_journal_id': False,
                # new fields: to fill in if need be
                'partner_ids': [(6, 0, partner_ids)],
                'employee_ids': [(6, 0, employee_ids)],
                'transfer_journal_ids': [(6, 0, transfer_journal_ids)],
                # 'display' boolean: to set to True to display the relative section by default in the selector
                'display_partner': display_partner,
                'display_employee': display_employee,
                'display_transfer_journal': display_transfer_journal,
            }
            selector_obj.write(cr, uid, selector.id, vals)

    def us_4879_fo_from_shipping_except_to_close(self, cr, uid, *a, **b):
        cr.execute("update sale_order set state='done' where state='shipping_except' and procurement_request='f'")
        self._logger.warn('FO from shipping_except to done: %d' % (cr.rowcount,))
        return True

    def us_3873_update_reconcile_filter_in_partner_report_templates(self, cr, uid, *a, **b):
        """
        Updates the Wizard Templates for the "Partner Ledger" and "Partner Balance" following the change on reconcile filter:
        - "Include Reconciled Entries" ticked ==> becomes "Reconciled: Empty"
        - "Include Reconciled Entries" unticked ==> becomes "Reconciled: No"
        (Note: templates aren't synched for now)
        """
        template_obj = self.pool.get('wizard.template')
        template_ids = template_obj.search(cr, uid, [('wizard_name', 'in',
                                                      ['account.partner.ledger', 'wizard.account.partner.balance.tree'])])
        for template in template_obj.browse(cr, uid, template_ids, fields_to_fetch=['wizard_name', 'values']):
            old_field = template.wizard_name == 'account.partner.ledger' and 'reconcil' or 'include_reconciled_entries'
            new_field = 'reconciled'
            try:
                values_dict = eval(template.values)
                if old_field in values_dict:
                    if not values_dict[old_field]:
                        reconciled = 'no'
                    else:
                        reconciled = 'empty'
                    values_dict[new_field] = reconciled
                    del values_dict[old_field]
                    template_obj.write(cr, uid, template.id, {'values': values_dict})
            except:
                pass

    def us_3873_update_display_partner_in_partner_balance_templates(self, cr, uid, *a, **b):
        """
        Updates the Wizard Templates for the "Partner Balance" report following the fact that the display_partner field
        is now required: an empty display_partner becomes "With movements" (= will give the same results as before US-3873 dev)
        (Note: templates aren't synched for now)
        """
        template_obj = self.pool.get('wizard.template')
        template_ids = template_obj.search(cr, uid, [('wizard_name', '=', 'wizard.account.partner.balance.tree')])
        for template in template_obj.browse(cr, uid, template_ids, fields_to_fetch=['values']):
            try:
                values_dict = eval(template.values)
                if 'display_partner' in values_dict:
                    if not values_dict['display_partner']:
                        values_dict['display_partner'] = 'with_movements'
                        template_obj.write(cr, uid, template.id, {'values': values_dict})
            except:
                pass

    def us_3873_remove_initial_balance_in_partner_balance_templates(self, cr, uid, *a, **b):
        """
        Removes the initial_balance from the Wizard Templates for the "Partner Balance" report
        (Note: templates aren't synched for now)
        """
        template_obj = self.pool.get('wizard.template')
        template_ids = template_obj.search(cr, uid, [('wizard_name', '=', 'wizard.account.partner.balance.tree')])
        for template in template_obj.browse(cr, uid, template_ids, fields_to_fetch=['values']):
            try:
                values_dict = eval(template.values)
                if 'initial_balance' in values_dict:
                    del values_dict['initial_balance']
                    template_obj.write(cr, uid, template.id, {'values': values_dict})
            except:
                pass

    # UF9.1
    def change_xml_payment_method(self, cr, uid, *a, **b):
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid])[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level

        if not level_current:
            return True


        identifier = self.pool.get('sync.client.entity')._get_entity(cr).identifier
        cr.execute("update sync_client_update_received set run='t', log='Set as run by US-4762' where run='f' and model='hr.payment.method'")
        cr.execute("delete from ir_model_data where model='hr.payment.method' and res_id not in (select id from hr_payment_method)")
        cr.execute("update ir_model_data set name=(select 'hr_payment_method_'||name from hr_payment_method where id=res_id) where model='hr.payment.method'")

        # on HQ sync down payment method
        if level_current == 'section':
            cr.execute("update ir_model_data set last_modification=NOW(), touched='[''name'']' where model='hr.payment.method'")
            pay_obj = self.pool.get('hr.payment.method')
            for pm in ['ESP', 'CHQ', 'VIR']:
                if not pay_obj.search(cr, uid, [('name', '=', pm)]):
                    pay_obj.create(cr, uid, {'name': pm})


        # touch employee created on this instance
        cr.execute("""update ir_model_data set last_modification=NOW(), touched='[''payment_method_id'']' where model='hr.employee' and module='sd' and name like %s||'/%%'
            and res_id in (select id from hr_employee where payment_method_id is not null)""" , (identifier,))

        return True

    # UF9.0
    def change_fo_seq_to_nogap(self, cr, uid, *a, **b):
        data = self.pool.get('ir.model.data')
        seq_id = False
        try:
            seq_id = data.get_object_reference(cr, uid, 'sale', 'seq_sale_order')[1]
        except:
            return True

        if seq_id:
            seq_obj = self.pool.get('ir.sequence')
            seq_id = seq_obj.search(cr, uid, [('id', '=', seq_id), ('implementation', '=', 'psql')])
            if seq_id:
                seq_obj.write(cr, uid, seq_id[0], {'implementation': 'no_gap'})
                self._logger.warn('Change FO seq to no_gap')
        return True

    def us_4481_monitor_set_null_size(self,cr, uid, *a, **b):
        if self.pool.get('sync.version.instance.monitor'):
            cr.execute('update sync_version_instance_monitor set cloud_size=0 where cloud_size is null')
            cr.execute('update sync_version_instance_monitor set backup_size=0 where backup_size is null')
        return True

    def us_3319_product_track_price(self, cr, uid, *a, **b):
        cr.execute('select count(*) from standard_price_track_changes')
        num = cr.fetchone()
        if num and num[0]:
            cr.execute("""insert into standard_price_track_changes ( create_uid, create_date, old_standard_price, new_standard_price, user_id, product_id, change_date, transaction_name)
                    select 1, NOW(), t.standard_price, t.standard_price, 1, p.id, date_trunc('second', now()::timestamp), 'Price corrected' from product_product p, product_template t where p.product_tmpl_id=t.id and t.cost_method='average'
                    """)
        return True

    def us_3015_remove_whitespaces_product_description(self, cr, uid, *a, **b):
        # Checking product's description
        cr.execute('''SELECT id, name FROM product_template WHERE name LIKE ' %' or name LIKE '% ' ''')
        for x in cr.fetchall():
            cr.execute('''UPDATE product_template SET name = %s WHERE id = %s''', (x[1].strip(), x[0]))

        # Checking product's description in the translations
        cr.execute('''SELECT id, value FROM ir_translation 
            WHERE name = 'product.template,name' AND value LIKE ' %' or value LIKE '% ' ''')
        for x in cr.fetchall():
            cr.execute('''UPDATE ir_translation SET value = %s WHERE id = %s''', (x[1].strip(), x[0]))

        return True

    # UF8.2
    def ud_trans(self, cr, uid, *a, **b):
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid])[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level
        if level_current == 'section':
            self.pool.get('sync.trigger.something').create(cr, uid, {'name': 'clean_ud_trans'})

            unidata_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]


            cr.execute("""
                update ir_translation r set xml_id =
                    (select d.name from ir_model_data d where model='product.product' and module='sd' and d.res_id=(select p.id from product_product p where p.product_tmpl_id=r.res_id))
                    where r.name='product.template,name'
            """)
            self._logger.warn('HQ update xml_id no %d product trans' % (cr.rowcount,))

            cr.execute("""update ir_model_data set last_modification=NOW(), touched='[''value'']' where
                model='ir.translation' and
                res_id in (
                   select id from ir_translation where name='product.template,name' and res_id in (
                        select p.product_tmpl_id from product_product p where p.international_status=%s
                        )
                )
            """, (unidata_id,))
            self._logger.warn('HQ touching %d UD trans' % (cr.rowcount,))

            # send product on which UD has changed the name without any lang ctx, if there isn't any ir.trans record
            cr.execute("""update ir_model_data set last_modification=NOW(), touched='[''name'']'
                where model='product.product' and
                res_id in (
                    select id from product_product where product_tmpl_id in
                        ( select id from product_template where id in
                            (select res_id from audittrail_log_line where name='name' and object_id=128 and method='write')
                          and id not in (select res_id from ir_translation where name='product.template,name' and lang='en_MF')
                        )
                )
            """)
            self._logger.warn('HQ touching %d UD prod' % (cr.rowcount,))

        return True

    # UF8.1
    def cancel_extra_empty_draft_po(self, cr, uid, *a, **b):
        rule_obj = self.pool.get('sync.client.message_rule')
        msg_to_send_obj = self.pool.get("sync.client.message_to_send")

        if self.pool.get('sync_client.version'):
            rule = rule_obj.get_rule_by_remote_call(cr, uid, 'purchase.order.update_fo_ref')
            cr.execute('''
                select bad.id,bad.name,bad.state, bad.client_order_ref
                from sale_order bad
                left join sale_order_line badline on badline.order_id = bad.id
                left join sale_order old on old.client_order_ref=bad.client_order_ref
                where 
                bad.split_type_sale_order='original_sale_order' and
                bad.client_order_ref ~ '.*-[1,2,3]$' and
                bad.procurement_request='f' and
                bad.state in ('draft', 'cancel') and
                old.split_type_sale_order != 'original_sale_order'
                group by bad.id, bad.name, bad.state
                having count(badline)=0 and count(old.id) > 0
            ''')
            for x in cr.fetchall():
                self._logger.warn('US-4454: cancel FO %s, ref: %s (id:%s)' % (x[1], x[3], x[0]))
                cr.execute("update sale_order set state='cancel', client_order_ref='' where id=%s", (x[0],))
                gen_ids = self.pool.get('sale.order').search(cr, uid, [('client_order_ref', '=', x[3]), ('state', '!=', 'cancel')])
                if gen_ids:
                    self._logger.warn('US-4454: gen ref %s' % gen_ids)
                    for gen_id in gen_ids:
                        arguments = self.pool.get('sale.order').get_message_arguments(cr, uid, gen_id, rule)
                        identifiers = msg_to_send_obj._generate_message_uuid(cr, uid, 'sale.order', [gen_id], rule.server_id)
                        data = {
                            'identifier' : identifiers[gen_id],
                            'remote_call': rule.remote_call,
                            'arguments': arguments,
                            'destination_name': x[3].split('.')[0],
                            'sent' : False,
                            'res_object': '%s,%s' % ('sale.order', gen_id),
                            'generate_message' : True,
                        }
                        msg_to_send_obj.create(cr, uid, data)

        return True

    def us_4430_set_puf_to_reversal(self, cr, uid, *a, **b):
        """
        Context: in case of an SI refund-cancel or modify since US-1255 (UF7.0) the original PUR are marked as reallocated,
        since US-4137 (UF7.2) PUF are marked as reversal.
        This method fixes the entries generated in between:
        - sets the PUF AJIs as is_reversal: will fix the discrepancies in Financing Contracts and Budget Monitoring Report
        - sets the PUF JIs as is_si_refund: will make the lines not correctable

        Criteria used to spot the JIs to fix:
        - JIs booked on a journal having the type "Purchase refund"
        - which belong to a JE system
        - which are reconciled (implies that all SI headers were booked on a reconcilable account) with a JI:
            ==> booked on a journal having the type "Purchase"
            ==> which belongs to a JE system
            ==> which belongs to a JE having at least one leg set as "corrected"
                Cf: - the JI corresponding to the SI header line is not set as corrected during a refund-cancel, only the SI lines are.
                    - since US-1255 (UF7.0) it is not possible to do a refund-cancel once one of the SI lines has been corrected.
        - with a creation date after 7.0
            ==> no ending date to cover the diff between UF7.2 patch date at sync server and within each instance
            ==> entries generated after 7.2 are already correct and won't be impacted
        - which are set neither as "is_si_refund" nor as "reversal".
        """
        if self.pool.get('sync_client.version'):  # exclude sync server + new instances being created
            user_obj = self.pool.get('res.users')
            update_aji = """
                UPDATE account_analytic_line
                SET is_reversal = 't'
                WHERE move_id IN (
                    SELECT id FROM account_move_line
                    WHERE move_id IN (
                        SELECT DISTINCT(am.id)
                            FROM account_move_line aml
                            INNER JOIN account_move am ON aml.move_id = am.id
                            INNER JOIN account_journal j ON aml.journal_id = j.id
                            WHERE j.type = 'purchase_refund'
                            AND am.status = 'sys'
                            AND aml.create_date > (SELECT applied FROM sync_client_version WHERE name = 'UF7.0' LIMIT 1)
                            AND aml.is_si_refund = 'f'
                            AND aml.reversal = 'f'
                            AND aml.reconcile_id IS NOT NULL
                            AND aml.reconcile_id IN (
                                SELECT r.id
                                FROM account_move_reconcile r
                                INNER JOIN account_move_line aml ON aml.reconcile_id = r.id
                                AND aml.id IN (
                                    SELECT aml.id
                                    FROM account_move_line aml
                                    INNER JOIN account_move am ON aml.move_id = am.id
                                    INNER JOIN account_journal j ON aml.journal_id = j.id
                                    WHERE j.type = 'purchase'
                                    AND am.status = 'sys'
                                    AND am.id IN (
                                        SELECT DISTINCT(am.id)
                                        FROM account_move am
                                        INNER JOIN account_move_line aml ON aml.move_id = am.id
                                        WHERE aml.corrected = 't'
                                        )
                                    )
                                )
                            )
                    );
                """
            update_ji = """
                UPDATE account_move_line
                SET is_si_refund = 't'
                WHERE move_id IN (
                    SELECT DISTINCT(am.id)
                    FROM account_move_line aml
                    INNER JOIN account_move am ON aml.move_id = am.id
                    INNER JOIN account_journal j ON aml.journal_id = j.id
                    WHERE j.type = 'purchase_refund'
                    AND am.status = 'sys'
                    AND aml.create_date > (SELECT applied FROM sync_client_version WHERE name = 'UF7.0' LIMIT 1)
                    AND aml.is_si_refund = 'f'
                    AND aml.reversal = 'f'
                    AND aml.reconcile_id IS NOT NULL
                    AND aml.reconcile_id IN (
                        SELECT r.id
                        FROM account_move_reconcile r
                        INNER JOIN account_move_line aml ON aml.reconcile_id = r.id
                        AND aml.id IN (
                            SELECT aml.id
                            FROM account_move_line aml
                            INNER JOIN account_move am ON aml.move_id = am.id
                            INNER JOIN account_journal j ON aml.journal_id = j.id
                            WHERE j.type = 'purchase'
                            AND am.status = 'sys'
                            AND am.id IN (
                                SELECT DISTINCT(am.id)
                                FROM account_move am
                                INNER JOIN account_move_line aml ON aml.move_id = am.id
                                WHERE aml.corrected = 't'
                                )
                            )
                        )
                    );
                """
            # trigger the sync for all AJIs whose the prop. instance is the current instance, to cover the use case
            # where only AJIs exist in a project because the doc was generated in coordo or in another project
            current_instance = user_obj.browse(cr, uid, uid).company_id.instance_id
            if current_instance and current_instance.level in ('coordo', 'project'):
                trigger_sync = """
                    UPDATE ir_model_data SET last_modification=NOW(), touched='[''is_reversal'']'
                    WHERE module='sd' AND model='account.analytic.line' AND res_id IN (
                        SELECT aal.id
                        FROM account_analytic_line aal
                        INNER JOIN account_analytic_journal aaj ON aal.journal_id = aaj.id
                        WHERE aaj.is_current_instance = 't'
                        AND move_id IN (
                        SELECT id FROM account_move_line
                        WHERE move_id IN (
                            SELECT DISTINCT(am.id)
                                FROM account_move_line aml
                                INNER JOIN account_move am ON aml.move_id = am.id
                                INNER JOIN account_journal j ON aml.journal_id = j.id
                                WHERE j.type = 'purchase_refund'
                                AND am.status = 'sys'
                                AND aml.create_date > (SELECT applied FROM sync_client_version WHERE name = 'UF7.0' LIMIT 1)
                                AND aml.is_si_refund = 'f'
                                AND aml.reversal = 'f'
                                AND aml.reconcile_id IS NOT NULL
                                AND aml.reconcile_id IN (
                                    SELECT r.id
                                    FROM account_move_reconcile r
                                    INNER JOIN account_move_line aml ON aml.reconcile_id = r.id
                                    AND aml.id IN (
                                        SELECT aml.id
                                        FROM account_move_line aml
                                        INNER JOIN account_move am ON aml.move_id = am.id
                                        INNER JOIN account_journal j ON aml.journal_id = j.id
                                        WHERE j.type = 'purchase'
                                        AND am.status = 'sys'
                                        AND am.id IN (
                                            SELECT DISTINCT(am.id)
                                            FROM account_move am
                                            INNER JOIN account_move_line aml ON aml.move_id = am.id
                                            WHERE aml.corrected = 't'
                                        )
                                    )
                                )
                            )
                        )
                    );
                """
                cr.execute(trigger_sync)
                self._logger.warn('%s entries for which a sync will be triggered.' % (cr.rowcount,))
            cr.execute(update_aji)
            self._logger.warn('%s AJI updated.' % (cr.rowcount,))
            cr.execute(update_ji)
            self._logger.warn('%s JI updated.' % (cr.rowcount,))


    # UF8.0
    def set_sequence_main_nomen(self, cr, uid, *a, **b):
        nom = ['MED', 'LOG', 'LIB', 'SRV']
        nom_obj = self.pool.get('product.nomenclature')
        seq = 0
        for name in nom:
            seq += 10
            nom_ids = nom_obj.search(cr, uid, [('level', '=', 0), ('name', '=', name)])
            if nom_ids:
                nom_obj.write(cr, uid, nom_ids, {'sequence': seq})

        return True

    def us_3734_rename_partners_with_new_lines(self, cr, uid, *a, **b):
        """
        Remove the "new line character" from the name of the partners, as well as in the related JIs and AJIs
        """
        update_partner = """
            UPDATE res_partner 
            SET name = regexp_replace(name, E'[\\n\\r]+', ' ', 'g' ) 
            WHERE name like '%' || chr(10) || '%';
            """
        update_ji = """
            UPDATE account_move_line 
            SET partner_txt = regexp_replace(partner_txt, E'[\\n\\r]+', ' ', 'g' ) 
            WHERE partner_txt like '%' || chr(10) || '%';
        """
        update_aji = """
            UPDATE account_analytic_line 
            SET partner_txt = regexp_replace(partner_txt, E'[\\n\\r]+', ' ', 'g' ) 
            WHERE partner_txt like '%' || chr(10) || '%';
        """
        cr.execute(update_partner)
        cr.execute(update_ji)
        cr.execute(update_aji)

    def us_4407_update_free_lines_ad(self, cr, uid, *a, **b):
        """
        Updates the distribution_id of the Free1/2 lines by using the distrib_line_id
        """
        update_free_1 = """
                        UPDATE account_analytic_line 
                        SET distribution_id = (SELECT distribution_id FROM free_1_distribution_line 
                                               WHERE id=regexp_replace(distrib_line_id, 'free.1.distribution.line,', '')::int) 
                        WHERE distrib_line_id ~ 'free.1.distribution.line,[0-9]+$' AND distribution_id IS NULL;
                        """
        update_free_2 = """
                        UPDATE account_analytic_line 
                        SET distribution_id = (SELECT distribution_id FROM free_2_distribution_line 
                                               WHERE id=regexp_replace(distrib_line_id, 'free.2.distribution.line,', '')::int) 
                        WHERE distrib_line_id ~ 'free.2.distribution.line,[0-9]+$' AND distribution_id IS NULL;
                        """
        cr.execute(update_free_1)
        cr.execute(update_free_2)

    def us_4151_change_correct_out_currency(self, cr, uid, *a, **b):
        '''
        search the currency_id in FO/IR for each OUT/PICK to set the correct one, doesn't change it if no FO/IR found
        '''
        company_curr = self.pool.get('res.company').browse(cr, uid, 1, fields_to_fetch=['currency_id']).currency_id.id

        move_ids_currencies = {}
        cr.execute('''
            select m.id, m.price_currency_id, s.procurement_request, pl.currency_id
            from stock_move m
                left join stock_picking p on (m.picking_id = p.id)
                left join sale_order_line sl on (m.sale_line_id = sl.id)
                left join sale_order s on (sl.order_id = s.id)
                left join product_pricelist pl on (s.pricelist_id = pl.id)
            where m.sale_line_id is not null and m.type = 'out' and p.type = 'out' and p.subtype in ('standard', 'picking')
        ''')
        for x in cr.fetchall():
            if x[2]:
                currency_id_key = company_curr
            else:
                currency_id_key = x[3]
            if x[1] != currency_id_key:
                if currency_id_key in move_ids_currencies:
                    move_ids_currencies[currency_id_key].append(x[0])
                else:
                    move_ids_currencies.update({currency_id_key: [x[0]]})

        for currency_id in move_ids_currencies:
            cr.execute('''update stock_move set price_currency_id = %s where id in %s'''
                       , (currency_id, tuple(move_ids_currencies[currency_id])))

        return True

    # UF7.3
    def flag_pi(self, cr, uid, *a, **b):
        cr.execute('''select distinct i.id, p.default_code from
            physical_inventory_discrepancy d,
            physical_inventory i,
            product_product p,
            stock_move m
            left join stock_production_lot lot on lot.id=m.prodlot_id
            where d.inventory_id=i.id and d.product_id = p.id and m.product_id=d.product_id and
                m.location_id=i.location_id and m.location_dest_id=i.location_id and
                m.state='done' and coalesce(m.expired_date, '2999-01-01')=coalesce(d.expiry_date, '2999-01-01') and coalesce(lot.name,'')=coalesce(d.batch_number,'') and d.ignored='f'
        ''')
        pi = {}
        for x in cr.fetchall():
            pi.setdefault(x[0], []).append(x[1])

        for pi_id in pi:
            cr.execute('''update physical_inventory set bad_stock_msg=%s, has_bad_stock='t' where id=%s''', ('\n'.join(pi[pi_id]), pi_id))

        return True

    def send_instance_uuid(self, cr, uid, *a, **b):
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if instance_id and not instance_id.instance_identifier and instance_id.state == 'active':
            entity = self.pool.get('sync.client.entity')
            if entity:
                identifier = entity.get_uuid(cr, uid)
                self._logger.warn('missing instance_identifier, set to %s' % (identifier,))
                self.pool.get('msf.instance').write(cr, uid, [instance_id.id], {'instance_identifier': identifier})

        return True

    # UF7.1 patches
    def recompute_amount(self, cr, uid, *a, **b):
        cr.execute("select min(id) from purchase_order_line where state in ('cancel', 'cancel_r') group by order_id")
        pol_ids = [x[0] for x in cr.fetchall()]
        if pol_ids:
            self.pool.get('purchase.order.line')._call_store_function(cr, uid, pol_ids, keys=['state'])
            self._logger.warn("Recompute amount on %d POs" % (len(pol_ids), ))

        cr.execute("select min(id) from sale_order_line where state in ('cancel', 'cancel_r') group by order_id")
        sol_ids = [x[0] for x in cr.fetchall()]
        if sol_ids:
            self.pool.get('sale.order.line')._call_store_function(cr, uid, sol_ids, keys=['state'])
            self._logger.warn("Recompute amount on %d SOs" % (len(sol_ids), ))

    def gen_pick(self, cr, uid, *a, **b):
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        instance_name = c and c.instance_id and c.instance_id.code
        if instance_name == 'SO_SOMA':
            self._logger.warn("SO_SOMA_OCA fix PO00027 to FO00013-1")
            self.pool.get('purchase.order.line').write(cr, uid, [499, 500, 501, 502], {'origin': '17/NL/SO001/FO00013-1'})
            self.pool.get('purchase.order.line').action_confirmed(cr, uid, [499, 500, 501, 502])

        cr.execute("""select l.id,l.line_number, o.name, o.state, l.state
        from sale_order_line l
        inner join sale_order o on o.id = l.order_id
        left join product_product p on p.id=l.product_id
        left join product_template t on t.id=p.product_tmpl_id
        left join stock_move m on m.sale_line_id=l.id
        left join purchase_order_line pol on pol.linked_sol_id = l.id
        where l.state in ('confirmed', 'done')
        and l.type='make_to_order'
        and m.id is null
        and pol.state != 'cancel'
        and o.split_type_sale_order!='original_sale_order'
        and l.write_date > '2018-01-10 00:00:00'
        and l.write_date is not null""")
        to_conf = []
        state_dict = {}
        for x in cr.fetchall():
            to_conf.append(x[0])
            state_dict.setdefault(x[4], [])
            state_dict[x[4]].append(x[0])
            self._logger.warn("Gen pick for FO %s, line %s (line id:%s)" % (x[2], x[1], x[0]))
        if to_conf:
            self.pool.get('sale.order.line').action_confirmed(cr, uid, to_conf, {})
        for state in state_dict:
            self.pool.get('sale.order.line').write(cr, uid, state_dict[state], {'state': state}, {})
        return True

    def trigger_pofomsg(self, cr, uid, *a, **b):
        sync_client_obj = self.pool.get('sync.client.entity')
        if sync_client_obj:
            cr.execute("select identifier from sync_client_message_to_send where remote_call='sale.order.create_so'")
            po_sent = [0]
            for x in cr.fetchall():
                po_id = x[0].split('/')[-1].split('_')[0]
                try:
                    po_sent.append(int(po_id))
                except:
                    pass
            cr.execute("""
                select po.id from purchase_order po where po.partner_type not in ('external', 'esc') and po.split_po='f'
                and po.state in ('draft', 'draft-p', 'validated_p', 'validated') and po.id in (select res_id from ir_model_data where model='purchase.order' and (sync_date > last_modification and sync_date is not null))
                and po.id not in %s
                """, (tuple(po_sent), ))
            to_touch = [x[0] for x in cr.fetchall()]
            self._logger.warn("PO to touch: %s" % (','.join([str(x) for x in to_touch]),))
            if to_touch:
                cr.execute("update ir_model_data set last_modification=NOW() where res_id in %s and model='purchase.order'", (tuple(to_touch),))

            cr.execute("select identifier from sync_client_message_to_send where remote_call='purchase.order.normal_fo_create_po'")
            fo_sent = [0]
            for x in cr.fetchall():
                fo_id = x[0].split('/')[-1].split('_')[0]
                try:
                    fo_sent.append(int(fo_id))
                except:
                    pass
            cr.execute("""
                select fo.id from sale_order fo, res_partner p where
                p.id = fo.partner_id and p.partner_type not in ('external', 'esc') and procurement_request='f' and coalesce(fo.client_order_ref, '')=''
                and fo.state != 'cancel' and fo.id in (select res_id from ir_model_data where model='sale.order' and (sync_date > last_modification and sync_date is not null))
                and (fo.state != 'done' or fo.id in (select order_id from sale_order_line where coalesce(write_date, create_date) > '2018-01-14 18:00:00'))
                and fo.id not in %s
                """, (tuple(fo_sent), ))
            to_touch = [x[0] for x in cr.fetchall()]
            self._logger.warn("FO to touch: %s" % (','.join([str(x) for x in to_touch]),))
            if to_touch:
                cr.execute("update ir_model_data set last_modification=NOW() where res_id in %s and model='sale.order'", (tuple(to_touch),))


            # trigger sync msg for confirmed FO line
            cr.execute('''
                select l.id, l.line_number, o.name
                from sale_order_line l, sale_order o where
                     l.order_id=o.id and l.state in ('done', 'confirmed') and l.write_date>'2018-01-10' and l.write_date is not null
                     and l.id not in (select regexp_replace(identifier,'.*/([0-9]+)_[0-9]+', '\\1')::integer from sync_client_message_to_send where remote_call='purchase.order.line.sol_update_original_pol' and identifier ~ '/[0-9-]+_[0-9]+$')
                     and o.id not in (select regexp_replace(identifier,'.*/([0-9]+)_[0-9]+', '\\1')::integer from sync_client_message_to_send where remote_call='purchase.order.update_split_po' and identifier ~ '/[0-9-]+_[0-9]+$')
                     and o.procurement_request='f'
                     and o.split_type_sale_order!='original_sale_order'
            ''')
            for x in cr.fetchall():
                self._logger.warn("Fo line trigger confirmed msg FO: %s, line num %s, line id %s" % (x[2], x[1], x[0]))
                self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', x[0], {},
                                                                                      'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context={})


            # trigger sync msg for validated po lines
            cr.execute('''
                select l.id, l.line_number, o.name
                from purchase_order_line l, purchase_order o where
                     l.order_id=o.id and l.state = 'validated' and l.write_date>'2018-01-10' and o.partner_type not in ('esc', 'external') and l.write_date is not null
                     and l.id not in (select regexp_replace(identifier,'.*/([0-9]+)_[0-9]+', '\\1')::integer from sync_client_message_to_send where remote_call='sale.order.line.create_so_line' and identifier ~ '/[0-9-]+_[0-9]+$')
                     and o.id not in (select regexp_replace(identifier,'.*/([0-9]+)_[0-9]+', '\\1')::integer from sync_client_message_to_send where remote_call='sale.order.create_so' and arguments like '%order_line%' and identifier ~ '/[0-9-]+_[0-9]+$')
            ''')
            to_touch = []
            for x in cr.fetchall():
                self._logger.warn("PO line to touch: %s, line num %s, line id %s" % (x[2], x[1], x[0]))
                to_touch.append(x[0])
            if to_touch:
                cr.execute("update ir_model_data set last_modification=NOW() where res_id in %s and model='purchase.order.line'", (tuple(to_touch),))


            cr.commit()
            return True

    def close_pol_already_processed(self, cr, uid, *a, **b):
        wf_service = netsvc.LocalService("workflow")
        cr.execute("select l.id, l.order_id, l.product_qty, o.name, l.line_number from purchase_order_line l, purchase_order o where l.order_id=o.id and l.state='confirmed'")
        for x in cr.fetchall():
            cr.execute('''select sum(product_qty) from stock_picking p, stock_move m
            where m.picking_id = p.id and p.type='in' and p.state in ('done', 'cancel', 'cancel_r')
            and p.purchase_id = %s and m.purchase_line_id = %s''', (x[1], x[0]))
            res = cr.fetchone()
            if res and res[0] and res[0] >= x[2]:
                self._logger.warn("PO line to close: PO %s, line number: %s, poline id %s" % (x[3], x[4], x[0]))
                wf_service.trg_validate(uid, 'purchase.order.line', x[0], 'done', cr)
        cr.commit()
        return True

    # UF7.0 patches
    def post_sll(self, cr, uid, *a, **b):
        # set constraint on ir_ui_view
        cr.drop_index_if_exists('ir_ui_view', 'ir_ui_view_model_type_priority')
        cr.drop_constraint_if_exists('ir_ui_view', 'ir_ui_view_unique_view')
        cr.execute('CREATE UNIQUE INDEX ir_ui_view_model_type_priority ON ir_ui_view (priority, type, model) WHERE inherit_id IS NULL')
        cr.execute("delete from ir_ui_view where name='aaa' and model='aaa' and priority=5")

        if not cr.column_exists('purchase_order', 'state_moved0'):
            self._logger.warn("New db, no sll migration")
            return True

        # rfq
        cr.execute("update purchase_order set state=state_moved0")
        cr.execute("update purchase_order set rfq_state='cancel' where state='cancel' and rfq_ok='t'")
        cr.execute("update purchase_order set rfq_state='done' where state='done' and rfq_ok='t'")
        cr.execute("update purchase_order set rfq_state='updated' where state='rfq_updated' and rfq_ok='t'")
        cr.execute("update purchase_order set rfq_state='sent' where state='rfq_sent' and rfq_ok='t'")
        cr.execute("update purchase_order set rfq_state='draft' where state='draft' and rfq_ok='t'")


        # po
        # TODO trigger confirmation
        # Delete WKF on PO / proc.order
        #cr.execute("update purchase_order set state='' where state='wait' and rfq_ok='f'")
        #cr.execute("update purchase_order set state='' where state='confirmed_wait' and rfq_ok='f'")

        cr.execute("update purchase_order set state='sourced_p' where state='sourced' and rfq_ok='f'")
        cr.execute("update purchase_order set state='validated' where state='confirmed' and rfq_ok='f'")
        cr.execute("update purchase_order set state='confirmed' where state='approved' and rfq_ok='f'")



        cr.execute("delete from wkf_workitem item where act_id in (select act.id from wkf_activity act where act.wkf_id in (select wkf.id from wkf where wkf.osv='purchase.order'))")
        cr.execute("delete from wkf_activity act where act.wkf_id in (select wkf.id from wkf where wkf.osv='purchase.order')")
        cr.execute("delete from wkf_instance inst where inst.wkf_id in (select wkf.id from wkf where wkf.osv='purchase.order')")



        # pol
        cr.execute("update purchase_order_line set state='draft' where order_id in (select id from purchase_order where rfq_ok='f' and state='draft')")
        cr.execute("update purchase_order_line set state='validated' where order_id in (select id from purchase_order where rfq_ok='f' and state='validated')")
        cr.execute("update purchase_order_line set state='sourced_sy' where order_id in (select id from purchase_order where rfq_ok='f' and state='sourced_p')")
        cr.execute("update purchase_order_line set state='confirmed' where order_id in (select id from purchase_order where rfq_ok='f' and state in ('confirmed', 'confirmed_wait'))")
        cr.execute("update purchase_order_line set state='done' where order_id in (select id from purchase_order where rfq_ok='f' and state='done')")
        cr.execute("update purchase_order_line set state='cancel' where order_id in (select id from purchase_order where rfq_ok='f' and state='cancel')")
        cr.execute("update purchase_order_line pol set confirmed_delivery_date=(select delivery_confirmed_date from purchase_order o where o.id = pol.order_id) where pol.confirmed_delivery_date is null and state in ('sourced_sy', 'confirmed')")



        cr.execute("update purchase_order_line pol set linked_sol_id=(select sol.id from sale_order_line sol where sol.procurement_id = pol.procurement_id) where pol.procurement_id is not null and pol.order_id not in (select id from purchase_order where state='split')")


        # this msg rule is needed as it can be triggered during this update procedure
        self.pool.get('sync.client.message_rule').create(cr, uid, {
            'name': 'FO line updates PO line',
            'server_id': 999,
            'model': 'sale.order.line',
            'domain': "[('order_id.partner_type', '!=', 'external'), ('state', '!=', 'draft'), ('product_uom_qty', '!=', 0.0)]",
            'sequence_number': 12,
            'remote_call': 'purchase.order.line.sol_update_original_pol',
            'arguments': "['resourced_original_line/id', 'resourced_original_remote_line','sync_sourced_origin', 'sync_local_id', 'sync_linked_pol', 'order_id/name', 'product_id/id', 'product_id/name', 'name', 'state','product_uom_qty', 'product_uom', 'price_unit', 'in_name_goods_return', 'analytic_distribution_id/id','comment','have_analytic_distribution_from_header','line_number', 'nomen_manda_0/id','nomen_manda_1/id','nomen_manda_2/id','nomen_manda_3/id', 'nomenclature_description','notes','default_name','default_code','date_planned','is_line_split', 'original_line_id/id', 'confirmed_delivery_date', 'stock_take_date', 'cancel_split_ok', 'modification_comment']",
            'destination_name': 'partner_id',
            'active': True,
            'type': 'MISSION',
            'wait_while': "[('order_id.state', 'in', ['draft', 'draft_p']), ('order_id.partner_type', 'not in', ['external', 'esc']), ('order_id.client_order_ref', '=', False)]",
        })

        # tigger WKF
        pol_obj = self.pool.get('purchase.order.line')
        po_obj = self.pool.get('purchase.order')
        wkf = netsvc.LocalService("workflow")
        for state in ('draft', 'validated', 'sourced_sy', 'confirmed'):
            pol_ids = pol_obj.search(cr, uid, [('state', '=', state), ('order_id.rfq_ok', '=', False)])
            self._logger.warn("%d %s PO lines: create wkf" % (len(pol_ids), state))
            if pol_ids:
                for pol in pol_ids:
                    wkf.trg_create(1, 'purchase.order.line', pol, cr)
                cr.execute('''
                    update wkf_workitem
                       set act_id = (select act.id from wkf_activity act, wkf where act.name=%s and act.wkf_id = wkf.id and wkf.osv='purchase.order.line')
                    where inst_id in (select inst.id from wkf_instance inst where inst.res_id in %s and  wkf_id = (select id from wkf where wkf.osv='purchase.order.line'))
                ''', (state, tuple(pol_ids)))

        po_ids = po_obj.search(cr, uid, [('state', '=', 'confirmed_wait')])
        self._logger.warn("%d PO confirmed wait to trigger." % (len(po_ids), ))
        for po_id in  po_ids:
            self._logger.warn("PO id:%d, confirm %d lines" % (po_id, len(po_ids)))
            pol_ids = pol_obj.search(cr, uid, [('state', '=', 'confirmed'), ('order_id', '=', po_id)])
            if pol_ids:
                try:
                    pol_obj.action_confirmed(cr, uid, pol_ids)
                except Exception:
                    error = "Confirmed wait trigger fails on po_id %s, %s" % (po_id, tools.ustr(traceback.format_exc()))
                    self._logger.warn(error)
                    netsvc.ops_event(cr.dbname, kind='SLL_MIG', dat=error)

        # so
        cr.execute("update sale_order set state=state_moved0")
        cr.execute("delete from wkf_workitem item where act_id in (select act.id from wkf_activity act where act.wkf_id in (select wkf.id from wkf where wkf.osv='sale.order'))")
        cr.execute("delete from wkf_activity act where act.wkf_id in (select wkf.id from wkf where wkf.osv='sale.order')")
        cr.execute("delete from wkf_instance inst where inst.wkf_id in (select wkf.id from wkf where wkf.osv='sale.order')")
        cr.execute("update sale_order set state='confirmed' where state in ('manual', 'progress')");
        #cr.execute("update sale_order_line set state='draft' where order_id in (select id from sale_order where state='draft')")
        cr.execute("update sale_order_line set state='validated' where order_id in (select id from sale_order where state='validated') and state='draft'")
        #cr.execute("update sale_order_line set state='sourced' where order_id in (select id from sale_order where state='sourced')")
        #cr.execute("update sale_order_line set state='confirmed' where order_id in (select id from sale_order where state='confirmed')")
        #cr.execute("update sale_order_line set state='done' where order_id in (select id from sale_order where state='done')")
        #cr.execute("update sale_order_line set state='cancel' where order_id in (select id from sale_order where state='cancel')")


        sol_obj = self.pool.get('sale.order.line')


        cr.execute('''select sol.id from sale_order_line sol, purchase_order_line pol, purchase_order o
            where pol.linked_sol_id = sol.id and pol.order_id = o.id and o.state='draft' and sol.state='confirmed'
        ''')
        from_confirmed_to_sourced = [x[0] for x in cr.fetchall()]


        for state in ('draft', 'validated', 'sourced', 'confirmed'):
            sol_ids = sol_obj.search(cr, uid, [('state', '=', state)])
            self._logger.warn("%d %s SO lines: create wkf" % (len(sol_ids), state))
            if state == 'sourced':
                sol_ids += from_confirmed_to_sourced
            elif state == 'confirmed':
                sol_ids = list(set(sol_ids) - set(from_confirmed_to_sourced))
            if sol_ids:
                for sol in sol_ids:
                    wkf.trg_create(1, 'sale.order.line', sol, cr)
                cr.execute('''
                    update wkf_workitem
                       set act_id = (select act.id from wkf_activity act, wkf where act.name=%s and act.wkf_id = wkf.id and wkf.osv='sale.order.line')
                    where inst_id in (select inst.id from wkf_instance inst where inst.res_id in %s and  wkf_id = (select id from wkf where wkf.osv='sale.order.line'))
                ''', (state, tuple(sol_ids)))

        to_source_ids = sol_obj.search(cr, uid, [('state', '=', 'sourced'), ('order_id.state', '=', 'validated')])
        # so partially confirmed: we must generate next doc on sourced line
        for to_source_id in to_source_ids:
            self._logger.warn("Source FO line %s" % (to_source_id,))
            try:
                self.pool.get('sale.order.line').source_line(cr, uid, [to_source_id])
            except Exception:
                error = "Confirmed wait trigger fails on po_id %s, %s" % (po_id, tools.ustr(traceback.format_exc()))
                self._logger.warn(error)
                netsvc.ops_event(cr.dbname, kind='SLL_MIG', dat=error)


        # set FO as sourced if PO line is draft
        if from_confirmed_to_sourced:
            cr.execute("update sale_order_line set state='sourced' where id in %s", (tuple(from_confirmed_to_sourced),))

        # set FO as sourced-v if PO line is Validated
        cr.execute('''select sol.id from sale_order_line sol, purchase_order_line pol
            where pol.linked_sol_id = sol.id and pol.state='validated' and sol.state in ('sourced', 'confirmed')
        ''')
        to_sourced_v = [x[0] for x in cr.fetchall()]
        if to_sourced_v:
            cr.execute("update sale_order_line set state='sourced_v' where id in %s", (tuple(to_sourced_v),))


        # do not re-generate messages
        cr.execute("select date_trunc('second', max(create_date)) from sync_client_message_to_send")
        create_date = [x[0] for x in cr.fetchall()]
        if create_date:
            cr.execute("update ir_model_data set sync_date=%s where module='sd' and model in ('purchase.order', 'sale.order', 'sale.order.line', 'purchase.order.line')", (create_date[0],))

        # Set sync id on POL/SOL
        cr.execute("update purchase_order_line set sync_linked_sol=regexp_replace(sync_order_line_db_id,'/FO([0-9-]+)_([0-9]+)$', '/FO\\1/\\2') where sync_order_line_db_id ~ '/FO([0-9-]+)_([0-9]+)$' ")
        cr.execute("update sale_order_line set sync_linked_pol=regexp_replace(source_sync_line_id,'/PO([0-9-]+)_([0-9]+)$', '/PO\\1/\\2') where source_sync_line_id ~ '/PO([0-9-]+)_([0-9]+)$'")


        acl_file = os.path.join(tools.config['root_path'], 'addons/msf_profile/migrations/7.0_acl.txt')
        if not os.path.exists(acl_file):
            self._logger.warn("File %s not found" % acl_file)
        else:
            all_acl = []
            fd = open(acl_file)
            for line in fd.readlines():
                line = line.strip()
                if line:
                    all_acl.append(line)
            update_module = self.pool.get('sync.server.update')
            if update_module:
                # we are on a sync server
                # delete depecrated acl to prevent NR on new created instance
                cr.execute('''delete from sync_server_update where sdref in %s''', (tuple(all_acl),))
            else:
                user_obj = self.pool.get('res.users')
                usr = user_obj.browse(cr, uid, [uid])[0]
                level_current = False

                if usr and usr.company_id and usr.company_id.instance_id:
                    level_current = usr.company_id.instance_id.level
                # only at hq ?
                if level_current == 'section':
                    for line in all_acl:
                        if line.startswith('_msf_profile/field_access_rule_line'):
                            # FARL change of field xmlid, force update on this FARL
                            cr.execute('''update ir_model_data set touched='[''field_name'']', last_modification=NOW() where name=%s''' , (line, ))
                        elif line.startswith('_msf_profile_sale_override'):
                            # ACL xmlid changed, force update
                            cr.execute('''update ir_model_data set touched='[''name'']', last_modification=NOW() where name=%s''' , (line.replace('sale_override', 'sale'), ))

        cr.commit()
        return True


    def delete_commitment(self, cr, uid, *a, **b):
        journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('code', '=', 'ENGI')])
        if journal_ids:
            aa_obj = self.pool.get('account.analytic.line')
            aa_ids = aa_obj.search(cr, uid, [('journal_id', 'in', journal_ids)])
            self._logger.warn("Delete %d Commitment" % len(aa_ids))
            if aa_ids:
                aa_obj.unlink(cr, uid, aa_ids)
        return True

    def us_3306(self, cr, uid, *a, **b):
        '''setup currency rate constraint
        '''
        cr.execute("SELECT conname, pg_catalog.pg_get_constraintdef(oid, true) as condef FROM pg_constraint where conname='res_currency_rate_rate_unique';")
        if not cr.fetchone():
            # delete the double indonesian rupiah currency
            currency_id = self.pool.get('res.currency').search(cr, uid,
                                                               [('name', '=', 'IDR'),
                                                                ('active', 'in', ('t', 'f'))])
            if currency_id:
                # remove the first rate added
                rate_obj = self.pool.get('res.currency.rate')
                rate_id = rate_obj.search(cr, uid,
                                          [('currency_id', '=', currency_id[0]),
                                           ('name', '=', '2014-01-01')], order='id',
                                          limit=1)
                if rate_id:
                    cr.execute('delete from res_currency_rate where id = %s', (rate_id[0],))
                    imd_obj = self.pool.get('ir.model.data')
                    imd_ids = imd_obj.search(cr, uid, [('model', '=', 'res.currency.rate'), ('res_id', '=', rate_id[0])])
                    imd_obj.unlink(cr, uid, imd_ids)
                cr.commit()

                # add the constraint
                try:
                    cr.execute("""
                        ALTER TABLE "%s" ADD CONSTRAINT "%s" %s
                        """ % ('res_currency_rate', 'res_currency_rate_rate_unique',
                               'unique(name, currency_id)'))  # not_a_user_entry
                except:
                    self._logger.warn('Unable to set unique constraint on currency rate')
                    cr.rollback()
        return True

    def us_2676(self, cr, uid, *a, **b):
        context = {}
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid], context=context)[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level

        if level_current == 'section':
            cr.execute('''update ir_model_data set last_modification=NOW(), touched='[''code'']' where model='account.analytic.journal' and res_id in
                (select id from account_analytic_journal where code='ENGI')
            ''')
        return True

    def us_3345_remove_space_in_employee_name(self, cr, uid, *a, **b):
        """
        Removes spaces at the beginning and end of employee name
        """
        sql_resource_table = """
            UPDATE resource_resource SET name = TRIM(name) WHERE id IN (SELECT resource_id FROM hr_employee);
            """
        sql_employee_table = """
            UPDATE hr_employee SET name_resource = TRIM(name_resource);
            """
        cr.execute(sql_resource_table)
        cr.execute(sql_employee_table)

    def us_3756_remove_space_partner(self, cr, uid, *a, **b):
        cr.execute('UPDATE res_partner SET name = TRIM(name)')
        return True

    def set_stock_level(self, cr, uid, *a, **b):
        done = {}
        cr.execute("delete from stock_mission_report_line_location where location_id is not null");
        cr.execute("select distinct m.product_id, m.location_id, m.location_dest_id, t.uom_id from stock_move m, product_template t, product_product p where m.product_id = p.id and t.id = p.product_tmpl_id and m.state='done'")
        prod_obj = self.pool.get('product.product')
        for x in cr.fetchall():
            for loc in (x[1], x[2]):
                key = (x[0], loc)
                if key in done:
                    continue
                av = prod_obj.get_product_available(cr, uid, [x[0]], context={'states': ('done',), 'what': ('in', 'out'), 'location': loc})
                cr.execute("""insert into stock_mission_report_line_location (location_id, product_id, quantity, last_mod_date, uom_id)
                    values (%s, %s, %s, NOW(), %s) RETURNING id
                """, (loc, x[0], av[x[0]], x[3]))
                created_id = cr.fetchone()[0]
                cr.execute("select create_ir_model_data(%s)", (created_id, ))
                done[key] = True
        # reset stock mission report line
        cr.execute('truncate mission_move_rel')
        fields_to_reset = ['in_pipe_coor_val', 'in_pipe_coor_qty', 'in_pipe_val', 'in_pipe_qty',
                           'secondary_val', 'cu_qty', 'wh_qty', 'cu_val', 'stock_val', 'central_qty',
                           'cross_qty', 'cross_val', 'secondary_qty', 'central_val', 'internal_qty', 'stock_qty'
                           ]
        if self.pool.get('sync.client.entity'):
            cr.execute("""update ir_model_data set touched='[''wh_qty'']', last_modification=NOW()
                where
                    module='sd' and model='stock.mission.report.line' and
                    res_id in (
                        select id from stock_mission_report_line where 
                        """ + ' OR '.join(['%s!=0'%x for x in fields_to_reset]) + """
                    )
            """) # not_a_user_entry

        cr.execute("""
            update stock_mission_report_line set
              """ + ' , '.join(['%s=0'%x for x in fields_to_reset])+ """
            where mission_report_id in
            (
                select id from stock_mission_report where full_view='f' and export_ok='t'
            )
        """) # not_a_user_entry

    def us_3516_change_damage_reason_type_incoming_ok(self, cr, uid, *a, **b):
        cr.execute("UPDATE stock_reason_type SET incoming_ok = 't' WHERE name = 'Damage'")
        cr.execute("UPDATE return_claim SET old_version='t' WHERE state!='draft'")
        return True

    def us_3879_set_pricelist_id_for_ir(self, cr, uid, *a, **b):
        currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        pricelist_id = self.pool.get('product.pricelist').search(cr, uid, [('type', '=', 'sale'),
                                                                           ('currency_id', '=', currency_id)], limit=1)[0]

        cr.execute("UPDATE sale_order SET pricelist_id = %s WHERE procurement_request = 't'", (pricelist_id,))
        return True

    # OLD patches
    def us_3048_patch(self, cr, uid, *a, **b):
        '''
        some protocol are now removed from possible protocols
        If an instance was using a removed protocol, change the connexion to
        use XMLRPCS
        '''
        server_connection = self.pool.get('sync.client.sync_server_connection')
        if not server_connection:
            return True
        connection_ids = server_connection.search(cr, uid, [])
        read_result = server_connection.read(cr, uid, connection_ids,
                                             ['protocol', 'port', 'host'])
        connection = read_result[0]
        if connection['protocol'] not in ['xmlrpc', 'gzipxmlrpcs']:
            # check port 443 permit to connect to sync_server
            from sync_client.timeout_transport import TimeoutTransport
            transport = TimeoutTransport(timeout=10.0)
            try:
                sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/db'%(connection['host'], 443), transport=transport)
                sock.server_version()
            except Exception:
                vals = {
                    'protocol': 'xmlrpc',
                    'port': 8069,
                }
            else:
                vals = {
                    'protocol': 'gzipxmlrpcs',
                    'port': 443,
                }
            server_connection.write(cr, uid, [connection['id']], vals)

    def us_2647(self, cr, uid, *a, **b):
        cr.execute('''update stock_inventory_line set dont_move='t' where id not in (
                select l.id from stock_inventory_line l
                    inner join stock_inventory_move_rel r on l.inventory_id = r.inventory_id
                    inner join stock_move m on m.id = r.move_id and m.product_id = l.product_id and coalesce(m.prodlot_id,0) = coalesce(l.prod_lot_id,0)
            ) and inventory_id in (select id from stock_inventory where state='done')
            ''')

        return True

    def us_2444_touch_liquidity_journals(self, cr, uid, *a, **b):
        if _get_instance_level(self, cr, uid) == 'project':
            cr.execute('''
                update ir_model_data set last_modification=NOW(), touched='[''type'']'
                where module='sd' and model='account.journal' and res_id in (
                    select id from account_journal where type in ('bank', 'cash', 'cheque') and is_current_instance='t'
                )
            ''')

    def us_3098_patch(self, cr, uid, *a, **b):
        cr.execute("""
            SELECT id, name
            FROM res_partner
            WHERE name IN (select name from res_partner where partner_type = 'internal')
            AND name IN (select name from res_partner where partner_type = 'intermission')
            AND partner_type = 'intermission';
        """)
        wrong_partners = cr.fetchall()

        updated_doc = []
        for partner in wrong_partners:
            intermission_partner_id = partner[0]
            partner_name = partner[1]
            internal_partner_id = self.pool.get('res.partner').search(cr, uid, [
                ('name', '=', partner_name),
                ('partner_type', '=', 'internal'),
            ])[0]
            address_id = self.pool.get('res.partner.address').search(cr, uid, [
                ('partner_id', '=', internal_partner_id),
                ('type', '=', 'default'),
            ])
            if not address_id:
                address_id = self.pool.get('res.partner.address').search(cr, uid, [
                    ('partner_id', '=', internal_partner_id),
                ])

            address_id = address_id[0]

            cr.execute("SELECT name FROM stock_picking WHERE partner_id = %s AND state not in ('done', 'cancel');", (intermission_partner_id,))
            updated_doc += [x[0] for x in cr.fetchall()]
            cr.execute("""
                UPDATE stock_picking
                SET partner_id = %s, partner_id2 = %s, address_id = %s, partner_type_stock_picking = 'internal', invoice_state = 'none'
                WHERE partner_id = %s
                AND state not in ('done', 'cancel');
            """, (internal_partner_id, internal_partner_id, address_id, intermission_partner_id) )
            cr.execute("""
                UPDATE stock_move
                SET partner_id = %s, partner_id2 = %s, address_id = %s
                WHERE (partner_id = %s OR partner_id2 = %s) AND state not in ('done', 'cancel');
            """, (internal_partner_id, internal_partner_id, address_id, intermission_partner_id, intermission_partner_id) )

            cr.execute("SELECT name FROM purchase_order WHERE partner_id = %s AND state not in ('done', 'cancel');", (intermission_partner_id,))
            updated_doc += [x[0] for x in cr.fetchall()]
            cr.execute("""
                UPDATE purchase_order
                SET partner_id = %s, partner_address_id = %s, partner_type = 'internal'
                WHERE partner_id = %s
                AND state not in ('done', 'cancel');
            """, (internal_partner_id, address_id, intermission_partner_id) )
            cr.execute("""
                UPDATE purchase_order_line pol
                SET partner_id = %s
                FROM purchase_order po
                WHERE pol.order_id = po.id
                AND pol.partner_id = %s
                AND po.state not in ('done', 'cancel');
            """, (internal_partner_id, intermission_partner_id) )

            cr.execute("SELECT name FROM sale_order WHERE partner_id = %s AND state not in ('done', 'cancel');", (intermission_partner_id,))
            updated_doc += [x[0] for x in cr.fetchall()]
            cr.execute("""
                UPDATE sale_order
                SET partner_id = %s, partner_invoice_id = %s, partner_order_id = %s, partner_shipping_id = %s, partner_type = 'internal'
                WHERE partner_id = %s
                AND state not in ('done', 'cancel');
            """, (internal_partner_id, address_id, address_id, address_id, intermission_partner_id) )
            cr.execute("""
                UPDATE sale_order_line sol
                SET order_partner_id = %s
                FROM sale_order so
                WHERE sol.order_id = so.id
                AND sol.order_partner_id = %s
                AND so.state not in ('done', 'cancel');
            """, (internal_partner_id, intermission_partner_id) )

            cr.execute("SELECT name FROM shipment WHERE partner_id = %s AND state not in ('done', 'cancel', 'delivered');", (intermission_partner_id,))
            updated_doc += [x[0] for x in cr.fetchall()]
            cr.execute("""
                UPDATE shipment
                SET partner_id = %s, partner_id2 = %s, address_id = %s
                WHERE partner_id = %s
                AND state not in ('done', 'cancel', 'delivered');
            """, (internal_partner_id, internal_partner_id, address_id, intermission_partner_id) )

        if updated_doc:
            self._logger.warn("Following documents have been updated with internal partner: %s" % ", ".join(updated_doc))

        return True

    def us_2257_patch(self, cr, uid, *a, **b):
        context = {}
        user_obj = self.pool.get('res.users')
        partner_obj = self.pool.get('res.partner')
        usr = user_obj.browse(cr, uid, [uid], context=context)[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level

        if level_current == 'section':
            intermission_ids = partner_obj.search(cr, uid, [('active', 'in', ['t', 'f']), ('partner_type', '=', 'intermission')])
            address_ids = []
            if intermission_ids:
                address_ids = self.pool.get('res.partner.address').search(cr, uid, [('partner_id', 'in', intermission_ids)])
                self._logger.warn('touch %d partners, %d addresses' % (len(intermission_ids), len(address_ids)))
                cr.execute("update ir_model_data set touched='[''name'']', last_modification=now() where model='res.partner' and module='sd' and res_id in %s" , (tuple(intermission_ids), ))
                if address_ids:
                    cr.execute("update ir_model_data set touched='[''name'']', last_modification=now() where model='res.partner.address' and module='sd' and res_id in %s" , (tuple(address_ids), ))

        return True

    def us_2730_patch(self, cr, uid, *a, **b):
        '''
        remove all translations, and then re-import them
        so that the {*}_MF.po files are authoritative
        '''
        cr.execute("""delete from ir_model_data where model='ir.translation' and res_id in (
            select id from ir_translation where lang = 'fr_MF' and type != 'model'
            )
        """)
        cr.execute("delete from ir_translation where lang = 'fr_MF' and type != 'model'")
        irmm = self.pool.get('ir.module.module')
        msf_profile_id = irmm.search(cr, uid, [('name', '=', 'msf_profile')])
        irmm.update_translations(cr, uid, msf_profile_id)

    def us_2632_patch(self, cr, uid, *a, **b):
        '''fix ir.model.data entries on sync_server instances
        '''
        update_module = self.pool.get('sync.server.update')
        if update_module:
            cr.execute("""
            UPDATE ir_model_data SET module='msf_sync_data_server' WHERE
            model='sync_server.message_rule' AND module='';
            """)

    def us_2806_add_ir_ui_view_constraint(self, cr, uid, *a, **b):
        '''
        The constraint may have not been added during the update because it is
        needeed to update all the modules before to add this constraint.
        Having it in this patch script will add it at the end of the update.
        '''
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = \'ir_ui_view_model_type_priority\'')
        if not cr.fetchone():
            cr.execute("""SELECT model, type, priority, count(*)
            FROM ir_ui_view
            WHERE inherit_id IS NULL
            GROUP BY model, type, priority
            HAVING count(*) > 1""")
            if not cr.fetchone():
                cr.execute('CREATE UNIQUE INDEX ir_ui_view_model_type_priority ON ir_ui_view (priority, type, model) WHERE inherit_id IS NULL')
            else:
                self._logger.warn('The constraint \'ir_ui_view_model_type_priority\' have not been created because there is some duplicated values.')

    def remove_not_synchronized_data(self, cr, uid, *a, **b):
        '''
        The list of models to synchronize was wrong. It is now build
        automatically and is then more exact.
        This patch will remove all the data from ir_model_data that are not
        synchronized models.
        '''
        from sync_common import WHITE_LIST_MODEL
        removed_obj = 0

        # if sync_client module is installed, get the list of synchronized models
        if self.pool.get('sync.client.rule') and\
                self.pool.get('sync.client.message_rule'):
            entity_obj = self.pool.get('sync.client.entity')
            server_model_white_set = entity_obj.get_model_white_list(cr, uid)

            # check that all models from the newly generated list are in the hardcoded white list
            difference = server_model_white_set.difference(WHITE_LIST_MODEL)
            if difference:
                err_msg = 'Warning: Some models used in the synchronization '\
                    'rule are not present in the WHITE_LIST_MODEL: %s'
                self._logger.warn(err_msg)
            if server_model_white_set:
                # get list of all existing models used in ir_model_data
                cr.execute('SELECT DISTINCT(model) FROM ir_model_data')
                model_list = [x and x[0] for x in cr.fetchall()]
                model_to_remove = (set(model_list).difference(server_model_white_set))
                import pprint
                pp = pprint.PrettyPrinter(indent=2)
                model_to_remove_pp = pp.pformat(model_to_remove)
                self._logger.warn('%s models should not be part of ir_model_data.' % len(model_to_remove))
                self._logger.warn('The objects linked to the model(s) %s will be removed from ir_model_data.' % model_to_remove_pp)

                for model in model_to_remove:
                    cr.execute("DELETE FROM ir_model_data WHERE model=%s AND module='sd'", (model,))
                    current_count = cr.rowcount
                    removed_obj += current_count
                    self._logger.warn('ir.model.data, model=%s, %s objects deleted.' % (model, current_count))
                self._logger.warn('ir.model.data, total of %s objects deleted.' % removed_obj)

    def us_1613_remove_all_track_changes_action(self, cr, uid, *a, **b):
        '''
        each time the msf_audittrail is updated, the subscribe() method is
        called on all rules.
        This method create a new action for each rule (even if one already
        exists). This patch will remove all existing 'Track changes' actions
        (they will be re-created on the next msf_audittrail update and now
        there is a check to prevent to have more than one).
        '''
        obj_action = self.pool.get('ir.actions.act_window')
        if obj_action:
            search_result = obj_action.search(cr, uid,
                                              [('name', '=', 'Track changes'),
                                               ('domain', '!=', False)])
            if search_result:
                obj_action.unlink(cr, uid, search_result)
                self._logger.info('%d Track changes action deleted' % (len(search_result),))
                # call subscribe on all rule to recreate the Trach changes action
                rule_obj = self.pool.get('audittrail.rule')
                rules_ids = rule_obj.search(cr, uid, [])
                rule_obj.subscribe(cr,uid, rules_ids)

    def us_2110_patch(self, cr, uid, *a, **b):
        '''setup the size on all attachment'''
        attachment_obj = self.pool.get('ir.attachment')
        attachment_ids = attachment_obj.search(cr, uid, [])
        deleted_count = 0
        logger = logging.getLogger('update')
        for attachment in attachment_obj.browse(cr, uid, attachment_ids):
            vals = {}
            # check existance of the linked document, if the linked document
            # don't exist anymore, delete the attachement
            model_obj = self.pool.get(attachment.res_model)
            if not model_obj or not model_obj.search(cr, uid,
                                                     [('id', '=', attachment.res_id),]):
                attachment_obj.unlink(cr, uid, attachment.id)
                logger.warn('deleting attachment %s' % attachment.id)
                deleted_count += 1
                continue
            if attachment.datas:
                decoded_datas = base64.decodestring(attachment.datas)
                vals['size'] = attachment_obj.get_octet_size(decoded_datas)
                attachment_obj.write(cr, uid, attachment.id, vals)
        if deleted_count:
            logger.warn('%s attachment(s) deleted.' % deleted_count)

    def us_2068_remove_updated_linked_to_activate_instance(self, cr, uid, *a, **b):
        '''
        A button "Activate Instance" as be removed from the user interface, but
        this button had some related updates that are sent to new instance on
        the first sync and genereate not run. Remove all of this updates on the
        sync server.
        '''
        update_module = self.pool.get('sync.server.update')
        if update_module:
            # this script is exucuted on server side only
            update_to_delete_ids = update_module.search(cr, uid,
                                                        [('sdref', 'in',
                                                          ('sync_client_activate_wizard_action',
                                                           'BAR_sync_clientactivate_entity_wizard_view_activate'))])
            update_module.unlink(cr, uid, update_to_delete_ids)

    def us_2075_partner_locally_created(self, cr, uid, *a, **b):
        entity = self.pool.get('sync.client.entity')
        if entity:
            identifier = entity.get_entity(cr, uid).identifier
            if identifier:
                cr.execute("""update res_partner set locally_created='f' where id in (
                    select res_id from ir_model_data d
                    where d.module='sd'
                        and d.model='res.partner'
                        and name not in ('msf_doc_import_supplier_tbd', 'order_types_res_partner_local_market')
                        and name not like '%s%%'
                    ) """ % (identifier, ))  # not_a_user_entry
                self._logger.warn('%s non local partners updated' % (cr.rowcount,))
        return True

    def setup_security_on_sync_server(self, cr, uid, *a, **b):
        update_module = self.pool.get('sync.server.update')
        if not update_module:
            # this script is executed on server side, update the first delete
            return

        data_obj = self.pool.get('ir.model.data')
        group_id = data_obj.get_object_reference(cr, uid, 'base',
                                                 'group_erp_manager')[1]

        model_obj = self.pool.get('ir.model')
        model_list_not_to_change = ['res.users', 'res.lang', 'res.widget',
                                    'res.widget.user', 'res.log', 'publisher_warranty.contract',
                                    'module.module']
        model_ids = model_obj.search(cr, uid,
                                     [('model', 'not like', "ir%"),
                                      ('model', 'not in', model_list_not_to_change)])

        access_obj = self.pool.get('ir.model.access')
        no_group_access = access_obj.search(cr, uid, [('group_id', '=', False),
                                                      ('model_id', 'in', model_ids)])
        access_obj.write(cr, uid, no_group_access, {'group_id': group_id})

    def us_1482_fix_default_code_on_msf_lines(self, cr, uid, *a, **b):
        """
        If the default code set on the MSR lines is different from the
        default_code set on the related product_id, it means that the MSR lines
        should be updated.
        The call of write on them do the job.
        """

        request = """
        UPDATE stock_mission_report_line
        SET default_code=subquerry.pp_code
        FROM
            (SELECT msrl.id AS msrl_id, msrl.default_code AS msrl_code,
             pp.default_code AS pp_code FROM stock_mission_report_line AS msrl
             JOIN product_product AS pp ON pp.id = msrl.product_id
             WHERE
                msrl.default_code != pp.default_code
            ) AS subquerry
        WHERE
            stock_mission_report_line.id = msrl_id
        """
        cr.execute(request)

    def us_1381_encrypt_passwords(self, cr, uid, *a, **b):
        """
        encrypt all passwords
        """
        from passlib.hash import bcrypt
        users_obj = self.pool.get('res.users')
        user_ids = users_obj.search(cr, uid, [('active', 'in', ('t', 'f'))])
        for user in users_obj.read(cr, uid, user_ids, ['password']):
            original_password = tools.ustr(user['password'])
            # check the password is not already encrypted
            if not bcrypt.identify(original_password):
                encrypted_password = bcrypt.encrypt(original_password)
                users_obj.write(cr, uid, user['id'],
                                {'password': encrypted_password})

    def us_1610_set_oc_on_all_groups(self, cr, uid, *a, **b):
        from sync_common import OC_LIST
        lower_oc_list = [x.lower() for x in OC_LIST]
        logger = logging.getLogger('update')
        update_module = self.pool.get('sync.server.entity_group')
        if update_module:
            # get all groups that don't have any oc
            group_ids = update_module.search(cr, uid,
                                             [('oc', '=', False)])
            for group in update_module.read(cr, uid, group_ids, ['name']):
                group_name = group['name'].lower()
                if 'oc' in group_name:
                    index = group_name.index('oc')
                    oc = group_name[index:index+3]
                    if oc in lower_oc_list:
                        update_module.write(cr, uid, group['id'], {'oc': oc})
                    else:
                        logger.warn("""OC = %s from group '%s' is not in the OC_LIST, please fix
                                manually""" % (oc, group['name']))
                else:
                    logger.warn('sync.server.entity_group "%s" does not contain '\
                                '"oc" or "OC" in its name. Please set up the '\
                                'oc manually' % group['name'])

        sync_client_module = self.pool.get('sync.client.entity')
        if sync_client_module:
            # get all entities that don't have any oc
            entity_ids = sync_client_module.search(cr, uid,
                                                   [('oc', '=', False)])
            for entity in sync_client_module.read(cr, uid, entity_ids,
                                                  ['name']):
                entity_name = entity['name'].lower()
                if 'oc' in entity_name:
                    index = entity_name.index('oc')
                    oc = entity_name[index:index+3]
                    if oc in lower_oc_list:
                        sync_client_module.write(cr, uid, entity['id'], {'oc': oc})
                    else:
                        logger.warn("""OC = %s from group '%s' is not in the OC_LIST, please fix
                                manually""" % (oc, group['name']))
                else:
                    logger.warn('sync.client.entity "%s" does not contain '\
                                '"oc" or "OC" in its name. Please set up the '\
                                'oc manually' % entity['name'])

    def us_1725_force_sync_on_hr_employee(self, cr, uid, *a, **b):
        '''
        force sync on all local employee
        '''

        if _get_instance_level(self, cr, uid) == 'coordo':

            # get all local employee
            hr_employee_obj = self.pool.get('hr.employee')
            local_employee_ids = hr_employee_obj.search(cr, uid,
                                                        [('employee_type', '=', 'local'),
                                                         ('name','!=','Administrator')])

            total_employee = len(local_employee_ids)
            start_chunk = 0
            chunk_size = 100
            while start_chunk < total_employee:
                ids_chunk = local_employee_ids[start_chunk:start_chunk+chunk_size]
                cr.execute("""UPDATE
                    ir_model_data SET last_modification=NOW(), touched='[''code'']'
                WHERE
                    module='sd' AND model='hr.employee' AND res_id in %s""",
                           (tuple(ids_chunk),))
                start_chunk += chunk_size

    def us_1388_change_sequence_implementation(self, cr, uid, *a, **b):
        """
        change the implementation of the finance.ocb.export ir_sequence to be
        psql (instead of no_gap
        """
        seq_obj = self.pool.get('ir.sequence')
        # get the ir_sequence id
        seq_id_list = seq_obj.search(cr, uid,
                                     [('code', '=', 'finance.ocb.export')])
        if seq_id_list:
            seq_obj.write(cr, uid, seq_id_list, {'implementation': 'psql'})


    def us_1421_lower_login(self, cr, uid, *a, **b):
        user_obj = self.pool.get('res.users')
        logger = logging.getLogger('update login')
        cr.execute('select id, login from res_users')
        for d in cr.fetchall():
            lower_login = tools.ustr(d[1]).lower()
            if tools.ustr(d[1]) == lower_login:
                continue
            if user_obj.search(cr, uid, [('login', '=', lower_login), ('active', 'in', ['t', 'f'])]):
                logger.warn('Login of user id %s not changed because of duplicates' % (d[0], ))
            else:
                cr.execute('update res_users set login=%s where id=%s', (lower_login, d[0]))
        return True

    def us_993_patch(self, cr, uid, *a, **b):
        # set no_update to True on USB group_type not to delete it on
        # existing instances
        cr.execute("""
        UPDATE ir_model_data SET noupdate='t'
        WHERE model='sync.server.group_type' AND
        name='sync_remote_warehouse_rule_group_type'
        """)

    # XXX do not remove this patch !!! XXX
    def us_1030_create_pricelist_patch(self, cr, uid, *a, **b):
        '''
        Find currencies without associated pricelist and create this price list
        '''
        currency_module = self.pool.get('res.currency')
        # Find currencies without associated pricelist
        cr.execute("""SELECT id FROM res_currency
                   WHERE id NOT IN (SELECT currency_id FROM product_pricelist)
                   AND currency_table_id IS NULL""")
        curr_ids = cr.fetchall()
        for cur_id in curr_ids:
            currency_module.create_associated_pricelist(cr, uid, cur_id[0])

    def us_918_patch(self, cr, uid, *a, **b):
        update_module = self.pool.get('sync.server.update')
        if update_module:
            # if this script is exucuted on server side, update the first delete
            # update of ZMK to be executed before the creation of ZMW (sequence
            # 4875). Then if ZMK is correctly deleted, ZMW can be added
            cr.execute("UPDATE sync_server_update "
                       "SET sequence=4874 "
                       "WHERE id=2222677")

            # change sdref ZMW to base_ZMW
            cr.execute("UPDATE sync_server_update "
                       "SET sdref='base_ZMW' "
                       "WHERE model='res.currency' AND sdref='ZMW'")

            # remove the ZMK creation update
            cr.execute("DELETE FROM sync_server_update WHERE id=52325;")
            cr.commit()

            # some update where refering to the old currency with sdref=sd.ZMW
            # as the reference changed, we need to modify all of this updates
            # pointing to a wrong reference (currency_rates, ...)
            updates_to_modify = update_module.search(
                cr, uid, [('values', 'like', '%sd.ZMW%')],)
            for update in update_module.browse(cr, uid, updates_to_modify):
                update_values = eval(update.values)
                if 'sd.ZMW' in update_values:
                    index = update_values.index('sd.ZMW')
                    update_values[index] = 'sd.base_ZMW'
                vals = {'values': update_values,}
                update_module.write(cr, uid, update.id, vals)

            # do the same for sdref=sd.base_ZMK
            updates_to_modify = update_module.search(
                cr, uid, [('values', 'like', '%sd.base_ZMK%')],)
            for update in update_module.browse(cr, uid, updates_to_modify):
                update_values = eval(update.values)
                if 'sd.base_ZMK' in update_values:
                    index = update_values.index('sd.base_ZMK')
                    update_values[index] = 'sd.base_ZMW'
                vals = {'values': update_values,}
                update_module.write(cr, uid, update.id, vals)
        else:
            # change the sdref on the client that use the wrong ZMK
            cr.execute("""UPDATE ir_model_data
            SET name='ZMW' WHERE name='ZMK'""")

            cr.execute("""UPDATE ir_model_data
            SET name='base_ZMW' WHERE name='base_ZMK'""")
            cr.commit()

            # check if the currency related to sd.base_ZMW exist, if not,
            # delete the ir_model_data base_ZMW entry and change the ZMW entry to base_ZMW
            cr.execute("""SELECT res_id FROM ir_model_data
            WHERE module='sd' and name='base_ZMW'""")
            res_id = cr.fetchone()
            if res_id and res_id[0]:
                cr.execute("""SELECT id FROM res_currency
                WHERE id=%s""", (res_id[0], ))
                currency_exists = cr.fetchone()
                if not currency_exists:
                    # delete the entry
                    cr.execute("""DELETE FROM ir_model_data
                    WHERE module='sd' AND name='base_ZMW'""")
                    cr.commit()

            # modify the ZMW to base_ZMW
            cr.execute("""UPDATE ir_model_data SET name='base_ZMW'
            WHERE module='sd' AND name='ZMW'""")

            # check if some updates with wrong sdref were ready to be sent and if yes, fix them
            update_module = self.pool.get('sync.client.update_to_send')
            if update_module:
                # change sdref ZMW to base_ZMW
                cr.execute("UPDATE sync_client_update_to_send "
                           "SET sdref='base_ZMW' "
                           "WHERE sdref='base_ZMK'")
                cr.execute("UPDATE sync_client_update_to_send "
                           "SET sdref='ZMW' "
                           "WHERE sdref='ZMK'")

    def us_898_patch(self, cr, uid, *a, **b):
        context = {}
        # remove period state from upper levels as an instance should be able
        # to see only the children account.period.state's
        period_state_obj = self.pool.get('account.period.state')
        period_obj = self.pool.get('account.period')
        msf_instance_obj = self.pool.get('msf.instance')

        # get the current instance id
        instance_ids = []
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id and user.company_id.instance_id:
            instance_ids = [user.company_id.instance_id.id]

        # get all the children of this instance
        children_ids = msf_instance_obj.get_child_ids(cr, uid)

        # remove period_state that are not concerning current instance or his
        # children
        period_state_ids = []
        period_state_ids = period_state_obj.search(cr, uid,
                                                   [('instance_id', 'not in', children_ids + instance_ids)])
        if period_state_ids:
            period_state_obj.unlink(cr, uid, period_state_ids)

        # delete ir.model.data related to deleted account.period.state
        model_data = self.pool.get('ir.model.data')
        ids_to_delete = []
        for period_state_id in period_state_ids:
            period_state_xml_id = period_state_obj.get_sd_ref(cr, uid, period_state_id)
            ids_to_delete.append(model_data._get_id(cr, uid, 'sd',
                                                    period_state_xml_id))
        model_data.unlink(cr, uid, ids_to_delete)

        # touch all ir.model.data object related to the curent
        # instance periods
        # this permit to fix incorrect period state on upper level
        # by re-sending state and create the missing period_states
        period_ids = period_obj.search(cr, uid, [('active', 'in', ('t', 'f'))])
        period_state_obj.update_state(cr, uid, period_ids)

    def sync_down_msfid(self, cr, uid, *a, **b):
        context = {}
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid], context=context)[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level

        if level_current == 'section':
            data_obj = self.pool.get('ir.model.data')
            unidata_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]
            # TEST ONLY
            #cr.execute('update product_product set msfid=id')

            # on prod: only UniData product
            cr.execute("""update ir_model_data set touched='[''msfid'']',
                last_modification=now()
                where module='sd' and model='product.product' and
                res_id in (
                    select id from product_product where international_status = %s and coalesce(msfid,0) != 0
                )""", (unidata_id, ))
        return True

    def us_332_patch(self, cr, uid, *a, **b):
        context = {}
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid], context=context)[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level

        if level_current == 'section':
            # create MSFID for product.nomenclature
            nomen_obj = self.pool.get('product.nomenclature')
            nomen_ids = nomen_obj.search(cr, uid, [('msfid', '=', False)], order='level asc, id')

            for nomen_id in nomen_ids:
                nomen = nomen_obj.browse(cr, uid, nomen_id, context={})
                msfid = ""
                if not nomen.msfid:
                    nomen_parent = nomen.parent_id
                    if nomen_parent and nomen_parent.msfid:
                        msfid = nomen_parent.msfid + "-"
                    name_first_word = nomen.name.split(' ')[0]
                    msfid += name_first_word
                    # Search same msfid
                    ids = nomen_obj.search(cr, uid, [('msfid', '=', msfid)])
                    if ids:
                        msfid += str(nomen.id)
                    nomen_obj.write(cr, uid, nomen.id, {'msfid': msfid})

            # create MSFID for product.category
            categ_obj = self.pool.get('product.category')
            categ_ids = categ_obj.search(cr, uid, [('msfid', '=', False), ('family_id', '!=', False)], order='id')

            for categ in categ_obj.browse(cr, uid, categ_ids, context={}):
                msfid = ""
                if not categ.msfid and categ.family_id and categ.family_id.name:
                    msfid = categ.family_id.name[0:4]
                    ids = categ_obj.search(cr, uid, [('msfid', '=', msfid)])
                    if ids:
                        msfid += str(categ.id)
                    categ_obj.write(cr, uid, categ.id, {'msfid': msfid})

    def update_parent_budget_us_489(self, cr, uid, *a, **b):
        logger = logging.getLogger('update')
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        instance_name = c and c.instance_id and c.instance_id.name
        if instance_name == 'BD_DHK_OCA':
            budget_obj = self.pool.get('msf.budget')
            parent_id = budget_obj.search(cr, uid, [('type', '=', 'view'), ('id', '=', 2)])
            child_id = budget_obj.search(cr, uid, [('type', '=', 'normal'), ('id', '=', 4)])
            if not parent_id or not child_id:
                logger.warn('US-489: budget not found, parent: %s, child: %s' % (parent_id, child_id))
                return False
            budget_obj.write(cr, uid, parent_id, {'state': 'draft'})
            budget_obj.unlink(cr, uid, parent_id)
            fields = ['cost_center_id', 'fiscalyear_id', 'decision_moment_id']
            data = budget_obj.read(cr, uid, child_id[0], fields)
            vals = {}
            for f in fields:
                vals[f] = data[f] and data[f][0]
            budget_obj._check_parent(cr, uid, vals)
            budget_obj.update_parent_budgets(cr, uid, child_id)
            logger.warn('US-489: parent budget %s updated' % (parent_id,))

    def us_394_2_patch(self, cr, uid, *a, **b):
        obj = self.pool.get('ir.translation')
        obj.clean_translation(cr, uid, context={})
        obj.add_xml_ids(cr, uid, context={})

    def us_394_3_patch(self, cr, uid, *a, **b):
        self.us_394_2_patch(cr, uid, *a, **b)

    def update_us_435_2(self, cr, uid, *a, **b):
        period_obj = self.pool.get('account.period')
        period_state_obj = self.pool.get('account.period.state')
        periods = period_obj.search(cr, uid, [])
        for period in periods:
            period_state_obj.update_state(cr, uid, period)

        return True

    def update_us_133(self, cr, uid, *a, **b):
        p_obj = self.pool.get('res.partner')
        po_obj = self.pool.get('purchase.order')
        pl_obj = self.pool.get('product.pricelist')

        # Take good pricelist on existing partners
        p_ids = p_obj.search(cr, uid, [])
        fields = [
            'property_product_pricelist_purchase',
            'property_product_pricelist',
        ]
        for p in p_obj.read(cr, uid, p_ids, fields):
            p_obj.write(cr, uid, [p['id']], {
                'property_product_pricelist_purchase': p['property_product_pricelist_purchase'][0],
                'property_product_pricelist': p['property_product_pricelist'][0],
            })

        # Take good pricelist on existing POs
        pl_dict = {}
        po_ids = po_obj.search(cr, uid, [
            ('pricelist_id.type', '=', 'sale'),
        ])
        for po in po_obj.read(cr, uid, po_ids, ['pricelist_id']):
            vals = {}
            if po['pricelist_id'][0] in pl_dict:
                vals['pricelist_id'] = pl_dict[po['pricelist_id'][0]]
            else:
                pl_currency = pl_obj.read(cr, uid, po['pricelist_id'][0], ['currency_id'])
                p_pl_ids = pl_obj.search(cr, uid, [
                    ('currency_id', '=', pl_currency['currency_id'][0]),
                    ('type', '=', 'purchase'),
                ])
                if p_pl_ids:
                    pl_dict[po['pricelist_id'][0]] = p_pl_ids[0]
                    vals['pricelist_id'] = p_pl_ids[0]

            if vals:
                po_obj.write(cr, uid, [po['id']], vals)

    def us_822_patch(self, cr, uid, *a, **b):
        fy_obj = self.pool.get('account.fiscalyear')
        level = self.pool.get('res.users').browse(cr, uid,
                                                  [uid])[0].company_id.instance_id.level

        # create FY15 /FY16 'system' periods (number 0 and 16)
        if level == 'section':
            fy_ids = self.pool.get('account.fiscalyear').search(cr, uid, [
                ('date_start', 'in', ('2015-01-01', '2016-01-01', ))
            ])
            if fy_ids:
                for fy_rec in fy_obj.browse(cr, uid, fy_ids):
                    year = int(fy_rec['date_start'][0:4])
                    periods_to_create = [16, ]
                    if year != 2015:
                        # for FY15 period 0 not needed as no initial balance for
                        # the first FY of UF start
                        periods_to_create.insert(0, 0)

                    self.pool.get('account.year.end.closing').create_periods(cr,
                                                                             uid, fy_rec.id, periods_to_create=periods_to_create)

        # update fiscal year state (new model behaviour-like period state)
        fy_ids = self.pool.get('account.fiscalyear').search(cr, uid, [])
        if fy_ids:
            self.pool.get('account.fiscalyear.state').update_state(cr, uid,
                                                                   fy_ids)

        return True

    def us_908_patch(self, cr, uid, *a, **b):
        # add the version to unifield-version.txt as the code which
        # automatically add this version name is contained in the patch itself.
        from updater import re_version
        from tools import config
        file_path = os.path.join(config['root_path'], 'unifield-version.txt')
        # get the last known patch line
        # 16679c0321623dd7e13fdd5fad6f677c 2015-12-22 14:30:00 UF2.0-0p1
        with open(file_path, 'r') as f:
            lines = f.readlines()
        #if last_version don't have any name
        # and the previous is UF2.0-0p1
        last_line = lines[-1]
        last_line = last_line.rstrip()
        if not last_line: #  the last is an empty line, no new patch was installed
            return True
        result = re_version.findall(last_line)
        md5sum, date, version_name = result[0]
        if not version_name:
            # check that the previous patch was UF2.1
            previous_line = lines[-2].rstrip() or lines[-3].rstrip() #  may be
            # there is a blank line between
            previous_line_res = re_version.findall(previous_line)
            p_md5sum, p_date, p_version_name = previous_line_res[0]
            if p_md5sum == '16679c0321623dd7e13fdd5fad6f677c':
                last_line = '%s %s %s' % (md5sum, date, 'UF2.1-0') + os.linesep
                lines[-1] = last_line
                with open(file_path, 'w') as file:
                    file.writelines(lines)

    def uftp_144_patch(self, cr, uid, *a, **b):
        """
        Sorting Fix in AJI: ref and partner_txt mustn't be empty strings
        """
        cr.execute("UPDATE account_analytic_line SET ref=NULL WHERE ref='';")
        cr.execute("UPDATE account_analytic_line SET partner_txt=NULL WHERE partner_txt='';")

    def disable_crondoall(self, cr, uid, *a, **b):
        cron_obj = self.pool.get('ir.cron')
        cron_ids = cron_obj.search(cr, uid, [('doall', '=', True), ('active', 'in', ['t', 'f'])])
        if cron_ids:
            cron_obj.write(cr, uid, cron_ids, {'doall': False})

    def bar_action_patch(self, cr, uid, *a, **b):
        rules_obj = self.pool.get('msf_button_access_rights.button_access_rule')
        data_obj = self.pool.get('ir.model.data')
        view_obj = self.pool.get('ir.ui.view')
        rule_ids = rules_obj.search(cr, uid, [('xmlname', '=', False), ('type', '=', 'action'), ('view_id', '!=', False), ('active', 'in', ['t', 'f'])])
        view_to_gen = {}
        for rule in rules_obj.read(cr, uid, rule_ids, ['view_id']):
            view_to_gen[rule['view_id'][0]] = True
            rules_obj.unlink(cr, uid, rule['id'])
            d_ids = data_obj.search(cr, uid, [
                ('module', '=', 'sd'),
                ('model', '=', 'msf_button_access_rights.button_access_rule'),
                ('res_id', '=', rule['id'])
            ])
            if d_ids:
                data_obj.unlink(cr, uid, d_ids)
        for view in view_to_gen:
            view_obj.generate_button_access_rules(cr, uid, view)

    def us_1024_send_bar_patch(self, cr, uid, *a, **b):
        context = {}
        user_obj = self.pool.get('res.users')
        ir_ui_obj = self.pool.get('ir.ui.view')
        data_obj = self.pool.get('ir.model.data')
        rules_obj = self.pool.get('msf_button_access_rights.button_access_rule')

        usr = user_obj.browse(cr, uid, [uid], context=context)[0]

        rule_ids = rules_obj.search(cr, uid, [('xmlname', '=', False), ('type', '=', 'action'), ('view_id', '!=', False), ('active', 'in', ['t', 'f'])])
        if rule_ids:
            data_ids = data_obj.search(cr, uid, [
                ('module', '=', 'sd'),
                ('model', '=', 'msf_button_access_rights.button_access_rule'),
                ('res_id', 'in', rule_ids)
            ])
            if rule_ids:
                data_obj.unlink(cr, uid, data_ids)
            for rule in rules_obj.read(cr, uid, rule_ids, ['type', 'name']):
                xmlname = ir_ui_obj._get_xmlname(cr, uid, rule['type'], rule['name'])
                rules_obj.write(cr, uid, rule['id'], {'xmlname': xmlname})

        if usr and usr.company_id and usr.company_id.instance_id and usr.company_id.instance_id.level == 'section':
            cr.execute('''update ir_model_data
                set touched='[''active'']', last_modification=NOW()
                where module='sd' and model='msf_button_access_rights.button_access_rule'
            ''')


    def us_750_patch(self, cr, uid, *a, **b):
        """
        Update the heat_sensitive_item field of product.product
        to 'Yes' if there is a value already defined by de-activated.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param a: Non-named parameters
        :param b: Named parameters
        :return: True
        """
        prd_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')

        heat_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'heat_yes')[1]
        no_heat_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'heat_no')[1]

        prd_ids = prd_obj.search(cr, uid, [('heat_sensitive_item', '!=', False), ('active', 'in', ['t', 'f'])])
        if prd_ids:
            cr.execute("""
                UPDATE product_product SET heat_sensitive_item = %s, is_kc = True, kc_txt = 'X', show_cold_chain = True WHERE id IN %s
            """, (heat_id, tuple(prd_ids),))

        no_prd_ids = prd_obj.search(cr, uid, [('heat_sensitive_item', '=', False), ('active', 'in', ['t', 'f'])])
        if no_prd_ids:
            cr.execute("""
                UPDATE product_product SET heat_sensitive_item = %s, is_kc = False, kc_txt = '', show_cold_chain = False WHERE id IN %s
            """, (no_heat_id, tuple(no_prd_ids),))

        cr.execute('ALTER TABLE product_product ALTER COLUMN heat_sensitive_item SET NOT NULL')

        return True

    def update_us_963_negative_rule_seq(self, cr, uid, *a, **b):
        if self.pool.get('sync.client.update_received'):
            cr.execute("update sync_client_update_received set rule_sequence=-rule_sequence where is_deleted='t'")

    def another_translation_fix(self, cr, uid, *a, **b):
        if self.pool.get('sync.client.update_received'):
            ir_trans = self.pool.get('ir.translation')
            cr.execute('''select id, xml_id, name from ir_translation where
                xml_id is not null and
                res_id is null and
                type='model'
            ''')
            for x in cr.fetchall():
                res_id = ir_trans._get_res_id(cr, uid, name=x[2], sdref=x[1])
                if res_id:
                    cr.execute('update ir_translation set res_id=%s where id=%s', (res_id, x[0]))
        return True

    def another_other_translation_fix_bis(self, cr, uid, *a, **b):
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        instance_name = c and c.instance_id and c.instance_id.name or ''
        logger = logging.getLogger('update')
        if instance_name.startswith('OCG'):
            logger.warn('Execute US-1527 script')
            self.another_other_translation_fix(cr, uid, *a, **b)
        else:
            logger.info('Do not execute US-1527 script')
        return True

    def another_other_translation_fix(self, cr, uid, *a, **b):
        cr.execute('''
            DELETE FROM ir_model_data WHERE model = 'ir.translation'
            AND res_id IN (SELECT id FROM ir_translation WHERE res_id = 0 AND name = 'product.template,name')
        ''')
        cr.execute('''
            DELETE FROM ir_translation WHERE res_id = 0 AND name = 'product.template,name'
        ''')
        return True

    def clean_far_updates(self, cr, uid, *a, **b):
        '''
        US-1148: is_keep_cool has been removed on product
        delete FAR line update related to this old fields
        '''
        if self.pool.get('sync.server.update'):
            cr.execute("delete from sync_server_update where values like '%msf_outgoing.field_product_product_is_keep_cool%' and model='msf_field_access_rights.field_access_rule_line'")

    def us_1185_patch(self, cr, uid, *a, **b):
        # AT HQ level: untick 8/9 top accounts for display in BS/PL report
        user_rec = self.pool.get('res.users').browse(cr, uid, [uid])[0]
        if user_rec.company_id and user_rec.company_id.instance_id \
                and user_rec.company_id.instance_id.level == 'section':
            account_obj = self.pool.get('account.account')
            codes = ['8', '9', ]

            ids = account_obj.search(cr, uid, [
                ('type', '=', 'view'),
                ('code', 'in', codes),
            ])
            if ids and len(ids) == len(codes):
                account_obj.write(cr, uid, ids, {
                    'display_in_reports': False,
                })

    def us_1263_patch(self, cr, uid, *a, **b):
        ms_obj = self.pool.get('stock.mission.report')

        ms_touched = "['name']"
        msl_touched = "['internal_qty']"

        ms_ids = ms_obj.search(cr, uid, [('local_report', '=', True)])
        if not ms_ids:
            return True

        # Touched Mission stock reports
        cr.execute('''UPDATE ir_model_data
                      SET touched = %s, last_modification = now()
                      WHERE model =  'stock.mission.report' AND res_id in %s''', (ms_touched, tuple(ms_ids),))
        # Touched Mission stock report lines
        cr.execute('''UPDATE ir_model_data
                      SET touched = %s, last_modification = now()
                      WHERE
                          model = 'stock.mission.report.line'
                          AND
                          res_id IN (SELECT l.id
                                     FROM stock_mission_report_line l
                                     WHERE
                                       l.mission_report_id IN %s
                                       AND (l.internal_qty != 0.00
                                       OR l.stock_qty != 0.00
                                       OR l.central_qty != 0.00
                                       OR l.cross_qty != 0.00
                                       OR l.secondary_qty != 0.00
                                       OR l.cu_qty != 0.00
                                       OR l.in_pipe_qty != 0.00
                                       OR l.in_pipe_coor_qty != 0.00))''', (msl_touched, tuple(ms_ids)))
        return True

    def us_1273_patch(self, cr, uid, *a, **b):
        # Put all internal requests import_in_progress field to False
        ir_obj = self.pool.get('sale.order')
        context = {'procurement_request': True}
        ir_ids = ir_obj.search(cr, uid, [('import_in_progress', '=', True)], context=context)
        if ir_ids:
            ir_obj.write(cr, uid, ir_ids, {'import_in_progress': False})
        return True

    def us_1297_patch(self, cr, uid, *a, **b):
        """
        Correct budgets with View Type Cost Center (consolidation)
        """
        budget_obj = self.pool.get('msf.budget')
        # apply the patch only if there are budgets on several fiscal years
        sql_count_fy = "SELECT COUNT(DISTINCT(fiscalyear_id)) FROM msf_budget;"
        cr.execute(sql_count_fy)
        count_fy = cr.fetchone()[0]
        if count_fy > 1:
            # get only budgets already validated
            sql_budgets = "SELECT id FROM msf_budget WHERE type != 'view' AND state != 'draft';"
            cr.execute(sql_budgets)
            budgets = cr.fetchall()
            if budgets:
                budget_to_correct_ids = [x and x[0] for x in budgets]
                # update the parent budgets
                budget_obj.update_parent_budgets(cr, uid, budget_to_correct_ids)
        return True

    def us_1427_patch(self, cr, uid, *a, **b):
        """
        Put active all inactive products with stock quantities in internal locations
        """
        sql = """
        UPDATE product_product SET active = 't' WHERE id IN (
            SELECT DISTINCT(q.product_id) FROM (
            SELECT location_id, product_id, sum(sm.product_qty) AS qty
                FROM (
                    (
                        SELECT location_id, product_id, sum(-product_qty) AS product_qty
                        FROM stock_move
                        WHERE location_id IN (SELECT id FROM stock_location WHERE usage = 'internal') AND state = 'done'
                        GROUP BY location_id, product_id
                    )
                    UNION
                    (
                        SELECT location_dest_id, product_id, sum(product_qty) AS product_qty
                        FROM stock_move
                        WHERE location_dest_id IN (SELECT id FROM stock_location WHERE usage = 'internal') AND state = 'done'
                        GROUP BY location_dest_id, product_id
                    )
                ) AS sm GROUP BY location_id, product_id) AS q
            LEFT JOIN product_product pp ON q.product_id = pp.id WHERE q.qty > 0 AND pp.active = 'f' ORDER BY q.product_id)
        """
        cr.execute(sql)
        return True

    def us_1452_patch_bis(self, cr, uid, *a, **b):
        """
        Put 1.00 as cost price for all product with cost price = 0.00
        """
        setup_obj = self.pool.get('unifield.setup.configuration')
        setup_br = setup_obj.get_config(cr, uid)
        sale_percent = 1.00
        if setup_br:
            sale_percent = 1 + (setup_br.sale_price/100.00)


        sql = """UPDATE product_template SET standard_price = 1.00, list_price = %s WHERE standard_price = 0.00 RETURNING id"""
        cr.execute(sql, (sale_percent, ))


        prod_templ_ids = [x[0] for x in cr.fetchall()]
        if prod_templ_ids:
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            p_ids = self.pool.get('product.product').search(cr, uid, [('product_tmpl_id', 'in', prod_templ_ids)])
            for p_id in p_ids:
                cr.execute("""insert into standard_price_track_changes (create_uid, create_date, new_standard_price, user_id, product_id, change_date, transaction_name, old_standard_price) VALUES
                        (1, NOW(), 1, 1, %s, %s, 'Product price reset 1', 0)
                """, (p_id, now))
            cr.execute('update product_product set uf_write_date=%s where id in %s', (now, tuple(p_ids)))
        return True

    def us_1430_patch(self, cr, uid, *a, **b):
        """
        Resync. all ir.translation related to product.template,name of Local products
        """
        context = {}
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid], context=context)[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level

        if level_current == 'coordo':
            cr.execute("""
                UPDATE ir_model_data
                    SET touched = '[''src'']', last_modification = now()
                    WHERE model = 'ir.translation' AND res_id IN (
                        SELECT t.id FROM ir_translation t
                            LEFT JOIN product_template pt ON pt.id = t.res_id
                            LEFT JOIN product_product pp ON pp.product_tmpl_id = pt.id
                            LEFT JOIN product_international_status s ON s.id = pp.international_status
                            LEFT JOIN ir_model_data d ON d.res_id = s.id
                        WHERE
                            t.name = 'product.template,name'
                          AND
                            d.model = 'product.international.status'
                          AND
                            d.name = 'int_4'
                          AND
                            d.module = 'product_attributes')""")

        return True

    def us_trans_admin_fr(self, cr, uid, *a, **b):
        """
        replay fr_MF translations for instances were sync has been run with French admin user
        """
        context = {}
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid], context=context)[0]
        instance_name = False
        instance_id = False
        top_level = False
        coordo_id = False
        if usr and usr.company_id and usr.company_id.instance_id:
            instance_name = usr.company_id.instance_id.instance
            instance_id = usr.company_id.instance_id.instance_identifier
            if usr.company_id.instance_id.parent_id:
                if usr.company_id.instance_id.parent_id.parent_id:
                    coordo_id = usr.company_id.instance_id.parent_id.instance_identifier
                    top_level = usr.company_id.instance_id.parent_id.parent_id.instance
                else:
                    top_level = usr.company_id.instance_id.parent_id.instance

        if instance_name in ('OCG_CM1_COO', 'OCG_CM1_KSR',
                             'OCG_CM1_MRA', 'OCBHT118', 'OCBHT143', 'OCBHT101'):
            self._logger.warn('Replay fr_MF updates')
            cr.execute("""delete from ir_model_data where model='ir.translation' and module='sd'
                and res_id in (select id from ir_translation where res_id=0 and name='product.template,name')
            """);
            cr.execute("delete from ir_translation where res_id=0 and name='product.template,name'");
            if top_level:
                cr.execute("""update sync_client_update_received set run='f' where id in
                    (select max(id) from sync_client_update_received where model='ir.translation' and source=%s group by sdref)
                """, (top_level, ))

            else:
                cr.execute("""update sync_client_update_received set run='f' where id in
                    (select max(id) from sync_client_update_received where sdref in
                            (select d.name from ir_model_data d where d.module='sd' and d.model='ir.translation' and d.res_id in
                                (select t.id from ir_translation t, product_template p where t.name='product.template,name' and t.res_id=p.id and lang='fr_MF')
                            ) group by sdref
                        )
                """)

            if instance_id:
                # delete en_MF translations created on instance for UniData products
                # sync down deletion
                cr.execute("""update ir_model_data set last_modification=NOW() where module='sd' and model='ir.translation' and res_id in (
                    select id from ir_translation t where t.lang in ('en_MF', 'fr_MF') and name='product.template,name' and res_id in
                    (select t.id from product_template t, product_product p where p.product_tmpl_id = t.id and international_status=6)
                    and name like '%s%%'
                )""" % instance_id)  # not_a_user_entry
                cr.execute("""delete from ir_translation t
                    where t.lang in ('en_MF', 'fr_MF') and name='product.template,name' and res_id in
                        (select t.id from product_template t, product_product p where p.product_tmpl_id = t.id and international_status=6)
                    and id in
                        (select d.res_id from ir_model_data d where d.module='sd' and d.model='ir.translation' and name like '%s%%')
                """ % instance_id)  # not_a_user_entry
                if coordo_id and instance_name in ('OCBHT118', 'OCBHT143'):
                    # also remove old UniData trans sent by coordo
                    cr.execute("""delete from ir_translation t
                        where t.lang in ('en_MF', 'fr_MF') and name='product.template,name' and res_id in
                            (select t.id from product_template t, product_product p where p.product_tmpl_id = t.id and international_status=6)
                        and id in
                            (select d.res_id from ir_model_data d where d.module='sd' and d.model='ir.translation' and name like '%s%%')
                    """ % coordo_id)  # not_a_user_entry

                self._logger.warn('%s local translation for UniData products deleted' % (cr.rowcount,))

    def us_1732_sync_state_ud(self, cr, uid, *a, **b):
        """
        Make the product.product with state_ud is not null as to be synchronized at HQ
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param a: Named parameters
        :param b: Unnamed parameters
        :return:
        """
        if _get_instance_level(self, cr, uid) == 'hq':
            cr.execute("""
                UPDATE ir_model_data SET last_modification = NOW(), touched = '[''state_ud'']'
                WHERE
                    module = 'sd'
                AND
                    model = 'product.product'
                AND
                    res_id IN (
                        SELECT id FROM product_product WHERE state_ud IS NOT NULL
            )""")

    def us_1766_fix_fxa_aji_curr(self, cr, uid, *a, **b):
        """
        Fix FXA AJIs:
            - set book currency = fct currency
            - set book amount = fct amount
        """
        context = {}
        logger = logging.getLogger('fix_us_1766')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        currency_id = user.company_id.currency_id and user.company_id.currency_id.id or False

        if currency_id:
            journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'cur_adj'), ('active', 'in', ['t', 'f'])])
            if journal_ids:
                cr.execute("""select entry_sequence from account_analytic_line
                    where journal_id in %s and
                    currency_id != %s """, (tuple(journal_ids), currency_id))
                all_seq = [x[0] for x in cr.fetchall()]
                logger.warn('Fix %d FXA AJIs: %s' % (len(all_seq), ','.join(all_seq)))
                cr.execute("""update account_analytic_line set
                    currency_id = %s,
                    amount = amount_currency
                    where journal_id in %s and
                    currency_id != %s""", (currency_id, tuple(journal_ids), currency_id))


    def us_635_dest_partner_ids(self, cr, uid, *a, **b):
        """
        Fill many2many field dest_partner_ids
        """
        context = {}
        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')

        po_ids = po_obj.search(cr, uid, [], context=context)
        for po_id in po_ids:
            so_ids = po_obj.get_so_ids_from_po_ids(cr, uid, po_id, context=context)
            for so in so_obj.browse(cr, uid, so_ids, context=context):
                if not so.procurement_request:
                    po_obj.write(cr, uid, po_id, {
                        'dest_partner_ids': [(4, so.partner_id.id)],
                    }, context=context)

        return True

    def us_1671_stopped_products(self, cr, uid, *a, **b):
        '''
        Fill field product_state of object stock.mission.report.line with the state of the products (product.product)
        '''
        prod_obj = self.pool.get('product.product')
        smrl_obj = self.pool.get('stock.mission.report.line')
        context = {}

        prod_ids = prod_obj.search(cr, uid, [('state', '!=', False), ('active', 'in', ['t', 'f'])], context=context)
        smrl_to_modify = smrl_obj.search(cr, uid, [('product_id', 'in', prod_ids), ('mission_report_id.local_report', '=', True)], context=context)

        for smrl in smrl_obj.browse(cr, uid, smrl_to_modify, context=context):
            smrl_obj.write(cr, uid, smrl.id, {'product_state': smrl.product_id.state.code}, context=context)
        return True

    def us_1721_dates_on_products(self, cr, uid, *a, **b):
        """
        Fill the uf_create_date and uf_write_date for existing products
        """
        cr.execute("""UPDATE product_product SET uf_write_date = write_date, uf_create_date = create_date""")
        return True

    def us_1359_update_move_shipment(self, cr, uid, *a, **b):
        """
        Fill the 'pick_shipment_id' value for stock move in a shipment
        """
        cr.execute("""UPDATE stock_move sm SET pick_shipment_id = sp.shipment_id FROM stock_picking sp WHERE sm.picking_id = sp.id AND sp.shipment_id IS NOT NULL""")
        return True

    def us_1167_status_inconsistencies(self, cr, uid, *a, **b):
        '''
        fill fields of stock.mission.report.line:
            - state_ud
            - product_active
            - international_status_code
        '''
        smr_obj = self.pool.get('stock.mission.report')
        context = {}

        smr_ids = smr_obj.search(cr, uid, [('local_report', '=', True)], context=context)

        if not smr_ids:
            return True

        cr.execute('''
        UPDATE stock_mission_report_line
        SET state_ud = sr.state_ud, international_status_code = sr.is_code, product_active = sr.active
        FROM (
          SELECT p.id AS id, p.active AS active, COALESCE(p.state_ud, '') AS state_ud, pis.code AS is_code
          FROM product_product p
            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
            LEFT JOIN product_international_status pis ON pis.id = p.international_status
          ) AS sr
        WHERE stock_mission_report_line.product_id = sr.id;
        ''')

        cr.execute('''
        UPDATE ir_model_data
        SET touched = '[''state_ud'', ''product_active'', ''international_status_code'']', last_modification = now()
        WHERE model = 'stock.mission.report.line' AND res_id IN (
          SELECT id FROM stock_mission_report_line WHERE mission_report_id IN %s)
        ''', (tuple(smr_ids),))

        return True

    def us_1562_rename_special_periods(self, cr, uid, *a, **b):
        """
        Update the name and code of the special Periods from "Period xx" to "Period xx YYYY" (ex: Period 13 2017)
        """
        update_name_and_code = """
            UPDATE account_period AS p
            SET name = name || ' ' || (SELECT SUBSTR(code, 3, 4) FROM account_fiscalyear AS fy WHERE p.fiscalyear_id = fy.id),
            code = code || ' ' || (SELECT SUBSTR(code, 3, 4) FROM account_fiscalyear AS fy WHERE p.fiscalyear_id = fy.id)
            WHERE name like 'Period %';
            """
        update_translation = """
            UPDATE ir_translation AS t 
            SET src = (SELECT t.src || ' ' || to_char(date_start,'YYYY') FROM account_period WHERE id=t.res_id), 
            value = (SELECT t.value || ' ' || to_char(date_start,'YYYY') FROM account_period WHERE id=t.res_id) 
            WHERE name='account.period,name' AND src LIKE 'Period%' AND type='model';
        """
        cr.execute(update_name_and_code)
        cr.execute(update_translation)


patch_scripts()



class ir_model_data(osv.osv):
    _inherit = 'ir.model.data'
    _name = 'ir.model.data'

    def _update(self,cr, uid, model, module, values, xml_id=False, store=True, noupdate=False, mode='init', res_id=False, context=None):
        """
            Store in context that we came from _update
        """
        if not context:
            context = {}
        ctx = context.copy()
        ctx['update_mode'] = mode
        return super(ir_model_data, self)._update(cr, uid, model, module, values, xml_id, store, noupdate, mode, res_id, ctx)

    def patch13_install_export_import_lang(self, cr, uid, *a, **b):
        mod_obj = self.pool.get('ir.module.module')
        mod_ids = mod_obj.search(cr, uid, [('name', '=', 'export_import_lang')])
        if mod_ids and mod_obj.read(cr, uid, mod_ids, ['state'])[0]['state'] == 'uninstalled':
            mod_obj.write(cr, uid, mod_ids[0], {'state': 'to install'})

    def us_254_fix_reconcile(self, cr, uid, *a, **b):
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        sql_file = opj('msf_profile', 'data', 'us_254.sql')
        instance_name = c and c.instance_id and c.instance_id.name
        if instance_name in ['OCBHT101', 'OCBHT143', 'OCBHQ']:
            logger = logging.getLogger('update')
            try:
                fp = tools.file_open(sql_file, 'r')
                logger.warn('Execute us-254 sql')
                cr.execute(fp.read())
                fp.close()
                logger.warn('Sql done')
                os.rename(fp.name, "%sold" % fp.name)
                logger.warn('Sql file renamed')
            except IOError:
                # file does not exist
                pass

    def _us_268_gen_message(self, cr, uid, obj, id, fields, values):
        msg_obj = self.pool.get("sync.client.message_to_send")
        xmlid = obj.get_sd_ref(cr, uid, id)
        data = {
            'identifier': 'us_268_fix_%s_%s' % (obj._name, id),
            'sent': False,
            'generate_message': True,
            'remote_call': "ir.model.data._query_from_sync",
            'arguments':"['%s', '%s', %r, %r]" % (obj._name, xmlid, fields, values),
            'destination_name': 'OCBHQ',
        }
        msg_obj.create(cr, uid, data)

    def us_268_fix_seq(self, cr, uid, *a, **b):
        msg_obj = self.pool.get("sync.client.message_to_send")
        if not msg_obj:
            return True
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        instance_name = c and c.instance_id and c.instance_id.name
        touch_file = opj('msf_profile', 'data', 'us_268.sql')
        # TODO: set as done
        if instance_name == 'OCBHT143':
            logger = logging.getLogger('update')
            try:
                fp = tools.file_open(touch_file, 'r')
                logger.warn('Execute us-268 sql')
                cr.execute(fp.read())
                fp.close()
                logger.warn('Sql done')
                os.rename(fp.name, "%sold" % fp.name)
                logger.warn('Sql file renamed')
            except IOError:
                # file does not exist
                pass

        elif instance_name == 'OCBHT101' and msg_obj:
            logger = logging.getLogger('update')
            try:
                fp = tools.file_open(touch_file, 'r')
                fp.close()
            except IOError:
                return True
            logger.warn('Execute US-268 queries')
            journal_obj = self.pool.get('account.journal')
            instance_id = c.instance_id.id
            account_move_obj = self.pool.get('account.move')
            analytic_obj = self.pool.get('account.analytic.line')
            invoice_obj = self.pool.get('account.invoice')

            journal_id = journal_obj.search(cr, uid, [('type', '=', 'purchase'), ('is_current_instance', '=', True)])[0]
            journal = journal_obj.browse(cr, uid, journal_id)

            analytic_journal_id = journal.analytic_journal_id.id

            move_ids_to_fix = [453, 1122, 1303]

            instance_xml_id = self.pool.get('msf.instance').get_sd_ref(cr, uid, instance_id)
            journal_xml_id = journal_obj.get_sd_ref(cr, uid, journal_id)
            analytic_journal_xml_id = self.pool.get('account.analytic.journal').get_sd_ref(cr, uid, analytic_journal_id)

            move_prefix = c.instance_id.move_prefix

            for move in account_move_obj.browse(cr, uid, move_ids_to_fix):
                if move.instance_id.id == instance_id:
                    # fix already applied
                    continue

                seq_name = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id, context={'fiscalyear_id': move.period_id.fiscalyear_id.id})
                reference = '%s-%s-%s' % (move_prefix, journal.code, seq_name)

                cr.execute('update account_move set instance_id=%s, journal_id=%s, name=%s where id=%s', (instance_id, journal_id, reference, move.id))
                invoice_ids = invoice_obj.search(cr, uid, [('move_id', '=', move.id)])
                if invoice_ids:
                    cr.execute('update account_invoice set journal_id=%s, number=%s where id=%s', (journal_id, reference, invoice_ids[0]))

                self._us_268_gen_message(cr, uid, account_move_obj, move.id,
                                         ['instance_id', 'journal_id', 'name'], [instance_xml_id, journal_xml_id, reference]
                                         )
                for line in move.line_id:
                    cr.execute('update account_move_line set instance_id=%s, journal_id=%s where id=%s', (instance_id, journal_id, line.id))
                    self._us_268_gen_message(cr, uid, self.pool.get('account.move.line'), line.id,
                                             ['instance_id', 'journal_id'], [instance_xml_id, journal_xml_id]
                                             )

                    analytic_ids = analytic_obj.search(cr, uid, [('move_id', '=', line.id)])

                    for analytic_id in analytic_ids:
                        cr.execute('update account_analytic_line set instance_id=%s, entry_sequence=%s, journal_id=%s where id=%s', (instance_id, reference, analytic_journal_id, analytic_id))
                        self._us_268_gen_message(cr, uid, analytic_obj, analytic_id,
                                                 ['instance_id', 'entry_sequence', 'journal_id'], [instance_xml_id, reference, analytic_journal_xml_id]
                                                 )
            os.rename(fp.name, "%sold" % fp.name)
            logger.warn('Set US-268 as executed')


ir_model_data()

class account_installer(osv.osv_memory):
    _inherit = 'account.installer'
    _name = 'account.installer'

    _defaults = {
        'charts': 'msf_chart_of_account',
    }

    # Fix for UF-768: correcting fiscal year and name
    def execute(self, cr, uid, ids, context=None):
        super(account_installer, self).execute(cr, uid, ids, context=context)
        # Retrieve created fiscal year
        fy_obj = self.pool.get('account.fiscalyear')
        for res in self.read(cr, uid, ids, context=context):
            if 'date_start' in res and 'date_stop' in res:
                f_ids = fy_obj.search(cr, uid, [('date_start', '<=', res['date_start']), ('date_stop', '>=', res['date_stop']), ('company_id', '=', res['company_id'])], context=context)
                if len(f_ids) > 0:
                    # we have one
                    new_name = "FY " + res['date_start'][:4]
                    new_code = "FY" + res['date_start'][:4]
                    if int(res['date_start'][:4]) != int(res['date_stop'][:4]):
                        new_name = "FY " + res['date_start'][:4] +'-'+ res['date_stop'][:4]
                        new_code = "FY" + res['date_start'][2:4] +'-'+ res['date_stop'][2:4]
                    vals = {
                        'name': new_name,
                        'code': new_code,
                    }
                    fy_obj.write(cr, uid, f_ids, vals, context=context)
        return

account_installer()

class res_config_view(osv.osv_memory):
    _inherit = 'res.config.view'
    _name = 'res.config.view'
    _defaults={
        'view': 'extended',
    }
res_config_view()

class base_setup_company(osv.osv_memory):
    _inherit = 'base.setup.company'
    _name = 'base.setup.company'

    def default_get(self, cr, uid, fields_list=None, context=None):
        ret = super(base_setup_company, self).default_get(cr, uid, fields_list, context)
        if not ret.get('name'):
            ret.update({'name': 'MSF', 'street': 'Rue de Lausanne 78', 'street2': 'CP 116', 'city': 'Geneva', 'zip': '1211', 'phone': '+41 (22) 849.84.00'})
            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            ret['name'] = company.name
            addresses = self.pool.get('res.partner').address_get(cr, uid, company.id, ['default'])
            default_id = addresses.get('default', False)
            # Default address
            if default_id:
                address = self.pool.get('res.partner.address').browse(cr, uid, default_id, context=context)
                for field in ['street','street2','zip','city','email','phone']:
                    ret[field] = address[field]
                for field in ['country_id','state_id']:
                    if address[field]:
                        ret[field] = address[field].id
            # Currency
            cur = self.pool.get('res.currency').search(cr, uid, [('name','=','EUR')])
            if company.currency_id:
                ret['currency'] = company.currency_id.id
            elif cur:
                ret['currency'] = cur[0]

            fp = tools.file_open(opj('msf_profile', 'data', 'msf.jpg'), 'rb')
            ret['logo'] = base64.encodestring(fp.read())
            fp.close()
        return ret

base_setup_company()

class res_users(osv.osv):
    _inherit = 'res.users'
    _name = 'res.users'

    def _get_default_ctx_lang(self, cr, uid, context=None):
        config_lang = self.pool.get('unifield.setup.configuration').get_config(cr, uid).lang_id
        if config_lang:
            return config_lang
        if self.pool.get('res.lang').search(cr, uid, [('translatable','=',True), ('code', '=', 'en_MF')]):
            return 'en_MF'
        return 'en_US'

    def set_default_partner_lang(self, cr, uid, context=None):
        """
            when base module is installed en_US is the default lang for partner
            overwrite this default value
        """

        values_obj = self.pool.get('ir.values')
        default_value = values_obj.get(cr, uid, 'default', False, ['res.partner'])
        if not default_value or 'lang' not in [x[1] for x in default_value] or ('lang', 'en_US') in [(x[1], x[2]) for x in default_value]:
            values_obj.set(cr, uid, 'default', False, 'lang', ['res.partner'], 'en_MF')

        return True

    _defaults = {
        'context_lang': _get_default_ctx_lang,
    }

res_users()

class email_configuration(osv.osv):
    _name = 'email.configuration'
    _description = 'Email configuration'

    _columns = {
        'smtp_server': fields.char('SMTP Server', size=512, required=True),
        'email_from': fields.char('Email From', size=512, required=True),
        'smtp_port': fields.integer('SMTP Port', required=True),
        'smtp_ssl': fields.boolean('Use SSL'),
        'smtp_user': fields.char('SMTP User', size=512),
        'smtp_password': fields.char('SMTP Password', size=512),
        'destination_test': fields.char('Email Destination Test', size=512),
    }
    _defaults = {
        'smtp_port': 25,
        'smtp_ssl': False,
    }

    def set_config(self, cr):
        data = ['smtp_server', 'email_from', 'smtp_port', 'smtp_ssl', 'smtp_user', 'smtp_password']
        cr.execute("""select %s from email_configuration
            limit 1""" % ','.join(data))  # not_a_user_entry
        res = cr.fetchone()
        if res:
            for i, key in enumerate(data):
                tools.config[key] = res[i] or False
        return True

    def __init__(self, pool, cr):
        super(email_configuration, self).__init__(pool, cr)
        cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (self._table,))
        if cr.rowcount:
            self.set_config(cr)

    def _update_email_config(self, cr, uid, ids, context=None):
        self.set_config(cr)
        return True

    def test_email(self, cr, uid, ids, context=None):
        cr.execute('select destination_test from email_configuration limit 1')
        res = cr.fetchone()
        if not res or not res[0]:
            raise osv.except_osv(_('Warning !'), _('No destination email given!'))
        if not tools.email_send(False, [res[0]], 'Test email from UniField', 'This is a test.'):
            raise osv.except_osv(_('Warning !'), _('Could not deliver email'))
        return True

    _constraints = [
        (_update_email_config, 'Always true: update email configuration', [])
    ]
email_configuration()


class ir_cron_linux(osv.osv_memory):
    _name = 'ir.cron.linux'
    _description = 'Start memory cleaning cron job from linux crontab'
    _columns = {
    }

    def __init__(self, *a, **b):
        self._logger = logging.getLogger('ir.cron.linux')
        self._jobs = {
            'memory_clean': ('osv_memory.autovacuum', 'power_on', ()),
            'save_puller': ('sync.server.update', '_save_puller', ())
        }
        self.running = {}
        for job in self._jobs:
            self.running[job] = Lock()

        super(ir_cron_linux, self).__init__(*a, **b)

    def execute_job(self, cr, uid, job, context=None):
        if job not in self._jobs:
            raise osv.except_osv(_('Warning !'), _('Job does not exists'))
        if uid != 1:
            raise osv.except_osv(_('Warning !'), _('Permission denied'))
        if not self.running[job].acquire(False):
            self._logger.info("Linux cron: job %s already running" % (job, ))
            return False
        try:
            self._logger.info("Linux cron: starting job %s" % (job, ))
            obj = self.pool.get(self._jobs[job][0])
            fct = getattr(obj, self._jobs[job][1])
            args = self._jobs[job][2]
            fct(cr, uid, *args)
            self._logger.info("Linux cron: job %s done" % (job, ))
        except Exception:
            self._logger.warning('Linux cron: job %s failed' % (job, ), exc_info=1)
        finally:
            self.running[job].release()
        return True

ir_cron_linux()


class communication_config(osv.osv):
    """ Communication configuration """
    _name = "communication.config"
    _description = "Communication configuration"

    _columns = {
        'message': fields.text('Message to display',
                               help="Enter the message you want to display as a banner. Nothing more than the information entered here will be displayed."),
        'from_date': fields.datetime('Broadcast start date', help='If defined, the display of the message will start at this date'),
        'to_date': fields.datetime('Broadcast stop date', help='If defined, the display of the message will stop at this date'),
    }

    def display_banner(self, cr, uid, ids=None, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        sync_disabled = self.pool.get('sync.server.disabled')
        if sync_disabled and sync_disabled.is_set(cr, 1, context):
            return True

        if ids is None:
            ids = self.search(cr, 1, [], context=context)

        com_obj = self.read(cr, 1, ids[0], ['message', 'from_date',
                                            'to_date'], context=context)
        if not com_obj['message']:
            return False

        if not com_obj['from_date'] and not com_obj['to_date']:
            return True

        current_date = fields.datetime.now()
        if not com_obj['from_date'] and com_obj['to_date']\
                and com_obj['to_date'] > current_date:
            return True

        if com_obj['from_date'] and not com_obj['to_date']\
                and com_obj['from_date'] < current_date:
            return True

        if com_obj['from_date'] and com_obj['to_date']\
                and com_obj['from_date'] < current_date\
                and com_obj['to_date'] > current_date:
            return True

        return False

    def get_message(self, cr, uid, ids=None, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        sync_disabled = self.pool.get('sync.server.disabled')
        if sync_disabled and sync_disabled.is_set(cr, 1, context):
            return sync_disabled.get_message(cr, 1, context)

        if ids is None:
            ids = self.search(cr, 1, [], context=context)
        return self.read(cr, 1, ids[0], ['message'],
                         context=context)['message']

    def _check_only_one_obj(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        obj = self.search(cr, 1, [], context=context)
        if len(obj) > 1:
            return False
        return True

    _constraints = [
        (_check_only_one_obj, 'You cannot have more than one Communication configuration', ['message']),
    ]

communication_config()

class sync_tigger_something(osv.osv):
    _name = 'sync.trigger.something'

    _columns = {
        'name': fields.char('Name', size=256),
    }

    def delete_ir_model_access(self, cr, uid, context=None):
        _logger = logging.getLogger('trigger')
        ir_model_access = self.pool.get('ir.model.access')

        ids_to_del = ir_model_access.search(cr, uid, [('from_system', '=', False)])
        access_ids_to_keep = ir_model_access.search(cr, uid, [('from_system', '=', True)])
        if ids_to_del:
            cr.execute("delete from ir_model_access where id in %s", (tuple(ids_to_del),))
            cr.execute("delete from ir_model_data where res_id in %s and model='ir.model.access'", (tuple(ids_to_del),))
            _logger.warn('Purge %d ir_model_access %d kept'  % (len(ids_to_del), len(access_ids_to_keep)))
        return True

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        _logger = logging.getLogger('trigger')
        if context.get('sync_update_execution') and vals.get('name') == 'clean_ud_trans':

            data_obj = self.pool.get('ir.model.data')
            unidata_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]

            trans_to_delete = """from ir_translation where name='product.template,name'
                and ( res_id in (select p.product_tmpl_id from product_product p where p.international_status=%s) or coalesce(res_id,0)=0) and type='model'
            """ % (unidata_id,)  # not_a_user_entry
            cr.execute("""delete from ir_model_data where model='ir.translation' and res_id in (
                select id  """ + trans_to_delete + """
            )""")  # not_a_user_entry
            _logger.warn('Delete %d sdref linked to UD trans' % (cr.rowcount,))
            cr.execute("delete "+ trans_to_delete) # not_a_user_entry
            _logger.warn('Delete %d trans linked to UD trans' % (cr.rowcount,))

        if context.get('sync_update_execution') and vals.get('name') == 'clean_ir_model_access':
            self.delete_ir_model_access(cr, uid, context=context)

        if vals.get('name') == 'clean_ud_fff':
            # US-5356
            data_obj = self.pool.get('ir.model.data')
            unidata_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]

            trans_query = """
                ir_translation where name in ('product.product,function_value', 'product.product,form_value', 'product.product,fit_value') and
                type = 'model' and
                res_id in (
                  select id from product_product where international_status=%s
                )
            """
            # 1/ delete xmlid linked to trans
            cr.execute('''delete from ir_model_data where
                model='ir.translation' and
                module='sd' and
                res_id in (
                    select id from '''+trans_query+'''
                )
            ''', (unidata_id,))  # not_a_user_entry
            _logger.warn('Delete %d ir.model.data trans linked to UD' % (cr.rowcount,))

            # 2/ delete trans
            cr.execute('delete from '+ trans_query, (unidata_id,))  # not_a_user_entry
            _logger.warn('Delete %d trans linked to UD' % (cr.rowcount,))

            # 3/ reset fields
            cr.execute('''update product_product set
                  form_value=NULL,
                  fit_value=NULL,
                  function_value=NULL,
                  product_catalog_path=NULL
                where international_status=%s ''', (unidata_id,))
            _logger.warn('Reset %d UD products' % (cr.rowcount,))

        if vals.get('name') == 'us-5398-product-price':
            msf_instance_obj = self.pool.get('msf.instance')
            prod_obj = self.pool.get('product.product')

            instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if instance.instance.startswith('OCG') and \
                '_KE1_' not in instance.instance and \
                '_UA1_' not in instance.instance and \
                '_MX1_' not in instance.instance and \
                    '_LB1_' not in instance.instance:

                setup_br = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
                if not setup_br:
                    percent = 0
                else:
                    percent = setup_br.sale_price


                data_file = tools.file_open(opj('msf_profile', 'data', 'us-5398-product-price.csv'), 'rb')
                data = data_file.read()

                hq_id = msf_instance_obj.search(cr, uid, [('code', '=', 'CH')])
                hq_info =  msf_instance_obj.browse(cr, uid, hq_id[0])

                crypt_o = tools.misc.crypt(hq_info.instance_identifier)
                clear_data = cStringIO.StringIO(crypt_o.decrypt(data))
                csv_reader = csv.reader(clear_data, delimiter=',')
                csv_reader.next()
                xmlid_price = {}
                xmlid_code = {}
                prod_id_price = {}

                for line in csv_reader:
                    xmlid_price[line[1]] = float(line[2])
                    xmlid_code[line[1]] = line[0]


                all_xmlid = xmlid_price.keys()

                for sdref, p_id in prod_obj.find_sd_ref(cr, uid, all_xmlid).iteritems():
                    prod_id_price[p_id] = xmlid_price[sdref]
                    del xmlid_code[sdref]

                if xmlid_code:
                    _logger.warn('OCG Prod price update, %d products not found: %s' % (len(xmlid_code), ', '.join(xmlid_code.values())))

                nb_updated= 0
                nb_ignored = 0
                for prod in prod_obj.read(cr, uid, prod_id_price.keys(), ['standard_price', 'product_tmpl_id']):
                    if abs(prod['standard_price'] - prod_id_price[prod['id']]) > 0.000001:
                        list_price = round(prod_id_price[prod['id']] * (1 + (percent/100.00)), 5)
                        nb_updated += 1
                        cr.execute('update product_template set standard_price=%s, list_price=%s where id=%s', (prod_id_price[prod['id']], list_price, prod['product_tmpl_id'][0]))
                        cr.execute("""insert into standard_price_track_changes ( create_uid, create_date, old_standard_price, new_standard_price, user_id, product_id, change_date, transaction_name) values
                            (1, NOW(), %s, %s, 1, %s, date_trunc('second', now()::timestamp), 'OCG Prod price update')
                            """,  (prod['standard_price'], prod_id_price[prod['id']], prod['id']))
                    else:
                        nb_ignored += 1

                _logger.warn('OCG Prod price update: %d updated, %s ignored' % (nb_updated, nb_ignored))


        return super(sync_tigger_something, self).create(cr, uid, vals, context)

sync_tigger_something()

class sync_tigger_something_up(osv.osv):
    _name = 'sync.trigger.something.up'

    _columns = {
        'name': fields.char('Name', size=256),
        'args': fields.text('Args'),
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('sync_update_execution'):
            _logger = logging.getLogger('tigger')
            if vals.get('name') == 'clean_mission_stock_central':
                remote_id = self.pool.get('msf.instance').search(cr, uid, [('code', '=', vals['args'])])
                if remote_id:
                    cr.execute("update stock_mission_report_line set central_qty=0,central_val=0 where mission_report_id in (select id from stock_mission_report where instance_id = %s and full_view='f')", (remote_id[0],))
                    _logger.warn('Reset %d mission stock Unall. Stock for instance_id %s' % (cr.rowcount, remote_id[0]))
            elif vals.get('name') == 'clean_mission_stock_cu':
                remote_id = self.pool.get('msf.instance').search(cr, uid, [('code', '=', vals['args'])])
                if remote_id:
                    cr.execute("update stock_mission_report_line set cu_qty=0, cu_val=0 where mission_report_id in (select id from stock_mission_report where instance_id = %s and full_view='f')", (remote_id[0],))
                    _logger.warn('Reset %d mission stock CU Stock for instance_id %s' % (cr.rowcount, remote_id[0]))

        return super(sync_tigger_something_up, self).create(cr, uid, vals, context)

sync_tigger_something_up()
