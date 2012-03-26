<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>Analytic Journal Items</Title>
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
</Styles>
<Worksheet ss:Name="Sheet">
<Table ss:ExpandedColumnCount="18" ss:ExpandedRowCount="${len(objects)+1}" x:FullColumns="1"
x:FullRows="1">
% for x in range(0,18):
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
<Row>
% for header in ['Proprietary Instance', 'Journal Code', 'Entry Sequence', 'Description', 'Ref.', 'Posting Date', 'Document Date', 'Period', 'G/L Account', 'Ana. Account', 'Third Party', 'Book. Amount', 'Book. Currency', 'Func. Amount', 'Func. Currency', 'Out. Amount', 'Out. Currency', 'Reversal Origin']:
<Cell ss:StyleID="ssH"><Data ss:Type="String">${header}</Data></Cell>
% endfor
</Row>
% for o in objects:
<Row>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.company_id and o.company_id.name or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.journal_id and o.journal_id.code or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.move_id and o.move_id.move_id and o.move_id.move_id.name or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${(o.name or '')|x}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.ref or ''}</Data>
</Cell>
% if o.date:
<Cell ss:StyleID="ssBorderDate">
        <Data ss:Type="DateTime">${o.date|n}T00:00:00</Data>
</Cell>
% else:
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">  </Data>
</Cell>
% endif
% if o.document_date and o.document_date != 'False':
<Cell ss:StyleID="ssBorderDate">
        <Data ss:Type="DateTime">${o.document_date|n}T00:00:00</Data>
</Cell>
% else:
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">  </Data>
</Cell>
% endif
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.period_id and o.period_id.name or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.general_account_id and o.general_account_id.code or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.account_id and o.account_id.name or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.partner_txt or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="Number">${o.amount or '0.0'}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.company_id and o.company_id.currency_id and o.company_id.currency_id.name or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="Number">${o.amount_currency or '0.0'}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.currency_id and o.currency_id.name or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="Number">${o.output_amount or '0.0'}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.output_currency and o.output_currency.name or ''}</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${o.reversal_origin and o.reversal_origin.name or ''}</Data>
</Cell>
</Row>
% endfor
</Table>
<AutoFilter x:Range="R1C1:R1C18" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
</Worksheet>
</Workbook>
