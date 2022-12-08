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
    <!-- Header title for EACH page/sheet @ the top -->
    <Style ss:ID="title">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:Indent="0"/>
      <Font ss:Bold="1"/>
    </Style>
    <!-- Labels for information in header part of each page/sheet -->
    <Style ss:ID="header_part">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="header_part_side"> <!-- borders on the sides only -->
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="header_part_center">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="header_part_number">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="Standard"/>
    </Style>
    <Style ss:ID="header_part_integer">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="#,##0"/>
    </Style>
    <Style ss:ID="column_headers">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Bold="1" ss:Size="11"/>
      <Interior ss:Color="#ffff66" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="analytic_header">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Font ss:Size="11"/>
      <Interior ss:Color="#ffff66" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="distribution_header">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
      <Font ss:Size="11"/>
      <Interior ss:Color="#b2b2b2" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="direct_invoice_header">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
      <Font ss:Size="11"/>
      <Interior ss:Color="#8cbb3c" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="left_bold">
      <Font ss:Bold="1"/>
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Blue left string for analytic distribution lines -->
    <Style ss:ID="ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <!-- Blue left string for analytic distribution lines -->
    <Style ss:ID="blue_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <!-- Grey left string for analytic distribution lines -->
    <Style ss:ID="grey_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#9E9E9E"/>
    </Style>
    <!-- Purple left string for analytic distribution lines -->
    <Style ss:ID="purple_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#8b0082"/>
    </Style>
    <!-- Red left string for analytic distribution lines -->
    <Style ss:ID="red_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#ff0000"/>
    </Style>
    <!-- Green left string for analytic distribution lines -->
    <Style ss:ID="green_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#006400"/>
    </Style>
    <Style ss:ID="centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Font ss:Bold="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Only used for register lines account's code -->
    <Style ss:ID="number_centre_bold">
      <Font ss:Bold="1"/>
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="0"/>
    </Style>
    <Style ss:ID="number_centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="0"/>
    </Style>
    <Style ss:ID="ana_centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff" ss:Bold="1"/>
    </Style>
    <Style ss:ID="date">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Short Date"/>
      <Font ss:Bold="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="amount_bold">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Font ss:Bold="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Initially used for invoice line number -->
    <Style ss:ID="text_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="@"/>
    </Style>
    <!-- For Amount IN/OUT in register lines -->
    <Style ss:ID="amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in blue font color) -->
    <Style ss:ID="ana_amount">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in blue font color) -->
    <Style ss:ID="blue_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in grey font color) -->
    <Style ss:ID="grey_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#9E9E9E"/>
    </Style>
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in purple font color) -->
    <Style ss:ID="purple_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#8b0082"/>
    </Style>
    <!-- Formated Number in red for analytic distribution amounts -->
    <Style ss:ID="red_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#ff0000"/>
    </Style>
    <!-- Formated Number in green for analytic distribution amounts -->
    <Style ss:ID="green_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#006400"/>
    </Style>
    <!-- Formated Number (without thousand separator) for analytic distribution amounts (in blue font color) -->
    <Style ss:ID="ana_percent">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
      <NumberFormat ss:Format="Fixed"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <Style ss:ID="short_date2">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
      <NumberFormat ss:Format="Short Date"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="invoice_header">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Grey color for deleted entries, manual entries, DP Reversals, Payable Entries... -->
    <Style ss:ID="grey_left_bold">
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_left">
      <Font ss:Color="#9E9E9E"/>
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_amount_bold">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_date">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Short Date"/>
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
  </Styles>
