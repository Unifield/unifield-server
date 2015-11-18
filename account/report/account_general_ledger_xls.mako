<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${get_title()|x}</Title>
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
<Style ss:ID="ssBorderColored1">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
##<Interior ss:Color="#3498db" ss:Pattern="Solid" />
<Font ss:Bold="1" />
</Style>
<Style ss:ID="ssBorderColored2">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
##  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
##  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
##<Interior ss:Color="#cde1f0" ss:Pattern="Solid" />
</Style>
<Style ss:ID="ssBorderColored2Right">
<Alignment ss:Vertical="Center" ss:Horizontal="Right"/>
<Borders>
##  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
##  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
##<Interior ss:Color="#cde1f0" ss:Pattern="Solid" />
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
<Style ss:ID="ssNumberColored1">
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="#,##0.00"/>
##<Interior ss:Color="#3498db" ss:Pattern="Solid" />
<Font ss:Bold="1" />
</Style>
<Style ss:ID="ssNumberColored2">
<Borders>
##  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
##  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="#,##0.00"/>
##<Interior ss:Color="#cde1f0" ss:Pattern="Solid" />
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
<Style ss:ID="ssAccountLineColored1">
<Alignment ss:Bottom="Top" ss:WrapText="1"/>
<Font ss:Size="8"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
##<Interior ss:Color="#3498db" ss:Pattern="Solid" />
</Style>
<Style ss:ID="ssAccountLineColored2">
<Alignment ss:Bottom="Top" ss:WrapText="1"/>
<Font ss:Size="8" />
<Borders>
##  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
##  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
##<Interior ss:Color="#cde1f0" ss:Pattern="Solid" />
</Style>
<Style ss:ID="ssAccountLineNoWrap">
<Alignment ss:Bottom="Top"/>
<Font ss:Size="8"/>
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
    col_count = 9
    if data['model'] == 'account.account':
        header_company_or_chart_of_account = 'Company'
    else:
        header_company_or_chart_of_account = 'Chart of Account'
    display_account = (data['form']['display_account']=='bal_all' and 'All') or (data['form']['display_account']=='bal_movement' and 'With movements') or 'With balance is not equal to 0'
%>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
% if get_show_move_lines():
<Column ss:AutoFitWidth="1" ss:Width="300" />
% endif
% if not get_show_move_lines():
<Column ss:AutoFitWidth="1" ss:Width="150" />
% endif
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Column ss:AutoFitWidth="1" ss:Width="64" />
<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${header_company_or_chart_of_account}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Fiscal Year</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Journals</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Display</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Filter By ${(get_filter(data) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Target Moves</Data></Cell>
<Cell ss:StyleID="ssH" ss:MergeAcross="1"><Data ss:Type="String">Proprietary Instances</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Currency</Data></Cell>
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
    <Data ss:Type="String">${(get_journals_str(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${get_display_info(data)|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_filter_info(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${(get_target_move(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader" ss:MergeAcross="1">
    <Data ss:Type="String">${(get_prop_instances(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String">${get_output_currency_code(data)}</Data>
</Cell>
</Row>
<Row>
% for x in range(col_count):
<Cell></Cell>
% endfor
</Row>
<Row>
% if get_show_move_lines():
<Cell ss:StyleID="ssH" ss:MergeAcross="1"><Data ss:Type="String">Entry Seq</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Posting Date</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Description</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Currency</Data></Cell>
% endif
% if not get_show_move_lines():
<Cell ss:StyleID="ssH"><Data ss:Type="String">Account / CCY</Data></Cell>
<Cell ss:StyleID="ssH" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Currency</Data></Cell>
% endif
<Cell ss:StyleID="ssH"><Data ss:Type="String">Debit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Credit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Booking Balance</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Balance ${get_output_currency_code(data)}</Data></Cell>
<Cell><Data ss:Type="String"></Data></Cell>
% if not get_show_move_lines():
<Cell><Data ss:Type="String"></Data></Cell>
% endif
</Row>

<%
ac_style_suffix = 'Colored1'
ccy_sub_total_style_suffix = 'Colored2'
ccy_sub_total_style_right_suffix = 'Right'
%>

% for o in get_children_accounts(a):
<Row>
<Cell ss:StyleID="ssBorder${ac_style_suffix}">
    <Data ss:Type="String">${(o.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder${ac_style_suffix}" ss:MergeAcross="2">
    <Data ss:Type="String">${(o.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder${ac_style_suffix}">
    <Data ss:Type="String">${get_output_currency_code(data)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ac_style_suffix}">
    <Data ss:Type="Number">${sum_debit_account(o)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ac_style_suffix}">
    <Data ss:Type="Number">${sum_credit_account(o)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ac_style_suffix}">
    <Data ss:Type="Number">${sum_balance_account(o)}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ac_style_suffix}">
    <Data ss:Type="Number">${sum_balance_account(o)}</Data>
</Cell>
</Row>

% for line in lines(o):
<Row>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String"></Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${(line['move'] or '' or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${(formatLang(line['ldate'],date=True)) or ''}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNoWrap">
    <Data ss:Type="String">${(line['lname'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${(line['currency_name'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="Number">${get_line_debit(line, booking=True)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="Number">${get_line_credit(line, booking=True)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="Number">${get_line_balance(line, booking=True)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="Number">${get_line_balance(line, booking=False)}</Data>
</Cell>
</Row>
% endfor

% for c in get_currencies(o):
<%
debit = sum_debit_account(o, ccy=c, booking=True)
credit = sum_credit_account(o, ccy=c, booking=True)
bal = sum_balance_account(o, ccy=c, booking=True)
show_line = debit or credit or bal
%>
% if show_line:
<Row>
<Cell ss:StyleID="ssBorder${ccy_sub_total_style_suffix}${ccy_sub_total_style_right_suffix}" ss:MergeAcross="3">
    <Data ss:Type="String">${(o.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine${ccy_sub_total_style_suffix}">
    <Data ss:Type="String">${(c.name or c.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ccy_sub_total_style_suffix}">
    <Data ss:Type="Number">${debit}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ccy_sub_total_style_suffix}">
    <Data ss:Type="Number">${credit}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ccy_sub_total_style_suffix}">
    <Data ss:Type="Number">${bal}</Data>
</Cell>
<Cell ss:StyleID="ssNumber${ccy_sub_total_style_suffix}">
    <Data ss:Type="Number">${sum_balance_account(o, ccy=c, booking=False)}</Data>
</Cell>
</Row>
% endif
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
