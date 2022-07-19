#!/usr/bin/env python
#-*- encoding:utf-8 -*-

from osv import osv
from tools.translate import _
import time

def update_name(self, cr, uid, prefix, ret, context):
    instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
    ret['datas']['target_filename'] = '%s_%s_%s' % (prefix, instance and instance.code or '', time.strftime('%Y%m%d'))
    return ret

class account_report_general_ledger(osv.osv_memory):
    _inherit = 'account.report.general.ledger'
    _name = 'account.report.general.ledger'

    def _print_report(self, cr, uid, ids, data, context=None):
        ret = super(account_report_general_ledger, self)._print_report(cr, uid, ids, data, context)
        return update_name(self, cr, uid, _('General Ledger'), ret, context)

account_report_general_ledger()


class account_balance_report(osv.osv_memory):
    _name = 'account.balance.report'
    _inherit = 'account.balance.report'

    def _print_report(self, cr, uid, ids, data, context=None):
        ret = super(account_balance_report, self)._print_report(cr, uid, ids, data, context)
        return update_name(self, cr, uid, _('Trial Balance'), ret, context)

account_balance_report()

class account_partner_balance(osv.osv_memory):
    _name = 'account.partner.balance'
    _inherit = 'account.partner.balance'

    def _print_report(self, cr, uid, ids, data, context=None):
        ret = super(account_partner_balance, self)._print_report(cr, uid, ids, data, context)
        return update_name(self, cr, uid, _('Partner Balance'), ret, context)

account_partner_balance()

class account_partner_ledger(osv.osv_memory):
    _name = 'account.partner.ledger'
    _inherit = 'account.partner.ledger'

    def _print_report(self, cr, uid, ids, data, context=None):
        ret = super(account_partner_ledger, self)._print_report(cr, uid, ids, data, context)
        return update_name(self, cr, uid, _('Partner Ledger'), ret, context)

account_partner_ledger()


class account_employee_balance(osv.osv_memory):
    _name = 'account.employee.balance'
    _inherit = 'account.employee.balance'

    def _print_report(self, cr, uid, ids, data, context=None):
        ret = super(account_employee_balance, self)._print_report(cr, uid, ids, data, context)
        return update_name(self, cr, uid, _('Employee Balance'), ret, context)


account_employee_balance()


class account_employee_ledger(osv.osv_memory):
    _name = 'account.employee.ledger'
    _inherit = 'account.employee.ledger'

    def _print_report(self, cr, uid, ids, data, context=None):
        ret = super(account_employee_ledger, self)._print_report(cr, uid, ids, data, context)
        return update_name(self, cr, uid, _('Employee Ledger'), ret, context)


account_employee_ledger()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
