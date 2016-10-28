<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${get_title()}</Title>
</DocumentProperties>
<Styles>
<Style ss:ID="ssH">
<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorder">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="sShortDate">
    <NumberFormat ss:Format="Short Date"/>
    <Alignment ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
</Style>
<Style ss:ID="sDate">
    <NumberFormat ss:Format="General Date"/>
    <Alignment ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
</Style>
</Styles>
<Worksheet ss:Name="Data Integrity">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
% for check in list_checks():
<Row>
<Cell ss:StyleID="ssH" ss:MergeAcross="${len(check.get('headers', 1))-1}"><Data ss:Type="String">${check['title']}</Data></Cell>
</Row>
<Row>
% for header in check['headers']:
<Cell ss:StyleID="ssH"><Data ss:Type="String">${header}</Data></Cell>
% endfor
</Row>
% for result in get_results(check.get('query')):
<Row>
  % for cell in result:
  <Cell ss:StyleID="ssBorder">
    % if isinstance(cell, (int, float, long)):
    <Data ss:Type="Number">${cell}</Data>
    % else:
    <Data ss:Type="String">${cell}</Data>
    % endif
  </Cell>
  %endfor
</Row>
% endfor
<Row />
<Row />
% endfor /* list_checks
</Table>
</Worksheet>
</Workbook>
