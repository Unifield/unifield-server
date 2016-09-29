<?xml version="1.0" ?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${title}</Title>
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
<NumberFormat ss:Format="Standard"/>
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
<Worksheet ss:Name="Sheet">
<Table ss:ExpandedColumnCount="${len(fields)}" ss:ExpandedRowCount="${len(result)+1}" x:FullColumns="1"
x:FullRows="1">
% for x in fields:
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
<Row>
% for header in fields:
<Cell ss:StyleID="ssH"><Data ss:Type="String">${header}</Data></Cell>
% endfor
</Row>
% for row in result:
<Row>
  % for k in row:
     <% d = '%s'%k %>
     % if d in ('True', 'False'):
       <Cell ss:StyleID="ssBorder">
        <Data ss:Type="Boolean">${d=='True' and '1' or '0'}</Data>
     % elif d and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', d):
       <Cell ss:StyleID="sShortDate">
        <Data ss:Type="DateTime">${d}T00:00:00.000</Data>
     % elif d and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$', d):
       <Cell ss:StyleID="sDate">
        <Data ss:Type="DateTime">${d.replace(' ','T')}.000</Data>
     % elif d and re.match('^-?[0-9]+\.?[0-9]*$', d):
       <Cell ss:StyleID="ssBorder">
        <Data ss:Type="Number">${d}</Data>
     % else:
       <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${d or ''}</Data>
    % endif
</Cell>
  % endfor
</Row>
% endfor
</Table>
<AutoFilter x:Range="R1C1:R1C${len(fields)}" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
</Worksheet>
</Workbook>
