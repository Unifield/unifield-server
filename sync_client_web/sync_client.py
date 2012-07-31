# -*- coding: utf-8 -*-
from osv import fields, osv

class company_test(osv.osv):
    _inherit = 'res.company'
    _columns = {
        'pad_index': fields.char('Pad root URL', size=64, required=True,
                                 help="The root URL of the company's pad "
                                      "instance"),
    }

company_test()
