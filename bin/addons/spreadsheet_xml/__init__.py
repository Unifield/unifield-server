# -*- coding: utf-8 -*-
##############################################################################

# The etree lib uses XML 1.0 whereas the files made by Excel are valid for the XML 1.1 version
# The unit separator &#31; is invalid in XML 1.0. To handle it we replace it with the following arbitrary string.
UNIT_SEPARATOR = '78hHYBWZnwnPWOXGa6Du3Y28BmwSCVu4PlYDM'

import spreadsheet_xml
import spreadsheet_xml_write
