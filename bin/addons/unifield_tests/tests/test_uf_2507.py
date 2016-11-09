#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest


class UF2507ResourcingTest(ResourcingTest):

    def test_uf_2507(self):
        """
        1/ Create a field order with 4 lines and source all lines
        in the same PO.
        2/ Delete the first line.
        3/ Add a new line without origin set
        4/ Set the origin on the new line
        5/ Validate and confirm the PO
        6/ Check the number of lines in the FO
        """
        db = self.used_db

        # Prepare object
        c_wiz_model = 'purchase.order.line.unlink.wizard'
        c_wiz = db.get(c_wiz_model)

        """
        1/ Create and source the first FO
        """
        order_id, order_line_ids, po_ids, po_line_ids = self.order_source_all_one_po(db)

        # Check number of generated PO and PO lines
        self.assertEqual(
            len(po_ids),
            1,
            "Number of generated PO : %s - Should be 1" % len(po_ids),
        )
        self.assertEqual(
            len(po_line_ids),
            4,
            "Number of lines generated in PO : %s - Should be 4" % len(po_line_ids),
        )

        """
        2/ Delete the first line of the PO
        """
        c_res = self.pol_obj.ask_unlink(po_line_ids[0])

        # Check display of cancel wizard
        self.assert_(
            c_res.get('res_id'),
            "No wizard returned by the cancellation of the PO line",
        )
        self.assert_(
            c_res.get('res_model') == c_wiz_model,
            "The model returned by the cancellation of the PO line is not good",
        )

        c_wiz.just_cancel(c_res.get('res_id'))

        # Check the PO line has been removed
        po_line_ids = self.po_obj.read(po_ids[0], ['order_line'])['order_line']
        self.assert_(
            len(po_line_ids) == 3,
            "The line has not been removed well on the PO (%s - should be 3)" % len(po_line_ids),
        )
        # Check the FO line has been removed
        self.assert_(
            self._get_number_of_valid_lines(db, order_id) == 3,
            "The line has not been removed well on the FO",
        )

        """
        3/ Add a new line without origin set
        """
        ana_distrib_id = self.pol_obj.read(po_line_ids[1], ['analytic_distribution_id'])['analytic_distribution_id']
        if not ana_distrib_id:
            ana_distrib_id = self.get_record(db, 'distrib_1')
        else:
            ana_distrib_id = ana_distrib_id[0]
        line_values = {
            'order_id': po_ids[0],
            'product_id': self.get_record(db, 'prod_log_1'),
            'product_uom': self.get_record(db, 'product_uom_unit', module='product'),
            'product_qty': 123,
            'price_unit': 01.20,
            'analytic_distribution_id': ana_distrib_id,
        }
        new_pol_id = self.pol_obj.create(line_values)

        # Check the PO line has been added well
        po_line_ids = self.po_obj.read(po_ids[0], ['order_line'])['order_line']
        self.assert_(
            len(po_line_ids) == 4,
            "Number of lines generated in PO : %s - Should be 4" % len(po_line_ids),
        )

        """
        4/ Set the origin on the new line
        """
        order_name = self.order_obj.read(order_id, ['name'])['name']
        self.pol_obj.write(new_pol_id, {'origin': order_name})

        """
        5/ Validate and confirm the PO
        """
        self._validate_po(db, po_ids)
        self._confirm_po(db, po_ids)


        """
        6/ Check the number of lines in the FO/IR
        """
        # Check the FO line has been added
        fo_lines_nb = self._get_number_of_valid_lines(db, order_id)
        self.assert_(
            fo_lines_nb == 4,
            "The line has not been added well on the order (%s - should be 4)" % fo_lines_nb,
        )


class UF2507FOResourcingTest(UF2507ResourcingTest):

    def setUp(self):
        self.pr = False
        super(UF2507FOResourcingTest, self).setUp()


class UF2507IRResourcingTest(UF2507ResourcingTest):

    def setUp(self):
        self.pr = True
        super(UF2507IRResourcingTest, self).setUp()



def get_test_suite():
    '''Return the class to use for tests'''
    return UF2507FOResourcingTest, UF2507IRResourcingTest