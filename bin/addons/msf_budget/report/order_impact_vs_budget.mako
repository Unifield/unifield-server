<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('Order Impact vs. Budget')}</Title>
</DocumentProperties>
<Styles>
<Style ss:ID="ssCell">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellRed">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
<Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#FF0000" />
</Style>
<Style ss:ID="ssCellBold">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Top" ss:Horizontal="Left" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssTitle">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Center" ss:Horizontal="Center" ss:WrapText="1"/>
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
<Font ss:Bold="1" />
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderRed">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#FF0000" />
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
<Style ss:ID="ssNumberRed">
<Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#FF0000" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssNumberRedBold">
<Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#FF0000" ss:Bold="1" />
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
<Style ss:ID="ssHeaderDateCell">
<Alignment ss:Vertical="Top" ss:Horizontal="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="Short Date" />
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
% for o in objects:
<Worksheet ss:Name="${ o.name or ''|x}">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="70" ss:Span="7"/>

<!-- HEADER -->
<Row>
    <Cell ss:StyleID="ssTitle" ss:MergeAcross="7">
       <Data ss:Type="String">${_('ORDER IMPACT VS. BUDGET')}</Data>
    </Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>
<Row>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Delivery requested date')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Delivery confirmed date')}</Data></Cell>
 <Cell ss:StyleID="ssHeader" ss:MergeAcross="2"><Data ss:Type="String">${_('PO reference')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Fiscal year')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Functional currency')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Report date')}</Data></Cell>
</Row>

<Row>
     <Cell ss:StyleID="ssHeaderDateCell">
        <Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data>
     </Cell>
     <Cell ss:StyleID="ssHeaderDateCell">
        <Data ss:Type="DateTime">${o.delivery_confirmed_date|n}T00:00:00.000</Data>
     </Cell>
     <Cell ss:StyleID="ssHeaderCell" ss:MergeAcross="2">
        <Data ss:Type="String">${ o.name or ''|x}</Data>
     </Cell>
     <Cell ss:StyleID="ssHeaderCell">
        <Data ss:Type="String">${ get_fiscal_year(o) or ''|x}</Data>
     </Cell>
     <Cell ss:StyleID="ssHeaderCell">
        <Data ss:Type="String">${ o.functional_currency_id and o.functional_currency_id.name or ''|x}</Data>
     </Cell>
    <Cell ss:StyleID="ssHeaderDateCell">
        <Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data>
     </Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCellRed" ss:MergeAcross="7">
        <Data ss:Type="String">${ check_distribution(o) and ' ' or _('WARNING: analytic distribution for this PO is not complete!') }</Data>
    </Cell>
</Row>

<!-- TABLE HEADER -->
<Row>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Cost Centre')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Account')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Dest.')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Budget amount')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Actual amount')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Remaining Budget')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('PO amount')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('PO impact')}</Data>
    </Cell>
</Row>

% for line in get_report_lines(o):

    <Row>
        % if line[0] == 'TOTALS':
            <Cell ss:StyleID="ssBorderBold">
                <Data ss:Type="String">${ _('TOTALS') |x}</Data>
            </Cell>
        % else:
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${ line[0] or '' |x}</Data>
            </Cell>
        % endif
        <Cell ss:StyleID="ssBorder">
            <Data ss:Type="String">${ line[1] or '' |x}</Data>
        </Cell>
        <Cell ss:StyleID="ssBorder">
            <Data ss:Type="String">${ line[7] or '' |x}</Data>
        </Cell>
        % if line[2] == 'Budget missing':
            <Cell ss:StyleID="ssBorderRed">
                <Data ss:Type="String">${ _('Budget missing') |x}</Data>
            </Cell>
        % elif line[0] == 'TOTALS':
            <Cell ss:StyleID="ssNumberBold">
                <Data ss:Type="Number">${ line[2] or 0.0 }</Data>
            </Cell>
        % elif not line[2]:
            <Cell ss:StyleID="ssNumber"></Cell>
        % else:
            <Cell ss:StyleID="ssNumber">
                <Data ss:Type="Number">${ line[2] or 0.0 }</Data>
            </Cell>
        % endif
        % if line[3] == line[4] == line[5] == '':
            <!-- empty lines used as separator... -->
            <Cell ss:StyleID="ssNumber"></Cell>
            <Cell ss:StyleID="ssNumber"></Cell>
            <Cell ss:StyleID="ssNumber"></Cell>
        % elif line[0] == 'TOTALS':
            <Cell ss:StyleID="ssNumberBold"><Data ss:Type="Number">${ line[3] or 0.0 }</Data></Cell>
            <Cell ss:StyleID="ssNumberBold"><Data ss:Type="Number">${ line[4] or 0.0 }</Data></Cell>
            <Cell ss:StyleID="ssNumberBold"><Data ss:Type="Number">${ line[5] or 0.0 }</Data></Cell>
        % else:
            <Cell ss:StyleID="ssNumber"><Data ss:Type="Number">${ line[3] or 0.0 }</Data></Cell>
            <Cell ss:StyleID="ssNumber"><Data ss:Type="Number">${ line[4] or 0.0 }</Data></Cell>
            <Cell ss:StyleID="ssNumber"><Data ss:Type="Number">${ line[5] or 0.0 }</Data></Cell>
        % endif
        % if not line[6]:
            <Cell ss:StyleID="ssNumber"></Cell>
        % elif isPos(line[6]):
            % if line[0] == 'TOTALS':
                <Cell ss:StyleID="ssNumberBold"><Data ss:Type="Number">${ line[6] or 0.0 }</Data></Cell>
            % else:
                <Cell ss:StyleID="ssNumber"><Data ss:Type="Number">${ line[6] or 0.0 }</Data></Cell>
            % endif
        % else:
            % if line[0] == 'TOTALS':
                <Cell ss:StyleID="ssNumberRedBold"><Data ss:Type="Number">${ line[6] or 0.0 }</Data></Cell>
            % else:
                <Cell ss:StyleID="ssNumberRed"><Data ss:Type="Number">${ line[6] or 0.0 }</Data></Cell>
            % endif
        % endif
    </Row>

% endfor

<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell" ss:MergeAcross="7">
        <Data ss:Type="String">${ _('Actual amounts in this report include confirmed POs (commitments) but not open / validated POs.') }</Data>
    </Cell>
</Row>

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14Order Impact vs. Budget"/>
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
% endfor
</Workbook>
