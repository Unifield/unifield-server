#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2019 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _
import logging
import time


class account_invoice_sync(osv.osv):
    _inherit = 'account.invoice'
    _logger = logging.getLogger('------sync.account.invoice')

    _columns = {
        'synced': fields.boolean("Synchronized"),
        'from_supply': fields.boolean('From Supply', help="Internal field indicating whether the document is related to a Supply workflow"),
        'counterpart_inv_number': fields.char('Counterpart Invoice Number', size=64, readonly=True),
        'counterpart_inv_status': fields.char('Counterpart Invoice Status', size=16, readonly=True),
    }

    _defaults = {
        'synced': lambda *a: False,
        'from_supply': lambda *a: False,
    }

    def create_analytic_distrib(self, cr, uid, vals, distrib, context=None):
        """
        Updates vals with the new analytic_distribution_id created based on the distrib in parameter if it exists
        """
        if context is None:
            context = {}
        analytic_distrib_obj = self.pool.get('analytic.distribution')
        cc_distrib_line_obj = self.pool.get('cost.center.distribution.line')
        fp_distrib_line_obj = self.pool.get('funding.pool.distribution.line')
        data_obj = self.pool.get('ir.model.data')
        # get the Funding Pool "PF"
        try:
            fp_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        if distrib:  # original distrib from PO or PO line
            # create the Analytic Distribution
            distrib_id = analytic_distrib_obj.create(cr, uid, {}, context=context)
            for cc_line in distrib.cost_center_lines:
                distrib_vals = {
                    'analytic_id': cc_line.analytic_id and cc_line.analytic_id.id,  # analytic_id = Cost Center for the CC distrib line
                    'percentage': cc_line.percentage or 0.0,
                    'distribution_id': distrib_id,
                    'currency_id': cc_line.currency_id.id,
                    'destination_id': cc_line.destination_id.id,
                }
                cc_distrib_line_obj.create(cr, uid, distrib_vals, context=context)
                distrib_vals.update({
                    'analytic_id': fp_id,  # analytic_id = Funding Pool for the FP distrib line
                    'cost_center_id': cc_line.analytic_id and cc_line.analytic_id.id,
                })
                fp_distrib_line_obj.create(cr, uid, distrib_vals, context=context)
            vals.update({'analytic_distribution_id': distrib_id,})

    def create_invoice_from_sync(self, cr, uid, source, invoice_data, context=None):
        """
        Creates automatic counterpart invoice at synchro time.
        Intermission workflow: an IVO sent generates an IVI
        Intersection workflow: an STV sent generates an SI
        """
        self._logger.info("+++ Create an account.invoice in %s matching the one sent by %s" % (cr.dbname, source))
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        currency_obj = self.pool.get('res.currency')
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')
        inv_line_obj = self.pool.get('account.invoice.line')
        account_obj = self.pool.get('account.account')
        so_po_common_obj = self.pool.get('so.po.common')
        product_uom_obj = self.pool.get('product.uom')
        po_obj = self.pool.get('purchase.order')
        stock_picking_obj = self.pool.get('stock.picking')
        product_obj = self.pool.get('product.product')
        invoice_dict = invoice_data.to_dict()
        # the counterpart instance must exist and be active
        partner_ids = partner_obj.search(cr, uid, [('name', '=', source), ('active', '=', True)], limit=1, context=context)
        if not partner_ids:
            raise osv.except_osv(_('Error'), _("The partner %s doesn't exist or is inactive.") % source)
        partner_id = partner_ids[0]
        partner = partner_obj.browse(cr, uid, partner_ids[0], fields_to_fetch=['property_account_payable'], context=context)
        journal_type = invoice_dict.get('journal_id', {}).get('type', '')
        if not journal_type or journal_type not in ('sale', 'intermission'):
            raise osv.except_osv(_('Error'), _("Impossible to retrieve the journal type, or the journal type found is incorrect."))
        currency_name = invoice_dict.get('currency_id', {}).get('name', '')
        if not currency_name:
            raise osv.except_osv(_('Error'), _("Impossible to retrieve the currency."))
        currency_ids = currency_obj.search(cr, uid, [('name', '=', currency_name), ('currency_table_id', '=', False),
                                                     ('active', '=', True)], limit=1, context=context)
        if not currency_ids:
            raise osv.except_osv(_('Error'), _("Currency %s not found or inactive.") % currency_name)
        currency_id = currency_ids[0]
        number = invoice_dict.get('number', '')
        state = invoice_dict.get('state', '')  # note that we get the real state as the doc can be beyond the "open" state at sync. time
        doc_date = invoice_dict.get('document_date', time.strftime('%Y-%m-%d'))
        posting_date = invoice_dict.get('date_invoice', time.strftime('%Y-%m-%d'))
        description = invoice_dict.get('name', '')
        source_doc = invoice_dict.get('origin', '')
        from_supply = invoice_dict.get('from_supply', False)
        inv_lines = invoice_dict.get('invoice_line', [])
        po = False
        vals = {}
        # STV in sending instance: generates an SI in the receiving instance
        if journal_type == 'sale':
            pur_journal_ids = journal_obj.search(cr, uid, [('type', '=', 'purchase'), ('is_current_instance', '=', True)], limit=1, context=context)
            if not pur_journal_ids:
                raise osv.except_osv(_('Error'), _("No Purchase Journal found for the current instance."))
            # for the SI use the Account Payable of the partner
            si_account = partner.property_account_payable
            if not si_account or posting_date < si_account.activation_date or \
                    (si_account.inactivation_date and posting_date >= si_account.inactivation_date):
                raise osv.except_osv(_('Error'), _("Account Payable not found or inactive for the partner %s.") % partner.name)
            vals.update(
                {
                    'journal_id': pur_journal_ids[0],
                    'account_id': si_account.id,
                    'type': 'in_invoice',
                    'is_direct_invoice': False,
                    'is_inkind_donation': False,
                    'is_debit_note': False,
                    'is_intermission': False,
                }
            )
        # IVO in sending instance: generates an IVI in the receiving instance
        elif journal_type == 'intermission':
            int_journal_ids = journal_obj.search(cr, uid, [('type', '=', 'intermission'), ('is_current_instance', '=', True)], limit=1, context=context)
            if not int_journal_ids:
                raise osv.except_osv(_('Error'), _("No Intermission Journal found for the current instance."))
            # for the IVI use the Intermission counterpart account from the Company form
            ivi_account = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.intermission_default_counterpart
            if not ivi_account or posting_date < ivi_account.activation_date or \
                    (ivi_account.inactivation_date and posting_date >= ivi_account.inactivation_date):
                raise osv.except_osv(_('Error'), _("The Intermission counterpart account is missing in the Company form or is inactive."))
            vals.update(
                {
                    'journal_id': int_journal_ids[0],
                    'account_id': ivi_account.id,
                    'type': 'in_invoice',
                    'is_inkind_donation': False,
                    'is_debit_note': False,
                    'is_intermission': True,
                }
            )
        # common fields whatever the invoice type
        if from_supply:
            po_id = False
            po_number = ''
            fo_number = ''
            ship_or_out_ref = ''
            main_in = False
            # extract PO number, and Shipment or Simple Out ref, from refs looking like:
            # "se_HQ2C1.19/se_HQ2/HT101/PO00001 : SHIP/00002-01" or "se_HQ1C2.19/se_HQ1/HT201/PO00003 : OUT/00001"
            inv_name_split = description.split()
            if inv_name_split:
                po_number = inv_name_split[0].split('.')[-1]
                po_ids = po_obj.search(cr, uid, [('name', '=', po_number)], limit=1, context=context)
                if po_ids:
                    po_id = po_ids[0]
                ship_or_out_ref = inv_name_split[-1]
            # extract FO number from source docs looking like:
            # "SHIP/00001-04:19/se_HQ1/HT101/FO00007" or "OUT/00003:19/se_HQ1/HT101/FO00008"
            inv_source_doc_split = source_doc.split(':')
            if inv_source_doc_split:
                fo_number = inv_source_doc_split[-1]
            if po_id:
                po = po_obj.browse(cr, uid, po_id, fields_to_fetch=['picking_ids', 'analytic_distribution_id', 'order_line'], context=context)
                shipment_ref = "%s.%s" % (source or '', ship_or_out_ref or '')
                # get the "main" IN
                main_in_ids = stock_picking_obj.search(cr, uid,
                                                       [('id', 'in', [picking.id for picking in po.picking_ids]),
                                                        ('shipment_ref', '=', shipment_ref)],
                                                       limit=1, context=context)
                if main_in_ids:
                    main_in = stock_picking_obj.browse(cr, uid, main_in_ids[0], fields_to_fetch=['name'], context=context)
                # fill in the Analytic Distribution
                # at header level if applicable
                po_distrib = po.analytic_distribution_id
                self.create_analytic_distrib(cr, uid, vals, po_distrib, context=context)  # update vals
            # note: in case a FO would have been manually created the PO and IN would be missing in the ref/source doc,
            # but the same codification is used so it's visible that sthg is missing
            description = "%s.%s : %s" % (source, fo_number, main_in and main_in.name or '')  # e.g. se_HQ1C1.19/se_HQ1/HT101/FO00008 : IN/00009
            source_doc = "%s:%s" % (main_in and main_in.name or '', po_id and po_number or '')  # e.g. IN/00009:19/se_HQ1/HT201/PO00009
        vals.update(
            {
                'partner_id': partner_id,
                'currency_id': currency_id,
                'document_date': doc_date,
                'date_invoice': posting_date,
                'name': description,
                'origin': source_doc,
                'counterpart_inv_number': number,
                'counterpart_inv_status': state and dict(self._columns['state'].selection).get(state) or '',  # use the state value and not its key
                'from_supply': True,
                'synced': True,
            }
        )
        inv_id = self.create(cr, uid, vals, context=context)
        if inv_id:
            # creation of the lines
            for inv_line in inv_lines:
                line_name = inv_line.get('name', '')
                if not line_name:  # required field
                    raise osv.except_osv(_('Error'), _("Impossible to retrieve the line description."))
                product_id = False
                product_data = inv_line.get('product_id', {})
                line_account_id = False
                # for the lines related to a product: use the account of the product / else use the one of the source invoice line
                if product_data:
                    default_code = product_data.get('default_code', '')
                    product_id = so_po_common_obj.get_product_id(cr, uid, product_data, default_code=default_code, context=context) or False
                    if not product_id:
                        raise osv.except_osv(_('Error'), _("Product %s not found.") % default_code)
                    product = product_obj.browse(cr, uid, product_id, fields_to_fetch=['product_tmpl_id', 'categ_id'], context=context)
                    line_account_id = product.product_tmpl_id.property_account_expense and product.product_tmpl_id.property_account_expense.id
                    if not line_account_id:
                        line_account_id = product.categ_id and product.categ_id.property_account_expense_categ and product.categ_id.property_account_expense_categ.id
                else:
                    account_code = inv_line.get('account_id', {}).get('code', '')
                    if not account_code:
                        raise osv.except_osv(_('Error'), _("Impossible to retrieve the account code at line level."))
                    account_ids = account_obj.search(cr, uid, [('code', '=', account_code)], limit=1, context=context)
                    if not account_ids:
                        raise osv.except_osv(_('Error'), _("Account code %s not found.") % account_code)
                    line_account_id = account_ids[0]
                if not line_account_id:
                    raise osv.except_osv(_('Error'), _("Error when retrieving the account at line level."))
                line_account = account_obj.browse(cr, uid, line_account_id,
                                                  fields_to_fetch=['activation_date', 'inactivation_date'], context=context)
                if posting_date < line_account.activation_date or \
                        (line_account.inactivation_date and posting_date >= line_account.inactivation_date):
                    raise osv.except_osv(_('Error'), _('The account "%s - %s" is inactive.') % (line_account.code, line_account.name))
                uom_id = False
                uom_data = inv_line.get('uos_id', {})
                if uom_data:
                    uom_name = uom_data.get('name', '')
                    uom_ids = product_uom_obj.search(cr, uid, [('name', '=', uom_name)], limit=1, context=context)
                    if not uom_ids:
                        raise osv.except_osv(_('Error'), _("Unit of Measure %s not found.") % uom_name)
                    uom_id = uom_ids[0]
                quantity = inv_line.get('quantity', 0.0)
                inv_line_vals = {
                    'invoice_id': inv_id,
                    'account_id': line_account_id,
                    'name': line_name,
                    'quantity': quantity,
                    'price_unit': inv_line.get('price_unit', 0.0),
                    'discount': inv_line.get('discount', 0.0),
                    'product_id': product_id,
                    'uos_id': uom_id,
                }
                if from_supply and po:
                    # fill in the AD at line level if applicable
                    # search the matching between PO line and invoice line based on description/product/quantity
                    matching_po_line = False
                    for po_line in po.order_line:
                        if po_line.name == line_name and po_line.product_id and po_line.product_id.id == product_id and \
                                po_line.product_qty == quantity and po_line.state not in ('draft', 'cancel', 'cancel_r'):
                            matching_po_line = po_line
                            break
                    if matching_po_line:
                        po_line_distrib = matching_po_line.analytic_distribution_id
                        self.create_analytic_distrib(cr, uid, inv_line_vals, po_line_distrib, context=context)  # update inv_line_vals
                inv_line_obj.create(cr, uid, inv_line_vals, context=context)
            if journal_type == 'sale':
                self._logger.info("SI No. %s created successfully." % inv_id)
            elif journal_type == 'intermission':
                self._logger.info("IVI No. %s created successfully." % inv_id)

    def update_counterpart_inv(self, cr, uid, source, invoice_data, state, context=None):
        """
        Updates the Counterpart Invoice Number and Status (to be triggered at synchro time)

        For the record:
        In most cases the state "Open" of the Out Invoices will be updated following both msg rules "create_invoice_from_sync" and
        "update_counterpart_inv_opened". However "update_counterpart_inv_opened" can't be skipped to cover use cases such as:
        - in C1: open IVO and reconcile the related JI manually: IVO is in Paid state
        - sync from C1 to C2: the counterpart inv. status in the IVI generated is directly: Paid
        - in C2: open IVI
        - sync from C2 to C1: the counterpart number (and status) is updated in C1
        - in C1: unreconcile IVO JI. The IVO is back to Open.
        - sync from C1 to C2: the counterpart inv. status in the related IVI is updated to: Open
        """
        self._logger.info("+++ Update Counterpart Invoice data from %s" % source)
        if context is None:
            context = {}
        invoice_dict = invoice_data.to_dict()
        number = invoice_dict.get('number', '')
        counterpart_inv_number = invoice_dict.get('counterpart_inv_number', '')
        state = state and dict(self._columns['state'].selection).get(state) or ''  # use the state value and not its key
        if number and counterpart_inv_number and state:
            inv_ids = self.search(cr, uid, [('number', '=', counterpart_inv_number)], limit=1, context=context)
            if inv_ids:
                vals = {
                    'counterpart_inv_number': number,
                    'counterpart_inv_status': state,
                }
                self.write(cr, uid, inv_ids[0], vals, context=context)
                # note that the "Counterpart Inv. Number" received is the "Number" of the invoice updated!
                self._logger.info("account.invoice %s: Counterpart Invoice %s set to %s" % (counterpart_inv_number, number, state))

    def update_counterpart_inv_opened(self, cr, uid, source, invoice_data, context=None):
        self.update_counterpart_inv(cr, uid, source, invoice_data, 'open', context=context)

    def update_counterpart_inv_paid(self, cr, uid, source, invoice_data, context=None):
        self.update_counterpart_inv(cr, uid, source, invoice_data, 'paid', context=context)

    def update_counterpart_inv_cancelled(self, cr, uid, source, invoice_data, context=None):
        self.update_counterpart_inv(cr, uid, source, invoice_data, 'cancel', context=context)


account_invoice_sync()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
