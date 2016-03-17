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
        """
        super(US311Test, self).setUp()
        self.synchronize(self.c1)
        self.synchronize(self.p1)
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
        self.p_sol_obj.confirmLine([self.p_irl1_id, self.p_irl2_id], run_scheduler=False)

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

        self.po_ids = set()
        po_line_ids = []
        for line in self.p_sol_obj.browse(line_ids):
            po_line_ids.extend(self.p_pol_obj.search([
                ('procurement_id', '=', line.procurement_id.id),
            ]))

        for po_line in self.p_pol_obj.read(po_line_ids, ['order_id']):
            self.po_ids.add(po_line['order_id'][0])

        self.p_po_id = self.po_ids and list(self.po_ids)[0] or False
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
        self.c_sol_obj.confirmLine(line_ids, run_scheduler=False)

        # Get the generated PO
        self.c_fo_id = self.run_auto_pos_creation(self.c1, order_to_check=self.c_fo_id)
        line_ids = self.c_sol_obj.search([('order_id', '=', self.c_fo_id)])
        self.po_ids = set()
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
            self.po_ids.add(po_line['order_id'][0])
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

    def tearDown(self):
        """
        """
        return
        super(US311Test, self).tearDown()

    def run_flow(self):
        """
        Confirm the PO, then process the IN and the P/P/S at Coordo
        Sync
        """
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

    def check_quantities(self, doc_type, ex_vals=None, real_vals=None):
        """
        Return True if the ex_vals dict is equal to the real_vals dict
        """
        if ex_vals is None:
            ex_vals = {}

        if real_vals is None:
            real_vals = {}

        self.assert_(ex_vals, "No expected quantities defined")
        self.assert_(real_vals, "No real quantities given")

        product_name = {}
        for pkey in ex_vals.keys():
            product_name[pkey] = self.p1.get('product.product').read(pkey, ['name'])['name']
        for pkey in real_vals.keys():
            if pkey not in product_name:
                product_name[pkey] = self.p1.get('product.product').read(pkey, ['name'])['name']

        kdiff = set(ex_vals.keys()) - set(real_vals.keys())
        self.assert_(
            not kdiff,
            """The result values of %s are not good:
            Expected values: %s,
            Result values  : %s,
            """ % (
                doc_type,
                ' - '.join('%s: %s' % (product_name[x], ex_vals[x]) for x in ex_vals.keys()),
                ' - '.join('%s: %s' % (product_name[x], real_vals[x]) for x in real_vals.keys()),
            ),
        )

        diff_qty = False
        for ex_key, ex_qty in ex_vals.iteritems():
            if real_vals.get(ex_key) != ex_qty:
                diff_qty = True

        self.assert_(
            not diff_qty,
            """The result values of %s are not good:
            Expected values: %s
            Result values  : %s
            """ % (
                doc_type,
                ' - '.join('%s: %s' % (product_name[x], ex_vals[x]) for x in ex_vals.keys()),
                ' - '.join('%s: %s' % (product_name[x], real_vals[x]) for x in real_vals.keys()),
            ),
        )

    def check_ir_quantities(self, ex_vals=None):
        """
        Check if the quantities in the IR are the same as expected in ex_vals.
        """
        real_vals = {}
        for line in self.p_so_obj.browse(self.p_ir_id).order_line:
            if line.state == 'done':
                continue
            real_vals.setdefault(line.product_id.id, 0.00)
            real_vals[line.product_id.id] += line.product_uom_qty

        self.check_quantities('IR', ex_vals, real_vals)

    def check_in_quantities(self, ex_vals=None):
        """
        Check if the quantities in IN are the same as expected in ex_vals.
        """
        real_vals = {}
        ir_name = self.p_so_obj.read(self.p_ir_id, ['name'])['name']
        self.p_in_ids = self.p_pick_obj.search([
            ('type', '=', 'in'),
            ('origin', 'like', ir_name),
        ])
        for pick in self.p_pick_obj.browse(self.p_in_ids):
            for move in pick.move_lines:
                real_vals.setdefault(move.product_id.id, 0.00)
                real_vals[move.product_id.id] += move.product_qty

        self.check_quantities('IN', ex_vals, real_vals)

    def check_out_quantities(self, ex_vals=None):
        """
        """
        real_vals = {}
        self.out_ids = self.p_pick_obj.search([('sale_id', '=', self.p_ir_id), ('type', '=', 'out')])
        for pick in self.p_pick_obj.browse(self.out_ids):
            for move in pick.move_lines:
                real_vals.setdefault(move.product_id.id, 0.00)
                real_vals[move.product_id.id] += move.product_qty

        self.check_quantities('OUT', ex_vals, real_vals)

    def check_prj_quantities(self, simple=False):
        """
        Check quantities of product in different documents at project
        """
        vals = self.ir_vals
        if simple and hasattr(self, 'simple_vals') and getattr(self, 'simple_vals'):
            vals = self.simple_vals

        self.check_ir_quantities(vals)

        # Check IN quantities
        self.check_in_quantities(vals)

        # Check OUT quantities
        self.check_out_quantities(vals)

        self.close_flow()

    def split_po_line(self):
        """
        On the generated PO, split the line of 25 PCE to two lines:
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

        line_ids = self.c_pol_obj.search([('order_id', 'in', list(self.po_ids))])
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

    def cancel_po_line(self):
        """
        Cancel the PO line
        """
        # Cancel the PO line
        res = self.c_pol_obj.ask_unlink(self.c_pol_15)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))

    def test_simple_split_1(self):
        """
        #1 Split the PO line
        #2 Validate the PO
        #3 Confirm the PO
        #4 Sync
        """
        #1 Split the PO line
        self.split_po_line()
        #2 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #3 Confirm the PO and #4 Sync
        self.run_flow()

        self.check_prj_quantities(simple=True)

    def test_simple_split_2(self):
        """
        #1 Split the PO line
        #2 Validate the PO
        #3 Sync
        #4 Confirm the PO
        #5 Sync
        """
        #1 Split the PO line
        self.split_po_line()
        #2 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #3 Sync
        self.synchronize(self.c1)
        #4 Confirm the PO and #5 Sync
        self.run_flow()

        self.check_prj_quantities(simple=True)

    def test_simple_split_3(self):
        """
        #1 Validate the PO
        #2 Split the PO line
        #3 Confirm the PO
        #4 Sync
        """
        #1 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #2 Split the PO line
        self.split_po_line()
        #3 Confirm the PO and #4 Sync
        self.run_flow()

        self.check_prj_quantities(simple=True)

    def test_cancel_line_1(self):
        """
        #1 Split the PO line
        #2 Cancel the PO line
        #3 Validate the PO
        #4 Confirm the PO
        #5 Sync
        """
        #1 Split the PO line
        self.split_po_line()
        #2 Cancel the PO line
        self.cancel_po_line()
        #3 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #4 Confirm the PO and #5 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_2(self):
        """
        #1 Split the PO line
        #2 Validate the PO
        #3 Cancel the PO line
        #4 Confirm the PO
        #5 Sync
        """
        #1 Split the PO line
        self.split_po_line()
        #2 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #3 Cancel the PO line
        self.cancel_po_line()
        #4 Confirm the PO and #5 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_3(self):
        """
        #1 Validate the PO
        #2 Split the PO line
        #3 Cancel the PO line
        #4 Confirm the PO
        #5 Sync
        """
        #1 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #2 Split the PO line
        self.split_po_line()
        #3 Cancel the PO line
        self.cancel_po_line()
        #4 Confirm the PO and #5 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_4(self):
        """
        #1 Split the PO line
        #2 Cancel the PO line
        #3 Validate the PO
        #4 Sync
        #5 Confirm the PO
        #6 Sync
        """
        #1 Split the PO line
        self.split_po_line()
        #2 Cancel the PO line
        self.cancel_po_line()
        #3 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #4 Synchronize
        self.synchronize(self.c1)
        #5 Confirm the PO and #6 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_5(self):
        """
        #1 Split the PO line
        #2 Validate the PO
        #3 Cancel the PO line
        #4 Sync
        #5 Confirm the PO
        #6 Sync
        """
        #1 Split the PO line
        self.split_po_line()
        #2 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #3 Cancel the PO line
        self.cancel_po_line()
        #4 Synchronize
        self.synchronize(self.c1)
        #5 Confirm the PO and #6 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_6(self):
        """
        #1 Split the PO line
        #2 Validate the PO
        #3 Sync
        #4 Cancel the PO line
        #5 Confirm the PO
        #6 Sync
        """
        #1 Split the PO line
        self.split_po_line()
        #2 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #3 Synchronize
        self.synchronize(self.c1)
        #4 Cancel the PO line
        self.cancel_po_line()
        #5 Confirm the PO and #6 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_7(self):
        """
        #1 Sync
        #2 Split the PO line
        #3 Cancel the PO line
        #4 Validate the PO
        #5 Confirm the PO
        #6 Sync
        """
        #1 Synchronize
        self.synchronize(self.c1)
        #2 Split the PO line
        self.split_po_line()
        #3 Cancel the PO line
        self.cancel_po_line()
        #4 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #5 Confirm the PO and #6 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_8(self):
        """
        #1 Sync
        #2 Split the PO line
        #3 Validate the PO
        #4 Cancel the PO line
        #5 Confirm the PO
        #6 Sync
        """
        #1 Synchronize
        self.synchronize(self.c1)
        #2 Split the PO line
        self.split_po_line()
        #3 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #4 Cancel the PO line
        self.cancel_po_line()
        #5 Confirm the PO and #6 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_9(self):
        """
        #1 Sync
        #2 Validate the PO
        #3 Split the PO line
        #4 Cancel the PO line
        #5 Confirm the PO
        #6 Sync
        """
        #1 Synchronize
        self.synchronize(self.c1)
        #2 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #3 Split the PO line
        self.split_po_line()
        #4 Cancel the PO line
        self.cancel_po_line()
        #5 Confirm the PO and #6 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_10(self):
        """
        #1 Sync
        #2 Split the PO line
        #2 Cancel the PO line
        #3 Validate the PO
        #4 Sync
        #6 Confirm the PO
        #7 Sync
        """
        #1 Synchronize
        self.synchronize(self.c1)
        #2 Split the PO line
        self.split_po_line()
        #3 Cancel the PO line
        self.cancel_po_line()
        #4 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #5 Synchronize
        self.synchronize(self.c1)
        #6 Confirm the PO and #7 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_11(self):
        """
        #1 Sync
        #2 Split the PO line
        #3 Validate the PO
        #4 Cancel the PO line
        #5 Sync
        #6 Confirm the PO
        #7 Sync
        """
        #1 Synchronize
        self.synchronize(self.c1)
        #2 Split the PO line
        self.split_po_line()
        #3 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #4 Cancel the PO line
        self.cancel_po_line()
        #5 Synchronize
        self.synchronize(self.c1)
        #6 Confirm the PO and #7 Sync
        self.run_flow()

        self.check_prj_quantities()

    def test_cancel_line_12(self):
        """
        #1 Sync
        #2 Split the PO line
        #3 Validate the PO
        #4 Sync
        #5 Cancel the PO line
        #6 Confirm the PO
        #7 Sync
        """
        #1 Synchronize
        self.synchronize(self.c1)
        #2 Split the PO line
        self.split_po_line()
        #3 Validate the PO
        self._validate_po(self.c1, [self.c_po_id])
        #4 Synchronize
        self.synchronize(self.c1)
        #5 Cancel the PO line
        self.cancel_po_line()
        #6 Confirm the PO and #7 Sync
        self.run_flow()

        self.check_prj_quantities()

    def cancel_original_splitted_line_more_on_new_line(self):
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
        ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 50.00,
        }
        self.check_ir_quantities(ir_vals)

        # Check IN quantities
        self.check_in_quantities(ir_vals)

        # Check OUT quantities
        self.check_out_quantities(ir_vals)

        self.close_flow()

    def change_product_on_splitted_line(self):
        """
        Change the product of the splitted line, confirm the PO, process the
        IN and the P/P/S at coordo, then sync.
        At project, check the product of lines in OUT.
        Process the IN and the OUT.
        """
        #1 Split the PO line
        self.split_po_line()

        # Change the product of the splitted line
        self.c_pol_obj.write(self.c_pol_10, {'product_id': self.c_prd3_id})

        self.run_flow()

        # Check IR quantities
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 15.00,
            self.p_prd3_id: 10.00,
        }
        self.check_ir_quantities(ir_vals)

        # Check IN quantities
        self.check_in_quantities(ir_vals)

        # Check OUT quantities
        self.check_out_quantities(ir_vals)

        self.close_flow()

