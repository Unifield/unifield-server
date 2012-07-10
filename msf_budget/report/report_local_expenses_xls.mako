<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>MSFUser</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2012-06-18T15:46:09Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
</DocumentProperties>
<ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>13170</WindowHeight>
  <WindowWidth>19020</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>60</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
</ExcelWorkbook>
<Styles>
<Style ss:ID="ssBoldLeft">
<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBoldCenter">
<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBoldRight">
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderLeft">
<Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderCenter">
<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderRight">
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
</Styles>
<Worksheet ss:Name="Sheet">
<%
    nb_of_columns = 3
    month_list = []
    if data and data.get('form'):
        if data.get('form').get('breakdown') and data.get('form').get('breakdown') == 'month':
            nb_of_columns = 3 + data.get('form').get('month_stop')
            month_list = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][0:data.get('form').get('month_stop')]
%>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="120" />
% for x in range(2,nb_of_columns):
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
% if data.get('form').get('header'):
% for line in data.get('form').get('header'):
<Row>
% for value in line:
<Cell ss:StyleID="ssBoldLeft">
   <Data ss:Type="String">${value}</Data>
</Cell>
% endfor
</Row>
% endfor
<Row/>
% endif
<Row>
<Cell ss:StyleID="ssBoldCenter"><Data ss:Type="String">Account code</Data></Cell>
<Cell ss:StyleID="ssBoldCenter"><Data ss:Type="String">Account name</Data></Cell>
% for month in month_list:
    <Cell ss:StyleID="ssBoldCenter"><Data ss:Type="String">${month}</Data></Cell>
% endfor
<Cell ss:StyleID="ssBoldCenter"><Data ss:Type="String">Total</Data></Cell>
</Row>
% if data.get('form').get('report_lines'):
% for line in data.get('form').get('report_lines'):
<Row>
% for value in line[0:2]:
<Cell ss:StyleID="ssBorderCenter">
   <Data ss:Type="String">${value}</Data>
</Cell>
% endfor
% for value in line[2:-1]:
<Cell ss:StyleID="ssBorderRight">
   <Data ss:Type="Number">${value}</Data>
</Cell>
% endfor
<Cell ss:StyleID="ssBoldRight">
   <Data ss:Type="Number">${line[-1]}</Data>
</Cell>
</Row>
% endfor
% endif
% if data.get('form').get('total_line'):
<Row>
% for total_value in data.get('form').get('total_line')[0:2]:
<Cell ss:StyleID="ssBoldCenter">
   <Data ss:Type="String">${total_value}</Data>
</Cell>
% endfor
% for total_value in data.get('form').get('total_line')[2:]:
<Cell ss:StyleID="ssBoldRight">
   <Data ss:Type="Number">${total_value}</Data>
</Cell>
% endfor
</Row>
% endif
</Table>
</Worksheet>
</Workbook>
