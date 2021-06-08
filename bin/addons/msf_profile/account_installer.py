# -*- coding: utf-8 -*-

from osv import fields, osv

class account_installer(osv.osv_memory):
    _name = 'account.installer'
    _inherit = 'account.installer'

    _columns = {
        'charts': fields.selection([('msf_chart_of_account', 'MSF Chart Of Account'), ('None', 'None')], 'Chart of Accounts',
                                   required=True,
                                   help="Installs localized accounting charts to match as closely as "
                                   "possible the accounting needs of your company based on your "
                                   "country."),
    }

    _defaults = {
        'charts': 'None'
    }

    def execute(self, cr, uid, ids, context=None):
        return super(account_installer, self).execute(cr, uid, ids, context)

account_installer()

