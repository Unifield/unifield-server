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

TRANSPORT_FEES_HELP = [
    ('freight_fixed', """What:
Use this type when encoding the actual transport costs according to what is negotiated in the MSF contract or quotation agreed with the service provider / transporter.

How:
Identify all transport-related expenses that MSF is paying to transporters when they provide these transportation services to MSF. Usually negotiated and defined in the contracts (eg: MIFAT contracts)."""),
    ('freight_negotiable', """What:
Use this type when encoding sum of any official fees paid to government authorities (with official receipts) that are not part of the transport costs negotiated in the MSF contract or quotation agreed with the service provider / transporter.

How:
Identify all transport-related expenses that MSF is paying to transporters when they provide these transportation services to MSF. MSF or Transporter has no control on these fees."""),
    ('freight_return', """What:
Use this type when encoding transport costs linked to return of cargo (eg: from project back to coordination) according to what is negotiated in the MSF contract or quotation agreed with the service provider / transporter.

How:
Identify all transport-related expenses that MSF is paying to transporters when they provide these reverse logistics transportation services to MSF. Usually negotiated and defined in the contracts (eg: MIFAT contracts)."""),
    ('insurance', """What:
Any expenses on transport that are classified as insurance costs/ fees.

How:
Fees indicate if both mandatory insurance obligations are being fulfilled by MSF and the appointed transporter (MSF Due diligence) or if MSF is insuring its cargo during transportation."""),
    ('truck', """What:
For all expenses / costs paid to the transporter per day for delay of MSF offloading cargo from the truck and releasing the truck according to agreed detention free days.

How:
These are fees that can provide an indicator that the transportation management process may not be efficient especially if MSF continues to pay huge detention expenses. It will be an indicator of point of improvement in the transportation process."""),
    ('demurrage', """What:
For all expenses / costs paid to the shipping line or agent per day for delay of MSF returning the empty container back to the shipping line / port terminal according to demurrage free days negotiated by supplier center (eg: ESC/RSC) on behalf of the MSF country of importation.

How:
These are fees that can provide an indicator that the transportation management process may not be efficient especially if MSF continues to pay huge detention expenses. It will be an indicator of point of improvement in the transportation process."""),
    ('freight_storage', """What:
This applies to only fees/ expenses linked to storage costs accumulated by MSF cargo staying in a defined transporter terminal or storage facility including in the trucks or containers, etc...

How:
These are fees that can provide an indicator that the transport process / negotiated contract terms may not be efficient."""),
    ('container', """What:
This applies to expenses / fees advanced to the shipping line by MSF or its appointed agent and is only reimbursed after MSF has officially returned back the container to the shipping line and obtained proof of container reception by the shipping line or its agent.

How:
These are fees that can provide an indicator that the transport process may not be efficient or the appointed Transporter is not efficient. It will be an indicator of point of improvement in the transport management process."""),
    ('freight_load', """What:
All loading fees whether done by manual labour or fork lift charges."""),
    ('freight_unload', """What:
All unloading / offloading fees whether done by manual labour or fork lift charges"""),
    ('direct', """What:
This applies to all expenses that we can classify as official direct taxes paid to government or any official authority during cargo transportation (comes with official receipts). Infrastructure Tax, Environmental Tax, etc...

How:
Identify all transport-related expenses / taxes that MSF is not exempted from either by law or via MSF Negotiated MOU / Host country Agreement (HCA)."""),
    ('indirect', """What:
This applies to all expenses that we can classify as official non direct taxes paid to government or any official authority during cargo transportation (comes with official receipts) (eg: VAT / Sales tax on the Transporters Invoice, Weigh bridge fees, any airfreight related taxes / fees, transport levies etc...)

How:
Identify all transport-related expenses / taxes that MSF is not exempted from either by law or via MSF Negotiated MOU / Host country Agreement (HCA)."""),
    ('other', """What:
Any other freight-related fees that don't fit in any of the above defined categories**. Make sure you add a remark to explain why this fee is \"Other\""""),
]

from . import stock
from . import purchase
from . import product
from . import sale
from . import report
from . import transport

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
