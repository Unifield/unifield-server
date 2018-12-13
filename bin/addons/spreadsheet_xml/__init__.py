# -*- coding: utf-8 -*-
##############################################################################

# The etree lib uses XML 1.0 whereas the files made by Excel are valid for the XML 1.1 version
# The record and unit separators &#30; and &#31; are invalid in XML 1.0. To handle them we replace them with the following arbitrary strings.
RECORD_SEPARATOR = 'ODI2NTg3N2VkMTFlM2RjMmU2MzFlM2NkMmEzM'
UNIT_SEPARATOR = '78hHYBWZnwnPWOXGa6Du3Y28BmwSCVu4PlYDM'

import spreadsheet_xml
import spreadsheet_xml_write
