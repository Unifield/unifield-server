# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    "name" : "Account For Multicompany",
    "version" : "1.1",
    "author" : "Tiny",
    "description" : """OpenERP Stock Management module can manage multi-warehouses, multi and structured stock locations.
Thanks to the double entry management, the inventory controlling is powerful and flexible:
* Moves history and planning,
* Different inventory methods (FIFO, LIFO, ...)
* Stock valuation (standard or average price, ...)
* Robustness faced with Inventory differences
* Automatic reordering rules (stock level, JIT, ...)
* Bar code supported
* Rapid detection of mistakes through double entry system
* Traceability (upstream/downstream, production lots, serial number, ...)
    """,
    "website" : "http://www.openerp.com",
    "depends" : ['profile_indian_account'],
    "category" : "Generic Modules/account_multicompany",
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : [
                    'account_multi_company_view.xml',
                    'account_multi_report.xml'
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
