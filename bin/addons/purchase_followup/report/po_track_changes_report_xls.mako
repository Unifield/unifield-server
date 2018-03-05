<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Unifield</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2014-04-16T22:36:07Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>11640</WindowHeight>
  <WindowWidth>15480</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>75</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="ssCellBlue">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Color="#0000FF" />
    </Style>

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font x:Family="Swiss" ss:Size="14" ss:Bold="1"/>
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="9" />
        <Interior ss:Color="#C0C0C0" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Size="8" ss:Bold="1"/>
        <Interior/>
    </Style>
    <Style ss:ID="line_header_orange">
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Size="8" ss:Bold="1"/>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Lines -->
    <Style ss:ID="line_left">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
     <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_center_no_digits">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="line_left_date">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="Short Date" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <NumberFormat ss:Format="Short Date" />
        <Font ss:Color="#0000FF" />
    </Style>
</Styles>


% for r in objects:
<ss:Worksheet ss:Name="IR Follow Up per Location">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Order ref
        <Column ss:AutoFitWidth="1" ss:Width="145.75" />
        ## Status
        <Column ss:AutoFitWidth="1" ss:Width="160.75" />
        ## Item
        <Column ss:AutoFitWidth="1" ss:Width="30.0" />
        ## Product code
        <Column ss:AutoFitWidth="1" ss:Width="70.25" />
        ## Product description
        <Column ss:AutoFitWidth="1" ss:Width="250.25" />
        ## Original Product code
        <Column ss:AutoFitWidth="1" ss:Width="70.25" />
        ## Qty
        <Column ss:AutoFitWidth="1" ss:Width="58.75" />
        ## UoM
        <Column ss:AutoFitWidth="1" ss:Width="58.75" />
        ## Original Qty
        <Column ss:AutoFitWidth="1" ss:Width="63.75" />
        ## Original UoM
        <Column ss:AutoFitWidth="1" ss:Width="63.75" />
        ## Price
        <Column ss:AutoFitWidth="1" ss:Width="75.75" />
        ## Currency
        <Column ss:AutoFitWidth="1" ss:Width="58.75" />
        ## Original Price
        <Column ss:AutoFitWidth="1" ss:Width="85.75" />
        ## Original Currency
        <Column ss:AutoFitWidth="1" ss:Width="90.75" />
        ## Price in functional currency
        <Column ss:AutoFitWidth="1" ss:Width="130.75" />
        ## Original Price in functional currency
        <Column ss:AutoFitWidth="1" ss:Width="160.75" />
        ## Subtotal (functional currency)
        <Column ss:AutoFitWidth="1" ss:Width="140.25" />
        ## Original Subtotal (functional currency)
        <Column ss:AutoFitWidth="1" ss:Width="170.25" />
        ## Modification comment
        <Column ss:AutoFitWidth="1" ss:Width="209.25" />

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header"><Data ss:Type="String">PURCHASE ORDER Track Changes report</Data><NamedCell ss:Name="Print_Area"/></Cell>
        </Row>

        <Row ss:Height="10"></Row>

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Instance information')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="file_header" ss:MergeAcross="4"><Data ss:Type="String">${_('Request parameters')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Name:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.instance_id.instance or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date start:')|x}</Data></Cell>
            % if isDate(r.start_date):
            <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.start_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Address:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.name or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date end:')|x}</Data></Cell>
            % if isDate(r.end_date):
            <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.end_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.address[0].street or ''|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Order Ref:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue" ss:MergeAcross="2"><Data ss:Type="String">${r.po_id.id and r.po_id.name or '-'|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.address[0].zip|x} ${r.company_id.partner_id.address[0].city|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date of the request:')|x}</Data></Cell>
            % if r.report_date and isDateTime(r.report_date):
            <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.report_date[0:10]|n}T${r.report_date[11:19]|n}.000</Data></Cell>
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.address[0].country_id and r.company_id.partner_id.address[0].country_id.name or ''|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
        </Row>

        <Row></Row>

        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Order ref')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Status')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Item')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Code')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Description')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Original Code')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Qty')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('UoM')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Original Qty')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Original UoM')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Unit Price')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Currency')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Original Unit Price')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Original Currency')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Price in functional currency')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Original Price in functional currency')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Subtotal (functional currency)')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_orange"><Data ss:Type="String">${_('Original Subtotal (functional currency)')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Modification comment')|x}</Data></Cell>
        </Row>

        % for line in getLines(r):
            <Row ss:Height="11.25">
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.order_id.name|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.state|x}</Data></Cell>
                <Cell ss:StyleID="line_center_no_digits"><Data ss:Type="Number">${line.line_number|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.product_id.default_code or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.name|x}</Data></Cell>
                % if line.original_product and line.product_id.default_code != line.original_product.default_code:
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.original_product.default_code or ''|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="Number">${line.product_qty|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.product_uom.name|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="Number">${line.original_qty or line.product_qty|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.original_uom.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line.price_unit|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line.currency_id.name|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line.original_price or line.price_unit|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line.original_currency_id and line.original_currency_id.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${computeCurrency(line, False)|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${computeCurrency(line, True)|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${computeCurrency(line, False) * line.product_qty|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${computeCurrency(line, True) * line.original_qty|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.modification_comment or ''|x}</Data></Cell>
            </Row>
        % endfor

    </Table>

    <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
        <PageSetup>
            <Layout x:Orientation="Landscape"/>
            <Footer x:Data="Page &amp;P of &amp;N"/>
        </PageSetup>
        <Selected/>
        <Panes>
            <Pane>
                <Number>3</Number>
                <ActiveRow>21</ActiveRow>
            </Pane>
        </Panes>
        <ProtectObjects>False</ProtectObjects>
        <ProtectScenarios>False</ProtectScenarios>
    </WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
