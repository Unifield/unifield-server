# -*- coding: utf-8 -*-

from osv import fields, osv
import tools
from os.path import join as opj

class msf_chart_of_account_installer(osv.osv_memory):
    _name = 'msf_chart_of_account.installer'
    _inherit = 'res.config'
    _columns = {
        'create': fields.boolean('Create Journals'),
        'import_invoice_default_account': fields.many2one('account.account', string="Re-billing Inter-section account"),
        'counterpart_hq_entries_default_account': fields.many2one('account.account', string="Default counterpart", domain="[('type', '!=', 'view')]", 
            help="Account that will be used as counterpart for HQ Validated Entries.")
    }
    
    def get_inter(self, cr, uid, *a, **b):
        try:
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_chart_of_account', '1404')[1]
        except ValueError:
            return False

    def get_counterpart(self, cr, uid, *a, **b):
        try:
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_chart_of_account', '4000')[1]
        except ValueError:
            return False

    _defaults = {
        'create': True,
        'import_invoice_default_account': get_inter,
        'counterpart_hq_entries_default_account': get_counterpart,
    }

    def execute(self, cr, uid, ids, context=None):
        res = self.read(cr, uid, ids)
        if res and res[0]:
            if res[0]['create']:
                fp = tools.file_open(opj('msf_chart_of_account', 'data/journal_data.xml'))
                tools.convert_xml_import(cr, 'msf_chart_of_account', fp, {}, 'init', True, None)
                fp.close()

            if res[0]['import_invoice_default_account']:
                self.pool.get('res.users').browse(cr, uid, uid).company_id.write({'import_invoice_default_account': res[0]['import_invoice_default_account']})
            if res[0]['counterpart_hq_entries_default_account']:
                self.pool.get('res.users').browse(cr, uid, uid).company_id.write({'counterpart_hq_entries_default_account': res[0]['counterpart_hq_entries_default_account']})
        return {}

msf_chart_of_account_installer()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

