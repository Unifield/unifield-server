<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>Local Expenses</Title>
</DocumentProperties>
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
    nb_of_rows = 2
    nb_of_columns = 3
    month_list = []
    if data and data.get('form'):
        if data.get('form').get('breakdown') and data.get('form').get('breakdown') == 'month':
            nb_of_columns = 3 + data.get('form').get('month_stop')
            month_list = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][0:data.get('form').get('month_stop')]
        if data.get('form').get('result_lines'):
            nb_of_rows = 2 + len(data.get('form').get('result_lines'))
%>
<Table ss:ExpandedColumnCount="${nb_of_rows}" ss:ExpandedRowCount="${nb_of_columns}" x:FullColumns="1"
x:FullRows="1">
% for x in range(0,nb_of_columns):
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
<Row>
<Cell ss:StyleID="ssBorderLeft"><Data ss:Type="String">Account code</Data></Cell>
<Cell ss:StyleID="ssBorderLeft"><Data ss:Type="String">Account name</Data></Cell>
% for month in month_list:
    <Cell ss:StyleID="ssBorderCenter"><Data ss:Type="String">${month}</Data></Cell>
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
<Cell ss:StyleID="ssBoldLeft">
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
<AutoFilter x:Range="R1C1:R1C${nb_of_columns}" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
</Worksheet>
</Workbook>
