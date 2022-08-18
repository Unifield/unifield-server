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
    <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
    <NumberFormat ss:Format="Short Date"/>
</Style>
<Style ss:ID="propinstance">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
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
    <Cell ss:StyleID="title"><Data ss:Type="String">${_t(get_title()).upper()}</Data></Cell>
    <Cell></Cell>
    <Cell><Data ss:Type="String">${_('Report Date')}:</Data></Cell>
    <Cell ss:StyleID="docdate"><Data ss:Type="String">${(data.get('reportdate', False)) or ''|x}</Data></Cell>
</Row>
<Row ss:AutoFitHeight="0" ss:Height="13.5"/>
<Row>
    <Cell><Data ss:Type="String">${_('Prop. Instance export')}: </Data></Cell>
    <Cell ss:StyleID="propinstance"><Data ss:Type="String">${(company.instance_id and company.instance_id.code or '')|x}</Data></Cell>
    <Cell><Data ss:Type="String">${_('Entry status')}: </Data></Cell>
    <Cell ss:StyleID="propinstance"><Data ss:Type="String">${(data.get('entry_status', False) or '')|x}</Data></Cell>
    <Cell ss:StyleID="docdate"><Data ss:Type="String">${_('from ')} ${(data.get('period_from', False) or (data.get('date_from', False)) or '')|x}</Data></Cell>
    <Cell ss:StyleID="propinstance"><Data ss:Type="String">${_('Filter used: ')}${(data.get('filter_used', False) or '')|x}</Data></Cell>
</Row>
<Row>
    <Cell><Data ss:Type="String">${_('Prop. Instances selected')}: </Data></Cell>
    <Cell ss:StyleID="propinstance"><Data ss:Type="String">${(data.get('selected_instances', False) or '')|x}</Data></Cell>
    <Cell><Data ss:Type="String">${_('Fiscal year')}: </Data></Cell>
    <Cell ss:StyleID="propinstance"><Data ss:Type="String">${(data.get('selected_fisc', False) or '')|x}</Data></Cell>
    <Cell ss:StyleID="docdate"><Data ss:Type="String">${_('to ')} ${(data.get('period_to', False) or (data.get('date_to', False)) or '')|x}</Data></Cell>
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
    % if cell == 'rec_date':
      <%
      reconcile_ref = result[0]
      reconcile_date = get_reconcile_date(reconcile_ref)
      %>
      % if reconcile_date:
        <Cell ss:StyleID="sShortDate"><Data ss:Type="DateTime">${reconcile_date|n}T00:00:00.000</Data></Cell>
      % else:
        <Cell ss:StyleID="ssBorder"></Cell>
      % endif
    % elif isinstance(cell, (int, float)):
      <Cell ss:StyleID="ssBorder"><Data ss:Type="Number">${cell}</Data></Cell>
    % else:
      <Cell ss:StyleID="ssBorder"><Data ss:Type="String">${cell|x}</Data></Cell>
    % endif
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
