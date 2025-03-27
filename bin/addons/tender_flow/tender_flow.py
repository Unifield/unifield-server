# -*- coding: utf-8 -*-
##############################################################################
#
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

from datetime import datetime
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from osv import osv, fields
from tools.translate import _
from lxml import etree

import decimal_precision as dp
import netsvc
import time
import tools

from purchase import PURCHASE_ORDER_STATE_SELECTION
from . import RFQ_LINE_STATE_SELECTION

class tender(osv.osv):
    '''
    tender class
    '''
    _name = 'tender'
    _description = 'Tender'
    _trace = True

    def _where_calc(self, cr, uid, domain, active_test=True, context=None):
        '''
        overwrite to allow search on customer and self instance
        '''
        new_dom = []
        product_id = False
        for x in domain:
            if x[0] == 'product_id':
                product_id = x[2]
            else:
                new_dom.append(x)

        ret = super(tender, self)._where_calc(cr, uid, new_dom, active_test=active_test, context=context)
        if product_id and isinstance(product_id, int):
            ret.tables.append('"tender_line"')
            ret.joins.setdefault('"tender"', [])
            ret.joins['"tender"'] += [('"tender_line"', 'id', 'tender_id', 'LEFT JOIN')]
            ret.where_clause.append(''' "tender_line"."product_id" = %s  ''')
            ret.where_clause_params.append(product_id)
        return ret

    def copy(self, cr, uid, id, default=None, context=None, done_list=[], local=False):
        if not default:
            default = {}
        default.update({
            'internal_state': 'draft',  # UF-733: Reset the internal_state
            'currency_id': False,
        })
        if not 'sale_order_id' in default:
            default['sale_order_id'] = False
        return super(osv.osv, self).copy(cr, uid, id, default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        cannot delete tender not draft
        '''
        # Objects
        t_line_obj = self.pool.get('tender.line')

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state != 'draft':
                raise osv.except_osv(_('Warning !'), _("Cannot delete Tenders not in 'draft' state."))

            if obj.sale_order_id:
                obj_name = obj.sale_order_id.procurement_request and _('an Internal Request') or _('a Field Order')
                raise osv.except_osv(_('Warning !'), _("This tender is linked to %s, so you cannot delete it. Please cancel it instead.") % obj_name)

            for line in obj.tender_line_ids:
                t_line_obj.fake_unlink(cr, uid, [line.id], context=context)

        return super(tender, self).unlink(cr, uid, ids, context=context)

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        return function values
        '''
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {'rfq_name_list': '',
                              }
            rfq_names = []
            for rfq in obj.rfq_ids:
                rfq_names.append(rfq.name)
            # generate string
            rfq_names.sort()
            result[obj.id]['rfq_name_list'] = ','.join(rfq_names)

        return result

    def _is_tender_from_fo(self, cr, uid, ids, field_name, args, context=None):
        # TODO JFB RR: partner on tender
        res = {}
        for tender_id in ids:
            res[tender_id] = False
        return res

    def _diff_nb_rfq_supplier(self, cr, uid, ids, field, args, context=None):
        if context is None:
            context = {}

        res = {}
        for tender in self.browse(cr, uid, ids, fields_to_fetch=['rfq_ids', 'supplier_ids'], context=context):
            diff_number = False
            supplier_ids = [supplier.id for supplier in tender.supplier_ids]
            rfq_ids = [rfq.id for rfq in tender.rfq_ids if rfq.partner_id.id in supplier_ids]
            if len(rfq_ids) < len(supplier_ids):
                diff_number = True
            res[tender.id] = diff_number
        return res

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        '''
        Fake method for 'product_id' field
        '''
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    _columns = {
        'name': fields.char('Tender Reference', size=64, required=True, select=True, readonly=True, sort_column='id'),
        'sale_order_id': fields.many2one('sale.order', string="Sale Order", readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('comparison', 'Comparison'), ('done', 'Closed'), ('cancel', 'Cancelled'), ], string="State", readonly=True),
        'supplier_ids': fields.many2many('res.partner', 'tender_supplier_rel', 'tender_id', 'supplier_id', string="Suppliers", domain="[('id', '!=', company_id)]",
                                         states={'draft': [('readonly', False)], 'comparison': [('readonly', False)]}, readonly=True,
                                         context={'search_default_supplier': 1, }),
        'location_id': fields.many2one('stock.location', 'Location', required=True, states={'draft': [('readonly', False)]}, readonly=True, domain=[('usage', '=', 'internal')]),
        'company_id': fields.many2one('res.company', 'Company', required=True, states={'draft': [('readonly', False)]}, readonly=True),
        'rfq_ids': fields.one2many('purchase.order', 'tender_id', string="RfQs", readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Tender Priority', states={'draft': [('readonly', False)], }, readonly=True,),
        'categ': fields.selection(ORDER_CATEGORY, string='Tender Category', required=True, states={'draft': [('readonly', False)], }, readonly=True, add_empty=True),
        'creator': fields.many2one('res.users', string="Creator", readonly=True, required=True,),
        'warehouse_id': fields.many2one('stock.warehouse', string="Warehouse", required=True, states={'draft': [('readonly', False)], }, readonly=True),
        'creation_date': fields.date(string="Creation Date", readonly=True, states={'draft': [('readonly', False)]}),
        'details': fields.char(size=30, string="Details", states={'draft': [('readonly', False)], }, readonly=True),
        'requested_date': fields.date(string="Requested Date", required=True, states={'draft': [('readonly', False)], }, readonly=True),
        'notes': fields.text('Notes'),
        'internal_state': fields.selection([('draft', 'Draft'), ('updated', 'Rfq Updated'), ], string="Internal State", readonly=True),
        'rfq_name_list': fields.function(_vals_get, method=True, string='RfQs Ref', type='char', readonly=True, store=False, multi='get_vals',),
        'product_id': fields.function(_get_fake, method=True, type='many2one', relation='product.product', string='Product', help='Product to find in the lines', store=False, readonly=True),
        'delivery_address': fields.many2one('res.partner.address', string='Delivery address', required=True),
        'tender_from_fo': fields.function(_is_tender_from_fo, method=True, type='boolean', string='Is tender from FO ?',),
        'diff_nb_rfq_supplier': fields.function(_diff_nb_rfq_supplier, method=True, type="boolean", string="Compare the number of rfqs and the number of suppliers", store=False),
        'currency_id': fields.many2one('res.currency', 'Currency for Comparison', help="Currency to use while comparing RfQs"),
    }

    _defaults = {
        'categ': False,
        'state': 'draft',
        'internal_state': 'draft',
        'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
        'creator': lambda obj, cr, uid, context: uid,
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'requested_date': lambda *a: time.strftime('%Y-%m-%d'),
        'priority': 'normal',
        'warehouse_id': lambda obj, cr, uid, context: len(obj.pool.get('stock.warehouse').search(cr, uid, [])) and obj.pool.get('stock.warehouse').search(cr, uid, [])[0],
    }

    _sql_constraints = [
    ]

    _order = 'id desc'

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is no restrictive products in lines
        '''
        if isinstance(ids, int):
            ids = [ids]

        line_obj = self.pool.get('tender.line')

        res = True
        for tender in self.browse(cr, uid, ids, context=context):
            res = res and line_obj._check_restriction_line(cr, uid, [x.id for x in tender.tender_line_ids if x.line_state != 'cancel'], context=context)

        return res

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Set default data
        '''
        # Object declaration
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')

        res = super(tender, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        # Get the delivery address
        company = user_obj.browse(cr, uid, uid, context=context).company_id
        res['delivery_address'] = partner_obj.address_get(cr, uid, company.partner_id.id, ['delivery'])['delivery']

        return res

    def _check_tender_from_fo(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        retour = True
        for tender in self.browse(cr, uid, ids, context=context):
            if not tender.tender_from_fo:
                return retour
            for sup in tender.supplier_ids:
                if sup.partner_type == 'internal':
                    retour = False
        return retour

    _constraints = [
        (_check_tender_from_fo, 'You cannot choose an internal supplier for this tender', []),
    ]

    def create(self, cr, uid, vals, context=None):
        '''
        Set the reference of the tender at this time
        '''
        if not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'tender')})

        return super(tender, self).create(cr, uid, vals, context=context)


    def write(self, cr, uid, ids, vals, context=None):
        """
        Check consistency between lines and categ of tender
        """
        if not ids:
            return True
        # UFTP-317: Make sure ids is a list
        if isinstance(ids, int):
            ids = [ids]
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        if ('state' in vals and vals.get('state') not in ('draft', 'comparison')) or \
           ('sale_order_line_id' in vals and vals.get('sale_order_line_id')):
            exp_sol_ids = exp_sol_obj.search(cr, uid, [
                ('tender_id', 'in', ids),
            ], context=context)
            exp_sol_obj.unlink(cr, uid, exp_sol_ids, context=context)

        r =  super(tender, self).write(cr, uid, ids, vals, context=context)
        if 'supplier_ids' in vals:
            for t_id in ids:
                # prevent deletion of partner if RfQ generated
                cr.execute("select partner_id from purchase_order po left join tender_supplier_rel sup on sup.tender_id = po.tender_id and sup.supplier_id = po.partner_id  where po.tender_id = %s and sup.supplier_id is null", (t_id,))
                missing_partners = [x[0] for x in cr.fetchall()]
                if missing_partners:
                    super(tender, self).write(cr, uid, [t_id], {'supplier_ids': [(4,x) for x in missing_partners]}, context=context)
        return r

    def onchange_categ(self, cr, uid, ids, category, context=None):
        """
        Check if the list of products is valid for this new category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of purchase.order to check
        :param category: DB value of the new choosen category
        :param context: Context of the call
        :return: A dictionary containing the warning message if any
        """
        nomen_obj = self.pool.get('product.nomenclature')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        message = {}
        res = False

        if ids and category in ['log', 'medical']:
            # Check if all product nomenclature of products in Tender lines are consistent with the category
            try:
                med_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'MED')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('MED nomenclature Main Type not found'))
            try:
                log_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'LOG')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('LOG nomenclature Main Type not found'))

            nomen_id = category == 'log' and log_nomen or med_nomen
            cr.execute('''SELECT l.id
                          FROM tender_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template pt ON p.product_tmpl_id = pt.id
                            LEFT JOIN tender t ON l.tender_id = t.id
                          WHERE (pt.nomen_manda_0 != %s) AND t.id in %s LIMIT 1''',
                       (nomen_id, tuple(ids)))
            res = cr.fetchall()

        if ids and category in ['service', 'transport']:
            # Avoid selection of non-service producs on Service Tender
            category = category == 'service' and 'service_recep' or 'transport'
            transport_cat = ''
            if category == 'transport':
                transport_cat = 'OR p.transport_ok = False'
            cr.execute('''SELECT l.id
                          FROM tender_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template pt ON p.product_tmpl_id = pt.id
                            LEFT JOIN tender t ON l.tender_id = t.id
                          WHERE (pt.type != 'service_recep' %s) AND t.id in %%s LIMIT 1''' % transport_cat, (tuple(ids),))  # not_a_user_entry
            res = cr.fetchall()

        if res:
            message.update({
                'title': _('Warning'),
                'message': _('This order category is not consistent with product(s) on this tender.'),
            })

        return {'warning': message}

    def onchange_warehouse(self, cr, uid, ids, warehouse_id, context=None):
        '''
        on_change function for the warehouse
        '''
        result = {'value': {}, }
        if warehouse_id:
            input_loc_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_input_id.id
            result['value'].update(location_id=input_loc_id)

        return result

    def change_supplier(self, cr, uid, ids, supplier_ids, context=None):
        if ids and supplier_ids and isinstance(supplier_ids, list) and isinstance(supplier_ids[0], tuple) and len(supplier_ids[0]) == 3:
            # display generates RfQs
            nb_po = self.pool.get('purchase.order').search(cr, uid, [('tender_id', 'in', ids)], count=True)
            return {'value': {'diff_nb_rfq_supplier': nb_po!=len(supplier_ids[0][2])}}

        return {}

    def wkf_generate_rfq(self, cr, uid, ids, context=None):
        '''
        generate the rfqs for each specified supplier
        '''
        if context is None:
            context = {}
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        partner_obj = self.pool.get('res.partner')
        obj_data = self.pool.get('ir.model.data')

        # no suppliers -> raise error
        for tender in self.browse(cr, uid, ids, context=context):
            # check some supplier have been selected
            if not tender.supplier_ids:
                raise osv.except_osv(_('Warning !'), _('You must select at least one supplier!'))
            # utp-315: check that the suppliers are not inactive (I use a SQL request because the inactive partner are ignored with the browse)
            sql = """
            select tsr.supplier_id, rp.name, rp.active
            from tender_supplier_rel tsr
            left join res_partner rp
            on tsr.supplier_id = rp.id
            where tsr.tender_id=%s
            and rp.active=False
            """
            cr.execute(sql, (ids[0],))
            inactive_supplier_ids = cr.dictfetchall()
            if any(inactive_supplier_ids):
                raise osv.except_osv(_('Warning !'), _("You can't have inactive supplier! Please remove: %s"
                                                       ) % ' ,'.join([partner['name'] for partner in inactive_supplier_ids]))
            # check some products have been selected
            tender_line_ids = self.pool.get('tender.line').search(cr, uid, [('tender_id', '=', tender.id), ('line_state', '!=', 'cancel')], context=context)
            if not tender_line_ids:
                raise osv.except_osv(_('Warning !'), _('You must select at least one product!'))
            for supplier in tender.supplier_ids:
                if not po_obj.search_exist(cr,  uid, [('tender_id', '=', tender.id), ('partner_id', '=', supplier.id)], context=context):
                    # create a purchase order for each supplier
                    address_id = partner_obj.address_get(cr, uid, [supplier.id], ['default'])['default']
                    if not address_id:
                        raise osv.except_osv(_('Warning !'), _('The supplier "%s" has no address defined!') % (supplier.name,))
                    pricelist_id = supplier.property_product_pricelist_purchase.id
                    values = {
                        'origin': tender.sale_order_id and tender.sale_order_id.name + ';' + tender.name or tender.name,
                        'rfq_ok': True,
                        'partner_id': supplier.id,
                        'partner_address_id': address_id,
                        'location_id': tender.location_id.id,
                        'pricelist_id': pricelist_id,
                        'company_id': tender.company_id.id,
                        'fiscal_position': supplier.property_account_position and supplier.property_account_position.id or False,
                        'tender_id': tender.id,
                        'warehouse_id': tender.warehouse_id.id,
                        'categ': tender.categ,
                        'priority': tender.priority,
                        'details': tender.details,
                        'delivery_requested_date': tender.requested_date,
                        'rfq_delivery_address': tender.delivery_address and tender.delivery_address.id or False,
                    }
                    # create the rfq - dic is udpated for default partner_address_id at purchase.order level
                    po_id = po_obj.create(cr, uid, values, context=dict(context, partner_id=supplier.id, rfq_ok=True))

                    for line in tender.tender_line_ids:
                        if line.line_state == 'cancel':
                            continue

                        if line.qty <= 0.00:
                            raise osv.except_osv(_('Error !'), _('You cannot generate RfQs for an line with a null quantity.'))

                        if line.product_id.id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]:
                            raise osv.except_osv(_('Warning !'), _('You can\'t have "To Be Defined" for the product. Please select an existing product.'))
                        newdate = datetime.strptime(line.date_planned, '%Y-%m-%d')
                        values = {'name': line.product_id.partner_ref,
                                  'product_qty': line.qty,
                                  'product_id': line.product_id.id,
                                  'product_uom': line.product_uom.id,
                                  'price_unit': 0.0,  # was price variable - uf-607
                                  'date_planned': newdate.strftime('%Y-%m-%d'),
                                  'notes': line.product_id.description_purchase,
                                  'order_id': po_id,
                                  'tender_line_id': line.id,
                                  'comment': line.comment,
                                  }
                        # create purchase order line
                        pol_obj.create(cr, uid, values, context=context)
                        message = _("Request for Quotation '%s' has been created.") % po_obj.browse(cr, uid, po_id, context=context).name
                        # create the log message
                        self.pool.get('res.log').create(cr, uid,
                                                        {'name': message,
                                                         'res_model': po_obj._name,
                                                         'secondary': False,
                                                         'res_id': po_id,
                                                         'domain': [('rfq_ok', '=', True)],
                                                         }, context={'rfq_ok': True})
                    self.infolog(cr, uid, "The RfQ id:%s (%s) has been generated from tender id:%s (%s)" % (
                        po_id,
                        po_obj.read(cr, uid, po_id, ['name'], context=context)['name'],
                        tender.id,
                        tender.name,
                    ))

        self.write(cr, uid, ids, {'state': 'comparison'}, context=context)
        return True

    def check_continue_sourcing(self, cr, uid, ids, context=None):
        '''
        Warn the user if the Tender, coming from an FO, has both service and non-service products
        '''
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        t_line_obj = self.pool.get('tender.line')

        for tender in self.browse(cr, uid, ids, fields_to_fetch=['sale_order_id'], context=context):
            if tender.sale_order_id and not tender.sale_order_id.procurement_request:
                has_srv_prod = t_line_obj.search_exist(cr, uid, [('tender_id', '=', tender.id),
                                                                 ('product_id.type', '=', 'service_recep')], context=context)
                has_not_srv_prod = t_line_obj.search_exist(cr, uid, [('tender_id', '=', tender.id),
                                                                     ('product_id.type', '!=', 'service_recep')], context=context)
                if has_srv_prod and has_not_srv_prod:
                    wiz_id = self.pool.get('tender.has.service.not.service.product.wizard').create(cr, uid, {'tender_id': tender.id}, context=context)
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'tender_has_service_not_service_product_wizard_form_view')[1]

                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'tender.has.service.not.service.product.wizard',
                        'res_id': wiz_id,
                        'view_type': 'form',
                        'view_mode': 'form',
                        'view_id': [view_id],
                        'target': 'new',
                        'context': context
                    }

        return self.continue_sourcing(cr, uid, ids, context=context)

    def continue_sourcing(self, cr, uid, ids, context=None):
        '''
        call when pressing "coutinue sourcing progress" button on tender
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        self.create_po(cr, uid, ids, context=context)

        wf_service = netsvc.LocalService("workflow")
        for tender_id in ids:
            wf_service.trg_validate(uid, 'tender', tender_id, 'button_done', cr)

        return True

    def wkf_action_done(self, cr, uid, ids, context=None):
        '''
        check all rfq are updated (or cancel)
        create or update PO to selected suppliers
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for tender in self.browse(cr, uid, ids, context=context):
            # close linked RfQ:
            for rfq in tender.rfq_ids:
                if rfq.rfq_state in ('updated', 'cancel'):
                    pol_obj = self.pool.get('purchase.order.line')
                    non_cancel_rfq_line_ids = pol_obj.search(cr, uid, [('order_id', '=', rfq.id), ('state', 'not in', ['cancel', 'cancel_r']),
                                                                       ('rfq_line_state', 'not in', ['cancel', 'cancel_r'])], context=context)
                    pol_obj.write(cr, uid, non_cancel_rfq_line_ids, {'rfq_line_state': 'done'}, context=context)
                    self.pool.get('purchase.order').write(cr, uid, [rfq.id], {'rfq_state': 'done'}, context=context)

            self.write(cr, uid, [tender.id], {'state': 'done'}, context=context)
            self.infolog(cr, uid, "The tender id:%s (%s) has been closed" % (tender.id, tender.name))

        return True

    def tender_integrity(self, cr, uid, tender, context=None):
        '''
        check the state of corresponding RfQs
        '''
        po_obj = self.pool.get('purchase.order')
        # no rfq in done state
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id), ('rfq_state', '=', 'done')], context=context)
        if rfq_ids:
            raise osv.except_osv(_('Error !'), _("Some RfQ are already Closed. Integrity failure."))
        # all rfqs must have been treated
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),
                                          ('rfq_state', 'in', ('draft', 'sent',)), ], context=context)
        if rfq_ids:
            raise osv.except_osv(_('Warning !'), _("Generated RfQs must be Updated or Cancelled."))
        # at least one rfq must be updated and not canceled
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),
                                          ('rfq_state', 'in', ('updated',)), ], context=context)
        if not rfq_ids:
            raise osv.except_osv(_('Warning !'), _("At least one RfQ must be in state Updated."))

        if tender.diff_nb_rfq_supplier:
            raise osv.except_osv(_('Warning !'), _("Please Generate RfQs for all Suppliers"))

        return rfq_ids

    def compare_rfqs(self, cr, uid, ids, context=None):
        '''
        compare rfqs button
        '''
        if len(ids) > 1:
            raise osv.except_osv(_('Warning !'), _('Cannot compare rfqs of more than one tender at a time!'))

        wiz_obj = self.pool.get('wizard.compare.rfq')

        for tender in self.browse(cr, uid, ids, context=context):
            # check if corresponding rfqs are in the good state
            rfq_ids = self.tender_integrity(cr, uid, tender, context=context)
            # gather the product_id -> supplier_id relationship to display it back in the compare wizard
            suppliers = {}
            for line in tender.tender_line_ids:
                if line.product_id and line.supplier_id and line.line_state != 'cancel':
                    suppliers.update({line.product_id.id: line.supplier_id.id, })
            # rfq corresponding to this tender with done state (has been updated and not canceled)
            # the list of rfq which will be compared
            c = dict(context, active_ids=rfq_ids, tender_id=tender.id, end_wizard=False, suppliers=suppliers,)
            # open the wizard
            action = wiz_obj.start_compare_rfq(cr, uid, ids, context=c)
        return action

    def create_po(self, cr, uid, ids, context=None):
        '''
        create a po from the updated RfQs
        '''
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        t_line_obj = self.pool.get('tender.line')
        po_to_use = False

        for tender in self.browse(cr, uid, ids, context=context):
            # check if corresponding rfqs are in the good state
            self.tender_integrity(cr, uid, tender, context=context)
            # integrity check, all lines must have purchase_order_line_id
            if not all([line.purchase_order_line_id.id for line in tender.tender_line_ids if line.line_state != 'cancel']):
                raise osv.except_osv(_('Error !'), _('All tender lines must have been compared!'))

            # Use the DPO order type if there is a service product used
            for tender_line in tender.tender_line_ids:
                if tender_line.line_state == 'cancel':
                    continue

                # search or create PO to use:
                order_type = 'regular'
                if tender.sale_order_id and not tender.sale_order_id.procurement_request and \
                        tender_line.product_id.type == 'service_recep':  # Only if coming from a FO
                    order_type = 'direct'
                po_to_use = t_line_obj.get_existing_po(cr, uid, [tender_line.id], order_type, context=context)
                if not po_to_use:
                    po_to_use = t_line_obj.create_po_from_tender_line(cr, uid, [tender_line.id], order_type, context=context)
                    # log new PO:
                    po = self.pool.get('purchase.order').browse(cr, uid, po_to_use, context=context)
                    self.pool.get('purchase.order').log(cr, uid, po_to_use, _('The Purchase Order %s for supplier %s has been created.') % (po.name, po.partner_id.name))
                    self.pool.get('purchase.order').infolog(cr, uid, 'The Purchase order %s for supplier %s has been created.' % (po.name, po.partner_id.name))

                anal_dist_to_copy = tender_line.sale_order_line_id and tender_line.sale_order_line_id.analytic_distribution_id.id or False

                # attach new PO line:
                pol_values = {
                    'order_id': po_to_use,
                    'linked_sol_id': tender_line.sale_order_line_id.id or False,
                    'origin': tender_line.sale_order_line_id and tender_line.sale_order_line_id.order_id.name or False,
                    'name': tender_line.product_id.partner_ref,
                    'product_qty': tender_line.qty,
                    'product_id': tender_line.product_id.id,
                    'product_uom': tender_line.product_uom.id,
                    'change_price_manually': 'True',
                    'price_unit': tender_line.price_unit,
                    'date_planned': tender_line.date_planned,
                    'move_dest_id': False,
                    'notes': tender_line.product_id.description_purchase,
                    'comment': tender_line.comment,
                }
                if anal_dist_to_copy:
                    pol_values['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, anal_dist_to_copy, {}, context=context)
                self.pool.get('purchase.order.line').create(cr, uid, pol_values, context=context)

            # when the po is generated, the tender is done - no more modification or comparison
            self.wkf_action_done(cr, uid, [tender.id], context=context)

        return po_to_use

    def cancel_tender(self, cr, uid, ids, context=None):
        '''
        Ask the user if he wants to re-source all lines
        '''
        wiz_obj = self.pool.get('tender.cancel.wizard')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for tender_id in ids:
            tender = self.read(cr, uid, ids[0], ['state', 'sale_order_id'], context=context)

            wiz_id = wiz_obj.create(cr, uid, {
                'tender_id': tender['id'],
                'not_draft': tender['state'] != 'draft',
                'no_need': not tender['sale_order_id'],
            }, context=context)

            if tender['sale_order_id'] or tender['state'] != 'draft':
                return {'type': 'ir.actions.act_window',
                        'res_model': 'tender.cancel.wizard',
                        'res_id': wiz_id,
                        'view_mode': 'form',
                        'view_type': 'form',
                        'target': 'new',
                        'context': context}
            else:
                wiz_obj.just_cancel(cr, uid, [wiz_id], context=context)

        return {}

    def wkf_action_cancel(self, cr, uid, ids, context=None):
        '''
        cancel all corresponding rfqs
        '''
        if context is None:
            context = {}

        t_line_obj = self.pool.get('tender.line')
        po_obj = self.pool.get('purchase.order')

        # set state
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        for tender in self.browse(cr, uid, ids, context=context):
            # search for the rfqs
            rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id), ('rfq_ok', '=', True)], context=context)
            # trigger all related rfqs
            po_obj.cancel_rfq(cr, uid, rfq_ids, context=context, resource=False)

            for line in tender.tender_line_ids:
                t_line_obj.cancel_sourcing(cr, uid, [line.id], context=context)
            self.infolog(cr, uid, "The tender id:%s (%s) has been canceled" % (
                tender.id,
                tender.name,
            ))

        return True

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the tender and all related documents to done state
        '''
        if isinstance(ids, int):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        for tender in self.browse(cr, uid, ids, context=context):
            line_updated = False
            if tender.state not in ('done', 'cancel'):
                for line in tender.tender_line_ids:
                    if line.purchase_order_line_id:
                        line_updated = True
                # Cancel or done all RfQ related to the tender
                for rfq in tender.rfq_ids:
                    if rfq.state not in ('done', 'cancel'):
                        if rfq.state == 'draft' or not line_updated:
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'purchase_cancel', cr)
                        else:
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_sent', cr)
                            if not rfq.valid_till:
                                self.pool.get('purchase.order').write(cr, uid, [rfq.id], {'valid_till': time.strftime('%Y-%m-%d')}, context=context)
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_updated', cr)

                if all_doc:
                    if tender.state == 'draft' or not tender.tender_line_ids or not line_updated:
                        # Call the cancel method of the tender
                        wf_service.trg_validate(uid, 'tender', tender.id, 'tender_cancel', cr)
                    else:
                        # Call the cancel method of the tender
                        wf_service.trg_validate(uid, 'tender', tender.id, 'button_done', cr)

        return True

    def check_empty_tender(self, cr, uid, ids, context=None):
        """
        If the tender is empty, return a wizard to ask user if he wants to
        cancel the whole tender
        """
        tender_wiz_obj = self.pool.get('tender.cancel.wizard')
        data_obj = self.pool.get('ir.model.data')

        for tender in self.browse(cr, uid, ids, context=context):
            if all(x.line_state in ('cancel', 'done') for x in tender.tender_line_ids):
                wiz_id = tender_wiz_obj.create(cr, uid, {'tender_id': tender.id}, context=context)
                view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'ask_tender_cancel_wizard_form_view')[1]
                return {'type': 'ir.actions.act_window',
                        'res_model': 'tender.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'view_id': [view_id],
                        'res_id': wiz_id,
                        'target': 'new',
                        'context': context}

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tender',
            'view_type': 'form',
            'view_mode': 'form, tree',
            'res_id': ids[0],
            'context': context,
            'target': 'crush',
        }

    def sourcing_document_state(self, cr, uid, ids, context=None):
        """
        Returns all documents that are in the sourcing for a givent tender
        """
        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        po_obj = self.pool.get('purchase.order')

        # corresponding sale order
        so_ids = []
        for tender in self.browse(cr, uid, ids, context=context):
            if tender.sale_order_id and tender.sale_order_id.id not in so_ids:
                so_ids.append(tender.sale_order_id.id)

        # from so, list corresponding po
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)

        # from listed po, list corresponding so
        all_so_ids = po_obj.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)

        all_sol_not_confirmed_ids = []
        # if we have sol_ids, we are treating a po which is make_to_order from sale order
        if all_so_ids:
            all_sol_not_confirmed_ids = sol_obj.search(cr, uid, [
                ('order_id', 'in', all_so_ids),
                ('type', '=', 'make_to_order'),
                ('product_id', '!=', False),
                ('state', 'not in', ['confirmed', 'done']),
            ], context=context)

        return so_ids, all_po_ids, all_so_ids, all_sol_not_confirmed_ids

    def change_currency(self, cr, uid, ids, context=None):
        '''
        Just reload the tender
        '''
        if not context:
            context = {}

        return True


tender()


class tender_line(osv.osv):
    '''
    tender lines
    '''
    _name = 'tender.line'
    _rec_name = 'product_id'
    _description = 'Tender Line'
    _trace = True

    _SELECTION_TENDER_STATE = [('draft', 'Draft'), ('comparison', 'Comparison'), ('done', 'Closed'), ]
    _max_qty = 10**10
    _max_msg = _('The quantity of the line has more than 10 digits. Please check the Qty to avoid loss of exact information')

    def on_product_change(self, cr, uid, id, product_id, uom_id, product_qty, categ, context=None):
        '''
        product is changed, we update the UoM
        '''
        if not context:
            context = {}

        prod_obj = self.pool.get('product.product')
        result = {'value': {}}
        if product_id:
            # Test the compatibility of the product with a tender
            result, test = prod_obj._on_change_restriction_error(cr, uid, product_id, field_name='product_id', values=result, vals={'constraints': ['external', 'esc', 'internal']}, context=context)
            if test:
                return result

            product = prod_obj.browse(cr, uid, product_id, context=context)
            result['value']['product_uom'] = product.uom_id.id
            result['value']['text_error'] = False
            result['value']['to_correct_ok'] = False

        res_qty = self.onchange_uom_qty(cr, uid, id, uom_id or result.get('value', {}).get('product_uom', False), product_qty)
        result['value']['qty'] = res_qty.get('value', {}).get('qty', product_qty)

        if uom_id:
            result['value']['product_uom'] = uom_id

        if categ and product_id:
            # Check consistency of product
            consistency_message = prod_obj.check_consistency(cr, uid, product_id, categ, context=context)
            if consistency_message:
                result.setdefault('warning', {})
                result['warning'].setdefault('title', 'Warning')
                result['warning'].setdefault('message', '')

                result['warning']['message'] = '%s \n %s' % \
                    (result.get('warning', {}).get('message', ''), consistency_message)

        return result

    def onchange_uom_qty(self, cr, uid, ids, uom_id, qty):
        '''
        Check round of qty according to the UoM
        '''
        res = {}

        tl = {}
        if ids:
            tl = self.read(cr, uid, ids[0], ['qty'])
        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'qty', result=res)

        if qty >= self._max_qty:
            res.setdefault('warning', {'title': '', 'message': ''})
            res['warning'].setdefault('title', '')
            res['warning'].setdefault('message', '')
            res.update({
                'value': {'qty': tl.get('qty', 0.00)},
                'warning': {'title': 'Warning', 'message': "\n".join([res['warning']['message'], _(self._max_msg)])}
            })

        return res

    def _get_total_price(self, cr, uid, ids, field_name, arg, context=None):
        '''
        return the subtotal
        '''
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            result[line.id] = {}
            if line.price_unit and line.qty:
                result[line.id]['total_price'] = line.price_unit * line.qty
            else:
                result[line.id]['total_price'] = 0.0

            if line.purchase_order_line_id:
                result[line.id]['currency_id'] = line.purchase_order_line_id.order_id.pricelist_id.currency_id.id
            else:
                result[line.id]['currency_id'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id

        return result

    def name_get(self, cr, user, ids, context=None):
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            code = rs.product_id and rs.product_id.name or ''
            res += [(rs.id, code)]
        return res

    _columns = {
        'product_id': fields.many2one('product.product', string="Product", required=True),
        'qty': fields.float(string="Qty", required=True, related_uom='product_uom'),
        'tender_id': fields.many2one('tender', string="Tender", required=True, ondelete='cascade'),
        'purchase_order_line_id': fields.many2one('purchase.order.line', string="Related RfQ line", readonly=True),
        'sale_order_line_id': fields.many2one('sale.order.line', string="Sale Order Line"),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'date_planned': fields.related('tender_id', 'requested_date', type='date', string='Requested Date', store=False, write_relate=False),
        # functions
        'supplier_id': fields.related('purchase_order_line_id', 'order_id', 'partner_id', type='many2one', relation='res.partner', string="Supplier", readonly=True),
        'price_unit': fields.related('purchase_order_line_id', 'price_unit', type="float", string="Unit Price", digits_compute=dp.get_precision('Purchase Price Computation'), readonly=True),  # same precision as related field!
        'delivery_confirmed_date': fields.related('purchase_order_line_id', 'confirmed_delivery_date', type="date", string="Confirmed DD", readonly=True),
        'total_price': fields.function(_get_total_price, method=True, type='float', string="Subtotal", digits_compute=dp.get_precision('Purchase Price'), multi='total'),
        'currency_id': fields.function(_get_total_price, method=True, type='many2one', relation='res.currency', string='Currency', multi='total'),
        'purchase_order_id': fields.related('purchase_order_line_id', 'order_id', type='many2one', relation='purchase.order', string="Related RfQ", readonly=True,),
        'purchase_order_line_number': fields.related('purchase_order_line_id', 'line_number', type="char", string="Related Line Number", readonly=True,),
        'state': fields.related('tender_id', 'state', type="selection", selection=_SELECTION_TENDER_STATE, string="State", write_relate=False),
        'line_state': fields.selection([('draft', 'Draft'), ('cancel', 'Cancelled'), ('cancel_r', 'Cancelled-r'), ('done', 'Done')], string='State', readonly=True),
        'comment': fields.char(size=128, string='Comment'),
        'has_to_be_resourced': fields.boolean(string='Has to be resourced'),
        'created_by_rfq': fields.boolean(string='Created by RfQ'),
        'product_default_code': fields.related('product_id', 'default_code', type='char', string='Product Code', size=64, store=False, write_relate=False),
        'product_name': fields.related('product_id', 'name', type='char', string='Product Description', size=128, store=False, write_relate=False),
    }

    _defaults = {
        'qty': lambda *a: 1.0,
        'state': lambda *a: 'draft',
        'line_state': lambda *a: 'draft',
    }

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is no restrictive products in lines
        '''
        if isinstance(ids, int):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.tender_id and line.product_id:
                if not self.pool.get('product.product')._get_restriction_error(cr, uid, line.product_id.id, vals={'constraints': ['external']}, context=context):
                    return False

        return True

    _sql_constraints = [
        #        ('product_qty_check', 'CHECK( qty > 0 )', 'Product Quantity must be greater than zero.'),
    ]

    def create(self, cr, uid, vals, context=None):
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        tender_obj = self.pool.get('tender')

        res = super(tender_line, self).create(cr, uid, vals, context=context)

        if 'tender_id' in vals and not vals.get('sale_order_line_id'):
            so_id = tender_obj.read(cr, uid, vals.get('tender_id'), ['sale_order_id'], context=context)['sale_order_id']
            if so_id:
                exp_sol_obj.create(cr, uid, {
                    'order_id': so_id[0],
                    'tender_line_id': res,
                }, context=context)

        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        if 'state' in vals and vals.get('state') != 'draft':
            exp_sol_ids = exp_sol_obj.search(cr, uid, [
                ('tender_line_id', 'in', ids),
            ], context=context)
            exp_sol_obj.unlink(cr, uid, exp_sol_ids, context=context)

        return super(tender_line, self).write(cr, uid, ids, vals, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}

        if not 'created_by_rfq' in default:
            default['created_by_rfq'] = False

        return super(tender_line, self).copy(cr, uid, id, default, context=context)

    def cancel_sourcing(self, cr, uid, ids, context=None):
        '''
        Cancel the line and re-source the FO line
        '''
        # Objects
        sol_obj = self.pool.get('sale.order.line')
        uom_obj = self.pool.get('product.uom')
        tender_obj = self.pool.get('tender')

        # Variables
        to_remove = []
        to_cancel = []
        sol_to_resource = []
        sol_to_update = {}
        sol_not_to_delete = []
        so_to_update = set()
        tender_to_update = set()

        for line in self.browse(cr, uid, ids, context=context):
            tender_to_update.add(line.tender_id.id)
            if line.sale_order_line_id and line.sale_order_line_id.state not in ('cancel', 'done'):
                so_to_update.add(line.sale_order_line_id.order_id.id)
                if line.sale_order_line_id.order_id.procurement_request:
                    sol_not_to_delete.append(line.sale_order_line_id.id)
                to_cancel.append(line.id)
                # Get the ID and the product qty of the FO line to re-source
                diff_qty = uom_obj._compute_qty(cr, uid, line.product_uom.id, line.qty, line.sale_order_line_id.product_uom.id)

                if line.has_to_be_resourced:
                    sol_to_resource.append(line.sale_order_line_id.id)

                sol_to_update.setdefault(line.sale_order_line_id.id, 0.00)
                sol_to_update[line.sale_order_line_id.id] += diff_qty
            elif line.tender_id.state == 'draft':
                to_remove.append(line.id)
            else:
                to_cancel.append(line.id)

        if to_cancel:
            self.write(cr, uid, to_cancel, {'line_state': 'cancel'}, context=context)

        # Update sale order lines
        so_to_cancel_ids = []
        for sol in sol_to_update:
            context['update_or_cancel_line_not_delete'] = sol in sol_not_to_delete
            so_to_cancel_id = sol_obj.update_or_cancel_line(cr, uid, sol, sol_to_update[sol], sol in sol_to_resource, context=context)
            if so_to_cancel_id:
                so_to_cancel_ids.append(so_to_cancel_id)

        if context.get('update_or_cancel_line_not_delete', False):
            del context['update_or_cancel_line_not_delete']

        # UF-733: if all tender lines have been compared (have PO Line id), then set the tender to be ready
        # for proceeding to other actions (create PO, Done etc)
        for tender in tender_obj.browse(cr, uid, list(tender_to_update), context=context):
            if tender.internal_state == 'draft':
                flag = True
                for line in tender.tender_line_ids:
                    if line.line_state != 'cancel' and not line.purchase_order_line_id:
                        flag = False
                if flag:
                    tender_obj.write(cr, uid, [tender.id], {'internal_state': 'updated'})

        if context.get('fake_unlink'):
            return to_remove

        return so_to_cancel_ids

    def fake_unlink(self, cr, uid, ids, context=None):
        '''
        Cancel the lines
        '''
        to_remove = self.cancel_sourcing(cr, uid, ids, context=dict(context, fake_unlink=True))
        for tl in self.browse(cr, uid, ids, context=context):
            self.infolog(cr, uid, "The tender line id:%s of tender id:%s (%s) has been canceled" % (
                tl.id,
                tl.tender_id.id,
                tl.tender_id.name,
            ))

        return self.write(cr, uid, to_remove, {'line_state': context.get('has_to_be_resourced') and 'cancel_r' or 'cancel'}, context=context)

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Ask user if he wants to re-source the needs
        '''
        # Objects
        wiz_obj = self.pool.get('tender.line.cancel.wizard')
        tender_obj = self.pool.get('tender')
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        # Variables
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        # Check if the line has been already deleted
        ids = self.search(cr, uid, [('id', 'in', ids), ('line_state', '!=', 'cancel')], context=context)
        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('The line has already been canceled - Please refresh the page'),
            )

        tender_id = False
        for line in self.browse(cr, uid, ids, context=context):
            tender_id = line.tender_id.id
            wiz_id = False
            last_line = False
            exp_sol_ids = None

            if line.tender_id.sale_order_id:
                exp_sol_ids = exp_sol_obj.search(cr, uid, [
                    ('tender_id', '=', tender_id),
                    ('tender_line_id', '!=', line.id),
                ], context=context)

                tender_so_ids, po_ids, so_ids, sol_nc_ids = tender_obj.sourcing_document_state(cr, uid, [tender_id], context=context)
                if line.sale_order_line_id and line.sale_order_line_id.id in sol_nc_ids:
                    sol_nc_ids.remove(line.sale_order_line_id.id)

                if po_ids and not exp_sol_ids and not sol_nc_ids:
                    last_line = True

            if line.sale_order_line_id:
                wiz_id = wiz_obj.create(cr, uid, {
                    'tender_line_id': line.id,
                    'last_line': last_line,
                }, context=context)
            elif not exp_sol_ids and line.tender_id.sale_order_id:
                wiz_id = wiz_obj.create(cr, uid, {
                    'tender_line_id': line.id,
                    'only_exp': True,
                    'last_line': last_line,
                }, context=context)
            else:
                wiz_id = wiz_obj.create(cr, uid, {'tender_line_id': line.id, 'only_exp': True}, context=context)

            if wiz_id:
                return {'type': 'ir.actions.act_window',
                        'res_model': 'tender.line.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': wiz_id,
                        'target': 'new',
                        'context': context}

        # if wiz_id:
        #     return wiz_obj.just_cancel(cr, uid, wiz_id, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'tender',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': tender_id,
                'target': 'crush',
                'context': context}

    def get_existing_po(self, cr, uid, ids, order_type, context=None):
        """
        SOURCING PROCESS: Do we have to create new PO or use an existing one ?
        If an existing one can be used, then returns his ID, otherwise returns False
        @return ID (int) of document to use or False
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res_id = False
        for tender_line in self.browse(cr, uid, ids, context=context):
            rfq_line = tender_line.purchase_order_line_id
            # common domain:
            domain = [
                ('partner_id', '=', rfq_line.partner_id.id),
                ('state', 'in', ['draft']),
                ('delivery_requested_date', '=', rfq_line.date_planned),
                ('rfq_ok', '=', False),
                ('order_type', '=', order_type),
            ]
            res_id = self.pool.get('purchase.order').search(cr, uid, domain, context=context)

        if res_id and isinstance(res_id, list):
            res_id = res_id[0]

        return res_id or False

    def create_po_from_tender_line(self, cr, uid, ids, order_type, context=None):
        '''
        SOURCING PROCESS: Create an new PO/DPO from tender line
        @return id of the newly created PO
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for tender_line in self.browse(cr, uid, ids, context=context):
            # commom fields:
            pricelist = tender_line.supplier_id.property_product_pricelist_purchase.id,
            if tender_line.purchase_order_line_id:
                price_ids = self.pool.get('product.pricelist').search(cr, uid, [('type', '=', 'purchase'), ('currency_id', '=', tender_line.purchase_order_line_id.currency_id.id)], context=context)
                if price_ids:
                    pricelist = price_ids[0]
            tender = tender_line.tender_id
            location_id = tender.location_id.id
            cross_docking_ok = True if tender_line.sale_order_line_id else False
            if tender.sale_order_id and tender.sale_order_id.procurement_request:
                location_id = self.pool.get('stock.location').search(cr, uid, [('input_ok', '=', True)], context=context)[0]
                cross_docking_ok = False if tender.sale_order_id.location_requestor_id.usage != 'customer' else True
            po_values = {
                'order_type': order_type,
                'origin': (tender.sale_order_id and tender.sale_order_id.name or "") + '; ' + tender.name,
                'partner_id': tender_line.supplier_id.id,
                'partner_address_id': self.pool.get('res.partner').address_get(cr, uid, [tender_line.supplier_id.id], ['default'])['default'],
                'customer_id': tender_line.sale_order_line_id and tender_line.sale_order_line_id.order_id.partner_id.id or False,
                'location_id': location_id,
                'company_id': tender.company_id.id,
                'cross_docking_ok': cross_docking_ok,
                'pricelist_id': pricelist,
                'fiscal_position': tender_line.supplier_id.property_account_position and tender_line.supplier_id.property_account_position.id or False,
                'warehouse_id': tender.warehouse_id.id,
                'categ': tender.categ,
                'priority': tender.priority,
                'origin_tender_id': tender.id,
                'details': tender.details,
                'delivery_requested_date': tender.requested_date,
                'dest_address_id': tender.delivery_address.id,
            }

        return self.pool.get('purchase.order').create(cr, uid, po_values, context=context)

