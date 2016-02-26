<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('Analytic Journal Items (Free 1 / Free 2)')}</Title>
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
<Style ss:ID="ssBorderTotal">
<Alignment ss:Vertical="Center" ss:WrapText="1" ss:Horizontal="Right"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<Font ss:Bold="1"/>
</Style>
<Style ss:ID="ssBorderNumber">
<Font ss:Bold="1"/>
<NumberFormat ss:Format="#,##0.00"/>
<Alignment ss:Vertical="Center" ss:WrapText="1" ss:Horizontal="Right"/>
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
<Table ss:ExpandedColumnCount="19" x:FullColumns="1" x:FullRows="1">
% for x in range(0,19):
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
<Row>
% for header in [_('Proprietary Instance'), _('Journal Code'), _('Entry Sequence'), _('Description'), _('Ref.'), _('Document Date'), _('Posting Date'), _('Period'), _('G/L Account'), _('Ana. Account'), _('Third Party'), _('Book. Amount'), _('Book. Currency'), _('Func. Amount'), _('Func. Currency'), _('Output Amount'), _('Output Currency'), _('Reversal Origin'), _('Entry status')]:
    <Cell ss:StyleID="ssH"><Data ss:Type="String">${header}</Data></Cell>
% endfor
</Row>
<%
  previous = False
  total = 0.0
  grand_total = 0.0
%>
% for o in objects:
<%
  grand_total += o.amount
%>
% if not previous:
<%
  previous = o.account_id.id
%>
% endif
% if previous != o.account_id.id:
<Row>
  <Cell ss:StyleID="ssBorderTotal" ss:MergeAcross="12"><Data ss:Type="String">${_('Subtotal')} </Data></Cell>
  <Cell ss:StyleID="ssBorderNumber"><Data ss:Type="Number">${total}</Data></Cell>
</Row>
<%
  total = 0.0
%>
% endif
<%
  total += o.amount
%>
<Row>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.instance_id and o.instance_id.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.journal_id and o.journal_id.code or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.move_id and o.move_id.move_id and o.move_id.move_id.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.ref or '')|x}</Data>
</Cell>
% if o.document_date and o.document_date != 'False':
<Cell ss:StyleID="ssBorderDate">
        <Data ss:Type="DateTime">${o.document_date|n}T00:00:00</Data>
</Cell>
% else:
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">  </Data>
</Cell>
% endif
% if o.date and o.date != 'False':
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
</Row>
<%
  previous = o.account_id.id
%>
% endfor
<!-- Last subtotal and GRAND TOTAL -->
<Row>
  <Cell ss:StyleID="ssBorderTotal" ss:MergeAcross="12"><Data ss:Type="String">${_('Subtotal')} </Data></Cell>
  <Cell ss:StyleID="ssBorderNumber"><Data ss:Type="Number">${total}</Data></Cell>
</Row>
<Row>
  <Cell ss:StyleID="ssBorderTotal" ss:MergeAcross="12"><Data ss:Type="String">${_('Total')} </Data></Cell>
  <Cell ss:StyleID="ssBorderNumber"><Data ss:Type="Number">${grand_total}</Data></Cell>
</Row>
</Table>
<AutoFilter x:Range="R1C1:R1C19" xmlns="urn:schemas-microsoft-com:office:excel">
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
