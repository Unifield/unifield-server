<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>Partner</Title>
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
<Style ss:ID="ssHeaderNumber">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="#,##0.00"/>
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
</Styles>
% for p_entries in get_partners(data):
<%
if p_entries[0].account_type == 'payable':
    worsheet_name = 'Payable Accounts'
else:
    worsheet_name = 'Receivable Accounts'
%>
<Worksheet ss:Name="${worsheet_name}">
<%
    col_count = 8
    if data['model'] == 'account.account':
        header_company_or_chart_of_account = 'Company'
    else:
        header_company_or_chart_of_account = 'Chart of Account'
    if 'all_journals' in data['form']:
       journals = 'All Journals'
    else:
       journals = ', '.join([lt or '' for lt in get_journal(data)])
    display_account = (data['form']['display_account']=='bal_all' and 'All') or (data['form']['display_account']=='bal_movement' and 'With movements') or 'With balance is not equal to 0'
%>
<Table x:FullColumns="1" x:FullRows="1">
## header (criteria)
% for x in range(0, col_count):
<Column ss:AutoFitWidth="1" ss:Width="150" />
% endfor
<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${header_company_or_chart_of_account}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Fiscal Year</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Journals</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Display Account</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Filter By ${(get_filter(data) or '')|x}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Entries Sorted By</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Target Moves</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Output Currency</Data></Cell>
</Row>
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
    <Data ss:Type="String">${(display_account or '')|x}</Data>
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
    <Data ss:Type="String">${get_output_currency_code()|x}</Data>
</Cell>
</Row>
<Row>
% for n in range(col_count):
<Cell ss:StyleID="ssHeader">
    <Data ss:Type="String"></Data>
</Cell>
% endfor
</Row>
## partner row
% for p_obj in p_entries:
<Row>
<Cell ss:StyleID="ssHeader" ss:MergeAcross="4">
    <Data ss:Type="String">${(p_obj.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssHeaderNumber">
    <Data ss:Type="String">${formatLang(p_obj.debit or 0.)}</Data>
</Cell>
<Cell ss:StyleID="ssHeaderNumber">
    <Data ss:Type="String">${formatLang(p_obj.credit or 0.)}</Data>
</Cell>
<Cell ss:StyleID="ssHeaderNumber">
    <Data ss:Type="String">${formatLang(p_obj.balance or 0.)}</Data>
</Cell>
</Row>
## account move line row
% for aml in get_partner_account_move_lines(p_entries[0].account_type, p_obj.partner_id.id, data):
<%
debit = currency_conv(aml.debit, aml.date)
credit = currency_conv(aml.credit, aml.date)
balance = debit - credit
%>
<Row>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${((aml.journal_id and aml.journal_id.code) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${((aml.move_id and aml.move_id.name) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${formatLang(aml.date, date=True)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${((aml.period_id and aml.period_id.name) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLine">
    <Data ss:Type="String">${((aml.account_id and aml.account_id.name) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="String">${formatLang(debit)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="String">${formatLang(credit)}</Data>
</Cell>
<Cell ss:StyleID="ssAccountLineNumber">
    <Data ss:Type="String">${formatLang(balance)}</Data>
</Cell>
</Row>
% endfor
<Row>
## total debit / credit / balance row
<%
debit, credit = get_partners_total_debit_credit_by_account_type(p_entries[0].account_type, data)
debit = currency_conv(debit, False)
credit = currency_conv(credit, False)
balance = debit - credit
%>
<Cell ss:StyleID="ssHeader" ss:MergeAcross="4">
    <Data ss:Type="String"></Data>
</Cell>
<Cell ss:StyleID="ssHeaderNumber">
    <Data ss:Type="String">${formatLang(debit)}</Data>
</Cell>
<Cell ss:StyleID="ssHeaderNumber">
    <Data ss:Type="String">${formatLang(credit)}</Data>
</Cell>
<Cell ss:StyleID="ssHeaderNumber">
    <Data ss:Type="String">${formatLang(balance)}</Data>
</Cell>
</Row>
% endfor
</Table>
<AutoFilter x:Range="R1C1:R1C18" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
</Worksheet>
% endfor
## endfor Worksheet
</Workbook>
