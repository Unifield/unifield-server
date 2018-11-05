<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_t(get_title())|x}</Title>
</DocumentProperties>
<Styles>
<Style ss:ID="Default" ss:Name="Normal">
    <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
</Style>
<Style ss:ID="ssH">
<Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
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
<Style ss:ID="title">
    <Font ss:FontName="Arial" x:Family="Swiss" ss:Bold="1"/>
</Style>
<Style ss:ID="docdate">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <NumberFormat ss:Format="Short Date"/>
</Style>
<Style ss:ID="propinstance">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
</Style>
</Styles>
<Worksheet ss:Name="${sheet_name(_t(get_title()))}">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Column ss:AutoFitWidth="1" ss:Width="150" />
<Row>
    <Cell ss:StyleID="title" ss:MergeAcross="5"><Data ss:Type="String">${_t(get_title()).upper()}</Data></Cell>
</Row>
<Row ss:AutoFitHeight="0" ss:Height="13.5"/>
<Row>
    <Cell><Data ss:Type="String">${_('Prop. Instance')}: </Data></Cell>
    <Cell ss:StyleID="propinstance"><Data ss:Type="String">${(company.instance_id and company.instance_id.code or '')|x}</Data></Cell>
</Row>
<Row>
    <Cell><Data ss:Type="String">${_('Report Date')}:</Data></Cell>
    <Cell ss:StyleID="docdate"><Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data></Cell>
</Row>
<Row />
<Row />
% for check in list_checks():
<Row>
<Cell ss:StyleID="ssH" ss:MergeAcross="${len(check.get('headers', 1))-1}"><Data ss:Type="String">${_t(check['title'])|x}</Data></Cell>
</Row>
<Row>
% for header in check['headers']:
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_t(header)|x}</Data></Cell>
% endfor
</Row>
% for result in get_results(check.get('query'), check.get('ref')):
<Row>
  % for cell in result:
  <Cell ss:StyleID="ssBorder">
    % if isinstance(cell, (int, float, long)):
    <Data ss:Type="Number">${cell}</Data>
    % else:
    <Data ss:Type="String">${cell|x}</Data>
    % endif
  </Cell>
  %endfor
</Row>
% endfor
<Row />
<Row />
% endfor /* list_checks
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
<PageSetup>
<Layout x:Orientation="Landscape"/>
<Header x:Margin="0.51181102362204722"/>
<Footer x:Margin="0.51181102362204722"/>
<PageMargins x:Bottom="0.98425196850393704" x:Left="0.78740157480314965"
x:Right="0.78740157480314965" x:Top="0.98425196850393704"/>
</PageSetup>
<FitToPage/>
<Print>
<FitHeight>0</FitHeight>
</Print>
<Selected/>
<ProtectObjects>False</ProtectObjects>
<ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</Worksheet>
</Workbook>
