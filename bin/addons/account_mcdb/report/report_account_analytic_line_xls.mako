<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('Analytic Journal Items')}</Title>
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
    max = 19
    if data and data.get('context') and data.get('context').get('display_fp'):
        max = 21
%>
<Table>
% for x in range(0,max):
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
<Row>
% for header in [_('Proprietary Instance'), _('Journal Code'), _('Entry Sequence'), _('Description'), _('Ref.'), _('Document Date'), _('Posting Date'), _('Period'), _('G/L Account'), _('Ana. Account'), _('Third Party'), _('Book. Amount'), _('Book. Currency'), _('Func. Amount'), _('Func. Currency'), _('Output Amount'), _('Output Currency'), _('Reversal Origin'), _('Entry status')]:
    % if header == _('Ana. Account') and data.get('context') and data.get('context').get('display_fp'):
        <Cell ss:StyleID="ssH"><Data ss:Type="String">${_('Destination')}</Data></Cell>
        <Cell ss:StyleID="ssH"><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
        <Cell ss:StyleID="ssH"><Data ss:Type="String">${_('Funding Pool')}</Data></Cell>
    % else:
        <Cell ss:StyleID="ssH"><Data ss:Type="String">${header}</Data></Cell>
    % endif
% endfor
% if display_hq_account():
    <Cell ss:StyleID="ssH"><Data ss:Type="String">${_('HQ System Account')}</Data></Cell>
% endif
</Row>
% for o in objects:
<Row>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.instance_id and o.instance_id.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.journal_id and o.journal_id.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.entry_sequence or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.ref or '')|x}</Data>
</Cell>
% if isDate(o.document_date):
<Cell ss:StyleID="ssBorderDate">
        <Data ss:Type="DateTime">${o.document_date|n}T00:00:00</Data>
</Cell>
% else:
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">  </Data>
</Cell>
% endif
% if isDate(o.date):
<Cell ss:StyleID="ssBorderDate">
        <Data ss:Type="DateTime">${o.date|n}T00:00:00</Data>
</Cell>
% else:
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">  </Data>
</Cell>
% endif
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.period_id and o.period_id.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${"%s - %s" % (o.general_account_id and o.general_account_id.code or '', o.general_account_id and o.general_account_id.name or '')|x}</Data>
</Cell>
% if data and data.get('context') and data.get('context').get('display_fp'):
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.destination_id and o.destination_id.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.cost_center_id and o.cost_center_id.code or '')|x}</Data>
</Cell>
% endif
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.account_id and o.account_id.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.partner_txt or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${o.amount_currency or '0.0'}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.currency_id and o.currency_id.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${o.amount or '0.0'}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.company_id and o.company_id.currency_id and o.company_id.currency_id.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${o.output_amount or '0.0'}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.output_currency and o.output_currency.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.reversal_origin and o.reversal_origin.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.move_state and getSel(o, 'move_state') or '')|x}</Data>
</Cell>
% if display_hq_account():
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.hq_system_account or '')|x}</Data>
</Cell>
% endif
</Row>
% endfor
</Table>
<AutoFilter x:Range="R1C1:R1C${max}" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
</WorksheetOptions>
</Worksheet>
</Workbook>
