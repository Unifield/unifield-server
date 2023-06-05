<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('Combined Journals Report')}</Title>
</DocumentProperties>
<Styles>
<Style ss:ID="ssCell">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellBold">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Top" ss:Horizontal="Left" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellRight">
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellRightBold">
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Font ss:Bold="1" />
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
<Style ss:ID="ssBorderTopLeftRight">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Center" ss:Horizontal="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderBottomLeftRight">
<Alignment ss:Vertical="Center" ss:Horizontal="Left" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
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
<Alignment ss:Vertical="Top" ss:Horizontal="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssHeaderNumber">
<Font ss:Bold="1" />
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssHeaderRight">
<Font ss:Bold="1" />
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssHeaderCell">
<Alignment ss:Vertical="Top" ss:Horizontal="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssHeaderNumberCell">
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssDateTimeLeft">
<Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="General Date" />
</Style>
</Styles>
<Worksheet ss:Name="${_('Combined Journals Report')}">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="110"/>
<Column ss:AutoFitWidth="1" ss:Width="80"/>
<Column ss:AutoFitWidth="1" ss:Width="130"/>
<Column ss:AutoFitWidth="1" ss:Width="180"/>
<Column ss:AutoFitWidth="1" ss:Width="120"/>
<Column ss:AutoFitWidth="1" ss:Width="80" ss:Span="1"/>
<Column ss:AutoFitWidth="1" ss:Width="60"/>
<Column ss:AutoFitWidth="1" ss:Width="120"/>
<Column ss:AutoFitWidth="1" ss:Width="160"/>
% if analytic_axis() in ('f1', 'f2'):
 <Column ss:AutoFitWidth="1" ss:Width="100"/>
% else:
 <Column ss:AutoFitWidth="1" ss:Width="80" ss:Span="2"/>
% endif
<Column ss:AutoFitWidth="1" ss:Width="100" ss:Span="1"/>
<Column ss:AutoFitWidth="1" ss:Width="80"/>
<Column ss:AutoFitWidth="1" ss:Width="100" ss:Span="1"/>
<Column ss:AutoFitWidth="1" ss:Width="80"/>
<Column ss:AutoFitWidth="1" ss:Width="90"/>
<Column ss:AutoFitWidth="1" ss:Width="70"/>

<!-- HEADER -->
<Row>
    <Cell ss:StyleID="ssDateTimeLeft" >
       <Data ss:Type="DateTime">${time.strftime('%Y-%m-%dT%H:%M:%S')|n}.000</Data>
    </Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    % if analytic_axis() not in ('f1', 'f2'):
        <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    % endif
    <Cell ss:StyleID="ssCell" >
       <Data ss:Type="String">${ current_inst_code() |x}</Data>
    </Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    % if analytic_axis() not in ('f1', 'f2'):
        <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
    % endif
    <Cell ss:StyleID="ssCellBold" ss:MergeAcross="2">
       <Data ss:Type="String">${_('COMBINED JOURNALS REPORT')}</Data>
    </Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>
<Row>
    % if analytic_axis() in ('f1', 'f2'):
        <Cell ss:StyleID="ssBorderTopLeftRight" ss:MergeAcross="19">
    % else:
        <Cell ss:StyleID="ssBorderTopLeftRight" ss:MergeAcross="21">
    % endif
        <Data ss:Type="String">${_('SELECTION')}</Data>
    </Cell>
</Row>
<Row>
    % if analytic_axis() in ('f1', 'f2'):
        <Cell ss:StyleID="ssBorderBottomLeftRight" ss:MergeAcross="19">
    % else:
        <Cell ss:StyleID="ssBorderBottomLeftRight" ss:MergeAcross="21">
    % endif
        <Data ss:Type="String">${ criteria() |x}</Data>
    </Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>

<!-- TABLE HEADER -->
<Row>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Proprietary Instance')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Journal Code')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Entry Sequence')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Description')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Reference')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Document Date')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Posting Date')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Period')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('G/L Account')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Third Parties')}</Data>
    </Cell>
    % if analytic_axis() == 'fp':
      <Cell ss:StyleID="ssHeader">
          <Data ss:Type="String">${_('Cost Centre')}</Data>
      </Cell>
      <Cell ss:StyleID="ssHeader">
          <Data ss:Type="String">${_('Destination')}</Data>
      </Cell>
      <Cell ss:StyleID="ssHeader">
          <Data ss:Type="String">${_('Funding Pool')}</Data>
      </Cell>
    % elif analytic_axis() in ('f1', 'f2'):
      <Cell ss:StyleID="ssHeader">
          <Data ss:Type="String">${_('Analytic Account')}</Data>
      </Cell>
    % endif
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Booking Debit')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Booking Credit')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Book. Currency')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Func. Debit')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Func. Credit')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Func. Currency')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Reconcile')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Status')}</Data>
    </Cell>
    % if display_hq_account():
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('HQ System Account')}</Data>
    </Cell>
    % endif
</Row>

% for line in lines():
<Row>
    <Cell ss:StyleID="ssBorder">
        <!-- updates the percentage of the report generation -->
        <Data ss:Type="String">${update_percent_display() and line['prop_instance']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['journal_code']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['entry_sequence']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['description']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['reference']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorderDate">
        <Data ss:Type="DateTime">${line['document_date']|n}T00:00:00.000</Data>
    </Cell>
    <Cell ss:StyleID="ssBorderDate">
        <Data ss:Type="DateTime">${line['posting_date']|n}T00:00:00.000</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['period']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['gl_account']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['third_party']|x}</Data>
    </Cell>
    % if analytic_axis() == 'fp':
      <Cell ss:StyleID="ssBorder">
          <Data ss:Type="String">${line['cost_center']|x}</Data>
      </Cell>
      <Cell ss:StyleID="ssBorder">
          <Data ss:Type="String">${line['destination']|x}</Data>
      </Cell>
      <Cell ss:StyleID="ssBorder">
          <Data ss:Type="String">${line['funding_pool']|x}</Data>
      </Cell>
    % elif analytic_axis() in ('f1', 'f2'):
      <Cell ss:StyleID="ssBorder">
          <Data ss:Type="String">${line['analytic_account']|x}</Data>
      </Cell>
    % endif
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${line['booking_debit']}</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${line['booking_credit']}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['booking_currency']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${line['func_debit']}</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${line['func_credit']}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['func_currency']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['reconcile']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${getSelValue('account.move', 'state', line['status']) or ''|x}</Data>
    </Cell>
    % if display_hq_account():
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['hq_system_account'] or ''|x}</Data>
    </Cell>
    % endif
</Row>
% endfor

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14Combined Journals Report"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
   <Print>
    <FitHeight>0</FitHeight>
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