tender_line()


class tender2(osv.osv):
    '''
    tender class
    '''
    _inherit = 'tender'
    _columns = {'tender_line_ids': fields.one2many('tender.line', 'tender_id', string="Tender lines", states={'draft': [('readonly', False)]}, readonly=True),
                }

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        reset the name to get new sequence number

        the copy method is here because upwards it goes in infinite loop
        '''
        if default is None:
            default = {}

        default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'tender'),
                       rfq_ids=[],
                       sale_order_line_id=False,)

        result = super(tender2, self).copy(cr, uid, id, default, context)

        return result

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset the tender line
        '''
        result = super(tender, self).copy_data(cr, uid, id, default=default, context=context)
        # reset the tender line
        for line in result['tender_line_ids']:
            line[2].update(sale_order_line_id=False,
                           purchase_order_line_id=False,
                           line_state='draft',)
        return result

tender2()


class purchase_order(osv.osv):
    '''
    add link to tender
    '''
    _inherit = 'purchase.order'

    def _check_valid_till(self, cr, uid, ids, context=None):
        """ Checks if valid till has been completed
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state == 'rfq_updated' and not obj.valid_till:
                return False
        return True

    _columns = {'tender_id': fields.many2one('tender', string="Tender", readonly=True, internal="purchase_order"),
                'rfq_delivery_address': fields.many2one('res.partner.address', string='Delivery address', internal="purchase_order"),
                'origin_tender_id': fields.many2one('tender', string='Tender', readonly=True, internal=True),
                'from_procurement': fields.boolean(string='RfQ created by a procurement order', internal=True),
                'rfq_ok': fields.boolean(string='Is RfQ ?', internal=True),
                'valid_till': fields.date(string='Valid Till', internal="purchase_order"),
                # add readonly when state is Done
                'sale_order_id': fields.many2one('sale.order', string='Link between RfQ and FO', readonly=True, internal="purchase_order"),
                }

    _defaults = {
        'rfq_ok': lambda self, cr, uid, c: c.get('rfq_ok', False),
        'rfq_state': 'draft',
    }

    _constraints = [
        (_check_valid_till,
            'You must specify a Valid Till date.',
            ['valid_till']), ]

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Set default data
        '''
        # Object declaration
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')

        res = super(purchase_order, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        # Get the delivery address
        company = user_obj.browse(cr, uid, uid, context=context).company_id
        res['rfq_delivery_address'] = partner_obj.address_get(cr, uid, company.partner_id.id, ['delivery'])['delivery']

        return res

    def create(self, cr, uid, vals, context=None):
        '''
        Set the reference at this step
        '''
        if context is None:
            context = {}
        if context.get('rfq_ok', False) and not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'rfq')})
        elif not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'purchase.order')})

        if context.get('rfq_ok', False) and not vals.get('location_id'):
            input_loc = self.pool.get('stock.location').search(cr, uid, [('input_ok', '=', True)], context=context)
            vals['location_id'] = input_loc and input_loc[0] or False

        return super(purchase_order, self).create(cr, uid, vals, context=context)

    def cancel_rfq(self, cr, uid, ids, context=None, resource=False, cancel_tender=False, resource_tender=False):
        '''
        method to cancel a RfQ and its lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        tend_l_obj = self.pool.get('tender.line')

        for rfq in self.browse(cr, uid, ids, context=context):
            if not rfq.rfq_ok:
                continue
            for rfq_line in rfq.order_line:
                if (rfq_line.order_id.partner_type in ('external', 'esc') and rfq_line.state in ('draft', 'validated', 'validated_n'))\
                        or (rfq_line.order_id.partner_type not in ('external', 'esc') and rfq_line.state == 'draft'):
                    signal = 'cancel'
                    if resource and rfq_line.linked_sol_id:
                        signal = 'cancel_r'
                    wf_service.trg_validate(uid, 'purchase.order.line', rfq_line.id, signal, cr)

            if cancel_tender and rfq.tender_id:
                if resource_tender:
                    tend_l_ids = tend_l_obj.search(cr, uid, [('tender_id', '=', rfq.tender_id.id)], context=context)
                    tend_l_obj.write(cr, uid, tend_l_ids, {'has_to_be_resourced': True}, context=context)
                    tend_l_obj.fake_unlink(cr, uid, tend_l_ids, context=context)
                wf_service.trg_validate(uid, 'tender', rfq.tender_id.id, 'tender_cancel', cr)

        return True

    def unlink(self, cr, uid, ids, context=None):
        '''
        Display an error message if the PO has associated IN
        '''
        in_ids = self.pool.get('stock.picking').search(cr, uid, [('purchase_id', 'in', ids)], context=context)
        if in_ids:
            raise osv.except_osv(_('Error !'), _('Cannot delete a document if its associated ' \
                                                 'document remains open. Please delete it (associated IN) first.'))

        # Copy a part of purchase_order standard unlink method to fix the bad state on error message
        purchase_orders = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in purchase_orders:
            if s['state'] in ['draft', 'cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Purchase Order(s) which are in %s State!') % _(dict(PURCHASE_ORDER_STATE_SELECTION).get(s['state'])))

        return super(purchase_order, self).unlink(cr, uid, ids, context=context)

    def _hook_copy_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        HOOK from purchase>purchase.py for COPY function. Modification of default copy values
        define which name value will be used
        '''
        # default values from copy function
        default = kwargs.get('default', False)
        # flag defining if the new object will be a rfq
        is_rfq = False
        # calling super function
        result = super(purchase_order, self)._hook_copy_name(cr, uid, ids, context=context, *args, **kwargs)
        if default.get('rfq_ok', False):
            is_rfq = True
        elif 'rfq_ok' not in default:
            for obj in self.browse(cr, uid, ids, context=context):
                # if rfq_ok is specified as default value for new object, we base our decision on this value
                if obj.rfq_ok:
                    is_rfq = True
        if is_rfq:
            result.update(name=self.pool.get('ir.sequence').get(cr, uid, 'rfq'))
        return result

    def hook_rfq_sent_check_lines(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the rfq_sent method from tender_flow>tender_flow.py
        - check lines after import
        '''
        pol_obj = self.pool.get('purchase.order.line')

        res = True
        empty_lines = pol_obj.search(cr, uid, [
            ('order_id', 'in', ids),
            ('product_qty', '<=', 0.00),
        ], context=context)
        if empty_lines:
            raise osv.except_osv(
                _('Error'),
                _('All lines of the RfQ should have a quantity before sending the RfQ to the supplier'),
            )
        return res

    def rfq_sent(self, cr, uid, ids, context=None):
        '''
        Method called when calling button Sent RfQ
        '''
        if not ids:
            return {}
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        pol_obj = self.pool.get('purchase.order.line')

        self.hook_rfq_sent_check_lines(cr, uid, ids, context=context)
        for rfq in self.browse(cr, uid, ids, fields_to_fetch=['name'], context=context):
            non_cancel_rfq_line_ids = pol_obj.search(cr, uid, [('order_id', '=', rfq.id), ('state', 'not in', ['cancel', 'cancel_r']),
                                                               ('rfq_line_state', 'not in', ['cancel', 'cancel_r'])], context=context)
            pol_obj.write(cr, uid, non_cancel_rfq_line_ids, {'rfq_line_state': 'sent'}, context=context)
            self.write(cr, uid, rfq.id, {'date_confirm': time.strftime('%Y-%m-%d')}, context=context)
            self.infolog(cr, uid, "The RfQ id:%s (%s) has been sent." % (rfq.id, rfq.name,))

        return True

    def action_updated(self, cr, uid, ids, context=None):
        '''
        method called when getting the updated state (case of RfQ)
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        pol_obj = self.pool.get('purchase.order.line')
        non_cancel_rfq_line_ids = pol_obj.search(cr, uid, [('order_id', 'in', ids), ('state', 'not in', ['cancel', 'cancel_r']),
                                                           ('rfq_line_state', 'not in', ['cancel', 'cancel_r'])], context=context)
        pol_obj.write(cr, uid, non_cancel_rfq_line_ids, {'rfq_line_state': 'updated'}, context=context)

        return True

    def check_rfq_updated(self, cr, uid, ids, context=None):
        tl_obj = self.pool.get('tender.line')
        line_obj = self.pool.get('purchase.order.line')

        if isinstance(ids, int):
            ids = [ids]

        for rfq in self.browse(cr, uid, ids, context=context):
            if not rfq.valid_till:
                raise osv.except_osv(_('Error'), _('You must specify a Valid Till date.'))

            if rfq.rfq_ok and rfq.tender_id:
                for line in rfq.order_line:
                    if not line.tender_line_id:
                        tl_ids = tl_obj.search(cr, uid, [('product_id', '=', line.product_id.id), ('tender_id', '=', rfq.tender_id.id), ('line_state', '=', 'draft')], context=context)
                        if tl_ids:
                            tl_id = tl_ids[0]
                        else:
                            tl_vals = {'product_id': line.product_id.id,
                                       'product_uom': line.product_uom.id,
                                       'qty': line.product_qty,
                                       'tender_id': rfq.tender_id.id,
                                       'created_by_rfq': True}
                            tl_id = tl_obj.create(cr, uid, tl_vals, context=context)
                            self.infolog(cr, uid, "The tender line id:%s has been created by the RfQ line id:%s (line number: %s)" % (
                                tl_id, line.id, line.line_number,
                            ))
                        line_obj.write(cr, uid, [line.id], {'tender_line_id': tl_id}, context=context)
            elif rfq.rfq_ok:
                line_ids = line_obj.search(cr, uid, [
                    ('order_id', '=', rfq.id),
                    ('price_unit', '=', 0.00),
                ], count=True, context=context)
                if line_ids:
                    raise osv.except_osv(
                        _('Error'),
                        _('''You cannot update an RfQ with lines without unit
price. Please set unit price on these lines or cancel them'''),
                    )

            self.action_updated(cr, uid, [rfq.id], context=context)
            self.infolog(cr, uid, "The RfQ id:%s (%s) has been updated" % (
                rfq.id, rfq.name,
            ))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form,tree,graph,calendar',
            'view_type': 'form',
            'target': 'crush',
            'context': {'rfq_ok': True},
            'domain': [('rfq_ok', '=', True)],
            'res_id': rfq.id,
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}

        ir_model_obj = self.pool.get('ir.model.data')
        # the search view depends on the type we want to display
        if view_type == 'search':
            if context.get('rfq_ok', False):
                # rfq search view
                view = ir_model_obj.get_object_reference(cr, uid, 'tender_flow', 'view_rfq_filter')
                if view:
                    view_id = view[1]
            if context.get('po_from_partners', False):
                context.pop('po_from_partners')
                view_id = ir_model_obj.get_object_reference(cr, uid, 'purchase', 'view_purchase_order_filter')[1]
        if view_type == 'tree':
            # the view depends on po type
            if context.get('rfq_ok', False):
                # rfq search view
                view = ir_model_obj.get_object_reference(cr, uid, 'tender_flow', 'view_rfq_tree')
                if view:
                    view_id = view[1]
        if view_type == 'form':
            if context.get('rfq_ok', False):
                view = ir_model_obj.get_object_reference(cr, uid, 'tender_flow', 'view_rfq_form')
                if view:
                    view_id = view[1]

        if context.get('po_from_transport'):
            if view_type == 'search':
                view_id = ir_model_obj.get_object_reference(cr, uid, 'purchase', 'view_purchase_order_filter')[1]

            if view_type == 'tree':
                view_id = ir_model_obj.get_object_reference(cr, uid, 'purchase', 'purchase_order_tree')[1]
                res = super(purchase_order, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
                root = etree.fromstring(res['arch'])
                for field in root.xpath('//tree'):
                    field.set('hide_new_button', '1')
                res['arch'] = etree.tostring(root, encoding='unicode')
                return res

        return super(purchase_order, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

    def rfq_closed(self, cr, uid, ids, context=None):
        '''
        close the Request for Quotation
        '''
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        for rfq in self.browse(cr, uid, ids, context=context):
            self.infolog(cr, uid, "The RfQ id:%s (%s) has been closed" % (rfq.id, rfq.name))

        pol_obj = self.pool.get('purchase.order.line')
        non_cancel_rfq_line_ids = pol_obj.search(cr, uid, [('order_id', 'in', ids), ('state', 'not in', ['cancel', 'cancel_r']),
                                                           ('rfq_line_state', 'not in', ['cancel', 'cancel_r'])], context=context)
        pol_obj.write(cr, uid, non_cancel_rfq_line_ids, {'rfq_line_state': 'done'}, context=context)

        return True


purchase_order()


class purchase_order_line(osv.osv):
    '''
    add a tender_id related field
    '''
    _inherit = 'purchase.order.line'

    _columns = {
        'tender_id': fields.related('order_id', 'tender_id', type='many2one', relation='tender', string='Tender', write_relate=False),
        'tender_line_id': fields.many2one('tender.line', string='Tender Line'),
        'rfq_ok': fields.related('order_id', 'rfq_ok', type='boolean', string='RfQ ?', write_relate=False),
        'sale_order_line_id': fields.many2one('sale.order.line', string='FO line', readonly=True),
        'rfq_line_state': fields.selection(string='State', selection=RFQ_LINE_STATE_SELECTION, readonly=True)
    }

    _defaults = {
        'rfq_line_state': lambda *args: 'draft',
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}

        # call super
        result = super(purchase_order_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            if context.get('rfq_ok', False):
                # the title of the screen depends on po type
                form = etree.fromstring(result['arch'])
                fields = form.xpath('//form[@string="%s"]' % _('Purchase Order Line'))
                for field in fields:
                    field.set('string', _("Request for Quotation Line"))
                result['arch'] = etree.tostring(form, encoding='unicode')

        return result


purchase_order_line()


class rfq_line_state(osv.osv):
    _name = "rfq.line.state"
    _description = "States of a RfQ line"

    _columns = {
        'name': fields.text(string='RfQ line state', store=True),
        'sequence': fields.integer(string='Sequence'),
    }

    def get_less_advanced_state(self, cr, uid, ids, states, context=None):
        '''
        Return the less advanced state of gives purchase order line states
        @param states: a list of string
        '''
        if not states:
            return False

        cr.execute("""SELECT name FROM rfq_line_state WHERE name IN %s ORDER BY sequence;""", (tuple(states),))

        min_state = cr.fetchone()

        return min_state[0] if min_state else False

    def get_sequence(self, cr, uid, ids, state, context=None):
        '''
        return the sequence of the given state
        @param state: the state's name as a string
        '''
        if not state:
            return False

        cr.execute("""SELECT sequence FROM rfq_line_state WHERE name = %s;""", (state,))
        sequence = cr.fetchone()

        return sequence[0] if sequence else False


rfq_line_state()


class sale_order_line(osv.osv):
    '''
    add link one2many to tender.line
    '''
    _inherit = 'sale.order.line'

    _columns = {
        'tender_line_ids': fields.one2many('tender.line', 'sale_order_line_id', string="Tender Lines", readonly=True),
        'created_by_tender': fields.many2one('tender', string='Created by tender'),
        'created_by_tender_line': fields.many2one('tender.line', string='Created by tender line'),
    }

    def copy_data(self, cr, uid, ids, default=None, context=None):
        '''
        Remove tender lines linked
        '''
        default = default or {}

        if not 'tender_line_ids' in default:
            default['tender_line_ids'] = []

        return super(sale_order_line, self).copy_data(cr, uid, ids, default, context=context)

sale_order_line()


class pricelist_partnerinfo(osv.osv):
    '''
    add new information from specifications
    '''
    def _get_line_number(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for price in self.browse(cr, uid, ids, context=context):
            res[price.id] = 0
            if price.purchase_order_line_id:
                res[price.id] = price.purchase_order_line_id.line_number

        return res

    _inherit = 'pricelist.partnerinfo'
    _columns = {'price': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price Computation'), help="This price will be considered as a price for the supplier UoM if any or the default Unit of Measure of the product otherwise"),
                'currency_id': fields.many2one('res.currency', string='Currency', required=True, domain="[('partner_currency', '=', partner_id)]", select=True),
                'valid_till': fields.date(string="Valid Till",),
                'comment': fields.char(size=128, string='Comment'),
                'purchase_order_id': fields.related('purchase_order_line_id', 'order_id', type='many2one', relation='purchase.order', string="Related RfQ", readonly=True,),
                'purchase_order_line_id': fields.many2one('purchase.order.line', string="RfQ Line Ref",),
                #'purchase_order_line_number': fields.related('purchase_order_line_id', 'line_number', type="integer", string="Related Line Number", ),
                'purchase_order_line_number': fields.function(_get_line_number, method=True, type="integer", string="Related Line Number", readonly=True),
                }
pricelist_partnerinfo()


class tender_line_cancel_wizard(osv.osv_memory):
    _name = 'tender.line.cancel.wizard'

    def _check_linked_rfq_lines(self, cr, uid, ids, name, args, context=None):
        """
        Check if the tender line is linked to some RfQ line(s)
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        pol_obj = self.pool.get('purchase.order.line')

        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, fields_to_fetch=['tender_line_id'], context=context):
            rfq_lines_ids = pol_obj.search(cr, uid, [('tender_line_id', '=', line.tender_line_id.id)], context=context)
            res[line.id] = rfq_lines_ids and True or False

        return res

    _columns = {
        'tender_line_id': fields.many2one('tender.line', string='Tender line', required=True),
        'only_exp': fields.boolean(string='Only added lines'),
        'last_line': fields.boolean(string='Last line of the FO to source'),
        'tender_line_has_rfq_lines': fields.function(_check_linked_rfq_lines, type='boolean', method=True, string='Linked to RfQ line(s)'),
    }

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Cancel the line 
        '''
        # Objects
        line_obj = self.pool.get('tender.line')
        tender_obj = self.pool.get('tender')
        so_obj = self.pool.get('sale.order')
        pol_obj = self.pool.get('purchase.order.line')
        wf_service = netsvc.LocalService("workflow")

        # Variables
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        line_ids = []
        tender_ids = set()
        so_ids = set()
        for wiz in self.browse(cr, uid, ids, context=context):
            tender_ids.add(wiz.tender_line_id.tender_id.id)
            line_ids.append(wiz.tender_line_id.id)
            if wiz.tender_line_id.tender_id.sale_order_id:
                so_ids.add(wiz.tender_line_id.tender_id.sale_order_id.id)
            # Check if some RfQ line(s) need to be cancelled
            if wiz.tender_line_has_rfq_lines:
                rfq_lines_ids = pol_obj.search(cr, uid, [('tender_line_id', '=', wiz.tender_line_id.id)], context=context)
                wf_service.trg_validate(uid, 'purchase.order.line', rfq_lines_ids, 'cancel', cr)

        if context.get('has_to_be_resourced'):
            line_obj.write(cr, uid, line_ids, {'has_to_be_resourced': True}, context=context)

        line_obj.fake_unlink(cr, uid, line_ids, context=context)

        tender_so_ids, po_ids, so_ids, sol_nc_ids = tender_obj.sourcing_document_state(cr, uid, list(tender_ids), context=context)
        for po_id in po_ids:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        so_to_cancel_ids = []
        if tender_so_ids:
            for so_id in tender_so_ids:
                if so_obj._get_ready_to_cancel(cr, uid, so_id, context=context)[so_id]:
                    so_to_cancel_ids.append(so_id)

        if so_to_cancel_ids:
            # Ask user to choose what must be done on the FO/IR
            context.update({
                'from_tender': True,
                'tender_ids': list(tender_ids),
            })
            return so_obj.open_cancel_wizard(cr, uid, set(so_to_cancel_ids), context=context)

        return tender_obj.check_empty_tender(cr, uid, list(tender_ids), context=context)

    def cancel_and_resource(self, cr, uid, ids, context=None):
        '''
        Flag the line to be re-sourced and run cancel method
        '''
        # Objects
        if context is None:
            context = {}

        context['has_to_be_resourced'] = True

        return self.just_cancel(cr, uid, ids, context=context)


tender_line_cancel_wizard()


class tender_cancel_wizard(osv.osv_memory):
    _name = 'tender.cancel.wizard'

    def _get_tender_source(self, cr, uid, ids, name, args, context=None):
        """
        Get the FO/IR which is linked to the tender
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        # Browse all given docs
        for wiz in self.browse(cr, uid, ids, fields_to_fetch=['tender_id'], context=context):
            res[wiz.id] = wiz.tender_id.sale_order_id and wiz.tender_id.sale_order_id.id or False

        return res

    _columns = {
        'tender_id': fields.many2one('tender', string='Tender', required=True),
        'not_draft': fields.boolean(string='Tender not draft'),
        'no_need': fields.boolean(string='No need'),
        'tender_source': fields.function(_get_tender_source, type='many2one', relation='sale.order', method=True, string='FO or IR linked to the Tender'),
    }

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Just cancel the wizard and the lines
        '''
        # Objects
        line_obj = self.pool.get('tender.line')
        so_obj = self.pool.get('sale.order')

        # Variables
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        line_ids = []
        tender_ids = []
        rfq_ids = []
        so_ids = []
        for wiz in self.browse(cr, uid, ids, context=context):
            tender_ids.append(wiz.tender_id.id)
            if wiz.tender_id.sale_order_id and wiz.tender_id.sale_order_id.id not in so_ids:
                so_ids.append(wiz.tender_id.sale_order_id.id)
            for line in wiz.tender_id.tender_line_ids:
                line_ids.append(line.id)
            for rfq in wiz.tender_id.rfq_ids:
                rfq_ids.append(rfq.id)

        if context.get('has_to_be_resourced'):
            line_obj.write(cr, uid, line_ids, {'has_to_be_resourced': True}, context=context)

        line_obj.fake_unlink(cr, uid, line_ids, context=context)

        self.pool.get('purchase.order').cancel_rfq(cr, uid, rfq_ids, context=context, resource=False)

        for tender in tender_ids:
            wf_service.trg_validate(uid, 'tender', tender, 'tender_cancel', cr)

        so_to_cancel_ids = []
        if so_ids:
            for so_id in so_ids:
                if so_obj._get_ready_to_cancel(cr, uid, so_id, context=context)[so_id]:
                    so_to_cancel_ids.append(so_id)

        if so_to_cancel_ids:
            # Ask user to choose what must be done on the FO/IR
            return so_obj.open_cancel_wizard(cr, uid, set(so_to_cancel_ids), context=context)

        return {'type': 'ir.actions.act_window_close'}

    def cancel_and_resource(self, cr, uid, ids, context=None):
        '''
        Flag the line to be re-sourced and run cancel method
        '''
        # Objects
        if context is None:
            context = {}

        context['has_to_be_resourced'] = True

        return self.just_cancel(cr, uid, ids, context=context)

    def close_window(self, cr, uid, ids, context=None):
        '''
        Just close the wizard and reload the tender
        '''
        return {'type': 'ir.actions.act_window_close'}


