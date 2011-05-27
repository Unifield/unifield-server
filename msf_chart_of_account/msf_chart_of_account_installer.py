# -*- coding: utf-8 -*-

from osv import fields, osv
import tools
from os.path import join as opj

class msf_chart_of_account_installer(osv.osv_memory):
    _name = 'msf_chart_of_account.installer'
    _inherit = 'res.config'
    _columns = {
        'create': fields.boolean('Create Journals'),
    }

    _defaults = {
        'create': True
    }

    def execute(self, cr, uid, ids, context=None):
        res = self.read(cr, uid, ids)
        if res and res[0] and res[0]['create']:
            fp = tools.file_open(opj('msf_chart_of_account', 'journal_data.xml'))
            tools.convert_xml_import(cr, 'msf_chart_of_account', fp, {}, 'init', True, None)
            fp.close()
        return {}

msf_chart_of_account_installer()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

