<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>General Ledger</Title>
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
<Style ss:ID="ssBorderDate">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="Short Date" />
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
<Font ss:Size="8" ss:Italic="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssAccountLine2">
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
</Styles>
<Worksheet ss:Name="Sheet">
<%
    max = 11
    if data['model'] == 'account.account':
        header_company_or_chart_of_account = 'Company'
    else:
        header_company_or_chart_of_account = 'Chart of Account'
    if 'all_journals' in data['form']:
       journals = 'All Journals'
    else:
       journals = ', '.join([lt or '' for lt in get_journal(data)])
    display_account = (data['form']['display_account']=='bal_all' and 'All') or (data['form']['display_account']=='bal_movement' and 'With movements') or 'With balance is not equal to 0'
    prop_instances_list = get_prop_instances(data)
    if prop_instances_list:
        prop_instances = ', '.join([lt or '' for lt in get_prop_instances(data)])
    else:
        prop_instances = 'All Instances'
%>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${header_company_or_chart_of_account}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Fiscal Year</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Journals</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Display</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Filter By ${(get_filter(data) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Entries Sorted By</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Target Moves</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Proprietary Instances</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Currency</Data></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
</Row>
% for a in objects:
<Row>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_account(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_fiscalyear(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(journals or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${get_display_info(data)|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_filter_info(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_sortby(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_target_move(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(prop_instances or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${get_output_currency_code(data)}</Data>
</Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
</Row>
<Row>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
<Cell></Cell>
</Row>
<Row>
<Row>
% if get_show_move_lines():
<Cell ss:StyleID="ssH"><Data ss:Type="String">Entry Seq</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Posting Date</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Description</Data></Cell>
% endif
% if not get_show_move_lines():
<Cell ss:StyleID="ssH"><Data ss:Type="String">CCY / Account</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String"></Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String"></Data></Cell>
% endif
<Cell ss:StyleID="ssH"><Data ss:Type="String">Debit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Credit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Balance ${get_output_currency_code(data)}</Data></Cell>
</Row>
% for c in get_currencies():
<Row>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(c.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder" ss:MergeAcross="2">
    <Data ss:Type="String"></Data>
</Cell>
<Cell ss:StyleID="ssNumber">
    <Data ss:Type="Number">${sum_debit_account(a, ccy=c)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
    <Data ss:Type="Number">${sum_credit_account(a, ccy=c)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
    <Data ss:Type="Number">${sum_balance_account(a, ccy=c)}</Data>
</Cell>
</Row>

% for o in get_children_accounts(a, ccy=c):
<Row>
<Cell ss:StyleID="ssBorder">
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(o.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder" ss:MergeAcross="2">
    <Data ss:Type="String">${(o.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
    <Data ss:Type="Number">${sum_debit_account(o, ccy=c)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
    <Data ss:Type="Number">${sum_credit_account(o, ccy=c)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
    <Data ss:Type="Number">${sum_balance_account(o, ccy=c)}</Data>
</Cell>
</Row>
% for line in lines(o, ccy=c):
<Row>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${(line['move'] or '' or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${(formatLang(line['ldate'],date=True)) or ''}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${(line['move'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="Number">${get_line_debit(line)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="Number">${get_line_credit(line)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="Number">${get_line_balance(line)}</Data>
</Cell>
</Row>
% endfor
% endfor
% endfor
% endfor
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14General Ledger"/>
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
