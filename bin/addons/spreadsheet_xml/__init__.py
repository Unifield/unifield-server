# -*- coding: utf-8 -*-
##############################################################################

# The etree lib uses XML 1.0 whereas the files made by Excel are valid for the XML 1.1 version
# To handle the characters only valid in XML 1.1 we use the following arbitrary string.
SPECIAL_CHAR = '78hHYBWZnwnPWOXGa6Du3Y28BmwSCVu4PlYDM'

from . import spreadsheet_xml
from . import spreadsheet_xml_write
from . import xlsx_write

