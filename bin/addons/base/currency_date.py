# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2019 MSF, TeMPO Consulting.
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

BEGINNING = '2020-01-01'


def get_date_type(self, cr):
    """
    Returns "document" or "posting" corresponding to the date type used for functional amount computation (depending on the OC)
    """
    param_obj = self.pool.get('ir.config_parameter')
    date_type = param_obj.get_param(cr, 1, 'currency_date.type')
    if not date_type:
        oc_sql = "SELECT oc FROM sync_client_entity LIMIT 1;"
        cr.execute(oc_sql)
        oc = cr.fetchone()[0]
        if oc in ('ocb', 'ocg'):
            date_type = 'document'
        else:
            date_type = 'posting'
        param_obj.set_param(cr, 1, 'currency_date.type', date_type)
    return date_type


def get_date(self, cr, document_date, posting_date, source_date=None):
    """
    Returns the date in parameter that will be used for functional amount computation
    """
    if source_date:
        currency_date = source_date
    elif not posting_date or posting_date < BEGINNING:  # returns True if the posting date is False
        currency_date = posting_date
    else:
        currency_date = get_date_type(self, cr) == 'posting' and posting_date or document_date  # can return an empty doc date
    return currency_date


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
