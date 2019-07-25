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
    <Style ss:ID="line_left0">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="10"/>
    </Style>
    <Style ss:ID="line_right0">
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
    <Style ss:ID="line_left1">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="10"/>
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="line_right1">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="10"/>
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
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
    <Style ss:ID="sShortDate0">
        <NumberFormat ss:Format="Short Date"/>
        <Alignment ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="sShortDate1">
        <NumberFormat ss:Format="Short Date"/>
        <Alignment ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
    </Style>
 </Styles>

 % for r in objects:
 <ss:Worksheet ss:Name="${_('Loan Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Product Code
        <Column ss:AutoFitWidth="1" ss:Width="102.5" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="301.5" />
        ## Order Type
        <Column ss:AutoFitWidth="1" ss:Width="54.0" />
        ## Movement Date
        <Column ss:AutoFitWidth="1" ss:Width="72.25" />
        ## Move Ref.
        <Column ss:AutoFitWidth="1" ss:Width="105.75" />
        ## Partner
        <Column ss:AutoFitWidth="1" ss:Width="135.75" />
        ## Partner Type
        <Column ss:AutoFitWidth="1" ss:Width="65.5" />
        ## Instance
        <Column ss:AutoFitWidth="1" ss:Width="172.25"  />
        ## Qty In
        <Column ss:AutoFitWidth="1" ss:Width="74.25" />
        ## Qty Out
        <Column ss:AutoFitWidth="1" ss:Width="74.25"  />
        ## Qty Balance
        <Column ss:AutoFitWidth="1" ss:Width="69.25"  />
        ## PO/FO Ref.
        <Column ss:AutoFitWidth="1" ss:Width="282.0"  />
        ## Origin Ref.
        <Column ss:AutoFitWidth="1" ss:Width="152.0"  />
        ## Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="57.25"  />
        ## Currency
        <Column ss:AutoFitWidth="1" ss:Width="45.75"  />
        ## Total Value
        <Column ss:AutoFitWidth="1" ss:Width="62.25"  />
        ## Status
        <Column ss:AutoFitWidth="1" ss:Width="42.25"  />

        <%
            headers_list = [
                _('Code'),
                _('Description'),
                _('Order Type'),
                _('Movement Date'),
                _('Move Ref.'),
                _('Partner'),
                _('Partner Type'),
                _('Instance'),
                _('Qty In'),
                _('Qty Out'),
                _('Qty Balance'),
                _('PO/FO Ref.'),
                _('Origin Ref.'),
                _('Unit Price'),
                _('Currency'),
                _('Total Value'),
                _('Status'),
            ]
        %>

        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        <% i = 0 %>
        % for flow in getMoves(r):
           <% i = 1 - i %>
           % for o in flow:
            <Row ss:Height="14.25">
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${o.product_id.default_code|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${o.product_id.name|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${o.reason_type_id.name|x}</Data></Cell>
                %if o.date and isDateTime(o.date):
                <Cell ss:StyleID="sShortDate${i}"><Data ss:Type="DateTime">${o.date[:10]|n}T${o.date[-8:]|n}.000</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${o.picking_id.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${o.partner_id.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${getSel(o.partner_id, 'partner_type') or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${getUserCompany()['instance_id'].name|x}</Data></Cell>
                % if isQtyOut(o):
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="Number">${getQty(o)|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="Number">${getQty(o)|x}</Data></Cell>
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="String"></Data></Cell>
                % endif
                % if o.balance:
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="Number">${o.balance|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="String"></Data></Cell>
                %endif
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${o.origin|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${getFirstSplitOnUnderscore(o.purchase_line_id.sync_order_line_db_id) or getFirstSplitOnUnderscore(o.sale_line_id.sync_order_line_db_id) or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="Number">${computeCurrency(o)|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${getUserCompany()['currency_id'].name|x}</Data></Cell>
                <Cell ss:StyleID="line_right${i}"><Data ss:Type="Number">${computeCurrency(o) * getQty(o)|x}</Data></Cell>
                <Cell ss:StyleID="line_left${i}"><Data ss:Type="String">${getSel(o, 'status')|x}</Data></Cell>
            </Row>
            % endfor
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
