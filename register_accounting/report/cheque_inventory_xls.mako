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
  <Created>2012-06-18T15:46:09Z</Created>
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

<Table >
<Column ss:Width="65.0"/>
<Column ss:Width="65.0"/>
<Column ss:Width="65.0"/>
<Column ss:Width="65.0"/>
<Column ss:Width="60.0"/>
<Column ss:Width="75.0"/>
<Column ss:Width="75.0"/>
<Column ss:Width="85.0"/>
<Column ss:Width="90.0"/>
<Column ss:Width="70.5"/>
<Column ss:Width="70.5"/>
<Column ss:Width="65.0"/>
<Column ss:Width="45.0"/>


  <Row>
    <Cell ss:StyleID="s25" ><Data ss:Type="String">${_('CHEQUE INVENTORY')}</Data></Cell>
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
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Amount reconciled')}</Data></Cell>
    <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Status')}</Data></Cell>
  </Row>
    <% lines = getLines(o) %>
    % for line in lines:
    <Row>
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.document_date|n}T00:00:00.000</Data></Cell>
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.date|n}T00:00:00.000</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.statement_id and line.statement_id.period_id and line.statement_id.period_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.cheque_number and line.cheque_number or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.sequence_for_reference and line.sequence_for_reference or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.name and line.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.first_move_line_id and line.first_move_line_id.ref or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.account_id and line.account_id.code and line.account_id.name and line.account_id.code + ' ' + line.account_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.first_move_line_id and line.first_move_line_id.partner_txt or '')|x}</Data></Cell>
        <Cell ss:StyleID="lineN" ><Data ss:Type="Number">${(line.amount_in and line.amount_in or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="lineN" ><Data ss:Type="Number">${(line.amount_out and line.amount_out or 0.00)|x}</Data></Cell>

        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.reconciled and 'X' or ''|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.state and getSel(line,'state') or '')|x}</Data></Cell>
    </Row>
    % endfor
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
</WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
