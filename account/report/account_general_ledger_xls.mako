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
</Styles>
<Worksheet ss:Name="Sheet">
<%
    max = 11
    if data['model'] == 'account.account':
        header_company_or_chart_of_account = 'Company'
    else:
        header_company_or_chart_of_account = 'Chart of Account'
    journals = ', '.join([ lt or '' for lt in get_journal(data) ])
    display_account = (data['form']['display_account']=='bal_all' and 'All') or (data['form']['display_account']=='bal_movement' and 'With movements') or 'With balance is not equal to 0'
    filter = get_filter(data)
    if filter:
        if filter == 'Date':
            filter = "%s - %s" % (formatLang(get_start_date(data),date=True),
                formatLang(get_end_date(data),date=True), )
        elif filter == 'Periods':
            filter = "%s - %s" % (get_start_period(data),
                get_end_period(data), )
    output_currency_code = get_output_currency_code(data)
    if not output_currency_code:
        output_currency_code = ''
%>
<Table ss:ExpandedColumnCount="${max}" ss:ExpandedRowCount="1" x:FullColumns="1"
x:FullRows="1">
% for x in range(0,max):
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">${header_company_or_chart_of_account}</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Fiscal Year</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Journals</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Display Account</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Filter By</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Entries Sorted By</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Target Moves</Data></Cell>
<Cell ss:StyleID="ssH"></Cell>
<Cell ss:StyleID="ssH"></Cell>
<Cell ss:StyleID="ssH"></Cell>
<Cell ss:StyleID="ssH"></Cell>
</Row>
% for a in objects:
<Row>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(get_account(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(get_fiscalyear(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(journals or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(display_account or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(filter or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(get_sortby(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(get_target_move(data) or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder"></Cell>
<Cell ss:StyleID="ssBorder"></Cell>
<Cell ss:StyleID="ssBorder"></Cell>
<Cell ss:StyleID="ssBorder"></Cell>
</Row>
<Row>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
</Row>

<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Date</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">JRNL</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Partner</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Ref</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Move</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Entry Label</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Counterpart</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Debit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Credit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Balance</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Currency</Data></Cell>
</Row>
% for o in get_children_accounts(a):
<Row>
<Cell ss:StyleID="ssBorder">
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(o.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(o.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
</Cell>
<Cell ss:StyleID="ssBorder">
</Cell>
<Cell ss:StyleID="ssBorder">
</Cell>
<Cell ss:StyleID="ssBorder">
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${formatLang(sum_debit_account(o), digits=get_digits(dp='Account'))}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${formatLang(sum_credit_account(o), digits=get_digits(dp='Account'))}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${formatLang(sum_balance_account(o), digits=get_digits(dp='Account'))}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${output_currency_code}</Data>
</Cell>
</Row>

% for line in lines(o):
<Row>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(formatLang(line['ldate'],date=True)) or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(line['lcode'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(line['partner_name'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(line['lref'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(line['move'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${(line['lname'] or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${strip_name(line['line_corresp'].replace(', ',','),25)}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${formatLang(line['debit'], digits=get_digits(dp='Account'))}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${formatLang(line['credit'], digits=get_digits(dp='Account'))}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${formatLang(line['progress'], digits=get_digits(dp='Account'))}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">${((company.currency_id and company.currency_id.name) or '')|x}</Data>
</Cell>
</Row>
% endfor

% endfor
% endfor
</Table>
<AutoFilter x:Range="R1C1:R1C18" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
</Worksheet>
</Workbook>