tender_cancel_wizard()


class tender_has_service_not_service_product_wizard(osv.osv_memory):
    _name = 'tender.has.service.not.service.product.wizard'

    _columns = {
        'tender_id': fields.many2one('tender', string='Tender'),
    }

    def continue_continue_sourcing(self, cr, uid, ids, context=None):
        '''
        Continue the PO creation from the Tender
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            self.pool.get('tender').continue_sourcing(cr, uid, [wiz.tender_id.id], context=context)

        return {'type': 'ir.actions.act_window_close'}

    def close_wizard(self, cr, uid, ids, context=None):
        '''
        Just close the wizard
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        return {'type': 'ir.actions.act_window_close'}


tender_has_service_not_service_product_wizard()


class expected_sale_order_line(osv.osv):
    _inherit = 'expected.sale.order.line'

    _columns = {
        'tender_line_id': fields.many2one(
            'tender.line',
            string='Tender line',
            ondelete='cascade',
        ),
        'tender_id': fields.related(
            'tender_line_id',
            'tender_id',
            string='Tender',
            type='many2one',
            relation='tender',
            write_relate=False,
        ),
    }

expected_sale_order_line()


SOURCE_DOCUMENT_MODELS = [
    ('', ''),
    ('po', 'Purchase Order'),
    ('rfq', 'Request for Quotation'),
    ('tender', 'Tender'),
    ('out', 'Outgoing Delivery'),
    ('pick', 'Picking Ticket'),
    ('int', 'Internal Move'),
]


