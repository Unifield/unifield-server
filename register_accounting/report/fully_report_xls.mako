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
  <Created>${time.strftime('%Y-%m-%dT%H:%M:%SZ')|n}</Created>
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
    <Style ss:ID="Default" ss:Name="Default"/>
    <Style ss:ID="Result" ss:Name="Result">
      <Font ss:Bold="1" ss:Italic="1" ss:Underline="Single"/>
    </Style>
    <Style ss:ID="Result2" ss:Name="Result2">
      <Font ss:Bold="1" ss:Italic="1" ss:Underline="Single"/>
    </Style>
    <Style ss:ID="Heading" ss:Name="Heading">
      <Font ss:Bold="1" ss:Italic="1" ss:Size="16"/>
    </Style>
    <Style ss:ID="Heading1" ss:Name="Heading1">
      <Font ss:Bold="1" ss:Italic="1" ss:Size="16"/>
    </Style>
    <Style ss:ID="co1"/>
    <Style ss:ID="co2"/>
    <Style ss:ID="co3"/>
    <Style ss:ID="co4"/>
    <Style ss:ID="co5"/>
    <Style ss:ID="co6"/>
    <Style ss:ID="co7"/>
    <Style ss:ID="co8"/>
    <Style ss:ID="co9"/>
    <Style ss:ID="co10"/>
    <Style ss:ID="co11"/>
    <Style ss:ID="co12"/>
    <Style ss:ID="co13"/>
    <Style ss:ID="co14"/>
    <Style ss:ID="ta1"/>
    <Style ss:ID="title">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:Indent="0"/>
    </Style>
    <Style ss:ID="pop">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    </Style>
    <Style ss:ID="ce2"/>
    <Style ss:ID="column_headers">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="O.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="O.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="O.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="O.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Bold="1" ss:Italic="1" ss:Size="11"/>
      <Interior ss:Color="#ffff66" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="ce4">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
    </Style>
    <Style ss:ID="ce5">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
    </Style>
    <Style ss:ID="ce6">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <NumberFormat ss:Format="Short Date"/>
    </Style>
    <Style ss:ID="ce7">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
    </Style>
    <Style ss:ID="ce8">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
      <NumberFormat ss:Format="Fixed"/>
    </Style>
    <Style ss:ID="ce9">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Font ss:Bold="1" ss:Italic="1" ss:Size="11"/>
    </Style>
    <Style ss:ID="short_date2">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
      <NumberFormat ss:Format="Short Date"/>
    </Style>
  </Styles>
  <Worksheet ss:Name="Info">
    <Table ss:StyleID="ta1">
      <Column ss:Width="105.1937"/>
      <Column ss:Width="64.0063"/>
      <Row ss:Height="12.1039">
        <Cell ss:MergeAcross="3" ss:StyleID="title">
          <Data ss:Type="String">REGISTER REPORT</Data>
        </Cell>
        <Cell ss:Index="2"/>
      </Row>
      <Row ss:Height="12.8126">
        <Cell ss:Index="2"/>
      </Row>
      <Row ss:Height="12.1039">
        <Cell>
          <Data ss:Type="String">Report Date:</Data>
        </Cell>
        <Cell ss:StyleID="short_date2" >
          <Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data>
        </Cell>
      </Row>
      <Row ss:Height="12.6425">
        <Cell>
          <Data ss:Type="String">Prop. Instance</Data>
        </Cell>
        <Cell ss:StyleID="pop">
          <Data ss:Type="String">${( company.instance_id and company.instance_id.code or '')|x}</Data>
        </Cell>
      </Row>
    </Table>
    <WorksheetOptions/>
  </Worksheet>
% for o in objects:
  <Worksheet ss:Name="${o.period_id.name}, ${o.journal_id.code}">
    <Table ss:StyleID="ta1">
      <Column ss:Width="95.9527"/>
      <Column ss:Width="78.2079"/>
      <Column ss:Width="64.2898"/>
      <Column ss:Width="103.663"/>
      <Column ss:Width="95.9527"/>
      <Column ss:Width="71.263"/>
      <Column ss:Width="166.9606"/>
      <Column ss:Width="115.9937"/>
      <Column ss:Width="66.6142"/>
      <Column ss:Width="79.7386"/>
      <Column ss:Width="58.9039"/>
      <Column ss:Width="97.5118"/>
      <Column ss:Width="43.4551"/>
      <Column ss:Span="1010" ss:Width="64.0063"/>
      <Row ss:Height="19.3039">
        <Cell ss:MergeAcross="3" ss:StyleID="title">
          <Data ss:Type="String">${o.journal_id.type == 'cash' and _('CASH REGISTER') or o.journal_id.type == 'bank' and _('BANK REGISTER') or o.journal_id.type == 'cheque' and _('CHEQUE REGISTER') or ''} REPORT</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
      </Row>
      <Row ss:AutoFitHeight="0" ss:Height="29.1118">
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Specific type</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Doc. Date</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Post. Date</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Sequence</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Desc</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Ref</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Account</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Third Parties</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Amount IN</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Amount OUT</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Currency</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Amt. Reconciled</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Status</Data>
        </Cell>
      </Row>
% for line in o.line_ids:
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="ce4">
          <Data ss:Type="String">${line.direct_invoice and _('Direct Invoice') or line.from_cash_return and _('Cash Return') or line.is_down_payment and _('Down Payment') and line.from_import_cheque_id and _('Cheque Import') or (line.transfer_journal_id and not line.is_transfer_with_change and _('Transfer')) or (line.transfer_journal_id and line.is_transfer_with_change and _('Transfer with change')) or line.imported_invoice_line_ids and _('Direct Payment') or _('Normal')}</Data>
        </Cell>
        <Cell ss:StyleID="ce6">
          <Data ss:Type="DateTime">${line.document_date}</Data>
        </Cell>
        <Cell ss:StyleID="ce6">
          <Data ss:Type="DateTime">${line.date}</Data>
        </Cell>
        <Cell ss:StyleID="ce4">
          <Data ss:Type="String">${line.sequence_for_reference or ''}</Data>
        </Cell>
        <Cell ss:StyleID="ce4">
          <Data ss:Type="String">${line.name or ''}</Data>
        </Cell>
        <Cell ss:StyleID="ce5">
          <Data ss:Type="String">${line.ref or ''}</Data>
        </Cell>
        <Cell ss:StyleID="ce4">
          <Data ss:Type="String">${line.account_id.code}</Data>
        </Cell>
        <Cell ss:StyleID="ce4">
          <Data ss:Type="String">${(line.partner_id and line.partner_id.name or line.transfer_journal_id and line.transfer_journal_id.name or line.employee_id and line.employee_id.name or '')}</Data>
        </Cell>
        <Cell ss:StyleID="ce8">
          <Data ss:Type="Number">${line.amount_in or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="ce8">
          <Data ss:Type="Number">${line.amount_out or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="ce5">
          <Data ss:Type="String">${line.currency_id and line.currency_id.name or ''}</Data>
        </Cell>
        <Cell ss:StyleID="ce5">
          <Data ss:Type="String">${line.reconciled and 'X' or ''}</Data>
        </Cell>
        <Cell ss:StyleID="ce5">
          <Data ss:Type="String">${line.state and getSel(line, 'state') or ''}</Data>
        </Cell>
      </Row>
% endfor
    </Table>
    <WorksheetOptions/>
  </Worksheet>
% endfor
</Workbook>