% for o in objects:
  <Worksheet ss:Name="${o.period_id.name|x}, ${o.journal_id.code|x}">
    <Names>
      <NamedRange ss:Name="Print_Titles" ss:RefersTo="=!R9"/>
    </Names>
    <Table>
      <Column ss:Width="93.75"/>
      <Column ss:Width="80.75" ss:Span="1"/>
      <Column ss:Width="132.75"/>
      <Column ss:Width="213.75"/>
      <Column ss:Width="98.25"/>
      <Column ss:Width="150.75"/>
      % if o.journal_id.type == 'cheque':
        <Column ss:Width="65"/>
      % endif
      <Column ss:Width="92.25"/>
      <Column ss:Width="134.25"/>
      <Column ss:Width="60"/>
      <Column ss:Width="66"/>
      <Column ss:Width="30.75"/>
      <Column ss:Width="72" ss:Span="3"/>
      <Column ss:Width="36" ss:Span="1"/>
      <Row ss:Height="19.3039">
        <Cell ss:MergeAcross="3" ss:StyleID="title">
          <Data ss:Type="String">${o.journal_id.type == 'cash' and _('CASH REGISTER FULL REPORT') or o.journal_id.type == 'bank' and _('BANK REGISTER FULL REPORT') or o.journal_id.type == 'cheque' and _('CHEQUE REGISTER FULL REPORT') or ''|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
      </Row>
      <%
      if o.journal_id.type == 'cash':
          closing_bal_title = _('CashBox balance:')
          closing_bal = o.balance_end_cash or 0.0
          calculated_bal = o.msf_calculated_balance or 0.0
      else:
          if o.journal_id.type == 'bank':
              closing_bal_title = _('Bank Statement balance:')
          else:
              closing_bal_title = _('Closing balance:')
          closing_bal = o.balance_end_real or 0.0
          calculated_bal = o.balance_end or 0.0
      %>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Report Date:')|x}</Data>
        </Cell>
        <Cell ss:StyleID="short_date2" >
          <Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data>
        </Cell>
        <Cell ss:StyleID="header_part_side"/>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Starting balance:')|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part_number">
          <Data ss:Type="Number">${o.balance_start or 0.0|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="12.6425">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Prop. Instance:')|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${( company.instance_id and company.instance_id.code or '')|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part_side"/>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${closing_bal_title|x} </Data>
        </Cell>
        <Cell ss:StyleID="header_part_number">
          <Data ss:Type="Number">${closing_bal|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Code:')}</Data>
        </Cell>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${o.journal_id.code|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part_side"/>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Calculated balance:')|x} </Data>
        </Cell>
        <Cell ss:StyleID="header_part_number">
          <Data ss:Type="Number">${calculated_bal|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Period:')|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${o.period_id and o.period_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part_side"/>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('State:')|x} </Data>
        </Cell>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${o.state and getSel(o, 'state') or ''|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Currency:')|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${o.currency and o.currency.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="header_part_side"/>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${_('Number of entries:')|x} </Data>
        </Cell>
        <Cell ss:StyleID="header_part_integer">
          <Data ss:Type="Number">${getNumberOfEntries(o)|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
      </Row>
      <Row ss:AutoFitHeight="0" ss:Height="29.1118">
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Entry type')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Doc Date')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Post Date')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Sequence')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Desc')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Ref')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Free Ref')|x}</Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="column_headers">
            <Data ss:Type="String">${_('Chk num')|x}</Data>
          </Cell>
        % endif
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Account')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Third Parties')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('IN')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('OUT')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Dest')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('CC')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('FP')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Free 1')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Free 2')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Rec?')|x}</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">${_('Status')|x}</Data>
        </Cell>
      </Row>
