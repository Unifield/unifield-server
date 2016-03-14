#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from test_uftp_326 import UFTP326Test

import time


class UFTP416Test(UFTP326Test):

    def setUp(self):
        super(UFTP416Test, self).setUp()
        self.c_move_obj = self.c1.get('stock.move')
        self.c_move_cancel_obj = self.c1.get('stock.move.cancel.wizard')

    def test_cancel_po_at_coordo(self):
        """
        Cancel the PO at coordo side.
        Check if the PO at project side is canceled.
        :return:
        """
        # Already done on UFTP326Test
        pass

    def cancel_or_resource_in_line_at_coordo(self, resource=False):
        """
        Cancel or Cancel & Resource the IN at coordo side.
        Check if the PO and the FO at coordo side are canceled.
        Check if the PO at project side is canceled.
        :return:
        """
        # Validate and confirm the PO
        self._validate_po(self.c1, [self.c_po_id])
        self._confirm_po(self.c1, [self.c_po_id])

        # Get the IN associated to this PO
        c_in_ids = self.c_pick_obj.search([('purchase_id', '=', self.c_po_id), ('type', '=', 'in')])
        self.c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out')])
        self.assert_(
            len(c_in_ids) == 1,
            "There are %s IN associated to PO - Should be 1" % len(c_in_ids),
        )
        self.assert_(
            len(self.c_out_ids) == 1,
            "There are %s OUT/PICK associated to FO - Should be 1" % len(self.c_out_ids),
        )

        # Cancel the first IN line
        pick_in_brw = self.c_pick_obj.browse(c_in_ids[0])
        in_move_id = False
        for in_move in pick_in_brw.move_lines:
            in_move_id = in_move.id
            wiz_res = self.c_move_obj.call_cancel_wizard([in_move_id])
            self.assert_(
                wiz_res.get('res_id') and wiz_res.get('res_model') == 'stock.move.cancel.wizard',
                "The wizard to cancel and resource the IN move is not well displayed",
            )
            if not resource:
                self.c_move_cancel_obj.just_cancel([wiz_res['res_id']])
            else:
                self.c_move_cancel_obj.cancel_and_resource([wiz_res['res_id']])
            break

        # Check IN and OUT states
        in_state = self.c_pick_obj.read(c_in_ids, ['state'])
        out_state = self.c_pick_obj.read(self.c_out_ids, ['state'])
        self.assert_(
            all([x['state'] != 'cancel' for x in in_state]),
            "All IN are canceled",
        )
        self.assert_(
            all([x['state'] != 'done' for x in out_state]),
            "All OUT/PICK not canceled",
        )

        # Check IN move state
        m_in_state = self.c_move_obj.read(in_move_id, ['state'])
        self.assert_(
            m_in_state['state'] == 'cancel',
            "The IN move has not been canceled well",
        )

    def test_cancel_in_at_coordo(self):
        pass

    def test_resource_in_at_coordo(self):
        pass

    def test_cancel_in_line_at_coordo(self):
        """
        Cancel the IN at coordo side.
        Check if the PO and the FO at coordo side are canceled.
        Check if the PO at project side is canceled.
        :return:
        """
        self.cancel_or_resource_in_line_at_coordo()


class UFTP416FOTest(UFTP416Test):

    def setUp(self):
        self.procurement_request = False
        super(UFTP416FOTest, self).setUp()

    def test_resource_in_line_at_coordo(self):
        """
        Cancel & Resource the IN at coordo side.
        Check if the PO and the FO at coordo side are canceled.
        Check if the PO at project side is canceled.
        :return:
        """
        fo_ids = self.c_so_obj.search([('procurement_request', '=', False)])
        self.cancel_or_resource_in_line_at_coordo(resource=True)
        end_fo_ids = self.c_so_obj.search([('procurement_request', '=', False)])
        self.assert_(
            len(end_fo_ids) ==len(fo_ids) + 1,
            "The new FO has not been well created",
        )

        # Check OUT move states
        c_out_brw = self.c_pick_obj.browse(self.c_out_ids)
        for c_out in c_out_brw:
            nb_lines = 0
            cancel = 0
            not_cancel = 0
            product_canceled = False
            product_line = 0
            for m_line in c_out.move_lines:
                nb_lines += 1
                if m_line.state == 'cancel':
                    if product_canceled != m_line.product_id.id:
                        cancel += 1
                        product_canceled = m_line.product_id.id
                    product_line += 1
                else:
                    not_cancel += 1

            self.assert_(
                cancel == 1,
                "There are more than one OUT line canceled :: %s" % cancel,
            )
            self.assert_(
                not_cancel == nb_lines - product_line,
                "There are not the good number of lines not canceled :: %s" % not_cancel,
            )

class UFTP416IRTest(UFTP416Test):

    def setUp(self):
        self.procurement_request = True
        super(UFTP416IRTest, self).setUp()

    def test_resource_in_line_at_coordo(self):
        """
        Cancel & Resource the IN at coordo side.
        Check if the PO and the FO at coordo side are canceled.
        Check if the PO at project side is canceled.
        :return:
        """
        ir_ids = self.c_so_obj.search([('procurement_request', '=', True)])
        ir_nb_lines = len(self.c_so_obj.read(self.c_so_id, ['order_line'])['order_line'])
        self.cancel_or_resource_in_line_at_coordo(resource=True)
        end_ir_ids = self.c_so_obj.search([('procurement_request', '=', True)])
        self.assert_(
            len(end_ir_ids) ==len(ir_ids) + 1,
            "The new IR has not been well created",
        )

        # Check OUT move states
        c_out_brw = self.c_pick_obj.read(self.c_out_ids, ['move_lines'])
        for c_out in c_out_brw:
            self.assert_(
                len(c_out['move_lines']) == ir_nb_lines-1,
                "The OUT move has not been well removed",
            )

def get_test_suite():
    return UFTP416FOTest, UFTP416IRTest
