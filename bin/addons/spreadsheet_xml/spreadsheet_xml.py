# -*- coding: utf-8 -*-

from lxml import etree
from mx import DateTime
from tools.translate import _
from osv import osv
import csv
from . import UNIT_SEPARATOR
import fileinput


# example to read a Excel XML file in consumption_calculation/wizard/wizard_import_rac.py
class SpreadsheetTools():
    defaultns = 'urn:schemas-microsoft-com:office:spreadsheet'
    namespaces = {'ss': defaultns}
    xa = {'namespaces': namespaces}

    def get(self, node, attr, default=None):
        return node.get(etree.QName(self.defaultns, attr), default)

class SpreadsheetCell(SpreadsheetTools):
    type = None
    data = None

    def __init__(self, node=None):
        if node is not None:
            data = node.find(etree.QName(self.defaultns, 'Data'))
            if data is not None:
                dtype = self.get(data, 'Type')
                self.data = data.text
                if dtype == 'Number':
                    if not self.data or '.' in self.data or 'E-' in self.data or 'e-' in self.data:
                        self.type = 'float'
                        self.data = float(self.data or 0.0)
                    else:
                        try:
                            self.type = 'int'
                            self.data = int(self.data)
                        except Exception as e:
                            self.type = 'int_error'
                            self.data = str(e)

                elif dtype == 'Boolean':
                    self.data = self.data in ('1', 'T', 't', 'True', 'true')
                    self.type = 'bool'
                elif dtype == 'DateTime' and self.data:
                    try:
                        self.data = DateTime.ISO.ParseDateTime(self.data)
                        self.type = 'datetime'
                    except Exception as e:
                        self.data = str(e)
                        self.type = 'datetime_error'
                elif dtype == 'String':
                    self.type = 'str'
                    if self.data:
                        self.data = self.data.replace('&#10;', "\n")

    def __str__(self):
        return "%s"%(self.data, )

    def __repr__(self):
        return "%s(<%s> %s)" % (self.__class__, self.type, self.data)


class SpreadsheetRow(SpreadsheetTools):

    def __init__(self, node):
        self.node = node
        self.cell_list = []
        self.cell_index = 0

    def __iter__(self):
        return self

    def next(self):
        return SpreadsheetRow(self.node.next())

    def len(self):
        """
            returns the num. of cells
        """
        index = 0
        for cell in self.node.xpath('ss:Cell', **self.xa):
            currindex = self.get(cell, 'Index')
            if not currindex:
                index += 1
            else:
                index = int(currindex)
            merged =  self.get(cell, 'MergeAcross', 0)
            if merged:
                index += int(merged)
        return index

    def __len__(self):
        return self.len()

    def iter_cells(self):
        index = 0
        for cell in self.node.xpath('ss:Cell', **self.xa):
            currindex = self.get(cell, 'Index')
            if not currindex:
                index += 1
            else:
                currindex = int(currindex)
                for i in xrange(index+1, currindex):
                    yield SpreadsheetCell()
                index = currindex
            merged =  self.get(cell, 'MergeAcross', 0)
            yield SpreadsheetCell(cell)
            for i in xrange(0, int(merged)):
                yield SpreadsheetCell()

    def gen_cell_list(self):
        for cell in self.iter_cells():
            self.cell_list.append(cell)

    def __getattr__(self, attr):
        if attr == 'cells':
            if not self.cell_list:
                self.gen_cell_list()
            return self.cell_list
        raise AttributeError

    def __getitem__(self, attr):
        if not self.cell_list:
            self.gen_cell_list()
        return self.cell_list[attr]

class SpreadsheetXML(SpreadsheetTools):

    def __init__(self, xmlfile=False, xmlstring=False, context=None):
        if context is None:
            context = {}
        try:
            if xmlfile:
                if context.get('from_je_import', False):
                    # replace the unit separator code by an arbitrary string (cf &#31; is invalid in XML 1.0 used by etree)
                    unit_separator_code = '&#31;'
                    for line in fileinput.input(xmlfile, inplace=1):
                        print line.replace(unit_separator_code, UNIT_SEPARATOR)
                self.xmlobj = etree.parse(xmlfile)
            else:
                self.xmlobj = etree.XML(xmlstring)
        except etree.XMLSyntaxError:
            raise osv.except_osv(_('Error'), _('Wrong format: it should be in Spreadsheet XML 2003'))

    def getWorksheets(self):
        ret = []
        for wb in self.xmlobj.xpath('//ss:Worksheet', **self.xa):
            ret.append(self.get(wb, 'Name'))
        return ret

    def getNbRows(self,worksheet=1):
        return len(self.xmlobj.xpath('//ss:Worksheet[%d]/ss:Table[1]/ss:Row' % (worksheet,), **self.xa))

    def getRows(self,worksheet=1):
        table = self.xmlobj.xpath('//ss:Worksheet[%d]/ss:Table[1]'%(worksheet, ), **self.xa)
        if not table:
            # in case no table, raise something understandable instead
            # of giving a let-me-fix
            raise osv.except_osv(_('Error'), _('File format problem: no Table found in the file, check the file format.'))
        return SpreadsheetRow(table[0].iter('{%s}Row' % self.defaultns))

    def enc(self, s):
        if isinstance(s, unicode):
            return s.encode('utf8')
        return s

    def to_csv(self, to_file=False, worksheet=1):
        if to_file:
            writer=csv.writer(to_file, 'UNIX')
        else:
            data = []
        for row in self.getRows(worksheet):
            if to_file:
                writer.writerow([self.enc(x.data) for x in row.iter_cells()])
            else:
                data.append([self.enc(x.data) for x in row.iter_cells()])
        if to_file:
            return True
        return data



if __name__=='__main__':
    spreadML = SpreadsheetXML('/mnt/Tempo/TestJFB/test_dates.xml')
    spreadML.getWorksheets()
    # Iterates through all sheets
    for ws_number in xrange(1, len(spreadML.getWorksheets())):
        rows = spreadML.getRows(ws_number)
        # ignore the 1st row
        rows.next()
        for row in rows:
            # number of cells: row.len()
            # cells can be retrieve like a list: row.cells[0] or like an iterator:
            for cell in row.iter_cells():
                print "%s |"%cell.data,
            print
            print "-"*4
