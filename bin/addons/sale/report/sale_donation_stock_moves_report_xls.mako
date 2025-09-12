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

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Size="10"/>
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
        <Font ss:Size="10"/>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="10"/>
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
        <Font ss:Size="10"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="sShortDate">
        <NumberFormat ss:Format="Short Date"/>
        <Alignment ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
 </Styles>

 % for r in objects:
 <ss:Worksheet ss:Name="${_('Donation Report')}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Product Code
        <Column ss:AutoFitWidth="1" ss:Width="92.5" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="271.5" />
        ## Account Code
        <Column ss:AutoFitWidth="1" ss:Width="150.75" />
        ## Donation Account
        <Column ss:AutoFitWidth="1" ss:Width="82.25" />
        ## Movement Date
        <Column ss:AutoFitWidth="1" ss:Width="72.25" />
        ## Move Ref.
        <Column ss:AutoFitWidth="1" ss:Width="102.0" />
        ## Line State
        <Column ss:AutoFitWidth="1" ss:Width="73.25" />
        ## Order Type
        <Column ss:AutoFitWidth="1" ss:Width="129.0" />
        ## Order Ref.
        <Column ss:AutoFitWidth="1" ss:Width="135.75" />
        ## Partner
        <Column ss:AutoFitWidth="1" ss:Width="135.75" />
        ## Partner Type
        <Column ss:AutoFitWidth="1" ss:Width="75.0" />
        ## Qty In
        <Column ss:AutoFitWidth="1" ss:Width="54.25" />
        ## Qty Out
        <Column ss:AutoFitWidth="1" ss:Width="54.25"  />
        ## Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="57.75"  />
        ## Currency (FX)
        <Column ss:AutoFitWidth="1" ss:Width="65.75"  />
        ## Total Value IN
        <Column ss:AutoFitWidth="1" ss:Width="75.25"  />
        ## Total Value OUT
        <Column ss:AutoFitWidth="1" ss:Width="75.25"  />
        % if r.display_bn_ed:
        ## Batch Number
        <Column ss:AutoFitWidth="1" ss:Width="85.25" />
        ## Expiry Date
        <Column ss:AutoFitWidth="1" ss:Width="75.0" />
        % endif
        ## Instance
        <Column ss:AutoFitWidth="1" ss:Width="150.75"  />

        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Code')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Description')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Account Code')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Donation Account')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Movement Date')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Move Ref.')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Line State')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Order Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Order Ref.')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Partner')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Partner Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Qty In')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Qty Out')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Unit Price')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Currency (FX)')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Total Value IN')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Total Value OUT')|x}</Data></Cell>
            % if r.display_bn_ed:
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Batch Number')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Expiry Date')|x}</Data></Cell>
            % endif
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Instance')|x}</Data></Cell>
        </Row>

        % for o in getMoves(r):
            <Row ss:Height="14.25">
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.product_id.default_code|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.product_id.name|x}</Data></Cell>
                % if o.product_id.property_account_expense:
                <Cell ss:StyleID="line_right"><Data ss:Type="String">${o.product_id.property_account_expense.code + ' - ' + o.product_id.property_account_expense.name|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String">${(o.product_id.categ_id.property_account_expense_categ.code + ' - ' + o.product_id.categ_id.property_account_expense_categ.name) or ''|x}</Data></Cell>
                % endif
                % if o.product_id.donation_expense_account.code:
                <Cell ss:StyleID="line_right"><Data ss:Type="String">${o.product_id.donation_expense_account.code|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String">${o.product_id.categ_id.donation_expense_account.code or ''|x}</Data></Cell>
                % endif
                %if o.date and isDateTime(o.date):
                <Cell ss:StyleID="sShortDate"><Data ss:Type="DateTime">${o.date[:10]|n}T${o.date[-8:]|n}.000</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.picking_id.name|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${getSel(o, 'state')|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${getRtTranslation(o.reason_type_id.name, o.reason_type_id.code)|x}</Data></Cell>
                % if isQtyOut(o):
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.sale_line_id and o.sale_line_id.order_id.name or ''|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.purchase_line_id and o.purchase_line_id.order_id.name or ''|x}</Data></Cell>
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.partner_id and o.partner_id.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.partner_id and getSel(o.partner_id, 'partner_type') or ''|x}</Data></Cell>
                % if isQtyOut(o):
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">0.00</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${getQty(o)|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${getQty(o)|x}</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">0.00</Data></Cell>
                % endif
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${computeCurrency(o)|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${userCompany['currency_id'].name|x}</Data></Cell>
                % if isQtyOut(o):
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">0.00</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${computeCurrency(o) * getQty(o)|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${computeCurrency(o) * getQty(o)|x}</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">0.00</Data></Cell>
                % endif
                % if r.display_bn_ed:
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.state == 'done' and o.prodlot_id and o.prodlot_id.name or ''|x}</Data></Cell>
                % if o.state == 'done' and o.expired_date and isDate(o.expired_date):
                <Cell ss:StyleID="sShortDate"><Data ss:Type="DateTime">${o.expired_date|n}T00:00:00.000</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                % endif
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${userCompany['instance_id'].name|x}</Data></Cell>
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
                <ActiveRow>13</ActiveRow>
            </Pane>
        </Panes>
        <ProtectObjects>False</ProtectObjects>
        <ProtectScenarios>False</ProtectScenarios>
    </WorksheetOptions>
 </ss:Worksheet>
 % endfor

</Workbook>
