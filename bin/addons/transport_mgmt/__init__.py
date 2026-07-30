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

from tools.translate import _


TRANSPORT_FEES_HELP = [
    ('transport_charges', _("""What:
Includes fees linked to non-negotiable/fixed operational charges such as loading, unloading, terminal handling, forklift use and any other mandatory 3rd party fees (with official receipts).

How:
Identify fees that neither MSF nor the transporter controls. They are imposed by authorities, non-negotiable, and operational adds-on.""")),
    ('negotiated_transport', _("""What:
Includes all fees linked to the transport rates negotiated in the MSF contract or agreed quotation with transporters.

How:
Identify the fees that MSF has under its control and useful for negotiation for future market assessments.""")),
    ('insurance', _("""What:
Includes MSF owned fees linked to mandatory insurance requirements and cargo insurance during transport.

How:
Identify if mandatory insurance obligations are being fulfilled by MSF by insuring its own cargo during transportation or by Service providers.""")),
    ('truck', _("""What:
Includes fees linked to delays in offloading and releasing cargo/truck according to agreed detention free days that lead to daily penalty fees from the transporter.

How:
Identify that the transportation management process may not be efficient especially if MSF pays huge detention expenses. It will be an indicator of point of improvement to be re-negotiated with transporter to be shared with ESCs & RSCs.""")),
    ('demurrage', _("""What:
Includes fees linked to delays in returning empty containers to the shipping line or agent at the port of entry according to demurrage free days negotiated by supplier center (eg: ESC/RSC) on behalf of the MSF country of importation.

How:
Identify that there is inefficiency in container handling or coordination process may not be efficient especially if MSF pays huge demurrage expenses. It will be an indicator of point of improvement to be shared with ESCs & RSCs.""")),
    ('freight_storage', _("""What:
Includes fees linked to storing cargo in transporter terminal or 3rd party storage facilities when it exceeds the free storage period.

How:
Identify that the transportation management process may not be efficient especially if MSF pays huge storage expenses. It will be an indicator of point of improvement.""")),
    ('container', _("""What:
Includes fees advanced to the shipping line by MSF or its appointed agent and is only reimbursed after MSF has officially returned back the container to the shipping line and obtained proof of container reception by the shipping line or its agent.

How:
Identify that the transportation management process or the appointed transporter may not be efficient. It will be an indicator of point of improvement.""")),
    ('taxes_duties_transport', _("""What:
Includes fees linked to transport-related taxes & duties such as weighbridge fees, official levies, environmental taxes and VAT when applicable.

How:
Identify all transport related expenses/taxes that MSF is not exempted from either by law or via MSF Negotiated MOU/Host country Agreement (HCA).""")),
    ('other_transport', _("""What:
Includes costs linked to any transport-related charges that do not fall within the defined categories above.

How:
Make sure you add a remark to explain why this fee is \"Other\".""")),
]

CUSTOMS_FEES_HELP = [
    ('customs_charges', _("""What:
Includes all the non-negotiable/fixed customs-related service fees such as terminal handling charges, port inspection fees, loading/unloading charges, escorts, bonded warehousing and other official port or airport charges.

How:
Identify all customs clearance expenses MSF can not negotiate or control because they are mandated by authorities, port/airport operators or shipping/airline handlers.""")),
    ('customs_clearance_srv', _("""What:
Include all the fees linked to clearance services provided by contracted service providers when fees are negotiated and not fixed by authorities.

How:
Identify all customs clearance expenses MSF pays to service providers when these services are outsourced and negotiated - usually in a MIFAT contract or via agreed quotation.""")),
    ('prearrival', _("""What:
Includes costs linked to non-negotiable/fixed fees during pre-clearance process. These fees usually official/statutory and will have official receipts.

How:
Identify all pre-arrival fees that MSF can not negotiate or control because they are fixed by authorities or infrastructure operators.""")),
    ('prearrival_srv', _("""What:
Includes fees linked to pre-arrival clearance services provided by contracted service providers or 3rd party provider when fees are negotiated and not fixed by authorities.

How:
Identify all pre-arrival expenses MSF pays to service providers when these services are outsourced and negotiated - usually in a MIFAT contract or via agreed quotation.""")),
    ('taxes_duties_customs', _("""What:
Includes statutory fees linked to customs-related taxes such as import duties, excise duties, withholding taxes, environmental taxes and VAT or sales tax paid directly for MSF cargo.

How:
Identify all direct or indirect taxes that MSF is not exempted from under the law or the MSF MOU/Host Country Agreement (HCA).""")),
    ('storage', _("""What:
Includes fees linked to storing cargo in customs-controlled terminals when customs clearance is delayed or processing exceeds the free storage period.

How:
Identify inefficiencies or delays in the importation process that may cause unnecessary storage costs. It will be an indicator of point of improvement.""")),
    ('penalty', _("""What:
Includes fees/penalties/fines imposed by customs authorities due to mistakes in the customs declaration process or any other non-compliance deemed to be caused by MSF or the appointed clearing agent.

How:
Identify non-compliance aspects either by MSF or by MSF appointed service providers during the customs clearance process. It will be an indicator of point of improvement.""")),
    ('other_customs', _("""What:
Includes costs linked to customs-related fees that do not fit within the above defined categories.

How:
Make sure you add a remark to explain why this fee is \"Other\".""")),
]

from . import wizard
from . import stock
from . import purchase
from . import product
from . import sale
from . import report
from . import transport

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