class US311TestCancelNewLine(US311Test):
    """
    Split the PO line at coordo side, then cancel the new created line.
    """
    def setUp(self):
        super(US311TestCancelNewLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
           self.p_prd2_id: 25.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 10.00,
        }

    def cancel_po_line(self):
        """
        Cancel the PO line
        """
        # Cancel the PO line
        res = self.c_pol_obj.ask_unlink(self.c_pol_15)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))

class US311TestCancelOldLine(US311Test):
    """
    Split the PO line at coordo side, then cancel the old line.
    """
    def setUp(self):
        super(US311TestCancelOldLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 25.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 15.00,
        }

    def cancel_po_line(self):
        """
        Cancel the old PO line
        """
        # Cancel the PO lines
        res = self.c_pol_obj.ask_unlink(self.c_pol_10)
        self.assert_(
            res.get('res_id', False) and res.get('res_model', False) == 'purchase.order.line.unlink.wizard',
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        w_res = self.c1.get('purchase.order.line.unlink.wizard').just_cancel(res.get('res_id'))

class US311TestCancelNewLineMoreOnNewLine(US311TestCancelNewLine):
    """
    Split the PO line at coordo side, add more than the initial quantity
    then cancel the splitted line.
    """
    def setUp(self):
        super(US311TestCancelNewLineMoreOnNewLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 60.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 10.00,
        }

    def split_po_line(self):
        super(US311TestCancelNewLineMoreOnNewLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_15, {'product_qty': 50.0})

class US311TestCancelNewLineMoreOnOldLine(US311TestCancelNewLine):
    """
    Split the PO line at coordo side, add more than the initial quantity
    then cancel the splitted line.
    """
    def setUp(self):
        super(US311TestCancelNewLineMoreOnOldLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 65.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 50.00,
        }

    def split_po_line(self):
        super(US311TestCancelNewLineMoreOnOldLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_10, {'product_qty': 50.0})

class US311TestCancelNewLineLessOnNewLine(US311TestCancelNewLine):
    """
    Split the PO line at coordo side, reduce the initial quantity
    then cancel the splitted line.
    """
    def setUp(self):
        super(US311TestCancelNewLineLessOnNewLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 23.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 10.00,
        }

    def split_po_line(self):
        super(US311TestCancelNewLineLessOnNewLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_15, {'product_qty': 13.0})

class US311TestCancelNewLineLessOnOldLine(US311TestCancelNewLine):
    """
    Split the PO line at coordo side, reduce the initial quantity
    then cancel the splitted line.
    """
    def setUp(self):
        super(US311TestCancelNewLineLessOnOldLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 20.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 5.00,
        }

    def split_po_line(self):
        super(US311TestCancelNewLineLessOnOldLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_10, {'product_qty': 5.0})

class US311TestCancelOldLineLessOnOldLine(US311TestCancelOldLine):
    """
    Split the PO line at coordo side, reduce the inital quantity
    then cancel the new created line.
    """
    def setUp(self):
        super(US311TestCancelOldLineLessOnOldLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 20.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 15.00,
        }

    def split_po_line(self):
        super(US311TestCancelOldLineLessOnOldLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_10, {'product_qty': 5.0})

class US311TestCancelOldLineLessOnNewLine(US311TestCancelOldLine):
    """
    Split the PO line at coordo side, reduce the inital quantity
    then cancel the new created line.
    """
    def setUp(self):
        super(US311TestCancelOldLineLessOnNewLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 23.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 13.00,
        }

    def split_po_line(self):
        super(US311TestCancelOldLineLessOnNewLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_15, {'product_qty': 13.0})

class US311TestCancelOldLineMoreOnOldLine(US311TestCancelOldLine):
    """
    Split the PO line at coordo side, add more than the inital quantity
    then cancel the new created line.
    """
    def setUp(self):
        super(US311TestCancelOldLineMoreOnOldLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 65.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 15.00,
        }

    def split_po_line(self):
        super(US311TestCancelOldLineMoreOnOldLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_10, {'product_qty': 50.0})

class US311TestCancelOldLineMoreOnNewLine(US311TestCancelOldLine):
    """
    Split the PO line at coordo side, add more than the inital quantity
    then cancel the new created line.
    """
    def setUp(self):
        super(US311TestCancelOldLineMoreOnNewLine, self).setUp()
        self.simple_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 60.00,
        }
        self.ir_vals = {
            self.p_prd1_id: 18.00,
            self.p_prd2_id: 50.00,
        }

    def split_po_line(self):
        super(US311TestCancelOldLineMoreOnNewLine, self).split_po_line()
        # Add quantities on new line
        self.c_pol_obj.write(self.c_pol_15, {'product_qty': 50.0})

class US311TestCancelAllLines(US311Test):
    """
    Split the PO line at coordo side, then cancel the old line and the new line
    """
    def setUp(self):
        super(US311TestCancelAllLines, self).setUp()
        self.ir_vals = {
            self.p_prd1_id: 18.00,
        }

    def cancel_po_line(self):
        """
        Cancel the old and the new PO lines
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

#def get_test_class():
#    return US311TestCancelNewLine

def get_test_suite():
    return US311TestCancelNewLine, US311TestCancelNewLineMoreOnNewLine, US311TestCancelNewLineMoreOnOldLine, US311TestCancelNewLineLessOnNewLine, US311TestCancelNewLineLessOnOldLine, US311TestCancelOldLine, US311TestCancelOldLineMoreOnNewLine, US311TestCancelOldLineMoreOnOldLine, US311TestCancelOldLineLessOnNewLine, US311TestCancelOldLineLessOnOldLine, US311TestCancelAllLines
