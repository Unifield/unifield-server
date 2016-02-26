# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    "name" : "Mission Stock Cron",
    "version" : "0.1",
    "author" : "TeMPO Consulting/MSF",
    "category" : "Stock",
    "description": """
        Disallow the cron of the mission stock data on runbot
        """,
    'website': 'http://www.unifield.org',
    'init_xml': [],
    "depends" : ["mission_stock"],
    'update_xml': [
    ],
    "additional_xml": [
        'mission_stock_cron_data.xml',
    ],
    "demo_xml": [],
    'test': [
    ],
    'installable': True,
}