<% tot_line = len(o.line_ids) %>
<% nbloop = 0 %>
% for line in sorted(o.line_ids, key=lambda x: x.sequence_for_reference):

      <% nbloop += 1 %>
      <% update_percent(nbloop, tot_line) %>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${ getEntryType(line) |x}</Data>
        </Cell>
        % if isDate(line.document_date):
        <Cell ss:StyleID="date">
          <Data ss:Type="DateTime">${line.document_date|n}T00:00:00.000</Data>
        </Cell>
        % else:
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % endif
        % if isDate(line.date):
        <Cell ss:StyleID="date">
          <Data ss:Type="DateTime">${line.date|n}T00:00:00.000</Data>
        </Cell>
        % else:
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % endif
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.sequence_for_reference or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${getRegRef(line) or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="left_bold">
            <Data ss:Type="String">${line.cheque_number}</Data>
          </Cell>
        % endif
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.account_id.code + ' ' + line.account_id.name|x}</Data>
        </Cell>
        <%
        third_party = ''
        if line.partner_id:
            third_party = line.partner_id.name
        elif line.employee_id:
            third_party = line.employee_id.name
        elif line.transfer_journal_id:
            third_party = line.transfer_journal_id.code
        %>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${third_party|x}</Data>
        </Cell>
        <Cell ss:StyleID="amount_bold">
          <Data ss:Type="Number">${line.amount_in or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="amount_bold">
          <Data ss:Type="Number">${line.amount_out or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.reconciled and 'X' or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.state and getSel(line, 'state') or ''|x}</Data>
        </Cell>
      </Row>

<!-- if it is a Down Payment that has been partially or totally reversed -->
<% dp_reversals_ml = getDownPaymentReversals(line) %>
% for dp_reversal_ml in sorted(dp_reversals_ml, key=lambda x: x.move_id.name):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('REV - Down Payment')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${dp_reversal_ml.move_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- DESC -->
          <Data ss:Type="String">${dp_reversal_ml.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- REF -->
          <Data ss:Type="String">${dp_reversal_ml.ref or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
    </Row>
% endfor

<!-- if there are Trade Payable Entries (automatically generated) - until US-3874 -->
<% partner_move_ids = line.partner_move_ids or False %>
% if partner_move_ids:
% for partner_move_id in sorted(partner_move_ids, key=lambda x: x.name):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('Payable Entry')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${partner_move_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- DESC -->
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- REF -->
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
    </Row>
% endfor
% endif

<!-- Direct invoice and invoice that comes from a PL (in a cash return) -->
<% move_lines = [] %>
<% invoice_move = line.invoice_id and line.invoice_id.move_id or line.advance_invoice_move_id %>
% if invoice_move:
<% move_lines = getMoveLines([invoice_move], line) %>
% elif line.imported_invoice_line_ids:
<% move_lines = getImportedMoveLines([ml for ml in line.imported_invoice_line_ids], line) %>
% elif line.direct_invoice_move_id:
<% move_lines = getMoveLines([line.direct_invoice_move_id], line) %>
% endif

% for inv_line in move_lines:
      <Row>
        <Cell ss:Index="4" ss:StyleID="text_left">
          <Data ss:Type="String">${hasattr(inv_line, 'line_number') and inv_line.line_number or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.move_id and inv_line.move_id.name or hasattr(inv_line, 'reference') and inv_line.reference or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${getFreeRef(inv_line) or ''|x}</Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        % endif
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.account_id and inv_line.account_id.code + ' ' + inv_line.account_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="amount">
          <Data ss:Type="Number">${hasattr(inv_line, 'amount_currency') and inv_line.amount_currency or 0.0}</Data>
        </Cell>
      </Row>
% if hasattr(inv_line, 'analytic_lines'):
% for ana_line in getAnalyticLines([x.id for x in inv_line.analytic_lines]):
<%
line_color = 'blue'
if ana_line.is_reallocated:
    line_color = 'purple'
elif ana_line.is_reversal:
    line_color = 'green'
elif ana_line.last_corrected_id:
    line_color = 'red'
endif
%>
      <Row>
        % if o.journal_id.type == 'cheque':
          <Cell ss:Index="9" ss:StyleID="${line_color}_ana_left">
        % else:
          <Cell ss:Index="8" ss:StyleID="${line_color}_ana_left">
        % endif
          <Data ss:Type="String">${ana_line.general_account_id.code + ' ' + ana_line.general_account_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.partner_txt or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_amount">
          <Data ss:Type="Number">${ana_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.destination_id and ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.cost_center_id and ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${not ana_line.free_account and ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.1.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.2.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${(ana_line.is_reallocated and _('Corrected')) or (ana_line.is_reversal and _('Reversal')) or ''}</Data>
        </Cell>
      </Row>
% endfor
% endif
% endfor

<!-- Display analytic lines linked to this register line -->
<!-- since US-6527: each return line has its own JE: US-3612 and BKLG-60 no more needed here -->
<%
a_lines = False
if not line.invoice_id and not line.imported_invoice_line_ids and line.fp_analytic_lines:
    a_lines = line.fp_analytic_lines
%>
% if a_lines:
% for ana_line in [x for x in sorted(a_lines, key=lambda x: x.id) if not x.free_account]:
<%
line_color = 'blue'
if ana_line.is_reallocated:
    line_color = 'purple'
elif ana_line.is_reversal:
    line_color = 'green'
elif ana_line.last_corrected_id:
    line_color = 'red'
endif
%>
      <Row>
        % if o.journal_id.type == 'cheque':
          <Cell ss:Index="9" ss:StyleID="${line_color}_ana_left">
        % else:
          <Cell ss:Index="8" ss:StyleID="${line_color}_ana_left">
        % endif
          <Data ss:Type="String">${ana_line.general_account_id.code + ' ' + ana_line.general_account_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.partner_txt or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_amount">
          <Data ss:Type="Number">${ana_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.destination_id and ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.cost_center_id and ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${(ana_line.is_reallocated and _('Corrected')) or (ana_line.is_reversal and _('Reversal')) or ''}</Data>
        </Cell>
      </Row>
% endfor
% endif

<!-- Display analytic lines Free 1 and Free 2 linked to this register line -->
<%
a_lines = False
if not line.invoice_id and not line.imported_invoice_line_ids and line.free_analytic_lines:
    a_lines = line.free_analytic_lines
%>
% if a_lines:
% for ana_line in [ x for x in sorted(a_lines, key=lambda x: x.id) if x.free_account]:
<%
line_color = 'blue'
if ana_line.is_reallocated:
    line_color = 'purple'
elif ana_line.is_reversal:
    line_color = 'green'
elif ana_line.last_corrected_id:
    line_color = 'red'
endif
%>
      <Row>
        % if o.journal_id.type == 'cheque':
          <Cell ss:Index="9" ss:StyleID="${line_color}_ana_left">
        % else:
          <Cell ss:Index="8" ss:StyleID="${line_color}_ana_left">
        % endif
          <Data ss:Type="String">${ana_line.general_account_id.code + ' ' + ana_line.general_account_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.partner_txt or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_amount">
          <Data ss:Type="Number">${ana_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.1.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.2.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${(ana_line.is_reallocated and _('Corrected')) or (ana_line.is_reversal and _('Reversal')) or ''}</Data>
        </Cell>
      </Row>
% endfor
% endif

<!-- AUTOMATED ENTRIES linked to the register line -->
<!-- Note: they are booked on accounts without AD -->
<% partner_move_line_ids = line.partner_move_line_ids or [] %>
% if partner_move_line_ids:
    % for partner_aml in sorted(partner_move_line_ids, key=lambda x: x.partner_txt):
        <Row ss:Height="14.5134">
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${_('Automated Entry')|x}</Data>
            </Cell>
            % if isDate(partner_aml.document_date):
              <Cell ss:StyleID="date">
                <Data ss:Type="DateTime">${partner_aml.document_date|n}T00:00:00.000</Data>
              </Cell>
            % else:
              <Cell ss:StyleID="left_bold">
                <Data ss:Type="String"></Data>
              </Cell>
            % endif
            % if isDate(partner_aml.date):
              <Cell ss:StyleID="date">
                <Data ss:Type="DateTime">${partner_aml.date|n}T00:00:00.000</Data>
              </Cell>
            % else:
              <Cell ss:StyleID="left_bold">
                <Data ss:Type="String"></Data>
              </Cell>
            % endif
            <Cell ss:StyleID="left_bold">
              <!-- SEQUENCE -->
              <Data ss:Type="String">${partner_aml.move_id.name|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${partner_aml.name|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${partner_aml.ref or ''|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String"></Data>
            </Cell>
            % if o.journal_id.type == 'cheque':
              <Cell ss:StyleID="left_bold">
                <Data ss:Type="String"></Data>
              </Cell>
            % endif
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${"%s %s" % (partner_aml.account_id.code, partner_aml.account_id.name)|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${partner_aml.partner_txt or ''|x}</Data>
            </Cell>
            <Cell ss:StyleID="amount_bold">
              <Data ss:Type="Number">${partner_aml.credit_currency or 0.0}</Data>
            </Cell>
            <Cell ss:StyleID="amount_bold">
              <Data ss:Type="Number">${partner_aml.debit_currency or 0.0}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${_('FALSE')|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${_('FALSE')|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${_('FALSE')|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String"></Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String"></Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${partner_aml.reconcile_id and 'X' or ''|x}</Data>
            </Cell>
            <Cell ss:StyleID="left_bold">
              <Data ss:Type="String">${partner_aml.move_id.state and getSel(partner_aml.move_id, 'state') or ''|x}</Data>
            </Cell>
        </Row>
    % endfor
% endif

% endfor

<!-- MANUAL ENTRIES -->
<% manual_amls = getManualAmls(o) %>
% for aml in sorted(manual_amls, key=lambda x: x.move_id.name):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('Manual Journal Entry')|x}</Data>
        </Cell>
        % if isDate(aml.document_date):
          <Cell ss:StyleID="grey_date">
            <Data ss:Type="DateTime">${aml.document_date|n}T00:00:00.000</Data>
          </Cell>
        % else:
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        % if isDate(aml.date):
          <Cell ss:StyleID="grey_date">
            <Data ss:Type="DateTime">${aml.date|n}T00:00:00.000</Data>
          </Cell>
        % else:
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${aml.move_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.ref or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${"%s %s" % (aml.account_id.code, aml.account_id.name)|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.partner_txt or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">${aml.credit_currency or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">${aml.debit_currency or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.reconcile_id and 'X' or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.move_id.state and getSel(aml.move_id, 'state') or ''|x}</Data>
        </Cell>
    </Row>

    <!-- ANALYTIC LINES linked to this manual Journal Item -->
    <%
    manual_aal_lines = getManualAjis(aml)
    %>
    % for manual_aal in sorted(manual_aal_lines, key=lambda x: x.id):
        <%
        aal_color = getManualAalColor(manual_aal)
        %>
        <Row>
          <%
          cell_index = o.journal_id.type == 'cheque' and 9 or 8
          %>
          <Cell ss:Index="${cell_index}" ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${"%s %s" % (manual_aal.general_account_id.code, manual_aal.general_account_id.name)|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${manual_aal.partner_txt or ''|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String"></Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_amount">
            <Data ss:Type="Number">${manual_aal.amount_currency}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${manual_aal.destination_id and manual_aal.destination_id.code or ''|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${manual_aal.cost_center_id and manual_aal.cost_center_id.code or ''|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${manual_aal.account_id and manual_aal.account_id.code or ''|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String"></Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String"></Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${(manual_aal.is_reallocated and _('Corrected')) or (manual_aal.is_reversal and _('Reversal')) or ''|x}</Data>
          </Cell>
        </Row>
    % endfor

    <!-- FREE1/FREE2 LINES linked to this manual Journal Item -->
    <%
    manual_free_lines = getManualFreeLines(aml)
    %>
    % for free_line in sorted(manual_free_lines, key=lambda x: x.id):
      <%
      aal_color = getManualAalColor(free_line)
      %>
      <Row>
        <%
        cell_index = o.journal_id.type == 'cheque' and 9 or 8
        %>
        <Cell ss:Index="${cell_index}" ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${"%s %s" % (free_line.general_account_id.code, free_line.general_account_id.name)|x}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${free_line.partner_txt or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_amount">
          <Data ss:Type="Number">${free_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${free_line.distrib_line_id and free_line.distrib_line_id._name == 'free.1.distribution.line' and \
                                   free_line.account_id and free_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${free_line.distrib_line_id and free_line.distrib_line_id._name == 'free.2.distribution.line' and \
                                   free_line.account_id and free_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${(free_line.is_reallocated and _('Corrected')) or (free_line.is_reversal and _('Reversal')) or ''|x}</Data>
        </Cell>
      </Row>
    % endfor
% endfor

<!-- DELETED ENTRIES -->
% for deleted_line in sorted(o.deleted_line_ids, key=lambda x: x.sequence):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('Deleted Entry')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${deleted_line.sequence or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
    </Row>
% endfor

    </Table>
    <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
      <PageSetup>
        <Layout x:Orientation="Landscape" x:CenterHorizontal="1" x:CenterVertical="0"/>
        <Header x:Margin="0"/>
        <Footer x:Margin="0"/>
        <PageMargins x:Bottom="0.40" x:Left="0.40" x:Right="0.40" x:Top="0.40"/>
      </PageSetup>
      <FitToPage/>
      <Print>
        <FitHeight>0</FitHeight>
        <ValidPrinterInfo/>
        <PaperSizeIndex>9</PaperSizeIndex>
        <Scale>60</Scale>
      </Print>
      <PageBreakZoom>70</PageBreakZoom>
      <DoNotDisplayGridlines/>
    </WorksheetOptions>
  </Worksheet>
% endfor
</Workbook>
