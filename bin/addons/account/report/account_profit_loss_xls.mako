<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_("Profit And Loss")}</Title>
</DocumentProperties>
<Styles>

<Style ss:ID="ssCell">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
</Style>
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
<Style ss:ID="ssNumber">
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssHeader">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssAccountLine">
<Alignment ss:Bottom="Top" ss:WrapText="1"/>
<Font ss:Size="8"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssAccountLineNumber">
<Alignment ss:Horizontal="Right" ss:Vertical="Bottom" ss:WrapText="1"/>
<Font ss:Size="8"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssAccountLineStrong">
<Alignment ss:Bottom="Top" ss:WrapText="1"/>
<Font ss:Size="8" ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssAccountLineNumberStrong">
<Alignment ss:Horizontal="Right" ss:Vertical="Bottom" ss:WrapText="1"/>
<Font ss:Size="8" ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="#,##0.00"/>
</Style>

</Styles>

<Worksheet ss:Name="Sheet">
<%
    col_count = 6
    get_data(data)  # init data
%>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="190" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="190" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Chart of Account")}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Fiscal Year")}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Display")}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Filter By")} ${(get_filter_name(data)!=_('No Filter') and _(get_filter_name(data)) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Proprietary Instances")}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Target Moves")}</Data></Cell>
</Row>

<Row>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_account(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_fiscalyear(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${get_display_info(data)|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_filter_info(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_prop_instances(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_target_move(data) or '')|x}</Data>
</Cell>
</Row>

<Row>
% for x in range(col_count):
<Cell></Cell>
% endfor
</Row>

<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Code</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Expense")}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Balance</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Code</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${_("Income")}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Balance</Data></Cell>
</Row>

## get_lines(): *1 keys: income, other expense
% for o in get_lines():
<Row>
## expense
<%
strong = o.get('level', False) and o['level'] < 4 and 'Strong' or ''
%>
<Cell ss:StyleID="ssAccountLine${strong}"><Data ss:Type="String">${(o.get('code', False) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLine${strong}"><Data ss:Type="String">${(o.get('name', False) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLineNumber${strong}"><Data ss:Type="Number">${(o.get('balance', False) or 0.0)}</Data></Cell>
## income
<%
strong = o.get('level1', False) and o['level1'] < 4 and 'Strong' or ''
%>
<Cell ss:StyleID="ssAccountLine${strong}"><Data ss:Type="String">${(o.get('code1', False) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLine${strong}"><Data ss:Type="String">${(o.get('name1', False) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLineNumber${strong}"><Data ss:Type="Number">${(o.get('balance1', False) or 0.0)}</Data></Cell>
</Row>
% endfor

<Row>
<Cell ss:StyleID="ssAccountLineStrong"><Data ss:Type="String">Balance ${company.currency_id.symbol or ''|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLineStrong"><Data ss:Type="String"></Data></Cell>
<Cell ss:StyleID="ssAccountLineNumberStrong"><Data ss:Type="Number">${sum_dr()}</Data></Cell>
<Cell ss:StyleID="ssAccountLineStrong"><Data ss:Type="String">Balance ${company.currency_id.symbol or ''|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLineStrong"><Data ss:Type="String"></Data></Cell>
<Cell ss:StyleID="ssAccountLineNumberStrong"><Data ss:Type="Number">${sum_cr()}</Data></Cell>
</Row>

% if final_result()['type'] and final_result()['type'] == 'Net Loss':
<Row>
<Cell ss:StyleID="ssAccountLineStrong" ss:MergeAcross="3"><Data ss:Type="String"></Data></Cell>
<Cell ss:StyleID="ssAccountLineStrong"><Data ss:Type="String">Net Loss ${company.currency_id.symbol or ''|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLineNumberStrong"><Data ss:Type="Number">${final_result()['balance']}</Data></Cell>
</Row>
% endif
% if final_result()['type'] and final_result()['type'] == 'Net Profit':
<Row>
<Cell ss:StyleID="ssAccountLineStrong"><Data ss:Type="String"></Data></Cell>
<Cell ss:StyleID="ssAccountLineStrong"><Data ss:Type="String">Net Profit ${company.currency_id.symbol or ''|x}</Data></Cell>
<Cell ss:StyleID="ssAccountLineNumberStrong"><Data ss:Type="Number">${final_result()['balance']}</Data></Cell>
<Cell ss:StyleID="ssAccountLineStrong" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
</Row>
% endif

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14Profit And Loss"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
   <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <Panes>
    <Pane>
     <Number>3</Number>
     <ActiveRow>17</ActiveRow>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</Worksheet>
</Workbook>
