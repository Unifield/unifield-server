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
import xmlrpc.client
import netsvc
import traceback
#import re

from msf_field_access_rights.osv_override import _get_instance_level
import io
import csv
import zlib
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta
import hashlib

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


    def us_12391_cleanup_rate_VEF_2016(self, cr, uid, *a, **b):
        # align OCB VEF 01/Jan/2016 rate ( 1st VEF entry is on 2016-02-29)
        cr.execute("select * from res_currency_rate r, ir_model_data d where d.model='res.currency.rate' and d.res_id=r.id and d.name in ('8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/2243', '8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/2559')")
        nb_rate = cr.rowcount
        if nb_rate == 1:
            cr.execute("update ir_model_data set name='8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/2559' where name='8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/2243'")
            cr.execute("update res_currency_rate set rate=354.6056 where id in (select res_id from ir_model_data where name='8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/2559')")
            self.log_info(cr, uid, 'US-12391: VEF 01/Jan/2016 rate fixed')
        elif nb_rate == 2:
            cr.execute("delete from res_currency_rate where name='2016-01-01' and id in (select res_id from ir_model_data where name='8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/2243')")
            cr.execute("delete from ir_model_data where name='8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/2243'")
            self.log_info(cr, uid, 'US-12391: VEF 01/Jan/2016 rate duplicated')


        # align OCB ZWL Jun/2016 rate sdref
        cr.execute("select res_id from ir_model_data where name in ('8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/4586', 'b32c686e-27d8-11e6-94fb-1002b58b8575/res_currency_rate/3094')")
        nb_rate = cr.rowcount
        if nb_rate == 2:
            cr.execute("delete from res_currency_rate where name='2016-06-01' and id in (select res_id from ir_model_data where name='b32c686e-27d8-11e6-94fb-1002b58b8575/res_currency_rate/3094')")
            cr.execute("delete from ir_model_data where name='b32c686e-27d8-11e6-94fb-1002b58b8575/res_currency_rate/3094'")
            self.log_info(cr, uid, 'US-12391: ZWL 01/Jun/2016 duplicated')
        elif nb_rate == 1:
            cr.execute("update ir_model_data set name='8461c7cf-a14a-11e4-8200-005056a95b32/res_currency_rate/4586' where name='b32c686e-27d8-11e6-94fb-1002b58b8575/res_currency_rate/3094'")
            self.log_info(cr, uid, 'US-12391: ZWL 01/Jun/2016 sdref name aligned')
        return True

    # UF32.0
    def us_12076_remove_po_audittrail_rule_domain(self, cr, uid, *a, **b):
        '''
        Remove the restrictions on purchase.order's and purchase.order.line's Track Changes to allow RfQs
        '''
        cr.execute("""
            UPDATE audittrail_rule SET domain_filter = '[]' 
            WHERE object_id IN (SELECT id FROM ir_model WHERE model IN ('purchase.order', 'purchase.order.line'))
        """)
        return True

    def us_12071_gdpr_patch(self, cr, uid, *a, **b):
        cr.execute("""UPDATE hr_employee
        SET
        payment_method_id = NULL,
        bank_name = NULL,
        bank_account_number = NULL
        WHERE employee_type = 'local'
        """)
        cr.execute("""
        DELETE FROM audittrail_log_line
        WHERE
            name IN ('payment_method_id', 'bank_name', 'bank_account_number') AND
            object_id = (SELECT id FROM ir_model WHERE model = 'hr.employee')""")
        return True

    def us_12110_remove_sup_fin_read(self, cr, uid, *a, **b):
        '''
        Remove all Sup_Fin_Read groups from all users
        '''
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if instance and instance.level == 'section':
            self.pool.get('sync.trigger.something').create(cr, uid, {'name': 'US-12110-Sup_Fin_Read'})
        return True

    # python 3
    def us_9321_2_remove_location_colors(self, cr, uid, *a, **b):
        '''
        Remove the search_color of the locations Configurable locations, Intermediate Stocks and Internal Consumption Units
        '''
        obj_data = self.pool.get('ir.model.data')
        # Get the locations ids
        conf = obj_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_internal_client_view')[1]
        interm = obj_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')[1]
        iconsu = obj_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_consumption_units_view')[1]

        cr.execute("""UPDATE stock_location SET search_color = NULL WHERE id IN %s""", (tuple([conf, interm, iconsu]),))
        return True

    def py3_migrate_pickle_ir_values(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity'):
            return True
        import pickle
        import json
        cr.execute("select id, value from ir_values where object='f'")
        ok=0
        fail=0
        for x in cr.fetchall():
            try:
                val = json.dumps(pickle.loads(bytes(x[1], 'utf8')))
                cr.execute('update ir_values set value=%s where id=%s', (val, x[0]))
                ok += 1
            except:
                fail += 1

        cr.execute("select id, meta from ir_values where coalesce(meta, '')!='' and meta!='web'")
        for x in cr.fetchall():
            try:
                val = json.dumps(pickle.loads(bytes(x[1], 'utf8')))
                cr.execute('update ir_values set meta=%s where id=%s', (val, x[0]))
                ok += 1
            except:
                fail += 1

        self.log_info(cr, uid, 'Pickle ir_values conversion: ok: %d , fail: %d' % (ok, fail))
        return True


    # UF31.0
    def us_11950_delete_previous_assets(self, cr,uid, *a, **b):
        cr.execute("delete from product_asset")
        cr.execute("update ir_sequence set number_next=1 where code='product.asset'")
        return True

    def us_11781_remove_product_country_restriction(self, cr, uid, *a, **b):
        '''
        Remove the country restrictions from the products who have some
        '''
        cr.execute("""UPDATE product_product SET restricted_country = 'f', country_restriction = NULL 
            WHERE restricted_country = 't'""")
        self.log_info(cr, uid, "US-11781: The Product Restrictions have been removed on %s Product(s)" % (cr.rowcount,))
        return True

    def us_11026_oca_liquidity_migration_journal(self, cr, uid, *a, **b):
        entity_obj = self.pool.get('sync.client.entity')
        if entity_obj and entity_obj.get_entity(cr, uid).oc == 'oca':
            sql_file = opj('msf_profile', 'data', 'us_11026_migration_items_to_liquidity_journals.sql')
            fp = tools.file_open(sql_file, 'r')
            cr.execute(fp.read())
            fp.close()
        return True

    def us_11571_new_job_text_field_employee(self, cr, uid, *a, **b):
        cr.execute('''
        UPDATE hr_employee emp
        SET job_name = job.name
        FROM hr_job job
        WHERE
            emp.job_id IS NOT NULL AND
            emp.job_id = job.id
        ''')
        return True

    def us_7168_7169_10518_fix_docs_reason_type(self, cr, uid, *a, **b):
        '''
        Fix the Reason Type of INs from scratch to have only Internal Supply, Return from unit or External Supply
        Prevent the 'Other' Reason Type from appearing in the IN, INT, OUT and P/P
        Fix the Reason Type of INs and INTs which have the Other Reason Type
        '''
        data_obj = self.pool.get('ir.model.data')
        int_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_supply')[1]
        intm_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1]
        ext_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
        ret_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1]
        oth_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
        loss_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
        deli_partner_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        # To ignore moves with Scrap and Loss RT, because of US-806 (stock_override/stock.py def create() stock_move)
        scrp_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
        exp_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_expiry')[1]

        exp_loc_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
        dest_loc_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_scrapped')[1]

        # RT INs from scratch and with RT Other: Internal
        cr.execute("""UPDATE stock_move SET reason_type_id = %s 
            WHERE reason_type_id NOT IN %s AND picking_id IN (SELECT p.id FROM stock_picking p 
                LEFT JOIN res_partner pt ON p.partner_id = pt.id WHERE p.type = 'in' 
                    AND ((p.purchase_id IS NULL AND p.partner_id IS NOT NULL AND pt.partner_type IN ('internal', 'esc'))
                    OR (p.purchase_id IS NOT NULL AND p.reason_type_id = %s)))
        """, (int_rt_id, tuple([int_rt_id, loss_rt_id, scrp_rt_id]), oth_rt_id))
        cr.execute("""UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p LEFT JOIN res_partner pt ON p.partner_id = pt.id 
                WHERE p.type = 'in' AND ((p.reason_type_id != %s AND p.purchase_id IS NULL AND p.partner_id IS NOT NULL 
                        AND pt.partner_type IN ('internal', 'esc'))
                    OR (p.purchase_id IS NOT NULL AND p.reason_type_id = %s)))""", (int_rt_id, int_rt_id, oth_rt_id))
        self.log_info(cr, uid, "US-7168-7169-10518: The Reason Type of %s IN(s) from scratch or with the Other Reason Type have been set to 'Internal'" % (cr.rowcount,))

        # RT INs from scratch and with RT Other: External
        cr.execute("""UPDATE stock_move SET reason_type_id = %s 
            WHERE reason_type_id NOT IN %s AND picking_id IN (SELECT p.id FROM stock_picking p 
                LEFT JOIN res_partner pt ON p.partner_id = pt.id WHERE p.type = 'in' 
                    AND ((p.purchase_id IS NULL AND ((p.partner_id IS NULL AND p.ext_cu IS NULL) 
                        OR (p.partner_id IS NOT NULL AND pt.partner_type = 'external')))
                    OR (p.purchase_id IS NOT NULL AND p.reason_type_id = %s)))
        """, (ext_rt_id, tuple([ext_rt_id, loss_rt_id, scrp_rt_id]), oth_rt_id))
        cr.execute("""UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p LEFT JOIN res_partner pt ON p.partner_id = pt.id 
                WHERE p.type = 'in'
                    AND ((p.reason_type_id != %s AND p.purchase_id IS NULL AND ((p.partner_id IS NULL AND p.ext_cu IS NULL)
                        OR (p.partner_id IS NOT NULL AND pt.partner_type = 'external')))
                    OR (p.purchase_id IS NOT NULL AND p.reason_type_id = %s)))""", (ext_rt_id, ext_rt_id, oth_rt_id))
        self.log_info(cr, uid, "US-7168-7169-10518: The Reason Type of %s IN(s) from scratch or with the Other Reason Type have been set to 'External'" % (cr.rowcount,))

        # RT INs from scratch and with RT Other: Return from Unit
        cr.execute("""UPDATE stock_move SET reason_type_id = %s 
            WHERE reason_type_id NOT IN %s AND picking_id IN (SELECT id FROM stock_picking WHERE type = 'in' 
                AND partner_id IS NULL AND ext_cu IS NOT NULL AND (purchase_id IS NULL
                OR (purchase_id IS NOT NULL AND reason_type_id = %s)))
        """, (ret_rt_id, tuple([ret_rt_id, loss_rt_id, scrp_rt_id]), oth_rt_id))
        cr.execute("""UPDATE stock_picking SET reason_type_id = %s 
            WHERE type = 'in' AND partner_id IS NULL AND ext_cu IS NOT NULL
                AND ((reason_type_id != %s AND purchase_id IS NULL)
                OR (purchase_id IS NOT NULL AND reason_type_id = %s))""", (ret_rt_id, ret_rt_id, oth_rt_id))
        self.log_info(cr, uid, "US-7168-7169-10518: The Reason Type of %s IN(s) from scratch or with the Other Reason Type have been set to 'Return from Unit'" % (cr.rowcount,))

        # RT INTs with RT Other: Loss/Expiry for the moves going to Destruction or Expired/Damaged/For scrap ;
        # Internal otherwise and for the document
        cr.execute("""UPDATE stock_move SET reason_type_id = %s
            WHERE location_dest_id IN %s
                AND picking_id IN (SELECT id FROM stock_picking WHERE type = 'internal' AND reason_type_id = %s)
            """, (exp_rt_id, tuple([exp_loc_id, dest_loc_id]), oth_rt_id))
        cr.execute("""UPDATE stock_move SET reason_type_id = %s
            WHERE location_dest_id NOT IN %s AND reason_type_id NOT IN %s
                AND picking_id IN (SELECT id FROM stock_picking WHERE type = 'internal' AND reason_type_id = %s)
            """, (intm_rt_id, tuple([exp_loc_id, dest_loc_id]), tuple([exp_rt_id, loss_rt_id, scrp_rt_id]), oth_rt_id))
        cr.execute("""UPDATE stock_picking SET reason_type_id = %s 
            WHERE type = 'internal' AND reason_type_id = %s""", (intm_rt_id, oth_rt_id))
        self.log_info(cr, uid, "US-7168-7169-10518: The Reason Type of %s INT(s) with the Other Reason Type have been set to 'Internal'" % (cr.rowcount,))

        # RT OUTs from scratch with RT Other: Deliver Partner
        cr.execute("""UPDATE stock_move SET reason_type_id = %s
            WHERE picking_id IN (SELECT id FROM stock_picking WHERE reason_type_id = %s AND type = 'out' AND 
                subtype = 'standard' AND sale_id IS NULL AND purchase_id IS NULL)
        """, (deli_partner_rt_id, oth_rt_id))
        cr.execute("""UPDATE stock_picking SET reason_type_id = %s WHERE reason_type_id = %s AND type = 'out' AND 
            subtype = 'standard' AND sale_id IS NULL AND purchase_id IS NULL""", (deli_partner_rt_id, oth_rt_id))
        self.log_info(cr, uid, "US-7168-7169-10518: The Reason Type of %s OUT(s) from scratch with the Other Reason Type have been set to 'Deliver Partner'" % (cr.rowcount,))

        # Change 'Other' RT
        cr.execute("""UPDATE stock_reason_type SET incoming_ok ='f', internal_ok = 'f', outgoing_ok = 'f'
            WHERE id = %s""", (oth_rt_id,))

        return True

    # UF30.1
    def us_11956_fix_po_line_reception_destination(self, cr, uid, *a, **b):
        '''
        Set the Reception Destination to Cross Docking for all PO line by Nomenclature (no product) if they are linked
        to a FO or an External IR
        '''
        cross_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking',
                                                                       'stock_location_cross_docking')[1]
        cr.execute('''
            UPDATE purchase_order_line SET reception_dest_id = %s WHERE id IN (
                SELECT pl.id FROM purchase_order_line pl 
                    LEFT JOIN sale_order so ON pl.link_so_id = so.id 
                    LEFT JOIN stock_location l ON so.location_requestor_id = l.id 
                WHERE pl.link_so_id = so.id AND pl.product_id IS NULL AND 
                    (so.procurement_request = 'f' OR (so.location_requestor_id IS NOT NULL AND l.usage = 'customer'))
        )''', (cross_id,))
        self.log_info(cr, uid, "US-11956: The Line Destination of %s PO line(s) by Nomenclature have been set to 'Cross Docking'" % (cr.rowcount,))
        return True


    # UF30.0
    def us_11810_fix_company_logo(self, cr, uid, *a, **b):
        '''
        Add the default logo to the company if there is none
        '''
        company = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id
        if not company.logo:
            default_logo = tools.file_open(opj('msf_profile', 'data', 'msf.jpg'), 'rb')
            self.pool.get('res.company').write(cr, uid, company.id, {'logo': base64.b64encode(default_logo.read())})
            default_logo.close()

        return True

    def us_1074_create_unifield_instance(self, cr, uid, *a, **b):
        uf_instance = self.pool.get('unifield.instance')
        unidata_proj =  self.pool.get('unidata.project')
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if instance and instance.level == 'section':
            cr.execute('''select p.id, p.country_id, instance.code, instance.id, p.uf_active from
                    unidata_project p, msf_instance instance
                    where
                        instance.id = p.instance_id
                ''')
            instance_cache = {}
            for proj in cr.fetchall():
                if proj[3] not in instance_cache:
                    inst_ids = uf_instance.search(cr, uid, [('instance_id', '=', proj[3])])
                    if not inst_ids:
                        instance_cache[proj[3]] = uf_instance.create(cr, uid, {'instance_id': proj[3],'country_id': proj[1], 'uf_active': proj[4]})
                    else:
                        instance_cache[proj[3]] = inst_ids[0]

                unidata_proj.write(cr, uid, proj[0], {'unifield_instance_id': instance_cache[proj[3]]})

        return True

    def us_11679_set_iil_oca(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance:
            return True

        if instance.instance.endswith('OCA'):
            cr.execute("""UPDATE unifield_setup_configuration
            SET esc_line='t'
            """)
        return True

    def us_11090_replace_DC4_by_space(self, cr, uid, *a, **b):
        cr.execute('''
        UPDATE account_move_line
        SET
            ref = regexp_replace(ref, E'\x14', ' ', 'g'),
            name = regexp_replace(name, E'\x14', ' ', 'g'),
            partner_txt = regexp_replace(partner_txt, E'\x14', ' ', 'g')
        WHERE ref ~ '\x14' OR name ~ '\x14' OR partner_txt ~ '\x14'
        ''')
        cr.execute('''
        UPDATE account_analytic_line
        SET
            ref = regexp_replace(ref, E'\x14', ' ', 'g'),
            name = regexp_replace(name, E'\x14', ' ', 'g'),
            partner_txt = regexp_replace(partner_txt, E'\x14', ' ', 'g')
        WHERE ref ~ '\x14' OR name ~ '\x14' OR partner_txt ~ '\x14'
        ''')

    def us_11130_trigger_down_account_mapping(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity'):
            # exclude new instances
            return True
        cr.execute("""UPDATE ir_model_data
        SET last_modification=NOW(), touched='[''account_id'', ''mapping_value'']'
        WHERE model='account.export.mapping'
        """)
        return True

    def us_11448_update_rfq_line_state(self, cr, uid, *a, **b):
        '''
        Update the rfq_line_state of all RFQ lines
        '''
        # Non-cancelled
        cr.execute("""
            UPDATE purchase_order_line pl SET rfq_line_state = p.rfq_state FROM purchase_order p
            WHERE pl.order_id = p.id AND pl.state NOT IN ('cancel', 'cancel_r') AND p.rfq_state != 'cancel' 
                AND p.rfq_ok = 't'
        """)

        # Cancelled(-r)
        cr.execute("""
            UPDATE purchase_order_line pl SET rfq_line_state = pl.state FROM purchase_order p
            WHERE pl.order_id = p.id AND pl.state IN ('cancel', 'cancel_r') AND p.rfq_ok = 't'
        """)

        return True

    def us_10874_bar_hard_post_wizard(self, cr, uid, *a, **b):
        bar = self.pool.get('msf_button_access_rights.button_access_rule')
        bar_ids = bar.search(cr, uid, [('name', '=', 'action_confirm_hard_posting'), ('model_id.name', '=', 'wizard.temp.posting')])
        group_ids = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'Fin_Hard_Posting')])
        if bar_ids and group_ids:
            bar.write(cr, uid, bar_ids, {'group_ids': [(6, 0, group_ids)]})

        return True

    def us_10783_11563_po_reception_destination(self, cr, uid, *a, **b):
        '''
        For each PO line, look at its origin to set the reception_destination_id. It can be Cross Docking, Service,
        Non-Stockable or Input
        '''
        data_obj = self.pool.get('ir.model.data')
        srv_id = self.pool.get('stock.location').get_service_location(cr, uid, context={})
        input_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
        cross_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        n_stock_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]

        # Cross Docking: PO line linked to a FO and product is not Service or an IR to Ext CU and product is neither
        # Service or Non-Stockable
        cr.execute("""UPDATE purchase_order_line SET reception_dest_id = %s WHERE id IN (
            SELECT pl.id FROM purchase_order_line pl 
                LEFT JOIN product_product pp ON pl.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN sale_order so ON pl.link_so_id = so.id 
                LEFT JOIN stock_location l ON so.location_requestor_id = l.id
            WHERE pl.link_so_id = so.id AND ((pt.type != 'service_recep' AND so.procurement_request = 'f') OR 
                (pt.type NOT IN ('service_recep', 'consu') AND so.location_requestor_id IS NOT NULL AND l.usage = 'customer'))
        )""", (cross_id,))
        self.log_info(cr, uid, "US-10783-11563: The Line Destination of %s PO line(s) have been set to 'Cross Docking'" % (cr.rowcount,))

        # Service: PO line from scratch or linked to internal IR and product is Service
        cr.execute("""UPDATE purchase_order_line SET reception_dest_id = %s WHERE id IN (
            SELECT pl.id FROM purchase_order_line pl
                LEFT JOIN product_product pp ON pl.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
            WHERE pt.type = 'service_recep'
        )""", (srv_id,))
        self.log_info(cr, uid, "US-10783-11563: The Line Destination of %s PO line(s) have been set to 'Service'" % (cr.rowcount,))

        # Non-Stockable: PO line from scratch or linked to internal IR and product is Non-Stockable
        cr.execute("""UPDATE purchase_order_line SET reception_dest_id = %s WHERE id IN (
            SELECT pl.id FROM purchase_order_line pl
                LEFT JOIN product_product pp ON pl.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN sale_order so ON pl.link_so_id = so.id 
                LEFT JOIN stock_location l ON so.location_requestor_id = l.id
            WHERE pt.type = 'consu' AND (pl.link_so_id IS NULL OR so.procurement_request = 't')
        )""", (n_stock_id,))
        self.log_info(cr, uid, "US-10783-11563: The Line Destination of %s PO line(s) have been set to 'Non-Stockable'" % (cr.rowcount,))

        # Input: All others
        cr.execute("""UPDATE purchase_order_line SET reception_dest_id = %s WHERE id IN (
            SELECT pl.id FROM purchase_order_line pl
                LEFT JOIN product_product pp ON pl.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN sale_order so ON pl.link_so_id = so.id 
                LEFT JOIN stock_location l ON so.location_requestor_id = l.id
            WHERE (pl.product_id IS NULL OR pt.type NOT IN ('service_recep', 'consu')) 
                AND (pl.link_so_id IS NULL OR (so.procurement_request = 't' AND l.usage != 'customer'))
        )""", (input_id,))
        self.log_info(cr, uid, "US-10783-11563: The Line Destination of %s PO line(s) have been set to 'Input'" % (cr.rowcount,))
        return True


    def us_11181_update_supply_signature_follow_up(self, cr, uid, *a, **b):
        '''
        Update the domain of the existing ir_rule for supply signatures.
        '''
        if _get_instance_level(self, cr, uid) == 'hq':
            rr_obj = self.pool.get('ir.rule')
            suppl_sign_fup_ids = rr_obj.search(cr, uid, [('name', '=', 'Signatures Follow-up Supply Creator')])
            if suppl_sign_fup_ids:
                data = {'domain_force': "[('doc_type', 'in', ['purchase.order', 'sale.order.fo', 'sale.order.ir', 'stock.picking.in', 'stock.picking.out', 'stock.picking.pick'])]"}
                rr_obj.write(cr, uid, suppl_sign_fup_ids, data)
        return True



    # UF29.0
    def us_11399_oca_mm_target(self, cr, uid, *a, **b):
        if self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id:
            cr.execute('''
                update
                    account_target_costcenter
                set
                    is_target='f'
                where
                    is_target='t'
                    and id in
                        (select res_id from ir_model_data where name='b8c174f0-2483-11e5-9d58-0050569320a7/account_target_costcenter/723')
            ''')
        return True

    def us_11177_bn_for_kcl_items(self, cr, uid, *a, **b):
        '''
        For each KCL item with item_lot/item_exp filled, the script will try to find a corresponding BN or create a new
        one, then fill item_lot_id with the data
        '''
        kcl_item_obj = self.pool.get('composition.item')
        bn_obj = self.pool.get('stock.production.lot')
        kcl_item_ids = kcl_item_obj.search(cr, uid, [('item_kit_type', '=', 'real'), '|', ('item_lot', '!=', False), ('item_exp', '!=', False)])
        ftf = ['item_product_id', 'item_lot', 'item_exp']
        for kcl_item in kcl_item_obj.browse(cr, uid, kcl_item_ids, fields_to_fetch=ftf):
            # Skip if the product is not ED anymore
            if kcl_item.item_exp and not kcl_item.item_product_id.perishable:
                continue
            # Use fake name and date for KCL lines with missing data, caused by BN/ED attributes changes over time
            if kcl_item.item_product_id.batch_management or kcl_item.item_product_id.perishable:
                lot_name = kcl_item.item_product_id.batch_management and (kcl_item.item_lot or 'TO-BE-REPLACED') or False
                lot_date = kcl_item.item_exp or '2999-12-31'
                new_bn_id = bn_obj._get_or_create_lot(cr, uid, lot_name, lot_date, kcl_item.item_product_id.id)
                kcl_item_obj.write(cr, uid, kcl_item.id, {'item_lot_id': new_bn_id, 'item_exp': lot_date})
        return True

    def us_8968_shipments_returned(self, cr, uid, *a, **b):
        '''
        Set the state of all existing Shipments that have been returned to Returned (cancel)
        '''
        ship_obj = self.pool.get('shipment')

        ships_to_cancel = []
        nb_ships = 0
        ship_ids = ship_obj.search(cr, uid, [('state', 'in', ['done', 'delivered'])])
        for ship in ship_obj.browse(cr, uid, ship_ids, fields_to_fetch=['pack_family_memory_ids']):
            if not ship.pack_family_memory_ids:  # Skip Shipments with no Pack Family
                continue
            all_returned = True
            for fam in ship.pack_family_memory_ids:
                if not fam.not_shipped:
                    all_returned = False
                    break
            if all_returned:
                ships_to_cancel.append(ship.id)
                nb_ships += 1

        if ships_to_cancel:
            cr.execute("""UPDATE shipment SET state = 'cancel' WHERE id IN %s""", (tuple(ships_to_cancel),))
            self.log_info(cr, uid, "US-8968: %d Shipments' state have been set to Returned" % (nb_ships,))
        return True

    def us_11046_fix_standard_price_products(self, cr, uid, *a, **b):
        '''
        Set the Costing Method of all Standard Price Products to Average Price
        '''
        cr.execute("""UPDATE product_template SET cost_method = 'average' WHERE cost_method = 'standard'""")
        self.log_info(cr, uid, "US-11046: The Costing Method of %s product(s) have been set to 'Average Price'" % (cr.rowcount,))
        return True

    def us_10629_fix_partner_fo_pricelist(self, cr, uid, *a, **b):
        '''
        Set property_product_pricelist to the value of property_product_pricelist_purchase in Partners where they are
        different
        '''
        cr.execute("""
            SELECT p.id, pl.currency_id FROM res_partner p 
            LEFT JOIN product_pricelist pl on p.property_product_pricelist_purchase = pl.id 
            LEFT JOIN product_pricelist pl2 on p.property_product_pricelist = pl2.id 
            WHERE pl.currency_id != pl2.currency_id
        """)

        for x in cr.fetchall():
            fo_pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [('currency_id', '=', x[1]), ('type', '=', 'sale')])
            if fo_pricelist_ids:
                cr.execute("""UPDATE res_partner SET property_product_pricelist = %s WHERE id = %s""", (fo_pricelist_ids[0], x[0]))
        return True

    def us_11022_accrual_third_party(self, cr, uid, *a, **b):
        cr.execute('''UPDATE msf_accrual_line SET third_party_name = NULL WHERE third_party_type IS NULL AND third_party_name IS NOT NULL ''')
        return True

    def us_10904_donations_done_state(self, cr, uid, *a, **b):
        cr.execute("update account_invoice set state='done' where is_inkind_donation = 't' and state='open'")
        return True

    def us_6976_analytic_translations(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        is_coordo = instance and instance.level == 'coordo'
        aa_ids = []

        # update name with en_MF translation
        cr.execute('''
            update
                account_analytic_account
            set
                name=tr.trans
            from
                ( select a.id, coalesce(tr_en.value, tr_fr.value, '') as trans
                from
                    account_analytic_account a
                    left join ir_translation tr_en on tr_en.name='account.analytic.account,name' and tr_en.res_id = a.id and tr_en.lang='en_MF' and tr_en.xml_id not like 'analytic_account%'
                    left join ir_translation tr_fr on tr_fr.name='account.analytic.account,name' and tr_fr.res_id = a.id and tr_fr.lang='fr_MF' and tr_fr.xml_id not like 'analytic_account%'
                group by a.id, tr_en.value, tr_fr.value
                ) as tr
            where
                tr.id = account_analytic_account.id and
                tr.trans != '' and
                account_analytic_account.name != tr.trans
            returning account_analytic_account.id
        ''')
        if is_coordo:
            aa_ids = [x[0] for x in cr.fetchall()]

        self.log_info(cr, uid, "US-6976: Update name on %s analytic accounts" % (cr.rowcount, ))

        if instance.code == 'OCBCD100':
            cr.execute('''update account_analytic_account set name='56-1-16 EVAL ROUGEOLE KAMWESHA 2' where name='56-1-31 EVAL ROUGEOLE LINGOMO-DJOLU (copy)' returning id ''');
            aa_ids += [x[0] for x in cr.fetchall()]
            self.log_info(cr, uid, "US-6976: Update OCBCD100 name on %s analytic account " % (cr.rowcount, ))

        if aa_ids:
            # for FP created at coordo, trigger sync to update name to HQ
            entity = self.pool.get('sync.client.entity')._get_entity(cr)
            if aa_ids:
                cr.execute('''
                    update
                        ir_model_data d
                    set
                        last_modification=NOW(), touched='[''name'']'
                    from
                        account_analytic_account a
                    where
                        d.res_id = a.id and
                        d.model= 'account.analytic.account' and
                        d.module='sd' and
                        a.category = 'FUNDING' and
                        d.name like '%s/%%%%' and
                        d.res_id in %%s
                    ''' % (entity.identifier ,), (tuple(aa_ids), )) # not_a_user_entry
                self.log_info(cr, uid, "US-6976: Trigger FP update on %s analytic accounts" % (cr.rowcount, ))

        cr.execute("update ir_translation set name='account.analytic.account,nameko' where name='account.analytic.account,name' and type='model'")
        return True

    def us_10835_disable_iil_menu(self, cr, uid, *a, **b):
        # hide menuitems
        setup_obj = self.pool.get('esc_line.setup')
        esc_line_install = setup_obj.create(cr, uid, {})
        setup_obj.execute(cr, uid, [esc_line_install])
        return True

    # UF28.0
    def us_10885_tc_entries(self, cr, uid, *a, **b):
        current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if current_instance and current_instance.instance in ('BD_DHK_OCA', 'HQ_OCA', 'MY_CPLC_OCA', 'OCBHQ', 'OCBPK105', 'OCG_HQ'):
            cr.execute('''
                update
                    audittrail_log_line l set res_id = p.product_tmpl_id
                from
                    ir_model m, ir_model_fields f , product_product p
                where
                    m.id=l.object_id
                    and f.id = l.field_id
                    and p.id=l.res_id
                    and f.model_id != m.id
                    and m.model='product.template'
                    and p.id!=p.product_tmpl_id
                    and l.create_date > (select applied from sync_client_version where name='UF27.0')
            ''')
        return True

    def us_11195_oca_period_nr(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity') or self.pool.get('sync.server.update'):
            return True

        oc_sql = "SELECT oc FROM sync_client_entity LIMIT 1;"
        cr.execute(oc_sql)
        oc = cr.fetchone()[0]
        if oc == 'oca':
            cr.execute("""update sync_client_update_received set
                run='t', log='Set as Run by US-11195'
                where
                    run='f' and
                    sdref in ('FY2022/Jul 2022_2022-07-01', 'FY2022/Jun 2022_2022-06-01') and
                    version in (3, 4)
            """)

            self.log_info(cr, uid, "US-11195: set %d NR on periods as Run" % (cr.rowcount, ))
        return True

    def us_8417_upd_srv_loc(self, cr, uid, *a, **b):
        '''
        Set 'virtual_location' to True on the existing 'Service' location
        '''
        cr.execute('''UPDATE stock_location SET virtual_location = 't' WHERE id = %s''',
                   (self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_service')[1],))

        return True

    def us_10652_chg_partn_property_fields(self, cr, uid, *a, **b):
        '''
        Update the data of the res_partner's fields property_product_pricelist_purchase, property_product_pricelist,
        property_account_receivable and property_account_payable as they have been changed from fields.property to fields.many2one
        '''
        def_purch_plist_id = self.pool.get('product.pricelist').get_company_default_pricelist(cr, uid, 'purchase')
        def_sale_plist_id = self.pool.get('product.pricelist').get_company_default_pricelist(cr, uid, 'sale')
        cr.execute("""
            SELECT p.id, pr.value_reference, pr2.value_reference, pr3.value_reference, pr4.value_reference 
            FROM res_partner p
              LEFT JOIN ir_property pr ON pr.res_id = 'res.partner,' || p.id AND pr.name = 'property_product_pricelist_purchase' 
              LEFT JOIN ir_property pr2 ON pr2.res_id = 'res.partner,' || p.id AND pr2.name = 'property_product_pricelist' 
              LEFT JOIN ir_property pr3 ON pr3.res_id = 'res.partner,' || p.id AND pr3.name = 'property_account_receivable' 
              LEFT JOIN ir_property pr4 ON pr4.res_id = 'res.partner,' || p.id AND pr4.name = 'property_account_payable'
        """)
        nb_partners = cr.rowcount
        for res in cr.fetchall():
            cr.execute("""
                UPDATE res_partner SET property_product_pricelist_purchase = %s, property_product_pricelist = %s, 
                property_account_receivable = %s, property_account_payable = %s WHERE id = %s
            """, (res[1] and int(res[1].split(',')[-1]) or def_purch_plist_id, res[2] and int(res[2].split(',')[-1]) or def_sale_plist_id,
                  res[3] and int(res[3].split(',')[-1]) or None, res[4] and int(res[4].split(',')[-1]) or None, res[0]))
        self.log_info(cr, uid, "US-10652: The Purchase Default Currency, Field Orders Default Currency, Account Receivable and Account Payable have been updated on %d partners" % (nb_partners,))

        return True

    def us_10586_running_one_time_accrual(self, cr, uid, *a, **b):
        user_obj = self.pool.get('res.users')
        current_instance = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance:
            cr.execute('''
                UPDATE msf_accrual_line a SET state='done'
                FROM account_move_line m
                WHERE
                    a.accrual_type='one_time_accrual' AND
                    a.state='running' AND
                    a.move_line_id=m.id AND
                    m.reconcile_id IS NOT NULL
            ''')
        return True

    def us_10353_inactivation_date(self, cr, uid, *a,**b):
        for journal_id in self.pool.get('account.journal').search(cr, uid, [('is_active', '=', False)]):
            cr.execute("""
                UPDATE account_journal
                SET inactivation_date = (SELECT date(create_date)
                        FROM audittrail_log_line
                        WHERE
                            object_id in (SELECT id FROM ir_model WHERE model='account.journal') AND
                            res_id=%s AND
                            name='is_active' AND
                            coalesce(new_value,'')=''
                        order by create_date desc limit 1)
                WHERE id=%s
            """, (journal_id, journal_id))
    # UF27.0
    def store_picking_subtype(self, cr, uid, *a, **b):
        cr.execute("""
            update
                stock_move m
            set
                picking_subtype = p.subtype
            from
                stock_picking p
            where
                p.id = m.picking_id
            """)
        return True

    def us_10105_custom_order_cv(self, cr, uid, *a, **b):
        # CV is_draft field for custom ordering
        cr.execute("update account_commitment set is_draft=state='draft'")
        return True

    def us_10105_custom_order(self, cr, uid, *a, **b):
        cr.execute("update account_invoice set is_draft=state='draft'")
        # fix wrong DF on OCBHT101 / OCBHT143
        cr.execute("update account_invoice set internal_number=number where number is not null and internal_number!=number")
        # emulate: order by internal_number desc null lasts
        cr.execute("update account_invoice set internal_number='' where internal_number is null")
        return True

    def us_10475_create_user_sup_config_hq(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if instance and instance.level == 'section':
            context = {}

            group_obj = self.pool.get('res.groups')
            to_copy_ids = group_obj.search(cr, uid, [('name', '=', 'Sup_Supply_System_Administrator')], context=context)
            if not to_copy_ids:
                return True

            menu_ids = self.pool.get('ir.ui.menu').search(cr, uid, [('groups_id', '=', to_copy_ids[0]), ('active', 'in', ['t', 'f'])], context={'ir.ui.menu.full_list': True})
            menu_ids.append(self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'menu_action_res_users_whitelist')[1])
            menu_ids.append(self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'menu_users')[1])
            gp_id = group_obj.create(cr, uid, {
                'name': 'Sup_Config_HQ',
                'level': 'hq',
                'visible_res_groups': True,
                'menu_access': [(6, 0, menu_ids)],
            }, context={})

            far_obj = self.pool.get('msf_field_access_rights.field_access_rule')
            far_ids = far_obj.search(cr, uid, [('group_ids', 'in', to_copy_ids), ('instance_level', '=', 'hq'), ('active', 'in', ['t', 'f'])], context=context)
            if far_ids:
                far_obj.write(cr, uid, far_ids, {'group_ids': [(4, gp_id)]}, context=context)
            self.log_info(cr, uid, "US-10475: %d far updated" % len(far_ids))

            bar_obj = self.pool.get('msf_button_access_rights.button_access_rule')
            bar_ids = bar_obj.search(cr, uid, [('group_ids', 'in', to_copy_ids), ('active', 'in', ['t', 'f'])], context=context)
            if bar_ids:
                bar_obj.write(cr, uid, bar_ids, {'group_ids': [(4, gp_id)]}, context=context)
            self.log_info(cr, uid, "US-10475: %d bar updated" % len(bar_ids))


            acl_obj = self.pool.get('ir.model.access')
            acl_ids = acl_obj.search(cr, uid, [('group_id', '=', to_copy_ids[0])], context=context)
            acl_nb = 0
            for acl in acl_obj.read(cr, uid, acl_ids, ['perm_unlink', 'perm_write', 'perm_read', 'perm_create', 'model_id'], context=context):
                del(acl['id'])
                acl['group_id'] = gp_id
                acl['name'] = 'Sup_Config_HQ'
                acl['model_id'] = acl['model_id'] and acl['model_id'][0] or False
                acl_obj.create(cr, uid, acl, context=context)
                acl_nb += 1
            self.log_info(cr, uid, "US-10475: %d acl created on Sup_Config_HQ" % acl_nb)

            # Window Actions not applicable

            return True

    def us_10662_remove_user_tz(self, cr, uid, *a, **b):
        cr.execute("update res_users set context_tz=NULL where context_tz IS NOT NULL")
        self.log_info(cr, uid, "US-10662: Timezone removed on %d user(s)" % (cr.rowcount,))
        return True

    def us_9999_custom_accrual_order(self, cr, uid, *a, **b):
        cr.execute("update msf_accrual_line set order_accrual='1901-01-01' where state != 'draft'")
        cr.execute("update msf_accrual_line set order_accrual=document_date where state = 'draft'")
        return True

    def us_9842_remove_space(self, cr, uid, *a, **b):
        cr.execute("UPDATE hr_employee SET identification_id = TRIM(identification_id) WHERE employee_type='ex' and identification_id is not null and identification_id!=TRIM(identification_id)")
        self.log_info(cr, uid, "US-9843: extra space removed on %d expat" % (cr.rowcount,))
        return True

    def set_creator_on_employee(self, cr, uid, *a, **b):
        current_instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance:  # existing instances only
            self.pool.get('sync.trigger.something.bidir_mission').create(cr, uid, {'name': 'instance_creator_employee', 'args': current_instance.code})
        return True

    def us_9588_set_real_period_on_aji_from_cv(self, cr, uid, *a, **b):
        cr.execute('update account_analytic_line  aji set real_period_id = cv.period_id from account_commitment cv, account_commitment_line cvline where cvline.commit_id=cv.id and aji.commitment_line_id=cvline.id')
        self.log_info(cr, uid, '%d AJIs from CV: period updates.' % (cr.rowcount,))
        return True

    def us_7852_set_journal_code(self, cr, uid, *a, **b):
        self.set_journal_code_on_aji(cr, uid)
        self.pool.get('ir.config_parameter').set_param(cr, 1, 'exec_set_journal_code_on_aji', True)
        return True

    def set_journal_code_on_aji(self, cr, uid, *a, **b):
        cr.execute("""
            update account_analytic_line a set
                partner_txt=j.code
            from
                account_move_line l, account_journal j
            where
                l.id = a.move_id and
                j.id = l.transfer_journal_id and
                a.partner_txt != j.code
        """)

        self.log_info(cr, uid, "US-7852: set journal code on %d AJIs" % (cr.rowcount,))

    def us_fix_segment_version(self, cr, uid, *a, **b):
        cr.execute('delete from replenishment_segment_line_period where from_date is not null and to_date is null and value=0')
        all_fields = []
        for x in range(1, 19):
            all_fields+=['rr_fmc_%d' % x, 'rr_fmc_from_%d' % x, 'rr_fmc_to_%d' % x]
        line_obj = self.pool.get('replenishment.segment.line')

        offset = 0
        while True:
            seg_line_ids = line_obj.search(cr, uid, [], limit=200, offset=offset, order='id')
            if not seg_line_ids:
                break
            for line in line_obj.read(cr, uid, seg_line_ids, all_fields):
                all_data = ''
                for x in all_fields:
                    all_data +='%s'%line[x]
                fmc_version = hashlib.md5(''.join(all_data)).hexdigest()
                cr.execute("update replenishment_segment_line set fmc_version=%s where id=%s", (fmc_version, line['id']))
            offset += 200
        return True

    def us_9394_fix_pi_and_reason_type(self, cr, uid, *a, **b):
        '''
        Set the new Reason Type column pi_discrepancy_type to True for 'Discrepancy' and 'Other', False otherwise
        Remove the Adjustment Type of discrepancy lines in PIs that are Counted or Validated
        '''
        # Fix the RT
        data_obj = self.pool.get('ir.model.data')
        other_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
        discr_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]

        cr.execute("""UPDATE stock_reason_type SET pi_discrepancy_type = 't' WHERE id IN %s""", (tuple([other_rt_id, discr_rt_id]),))
        cr.execute("""UPDATE stock_reason_type SET pi_discrepancy_type = 'f' WHERE id NOT IN %s""", (tuple([other_rt_id, discr_rt_id]),))

        # Fix the discrepancy lines
        cr.execute("""UPDATE physical_inventory_discrepancy SET reason_type_id = NULL WHERE inventory_id IN (
            SELECT id FROM physical_inventory WHERE state NOT IN ('confirmed', 'closed', 'cancel'))
        """)
        return True

    def us_10587_fix_rt_donation_loan(self, cr, uid, *a, **b):
        '''
        Do the same updates as us_9229_fix_rt but on PPLs and Packs, and avoid Loan, Donation (standard) and Donation
        before expiry flows
        Fix the Reason Type of all Picks, OUTs, PPLs and Packs coming from a Loan, Donation (standard) or Donation
        before expiry FO
        Set the Reason Type of those documents and their moves to the one corresponding to the FO's Type
        Set the Reason Type of PICK/01410-return and PICK/01410-return-01 in NG_COOR_OCA to Goods Return
        '''
        data_obj = self.pool.get('ir.model.data')
        deli_unit_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_unit')[1]
        deli_partner_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        loan_rt = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        don_st_rt = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
        don_exp_rt = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
        goods_ret_rt = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_return')[1]

        # To Deliver Unit
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p 
                LEFT JOIN sale_order s ON p.sale_id = s.id LEFT JOIN stock_location l ON s.location_requestor_id = l.id
                WHERE p.type = 'out' AND p.subtype IN ('packing', 'ppl') AND s.procurement_request = 't' 
                    AND l.location_category = 'consumption_unit' AND p.name NOT LIKE %s AND p.name NOT LIKE %s)
        ''', (deli_unit_rt_id, '%-return%', '%-surplus%'))
        self.log_info(cr, uid, "US-10587: %d PPLs/Packs and their lines had their Reason Type set to 'Deliver Unit'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT p.id FROM stock_picking p 
                LEFT JOIN sale_order s ON p.sale_id = s.id LEFT JOIN stock_location l ON s.location_requestor_id = l.id
                WHERE p.type = 'out' AND p.subtype IN ('packing', 'ppl') AND s.procurement_request = 't' 
                    AND l.location_category = 'consumption_unit' AND p.name NOT LIKE %s AND p.name NOT LIKE %s)
        ''', (deli_unit_rt_id, '%-return%', '%-surplus%'))

        # To Deliver Partner
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND p.subtype IN ('packing', 'ppl') AND s.procurement_request = 'f'
                    AND s.order_type NOT IN ('loan', 'donation_st', 'donation_exp') AND p.name NOT LIKE %s 
                    AND p.name NOT LIKE %s)
        ''', (deli_partner_rt_id, '%-return%', '%-surplus%'))
        self.log_info(cr, uid, "US-10587: %d PPLs/Packs and their lines had their Reason Type set to 'Deliver Partner'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND p.subtype IN ('packing', 'ppl') AND s.procurement_request = 'f'
                    AND s.order_type NOT IN ('loan', 'donation_st', 'donation_exp') AND p.name NOT LIKE %s 
                    AND p.name NOT LIKE %s)
        ''', (deli_partner_rt_id, '%-return%', '%-surplus%'))

        # Loan
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND s.procurement_request = 'f' AND s.order_type = 'loan' AND p.name NOT LIKE %s 
                    AND p.name NOT LIKE %s)
        ''', (loan_rt, '%-return%', '%-surplus%'))
        self.log_info(cr, uid, "US-10587: %d OUTs/Picks/PPLs/Packs and their lines had their Reason Type set to 'Loan'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND s.procurement_request = 'f' AND s.order_type = 'loan' AND p.name NOT LIKE %s 
                    AND p.name NOT LIKE %s)
        ''', (loan_rt, '%-return%', '%-surplus%'))

        # Donation (standard)
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND s.procurement_request = 'f' AND s.order_type = 'donation_st' 
                    AND p.name NOT LIKE %s AND p.name NOT LIKE %s)
        ''', (don_st_rt, '%-return%', '%-surplus%'))
        self.log_info(cr, uid, "US-10587: %d OUTs/Picks/PPLs/Packs and their lines had their Reason Type set to 'Donation (standard)'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND s.procurement_request = 'f' AND s.order_type = 'donation_st' 
                    AND p.name NOT LIKE %s AND p.name NOT LIKE %s)
        ''', (don_st_rt, '%-return%', '%-surplus%'))

        # Donation before expiry
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND s.procurement_request = 'f' AND s.order_type = 'donation_exp' 
                    AND p.name NOT LIKE %s AND p.name NOT LIKE %s)
        ''', (don_exp_rt, '%-return%', '%-surplus%'))
        self.log_info(cr, uid, "US-10587: %d OUTs/Picks/PPLs/Packs and their lines had their Reason Type set to 'Donation before expiry'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND s.procurement_request = 'f' AND s.order_type = 'donation_exp' 
                    AND p.name NOT LIKE %s AND p.name NOT LIKE %s)
        ''', (don_exp_rt, '%-return%', '%-surplus%'))

        # Fix the RT of a claim PICKs in NG_COOR_OCA
        msf_instance = self.pool.get('res.company')._get_instance_record(cr, uid)
        if msf_instance and msf_instance.instance == 'NG_COOR_OCA':
            cr.execute('''UPDATE stock_picking SET reason_type_id = %s WHERE id IN (11193, 13420)''', (goods_ret_rt,))
            cr.execute('''UPDATE stock_move SET reason_type_id = %s WHERE picking_id IN (11193, 13420)''', (goods_ret_rt,))
            self.log_info(cr, uid, "US-10587: PICK/01410-return, PICK/01410-return-01 and their lines had their Reason Type set to 'Goods Return'")

        return True


    def us_9406_create_bar(self, cr, uid, *a, **b):
        if _get_instance_level(self, cr, uid) != 'hq':
            return True

        creator_b_names = ['add_user_signatures', 'action_close_signature', 'activate_role', 'disable_role', 'activate_offline', 'disable_offline', 'activate_offline_reset']
        sign_b_names = ['open_sign_wizard', 'action_unsign']
        bar_obj = self.pool.get('msf_button_access_rights.button_access_rule')
        for group_name, model, b_names in [
            ('Sign_document_creator_finance', ['account.invoice', 'account.bank.statement'], creator_b_names),
            ('Sign_document_creator_supply', ['purchase.order', 'stock.picking', 'sale.order'], creator_b_names),
            ('Sign_user', ['account.invoice', 'account.bank.statement', 'purchase.order', 'stock.picking', 'sale.order'], sign_b_names)
        ]:
            group_ids = self.pool.get('res.groups').search(cr, uid, [('name', '=', group_name)])
            if not group_ids:
                group_id = self.pool.get('res.groups').create(cr, uid, {'name': group_name})
            else:
                group_id = group_ids[0]

            if model and b_names:
                bar_ids = bar_obj.search(cr, uid, [('name', 'in', b_names), ('model_id', 'in', model)])
                bar_obj.write(cr, uid, bar_ids, {'group_ids': [(6, 0, [group_id])]})

        user_manager = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'User_Manager')])
        if user_manager:
            bar_ids = bar_obj.search(cr, uid, [('name', '=', 'reset_signature'), ('model_id', '=', 'res.users')])
            bar_ids += bar_obj.search(cr, uid, [('name', '=', 'save'), ('model_id', '=', 'signature.change_date')])
            if bar_ids:
                bar_obj.write(cr, uid, bar_ids, {'group_ids': [(6, 0, [user_manager[0]])]})
        for group_name, menus in [
            ('Sign_user', ['base.menu_administration', 'base.menu_users', 'useability_dashboard_and_menu.signature_follow_up_menu', 'useability_dashboard_and_menu.my_signature_menu']),
            ('User_Manager', ['base.signature_image_menu']),
            ('Sign_document_creator_finance', ['base.menu_administration', 'base.menu_users', 'useability_dashboard_and_menu.signature_follow_up_menu', 'base.signature_image_menu']),
            ('Sign_document_creator_supply', ['base.menu_administration', 'base.menu_users', 'useability_dashboard_and_menu.signature_follow_up_menu', 'base.signature_image_menu']),
        ]:
            group_ids = self.pool.get('res.groups').search(cr, uid, [('name', '=', group_name)])
            if not group_ids:
                continue
            for menu in menus:
                module, xmlid = menu.split('.')
                try:
                    menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, xmlid)[1]
                except:
                    continue
                self.pool.get('ir.ui.menu').write(cr, uid, [menu_id], {'groups_id': [(4, group_ids[0])]})
        return True

    def us_9406_create_record_rules(self, cr, uid, *a, **b):
        if _get_instance_level(self, cr, uid) != 'hq':
            return True
        sign_user_id = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'Sign_user')])
        supply_creator_id = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'Sign_document_creator_supply')])
        finance_creator_id = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'Sign_document_creator_finance')])
        model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', 'signature.follow_up')])
        data = {
            'model_id': model_id[0],
            'perm_read': True,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
        }
        rr_obj = self.pool.get('ir.rule')
        data.update({
            'name': 'Signatures Follow-up Supply Creator',
            'domain_force': "[('doc_type', 'in', ['purchase.order', 'sale.order', 'stock.picking'])]",
            'groups': [(6, 0, supply_creator_id)],
        })
        rr_obj.create(cr, uid, data)
        data.update({
            'name': 'Signatures Follow-up Finance Creator',
            'domain_force': "[('doc_type', 'in', ['account.bank.statement.cash', 'account.bank.statement.bank', 'account.invoice.si', 'account.invoice.donation'])]",
            'groups': [(6, 0, finance_creator_id)],
        })
        rr_obj.create(cr, uid, data)
        data.update({
            'name': 'Signatures Follow-up Sign_User',
            'domain_force': "[('user_id', '=', user.id)]",
            'groups': [(6, 0, sign_user_id)],
        })
        rr_obj.create(cr, uid, data)
        return True

    def us_9406_create_common_acl(self, cr, uid, *a, **b):
        cr.execute("delete from ir_act_window where id in (select res_id from ir_model_data where name='account_hq_entries_action_hq_entries_import_wizard')")
        cr.execute("delete from ir_model_data where name='account_hq_entries_action_hq_entries_import_wizard'")
        if _get_instance_level(self, cr, uid) != 'hq':
            return True
        model_obj = self.pool.get('ir.model')
        acl_obj = self.pool.get('ir.model.access')
        for model in ['signature', 'signature.object', 'signature.line', 'signature.image', 'signature.follow_up']:
            model_id = model_obj.search(cr, uid, [('model', '=', model)])
            acl_obj.create(cr, uid, {
                'name': 'common',
                'model_id': model_id[0],
                'perm_read': True,
                'perm_create': model == 'signature',
            })
        return True

    def us_9406_empty_sign(self, cr, uid, *a, **b):
        # this script must always be run : i.e on past and new instances to hide menu

        for model, table in [
                ('purchase.order', 'purchase_order'), ('sale.order', 'sale_order'),
                ('account.bank.statement', 'account_bank_statement'),
                ('account.invoice', 'account_invoice'),
                ('stock.picking', 'stock_picking'),
        ]:
            cr.execute('select id from %s where signature_id is null' % (table, )) # not_a_user_entry
            for x in cr.fetchall():
                cr.execute("insert into signature (signature_res_model, signature_res_id) values (%s, %s) returning id", (model, x[0]))
                a = cr.fetchone()
                cr.execute("update %s set signature_id=%%s where id=%%s" % (table,) , (a[0], x[0])) # not_a_user_entry
        # hide menuitems
        setup_obj = self.pool.get('signature.setup')
        sign_install = setup_obj.create(cr, uid, {})
        setup_obj.execute(cr, uid, [sign_install])

        return True

    # UF26.0
    def fix_us_10163_ocbhq_funct_amount(self, cr, uid, *a, **b):
        ''' OCBHQ: fix amounts on EOY-2021-14020-OCBVE101-VES'''
        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if instance and instance.name == 'OCBHQ':
            cr.execute('''update account_move_line set credit_currency='636077529292.81' where id = (select res_id from ir_model_data where name='8e980ca1-dee3-11e5-a9b9-94659c5434c6/account_move_line/226517')''')
            cr.execute('''update account_move_line set debit_currency='636077529292.81' where id = (select res_id from ir_model_data where name='8e980ca1-dee3-11e5-a9b9-94659c5434c6/account_move_line/226518')''')

        return True

    def us_8259_remove_currency_table_wkf(self, cr, uid, *a, **b):
        cr.execute("delete from wkf_workitem where act_id in (select id from wkf_activity where wkf_id = (select id from wkf where name='wkf.res.currency.table' and osv='res.currency.table'))")
        cr.execute("delete from wkf_activity where wkf_id = (select id from wkf where name='wkf.res.currency.table' and osv='res.currency.table')")
        cr.execute("delete from wkf where name='wkf.res.currency.table' and osv='res.currency.table'")
        return True

    def us_10090_new_dep_journals(self, cr, uid, *a, **b):
        """
        Creates the DEP G/L journals in all OCB instances and DEP analytic journals in all existing instances.
        This is done in Python as the objects created must sync normally.
        """
        user_obj = self.pool.get('res.users')
        analytic_journal_obj = self.pool.get('account.analytic.journal')
        journal_obj = self.pool.get('account.journal')
        current_instance = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance:  # existing instances only
            # DEP analytic journal
            dep_analytic_journal_ids = analytic_journal_obj.search(cr, uid,
                                                                   [('code', '=', 'DEP'),
                                                                    ('type', '=', 'depreciation'),
                                                                    ('is_current_instance', '=', True)])
            if dep_analytic_journal_ids:  # just in case the journal has been created before the release
                dep_analytic_journal_id = dep_analytic_journal_ids[0]
            else:
                dep_analytic_vals = {
                    # Prop. Instance: by default the current one is used
                    'code': 'DEP',
                    'name': 'Depreciation',
                    'type': 'depreciation',
                }
                dep_analytic_journal_id = analytic_journal_obj.create(cr, uid, dep_analytic_vals)
            # DEP G/L journal in all OCB instances
            if current_instance.name.startswith('OCB')\
                    and not journal_obj.search_exist(cr, uid, [('code', '=', 'DEP'), ('type', '=', 'depreciation'),
                                                               ('is_current_instance', '=', True),
                                                               ('analytic_journal_id', '=', dep_analytic_journal_id)]):
                dep_vals = {
                    # Prop. Instance: by default the current one is used
                    'code': 'DEP',
                    'name': 'Depreciation',
                    'type': 'depreciation',
                    'analytic_journal_id': dep_analytic_journal_id,
                }
                journal_obj.create(cr, uid, dep_vals)
        return True

    def us_10010_hide_import_export_product_menu(self, cr, uid, *a, **b):
        data_obj = self.pool.get('ir.model.data')

        instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if not instance:
            return True

        import_prod_menu_id = data_obj.get_object_reference(cr, uid, 'import_data', 'menu_action_import_products')[1]
        update_prod_menu_id = data_obj.get_object_reference(cr, uid, 'import_data', 'menu_action_update_products')[1]
        self.pool.get('ir.ui.menu').write(cr, uid, [import_prod_menu_id, update_prod_menu_id], {'active': instance.level != 'project'}, context={})
        return True

    def us_8428_pi_type_migration(self, cr, uid, *a, **b):
        '''
        In PIs, if full_inventory == True, set the type to 'full'
        '''
        cr.execute("""UPDATE physical_inventory SET type = 'full' WHERE full_inventory = 't'""")
        cr.execute("""UPDATE physical_inventory SET type = 'partial' WHERE type is null""")

    def us_9229_fix_rt(self, cr, uid, *a, **b):
        '''
        Updates to do:
            - All OUTs and Picks plus their lines created from IR with Ext CU to have RT Deliver Unit
            - All OUTs and Picks plus their lines created from FO to have RT Deliver Partner
            - All OUT-CONSOs plus their lines to have RT Consumption Report
        '''
        data_obj = self.pool.get('ir.model.data')
        deli_unit_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_unit')[1]
        deli_partner_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        consu_rep_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_consumption_report')[1]

        # To Deliver Unit
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p 
                LEFT JOIN sale_order s ON p.sale_id = s.id LEFT JOIN stock_location l ON s.location_requestor_id = l.id
                WHERE p.type = 'out' AND p.subtype IN ('standard', 'picking') AND s.procurement_request = 't' 
                    AND l.location_category = 'consumption_unit')
        ''', (deli_unit_rt_id,))
        self.log_info(cr, uid, "US-9229: %d OUTs/Picks and their lines had their Reason Type set to 'Deliver Unit'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT p.id FROM stock_picking p 
                LEFT JOIN sale_order s ON p.sale_id = s.id LEFT JOIN stock_location l ON s.location_requestor_id = l.id
                WHERE p.type = 'out' AND p.subtype IN ('standard', 'picking') AND s.procurement_request = 't' 
                    AND l.location_category = 'consumption_unit')
        ''', (deli_unit_rt_id,))

        # To Deliver Partner
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND p.subtype IN ('standard', 'picking') AND s.procurement_request = 'f')
        ''', (deli_partner_rt_id,))
        self.log_info(cr, uid, "US-9229: %d OUTs/Picks and their lines had their Reason Type set to 'Deliver Partner'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT p.id FROM stock_picking p LEFT JOIN sale_order s ON p.sale_id = s.id
                WHERE p.type = 'out' AND p.subtype IN ('standard', 'picking') AND s.procurement_request = 'f')
        ''', (deli_partner_rt_id,))

        # To Consumption Report
        cr.execute('''
            UPDATE stock_picking SET reason_type_id = %s 
            WHERE id IN (SELECT id FROM stock_picking WHERE type = 'out' AND subtype IN ('standard', 'picking') 
                AND rac_id IS NOT NULL)
        ''', (consu_rep_rt_id,))
        self.log_info(cr, uid, "US-9229: %d OUT-CONSOs and their lines had their Reason Type set to 'Consumption Report'" % (cr.rowcount,))
        cr.execute('''
            UPDATE stock_move SET reason_type_id = %s 
            WHERE picking_id IN (SELECT id FROM stock_picking WHERE type = 'out' AND subtype IN ('standard', 'picking') 
                AND rac_id IS NOT NULL)
        ''', (consu_rep_rt_id,))

        return True

    # UF25.0
    def us_8451_split_rr(self, cr, uid, *a, **b):
        if not cr.column_exists('replenishment_segment_line', 'rr_fmc_1') or not cr.column_exists('replenishment_segment_line', 'rr_max_1'):
            return True

        for x in range(1, 19):
            cr.execute('''
            insert into replenishment_segment_line_period (line_id, value, from_date, to_date, max_value)
                select id, rr_fmc_%(x)s, rr_fmc_from_%(x)s, rr_fmc_to_%(x)s, rr_max_%(x)s
                from replenishment_segment_line
                where rr_fmc_%(x)s is not null
            ''', {'x': x})
        cr.execute('''update replenishment_segment_line_period set from_date='2020-01-01' where from_date is null and value is not null''')
        cr.execute('''update replenishment_segment_line_period set to_date='2222-02-28' where to_date is null and value is not null''')
        return True

    def us_5722_update_accruals(self, cr, uid, *a, **b):
        """
        Updates the existing accruals:
        - A) renames the states:
          ==> Partially Posted becomes Running, and Posted becomes Done
        - B) some pieces of data are now handled at line level:
          ==> moves them from the accrual itself (msf.accrual.line) to the expense line (msf.accrual.line.expense)
        - C) initializes the sequence on the existing Accruals so that the line numbers are consistent (Line number = 1 for point B)
        - D) sets the value to use for the fields "entry_sequence" (previously based on the JI linked to the global AD)
        """
        if self.pool.get('sync.client.entity') and not self.pool.get('sync.server.update'):  # existing instances
            accrual_obj = self.pool.get('msf.accrual.line')
            ml_obj = self.pool.get('account.move.line')
            cr.execute("UPDATE msf_accrual_line SET state = 'running' WHERE state = 'partially_posted'")
            self.log_info(cr, uid, '%d Accrual(s) set to: Running.' % (cr.rowcount,))
            cr.execute("UPDATE msf_accrual_line SET state = 'done' WHERE state = 'posted'")
            self.log_info(cr, uid, '%d Accrual(s) set to: Done.' % (cr.rowcount,))
            # NOTE: in all the Accruals created before this ticket there is NO sequence_id and NO Expense Lines
            cr.execute('''SELECT id, description, reference, expense_account_id, accrual_amount, state, move_line_id
                          FROM msf_accrual_line''')
            accruals = cr.fetchall()
            for accrual_data in accruals:
                accrual_id = accrual_data[0]
                # get the entry_sequence to set at doc level
                entry_seq = ''
                move_line_id = accrual_data[6]
                if accrual_data[5] != 'draft' and move_line_id:
                    ml = ml_obj.browse(cr, uid, move_line_id, fields_to_fetch=['move_id'])
                    entry_seq = ml and ml.move_id.name or ''
                # initialize the sequence for line numbering (ir_sequences are not synchronized)
                line_seq_id = accrual_obj.create_sequence(cr, uid)
                cr.execute("UPDATE msf_accrual_line "
                           "SET entry_sequence = %s, sequence_id = %s "
                           "WHERE id = %s", (entry_seq, line_seq_id, accrual_id))
                new_expense_line_vals = {
                    # the line_number will be automatically filled in, using the sequence created above
                    # no analytic_distribution_id is defined on the line, the global AD is kept
                    'accrual_line_id': accrual_id,
                    'description': accrual_data[1],
                    'reference': accrual_data[2] or '',
                    'expense_account_id': accrual_data[3],
                    'accrual_amount': accrual_data[4] or 0.0,
                }
                # call the standard "create" method on Accrual Expense Lines, which are not synchronized
                self.pool.get('msf.accrual.line.expense').create(cr, uid, new_expense_line_vals)
            self.log_info(cr, uid, '%d Accrual Expense Line(s) created.' % (len(accruals),))
        return True

    def fol_order_id_join_change_rules(self, cr, uid, *a, **b):
        """
            order_id now uses sql join for queries like order_id.state = draft
            update client sync rules to not generate sync messages for IR lines
            (this changes cannot wait for the following sync)
        """
        if not self.pool.get('sync.client.entity'):
            # exclude new instances
            return True
        cr.execute('''update sync_client_message_rule
                set
                    domain=$$[('order_id.partner_type', '!=', 'external'), ('state', '!=', 'draft'), ('order_id.procurement_request', '=', False), ('product_uom_qty', '!=', 0.0), '!', '&', ('order_id.fo_created_by_po_sync', '=', False), ('order_id.state', '=', 'draft')]$$,
                    wait_while=$$[('order_id.procurement_request', '=', False), ('order_id.state', 'in', ['draft', 'draft_p']), ('order_id.partner_type', 'not in', ['external', 'esc']), ('order_id.client_order_ref', '=', False)]$$
                where
                    remote_call = 'purchase.order.line.sol_update_original_pol'
        ''')
        return True

    def us_6475_set_has_tax_on_po(self, cr, uid, *a, **b):
        cr.execute('''
            update purchase_order
                set has_tax_at_line_level='t'
            where
                id in (
                select po.id
                    from
                purchase_order_line pol, purchase_order po, purchase_order_taxe tax
                where
                    po.state in ('draft', 'draft_p', 'validated', 'validated_p') and
                    pol.order_id = po.id and
                    pol.state not in ('cancel', 'cancel_r') and
                    tax.ord_id = pol.id
            )
        ''')
        self.log_info(cr, uid, 'US-6475: set PO has tax on %d records' % cr.rowcount)
        return True

    def us_7791_gdpr_patch(self, cr, uid, *a, **b):
        cr.execute("""UPDATE hr_employee
        SET
        birthday = NULL,
        gender = NULL,
        marital = NULL,
        mobile_phone = NULL,
        notes = NULL,
        private_phone = NULL,
        work_email = NULL,
        work_phone = NULL,
        country_id = NULL,
        ssnid = NULL
        WHERE employee_type = 'local';
        """)
        self.log_info(cr, uid, 'US-7791 : GDPR patch applied on %d rows' % (cr.rowcount,))
        return True


    def us_9173_fix_msf_customer_location(self, cr, uid, *a, **b):
        '''
        Remove the unbreakable spaces from the default 'MSF Cutsomer' location
        Rename manually created 'MSF Customer' locations into 'Other_MSF_Customer
        '''
        msf_cust_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')[1]

        # Removing the unbreakable space from the location and the translations
        cr.execute("""UPDATE stock_location SET name = replace(name, E'\u00a0', ' ') WHERE id = %s""", (msf_cust_id,))
        cr.execute("""UPDATE ir_translation SET src = replace(src, E'\u00a0', ' '), value = replace(value, E'\u00a0', ' ') 
            WHERE name = 'stock.location,name' AND res_id = %s""", (msf_cust_id,))

        # Renaming the non-default 'MSF Customer' locations and their translations
        cr.execute("""UPDATE stock_location SET name = 'Other_MSF_Customer' WHERE name = 'MSF Customer' AND id != %s""", (msf_cust_id,))
        cr.execute("""UPDATE ir_translation SET src = 'Other_MSF_Customer', value = 'Other_MSF_Customer' 
            WHERE name = 'stock.location,name' AND src = 'MSF Customer' AND res_id != %s
        """, (msf_cust_id,))

        return True

    # UF24.1
    def us_9849_trigger_upd_former_nsl(self, cr, uid, *a, **b):
        # UD prod changer from NSL to ST/NS => trigger sync to update active field on missions
        if not self.pool.get('sync.client.entity'):
            # exclude new instances
            return True
        if _get_instance_level(self, cr, uid) == 'hq':
            cr.execute("""
                update
                    product_product
                set
                    active_change_date=NOW()
                where id in (
                    select
                        p.id
                    from
                        product_product p, product_international_status c
                    where
                        p.international_status = c.id and
                        c.code = 'unidata' and
                        p.active = 't' and
                        p.standard_ok != 'non_standard_local' and
                        p.product_tmpl_id in (
                            select
                                distinct(res_id)
                            from
                                audittrail_log_line
                            where
                                old_value_text='non_standard_local' and
                                object_id = (select id from ir_model where model='product.template')
                        )
                )
            """)
            self.log_info(cr, uid, 'US-9849: %d updates' % (cr.rowcount, ))
        return True

    def us_9833_set_pick_from_wkf(self, cr, uid, *a, **b):
        cr.execute("""
            update
                stock_picking
            set
                from_wkf='t'
            where
                from_wkf='f' and
                sale_id is not null and
                type = 'out' and
                subtype in ('standard', 'picking')
        """)
        self.log_info(cr, uid, 'US-9833: %d OUT/Pick fixed' % (cr.rowcount,))
        return True


    # UF24.0

    def us_9570_ocb_auto_sync_time(self, cr, uid, *a, **b):
        entity_obj = self.pool.get('sync.client.entity')
        if entity_obj and entity_obj.get_entity(cr, uid).oc == 'ocb':
            cr.execute("SAVEPOINT us_9570")
            cron_obj = self.pool.get('ir.cron')
            cron_dom = [('model', '=', 'sync.client.entity'), ('function', '=', 'sync_threaded')]
            cron_id = cron_obj.search(cr, uid, cron_dom + [('active', 'in', ['t', 'f'])])
            if not cron_id:
                self.log_info(cr, uid, 'US-9570: patch not applied, cron job not found !')
                return True
            if len(cron_id) > 1:
                cron_id = cron_obj.search(cr, uid, cron_dom + [('active', '=', True)])
                if not cron_id or len(cron_id) > 1:
                    self.log_info(cr, uid, 'US-9570: patch not applied, multiple cron found !')
                    return True

            cron = cron_obj.browse(cr, uid, cron_id[0])
            if cron.interval_number == 12 and cron.interval_type == 'hours':
                nextcall = datetime.strptime(cron.nextcall, '%Y-%m-%d %H:%M:%S')
                if 7 * 60 <= nextcall.hour * 60 + nextcall.minute < 9 * 60 or \
                        19 * 60 <= nextcall.hour * 60 + nextcall.minute < 21 * 60:
                    self.log_info(cr, uid, 'US-9570: patch not applied, conditions already met')
                    return True

            now = datetime.now()
            minute = random.randint(1, 59)
            if now.hour < 5:
                hour = random.randint(7 , 8)
                days = 0 # same day
            elif now.hour < 17:
                hour = random.randint(19 ,20)
                days = 0 # same day
            else:
                hour = random.randint(7 , 8)
                days = 1 # next day

            cr.execute('update sync_client_sync_server_connection set automatic_patching_hour_from=19, automatic_patching_hour_to=8')
            nextcall_to_set = (now+relativedelta(hour=hour, minute=minute, days=days)).strftime('%Y-%m-%d %H:%M:%S')
            try:
                cron_obj.write(cr, uid, cron.id, {'nextcall': nextcall_to_set, 'interval_number': 12, 'interval_type': 'hours'})
                self.log_info(cr, uid, 'US-9570: patch applied %s' %  nextcall_to_set)
            except:
                cr.execute("ROLLBACK TO SAVEPOINT us_9570")
                self.log_info(cr, uid, 'US-9570: patch not applied, error during save !')

        return True


    def us_9577_display_manual_cv(self, cr, uid, *a, **b):
        cr.execute("UPDATE account_commitment SET cv_flow_type='supplier' WHERE cv_flow_type IS NULL")
        self.log_info(cr, uid, '%d manual CV visible' % (cr.rowcount,))
        return True

    def us_9160_hq_prod_touch_donation_account(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity'):
            # exclude new instances
            return True
        if _get_instance_level(self, cr, uid) == 'hq':
            cr.execute("""
                UPDATE ir_model_data
                SET touched ='[''donation_expense_account'']', last_modification = NOW()
                WHERE module='sd'
                AND model='product.product'
                AND res_id IN (
                    SELECT id
                    FROM product_product
                    WHERE donation_expense_account is not null and active='t'
                );
            """)
            self.log_info(cr, uid, 'Trigger donation_expense_account on %d products' % (cr.rowcount,))
        return True

    def us_8870_partner_instance_creator(self, cr, uid, *a, **b):
        entity = self.pool.get('sync.client.entity')
        if entity:
            b = time.time()
            cr.execute("""
                update res_partner p
                    set instance_creator=instance.code
                    from
                        ir_model_data d,
                        msf_instance instance
                    where
                        d.module = 'sd' and
                        d.model = 'res.partner' and
                        d.res_id = p.id and
                        instance.instance_identifier = split_part(d.name, '/', 1)
            """)

            self.log_info(cr, uid, 'Instance creator set on %d partners in %d sec' % (cr.rowcount, time.time() - b))
        return True

    def us_9436_set_dest_on_ir_out_converted(self, cr, uid, *a, **b):
        data_obj = self.pool.get('ir.model.data')
        distrib = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_distribution')[1]
        msf_customer = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')[1]
        cr.execute('''
            update stock_move m set location_dest_id=ir.location_requestor_id
                from
                    stock_picking p, sale_order ir
                where
                    p.id = m.picking_id and
                    p.shipment_id is not NULL and
                    ir.id = p.sale_id and
                    ir.procurement_request = 't' and
                    m.location_id = %s and
                    m.location_dest_id = %s
        ''', (distrib, msf_customer))
        self.log_info(cr, uid, 'US-9436: %d destinations changed on shipment linked to IR' % cr.rowcount)
        return True

    def us_8449_migrate_rr_min_max_auto_to_periods(self, cr, uid, *a, **b):
        if cr.column_exists('replenishment_segment_line', 'min_qty') and \
                cr.column_exists('replenishment_segment_line', 'rr_fmc_1') and \
                cr.column_exists('replenishment_segment_line', 'rr_max_1'):
            cr.execute("""update replenishment_segment_line line set rr_fmc_1=min_qty, rr_max_1=max_qty, min_qty=NULL, max_qty=NULL
                from replenishment_segment seg
                where
                    seg.id = line.segment_id and
                    seg.rule='minmax'
            """)

        if cr.column_exists('replenishment_segment_line', 'auto_qty') and cr.column_exists('replenishment_segment_line', 'rr_fmc_1'):
            cr.execute("""update replenishment_segment_line line set rr_fmc_1=auto_qty, auto_qty=NULL
                from replenishment_segment seg
                where
                    seg.id = line.segment_id and
                    seg.rule='auto'
            """)
        return True

    def us_9391_fix_non_picks(self, cr, uid, *a, **b):
        '''
        Fix the subtypes and names of INs/INTs with PICK names
        '''
        # INs from scratch with PICK name
        cr.execute("""
            UPDATE stock_picking SET name = 'IN/' || name, subtype = 'standard' 
            WHERE id IN (SELECT id FROM stock_picking WHERE name LIKE 'PICK%' AND name NOT LIKE '%return' AND type = 'in' AND subtype = 'picking')
        """)

        # INTs from scratch with PICK name
        cr.execute("""
            UPDATE stock_picking SET name = 'INT/' || name, subtype = 'standard' 
            WHERE id IN (SELECT id FROM stock_picking WHERE name LIKE 'PICK%' AND name NOT LIKE '%return' AND type = 'internal' AND subtype = 'picking')
        """)
        return True

    def us_9143_oca_change_dest_on_esc_po(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity') or self.pool.get('sync.server.update'):
            return True

        oc_sql = "SELECT oc FROM sync_client_entity LIMIT 1;"
        cr.execute(oc_sql)
        oc = cr.fetchone()[0]
        if oc == 'oca':
            dest_id = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', 'OPS'), ('category', '=', 'DEST')])
            if dest_id:
                # header AD
                cr.execute('''
                    update funding_pool_distribution_line dist_line set destination_id=%(dest)s
                        from
                            purchase_order po
                        where
                            po.partner_type='esc' and
                            po.state in ('validated_p', 'validated') and
                            po.analytic_distribution_id = dist_line.distribution_id and
                            dist_line.destination_id != %(dest)s
                    ''', {'dest': dest_id[0]})

                header_fp = cr.rowcount
                cr.execute('''
                    update cost_center_distribution_line dist_line set destination_id=%(dest)s
                        from
                            purchase_order po
                        where
                            po.partner_type='esc' and
                            po.state in ('validated_p', 'validated') and
                            po.analytic_distribution_id = dist_line.distribution_id and
                            dist_line.destination_id != %(dest)s
                    ''', {'dest': dest_id[0]})
                header_cc = cr.rowcount

                # AD line
                cr.execute('''
                    update funding_pool_distribution_line dist_line set destination_id=%(dest)s
                        from
                            purchase_order po, purchase_order_line pol
                        where
                            po.partner_type='esc' and
                            pol.order_id = po.id and
                            pol.state in ('validated_n', 'validated') and
                            pol.analytic_distribution_id = dist_line.distribution_id and
                            dist_line.destination_id != %(dest)s
                    ''', {'dest': dest_id[0]})

                line_fp = cr.rowcount
                cr.execute('''
                    update cost_center_distribution_line dist_line set destination_id=%(dest)s
                        from
                            purchase_order po, purchase_order_line pol
                        where
                            po.partner_type='esc' and
                            pol.order_id = po.id and
                            pol.state in ('validated_n', 'validated') and
                            pol.analytic_distribution_id = dist_line.distribution_id and
                            dist_line.destination_id != %(dest)s
                    ''', {'dest': dest_id[0]})
                line_cc = cr.rowcount

                self.log_info(cr, uid, 'US-9143: Dest changed on headers: fp: %d, cc: %d, on lines fp: %d, cc: %d' % (header_fp, header_cc, line_fp, line_cc))
        return True

    # UF23.0
    def us_8839_cv_from_fo(self, cr, uid, *a, **b):
        if cr.column_exists('account_commitment_line', 'po_line_product_id'):
            cr.execute('''update account_commitment_line set line_product_id=po_line_product_id, line_number=po_line_number''')
            cr.execute('''update
                account_commitment cv
                set cv_flow_type='supplier'
                from
                    purchase_order po
                where
                    po.id = cv.purchase_id
                ''')

        # hide menu
        menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'menu_account_commitment_from_fo')[1]
        self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': False})
        return True

    def us_8585_new_isi_journals(self, cr, uid, *a, **b):
        """
        Creates the ISI G/L and analytic journals in all existing instances.
        This is done in Python as the objects created must sync normally.
        """
        user_obj = self.pool.get('res.users')
        analytic_journal_obj = self.pool.get('account.analytic.journal')
        journal_obj = self.pool.get('account.journal')
        current_instance = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance:  # existing instances only
            # ISI analytic journal
            isi_analytic_journal_ids = analytic_journal_obj.search(cr, uid,
                                                                   [('code', '=', 'ISI'),
                                                                    ('type', '=', 'purchase'),
                                                                    ('is_current_instance', '=', True)])
            if isi_analytic_journal_ids:  # just in case the journal has been created before the release
                isi_analytic_journal_id = isi_analytic_journal_ids[0]
            else:
                isi_analytic_vals = {
                    # Prop. Instance: by default the current one is used
                    'code': 'ISI',
                    'name': 'Intersection Supplier Invoice',
                    'type': 'purchase',
                }
                isi_analytic_journal_id = analytic_journal_obj.create(cr, uid, isi_analytic_vals)
            # ISI G/L journal
            if not journal_obj.search_exist(cr, uid, [('code', '=', 'ISI'),  # just in case the journal has been created before the release
                                                      ('type', '=', 'purchase'),
                                                      ('is_current_instance', '=', True),
                                                      ('analytic_journal_id', '=', isi_analytic_journal_id)]):
                isi_vals = {
                    # Prop. Instance: by default the current one is used
                    'code': 'ISI',
                    'name': 'Intersection Supplier Invoice',
                    'type': 'purchase',
                    'analytic_journal_id': isi_analytic_journal_id,
                }
                journal_obj.create(cr, uid, isi_vals)
        return True

    def us_9044_add_location_colors(self, cr, uid, *a, **b):
        '''
        Add the search_color to each location which needs one
        Changes the name 'Quarantine' into 'Quarantine / For Scrap' where it is necessary
        Changes the name 'Quarantine (before scrap)' into 'Expired / Damaged / For Scrap' where it is necessary
        '''
        obj_data = self.pool.get('ir.model.data')
        # Get the locations ids
        stock = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        med = obj_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_medical')[1]
        log = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_logistic')[1]
        cd = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        inp = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
        p_qua = obj_data.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_quarantine_view')[1]
        qua = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_analyze')[1]
        exp = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]

        # Main stocks (Stock, LOG, MED): dimgray
        cr.execute("""UPDATE stock_location SET search_color = 'dimgray' WHERE id IN %s""", (tuple([stock, med, log]),))

        # Cross docking & Input: darkorchid
        cr.execute("""UPDATE stock_location SET search_color = 'darkorchid' WHERE id IN %s""", (tuple([cd, inp]),))

        # Quarantine (analyze): darkorange
        cr.execute("""UPDATE stock_location SET search_color = 'darkorange' WHERE id = %s""", (qua,))

        # Expired / Damaged / For Scrap: sandybrown
        cr.execute("""UPDATE stock_location SET name = 'Expired / Damaged / For Scrap', search_color = 'sandybrown' WHERE id = %s""", (exp,))

        # Fix the name of Quarantine location
        cr.execute("""UPDATE stock_location SET name = 'Quarantine / For Scrap' WHERE id = %s""", (p_qua,))

        # Fix the remote_location_name in stock_mission_report_line_location
        cr.execute("""UPDATE stock_mission_report_line_location SET remote_location_name = 'Expired / Damaged / For Scrap' 
            WHERE id IN (SELECT id FROM stock_mission_report_line_location WHERE remote_location_name = 'Quarantine (before scrap)')""")
        return True

    # UF22.1
    def us_8336_update_msr_used(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity'):
            # exclude new instances
            return True

        if _get_instance_level(self, cr, uid) == 'hq':
            # exclude hq
            return True

        doc_field_error_dom = [
            ('stock_move', 'product_id'),
            ('stock_production_lot', 'product_id'),
            ('purchase_order_line', 'product_id'),
            ('sale_order_line', 'product_id'),
            ('tender_line', 'product_id'),
            ('physical_inventory_counting', 'product_id'),
            ('initial_stock_inventory_line', 'product_id'),
            ('real_average_consumption_line', 'product_id'),
            ('replenishment_segment_line', 'product_id'),
            ('product_list_line', 'name'),
            ('composition_kit', 'composition_product_id'),
            ('composition_item', 'item_product_id'),
        ]
        report_ids = self.pool.get('stock.mission.report').search(cr, uid, [('local_report', '=', True), ('full_view', '=', False)])
        if not report_ids:
            return True
        report_id = report_ids[0]
        for table, foreign_field in doc_field_error_dom:
            # set used_in_transaction='t'
            cr.execute('''
                update
                    stock_mission_report_line l
                set
                    used_in_transaction='t'
                from
                    ''' + table + ''' ft
                where
                    coalesce(l.used_in_transaction,'f')='f' and
                    l.mission_report_id = %s and
                    ft.''' + foreign_field + ''' = l.product_id
                ''', (report_id, )) # not_a_user_entry

        cr.execute('''
            select d.name
            from ir_model_data d, stock_mission_report_line l
            where
                l.id = d.res_id and
                used_in_transaction='t' and
                d.model='stock.mission.report.line' and
                l.mission_report_id = %s
        ''', (report_id,))
        if cr.rowcount:
            zipstr = base64.b64encode(zlib.compress(bytes(','.join([x[0] for x in cr.fetchall()]), 'utf8')))
            self.pool.get('sync.trigger.something.up').create(cr, uid, {'name': 'msr_used', 'args': zipstr})
        return True

    # UF22.0
    def us_9003_partner_im_is_currencies(self, cr, uid, *a, **b):
        self.us_5559_set_pricelist(cr, uid, *a, **b)
        return True

    def us_8944_cold_chain_migration(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity'):
            # exclude new instances
            return True

        # trigger sync updates
        cr.execute('''
            update
                ir_model_data set last_modification=NOW(), touched='[''cold_chain'']'
            where
                model='product.product' and
                module='sd' and
                res_id in (
                    select p.id from
                        product_product p , product_cold_chain cold, product_international_status int, product_heat_sensitive heat
                    where
                        heat.id = p.heat_sensitive_item and
                        int.id=p.international_status and
                        cold.id=p.cold_chain and
                        int.name in ('Local', 'Temporary') and
                        cold.mapped_to is not null
                )
        ''')
        self.log_info(cr, uid, 'US-8944 thermo: %d products touched' % cr.rowcount)
        cr.execute('''
            update
                product_product p
            set
                cold_chain = cold.mapped_to
            from
                product_cold_chain cold, product_international_status int, product_heat_sensitive heat
            where
                heat.id = p.heat_sensitive_item and
                int.id=p.international_status and
                cold.id=p.cold_chain and
                int.name in ('Local', 'Temporary') and
                cold.mapped_to is not null
        ''')
        self.log_info(cr, uid, 'US-8944 thermo: %d products updated' % cr.rowcount)
        return True

    def us_8597_set_custom_default_from_web(self, cr, uid, *a, **b):
        cr.execute("update sale_order set location_requestor_id=NULL where location_requestor_id is not null and procurement_request='f'")
        self._logger.warn('US-8597: Location removed on %d FO' % (cr.rowcount,))

        cr.execute("""
            update ir_values set meta='web' where
                key='default' and
                (name, model) not in (('shop_id', 'sale.order'), ('warehouse_id', 'purchase.order'), ('lang', 'res.partner'))
            """)
        self._logger.warn('US-8597: web default value set on %d records' % (cr.rowcount,))
        return True

    def us_8805_product_set_archived(self, cr, uid, *a, **b):
        if self.pool.get('sync_client.version') and self.pool.get('sync.client.entity'):
            instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
            if instance and instance.level in ['project', 'coordo']:
                st_obj = self.pool.get('product.status')
                phase_out_ids = st_obj.search(cr, uid, [('code', '=', 'phase_out')])
                archived_ids = st_obj.search(cr, uid, [('code', '=', 'archived')])
                cr.execute('''
                    update product_template t set
                        state=%(archived_id)s
                    from product_product p, product_international_status st
                    where
                        st.id = p.international_status and
                        p.product_tmpl_id = t.id and
                        p.oc_subscription = 'f' and
                        p.active = 'f' and
                        st.code = 'unidata' and
                        t.state=%(phase_out_id)s
                    ''', {'archived_id': archived_ids[0], 'phase_out_id': phase_out_ids[0]})
                self.log_info(cr, uid, 'US-8805: %d products' % cr.rowcount)
        return True

    def us_8869_remove_ir_import(self, cr, uid, *a, **b):
        cr.execute("update internal_request_import set file_to_import=NULL");
        return True

    def us_7449_set_cv_version(self, cr, uid, *a, **b):
        """
        Sets the existing Commitment Vouchers in version 1.
        """
        if self.pool.get('sync.client.entity'):  # existing instances
            cr.execute("UPDATE account_commitment SET version = 1")
            self._logger.warn('Commitment Vouchers: %s CV(s) set to version 1.', cr.rowcount)
        return True

    # UF21.1
    def us_8810_fake_updates(self, cr, uid, *a, **b):
        if self.pool.get('sync.client.entity'):
            cr.execute("""
                update sync_client_update_received set
                    manually_ran='t', run='t', execution_date=now(),
                    manually_set_run_date=now(), editable='f',
                    log='Set manually to run without execution'
                where
                    run='f' and
                    sequence_number=1071578 and
                    source='OCG_HQ'
            """);
            self._logger.warn('US-8810: %d updates set as Run' % (cr.rowcount,))
        return True

    def us_8753_admin_never_expire_password(self, cr, uid, *a, **b):
        # do not deactivate, to be executed on each new instances
        cr.execute("update res_users set never_expire='t' where login='admin'")
        return True

    # UF21.0
    def us_8196_delete_default_prod_curr(self, cr, uid, *a, **b):
        cr.execute("delete from ir_values where key = 'default' and model='product.product' and name in ('currency_id','field_currency_id') ;")
        self._logger.warn('Delete %d default values on product currencies' % (cr.rowcount,))
        user_record = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'])
        if user_record.company_id and user_record.company_id.currency_id:
            cur_id = user_record.company_id.currency_id.id
            cr.execute("update product_product set currency_id = %s, currency_fixed='t' where currency_id != %s", (cur_id, cur_id))
            self._logger.warn('Changed cost price currency on %d products' % (cr.rowcount,))
            cr.execute("update product_product set field_currency_id = %s, currency_fixed='t' where field_currency_id != %s", (cur_id, cur_id))
            self._logger.warn('Changed field price currency on %d products' % (cr.rowcount,))
        return True

    def us_7941_auto_vi_set_partner(self, cr, uid, *a, **b):
        cr.execute('''
            update automated_import imp set partner_id = (select id from res_partner where ref='APU' and partner_type='esc' LIMIT 1)
                from automated_import_function function
            where
                function.id = imp.function_id and
                imp.partner_id is null and
                function.multiple='t'
        ''')
        self._logger.warn('APU set on %s VI import.' % (cr.rowcount,))

        cr.execute('''
            update automated_export exp set partner_id = (select id from res_partner where ref='APU' and partner_type='esc' LIMIT 1)
                from automated_export_function function
            where
                function.id = exp.function_id and
                exp.partner_id is null and
                function.multiple='t'
        ''')
        self._logger.warn('APU set on %s VI export.' % (cr.rowcount,))

        return True

    def us_8166_hide_consolidated_sm_report(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if not instance:
            return True
        consolidated_sm_report_menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'mission_stock', 'consolidated_mission_stock_wizard_menu')[1]
        self.pool.get('ir.ui.menu').write(cr, uid, consolidated_sm_report_menu_id, {'active': instance.level == 'coordo'}, context={})
        return True

    def us_7019_force_password_expiration(self, cr, uid, *a, **b):
        entity_obj = self.pool.get('sync.client.entity')
        if entity_obj:
            # don't run on new instances
            cr.execute("update res_users set last_password_change =  NOW() - interval '7 months'")
            self._logger.warn('Force password expiration on %d users.' % (cr.rowcount,))
            cr.execute("update res_users set never_expire='t' where login in ('unidata', 'unidata2', 'unidata_screen', 'unidatasupply', 'unidataonly')")
            self._logger.warn('Set never expire on %d unidata users.' % (cr.rowcount,))
            if self.pool.get('sync.server.entity'):
                cr.execute("""
                    update res_users u set never_expire='t' from
                        res_groups_users_rel grp_rel, ir_model_data d
                    where
                        grp_rel.uid = u.id and
                        d.res_id = grp_rel.gid and
                        d.name = 'instance_sync_user' and
                        d.module = 'sync_server'
                """)
                self._logger.warn('Sync server: set never expire on %d sync users.' % (cr.rowcount,))
        return True

    def us_7295_update_new_dest_cc_link(self, cr, uid, *a, **b):
        """
        CC Tab of the Destinations: replaces the old field "dest_cc_ids" by the new one "dest_cc_link_ids".

        1) In all instances: deletes the old CCs, and creates the related links without activation/inactivation dates.

        2) At HQ Level: sends a message to trigger the deletion of all the links created out of HQ (used at migration time only).

        3) Out of HQ: prevents the sync of the links created, they are used at migration time only and will be deleted, cf 2).
        """
        if not self.pool.get('sync.client.entity'):
            # exclude new instances
            return True
        analytic_acc_obj = self.pool.get('account.analytic.account')
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        dest_ids = analytic_acc_obj.search(cr, uid, [('category', '=', 'DEST')])
        dcl_nb = 0
        for dest in analytic_acc_obj.browse(cr, uid, dest_ids, fields_to_fetch=['dest_cc_ids']):
            for cc in dest.dest_cc_ids:
                dest_cc_link_obj.create(cr, uid, {'dest_id': dest.id, 'cc_id': cc.id})
                dcl_nb += 1
        self._logger.warn('Destinations: %s Dest CC Links generated.', dcl_nb)

        cr.execute("DELETE FROM destination_cost_center_rel")
        self._logger.warn('Destinations: %s CC deleted.', cr.rowcount)

        if _get_instance_level(self, cr, uid) == 'hq':
            self.pool.get('sync.trigger.something').create(cr, uid, {'name': 'us-7295-delete-not-hq-links'})
        else:
            cr.execute("""
                UPDATE ir_model_data 
                SET touched ='[]', last_modification = '1980-01-01 00:00:00'
                WHERE module='sd' 
                AND model='dest.cc.link' 
                AND name LIKE (SELECT instance_identifier FROM msf_instance WHERE id = (SELECT instance_id FROM res_company)) || '%'
            """)
        return True

    # UF20.0
    def us_7866_fill_in_target_cc_code(self, cr, uid, *a, **b):
        """
        Fills in the new "cost_center_code" field of the Account Target Cost Centers.
        """
        cr.execute("""
                   UPDATE account_target_costcenter t_cc
                   SET cost_center_code = (SELECT code FROM account_analytic_account a_acc WHERE a_acc.id = t_cc.cost_center_id);
                   """)
        self._logger.warn('Cost Center Code updated in %s Target CC.' % (cr.rowcount,))
        return True

    def us_7848_cold_chain(self, cr, uid, *a, **b):
        for table in ['internal_move_processor', 'outgoing_delivery_move_processor', 'return_ppl_move_processor', 'stock_move_in_processor', 'stock_move_processor']:
            cr.execute("update %s set kc_check = '' where kc_check != ''" % (table, )) # not_a_user_entry
            cr.execute(""" update %s rel set kc_check='X'
                from product_product prod, product_cold_chain c
                where
                    prod.id = rel.product_id and
                    prod.cold_chain = c.id and
                    c.cold_chain='t'
            """ % (table, )) # not_a_user_entry
        return True

    def us_7749_migrate_dpo_flow(self, cr, uid, *a, **b):
        # ignore old DPO IN: do not generate sync msg for old IN
        cr.execute("update stock_picking set dpo_incoming='f' where dpo_incoming='t'")
        cr.execute('update purchase_order set po_version=1')
        cr.execute("update purchase_order set po_version=2, invoice_method='picking' where order_type='direct' and state in ('draft', 'validated')")
        return True

    def us_6796_hide_prod_status_inconsistencies(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if not instance:
            return True
        report_prod_inconsistencies_menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_tools', 'export_report_inconsistencies_menu')[1]
        self.pool.get('ir.ui.menu').write(cr, uid, report_prod_inconsistencies_menu_id, {'active': instance.level != 'project'}, context={})
        return True

    # UF19.0
    def us_7808_ocg_rename_esc(self, cr, uid, *a, **b):
        entity_obj = self.pool.get('sync.client.entity')
        if entity_obj and entity_obj.get_entity(cr, uid).oc == 'ocg':
            cr.execute("update res_partner set name='MSF LOGISTIQUE' where id in (select res_id from ir_model_data where name='1e206c21-b2ba-11e4-a614-005056290182/res_partner/6')")
            self._logger.warn('%d ESC partner renamed' % (cr.rowcount,))

            if _get_instance_level(self, cr, uid) == 'hq':
                cr.execute("update ir_model_data set touched='[''name'']', last_modification=now() where name='1e206c21-b2ba-11e4-a614-005056290182/res_partner/6'")
                self._logger.warn('%d ESC sync update triggered' % (cr.rowcount,))
        return True


    def us_7243_migrate_contract_quad(self, cr, uid, *a, **b):
        quad_obj = self.pool.get('financing.contract.account.quadruplet')
        if not cr.table_exists('financing_contract_actual_account_quadruplets_old'):
            cr.execute("create table financing_contract_actual_account_quadruplets_old as (select * from financing_contract_actual_account_quadruplets)")
        already_migrated = {}
        cr.execute('truncate financing_contract_actual_account_quadruplets')
        cr.execute('select actual_line_id, account_quadruplet_id from financing_contract_actual_account_quadruplets_old')
        nb_mig = 0
        for x in cr.fetchall():
            if x[1] not in already_migrated:
                new_id = quad_obj.migrate_old_quad(cr, uid, [x[1]])
                already_migrated[x[1]] = new_id and new_id[0]
            if already_migrated.get(x[1]):
                nb_mig += 1
                cr.execute('insert into financing_contract_actual_account_quadruplets (actual_line_id, account_quadruplet_id) values (%s, %s)', (x[0], already_migrated[x[1]]))

        self._logger.warn('%d quad migrated' % (nb_mig,))
        return True

    def us7940_create_parent_seg(self, cr, uid, *a, **b):
        if not cr.column_exists('replenishment_segment', 'order_validation_lt') or not cr.column_exists('replenishment_segment', 'hidden'):
            return True

        seg_obj = self.pool.get('replenishment.segment')

        copy_fields = ['location_config_id', 'ir_requesting_location', 'order_creation_lt', 'order_validation_lt', 'supplier_lt', 'handling_lt', 'order_coverage', 'previous_order_rdd', 'date_next_order_received_modified', 'hidden']
        cr.execute("select id, description_seg, state, "+','.join(copy_fields)+"  from replenishment_segment where parent_id is NULL order by id")  # not_a_user_entry

        for seg in cr.dictfetchall():
            vals = {'name_parent_seg': self.pool.get('ir.sequence').get(cr, uid, 'replenishment.parent.segment')}
            for x in copy_fields:
                vals[x] = seg[x]
            vals['state_parent'] = seg['state']
            if vals['order_coverage']:
                vals['order_coverage'] = vals['order_coverage'] * 30.44
            vals['description_parent_seg'] = 'Parent %s' % seg['description_seg']

            cr.execute('''
                insert into replenishment_parent_segment (name_parent_seg, description_parent_seg, order_preparation_lt, time_unit_lt, state_parent, '''+','.join(copy_fields)+''')
                values
                (%(name_parent_seg)s, %(description_parent_seg)s, 0, 'd', %(state_parent)s, '''+','.join(['%%(%s)s' % x for x in copy_fields])+''')
                returning id
            ''', vals)  # not_a_user_entry
            parent_seg_id = cr.fetchone()[0]
            cr.execute('update replenishment_segment set parent_id=%s, safety_stock=safety_stock*30.44 where id=%s', (parent_seg_id, seg['id']))

            seg_sdref = seg_obj.get_sd_ref(cr, uid, seg['id'])
            cr.execute('''
                insert into ir_model_data
                    (noupdate, name, date_init, date_update, module, model, res_id, force_recreation, version, touched, last_modification)
                    values
                    ('f', %(sdref)s, now(), now(), 'sd', 'replenishment.parent.segment', %(parent_seg_id)s, 'f', 1, '[]', NOW())
                ''', {'sdref': '%s_parent'%seg_sdref, 'parent_seg_id': parent_seg_id})

        cr.execute('''update replenishment_order_calc_line line set segment_id=calc.segment_id from replenishment_order_calc calc where calc.id=line.order_calc_id''')
        cr.execute('''update replenishment_order_calc calc set parent_segment_id=seg.parent_id, time_unit_lt='d' from replenishment_segment seg where calc.segment_id=seg.id''')
        return True

    def us_2725_uf_write_date_on_products(self, cr, uid, *a, **b):
        '''
        Set the uf_write_date of products which don't have one to the date of creation
        '''

        cr.execute('''
            UPDATE product_product SET uf_write_date = uf_create_date WHERE uf_write_date is NULL
        ''')
        self._logger.warn('The uf_write_date has been modified on %s products' % (cr.rowcount,))

        return True

    def us_7742_update_stock_mission(self, cr, uid, *a, **b):
        cr.execute('''update stock_move m set included_in_mission_stock='t' from mission_move_rel rel where m.id = rel.move_id''')

        location_obj = self.pool.get('stock.location')
        quarantine_loc = location_obj.search(cr, uid, [('usage', '=', 'internal'), ('quarantine_location', '=', True)])
        input_loc = location_obj.search(cr, uid, [('usage', '=', 'internal'), ('input_ok', '=', True)])
        output_loc = location_obj.search(cr, uid, [('usage', '=', 'internal'), ('output_ok', '=', True)])
        report_ids = self.pool.get('stock.mission.report').search(cr, uid, [('local_report', '=', True), ('full_view', '=', False)])
        if not report_ids:
            return True
        report_id = report_ids[0]

        stock_query = '''
          SELECT al.product_id, al.qty FROM (
            SELECT
                m.product_id,
                SUM(
                    CASE
                        WHEN COALESCE(m.product_qty, 0.0)=0 THEN 0
                        WHEN m.location_dest_id in %(loc)s and m.location_id in %(loc)s THEN 0
                        WHEN m.location_dest_id in %(loc)s AND pt.uom_id = m.product_uom THEN m.product_qty
                        WHEN m.location_dest_id in %(loc)s AND pt.uom_id != m.product_uom THEN m.product_qty / u.factor * pu.factor
                        WHEN pt.uom_id = m.product_uom THEN -m.product_qty
                        ELSE -m.product_qty / u.factor * pu.factor
                    END
                ) AS qty
            FROM stock_move m
                LEFT JOIN product_product pp ON m.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_uom pu ON pt.uom_id = pu.id
                LEFT JOIN product_uom u ON m.product_uom = u.id
            WHERE
                m.state = 'done' AND
                m.included_in_mission_stock = 't' AND
                ( m.location_dest_id in %(loc)s or m.location_id in %(loc)s) AND
                m.location_dest_id != m.location_id
            GROUP BY
                m.product_id
            ) al WHERE qty!=0'''

        for col, loc in [('quarantine_qty', quarantine_loc), ('input_qty', input_loc), ('opdd_qty', output_loc)]:
            nb_update = 0
            cr.execute(stock_query, {'loc': tuple(loc)})
            for x in cr.fetchall():
                cr.execute('update stock_mission_report_line line set '+col+'=%s  where product_id = %s and line.mission_report_id=%s RETURNING id', (x[1], x[0], report_id)) # not_a_user_entry
                line_id = cr.fetchone()
                if line_id:
                    nb_update += 1
                    cr.execute("update ir_model_data set last_modification=NOW(), touched='[''product_id'']' where model='stock.mission.report.line' and module='sd' and res_id=%s", (line_id[0],))
            self._logger.warn('Mission stock line %s, updated: %d' % (col, nb_update))
        return True


    def us_7742_hide_stock_pipe(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if not instance:
            return True
        stock_pipe_report_menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_tools', 'stock_pipe_per_product_instance_menu')[1]
        self.pool.get('ir.ui.menu').write(cr, uid, stock_pipe_report_menu_id, {'active': instance.level == 'section'}, context={})
        return True

    # UF18.0
    def uf18_0_migrate_acl(self, cr, uid, *a, **b):
        cr.execute('''
            update button_access_rule_groups_rel set
            button_access_rule_id=(select res_id from ir_model_data where name='BAR_stockview_production_lot_tree_unlink' limit 1)
            where
            button_access_rule_id=(select res_id from ir_model_data where name='BAR_specific_rulesview_production_lot_tree_unlink' limit 1)
        ''')
        self._logger.warn('%d BAR updated' % (cr.rowcount, ))
        return True

    def us_7215_prod_set_active_sync(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.message_received'):
            # new instance
            return True
        cr.execute("""
            update product_product p set
                active_change_date=d.last_modification, active_sync_change_date=d.sync_date
            from
                ir_model_data d
            where
                d.model='product.product' and
                d.module='sd' and
                d.res_id = p.id and
                touched like '%''state''%'
        """)
        self._logger.warn('Set active_sync_change_date on %d product' % (cr.rowcount,))

        return True

    def us_7158_prod_set_uf_status(self, cr, uid, *a, **b):
        st_obj = self.pool.get('product.status')
        audit_obj = self.pool.get('audittrail.rule')
        stopped_ids = st_obj.search(cr, uid, [('code', '=', 'stopped'), ('active', 'in', ['t', 'f'])])
        phase_out_ids = st_obj.search(cr, uid, [('code', '=', 'phase_out')])

        st12_ids = st_obj.search(cr, uid, [('code', 'in', ['status1', 'status2']), ('active', 'in', ['t', 'f'])])
        valid_ids = st_obj.search(cr, uid, [('code', '=', 'valid')])

        # state 1, state2, blank to valid
        cr.execute('''update product_template set state = %s where state is NUll or state in %s''' , (valid_ids[0], tuple(st12_ids)))
        cr.execute('''update stock_mission_report_line set product_state='valid' where product_state is NULL or product_state in ('', 'status1', 'status2')''')

        # stopped to phase_out
        cr.execute('''update product_template set state = %s where state = %s RETURNING id''' , (phase_out_ids[0], stopped_ids[0]))
        prod_templ_ids = [x[0] for x in cr.fetchall()]
        if prod_templ_ids:
            audit_ids = audit_obj.search(cr, uid, [('name', '=', 'Product_template rule')])
            if audit_ids:
                audit_obj.audit_log(cr, uid, audit_ids, 'product.template', prod_templ_ids, 'write', previous_value=[{'state': (stopped_ids[0], 'Stopped'), 'id': pt_id} for pt_id in prod_templ_ids], current={x: {'state': (phase_out_ids[0], 'Phase out')} for x in prod_templ_ids}, context=None)
        cr.execute('''update stock_mission_report_line set product_state='phase_out' where product_state = 'stopped' ''')

        return True

    def us_5216_update_recurring_object_state(self, cr, uid, *a, **b):
        """
        Updates the state of the Recurring Plans and Recurring Models with the new rules set in US-5216.
        """
        if not self.pool.get('sync.server.update'):
            rec_plan_obj = self.pool.get('account.subscription')
            rec_model_obj = self.pool.get('account.model')
            # Recurring Plans
            rec_plans = {
                'draft': [],
                'running': [],
                'done': [],
            }
            rec_plan_ids = rec_plan_obj.search(cr, uid, [], order='NO_ORDER')
            for rec_plan in rec_plan_obj.browse(cr, uid, rec_plan_ids, fields_to_fetch=['lines_id']):
                if not rec_plan.lines_id:
                    rec_plans['draft'].append(rec_plan.id)
                else:
                    running = False
                    for sub_line in rec_plan.lines_id:
                        if not sub_line.move_id or sub_line.move_id.state != 'posted':
                            running = True
                            break
                    if running:
                        rec_plans['running'].append(rec_plan.id)
                    else:
                        rec_plans['done'].append(rec_plan.id)
            for plan_state in rec_plans:
                if rec_plans[plan_state]:
                    update_rec_plans = """
                                       UPDATE account_subscription
                                       SET state = %s
                                       WHERE id IN %s;
                                       """
                    cr.execute(update_rec_plans, (plan_state, tuple(rec_plans[plan_state])))
            # Recurring Models
            rec_models = {
                'draft': [],
                'running': [],
                'done': [],
            }
            rec_model_ids = rec_model_obj.search(cr, uid, [], order='NO_ORDER')
            for model_id in rec_model_ids:
                if rec_plan_obj.search_exist(cr, uid, [('model_id', '=', model_id), ('state', '=', 'done')]):
                    state = 'done'
                elif rec_plan_obj.search_exist(cr, uid, [('model_id', '=', model_id), ('state', '=', 'running')]):
                    state = 'running'
                else:
                    state = 'draft'
                rec_models[state].append(model_id)
            for model_state in rec_models:
                if rec_models[model_state]:
                    update_rec_models = """
                                        UPDATE account_model
                                        SET state = %s
                                        WHERE id IN %s;
                                        """
                    cr.execute(update_rec_models, (model_state, tuple(rec_models[model_state])))
        return True

    def us_5216_remove_duplicated_ir_values(self, cr, uid, *a, **b):
        """
        Removes the old ir.values related to the act_window "Recurring Entries To Post",
        so that the menu entry appears only once in the already existing DBs.
        """
        cr.execute("""
           DELETE FROM ir_values
           WHERE
                name='act_account_subscription_to_account_move_line_open' AND
                key2='client_action_relate' AND
                model='account.subscription'
        """)
        return True

    def us_7448_set_revaluated_periods(self, cr, uid, *a, **b):
        """
        Sets the tag "is_revaluated" for the existing periods in which the revaluation has been run,
        based on the rules which applied until now
        """
        if not self.pool.get('sync.server.update'):
            user_obj = self.pool.get('res.users')
            period_obj = self.pool.get('account.period')
            fy_obj = self.pool.get('account.fiscalyear')
            journal_obj = self.pool.get('account.journal')
            aml_obj = self.pool.get('account.move.line')
            instance = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
            revaluated_period_ids = []
            if instance and instance.level == 'coordo':
                reval_journal_ids = journal_obj.search(cr, uid, [('type', '=', 'revaluation'), ('is_current_instance', '=', True)])
                if reval_journal_ids:
                    period_ids = period_obj.search(cr, uid, [('special', '=', False)])
                    for period in period_obj.browse(cr, uid, period_ids, fields_to_fetch=[('number', 'fiscalyear_id', 'name')]):
                        # domain taken from the check which was done until now at period closing time
                        aml_domain = [('journal_id', 'in', reval_journal_ids), ('period_id', '=', period.id)]
                        # additional check which was done at revaluation time
                        # for the January periods having a previous FY
                        if period.number == 1:
                            if fy_obj.search_exist(cr, uid, [('date_start', '<', period.fiscalyear_id.date_start)]):
                                aml_domain.append(('name', 'like', "Revaluation - %s" % (period.name,)))
                        if aml_obj.search_exist(cr, uid, aml_domain):
                            revaluated_period_ids.append(period.id)
            if revaluated_period_ids:
                update_period_sql = """
                                UPDATE account_period
                                SET is_revaluated = 't'
                                WHERE id IN %s;
                                """
                cr.execute(update_period_sql, (tuple(revaluated_period_ids),))
                self._logger.warn('Number of periods set as revaluated: %s.' % (cr.rowcount,))
        return True

    def us_7412_set_fy_closure_settings(self, cr, uid, *a, **b):
        """
        Sets the Fiscal Year Closure options depending on the OC.
        """
        if self.pool.get('sync.client.entity') and not self.pool.get('sync.server.update'):
            oc_sql = "SELECT oc FROM sync_client_entity LIMIT 1;"
            cr.execute(oc_sql)
            oc = cr.fetchone()[0]
            has_move_regular_bs_to_0 = False
            has_book_pl_results = False
            if oc == 'ocg':
                has_move_regular_bs_to_0 = True
            elif oc == 'ocb':
                has_move_regular_bs_to_0 = True
                has_book_pl_results = True
            update_company = """
                             UPDATE res_company
                             SET has_move_regular_bs_to_0 = %s, has_book_pl_results = %s;
                             """
            cr.execute(update_company, (has_move_regular_bs_to_0, has_book_pl_results))

    def us_6453_set_ref_on_in(self, cr, uid, *a, **b):
        if self.pool.get('sync.client.entity'):
            cr.execute('''
            update stock_picking set customer_ref=x.ref, customers=x.cust from (
                select
                    p.id,
                    string_agg(distinct(regexp_replace(so.client_order_ref,'^.*\.', '')),';') as ref,
                    string_agg(distinct(part.name), ';') as cust
                from
                    stock_picking p,
                    sale_order so,
                    sale_order_line sol,
                    purchase_order_line pol,
                    purchase_order po,
                    res_partner part
                where
                    p.type='in' and
                    p.purchase_id=po.id and
                    pol.order_id=po.id and
                    pol.linked_sol_id=sol.id and
                    sol.order_id=so.id and
                    part.id = so.partner_id
                group by p.id
                ) as x
            where x.id=stock_picking.id and type='in'
            ''')

            cr.execute("SELECT name FROM sync_client_entity LIMIT 1")
            inst_name = cr.fetchone()[0]
            if not inst_name:
                return False

            cr.execute("update stock_picking set customers=%s where customers is null and type='in'", (inst_name, ))

        return True

    def us_7646_dest_loc_on_pol(self, cr, uid, *a, **b):
        data_obj = self.pool.get('ir.model.data')
        try:
            service_id = self.pool.get('stock.location').get_service_location(cr, uid)
            conso_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
            log_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_logistic')[1]
            med_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_medical')[1]
            cross_dock_id =  data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        except:
            return True

        cr.execute('''update purchase_order_line set location_dest_id = %s where id in (
            select pol.id
            from purchase_order_line pol, purchase_order po, product_product prod, product_template tmpl
            where
                pol.order_id = po.id and
                pol.product_id = prod.id and
                tmpl.id = prod.product_tmpl_id and
                tmpl.type = 'service_recep' and
                coalesce(po.cross_docking_ok, 'f') = 'f' and
                pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n')
            ) ''', (service_id,))
        self._logger.warn('POL loc_dest service on %s lines' % (cr.rowcount,))

        cr.execute('''update purchase_order_line set location_dest_id = %s where id in (
            select pol.id
            from purchase_order_line pol, purchase_order po, product_product prod, product_template tmpl
            where
                pol.order_id = po.id and
                pol.product_id = prod.id and
                tmpl.id = prod.product_tmpl_id and
                tmpl.type = 'consu' and
                pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n')
            ) ''', (conso_id,))
        self._logger.warn('POL loc_dest conso on %s lines' % (cr.rowcount,))

        cr.execute('''update purchase_order_line set location_dest_id = so.location_requestor_id
                        from sale_order so, sale_order_line sol, stock_location loc, product_product prod, product_template tmpl
                        where
                            so.id = sol.order_id and
                            loc.id = so.location_requestor_id and
                            loc.usage != 'customer' and
                            so.procurement_request = 't' and
                            purchase_order_line.linked_sol_id = sol.id and
                            purchase_order_line.product_id = prod.id and
                            tmpl.id = prod.product_tmpl_id and
                            tmpl.type != 'consu' and
                            purchase_order_line.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') ''', (conso_id,))
        self._logger.warn('POL loc_dest IR on %s lines' % (cr.rowcount,))

        cr.execute('''update purchase_order_line set location_dest_id = %s from purchase_order po
                        where
                            po.id = purchase_order_line.order_id and
                            purchase_order_line.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and
                            coalesce(po.cross_docking_ok, 'f') = 't' and
                            location_dest_id is NULL ''', (cross_dock_id,))
        self._logger.warn('POL loc_dest Cross Dock on %s lines' % (cr.rowcount,))

        cr.execute('''update purchase_order_line set location_dest_id = %s
                    from product_product prod, product_template tmpl, product_nomenclature nom
                    where
                        purchase_order_line.product_id = prod.id and
                        tmpl.nomen_manda_0 = nom.id and
                        nom.name = 'MED' and
                        tmpl.id = prod.product_tmpl_id and
                        location_dest_id is NULL and
                        purchase_order_line.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') ''', (med_id,))
        self._logger.warn('POL loc_dest MED on %s lines' % (cr.rowcount,))

        cr.execute('''update purchase_order_line set location_dest_id = %s
                    from product_product prod, product_template tmpl, product_nomenclature nom
                    where
                        purchase_order_line.product_id = prod.id and
                        tmpl.nomen_manda_0 = nom.id and
                        nom.name = 'LOG' and
                        tmpl.id = prod.product_tmpl_id and
                        location_dest_id is NULL and
                        purchase_order_line.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') ''', (log_id,))
        self._logger.warn('POL loc_dest LOG on %s lines' % (cr.rowcount,))
        return True


    def us_6544_no_sync_on_forced_out(self, cr, uid, *a, **b):
        # already forced OUT as delivred must no generate sync msg to prevent NR at reception
        if self.pool.get('sync_client.version'):
            cr.execute('''
                update ir_model_data set sync_date=NOW() where id in (
                    select d.id from
                        stock_picking p
                        left join ir_model_data d on d.model='stock.picking' and d.res_id=p.id and d.module='sd'
                    where
                        p.type='out' and
                        p.subtype='standard' and
                        p.state='delivered' and
                        (d.sync_date is null or d.sync_date < d.last_modification)
            )''')
            self._logger.warn('Prevent NR on forced delivered OUT (%s)' % (cr.rowcount,))
        return True

    # UF17.1
    def us_7631_set_default_liquidity_accounts(self, cr, uid, *a, **b):
        if self.pool.get('sync_client.version') and self.pool.get('sync.client.entity'):
            oc_sql = "SELECT oc FROM sync_client_entity LIMIT 1"
            cr.execute(oc_sql)
            oc = cr.fetchone()[0]
            if not oc:
                return False

            to_write = {}
            account_obj = self.pool.get('account.account')

            # cash
            ids_10100 = account_obj.search(cr, uid, [('code', '=', '10100')])
            if ids_10100:
                to_write.update({'cash_debit_account_id': ids_10100[0], 'cash_credit_account_id': ids_10100[0]})


            # bank
            ids_10200 = account_obj.search(cr, uid, [('code', '=', '10200')])
            if ids_10200:
                to_write.update({'bank_debit_account_id': ids_10200[0], 'bank_credit_account_id': ids_10200[0]})


            # cheque
            if oc == 'oca':
                cheque_code = '15630'
            else:
                cheque_code = '10210'

            ids_cheque = account_obj.search(cr, uid, [('code', '=', cheque_code)])
            if ids_cheque:
                to_write.update({'cheque_debit_account_id': ids_cheque[0], 'cheque_credit_account_id': ids_cheque[0]})

            if to_write:
                company_id = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.id
                self.pool.get('res.company').write(cr, uid, company_id, to_write)
                self._logger.warn('Liquidity journals set on company form')

            return True

    def sync_msg_from_itself(self, cr, uid, *a, **b):
        instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if not instance:
            return True
        cr.execute(''' update sync_client_message_received set run='t', manually_ran='t', log='Set manually to run without execution', manually_set_run_date=now() where run='f' and source=%s ''', (instance.instance, ))
        self._logger.warn('Set %s self sync messages as Run' % (cr.rowcount,))
        return True

    def us_7593_inactivate_en_US(self, cr, uid, *a, **b):
        """
        Inactivates en_US and replaces it by en_MF for users, partners and related not runs
        """
        lang_sql = "UPDATE res_lang SET active = 'f' WHERE code='en_US';"
        cr.execute(lang_sql)
        partner_sql = "UPDATE res_partner SET lang='en_MF' WHERE lang='en_US';"
        cr.execute(partner_sql)
        partner_count = cr.rowcount
        user_sql = "UPDATE res_users SET context_lang='en_MF' WHERE context_lang='en_US';"
        cr.execute(user_sql)
        user_count = cr.rowcount
        self._logger.warn('English replaced by MSF English for %s partner(s) and %s user(s).' %
                          (partner_count, user_count))


    # UF17.0
    def recursive_fix_int_previous_chained_pick(self, cr, uid, to_fix_pick_id, prev_chain_pick_id, context=None):
        if context is None:
            context = {}

        pick_obj = self.pool.get('stock.picking')
        cr.execute("update stock_picking set previous_chained_pick_id=%s where id=%s" , (prev_chain_pick_id, to_fix_pick_id))
        pick = pick_obj.browse(cr, uid, to_fix_pick_id, fields_to_fetch=['backorder_id'], context=context)
        if pick.backorder_id:
            self.recursive_fix_int_previous_chained_pick(cr, uid, pick.backorder_id.id, prev_chain_pick_id, context={})

        return True

    def us_7533_fix_int_previous_chained_pick_id(self, cr, uid, *a, **b):
        """
        Fix the previous_chained_pick_id of INTs which have been partially processed
        """
        cr.execute("""
            SELECT backorder_id, previous_chained_pick_id FROM stock_picking 
            WHERE type = 'internal' AND subtype = 'standard' AND backorder_id IS NOT NULL 
                AND previous_chained_pick_id IS NOT NULL
        """)

        for pick in cr.fetchall():
            self.recursive_fix_int_previous_chained_pick(cr, uid, pick[0], pick[1], context={})

        return True

    def us_7425_clean_period_not_run(self, cr, uid, *a, **b):
        """
        Sets as "Run without execution" the updates related to the field-closing of periods received from OCBHQ and not executed
        in projects and coordos because the related FY is already Mission-Closed.
        """
        if self.pool.get('sync_client.version') and self.pool.get('sync.client.entity'):
            oc_sql = "SELECT oc FROM sync_client_entity LIMIT 1;"
            cr.execute(oc_sql)
            oc = cr.fetchone()[0]
            if oc == 'ocb':
                instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
                if instance and instance.level in ['project', 'coordo']:
                    update_dom = [('model', '=', 'account.period'),
                                  ('run', '=', False),
                                  ('log', 'like', "Fiscal Year is already in Mission-Closed.")]
                    update_ids = self.pool.get('sync.client.update_received').search(cr, uid, update_dom)
                    if update_ids:
                        update_sync_received = """
                            UPDATE sync_client_update_received
                            SET manually_ran='t', run='t', execution_date=now(), 
                            manually_set_run_date=now(), editable='f', 
                            log='Set manually to run without execution'
                            WHERE id IN %s;
                        """
                        cr.execute(update_sync_received, (tuple(update_ids),))
                        self._logger.warn('%s Not Runs on periods set as manually run without exec. as the FY is already closed.' %
                                          (cr.rowcount,))

    def us_7015_del_rac_line_sql(self, cr, uid, *a, **b):
        cr.drop_constraint_if_exists('real_average_consumption_line', 'real_average_consumption_line_unique_lot_poduct')
        return True

    def us_7236_remove_reg_wkf_and_partial_close_state(self, cr, uid, *a, **b):
        """
        Both the workflows and the "Partial Close" state are not used anymore in the registers, so:
        - deletes the workflow related to registers
        - sets to Open the existing registers in "Partial Close" state
        """
        delete_wkf_transition = """
            DELETE FROM wkf_transition
            WHERE (signal IN ('button_open', 'button_confirm_cash', 'button_reopen', 'button_write_off') OR signal IS NULL)
            AND act_from IN 
                (SELECT id FROM wkf_activity WHERE wkf_id = 
                    (SELECT id FROM wkf WHERE name='account.cash.statement.workflow' AND osv='account.bank.statement')
                );
        """
        delete_wkf_workitem = """
            DELETE FROM wkf_workitem WHERE act_id IN
                (SELECT id FROM wkf_activity WHERE wkf_id = 
                    (SELECT id FROM wkf WHERE name='account.cash.statement.workflow' AND osv='account.bank.statement')
                );
        """
        delete_wkf_activity = """
            DELETE FROM wkf_activity 
            WHERE wkf_id = (SELECT id FROM wkf WHERE name='account.cash.statement.workflow' AND osv='account.bank.statement');
        """
        delete_wkf = """
            DELETE FROM wkf WHERE name='account.cash.statement.workflow' AND osv='account.bank.statement';
        """
        update_reg_state = """
            UPDATE account_bank_statement SET state = 'open' WHERE state = 'partial_close';
        """
        cr.execute(delete_wkf_transition)
        cr.execute(delete_wkf_workitem)
        cr.execute(delete_wkf_activity)
        cr.execute(delete_wkf)  # will also delete data in wkf_instance because of the ONDELETE 'cascade'
        cr.execute(update_reg_state)
        self._logger.warn('%s registers in Partial Close state have been re-opened.' % (cr.rowcount,))
        return True

    def us_7221_reset_starting_balance(self, cr, uid, *a, **b):
        """
        Reset the Starting Balance of the first register created for each journal if it is still in Draft state
        """
        # Cashbox details set to zero
        cr.execute("""
                   UPDATE account_cashbox_line
                   SET number = 0 
                   WHERE starting_id IN (
                       SELECT id FROM account_bank_statement
                       WHERE state = 'draft'
                       AND prev_reg_id IS NULL
                       AND journal_id IN (SELECT id FROM account_journal WHERE type='cash')
                   );
                   """)
        # Starting Balance set to zero
        cr.execute("""
                   UPDATE account_bank_statement
                   SET balance_start = 0.0
                   WHERE state = 'draft'
                   AND prev_reg_id IS NULL
                   AND journal_id IN (SELECT id FROM account_journal WHERE type in ('bank', 'cash'));
                   """)
        self._logger.warn('Starting Balance set to zero in %s registers.' % (cr.rowcount,))

        return True

    def us_6641_remove_duplicates_from_stock_mission(self, cr, uid, *a, **b):
        """
        Remove duplicates products (lines not coming from the current instance) from the generated Stock Mission Report lines
        """
        if not self.pool.get('sync.client.message_received'):  # New instance
            return True

        instance_id = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id.id
        if not instance_id:
            return True
        cr.execute("""
                SELECT l.id FROM stock_mission_report_line l 
                    LEFT JOIN ir_model_data d ON d.res_id = l.id AND d.model = 'stock.mission.report.line' AND d.module = 'sd'
                WHERE d.name LIKE (SELECT identifier||'%%' FROM sync_client_entity) AND 
                    mission_report_id IN (SELECT id FROM stock_mission_report WHERE instance_id != %s)
        """, (instance_id,))

        lines_to_del = [l[0] for l in cr.fetchall()]
        if lines_to_del:
            cr.execute("""DELETE FROM stock_mission_report_line WHERE id IN %s""", (tuple(lines_to_del),))
            self._logger.warn('%s Stock Mission Report lines have been deleted.' % (len(lines_to_del),))

        return True

    # UF16.1
    def remove_ir_actions_linked_to_deleted_modules(self, cr, uid, *a, **b):
        # delete remove actions
        cr.execute("delete from ir_act_window where id in (select res_id from ir_model_data where module in ('procurement_report', 'threshold_value') and model='ir.actions.act_window')")

        # delete xmlid
        cr.execute("delete from ir_model_data where module in ('procurement_report', 'threshold_value') and model='ir.actions.act_window'")

        # delete sdred
        cr.execute("delete from ir_model_data where name in ('procurement_report_action_auto_supply_rules_report', 'procurement_report_action_min_max_rules_report', 'procurement_report_action_order_cycle_rules_report', 'procurement_report_action_compute_schedulers_min_max', 'threshold_value_action_compute_schedulers_threshold', 'procurement_report_action_procurement_batch_form', 'procurement_report_action_procurement_rules_report', 'threshold_value_action_threshold_value', 'procurement_report_action_threshold_value_rules_report')")

        return True

    def us_7025_7039_fix_nr_empty_ins(self, cr, uid, *a, **b):
        """
        1. Set the Not Runs to run:
            - Error from coordo: "Exception: Something goes wrong with this message and no confirmation of delivery".
            - Error from project: "Exception: Unable to receive Shipment Details into an Incoming Shipment in this
                instance as IN IN/XXXXX (POXXXXX) already fully/partially cancelled/Closed".
        2. Remove reference data from empty INs (Backorder, Origin, links to FO, links to PO, Ship Reference, ...) and
            modify "Change Reason" to "False movement, bug US-7025/7039".
        3. Remove empty Draft IVOs.
        """
        if not self.pool.get('sync.client.message_received'):
            # new instance
            return True
        # 1
        cr.execute("""
            SELECT id, identifier, arguments FROM sync_client_message_received
            WHERE run = 'f' AND remote_call IN ('stock.picking.closed_in_validates_delivery_out_ship', 'stock.picking.partial_shipped_fo_updates_in_po')
        """)
        to_run_ids = []
        to_run_name = []
        for msg in cr.fetchall():
            args = eval(msg[2])[0]
            if args.get('shipment_ref', False) and args['shipment_ref'].endswith('-s') or args.get('name', False) and args['name'].endswith('-s'):
                to_run_ids.append(msg[0])
                to_run_name.append(msg[1])
        if to_run_ids:
            cr.execute("""
                UPDATE sync_client_message_received SET run = 't', manually_ran = 't', execution_date = %s
                WHERE id IN %s""", (time.strftime("%Y-%m-%d %H:%M:%S"), tuple(to_run_ids))
                       )
            self._logger.warn('The following Not Runs have been set to Run: %s.', (', '.join(to_run_name),))

        # 2
        cr.execute("""
            SELECT p.id, p.name FROM stock_picking p LEFT JOIN stock_move m ON p.id = m.picking_id WHERE m.id IS NULL
                AND p.type = 'in' AND p.subtype = 'standard' AND p.state = 'done' AND shipment_ref like '%s' AND purchase_id is not null
        """)
        empty_in_ids = []
        empty_in_names = []
        for inc in cr.fetchall():
            empty_in_ids.append(inc[0])
            empty_in_names.append(inc[1])
        if empty_in_ids:
            cr.execute("""
                UPDATE stock_picking SET sale_id = NULL, purchase_id = NULL, backorder_id = NULL, origin = '', 
                    shipment_ref = '', change_reason = 'False movement, bug US-7025/7039' WHERE id IN %s
            """, (tuple(empty_in_ids),))
            self._logger.warn('The following empty INs have been modified: %s.', (', '.join(empty_in_names),))

        # 3
        try:
            sync_id = self.pool.get('ir.model.data').get_object_reference(cr, 1, 'base', 'user_sync')[1]
        except:
            return True
        cr.execute("""
            DELETE FROM account_invoice WHERE id IN (
                SELECT a.id FROM account_invoice a LEFT JOIN account_invoice_line l ON a.id = l.invoice_id 
                    WHERE l.id IS NULL AND a.state = 'draft' AND a.type = 'out_invoice' AND a.is_debit_note = 'f'
                    AND a.is_inkind_donation = 'f' AND a.is_intermission = 't' AND a.user_id = %s AND a.name like 'IN/%%' AND a.create_date < '2020-01-17 00:00:00'
            )
        """, (sync_id, ))
        self._logger.warn('%s empty IVOs have been deleted.', (cr.rowcount,))

        return True

    def us_6513_rename_dispatch_to_shipment(self, cr, uid, *a, **b):
        """
        Rename the locations named 'Dispatch' to 'Shipment' for normal Location and Stock Mission report
        """
        cr.execute("""UPDATE stock_location SET name = 'Shipment' WHERE name = 'Dispatch'""")
        cr.execute("""
            UPDATE stock_mission_report_line_location SET remote_location_name = 'Shipment' 
            WHERE remote_location_name = 'Dispatch' 
        """)
        return True

    # UF16.0
    def us_7181_add_oc_subscrpition_to_unidata_products(self, cr, uid, *a, **b):
        """
        Set the new 'oc_subscription' boolean to True for each product with 'Unidata' as Product Creator
        """
        cr.execute("""
            UPDATE product_product SET oc_subscription = 't' WHERE id IN (
                SELECT p.id FROM product_product p LEFT JOIN product_international_status i ON p.international_status = i.id
                WHERE i.code = 'unidata'
            )
        """)
        self._logger.warn('%s Unidata product(s) have been updated.' % (cr.rowcount,))

        return True

    def us_6692_new_od_journals(self, cr, uid, *a, **b):
        """
        1. Change the type of the existing correction journals (except OD) to "Correction Manual" so they remain usable

        2. Create:
        - ODM journals in all existing instances
        - ODHQ journals in existing coordo instances

        Notes:
        - creations are done in Python as the objects created must sync normally
        - none of these journals already exists in prod. DB.
        """
        user_obj = self.pool.get('res.users')
        analytic_journal_obj = self.pool.get('account.analytic.journal')
        journal_obj = self.pool.get('account.journal')
        current_instance = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance:  # existing instances only
            # existing correction journals
            cr.execute("""
                       UPDATE account_analytic_journal
                       SET type = 'correction_manual'
                       WHERE type = 'correction'
                       AND code != 'OD';
                       """)
            self._logger.warn('%s correction analytic journal(s) updated.' % (cr.rowcount,))
            cr.execute("""
                       UPDATE account_journal
                       SET type = 'correction_manual'
                       WHERE type = 'correction'
                       AND code != 'OD';
                       """)
            self._logger.warn('%s correction journal(s) updated.' % (cr.rowcount,))
            # ODM analytic journal
            odm_analytic_vals = {
                # Prop. Instance: by default the current one is used
                'code': 'ODM',
                'name': 'Correction manual',
                'type': 'correction_manual',
            }
            odm_analytic_journal_id = analytic_journal_obj.create(cr, uid, odm_analytic_vals)
            # ODM G/L journal
            odm_vals = {
                # Prop. Instance: by default the current one is used
                'code': 'ODM',
                'name': 'Correction manual',
                'type': 'correction_manual',
                'analytic_journal_id': odm_analytic_journal_id,
            }
            journal_obj.create(cr, uid, odm_vals)
            if current_instance.level == 'coordo':
                # ODHQ analytic journal
                odhq_analytic_vals = {
                    # Prop. Instance: by default the current one is used
                    'code': 'ODHQ',
                    'name': 'Correction automatic HQ',
                    'type': 'correction_hq',
                }
                odhq_analytic_journal_id = analytic_journal_obj.create(cr, uid, odhq_analytic_vals)
                # ODHQ G/L journal
                odhq_vals = {
                    # Prop. Instance: by default the current one is used
                    'code': 'ODHQ',
                    'name': 'Correction automatic HQ',
                    'type': 'correction_hq',
                    'analytic_journal_id': odhq_analytic_journal_id,
                }
                journal_obj.create(cr, uid, odhq_vals)
        return True

    def us_6684_push_backup(self, cr, uid, *a, **b):
        backup_obj = self.pool.get('backup.config')
        if backup_obj:
            cr.execute("update ir_cron set manual_activation='f' where function='send_backup_bg' and model='msf.instance.cloud'")
            cr.execute("update ir_cron set name='Send Continuous Backup', manual_activation='f' where function='sent_continuous_backup_bg' and model='backup.config'")
            if cr.column_exists('backup_config', 'continuous_backup_enabled'):
                cr.execute("update backup_config set backup_type='cont_back' where continuous_backup_enabled='t'")

            # update active field on cron
            bck_ids = backup_obj.search(cr, uid, [])
            backup_obj.write(cr, uid, bck_ids, {})
        return True

    def us_7024_update_standard(self, cr, uid, *a, **b):
        cr.execute("update product_product set standard_ok='standard' where standard_ok='True'")
        cr.execute("update product_product set standard_ok='non_standard' where standard_ok='False'")
        return True

    # UF15.3
    def us_7147_reset_duplicate_proj_fxa(self, cr, uid, *a, **b):
        cr.execute("""
            select am.name, am.id, aml.id, data.name
                from account_move_line aml
                inner join account_journal aj ON aml.journal_id = aj.id
                inner join account_move am ON aml.move_id = am.id
                inner join account_period ap ON aml.period_id = ap.id
                inner join account_account aa ON aml.account_id = aa.id
                inner join msf_instance i ON aml.instance_id = i.id
                inner join ir_model_data data on data.res_id = aml.id and data.model = 'account.move.line'
            where
                aj.type = 'cur_adj' and
                i.level = 'project' and
                aml.reconcile_id is null and
                aa.reconcile = 't' and
                (aml.credit != 0 or aml.debit != 0)
        """)
        for x in cr.fetchall():
            cr.execute("select id from sync_client_update_to_send where model='account.move.reconcile' and values ~* '.*sd.%s[,''].*'" % x[3]) # not_a_user_entry
            if not cr.rowcount:
                cr.execute("select id from sync_client_update_received where model='account.move.reconcile' and values ~* '.*sd.%s[,''].*'" % x[3]) # not_a_user_entry
                if not cr.rowcount:
                    cr.execute("update account_move_line set credit=0, debit=0 where move_id = %s", (x[1], ))
                    cr.execute("update account_analytic_line set amount=0, amount_currency=0 where move_id in (select id from account_move_line where move_id = %s)", (x[1], ))
                    self._logger.warn('Set 0 on FXA %s' % (x[0],))
        return True

    # UF15.2
    def rec_entries_uf14_1_uf15(self, cr, uid, *a, **b):
        current_instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance:
            trigger_obj = self.pool.get('sync.trigger.something.target')
            cr.execute('''
                select sdref, values, source from sync_client_update_received where model='account.move.reconcile' and execution_date > ( select applied from sync_client_version where name='UF15.0') and fields not like '%action_date%'
            ''')

            for update in cr.fetchall():
                rec_number = False
                try:
                    rec_number = eval(update[1])
                except:
                    self._logger.warn('Unable to parse values, sdref: %s' % update[0])

                if rec_number:
                    trigger_obj.create(cr, uid, {'name': 'trigger_rec', 'destination': update[2] , 'args': rec_number[0], 'local': True})

        return True

    # UF15.1
    def us_6930_gen_unreconcile(self, cr, uid, *a, **b):
        # generate updates to delete reconcile done after UF15.0
        current_instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance:
            unrec_obj = self.pool.get('account.move.unreconcile')
            cr.execute('''
                select d.name from ir_model_data d
                left join
                    account_move_reconcile rec on d.model='account.move.reconcile' and d.res_id = rec.id
                where d.model='account.move.reconcile' and rec.id is null and touched like '%action_date%'
            ''')
            for sdref_rec in cr.fetchall():
                unrec_obj.create(cr, uid, {'reconcile_sdref': sdref_rec[0]})
        return True

    def us_6905_manage_bned_switch(self, cr, uid, *a, **b):
        fake_ed = '2999-12-31'
        fake_bn = 'TO-BE-REPLACED'

        lot_obj = self.pool.get('stock.production.lot')

        # old move with BN or ED if product is no_bn no_ed
        # set no on bn or en moves
        cr.execute('''
            update stock_move set prodlot_id=NULL, expired_date=NULL, hidden_batch_management_mandatory='f', hidden_perishable_mandatory='f', old_lot_info=(select name||'#'||life_date from stock_production_lot where id=stock_move.prodlot_id)||E'\n'||COALESCE(old_lot_info, '') where id in
                (select m.id from stock_move m, product_product p where p.id = m.product_id and p.perishable='f' and p.batch_management='f' and m.prodlot_id is not null and m.state in ('done', 'cancel'))
        ''')
        self._logger.warn('%d done/cancel moves set from ED or BN to no' % (cr.rowcount, ))


        # set bn on no moves
        cr.execute('''select distinct(product_id) from stock_move m, product_product p where p.id = m.product_id and p.perishable='t' and p.batch_management='t' and m.prodlot_id is null and m.state = 'done' and m.product_qty!=0 and m.location_dest_id != m.location_id''')
        self._logger.warn('%d done/cancel moves set from NO to BN' % (cr.rowcount, ))
        for prod_id in cr.fetchall():
            batch_id = lot_obj._get_or_create_lot(cr, uid, name=fake_bn, expiry_date=fake_ed, product_id=prod_id)
            cr.execute("update stock_move set hidden_batch_management_mandatory='t', hidden_perishable_mandatory='f', prodlot_id=%s, expired_date=%s, old_lot_info='US-6905 BN set'||E'\n'||COALESCE(old_lot_info, '') where product_id=%s and prodlot_id is null and state = 'done' and product_qty!=0 and location_dest_id != location_id", (batch_id, fake_ed, prod_id))

        # set ed on no moves
        cr.execute('''select distinct(product_id) from stock_move m, product_product p where p.id = m.product_id and p.perishable='t' and p.batch_management='f' and m.prodlot_id is null and m.state = 'done' and m.product_qty!=0 and m.location_dest_id != m.location_id''')
        self._logger.warn('%d done/cancel moves set from NO to ED' % (cr.rowcount, ))
        for prod_id in cr.fetchall():
            batch_id = lot_obj._get_or_create_lot(cr, uid, name=False, expiry_date=fake_ed, product_id=prod_id)
            cr.execute("update stock_move set hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t', prodlot_id=%s, expired_date=%s, old_lot_info='US-6905 EN set'||E'\n'||COALESCE(old_lot_info, '') where product_id=%s and prodlot_id is null and state = 'done' and product_qty!=0 and location_dest_id != location_id", (batch_id, fake_ed, prod_id))

        # set ed on bn moves
        cr.execute("update stock_production_lot set name='MSFBN/'||name, type='internal' where id in (select lot.id from stock_production_lot lot, product_product p where p.id = lot.product_id and type='standard' and p.perishable='t' and p.batch_management='f') returning name")
        for lot in cr.fetchall():
            self._logger.warn('BN %s from standard to internal' % (lot[0], ))

        # set bn on ed moves
        cr.execute("update stock_production_lot set type='standard', name='S'||name where id in (select lot.id from stock_production_lot lot, product_product p where p.id = lot.product_id and type='internal' and p.perishable='t' and p.batch_management='t') returning name")
        for lot in cr.fetchall():
            self._logger.warn('BN %s from internal to standard' % (lot[0], ))

        return True

    # UF15.0
    def us_6768_trigger_FP_sync(self, cr, uid, *a, **b):
        """
        Triggers a synch. on the FP CD1-KNDAK_ in OCBCD100, to trigger its re-recreation in the projects
        """
        user_obj = self.pool.get('res.users')
        current_instance = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
        if current_instance and current_instance.code == 'OCBCD100':
            cr.execute("""
                UPDATE ir_model_data 
                SET touched ='[''code'']', last_modification = NOW()
                WHERE module='sd' 
                AND model='account.analytic.account' 
                AND name = '3beb0a5e-5a6b-11e8-a0e4-1c4d70b8cca6/account_analytic_account/444';                
            """)
        return True

    def uf15_fields_moved(self, cr, uid, *a, **b):
        if _get_instance_level(self, cr, uid) == 'hq':
            # touch BAR and ACL for fields moved from one module to another (i.e sdref renamed)
            cr.execute("""
                update ir_model_data set last_modification=now(), touched='[''name'']' 
                where name in ('ir_model_access_res_currency_tables_model_res_currency_table_user read', 'ir_model_access_res_currency_tables_model_res_currency_table_admin', '_msf_profile_res_currency_tables_model_res_currency_table_Fin_Config_Full', '_msf_profile_res_currency_tables_model_res_currency_table_Fin_Config_HQ', 'BAR_res_currency_tablesview_currency_table_form_valid', 'BAR_res_currency_tablesview_currency_table_form_closed')
            """)
            self._logger.warn('%d BAR/ACL sync touched' % (cr.rowcount,))
        elif self.pool.get('sync.server.update'):
            # prevent NR on init sync for FARL/BAR on renamed or deleted fields
            cr.execute('''
                update sync_server_update set rule_id = NULL
                where sdref in ('_msf_profile_account_payment_model_payment_mode_common','_msf_profile_account_voucher_model_account_voucher_line_common','_msf_profile_account_payment_model_payment_line_common','_msf_profile_account_voucher_model_sale_receipt_report_common','_msf_profile_account_payment_model_payment_order_common','_msf_profile_account_voucher_model_account_voucher_common','BAR_account_voucherview_purchase_receipt_form_action_cancel_draft','BAR_account_voucherview_account_voucher_unreconcile_trans_unrec','BAR_account_voucherview_vendor_receipt_form_proforma_voucher','BAR_account_paymentview_payment_order_form_set_done','BAR_account_voucherview_purchase_receipt_form_compute_tax','BAR_account_voucherview_sale_receipt_form_account_voucheract_pay_voucher','BAR_account_voucherview_voucher_form_proforma_voucher','BAR_account_voucherview_vendor_payment_form_cancel_voucher','BAR_account_paymentaccount_payment_populate_statement_view_populate_statement','BAR_account_voucherview_voucher_form_compute_tax','BAR_account_paymentview_payment_order_form_open','BAR_account_voucherview_account_statement_from_invoice_search_invoices','BAR_account_voucherview_sale_receipt_form_action_cancel_draft','BAR_account_voucherview_vendor_receipt_form_action_cancel_draft','BAR_account_voucherview_sale_receipt_form_compute_tax','BAR_account_voucherview_sale_receipt_form_cancel_voucher','BAR_account_voucherview_account_statement_from_invoice_lines_populate_statement','BAR_account_voucherview_sale_receipt_form_proforma_voucher','BAR_account_voucherview_voucher_tree_proforma_voucher','BAR_account_voucherview_purchase_receipt_form_cancel_voucher','BAR_account_voucherview_purchase_receipt_form_account_voucheract_pay_bills','BAR_account_voucherview_vendor_payment_form_proforma_voucher','BAR_account_voucherview_voucher_form_cancel_voucher','BAR_account_paymentview_create_payment_order_search_entries','BAR_account_paymentview_payment_order_form_set_to_draft','BAR_account_voucherview_voucher_form_action_cancel_draft','BAR_account_voucherview_vendor_payment_form_action_cancel_draft','BAR_account_paymentview_create_payment_order_lines_create_payment','BAR_account_paymentaccount_payment_make_payment_view_launch_wizard','BAR_account_voucherview_vendor_receipt_form_cancel_voucher','BAR_account_paymentview_payment_order_tree_cancel','BAR_account_voucherview_purchase_receipt_form_proforma_voucher','BAR_account_paymentview_payment_order_form_cancel','BAR_account_paymentview_payment_order_tree_set_done','BAR_account_paymentview_payment_order_form_account_paymentaction_create_payment_order','BAR_account_paymentview_payment_order_tree_open','ir_model_access_res_currency_tables_model_res_currency_table_user read','ir_model_access_res_currency_tables_model_res_currency_table_admin','_msf_profile_res_currency_tables_model_res_currency_table_Fin_Config_Full','_msf_profile_res_currency_tables_model_res_currency_table_Fin_Config_HQ','BAR_res_currency_tablesview_currency_table_form_valid','BAR_res_currency_tablesview_currency_table_form_closed', 'base_group_extended')
                ''')
            self._logger.warn('%d sync updates deactivated for init sync' % (cr.rowcount,))
        return True

    def us_6618_create_shadow_pack(self, cr, uid, *a, **b):
        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        if not wh_ids:
            return True

        wh = self.pool.get('stock.warehouse').browse(cr, uid, wh_ids[0])
        loc_ship = wh.lot_dispatch_id.id
        loc_distrib = wh.lot_distribution_id.id
        if not loc_ship or not loc_distrib:
            return True

        if cr.column_exists('stock_picking', 'first_shipment_packing_id'):
            cr.execute('''
                select * from stock_picking
                where
                    subtype='packing' and
                    name ~ 'PACK/[0-9]+-(surplus|return-)?[0-9]+-[0-9]+' and
                    first_shipment_packing_id is null and
                    id not in (
                        select first_shipment_packing_id from stock_picking where first_shipment_packing_id is not null
                    )
            ''')
        else:
            cr.execute('''
                select * from stock_picking
                where
                    subtype='packing' and
                    name ~ 'PACK/[0-9]+-(surplus|return-)?[0-9]+-[0-9]+'
            ''')
        create_ship = []
        for ship in cr.dictfetchall():
            ship_id = ship['id']
            del(ship['id'])
            del(ship['shipment_id'])
            ship['state'] = 'done'
            ship['name'] = '%s-s' % ship['name']
            columns = []
            values = []
            columns = list(ship.keys())
            values = ['%%(%s)s' % x for x in columns]
            cr.execute('''insert into stock_picking (''' +','.join(columns)+ ''') VALUES (''' + ','.join(values) + ''') RETURNING ID''', ship) # not_a_user_entry
            new_ship_id = cr.fetchone()[0]
            create_ship.append(ship['name'])

            cr.execute("select * from stock_move where picking_id = %s", (ship_id,))
            for move in cr.dictfetchall():
                del(move['id'])
                move['picking_id'] = new_ship_id
                move['location_id'] = loc_ship
                move['location_dest_id'] = loc_distrib
                move['state'] = 'done'
                move['date'] = move['create_date']
                columns = []
                values = []
                columns = list(move.keys())
                values = ['%%(%s)s' % x for x in columns]
                cr.execute('''insert into stock_move (''' +','.join(columns)+ ''') VALUES (''' + ','.join(values) + ''') ''', move) # not_a_user_entry

        self._logger.warn('%d shadow pack created from %s' % (len(create_ship), ','.join(create_ship)))
        return True

    def us_6354_trigger_donation_account_sync(self, cr, uid, *a, **b):
        """
        Triggers a synch. on the Intersection Partners at HQ, so that their Donation Payable Account is retrieved in the lower instances
        """
        if _get_instance_level(self, cr, uid) == 'hq':
            cr.execute("""
                UPDATE ir_model_data 
                SET touched ='[''donation_payable_account'']', last_modification = NOW()
                WHERE module='sd' 
                AND model='res.partner' 
                AND res_id IN (
                    SELECT id
                    FROM res_partner
                    WHERE partner_type = 'section'
                );
            """)
            self._logger.warn('Sync. triggered on %s Intersection Partner(s).' % (cr.rowcount,))
        return True

    def us_6457_update_uf_create_date_product(self, cr, uid, *a, **b):
        """
        Fill the uf_create_date for existing products
        """
        cr.execute("""UPDATE product_product SET uf_create_date = create_date WHERE uf_create_date IS NULL""")
        self._logger.warn('Set uf_create_date on %d products' % cr.rowcount)
        return True

    # UF14.1
    def us_6433_remove_sale_override_sourcing(self, cr, uid, *a, **b):
        cr.execute("delete from ir_act_window where id in (select res_id from ir_model_data where name='sale_order_sourcing_progress_action' and module='sale_override' and model='ir.actions.act_window')")
        l1 = cr.rowcount
        cr.execute("delete from ir_model_data where name='sale_order_sourcing_progress_action' and module='sale_override' and model='ir.actions.act_window'")
        l2 = cr.rowcount
        self._logger.warn("Deleted %d+%d old sourcing progress entry" % (l1, l2))
        return True

    def us_6498_set_qty_to_process(self, cr, uid, *a, **b):
        cr.execute('''
            update stock_move
                set selected_number=to_pack-from_pack+1
            where id =ANY(
                select unnest(move_lines) from pack_family_memory where shipment_id in (select id from shipment where state='shipped') and state!='done'
                )
        ''')
        self._logger.warn('Set qty to process on %d stock.move' % cr.rowcount)
        return True

    # UF14.0
    def us_6342_cancel_ir(self, cr, uid, *a, **b):
        """
         bug at IR import: IRs stuck in draft state, edition not allowed => set to Cancel
        """

        ir_name = []
        ir_ids = []
        cr.execute("""select ir.name, ir.id from sale_order ir left join sale_order_line irl on irl.order_id=ir.id  where ir.state='draft' and ir.import_in_progress='t' and ir.procurement_request='t'  group by ir.name,ir.id order by ir.name""")
        for x in cr.fetchall():
            ir_name.append(x[0])
            ir_ids.append(x[1])

        if ir_name:
            self._logger.warn('%d IRs to Cancel: %s' % (len(ir_name), ', '.join(ir_name)))
            # SOL
            cr.execute('''update sale_order_line set state='cancel' where order_id in %s ''', (tuple(ir_ids),))

            # wkf
            cr.execute('''update wkf_workitem set act_id=(select id from wkf_activity where name='cancel' and wkf_id = (select id from wkf where osv='sale.order.line'))
                 where inst_id in (select id from wkf_instance where res_type='sale.order.line' and res_id in (select id from sale_order_line where order_id in %s))
            ''', (tuple(ir_ids),))
            cr.execute('''update wkf_instance set state='complete' where res_type='sale.order.line' and res_id in (select id from sale_order_line where order_id in %s)''', (tuple(ir_ids),))

            # SO
            cr.execute('''update sale_order set state='cancel', import_in_progress='f' where id in %s ''', (tuple(ir_ids),))

        return True

    def us_5952_delivered_closed_outs_to_delivered_state(self, cr, uid, *a, **b):
        """
        Set the OUT pickings in 'Done' state with delivered = True to the 'Delivered' state
        """
        cr.execute('''
            UPDATE stock_picking SET state = 'delivered' 
            WHERE state = 'done' AND type = 'out' AND subtype = 'standard' AND delivered = 't'
        ''')
        return True

    def us_6108_onedrive_bg(self, cr, uid, *a, **b):
        cr.execute("update ir_cron set function='send_backup_bg' where function='send_backup' and model='msf.instance.cloud'")
        return True

    def us_6075_set_paid_invoices_as_closed(self, cr, uid, *a, **b):
        cr.execute('''SELECT i.id, i.number
            FROM account_invoice i
                LEFT JOIN account_move_line l ON i.move_id=l.move_id
                LEFT JOIN account_move_line rec_line ON rec_line.reconcile_id = l.reconcile_id
                LEFT JOIN account_journal j ON j.id = rec_line.journal_id AND j.type in ('cash', 'bank', 'cheque')
            WHERE i.state='paid'
                AND l.reconcile_id is not null
                AND l.account_id=i.account_id
                AND l.is_counterpart
            GROUP BY i.id, i.number
            HAVING min(j.id) IS NULL
            ORDER BY i.id
        ''')
        inv_ids = []
        inv_name = []
        for x in cr.fetchall():
            inv_ids.append(x[0])
            inv_name.append(x[1])
        if inv_ids:
            self._logger.warn('%d Invoices change state from Paid to Close: %s' % (len(inv_ids), ', '.join(inv_name)))
            cr.execute("update account_invoice set state='inv_close' where state='paid' and id in %s", (tuple(inv_ids), ))
        return True

    def us_6076_set_inv_as_from_supply(self, cr, uid, *a, **b):
        """
        Set the new tag from_supply to True in the related account.invoices
        """
        update_inv = """
            UPDATE account_invoice
            SET from_supply = 't' 
            WHERE picking_id IS NOT NULL
            OR id IN (SELECT DISTINCT (invoice_id) FROM shipment WHERE invoice_id IS NOT NULL);
        """
        cr.execute(update_inv)
        self._logger.warn('Tag from_supply set to True in %s account.invoice(s).' % (cr.rowcount,))
        return True


    # UF13.1
    def us_3413_align_in_partner_to_po(self,cr, uid, *a, **b):
        cr.execute("select p.name, p.id, po.partner_id, p.partner_id from stock_picking p, purchase_order po where p.type='in' and po.id = p.purchase_id and ( p.partner_id != po.partner_id or p.partner_id2 != po.partner_id) order by p.name")
        pick_to_update = []
        for x in cr.fetchall():
            pick_to_update.append(x[1])
            self._logger.warn('Update partner on IN: %s, from partner id: %s to id %s' % (x[0], x[3], x[2]))
        if pick_to_update:
            cr.execute('''update stock_picking set (partner_id, partner_id2, address_id) = (select po.partner_id, po.partner_id, po.partner_address_id from purchase_order po where po.id=stock_picking.purchase_id) where id in %s''' , (tuple(pick_to_update),))
            cr.execute('''update stock_move set partner_id=(select partner_id from stock_picking where id=stock_move.picking_id) where picking_id in %s''', (tuple(pick_to_update),))
            cr.execute('''select p.id from stock_picking p, res_partner_address ad where p.address_id = ad.id and p.id in %s and p.partner_id2 != ad.partner_id''', (tuple(pick_to_update),))
            address_to_fix = [x[0] for x in cr.fetchall()]
            if address_to_fix:
                cr.execute('''update stock_picking set address_id=(select min(id) from res_partner_address where partner_id=stock_picking.partner_id) where id in %s''', (tuple(address_to_fix), ))
                self._logger.warn('Update address on %d IN' % cr.rowcount)
        return True

    def us_6111_nr_field_closed_mar_2018(self, cr, uid, *a, **b):
        if not self.pool.get('sync.client.entity'):
            return True

        instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance:
            return True

        if instance.instance.startswith('OCG'):
            cr.execute("""
                update sync_client_update_received set
                    run='t',
                    log='Set manually to run without execution',
                    manually_set_run_date=now(),
                    editable='f'
                where
                    run='f' and
                    sdref = 'FY2018/Mar 2018_2018-03-01' and
                    values like '%''field-closed''%'
            """)
            self._logger.warn('%d NR Mar 2018 field-closed set as run' % (cr.rowcount, ))

        return True

    def us_6128_delete_auto_group(self, cr, uid, *a, **b):
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance_id:
            return True
        if instance_id.level == 'section':
            login_to_del = ['sup_consumption_management', 'sup_consumption_only', 'sup_demand_manager', 'sup_fin_read', 'sup_med_read', 'sup_product_manager', 'sup_product_mgr_coordo', 'sup_purchase_cr', 'sup_purchase_manager', 'sup_purchase_officer', 'sup_purchase_sup', 'sup_read_all', 'sup_request_sourcing', 'sup_request_validator', 'sup_requester', 'sup_store_keeper', 'sup_supply_config', 'sup_supply_system_administrator', 'sup_transport_manager', 'sup_valid_line_fo', 'sup_valid_line_ir', 'sup_valid_line_po', 'sup_warehouse_cr', 'sup_warehouse_manager', 'sync_config', 'sync_manual', 'user_manager', 'fin_accounting_entries_act', 'fin_accounting_entries_consult', 'fin_accounting_reports', 'fin_advanced_accounting', 'fin_bnk_chk_registers', 'fin_bnk_chk_responsible_access', 'fin_budget', 'fin_cash_registers', 'fin_cash_responsible_access', 'fin_config_admin_mission', 'fin_config_coordo', 'fin_config_full', 'fin_config_hq', 'fin_config_project', 'fin_consult_sup', 'fin_grant_mgt', 'fin_hard_posting', 'fin_hq_entries', 'fin_hr', 'fin_invoicing_advanced', 'fin_local_payroll', 'fin_register_project_responsible', 'fin_supplier_invoices', 'fin_supplier_invoices_validation', 'auditor_read']

            cr.execute('delete from res_users where login in %s', (tuple(login_to_del),))
            self._logger.warn('%d users deleted' % (cr.rowcount, ))

        return True

    # UF13.1
    def us_5859_remove_deprecated_objects(self, cr, uid, *a, **b):
        to_del = [
            'stock.move.track',
            'stock.move.consume',
            'stock.move.scrap',
            'create.picking.processor',
            'create.picking.move.processor',
            'create.picking',
            'validate.picking.processor',
            'validate.move.processor',
            'ppl.move.processor',
            'shipment.processor',
            'shipment.family.processor',
            'shipment.additional.line.processor',
            'shipment.wizard',
            'memory.additionalitems',
            'stock.move.memory.shipment.additionalitems',
        ]
        cr.execute('delete from ir_model where model in %s', (tuple(to_del),))
        return True

    def us_5859_set_flag_on_sub_pick(self, cr, uid, *a, **b):
        cr.execute("update stock_picking set is_subpick = 't' where subtype='picking' and name like '%-%'")
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
        rest cu_qty
        """
        trigger_up = self.pool.get('sync.trigger.something.up')
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        if not instance_id:
            return True

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
            'domain': "[('order_id.partner_type', '!=', 'external'), ('state', '!=', 'draft'), ('product_uom_qty', '!=', 0.0), ('order_id.procurement_request', '=', False)]",
            'sequence_number': 12,
            'remote_call': 'purchase.order.line.sol_update_original_pol',
            'arguments': "['resourced_original_line/id', 'resourced_original_remote_line','sync_sourced_origin', 'sync_local_id', 'sync_linked_pol', 'order_id/name', 'product_id/id', 'product_id/name', 'name', 'state','product_uom_qty', 'product_uom', 'price_unit', 'in_name_goods_return', 'analytic_distribution_id/id','comment','have_analytic_distribution_from_header','line_number', 'nomen_manda_0/id','nomen_manda_1/id','nomen_manda_2/id','nomen_manda_3/id', 'nomenclature_description','notes','default_name','default_code','date_planned','is_line_split', 'original_line_id/id', 'confirmed_delivery_date', 'stock_take_date', 'cancel_split_ok', 'modification_comment']",
            'destination_name': 'partner_id',
            'active': True,
            'type': 'MISSION',
            'wait_while': "[('order_id.state', 'in', ['draft', 'draft_p']), ('order_id.partner_type', 'not in', ['external', 'esc']), ('order_id.client_order_ref', '=', False), ('order_id.procurement_request', '=', False)]",
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
                           'secondary_val', 'cu_qty', 'wh_qty', 'cu_val', 'stock_val',
                           'cross_qty', 'cross_val', 'secondary_qty', 'internal_qty', 'stock_qty'
                           ]
        if self.pool.get('sync.client.entity'):
            cr.execute("""update ir_model_data set touched='[''wh_qty'']', last_modification=NOW()
                where
                    module='sd' and model='stock.mission.report.line' and
                    res_id in (
                        select id from stock_mission_report_line where
                        """ + ' OR '.join(['%s!=0'%x for x in fields_to_reset]) + """ )
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
                sock = xmlrpc.client.ServerProxy('http://%s:%s/xmlrpc/db'%(connection['host'], 443), transport=transport)
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
                decoded_datas = base64.b64decode(attachment.datas)
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
                        and name != 'order_types_res_partner_local_market'
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
        #prd_obj = self.pool.get('product.product')
        #data_obj = self.pool.get('ir.model.data')

        #heat_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'heat_yes')[1]
        #no_heat_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'heat_no')[1]

        #prd_ids = prd_obj.search(cr, uid, [('heat_sensitive_item', '!=', False), ('active', 'in', ['t', 'f'])])
        #if prd_ids:
        #    cr.execute("""
        #        UPDATE product_product SET heat_sensitive_item = %s, is_kc = True, kc_txt = 'X', show_cold_chain = True WHERE id IN %s
        #    """, (heat_id, tuple(prd_ids),))

        #no_prd_ids = prd_obj.search(cr, uid, [('heat_sensitive_item', '=', False), ('active', 'in', ['t', 'f'])])
        #if no_prd_ids:
        #    cr.execute("""
        #        UPDATE product_product SET heat_sensitive_item = %s, is_kc = False, kc_txt = '', show_cold_chain = False WHERE id IN %s
        #    """, (no_heat_id, tuple(no_prd_ids),))

        #cr.execute('ALTER TABLE product_product ALTER COLUMN heat_sensitive_item SET NOT NULL')

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

    def log_info(self, cr, uid, msg, context=None):
        self._logger.warn(msg)
        self.pool.get('res.log').create(cr, uid, {
            'name': '[AUTO] %s ' % msg,
            'read': True,
        }, context=context)
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

    def default_get(self, cr, uid, fields_list=None, context=None, from_web=False):
        ret = super(base_setup_company, self).default_get(cr, uid, fields_list, context, from_web=from_web)
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
            fp = tools.file_open(opj('msf_profile', 'data', 'msf.jpg'), 'rb')
            ret['logo'] = base64.b64encode(fp.read())
            fp.close()
        return ret

base_setup_company()

class res_users(osv.osv):
    _inherit = 'res.users'
    _name = 'res.users'

    def _get_default_ctx_lang(self, cr, uid, context=None):
        config_obj = self.pool.get('unifield.setup.configuration')
        if config_obj.search_exists(cr, uid, [], context=context):
            # if not record, get_config create a record
            # incorrect in case of user creation during install
            config_lang = config_obj.get_config(cr, uid).lang_id
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
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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

class sync_tigger_something_target(osv.osv):
    _name = 'sync.trigger.something.target'

    _columns = {
        'name': fields.char('Name', size=256, select=1),
        'destination': fields.char('Destination', size=256, select=1),
        'args': fields.text('Args', select=1),
        'local': fields.boolean('Generated on the instance'),
    }

    _defaults = {
        'local': False,
    }
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('sync_update_execution') and vals.get('name') == 'trigger_rec':
            current_instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
            if current_instance.instance == vals.get('destination'):
                # coordo retrieves updates targeted to project
                rec_obj = self.pool.get('account.move.reconcile')
                # check if this rec num was already requested by an instance
                if not self.search(cr, uid, [('name', '=', 'trigger_rec'), ('args', '=', vals['args']), ('local', '=', False)], context=context):
                    rec_ids = rec_obj.search(cr, uid, [('name', '=', vals['args'])], context=context)
                    if rec_ids:
                        cr.execute('''update account_move_reconcile set action_date=create_date where id in %s''', (tuple(rec_ids),))
                        cr.execute('''update ir_model_data set last_modification=NOW(), touched='[''name'']' where model='account.move.reconcile' and res_id in %s ''', (tuple(rec_ids),))

        return super(sync_tigger_something_target, self).create(cr, uid, vals, context)

sync_tigger_something_target()

class sync_tigger_something_target_lower(osv.osv):
    _inherit = 'sync.trigger.something.target'
    _name = 'sync.trigger.something.target.lower'

    _columns = {

    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        if context.get('sync_update_execution') and vals.get('name') == 'sync_fp':
            current_instance = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id.instance_id
            if current_instance and current_instance.instance == vals.get('destination'):
                fp_to_coo_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'FUNDING'), ('instance_id', '=', current_instance.id)], context=context)
                if fp_to_coo_ids:
                    logging.getLogger('trigger').info('Touch %d fp' % (len(fp_to_coo_ids),))
                    # trigger a sync in SQL in order not to re-trigger sync on the o2m linked to the FP
                    trigger_sync_sql = """
                        UPDATE ir_model_data
                        SET touched ='[''code'']', last_modification=NOW()
                        WHERE module='sd'
                        AND model='account.analytic.account'
                        AND res_id IN %s
                    """
                    cr.execute(trigger_sync_sql, (tuple(fp_to_coo_ids),))

        return super(sync_tigger_something_target_lower, self).create(cr, uid, vals, context)

sync_tigger_something_target_lower()

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
                select id  """ + trans_to_delete + """ )""")  # not_a_user_entry
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
                clear_data = io.StringIO(crypt_o.decrypt(data))
                csv_reader = csv.reader(clear_data, delimiter=',')
                next(csv_reader)
                xmlid_price = {}
                xmlid_code = {}
                prod_id_price = {}

                for line in csv_reader:
                    xmlid_price[line[1]] = float(line[2])
                    xmlid_code[line[1]] = line[0]


                all_xmlid = list(xmlid_price.keys())

                for sdref, p_id in prod_obj.find_sd_ref(cr, uid, all_xmlid).items():
                    prod_id_price[p_id] = xmlid_price[sdref]
                    del xmlid_code[sdref]

                if xmlid_code:
                    _logger.warn('OCG Prod price update, %d products not found: %s' % (len(xmlid_code), ', '.join(list(xmlid_code.values()))))

                nb_updated= 0
                nb_ignored = 0
                for prod in prod_obj.read(cr, uid, list(prod_id_price.keys()), ['standard_price', 'product_tmpl_id']):
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

        if vals.get('name') == 'us-7295-delete-not-hq-links' and context.get('sync_update_execution'):
            cr.execute("""
                DELETE FROM dest_cc_link 
                WHERE id IN (
                    SELECT res_id
                    FROM ir_model_data
                    WHERE module='sd' 
                    AND model='dest.cc.link' 
                    AND name LIKE ANY (
                        SELECT instance_identifier || '%'
                        FROM msf_instance
                        WHERE level IN ('coordo', 'project')
                    )
                )
            """)
            cr.execute("""
                DELETE FROM ir_model_data
                WHERE module='sd' 
                AND model='dest.cc.link' 
                AND name LIKE ANY (
                    SELECT instance_identifier || '%'
                    FROM msf_instance
                    WHERE level IN ('coordo', 'project')
                )
            """)
            _logger.warn('Deletion of %d Dest CC Links created out of HQ' % (cr.rowcount,))

        if vals.get('name') == 'US-12110-Sup_Fin_Read':
            cr.execute("""
            DELETE FROM res_groups_users_rel
            WHERE gid=(SELECT id FROM res_groups WHERE name='Sup_Fin_Read')""")

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
            if vals.get('name') == 'clean_mission_stock_cu':
                remote_id = self.pool.get('msf.instance').search(cr, uid, [('code', '=', vals['args'])])
                if remote_id:
                    cr.execute("update stock_mission_report_line set cu_qty=0, cu_val=0 where mission_report_id in (select id from stock_mission_report where instance_id = %s and full_view='f')", (remote_id[0],))
                    _logger.warn('Reset %d mission stock CU Stock for instance_id %s' % (cr.rowcount, remote_id[0]))
            elif vals.get('name') == 'msr_used':
                cr.execute('''
                    update stock_mission_report_line l
                        set used_in_transaction='t'
                    from
                        ir_model_data d
                    where
                        d.model='stock.mission.report.line' and
                        d.res_id = l.id and
                        d.name in %s
                ''', (tuple((str(zlib.decompress(base64.b64decode(bytes(vals.get('args'), 'utf8'))), 'utf8').split(','))),))
        return super(sync_tigger_something_up, self).create(cr, uid, vals, context)

sync_tigger_something_up()

class sync_tigger_something_bidir_mission(osv.osv):
    _name = 'sync.trigger.something.bidir_mission'

    _columns = {
        'name': fields.char('Name', size=256),
        'args': fields.text('Args'),
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('name') == 'instance_creator_employee' and vals.get('args'):
            # populate instance_creator on hr.employee
            # triggered from sync to process sync in-pipe employee or after init sync
            entity = self.pool.get('sync.client.entity')
            if entity:
                b = time.time()
                cr.execute("""
                    update hr_employee hr
                        set instance_creator=instance.code
                        from
                            ir_model_data d,
                            msf_instance instance
                        where
                            d.module = 'sd' and
                            d.model = 'hr.employee' and
                            d.res_id = hr.id and
                            instance.instance_identifier = split_part(d.name, '/', 1) and
                            coalesce(hr.instance_creator, '') = '' and
                            hr.employee_type='local'
                """)
                self.pool.get('patch.scripts').log_info(cr, uid, 'Instance creator set on %d local employees in %d sec' % (cr.rowcount, time.time() - b))

                c = self.pool.get('res.users').browse(cr, uid, uid).company_id
                instance = c and c.instance_id and c.instance_id
                main_parent = instance.code
                if instance.parent_id:
                    main_parent = instance.parent_id.code
                    if instance.parent_id.parent_id:
                        main_parent = instance.parent_id.parent_id.code
                cr.execute("update hr_employee set instance_creator=%s where employee_type='ex' and coalesce(instance_creator, '') = ''", (main_parent, ))
                self.pool.get('patch.scripts').log_info(cr, uid, 'Instance creator set on %d expat employees' % (cr.rowcount, ))

        return super(sync_tigger_something_bidir_mission, self).create(cr, uid, vals, context)

sync_tigger_something_bidir_mission()
