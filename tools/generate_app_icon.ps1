Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $PSScriptRoot
$graphicsPathType = [System.Drawing.Drawing2D.GraphicsPath]
$pixelFormat = [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
$blue = [System.Drawing.Color]::FromArgb(57, 127, 184)
$white = [System.Drawing.Color]::White

function New-IconBitmap([int]$size, [bool]$transparentBackground, [bool]$compactStar = $false, [bool]$circular = $false) {
    $bitmap = [System.Drawing.Bitmap]::new($size, $size, $pixelFormat)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $scale = $size / 512.0
    $graphics.ScaleTransform($scale, $scale)

    if (-not $transparentBackground) {
        $path = $graphicsPathType::new()
        if ($circular) {
            $path.AddEllipse(32, 32, 448, 448)
        } else {
        $path.AddArc(32, 32, 160, 160, 180, 90)
        $path.AddArc(320, 32, 160, 160, 270, 90)
        $path.AddArc(320, 320, 160, 160, 0, 90)
        $path.AddArc(32, 320, 160, 160, 90, 90)
        $path.CloseFigure()
        }
        $graphics.FillPath([System.Drawing.SolidBrush]::new($blue), $path)
        $path.Dispose()
    }

    $star = $graphicsPathType::new()
    # Equal cardinal tips and mirrored inner vertices give exact fourfold symmetry.
    $vertices = [System.Drawing.PointF[]]@(
        [System.Drawing.PointF]::new(256, 76),
        [System.Drawing.PointF]::new(292.8, 219.2),
        [System.Drawing.PointF]::new(436, 256),
        [System.Drawing.PointF]::new(292.8, 292.8),
        [System.Drawing.PointF]::new(256, 436),
        [System.Drawing.PointF]::new(219.2, 292.8),
        [System.Drawing.PointF]::new(76, 256),
        [System.Drawing.PointF]::new(219.2, 219.2)
    )
    $incoming = @()
    $outgoing = @()
    for ($i = 0; $i -lt $vertices.Count; $i++) {
        $vertex = $vertices[$i]
        $previous = $vertices[($i + 7) % 8]
        $next = $vertices[($i + 1) % 8]
        $trim = if ($i % 2 -eq 0) { 18.0 } else { 7.0 }
        $beforeLength = [Math]::Sqrt([Math]::Pow($previous.X - $vertex.X, 2) + [Math]::Pow($previous.Y - $vertex.Y, 2))
        $afterLength = [Math]::Sqrt([Math]::Pow($next.X - $vertex.X, 2) + [Math]::Pow($next.Y - $vertex.Y, 2))
        $incoming += [System.Drawing.PointF]::new($vertex.X + ($previous.X - $vertex.X) * $trim / $beforeLength,
            $vertex.Y + ($previous.Y - $vertex.Y) * $trim / $beforeLength)
        $outgoing += [System.Drawing.PointF]::new($vertex.X + ($next.X - $vertex.X) * $trim / $afterLength,
            $vertex.Y + ($next.Y - $vertex.Y) * $trim / $afterLength)
    }
    # Round each corner with the same construction in all four quadrants.
    for ($step = 1; $step -le 8; $step++) {
        $i = $step % 8
        $previousIndex = ($i + 7) % 8
        $vertex = $vertices[$i]
        $start = $incoming[$i]
        $end = $outgoing[$i]
        $control1 = [System.Drawing.PointF]::new($start.X + ($vertex.X - $start.X) * 2 / 3,
            $start.Y + ($vertex.Y - $start.Y) * 2 / 3)
        $control2 = [System.Drawing.PointF]::new($end.X + ($vertex.X - $end.X) * 2 / 3,
            $end.Y + ($vertex.Y - $end.Y) * 2 / 3)
        $star.AddLine($outgoing[$previousIndex], $start)
        $star.AddBezier($start, $control1, $control2, $end)
    }
    $star.CloseFigure()
    if ($compactStar) {
        $matrix = [System.Drawing.Drawing2D.Matrix]::new(0.85, 0, 0, 0.85, 38.4, 38.4)
        $star.Transform($matrix)
        $matrix.Dispose()
    }
    $graphics.FillPath([System.Drawing.SolidBrush]::new($white), $star)
    $star.Dispose()
    $graphics.Dispose()
    return $bitmap
}

function Save-Png([System.Drawing.Bitmap]$bitmap, [string]$path) {
    try {
        $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $bitmap.Dispose()
    }
}

$assetPath = Join-Path $root 'star_savior/assets'
Save-Png (New-IconBitmap 1024 $false) (Join-Path $assetPath 'app-icon-master.png')
Save-Png (New-IconBitmap 512 $false) (Join-Path $assetPath 'app-icon.png')
Save-Png (New-IconBitmap 512 $false $false $true) (Join-Path $assetPath 'floating-icon.png')

$icoSizes = @(16, 24, 32, 48, 64, 128, 256)
$pngEntries = foreach ($size in $icoSizes) {
    $image = New-IconBitmap $size $false
    $stream = [System.IO.MemoryStream]::new()
    $image.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $image.Dispose()
    [pscustomobject]@{ Size = $size; Bytes = $stream.ToArray() }
    $stream.Dispose()
}
$icoPath = Join-Path $assetPath 'app-icon.ico'
$icoStream = [System.IO.File]::Create($icoPath)
$writer = [System.IO.BinaryWriter]::new($icoStream)
$writer.Write([uint16]0)
$writer.Write([uint16]1)
$writer.Write([uint16]$pngEntries.Count)
$offset = 6 + (16 * $pngEntries.Count)
foreach ($entry in $pngEntries) {
    $dimension = if ($entry.Size -eq 256) { [byte]0 } else { [byte]$entry.Size }
    $writer.Write($dimension)
    $writer.Write($dimension)
    $writer.Write([byte]0)
    $writer.Write([byte]0)
    $writer.Write([uint16]1)
    $writer.Write([uint16]32)
    $writer.Write([uint32]$entry.Bytes.Length)
    $writer.Write([uint32]$offset)
    $offset += $entry.Bytes.Length
}
foreach ($entry in $pngEntries) { $writer.Write($entry.Bytes) }
$writer.Dispose()
$icoStream.Dispose()

$androidRes = Join-Path $root 'android/app/src/main/res'
Save-Png (New-IconBitmap 512 $false) (Join-Path $androidRes 'drawable-nodpi/app_icon.png')
Save-Png (New-IconBitmap 512 $false $false $true) (Join-Path $androidRes 'drawable-nodpi/floating_icon.png')
Save-Png (New-IconBitmap 432 $true $true) (Join-Path $androidRes 'drawable-nodpi/ic_launcher_foreground.png')
foreach ($density in @(@('mdpi', 48), @('hdpi', 72), @('xhdpi', 96), @('xxhdpi', 144), @('xxxhdpi', 192))) {
    $folder = Join-Path $androidRes ('mipmap-' + $density[0])
    Save-Png (New-IconBitmap $density[1] $false) (Join-Path $folder 'ic_launcher.png')
}
