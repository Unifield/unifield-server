# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP SA (<http://openerp.com>).
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

import os
import sys
from setuptools import setup
import py2exe; assert py2exe

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from setup_py2exe_custom import custom_py2exe

setup(service=["OpenERPWebService"],
      cmdclass={'py2exe': custom_py2exe},
      options={"py2exe":{"excludes":["Tkconstants","Tkinter","tcl",
                                     "_imagingtk","PIL._imagingtk",
                                     "ImageTk", "PIL.ImageTk",
                                     "FixTk"],
                         "ascii": True,  # do not need encodings
                         "collected_libs_dir": "libs",
                         "skip_archive": 1,
                         "bundle_files": 3, 
                         "optimize": 0,
                         "compressed": 0,
                         "dll_excludes": [ 'w9xpopen.exe' ],
                         }})

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

