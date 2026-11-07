# Exporta un .docx a PDF con Word, para revisar cómo queda.
param([string]$Docx, [string]$Pdf)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $d = $word.Documents.Open((Resolve-Path $Docx).Path, $false, $true)
    $d.ExportAsFixedFormat($Pdf, 17)
    "paginas: " + $d.ComputeStatistics(2)
    $d.Close($false)
} finally { $word.Quit() }
