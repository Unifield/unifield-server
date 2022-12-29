# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from tools.translate import _


class merged_ud_products(XlsxReportParser):

    def generate(self, context=None):
        if context is None:
            context = {}

        is_mission = self.pool.get('res.company')._get_instance_level(self.cr, self.uid) != 'section'

        data_obj = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        sheet = self.workbook.active

        self.create_style_from_template('title_style', 'A1')
        self.create_style_from_template('filter_style', 'A2')
        self.create_style_from_template('filter_txt', 'C2')
        self.create_style_from_template('filter_date', 'C3')

        self.create_style_from_template('kept_title', 'A5')
        self.create_style_from_template('non_kept_title', 'H5')
        self.create_style_from_template('merged_date_title', 'O5')

        self.create_style_from_template('header_row', 'A6')
        self.create_style_from_template('row', 'A7')
        self.create_style_from_template('row_date', 'O7')
        self.create_style_from_template('row_qty', 'P7')
        self.create_style_from_template('header_stock', 'P6')

        self.duplicate_column_dimensions(default_width=10.75)
        sheet.freeze_panes = 'A7'

        sheet.title = _('Merged UD Products')

        sheet.merged_cells.ranges.append("A1:F1")
        if is_mission:
            sheet.append([self.cell_ro(_('Merged UniData products'), 'title_style')])
        else:
            sheet.append([self.cell_ro(_('HQ Merged UniData products'), 'title_style')])

        sheet.merged_cells.ranges.append("A2:B3")
        sheet.append([
            self.cell_ro(_('Filters'), 'filter_style'),
            '',
            self.cell_ro(_('Merge date from:'), 'filter_txt'),
            self.cell_ro(_('Merge Date to:'), 'filter_txt'),
            self.cell_ro(_('Product code:'), 'filter_txt'),
            self.cell_ro(_('Product Main Type:'), 'filter_txt'),
        ])
        filters = ['', '']

        wiz = self.pool.get('merged_ud_products').browse(self.cr, self.uid, self.ids[0], context=context)
        if wiz.start_date:
            filters.append(self.cell_ro(datetime.strptime(wiz.start_date, '%Y-%m-%d'), 'filter_date'))
        else:
            filters.append(self.cell_ro('-', 'filter_txt'))
        if wiz.end_date:
            filters.append(self.cell_ro(datetime.strptime(wiz.end_date, '%Y-%m-%d'), 'filter_date'))
        else:
            filters.append(self.cell_ro('-', 'filter_txt'))

        filters.append(self.cell_ro(wiz.product_code or '-', 'filter_txt'))
        filters.append(self.cell_ro(wiz.main_type_id.name or '-', 'filter_txt'))

        sheet.append(filters)

        sheet.append([])
        sheet.merged_cells.ranges.append("A5:G5")
        sheet.merged_cells.ranges.append("H5:N5")
        sheet.append([
            self.cell_ro(_('Kept product:'), 'kept_title'),
            self.cell_ro('', 'kept_title'),
            self.cell_ro('', 'kept_title'),
            self.cell_ro('', 'kept_title'),
            self.cell_ro('', 'kept_title'),
            self.cell_ro('', 'kept_title'),
            self.cell_ro('', 'kept_title'),
            self.cell_ro(_('Non-Kept Merged product:'), 'non_kept_title'),
            self.cell_ro('', 'non_kept_title'),
            self.cell_ro('', 'non_kept_title'),
            self.cell_ro('', 'non_kept_title'),
            self.cell_ro('', 'non_kept_title'),
            self.cell_ro('', 'non_kept_title'),
            self.cell_ro('', 'non_kept_title'),
            self.cell_ro('', 'merged_date_title'),
        ])

        label = [
            self.cell_ro(x, 'header_row') for x in
                [
                    _('Code'), _('Description'), _('Product Creator'),
                    _('Standardization Level'), _('UniData Status'),
                    _('UniField Status'), _('Active Status'), _('Code'),
                    _('Description'), _('Product Creator'),
                    _('Standardization Level'), _('UniData Status'),
                    _('UniField Status'), _('Active Status'), _('Date of Merge')
            ]
        ]

        if is_mission:
            stock_id = data_obj.get_object_reference(self.cr, self.uid, 'stock', 'stock_location_stock')[1]
            log_id = data_obj.get_object_reference(self.cr, self.uid, 'stock_override', 'stock_location_logistic')[1]
            med_id = data_obj.get_object_reference(self.cr, self.uid, 'msf_config_locations', 'stock_location_medical')[1]
            cross_id = data_obj.get_object_reference(self.cr, self.uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
            input_id = data_obj.get_object_reference(self.cr, self.uid, 'msf_cross_docking', 'stock_location_input')[1]
            quarantine_ids = [
                data_obj.get_object_reference(self.cr, self.uid, 'stock_override', 'stock_location_quarantine_analyze')[1],
                data_obj.get_object_reference(self.cr, self.uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
            ]
            packing_id = data_obj.get_object_reference(self.cr, self.uid, 'msf_outgoing', 'stock_location_packing')[1]
            shipmend_id = data_obj.get_object_reference(self.cr, self.uid, 'msf_outgoing', 'stock_location_dispatch')[1]
            distribution_id = data_obj.get_object_reference(self.cr, self.uid, 'msf_outgoing', 'stock_location_distribution')[1]

            eprep_view_id = data_obj.get_object_reference(self.cr, self.uid, 'msf_config_locations', 'stock_location_eprep_view')[1]
            eprep_ids = loc_obj.search(self.cr, self.uid, [('location_id', '=', eprep_view_id)], context=context)

            itermediate_view =  data_obj.get_object_reference(self.cr, self.uid, 'msf_config_locations', 'stock_location_intermediate_client_view')[1]
            intermediate_ids = loc_obj.search(self.cr, self.uid, [('location_id', '=', itermediate_view)], context=context)

            icu_view = data_obj.get_object_reference(self.cr, self.uid, 'msf_config_locations', 'stock_location_consumption_units_view')[1]
            icu_ids = loc_obj.search(self.cr, self.uid, [('location_id', '=', icu_view)], context=context)


            all_internal_ids = loc_obj.search(self.cr, self.uid, [('usage', '=', 'internal')], context=context)
            stock_name = {}
            for st in loc_obj.read(self.cr, self.uid, all_internal_ids, ['name'], context=context):
                stock_name[st['id']] = st['name']

            label += [
                self.cell_ro(_('Instance stock'), 'header_stock'),
                self.cell_ro(_('Instance stock val.'), 'header_stock'),
                self.cell_ro(_('Stock qty'), 'header_stock'),
                self.cell_ro(_('Cross Docking'), 'header_stock'),
                self.cell_ro(_('Input'), 'header_stock'),
                self.cell_ro(_('LOG'), 'header_stock'),
                self.cell_ro(_('MED'), 'header_stock'),
            ]
            for x in intermediate_ids:
                label.append(self.cell_ro(stock_name[x], 'header_stock'))

            for x in icu_ids:
                label.append(self.cell_ro(stock_name[x], 'header_stock'))

            for x in eprep_ids:
                label.append(self.cell_ro(stock_name[x], 'header_stock'))

            label += [
                self.cell_ro(_('Quarantine / For Scrap Qty'), 'header_stock'),
                self.cell_ro(_('Packing'), 'header_stock'),
                self.cell_ro(_('Shipment'), 'header_stock'),
                self.cell_ro(_('Distribution'), 'header_stock'),
                self.cell_ro(_('In Pipe Qty'), 'header_stock'),
                self.cell_ro(_('Open Transactions'), 'header_stock'),

            ]

        sheet.append(label)

        limit = 100
        offset = 0
        while True:
            non_ids = self.pool.get('merged_ud_products')._get_non_kept_ids(self.cr, self.uid, self.ids[0], limit=limit, offset=offset, context=context)
            if not non_ids:
                break
            offset += limit

            if is_mission:
                self.cr.execute('''
                select
                    m.product_id, m.location_id, m.quantity
                from
                    stock_mission_report_line_location m, product_product p
                where
                    m.product_id = p.kept_initial_product_id and
                    p.id in %s and
                    m.location_id in %s
                ''', (tuple(non_ids), tuple(all_internal_ids)))
                prod_qty_by_loc ={}

                for x in self.cr.fetchall():
                    prod_qty_by_loc.setdefault(x[0], {}).update({x[1]: x[2]})
                    prod_qty_by_loc[x[0]]['all'] = prod_qty_by_loc[x[0]].setdefault('all', 0) + x[2]
                    if x[1] in quarantine_ids:
                        prod_qty_by_loc[x[0]]['quar'] = prod_qty_by_loc[x[0]].setdefault('quar', 0) + x[2]
                    if x[1] in [stock_id, med_id, log_id]:
                        prod_qty_by_loc[x[0]]['stock'] = prod_qty_by_loc[x[0]].setdefault('stock', 0) + x[2]
                    # TODO :stock < 0 ??

                in_pipe = {}
                self.cr.execute('''
                  SELECT x.product_id, sum(x.product_qty), x.uom_id, x.stock_uom
                  FROM (
                    SELECT pol.product_id as product_id, sum(pol.product_qty) as product_qty, pol.product_uom as uom_id, tmpl.uom_id as stock_uom
                        FROM purchase_order_line pol, purchase_order po, product_product old, product_product kept, product_template tmpl
                    WHERE
                        pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and
                        po.id = pol.order_id and
                        pol.product_id is not null and
                        old.kept_initial_product_id = pol.product_id and
                        kept.id = pol.product_id and
                        tmpl.id = kept.product_tmpl_id and
                        old.id in %s
                    GROUP BY pol.product_id, pol.product_uom, tmpl.uom_id
                    UNION
                    SELECT m.product_id as product_id, sum(m.product_qty) as product_qty, m.product_uom as uom_id, tmpl.uom_id as stock_uom
                        FROM stock_move m
                        LEFT JOIN stock_picking s ON m.picking_id = s.id
                        LEFT JOIN product_product old ON old.kept_initial_product_id = m.product_id
                        LEFT JOIN product_product kept ON kept.id = m.product_id
                        LEFT JOIN product_template tmpl ON tmpl.id = kept.product_tmpl_id
                      WHERE
                        s.type = 'in' AND m.state in ('confirmed', 'waiting', 'assigned') and
                        old.id in %s
                      GROUP BY m.product_id, m.product_uom, tmpl.uom_id
                    ) x
                    GROUP BY x.product_id, x.product_qty, x.uom_id, x.stock_uom
                ''', (tuple(non_ids), tuple(non_ids,)))
                for x in self.cr.fetchall():
                    qty = x[1]
                    if qty and x[2] != x[3]:
                        qty = self.pool.get('product.uom')._compute_qty(self.cr, self.uid, x[2], qty, x[3])
                    in_pipe[x[0]] = in_pipe.setdefault(x[0], 0) + qty


                in_use = set()
                inital_non_ids = set(non_ids)

                # stock move
                self.cr.execute('''
                    select
                        m.product_id
                    from
                        stock_move m, product_product old
                    where
                        old.kept_initial_product_id = m.product_id and
                        old.id in %s and
                        m.state not in ('done', 'cancel')
                    group by m.product_id
                ''', (tuple(inital_non_ids), ))
                in_use.update(set([x[0] for x in self.cr.fetchall()]))
                inital_non_ids -= in_use
                if inital_non_ids:
                    # PO / RfQ
                    self.cr.execute('''
                        select
                            l.product_id
                        from
                            purchase_order po, purchase_order_line l, product_product old
                        where
                            l.order_id = po.id and
                            l.state not in ('done', 'cancel', 'cancel_r') and
                            po.active = 't' and
                            old.kept_initial_product_id = l.product_id and
                            old.id in %s
                        group by l.product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use
                if inital_non_ids:
                    # FO / IR
                    self.cr.execute('''
                        select
                            l.product_id
                        from
                            sale_order so, sale_order_line l, product_product old
                        where
                            l.order_id = so.id and
                            l.state not in ('done', 'cancel', 'cancel_r') and
                            so.active = 't' and
                            old.kept_initial_product_id = l.product_id and
                            old.id in %s
                        group by l.product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # Tender
                    self.cr.execute('''
                        select
                            l.product_id
                        from
                            tender t, tender_line l, product_product old
                        where
                            l.tender_id = t.id and
                            t.state not in ('done', 'cancel') and
                            old.kept_initial_product_id = l.product_id and
                            old.id in %s
                        group by l.product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # Main KIT
                    self.cr.execute('''
                        select
                            k.composition_product_id
                        from
                            composition_kit k, product_product old
                        where
                            k.state not in ('done', 'cancel') and
                            k.active = 't' and
                            old.kept_initial_product_id = k.composition_product_id and
                            old.id in %s
                        group by k.composition_product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # Listed in KIT
                    self.cr.execute('''
                        select
                            item.item_product_id
                        from
                            composition_kit k, composition_item item, product_product old
                        where
                            k.state not in ('done', 'cancel') and
                            k.active = 't' and
                            item.item_kit_id = k.id and
                            old.kept_initial_product_id = item.item_product_id and
                            old.id in %s
                        group by item.item_product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # ISI
                    self.cr.execute('''
                        select
                            l.product_id
                        from
                            initial_stock_inventory isi, initial_stock_inventory_line l, product_product old
                        where
                            isi.state not in ('done', 'cancel') and
                            l.inventory_id = isi.id and
                            old.kept_initial_product_id = l.product_id and
                            old.id in %s
                        group by l.product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # PI tab 1
                    self.cr.execute('''
                        select
                            rel.inventory_id
                        from
                            physical_inventory pi,  physical_inventory_product_rel rel, product_product old
                        where
                            pi.state not in ('closed', 'cancel') and
                            rel.product_id = pi.id and
                            old.kept_initial_product_id = rel.inventory_id and
                            old.id in %s
                        group by rel.inventory_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # PI tab 2
                    self.cr.execute('''
                        select
                            cs.product_id
                        from
                            physical_inventory pi,  physical_inventory_counting cs, product_product old
                        where
                            pi.state not in ('closed', 'cancel') and
                            cs.inventory_id = pi.id and
                            old.kept_initial_product_id = cs.product_id and
                            old.id in %s
                        group by cs.product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # PI tab 3
                    self.cr.execute('''
                        select
                            dl.product_id
                        from
                            physical_inventory pi,  physical_inventory_discrepancy dl, product_product old
                        where
                            pi.state not in ('closed', 'cancel') and
                            dl.inventory_id = pi.id and
                            old.kept_initial_product_id = dl.product_id and
                            old.id in %s
                        group by dl.product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

                if inital_non_ids:
                    # Invoices
                    self.cr.execute('''
                        select
                            l.product_id
                        from
                            account_invoice i, account_invoice_line l, account_account a, product_product old
                        where
                            (i.state = 'draft' or i.state = 'open' and a.reconcile = 't') and
                            l.invoice_id = i.id and
                            a.id = i.account_id and
                            old.kept_initial_product_id = l.product_id and
                            old.id in %s
                        group by l.product_id
                    ''', (tuple(inital_non_ids), ))
                    in_use.update(set([x[0] for x in self.cr.fetchall()]))
                    inital_non_ids -= in_use

            for non_kept in self.pool.get('product.product').browse(self.cr, self.uid, non_ids, context=context):
                line = [
                    self.cell_ro(non_kept.kept_initial_product_id.default_code, 'row'),
                    self.cell_ro(non_kept.kept_initial_product_id.name, 'row'),
                    self.cell_ro(non_kept.kept_initial_product_id.international_status.name, 'row'),
                    self.cell_ro(self.getSel(non_kept.kept_initial_product_id, 'standard_ok'), 'row'),
                    self.cell_ro(self.getSel(non_kept.kept_initial_product_id, 'state_ud') or '', 'row'),
                    self.cell_ro(non_kept.kept_initial_product_id.state.name or '', 'row'),
                    self.cell_ro(non_kept.kept_initial_product_id.active, 'row'),
                    self.cell_ro(non_kept.default_code, 'row'),
                    self.cell_ro(non_kept.name, 'row'),
                    self.cell_ro(non_kept.international_status.name, 'row'),
                    self.cell_ro(self.getSel(non_kept, 'standard_ok'), 'row'),
                    self.cell_ro(self.getSel(non_kept, 'state_ud') or '', 'row'),
                    self.cell_ro(non_kept.state.name or '', 'row'),
                    self.cell_ro(non_kept.active, 'row'),
                    self.cell_ro(non_kept.unidata_merge_date and datetime.strptime(non_kept.unidata_merge_date, '%Y-%m-%d %H:%M:%S') or '', 'row_date'),
                ]

                if is_mission:
                    stock = prod_qty_by_loc.get(non_kept.kept_initial_product_id.id, {})
                    line += [
                        self.cell_ro(stock.get('all', ''), 'row_qty'),
                        self.cell_ro(stock.get('all', 0) * non_kept.kept_initial_product_id.standard_price or '', 'row_qty'),
                        self.cell_ro(stock.get('stock', ''), 'row_qty'),
                        self.cell_ro(stock.get(cross_id, ''), 'row_qty'),
                        self.cell_ro(stock.get(input_id, ''), 'row_qty'),
                        self.cell_ro(stock.get(log_id, ''), 'row_qty'),
                        self.cell_ro(stock.get(med_id, ''), 'row_qty')
                    ]
                    for x in intermediate_ids:
                        line.append(self.cell_ro(stock.get(x, ''), 'row_qty'))
                    for x in icu_ids:
                        line.append(self.cell_ro(stock.get(x, ''), 'row_qty'))
                    for x in eprep_ids:
                        line.append(self.cell_ro(stock.get(x, ''), 'row_qty'))
                    line += [
                        self.cell_ro(stock.get('quar', ''), 'row_qty'),
                        self.cell_ro(stock.get(packing_id, ''), 'row_qty'),
                        self.cell_ro(stock.get(shipmend_id, ''), 'row_qty'),
                        self.cell_ro(stock.get(distribution_id, ''), 'row_qty'),
                        self.cell_ro(in_pipe.get(non_kept.kept_initial_product_id.id, ''), 'row_qty'),
                        self.cell_ro(non_kept.kept_initial_product_id.id in in_use, 'row'),
                    ]

                sheet.append(line)
        sheet.auto_filter.ref = "A6:O6"




XlsxReport('report.report_merged_ud_products', parser=merged_ud_products, template='addons/product_attributes/report/merged_ud_products.xlsx')

