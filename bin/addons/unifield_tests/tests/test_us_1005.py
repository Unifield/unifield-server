#!/usr/bin/env python
# -*- coding: utf8 -*-

#
# FINANCE GL/AD CORRECTION UNIT TESTS
# Developer: Vincent GREINER
#

from unifield_test import UnifieldTestException
from unifield_test import UnifieldTest
from finance import FinanceTest

import time
from datetime import datetime


class TestUS1005(FinanceTest):
    reg_id = False

    def setUp(self):
        abs_obj = self.p1.get('account.bank.statement')
        nb = abs_obj.search_count([])
        reg_code = "US-1005%s" % nb
        self.reg_id, j_id = self.register_create(self.p1, reg_code, reg_code, 'bank', '10200', 'EUR')
        abs_obj.button_open_bank([self.reg_id])

    def get_move_id_from_invoices(self, db, invoice_ids):
        move_ids = []
        if isinstance(invoice_ids, (int, long)):
            invoice_ids = [invoice_ids]

        for inv in db.get('account.invoice').read(invoice_ids, ['move_id']):
            move_ids.append(inv['move_id'][0])
        return move_ids

    def pending_payment(self, db, invoice_ids, percent=1):
        move_ids = self.get_move_id_from_invoices(db, invoice_ids)
        aml_obj = db.get('account.move.line')
        aml_ids = aml_obj.search([('move_id', 'in', move_ids), ('ready_for_import_in_register', '=', True)])

        self.assert_(aml_ids, "No line from invoice ids %s to import" %(invoice_ids,))

        import_inv = db.get('wizard.import.invoice')
        wiz_id = import_inv.create({'statement_id': self.reg_id, 'line_ids': [(6, 0, aml_ids)]})
        import_inv.group_import([wiz_id], {})

        wiz = import_inv.browse(wiz_id)
        import_line = wiz.invoice_lines_ids.next()
        amount = import_line.amount
        db.get('wizard.import.invoice.lines').write([import_line.id], {'amount': amount*percent})
        return import_inv.action_confirm([wiz_id]).get('st_line_ids')

    def check_posted_reconciled(self, db, move_ids):
        for x in db.get('account.move').browse(move_ids):
            self.assert_(x.state == 'posted', 'JE %s not posted at %s' % (x.name, db.db_name))
            rec = False
            for line in x.line_id:
                self.assert_(line.state == 'valid', 'JI %s not valid at %s' % (x.name, db.db_name))
                if line.reconcile_id:
                    rec = True
            self.assert_(rec, 'JI %s not reconciled at %s' % (x.name, db.db_name))

    def create_invoices(self, db, amount):
        self.partner_id = db.get('res.partner').search([('partner_type', '=', 'external')])[0]
        new_invoices = []
        for i in amount:
            i1 = self.invoice_create_supplier_invoice(db,
                lines_accounts=[('62000', i)],
                ad_header_breakdown_data=[['100', 'OPS', 'HT101', 'PF']],
                partner_id=self.partner_id,
                ccy_code='EUR',
                )
            self.invoice_validate(db, i1)
            new_invoices.append(i1)
        return new_invoices

    def check_local_instance(self, db, st_line_ids, invoice_ids):
        absl_obj = db.get('account.bank.statement.line')

        st_move = []
        for x in absl_obj.browse(st_line_ids):
            self.assert_(x.reconciled, 'St Line %s not reconciled, register %s' % (x.sequence_for_reference, x.statement_id.name))
            st_move.append(x.first_move_line_id.move_id.id)

        invoices_move_ids = self.get_move_id_from_invoices(db, invoice_ids)
        self.check_posted_reconciled(db, invoices_move_ids)

        for x in db.get('account.invoice').read(invoice_ids, ['name', 'state']):
            self.assert_(x['state'] == 'paid', 'Invoice %s not paid' % (x['name'],))

        self.check_posted_reconciled(db, st_move)
        return st_move + invoices_move_ids

    def test_05_invoices_import_1_invoice(self):
        absl_obj = self.p1.get('account.bank.statement.line')
        new_invoices = self.create_invoices(self.p1, [130])
        st1 = self.pending_payment(self.p1, new_invoices)
        absl_obj.posting(st1, 'hard')
        self.check_local_instance(self.p1, st1, new_invoices)

    def test_10_invoices_import_in_register_max_min(self):
        absl_obj = self.p1.get('account.bank.statement.line')
        new_invoices = self.create_invoices(self.p1, [130, 100])
        st1 = self.pending_payment(self.p1, new_invoices[0], 0.8)
        st2 = self.pending_payment(self.p1, new_invoices)
        absl_obj.posting(st1, 'hard')
        absl_obj.posting(st2, 'hard')
        self.check_local_instance(self.p1, st1+st2, new_invoices)

    def test_20_invoices_import_in_register_min_max(self):
        absl_obj = self.p1.get('account.bank.statement.line')
        new_invoices = self.create_invoices(self.p1, [30, 100])
        st1 = self.pending_payment(self.p1, new_invoices[0], 0.8)
        st2 = self.pending_payment(self.p1, new_invoices)
        absl_obj.posting(st1, 'hard')
        absl_obj.posting(st2, 'hard')
        self.check_local_instance(self.p1, st1+st2, new_invoices)

    def test_30_invoices_import_in_register_sync(self):
        absl_obj = self.p1.get('account.bank.statement.line')
        new_invoices = self.create_invoices(self.p1, [130, 100])
        st1 = self.pending_payment(self.p1, new_invoices[0], 0.8)
        st2 = self.pending_payment(self.p1, new_invoices)
        self.synchronize(self.p1)
        self.synchronize(self.c1)

        absl_obj.posting(st2, 'hard')
        absl_obj.posting(st1, 'hard')
        self.synchronize(self.p1)
        self.synchronize(self.c1)

        move_ids = self.check_local_instance(self.p1, st1+st2, new_invoices)

        # get account.move xmlid
        sdref_move = []
        for id in move_ids:
            sdref_move.append(self.p1.get('account.move').get_sd_ref(id))

        # on c1 get move id
        c1_move = []
        for id in sdref_move:
            c1_move.append(self.c1.get('account.move').find_sd_ref(id))

        self.check_posted_reconciled(self.c1, c1_move)


def get_test_class():
    return TestUS1005
