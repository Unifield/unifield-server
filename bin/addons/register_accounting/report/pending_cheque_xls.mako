<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>MSFUser</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2014-07-10T10:14:00Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>13170</WindowHeight>
  <WindowWidth>19020</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>60</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
<Styles>


<Style ss:ID="header">
	<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
	<Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
	<Borders>
	  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
	</Borders>
</Style>
<Style ss:ID="line">
	<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
	<Borders>
	  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
	</Borders>
</Style>


<Style ss:ID="lineN">
	<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
	<Borders>
	  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
	</Borders>
	<NumberFormat ss:Format="Standard"/>
</Style>

<Style ss:ID="title">
	<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
</Style>

<Style ss:ID="s22">
	<Borders>
		<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
	</Borders>
</Style>
<Style ss:ID="s23">
	<Borders>
		<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
	</Borders>
	<NumberFormat ss:Format="Short Date"/>
</Style>
<Style ss:ID="s24">
	<Borders>
		<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
		<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
	</Borders>
	<NumberFormat ss:Format="mmm\-yy"/>
</Style>

<Style ss:ID="short_date">
	<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
	<Borders>
	<Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
	<Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
	<Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
	<Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
	</Borders>
	<NumberFormat ss:Format="Short Date"/>
</Style>

<Style ss:ID="short_date2">
	<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
	<NumberFormat ss:Format="Short Date"/>
</Style>

<Style ss:ID="s25">
	<Font ss:Bold="1"/>
</Style>



</Styles>
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%( o.name.split('/')[-1] +'_'+str(o.id) or 'Sheet1')|x}">

<Table>
  <Column ss:Width="73.5" ss:Span="1"/>
  <Column ss:Width="67.5"/>
  <Column ss:Width="75.75"/>
  <Column ss:Width="113.25" ss:Span="1"/>
  <Column ss:Width="180.75"/>
  <Column ss:Width="70.5"/>
  <Column ss:AutoFitWidth="0" ss:Width="229.5"/>
  <Column ss:Width="60.75" ss:Span="1"/>
  <Column ss:AutoFitWidth="0" ss:Width="60.75" ss:Span="1"/>
  <Column ss:Width="45.25"/>
  <Column ss:Width="55.25"/>

  <Row>
    <Cell ss:StyleID="s25" ><Data ss:Type="String">${_('PENDING CHEQUE')}</Data></Cell>
  </Row>
  <Row ss:Index="3">
    <Cell ss:StyleID="title" ><Data ss:Type="String">${_('Instance:')}</Data></Cell>
    <Cell ss:StyleID="title" ><Data ss:Type="String">${( company.instance_id and company.instance_id.code or '')|x}</Data></Cell>
  </Row>
  <Row>
    <Cell ss:StyleID="title" ><Data ss:Type="String">${_('Report Date:')}</Data></Cell>
    <Cell ss:StyleID="short_date2" ><Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data></Cell>
  </Row>
  <Row>
    <Cell ss:StyleID="title"><Data ss:Type="String">${_('State:')}</Data></Cell>
    <Cell ss:StyleID="title"><Data ss:Type="String">${(o.state and getSel(o, 'state') or '')|x}</Data></Cell>
  </Row>
  <Row>
    <Cell ss:StyleID="title"><Data ss:Type="String">${_('Register name:')}</Data></Cell>
    <Cell ss:StyleID="title" ><Data ss:Type="String">${(o.name or '')|x}</Data></Cell>
  </Row>
  <Row>
    <Cell ss:StyleID="title" ><Data ss:Type="String">${_('Journal Code')}</Data></Cell>
    <Cell ss:StyleID="title" ><Data ss:Type="String">${(o.journal_id and o.journal_id.code or '')|x}</Data></Cell>
  </Row>
  <Row>
    <Cell ss:StyleID="title" ><Data ss:Type="String">${_('Currency')}</Data></Cell>
    <Cell ss:StyleID="title" ><Data ss:Type="String">${(o.journal_id and o.journal_id.currency and o.journal_id.currency.name or '')|x}</Data></Cell>
  </Row>
  <Row><Cell><Data ss:Type="String"></Data></Cell></Row>

	<Row>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Document Date')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Posting Date')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Period')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Cheque Number')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Sequence')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Description')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Reference')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Account')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Third Parties')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Amount In')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Amount Out')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Func. In')}</Data></Cell>
		<Cell ss:StyleID="header" ><Data ss:Type="String">${_('Func. Out')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Func. CCY')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Amount reconciled')}</Data></Cell>


	</Row>
    % for line in getLines(o):
    <Row>
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.document_date|n}T00:00:00.000</Data></Cell>
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.date|n}T00:00:00.000</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.statement_id and line.statement_id.period_id and line.statement_id.period_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.cheque_number and line.cheque_number or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.move_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.name and line.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.ref or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.account_id and line.account_id.code and line.account_id.name and line.account_id.code + ' ' + line.account_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.partner_txt or '')|x}</Data></Cell>
        <Cell ss:StyleID="lineN" ><Data ss:Type="Number">${(line.debit_currency and line.debit_currency or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="lineN" ><Data ss:Type="Number">${(line.credit_currency and line.credit_currency or 0.00)|x}</Data></Cell>

        <Cell ss:StyleID="lineN" ><Data ss:Type="Number">${(line.debit and line.debit or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="lineN" ><Data ss:Type="Number">${(line.credit and line.credit or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.functional_currency_id and line.functional_currency_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.is_reconciled and _('YES') or _('NO')|x}</Data></Cell>
    </Row>
    % endfor
</Table>

<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Margin="0.4921259845"/>
    <Footer x:Margin="0.4921259845"/>
    <PageMargins x:Bottom="0.984251969" x:Left="0.78740157499999996"
     x:Right="0.78740157499999996" x:Top="0.984251969"/>
   </PageSetup>
   <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
  </WorksheetOptions>
  <x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
