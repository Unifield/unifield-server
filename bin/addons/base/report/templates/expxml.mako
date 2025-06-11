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
<Style ss:ID="sInteger">
<NumberFormat ss:Format="#,##0"/>
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="sFloat">
<NumberFormat ss:Format="Standard"/>
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="sFloat3">
<NumberFormat ss:Format="#,##0.000"/>
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="sFloat4">
<NumberFormat ss:Format="#,##0.0000"/>
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="sFloat5">
<NumberFormat ss:Format="#,##0.00000"/>
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
<Table>
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
     % elif d and isDate(d):
        <Cell ss:StyleID="sShortDate">
        <Data ss:Type="DateTime">${d}T00:00:00.000</Data>
     % elif d and isDate(d, date_format='%Y-%m-%d %H:%M:%S'):
        <Cell ss:StyleID="sDate">
        <Data ss:Type="DateTime">${d.replace(' ','T')}.000</Data>
     % elif d and isDate(d, date_format='%Y-%m-%d %H:%M:%S.%f'):
        <Cell ss:StyleID="sDate">
        <Data ss:Type="DateTime">${d.replace(' ','T')}</Data>
     % elif d and re.match(r'^-?[0-9]+$', d):
        <Cell ss:StyleID="sInteger">
        <Data ss:Type="Number">${d}</Data>
     % elif d and re.match(r'^-?[0-9]+\.?[0-9]*$', d):
        <% match = re.match(r'^-?[0-9]+\.?([0-9]*)$', d) if d else False %>
        <% digits = '' %>
        % if match.group(1) and len(match.group(1)) > 2 and len(match.group(1)) < 6:
            <% digits = len(match.group(1)) %>
        % endif
        <Cell ss:StyleID="sFloat${digits}">
        <Data ss:Type="Number">${d}</Data>
     % else:
        <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${d or '' | x}</Data>
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
