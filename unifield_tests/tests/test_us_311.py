#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest


class US311Test(ResourcingTest):

    def setUp(self):
        """
        1/ Create an IR with two lines at project:
           * One with 18 PCE of product 1
           * One with 25 PCE of product 2
        2/ Validate the IR
        3/ Source all lines to the coordo
        4/ Validate the PO
        5/ Sync.
        6/ At coordo, validate the FO
        7/ Source the two lines to an external supplier
        8/ On the generated PO, split the line of 25 PCE to two lines:
           * One line with 15 PCE
           * One line with 10 PCE
        """
        super(US311Test, self).setUp()
        # Project objects mapper
        self.p_so_obj = self.p1.get('sale.order')
        self.p_sol_obj = self.p1.get('sale.order.line')
        self.p_po_obj = self.p1.get('purchase.order')
        self.p_pol_obj = self.p1.get('purchase.order.line')
        self.p_pick_obj = self.p1.get('stock.picking')
        self.p_move_obj = self.p1.get('stock.move')
        self.p_partner_obj = self.p1.get('res.partner')
        # Coordo objects mapper
        self.c_so_obj = self.c1.get('sale.order')
        self.c_sol_obj = self.c1.get('sale.order.line')
        self.c_po_obj = self.c1.get('purchase.order')
        self.c_pol_obj = self.c1.get('purchase.order.line')
        self.c_pick_obj = self.c1.get('stock.picking')
        self.c_move_obj = self.c1.get('stock.move')
        self.c_partner_obj = self.c1.get('res.partner')

        # Products
        self.p_prd1_id = self.get_record(self.p1, 'prod_log_1')
        self.p_prd2_id = self.get_record(self.p1, 'prod_log_2')
        self.p_prd3_id = self.get_record(self.p1, 'prod_log_3')
        self.c_prd1_id = self.get_record(self.c1, 'prod_log_1')
        self.c_prd2_id = self.get_record(self.c1, 'prod_log_2')
        self.c_prd3_id = self.get_record(self.c1, 'prod_log_3')

        # Get Project and Coordo partners
        project_name = self.get_db_partner_name(self.p1)
        coordo_name = self.get_db_partner_name(self.c1)
        c_proj_ids = self.c_partner_obj.search([('name', '=', project_name)])
        p_coordo_ids = self.p_partner_obj.search([('name', '=', coordo_name)])

        self.assert_(
            c_proj_ids,
            "No project partner found in Coordination",
        )
        self.assert_(
            p_coordo_ids,
            "No coordination partner found in Project",
        )
        self.c_prj_id = c_proj_ids[0]
        self.p_crd_id = p_coordo_ids[0]

        # Prepare values for IR
        uom_pce_id = self.get_record(self.p1, 'product_uom_unit', module='product')
        distrib_id = self.create_analytic_distribution(self.p1)

        """
        1/ Create an IR with two lines at project:
           * One with 18 PCE of product 1
           * One with 25 PCE of product 2
        """
        ir_values = {
            'procurement_request': True,
            'location_requestor_id': self.get_record(self.p1, 'external_cu'),
        }
        self.p_ir_id = self.p_so_obj.create(ir_values)
        l1_values = {
            'order_id': self.p_ir_id,
            'product_id': self.p_prd1_id,
            'product_uom': uom_pce_id,
            'product_uom_qty': 18.00,
            'type': 'make_to_order',
            'price_unit': 1.00,
        }
        self.p_irl1_id = self.p_sol_obj.create(l1_values)

        l2_values = l1_values.copy()
        l2_values.update({
            'product_id': self.p_prd2_id,
            'product_uom_qty': 25.00,
        })
        self.p_irl2_id = self.p_sol_obj.create(l2_values)

        """
        2/ Validate the IR
        """
        self.p1.exec_workflow('sale.order', 'procurement_validate', self.p_ir_id)

        """
        3/ Source all lines to the coordo
        """
        self.p_sol_obj.write([self.p_irl1_id, self.p_irl2_id], {
            'po_cft': 'po',
            'supplier': self.p_crd_id,
        })
        self.p_sol_obj.confirmLine([self.p_irl1_id, self.p_irl2_id])

        # Run the scheduler
        self.p_ir_id = self.run_auto_pos_creation(self.p1, order_to_check=self.p_ir_id)
        line_ids = self.p_sol_obj.search([('order_id', '=', self.p_ir_id)])
        not_sourced = True
        while not_sourced:
            not_sourced = False
            for line in self.p_sol_obj.browse(line_ids):
                if line.procurement_id.state != 'running':
                    not_source = True
            if not_sourced:
                time.sleep(1)

        po_ids = set()
        po_line_ids = []
        for line in self.p_sol_obj.browse(line_ids):
            po_line_ids.extend(self.p_pol_obj.search([
                ('procurement_id', '=', line.procurement_id.id),
            ]))

        for po_line in self.p_pol_obj.read(po_line_ids, ['order_id']):
            po_ids.add(po_line['order_id'][0])

        self.p_po_id = po_ids and list(po_ids)[0] or False
        self.p_po_name = self.p_po_obj.read(self.p_po_id, ['name'])['name']

        """
        4/ Validate the PO
        """
        self._validate_po(self.p1, [self.p_po_id])

        """
        5/ Sync.
        """
        self.synchronize(self.p1)
        self.synchronize(self.c1)

        """
        6/ At coordo, validate the FO
        """
        self.c_fo_id = None
        self.c_fo_ids = self.c_so_obj.search([('client_order_ref', 'like', self.p_po_name)])
        for c_fo_id in self.c_fo_ids:
            self.assert_(
                self.c_so_obj.read(c_fo_id, ['state'])['state'] == 'draft',
                "The FO at Coordo is not 'Draft'.",
            )
            self.c_fo_id = c_fo_id

        # Validate the Field order
        self.c1.exec_workflow('sale.order', 'order_validated', self.c_fo_id)

        """
        7/ Source the two lines to an external supplier
        """
        line_ids = self.c_sol_obj.search([('order_id', '=', self.c_fo_id)])
        self.c_sol_obj.write(line_ids, {
            'type': 'make_to_order',
            'po_cft': 'po',
            'supplier': self.get_record(self.c1, 'ext_supplier_1'),
        })
        self.c_sol_obj.confirmLine(line_ids)

        # Get the generated PO
        self.c_fo_id = self.run_auto_pos_creation(self.c1, order_to_check=self.c_fo_id)
        line_ids = self.c_sol_obj.search([('order_id', '=', self.c_fo_id)])
        po_ids = set()
        po_line_ids = []
        self.c_pol_18 = None
        self.c_pol_25 = None
        self.c_pol_10 = None
        self.c_pol_15 = None
        for line in self.c_sol_obj.browse(line_ids):
            if line.procurement_id:
                po_line_ids.extend(self.c_pol_obj.search([
                    ('procurement_id', '=', line.procurement_id.id),
                ]))
        for po_line in self.c_pol_obj.read(po_line_ids, ['order_id', 'product_qty']):
            po_ids.add(po_line['order_id'][0])
            self.c_po_id = po_line['order_id'][0]
            if po_line['product_qty'] == 18.00:
                self.c_pol_18 = po_line['id']
            elif po_line['product_qty'] == 25.00:
                self.c_pol_25 = po_line['id']

        self.assert_(
            self.c_pol_18,
            "Line with 18 PCE not found on PO",
        )
        self.assert_(
            self.c_pol_25,
            "Line with 25 PCE not found on PO",
        )

        """
        8/ On the generated PO, split the line of 25 PCE to two lines:
           * One line with 15 PCE
           * One line with 10 PCE
        """
        split_obj = self.c1.get('split.purchase.order.line.wizard')
        split_id = split_obj.create({
            'purchase_line_id': self.c_pol_25,
            'original_qty': 25.00,
            'old_line_qty': 10.00,
            'new_line_qty': 15.00,
        })
        split_obj.split_line([split_id])

        line_ids = self.c_pol_obj.search([('order_id', 'in', list(po_ids))])
        for pol in self.c_pol_obj.browse(line_ids):
            if pol.product_qty == 18.00:
                self.c_pol_18 = pol.id
            elif pol.product_qty == 10.00:
                self.c_pol_10 = pol.id
            elif pol.product_qty == 15.00:
                self.c_pol_15 = pol.id

        self.assert_(
            self.c_pol_18 and self.c_pol_10 and self.c_pol_15,
            "Not all needed PO lines are found",
        )

    def tearDown(self):
        """
        """
        super(US311Test, self).tearDown()

    def run_flow(self):
        """
        Confirm the PO, then process the IN and the P/P/S at Coordo
        Sync
        """
        # Validate the PO
        self._validate_po(self.c1, [self.c_po_id])

        # Confirm the PO
        self._confirm_po(self.c1, [self.c_po_id])

        # Process the IN
        c_in_ids = self.c_pick_obj.search([('purchase_id', '=', self.c_po_id), ('type', '=', 'in')])
        self.assert_(
            len(c_in_ids) == 1,
            "There are %s IN association to PO - Should be 1" % len(c_in_ids),
        )
        proc_obj = self.c1.get('stock.incoming.processor')
        proc_res = self.c_pick_obj.action_process(c_in_ids)
        proc_id = proc_res.get('res_id')
        proc_obj.copy_all([proc_id])
        proc_obj.do_incoming_shipment([proc_id])

        # Process P/P/S
        c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_fo_id), ('type', '=', 'out'), ('state', '=', 'assigned')])
        self.assert_(
            len(c_out_ids) == 1,
            "There are %s OUT/PICK associated to FO - Should be 1" % len(c_out_ids),
        )
        out_proc_obj = self.c1.get('outgoing.delivery.processor')
        conv_res = self.c_pick_obj.convert_to_standard(c_out_ids)
        out_id = conv_res.get('res_id')
        proc_res = self.c_pick_obj.action_process([out_id])
        out_proc_obj.copy_all([proc_res.get('res_id')])
        out_proc_obj.do_partial([proc_res.get('res_id')])

        self.synchronize(self.c1)
        self.synchronize(self.p1)

    def close_flow(self):
        """
        Process the IN and the OUT at project
        """
        # Process the IN
        proc_obj = self.p1.get('stock.incoming.processor')
        for in_id in self.p_in_ids:
            proc_res = self.p_pick_obj.action_process([in_id])
            proc_id = proc_res.get('res_id')
            proc_obj.copy_all([proc_id])
            proc_obj.do_incoming_shipment([proc_id])

        # Process the OUT
        out_proc_obj = self.p1.get('outgoing.delivery.processor')
        for out_id in self.out_ids:
            proc_res = self.p_pick_obj.action_process([out_id])
            out_proc_obj.copy_all([proc_res.get('res_id')])
            out_proc_obj.do_partial([proc_res.get('res_id')])

        self.assert_(
            self.p_so_obj.browse(self.p_ir_id).state == 'done',
            "The Internal request is not Closed",
        )

    def test_cancel_new_splitted_line(self):
        """
        Cancel the new line after the split, confirm the PO, process the IN and the P/P/S
        at coordo, then sync.
        At project, check the number of lines in OUT.
        Process the IN and the OUT.
        """
        # Cancel the PO line
        res = self.c_pol_obj.ask_unlink(self.c_pol_15)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))

        self.run_flow()

        # Check IR quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        for line in self.p_so_obj.browse(self.p_ir_id).order_line:
            if line.state == 'done':
                continue
            if line.product_id.id == self.p_prd1_id:
                prd1_qty += line.product_uom_qty
            elif line.product_id.id == self.p_prd2_id:
                prd2_qty += line.product_uom_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 10.00,
            "The quantities on IR moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check IN quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        ir_name = self.p_so_obj.read(self.p_ir_id, ['name'])['name']
        self.p_in_ids = self.p_pick_obj.search([
            ('type', '=', 'in'),
            ('origin', 'like', ir_name),
        ])
        for pick in self.p_pick_obj.browse(self.p_in_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 10.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check OUT quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        self.out_ids = self.p_pick_obj.search([('sale_id', '=', self.p_ir_id), ('type', '=', 'out')])
        for pick in self.p_pick_obj.browse(self.out_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 10.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        self.close_flow()

    def test_cancel_all_splitted_lines(self):
        """
        Cancel the splitted line, confirm the PO, process the IN and the P/P/S
        at coordo, then sync.
        At project, check the number of lines in OUT.
        Process the IN and the OUT.
        """
        # Cancel the PO lines
        res = self.c_pol_obj.ask_unlink(self.c_pol_10)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))
        res = self.c_pol_obj.ask_unlink(self.c_pol_15)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))

        self.run_flow()

        # Check IR quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        for line in self.p_so_obj.browse(self.p_ir_id).order_line:
            if line.state == 'done':
                continue
            if line.product_id.id == self.p_prd1_id:
                prd1_qty += line.product_uom_qty
            elif line.product_id.id == self.p_prd2_id:
                prd2_qty += line.product_uom_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 0.00,
            "The quantities on IR moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check IN quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        ir_name = self.p_so_obj.read(self.p_ir_id, ['name'])['name']
        self.p_in_ids = self.p_pick_obj.search([
            ('type', '=', 'in'),
            ('origin', 'like', ir_name),
        ])
        for pick in self.p_pick_obj.browse(self.p_in_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 0.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check OUT quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        self.out_ids = self.p_pick_obj.search([('sale_id', '=', self.p_ir_id), ('type', '=', 'out')])
        for pick in self.p_pick_obj.browse(self.out_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 0.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        self.close_flow()

    def test_cancel_original_splitted_line_more_on_new_line(self):
        """
        Cancel the splitted line, confirm the PO, process the IN and the P/P/S
        at coordo, then sync.
        At project, check the number of lines in OUT.
        Process the IN and the OUT.
        """
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_15, {'product_qty': 50.0})
        # Cancel the PO line
        res = self.c_pol_obj.ask_unlink(self.c_pol_10)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))

        self.run_flow()

        # Check IR quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        for line in self.p_so_obj.browse(self.p_ir_id).order_line:
            if line.state == 'done':
                continue
            if line.product_id.id == self.p_prd1_id:
                prd1_qty += line.product_uom_qty
            elif line.product_id.id == self.p_prd2_id:
                prd2_qty += line.product_uom_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 50.00,
            "The quantities on IR moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check IN quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        ir_name = self.p_so_obj.read(self.p_ir_id, ['name'])['name']
        self.p_in_ids = self.p_pick_obj.search([
            ('type', '=', 'in'),
            ('origin', 'like', ir_name),
        ])
        for pick in self.p_pick_obj.browse(self.p_in_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 50.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check OUT quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        self.out_ids = self.p_pick_obj.search([('sale_id', '=', self.p_ir_id), ('type', '=', 'out')])
        for pick in self.p_pick_obj.browse(self.out_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 50.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        self.close_flow()

    def test_cancel_original_splitted_line(self):
        """
        Cancel the splitted line, confirm the PO, process the IN and the P/P/S
        at coordo, then sync.
        At project, check the number of lines in OUT.
        Process the IN and the OUT.
        """
        # Cancel the PO line
        res = self.c_pol_obj.ask_unlink(self.c_pol_10)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))

        self.run_flow()

        # Check IR quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        for line in self.p_so_obj.browse(self.p_ir_id).order_line:
            if line.state == 'done':
                continue
            if line.product_id.id == self.p_prd1_id:
                prd1_qty += line.product_uom_qty
            elif line.product_id.id == self.p_prd2_id:
                prd2_qty += line.product_uom_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 15.00,
            "The quantities on IR moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check IN quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        ir_name = self.p_so_obj.read(self.p_ir_id, ['name'])['name']
        self.p_in_ids = self.p_pick_obj.search([
            ('type', '=', 'in'),
            ('origin', 'like', ir_name),
        ])
        for pick in self.p_pick_obj.browse(self.p_in_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 15.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        # Check OUT quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        self.out_ids = self.p_pick_obj.search([('sale_id', '=', self.p_ir_id), ('type', '=', 'out')])
        for pick in self.p_pick_obj.browse(self.out_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 15.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s)" % (prd1_qty, prd2_qty),
        )

        self.close_flow()

    def test_change_product_on_splitted_line(self):
        """
        Change the product of the splitted line, confirm the PO, process the
        IN and the P/P/S at coordo, then sync.
        At project, check the product of lines in OUT.
        Process the IN and the OUT.
        """
        # Change the product of the splitted line
        self.c_pol_obj.write(self.c_pol_10, {'product_id': self.c_prd3_id})

        self.run_flow()

        # Check IR quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        prd3_qty = 0.00
        for line in self.p_so_obj.browse(self.p_ir_id).order_line:
            if line.product_id.id == self.p_prd1_id:
                prd1_qty += line.product_uom_qty
            elif line.product_id.id == self.p_prd2_id:
                prd2_qty += line.product_uom_qty
            elif line.product_id.id == self.p_prd3_id:
                prd3_qty += line.product_uom_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 15.00 and prd3_qty == 10.00,
            "The quantities on IR moves are not good. (PRD1: %s - PRD2: %s - PRD3: %s)" % (prd1_qty, prd2_qty, prd3_qty),
        )

        # Check IN quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        prd3_qty = 0.00
        ir_name = self.p_so_obj.read(self.p_ir_id, ['name'])['name']
        self.p_in_ids = self.p_pick_obj.search([
            ('type', '=', 'in'),
            ('origin', 'like', ir_name),
        ])
        for pick in self.p_pick_obj.browse(self.p_in_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty
                elif move.product_id.id == self.p_prd3_id:
                    prd3_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 15.00 and prd3_qty == 10.00,
            "The quantities on IN moves are not good. (PRD1: %s - PRD2: %s - PRD3: %s)" % (prd1_qty, prd2_qty, prd3_qty),
        )

        # Check OUT quantities
        prd1_qty = 0.00
        prd2_qty = 0.00
        prd3_qty = 0.00
        self.out_ids = self.p_pick_obj.search([('sale_id', '=', self.p_ir_id), ('type', '=', 'out')])
        for pick in self.p_pick_obj.browse(self.out_ids):
            for move in pick.move_lines:
                if move.product_id.id == self.p_prd1_id:
                    prd1_qty += move.product_qty
                elif move.product_id.id == self.p_prd2_id:
                    prd2_qty += move.product_qty
                elif move.product_id.id == self.p_prd3_id:
                    prd3_qty += move.product_qty

        self.assert_(
            prd1_qty == 18.00 and prd2_qty == 15.00 and prd3_qty == 10.00,
            "The quantities on OUT moves are not good. (PRD1: %s - PRD2: %s - PRD3: %s)" % (prd1_qty, prd2_qty, prd3_qty),
        )

        self.close_flow()

def get_test_class():
    return US311Test