class procurement_request_sourcing_document(osv.osv):
    _name = 'procurement.request.sourcing.document'
    _inherit = 'procurement.request.sourcing.document'
    _table = 'procurement_request_sourcing_document2'
    _description = 'Sourcing Document'
    _rec_name = 'order_id'
    _auto = False

    _columns = {
        'order_id': fields.many2one('sale.order', string='Internal request'),
        'linked_id': fields.integer('Document Id'),
        'linked_name': fields.char('Document name', size=255),
        'linked_model': fields.selection(SOURCE_DOCUMENT_MODELS, 'Document model'),
    }

    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'procurement_request_sourcing_document2')

        cr.execute('''CREATE OR REPLACE view procurement_request_sourcing_document2 AS (
            SELECT
                ('x'||md5(''||COALESCE(order_id,0)||COALESCE(linked_id,0)||COALESCE(linked_name,'')))::bit(32)::int AS id,
                order_id AS order_id,
                linked_id AS linked_id,
                linked_name AS linked_name,
                linked_model AS linked_model
            FROM (
                SELECT p.id AS linked_id, sl.order_id AS order_id, p.name AS linked_name, CASE WHEN p.rfq_ok = 't' THEN 'rfq' ELSE 'po' END AS linked_model
                FROM purchase_order_line pl, purchase_order p, sale_order_line sl, sale_order so
                WHERE so.id = sl.order_id AND pl.order_id = p.id AND pl.linked_sol_id = sl.id AND so.procurement_request = True
                GROUP BY p.id, sl.order_id

                UNION

                SELECT t.id AS linked_id, sl.order_id AS order_id, t.name AS linked_name, 'tender' AS linked_model
                FROM tender_line tl, tender t, sale_order_line sl, sale_order so
                WHERE so.id = sl.order_id AND tl.tender_id = t.id AND tl.sale_order_line_id = sl.id AND so.procurement_request = True
                GROUP BY t.id, sl.order_id, t.name

                UNION

                SELECT p.id AS linked_id, sl.order_id AS order_id, p.name AS linked_name,
                    CASE WHEN p.type = 'out' AND p.subtype = 'standard' THEN 'out' ELSE 'pick' END AS linked_model
                FROM stock_move m, stock_picking p, sale_order_line sl, sale_order so
                WHERE so.id = sl.order_id AND m.picking_id = p.id AND m.sale_line_id = sl.id AND so.procurement_request = True
                    AND p.type = 'out' AND p.subtype in ('standard', 'picking')
                GROUP BY p.id, sl.order_id, p.name

                UNION

                SELECT p.id AS linked_id, sl.order_id AS order_id, p.name AS linked_name, 'int' AS linked_model
                FROM stock_move m, stock_picking p, sale_order_line sl, purchase_order_line pl, sale_order so
                WHERE so.id = sl.order_id AND m.picking_id = p.id AND m.purchase_line_id = pl.id AND pl.linked_sol_id = sl.id
                    AND so.procurement_request = True AND p.type = 'internal' AND p.subtype != 'sysint'
                GROUP BY p.id, sl.order_id, p.name
                ) AS subq
            )''')

    def go_to_document(self, cr, uid, ids, context=None):
        """
        Open the sourcing document in the new tab
        """
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        source_doc = self.browse(cr, uid, ids[0], fields_to_fetch=['linked_id', 'linked_model'], context=context)

        view_id = False
        if source_doc.linked_model == 'po':
            source_model = 'purchase.order'
        elif source_doc.linked_model == 'rfq':
            context.update({'rfq_ok': True})
            source_model = 'purchase.order'
        elif source_doc.linked_model == 'tender':
            source_model = 'tender'
        elif source_doc.linked_model == 'out':
            context.update({'pick_type': 'delivery'})
            source_model = 'stock.picking'
            view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_picking_out_form')[1]
        elif source_doc.linked_model == 'pick':
            context.update({'pick_type': 'picking_ticket'})
            source_model = 'stock.picking'
            view_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'view_picking_ticket_form')[1]
        elif source_doc.linked_model == 'int':
            source_model = 'stock.picking'
            view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_picking_form')[1]
        else:
            raise osv.except_osv(_('Error'), _('No model found for this document'))

        res = {
            'type': 'ir.actions.act_window',
            'res_model': source_model,
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': source_doc.linked_id,
            'context': context,
        }

        if view_id:
            res['view_id'] = [view_id]

        return res


procurement_request_sourcing_document()

class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def _get_is_rfq_generated(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = False

        if context is None:
            context = {}

        if not context.get('tender_id'):
            return ret

        cr.execute('select partner_id from purchase_order where tender_id = %s', (context['tender_id'], ))
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    _columns = {
        'is_rfq_generated': fields.function(_get_is_rfq_generated, method=1, internal=1, type='boolean', string='RfQ Generated for the tender in context'),
    }
res_partner()
