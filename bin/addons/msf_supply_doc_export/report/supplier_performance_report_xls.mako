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

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font ss:Size="13" ss:Bold="1" />
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="13" ss:Bold="1" />
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="line_header_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Lines -->
    <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#0"/>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#0"/>
    </Style>
    <Style ss:ID="line_right_nb">
        <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="Short Date" />
    </Style>
 </Styles>

% for r in objects:
<ss:Worksheet ss:Name="${_('Supplier Perf.')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Supplier
        <Column ss:AutoFitWidth="1" ss:Width="130.0" />
        ## PO Details
        <Column ss:AutoFitWidth="1" ss:Width="240.0" />
        ## PO Reference
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## IN Reference
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## SI Reference
        <Column ss:AutoFitWidth="1" ss:Width="130.0" />
        ## Line number
        <Column ss:AutoFitWidth="1" ss:Width="55.0" />
        ## Product Code
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="300.0" />
        ## Status
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Qty Ordered
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Qty Received
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Currency
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Catalogue Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## PO Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## IN Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## SI Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## SI Unit Price after Discount
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Discrepancy IN to PO
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Discrepancy SI to PO
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## SI Unit Price Discounted Amount (Before vs After Discount)
        <Column ss:AutoFitWidth="1" ss:Width="140.0" />
        ## Catalogue Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## PO Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## IN Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## SI Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## SI Unit Price after Discount (functional)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Discrepancy IN to PO (functional)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Discrepancy SI to PO (functional)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## SI Unit Price Discounted Amount (Before vs After Discount) (functional)
        <Column ss:AutoFitWidth="1" ss:Width="140.0" />
        ## PO Creation Date
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Validation Date
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Confirmation Date
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Requested Delivery Date (RDD)
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Estimated Delivery Date (EDD)
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Confirmed Delivery Date (CDD)
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Physical Reception Date
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Order Type
        <Column ss:AutoFitWidth="1" ss:Width="140.0" />
        ## Customer
        <Column ss:AutoFitWidth="1" ss:Width="165.0" />
        ## Days to validate
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Days to confirm
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Delay b/w actual delivery and CDD (days)
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Delay b/w actual delivery and RDD (days)
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Internal Lead Time (days PO creation to reception)
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Actual Supplier Lead Time (days PO validation to reception)
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Configured Supplier Lead Time
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Discrepancy b/w actual Lead Time and Supplier Lead Time
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('DB/Instance name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.company_id and r.company_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            % if isDateTime(r.report_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.report_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Supplier name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.partner_id and r.partner_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Supplier Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.pt_text or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Purchase Order Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.ot_text or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('From')|x}</Data></Cell>
            % if isDate(r.date_from):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.date_from)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('To')|x}</Data></Cell>
            % if isDate(r.date_to):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.date_to)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>

        <Row></Row>

        ## DATA HEADERS
        <%
        headers_list = [
            _('Supplier'),
            _('PO Details'),
            _('PO Reference'),
            _('IN Reference'),
            _('SI Reference'),
            _('Line number'),
            _('Product Code'),
            _('Product Description'),
            _('Status'),
            _('Qty Ordered'),
            _('Qty Received'),
            _('Currency'),
            _('Catalogue Unit Price'),
            _('PO Unit Price'),
            _('IN Unit Price'),
            _('SI Unit Price'),
            _('SI Unit Price after Discount'),
            _('Discrepancy IN to PO'),
            _('Discrepancy SI to PO'),
            _('SI Unit Price Discounted Amount (Before vs After Discount)'),
            _('Catalogue Unit Price (functional)'),
            _('PO Unit Price (functional)'),
            _('IN Unit Price (functional)'),
            _('SI Unit Price (functional)'),
            _('SI Unit Price after Discount (functional)'),
            _('Discrepancy IN to PO (functional)'),
            _('Discrepancy SI to PO (functional)'),
            _('SI Unit Price Discounted Amount (Before vs After Discount) (functional)'),
            _('PO Creation Date'),
            _('Validation Date'),
            _('Confirmation Date'),
            _('Requested Delivery Date (RDD)'),
            _('Estimated Delivery Date (EDD)'),
            _('Confirmed Delivery Date (CDD)'),
            _('Physical Reception Date'),
            _('Order Type'),
            _('Customer'),
            _('Days to validate'),
            _('Days to confirm'),
            _('Delay b/w actual delivery and CDD (days)'),
            _('Delay b/w actual delivery and RDD (days)'),
            _('Internal Lead Time (days PO creation to reception)'),
            _('Actual Supplier Lead Time (days PO validation to reception)'),
            _('Configured Supplier Lead Time'),
            _('Discrepancy b/w actual Lead Time and Supplier Lead Time'),
        ]
        %>
        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for line in getLines(r):
            <Row ss:Height="12.0">
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['partner_name']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['details']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['po_name']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['in_ref']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['si_ref']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['line_number']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['p_code'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['p_name']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${getSelValue('purchase.order.line', 'state', line['state'])|x}</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['qty_ordered'] or 0|x}</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['qty_received'] or 0|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['currency']|x}</Data></Cell>

                ## Normal Prices
                % if line['cat_unit_price'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['cat_unit_price'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['po_unit_price'] or 0|x}</Data></Cell>
                % if line['in_unit_price'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['in_unit_price'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['si_unit_price'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['si_unit_price'] or 0|x}</Data></Cell>
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['si_discount_price'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['discrep_in_po'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['discrep_in_po'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['discrep_si_po'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['discrep_si_po'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_right"><Data ss:Type="String">${line['discrep_si_discount'] != '-' and line['discrep_si_discount'] or ''|x}</Data></Cell>

                ## Functional Prices
                % if line['func_cat_unit_price'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['func_cat_unit_price'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['func_po_unit_price'] or 0|x}</Data></Cell>
                % if line['func_in_unit_price'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['func_in_unit_price'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['func_si_unit_price'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['func_si_unit_price'] or 0|x}</Data></Cell>
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['func_si_discount_price'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['func_discrep_in_po'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['func_discrep_in_po'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['func_discrep_si_po'] != '-':
                <Cell ss:StyleID="line_right_nb"><Data ss:Type="Number">${line['func_discrep_si_po'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_right"><Data ss:Type="String">${line['func_discrep_si_discount'] != '-' and line['func_discrep_si_discount'] or ''|x}</Data></Cell>

                ## Dates
                % if line['po_crea_date'] and isDateTime(line['po_crea_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['po_crea_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif

                % if line['po_vali_date'] and isDate(line['po_vali_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['po_vali_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['po_conf_date'] and isDate(line['po_conf_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['po_conf_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['po_rdd'] and isDate(line['po_rdd']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['po_rdd'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['po_rdd'] and isDate(line['po_edd']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['po_edd'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['po_cdd'] and isDate(line['po_cdd']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['po_cdd'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['in_receipt_date'] and isDateTime(line['in_receipt_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['in_receipt_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif

                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['order_type']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['customer']|x}</Data></Cell>

                ## Days
                % if line['days_crea_vali'] != '-':
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['days_crea_vali'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['days_crea_conf'] != '-':
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['days_crea_conf'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['days_cdd_receipt'] != '-':
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['days_cdd_receipt'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['days_rdd_receipt'] != '-':
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['days_rdd_receipt'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['days_crea_receipt'] != '-':
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['days_crea_receipt'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line['days_vali_receipt'] != '-':
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['days_vali_receipt'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['partner_lt'] or 0|x}</Data></Cell>
                % if line['discrep_lt_act_theo'] != '-':
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['discrep_lt_act_theo'] or 0|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
            </Row>
        % endfor

    </Table>
</ss:Worksheet>
% endfor
</Workbook>
