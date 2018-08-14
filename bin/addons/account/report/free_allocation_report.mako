<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('Analytic Allocation with Free - Report')}</Title>
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
<Style ss:ID="ssBorderBold">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
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
<Style ss:ID="ssBorderLeftRight">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Center" ss:Horizontal="Center" ss:WrapText="1"/>
<Borders>
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
<Style ss:ID="ssNumberBold">
<Font ss:Bold="1" />
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
<Worksheet ss:Name="${_('Analytic Allocation with Free')}">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="125"/>
<Column ss:AutoFitWidth="1" ss:Width="70" ss:Span="2"/>
<Column ss:AutoFitWidth="1" ss:Width="75"/>
<Column ss:AutoFitWidth="1" ss:Width="100"/>
<Column ss:AutoFitWidth="1" ss:Width="120" ss:Span="1"/>
<Column ss:AutoFitWidth="1" ss:Width="70"/>
<Column ss:AutoFitWidth="1" ss:Width="85" ss:Span="1"/>

<!-- LIST OF SELECTED FILTERS -->
<Row>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Proprietary Instance')}</Data></Cell>
    <Cell ss:StyleID="ssHeader" ss:MergeAcross="1"><Data ss:Type="String">${_('Accounts')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Journals')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Fiscal Year')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Period')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Document date')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Posting date')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Free 1')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Free 2')}</Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Cost Centers')}</Data></Cell>
</Row>

<Row>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_proprietary_instance(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell" ss:MergeAcross="1"><Data ss:Type="String">${ get_accounts(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_journals(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_fiscal_year(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_period(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_document_date(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_posting_date(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_free1(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_free2(data) or ''|x}</Data></Cell>
    <Cell ss:StyleID="ssHeaderCell"><Data ss:Type="String">${ get_cost_centers(data) or ''|x}</Data></Cell>
</Row>

<!-- TABLE HEADER -->
<Row></Row>
<Row>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Entry Sequence')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Account')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Destination')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Cost Center')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Funding Pool')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Free 1')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Free 2')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Book. Amount')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Book. Currency')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Func. Amount')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Func. Currency')}</Data>
    </Cell>
</Row>

% for entry_seq in lines(data):
    <!-- LINES -->
    <% line_number = 0 %>
    % for line in lines(data)[entry_seq]:
        <% line_number += 1 %>
        <Row>
            % if line_number == 1:
                <!-- entry seq. in bold -->
                <Cell ss:StyleID="ssBorderBold">
                    <Data ss:Type="String">${entry_seq|x}</Data>
                </Cell>
            % else:
                <!-- empty cell with only left and right borders -->
                <Cell ss:StyleID="ssBorderLeftRight">
                    <Data ss:Type="String"></Data>
                </Cell>
            % endif
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['account']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['destination']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['cost_center']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['funding_pool']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['free1']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['free2']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssNumber">
                <Data ss:Type="Number">${line['book_amount']}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['book_currency']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssNumber">
                <Data ss:Type="Number">${line['func_amount']}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${line['func_currency']|x}</Data>
            </Cell>
        </Row>
    % endfor
    <!-- TOTAL -->
    <% total_l = total_line(entry_seq) %>
    % if total_l:
        <Row>
            <% total_str = "%s %s" % (_("Total"), entry_seq) %>
            <Cell ss:StyleID="ssBorderBold">
                <Data ss:Type="String">${total_str|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorderBold" ss:MergeAcross="5"></Cell>
            <Cell ss:StyleID="ssNumberBold">
                <Data ss:Type="Number">${total_l['book_amount']}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorderBold">
                <Data ss:Type="String">${total_l['book_currency']|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssNumberBold">
                <Data ss:Type="Number">${total_l['func_amount']}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorderBold">
                <Data ss:Type="String">${company.currency_id.name|x}</Data>
            </Cell>
        </Row>
    % endif
    % if lines(data)[entry_seq]:
        <!-- EMPTY LINE BETWEEN EACH ENTRY SEQ. -->
        <Row>
            <Cell ss:MergeAcross="10"><Data ss:Type="String"></Data></Cell>
        </Row>
    % endif
% endfor

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14Analytic Allocation with Free - Report"/>
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
