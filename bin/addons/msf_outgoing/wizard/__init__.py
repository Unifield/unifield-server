# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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

from . import picking_processor
from . import incoming_shipment_processor
from . import change_product_move_processor
from . import split_move_processor
from . import internal_move_processor
from . import outgoing_delivery_processor
from . import ppl_processor
from . import return_ppl_processor
from . import return_shipment_processor
from . import return_pack_shipment_processor
from . import shipment_processor
from . import split_memory_move
from . import check_ppl_integrity
from . import ppl_set_pack_on_lines
from . import shipment_parcel_selection
