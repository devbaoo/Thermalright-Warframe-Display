package display

import (
	"bytes"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/gif"
	_ "image/jpeg"
	_ "image/png"
	"os"
	"sync"

	xdraw "golang.org/x/image/draw"
	"golang.org/x/image/font"
	"golang.org/x/image/font/basicfont"
	"golang.org/x/image/font/opentype"
	"golang.org/x/image/math/fixed"
)

const (
	PanelW          = 240
	PanelH          = 320
	PayloadSize     = PanelW * PanelH * 2
	FontValPath     = `C:\Windows\Fonts\bahnschrift.ttf`
	FontLblPath     = `C:\Windows\Fonts\segoeuib.ttf`
)

type ProcessedFrame struct {
	PreviewImage  image.Image // WYSIWYG for web preview
	HardwareImage image.Image // Exact 240x320 for physical LCD
	RGB565Bytes   []byte      // 153,600 bytes Little-Endian
	DurationMS    int         // Frame display time in ms
}

type Processor struct {
	mu             sync.RWMutex
	currentPath    string
	origFrames     []*image.RGBA
	origDurations  []int
	isAnimated     bool

	mountMode      string // "landscape" (320x240) or "portrait" (240x320)
	rotation       int    // 0, 90, 180, 270
	fitMode        string // "fill", "fit", "stretch"
	brightness     float64
	fpsOverride    int

	frames         []ProcessedFrame
	fontVal        font.Face
	fontLbl        font.Face
}

func NewProcessor() *Processor {
	p := &Processor{
		mountMode:   "landscape",
		rotation:    0,
		fitMode:     "fill",
		brightness:  1.0,
		fpsOverride: 20,
	}
	p.initFonts()
	return p
}

func (p *Processor) initFonts() {
	p.fontVal = basicfont.Face7x13
	p.fontLbl = basicfont.Face7x13

	valBytes, err := os.ReadFile(FontValPath)
	if err == nil {
		tf, err := opentype.Parse(valBytes)
		if err == nil {
			face, err := opentype.NewFace(tf, &opentype.FaceOptions{
				Size:    13,
				DPI:     72,
				Hinting: font.HintingFull,
			})
			if err == nil {
				p.fontVal = face
			}
		}
	}

	lblBytes, err := os.ReadFile(FontLblPath)
	if err == nil {
		tf, err := opentype.Parse(lblBytes)
		if err == nil {
			face, err := opentype.NewFace(tf, &opentype.FaceOptions{
				Size:    9,
				DPI:     72,
				Hinting: font.HintingFull,
			})
			if err == nil {
				p.fontLbl = face
			}
		}
	}
}

func (p *Processor) LoadFile(filePath string, rot int, fit string, bri float64, fps int, mount string) error {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return err
	}

	// Try decoding as animated GIF first
	gifData, errGif := gif.DecodeAll(bytes.NewReader(data))
	var origs []*image.RGBA
	var durs []int
	var animated bool

	if errGif == nil && len(gifData.Image) > 0 {
		animated = len(gifData.Image) > 1
		w := gifData.Config.Width
		h := gifData.Config.Height
		if w <= 0 || h <= 0 {
			w = gifData.Image[0].Bounds().Dx()
			h = gifData.Image[0].Bounds().Dy()
		}

		canvas := image.NewRGBA(image.Rect(0, 0, w, h))
		// Fill with black initially
		draw.Draw(canvas, canvas.Bounds(), &image.Uniform{color.Black}, image.Point{}, draw.Src)

		for i, frame := range gifData.Image {
			// Composite frame
			draw.Draw(canvas, frame.Bounds(), frame, frame.Bounds().Min, draw.Over)

			// Clone canvas
			frameClone := image.NewRGBA(canvas.Bounds())
			copy(frameClone.Pix, canvas.Pix)
			origs = append(origs, frameClone)

			durMs := 100
			if i < len(gifData.Delay) && gifData.Delay[i] > 0 {
				durMs = gifData.Delay[i] * 10
				if durMs <= 10 {
					durMs = 50
				}
			}
			durs = append(durs, durMs)
		}
	} else {
		// Static image (PNG, JPG)
		img, _, err := image.Decode(bytes.NewReader(data))
		if err != nil {
			return fmt.Errorf("unsupported image format: %w", err)
		}
		b := img.Bounds()
		rgba := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
		draw.Draw(rgba, rgba.Bounds(), img, b.Min, draw.Src)
		origs = append(origs, rgba)
		durs = append(durs, 100)
		animated = false
	}

	p.mu.Lock()
	p.currentPath = filePath
	p.origFrames = origs
	p.origDurations = durs
	p.isAnimated = animated
	p.rotation = rot
	p.fitMode = fit
	p.brightness = bri
	p.fpsOverride = fps
	p.mountMode = mount
	p.mu.Unlock()

	p.reprocessFrames()
	return nil
}

func (p *Processor) SetRotation(r int) {
	if r != 0 && r != 90 && r != 180 && r != 270 {
		return
	}
	p.mu.Lock()
	if p.rotation == r {
		p.mu.Unlock()
		return
	}
	p.rotation = r
	p.mu.Unlock()
	p.reprocessFrames()
}

func (p *Processor) SetFitMode(fit string) {
	if fit != "fill" && fit != "fit" && fit != "stretch" {
		return
	}
	p.mu.Lock()
	if p.fitMode == fit {
		p.mu.Unlock()
		return
	}
	p.fitMode = fit
	p.mu.Unlock()
	p.reprocessFrames()
}

func (p *Processor) SetBrightness(b float64) {
	if b < 0.1 {
		b = 0.1
	}
	if b > 1.0 {
		b = 1.0
	}
	p.mu.Lock()
	if p.brightness == b {
		p.mu.Unlock()
		return
	}
	p.brightness = b
	p.mu.Unlock()
	p.reprocessFrames()
}

func (p *Processor) SetFPS(fps int) {
	p.mu.Lock()
	if p.fpsOverride == fps {
		p.mu.Unlock()
		return
	}
	p.fpsOverride = fps
	p.mu.Unlock()
	p.reprocessFrames()
}

func (p *Processor) SetMountMode(m string) {
	if m != "landscape" && m != "portrait" {
		return
	}
	p.mu.Lock()
	if p.mountMode == m {
		p.mu.Unlock()
		return
	}
	p.mountMode = m
	p.mu.Unlock()
	p.reprocessFrames()
}

func (p *Processor) getCanvasDimensions() (int, int) {
	if p.mountMode == "portrait" {
		return 240, 320
	}
	return 320, 240
}

func (p *Processor) scaleAndRotateToView(src *image.RGBA, canvasW, canvasH int) *image.RGBA {
	srcW := src.Bounds().Dx()
	srcH := src.Bounds().Dy()

	fitW, fitH := canvasW, canvasH
	if p.rotation == 90 || p.rotation == 270 {
		fitW, fitH = canvasH, canvasW
	}

	var scaled *image.RGBA
	if p.fitMode == "stretch" {
		scaled = image.NewRGBA(image.Rect(0, 0, fitW, fitH))
		xdraw.BiLinear.Scale(scaled, scaled.Bounds(), src, src.Bounds(), xdraw.Over, nil)
	} else if p.fitMode == "fit" {
		ratioW := float64(fitW) / float64(srcW)
		ratioH := float64(fitH) / float64(srcH)
		ratio := ratioW
		if ratioH < ratio {
			ratio = ratioH
		}
		newW := int(float64(srcW) * ratio)
		newH := int(float64(srcH) * ratio)
		if newW < 1 {
			newW = 1
		}
		if newH < 1 {
			newH = 1
		}

		subScaled := image.NewRGBA(image.Rect(0, 0, newW, newH))
		xdraw.BiLinear.Scale(subScaled, subScaled.Bounds(), src, src.Bounds(), xdraw.Over, nil)

		scaled = image.NewRGBA(image.Rect(0, 0, fitW, fitH))
		draw.Draw(scaled, scaled.Bounds(), &image.Uniform{color.Black}, image.Point{}, draw.Src)
		ox := (fitW - newW) / 2
		oy := (fitH - newH) / 2
		draw.Draw(scaled, image.Rect(ox, oy, ox+newW, oy+newH), subScaled, image.Point{}, draw.Over)
	} else { // "fill" (center crop)
		ratioW := float64(fitW) / float64(srcW)
		ratioH := float64(fitH) / float64(srcH)
		ratio := ratioW
		if ratioH > ratio {
			ratio = ratioH
		}
		newW := int(float64(srcW) * ratio)
		newH := int(float64(srcH) * ratio)
		if newW < 1 {
			newW = 1
		}
		if newH < 1 {
			newH = 1
		}

		bigScaled := image.NewRGBA(image.Rect(0, 0, newW, newH))
		xdraw.BiLinear.Scale(bigScaled, bigScaled.Bounds(), src, src.Bounds(), xdraw.Over, nil)

		cx := (newW - fitW) / 2
		cy := (newH - fitH) / 2
		scaled = image.NewRGBA(image.Rect(0, 0, fitW, fitH))
		draw.Draw(scaled, scaled.Bounds(), bigScaled, image.Point{X: cx, Y: cy}, draw.Src)
	}

	// Clockwise rotation
	if p.rotation != 0 {
		return rotateClockwise(scaled, p.rotation)
	}
	return scaled
}

func rotateClockwise(src *image.RGBA, degrees int) *image.RGBA {
	w := src.Bounds().Dx()
	h := src.Bounds().Dy()

	switch degrees {
	case 90:
		dst := image.NewRGBA(image.Rect(0, 0, h, w))
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				dst.SetRGBA(h-1-y, x, src.RGBAAt(x, y))
			}
		}
		return dst
	case 180:
		dst := image.NewRGBA(image.Rect(0, 0, w, h))
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				dst.SetRGBA(w-1-x, h-1-y, src.RGBAAt(x, y))
			}
		}
		return dst
	case 270:
		dst := image.NewRGBA(image.Rect(0, 0, h, w))
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				dst.SetRGBA(y, w-1-x, src.RGBAAt(x, y))
			}
		}
		return dst
	default:
		return src
	}
}

func (p *Processor) mapViewToHardware(viewImg *image.RGBA) *image.RGBA {
	if p.mountMode == "portrait" {
		if viewImg.Bounds().Dx() == PanelW && viewImg.Bounds().Dy() == PanelH {
			return viewImg
		}
		dst := image.NewRGBA(image.Rect(0, 0, PanelW, PanelH))
		xdraw.BiLinear.Scale(dst, dst.Bounds(), viewImg, viewImg.Bounds(), xdraw.Over, nil)
		return dst
	}

	// Landscape (320x240) -> 90° clockwise maps to 240x320 physical LCD
	hw := rotateClockwise(viewImg, 90)
	if hw.Bounds().Dx() != PanelW || hw.Bounds().Dy() != PanelH {
		dst := image.NewRGBA(image.Rect(0, 0, PanelW, PanelH))
		xdraw.BiLinear.Scale(dst, dst.Bounds(), hw, hw.Bounds(), xdraw.Over, nil)
		return dst
	}
	return hw
}

func (p *Processor) rgbaToRGB565(img *image.RGBA) []byte {
	buf := make([]byte, PayloadSize)
	b := p.brightness
	idx := 0

	w := img.Bounds().Dx()
	h := img.Bounds().Dy()

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			c := img.RGBAAt(x, y)
			r := float64(c.R) * b
			g := float64(c.G) * b
			bl := float64(c.B) * b

			r5 := uint16(r) >> 3
			g6 := uint16(g) >> 2
			b5 := uint16(bl) >> 3

			v := (r5 << 11) | (g6 << 5) | b5
			buf[idx] = byte(v)
			buf[idx+1] = byte(v >> 8)
			idx += 2
			if idx >= PayloadSize {
				return buf
			}
		}
	}
	return buf
}

func (p *Processor) reprocessFrames() {
	p.mu.RLock()
	origs := make([]*image.RGBA, len(p.origFrames))
	copy(origs, p.origFrames)
	durs := make([]int, len(p.origDurations))
	copy(durs, p.origDurations)
	fps := p.fpsOverride
	canvasW, canvasH := p.getCanvasDimensions()
	p.mu.RUnlock()

	if len(origs) == 0 {
		return
	}

	var overrideDur int
	if fps > 0 {
		overrideDur = 1000 / fps
	}

	newFrames := make([]ProcessedFrame, 0, len(origs))
	for i, orig := range origs {
		view := p.scaleAndRotateToView(orig, canvasW, canvasH)
		hw := p.mapViewToHardware(view)
		rgb565 := p.rgbaToRGB565(hw)

		dur := durs[i]
		if overrideDur > 0 {
			dur = overrideDur
		}

		newFrames = append(newFrames, ProcessedFrame{
			PreviewImage:  view,
			HardwareImage: hw,
			RGB565Bytes:   rgb565,
			DurationMS:    dur,
		})
	}

	p.mu.Lock()
	p.frames = newFrames
	p.mu.Unlock()
}

func (p *Processor) FrameCount() int {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return len(p.frames)
}

func (p *Processor) GetFrame(idx int) *ProcessedFrame {
	p.mu.RLock()
	defer p.mu.RUnlock()
	if len(p.frames) == 0 {
		return nil
	}
	return &p.frames[idx%len(p.frames)]
}

func (p *Processor) RenderOverlayFrame(idx int, cpuUsage, gpuTemp, ramUsage float64, pos, style string) (image.Image, []byte) {
	frame := p.GetFrame(idx)
	if frame == nil {
		blank := image.NewRGBA(image.Rect(0, 0, PanelW, PanelH))
		return blank, p.rgbaToRGB565(blank)
	}

	viewBase, ok := frame.PreviewImage.(*image.RGBA)
	if !ok {
		return frame.PreviewImage, frame.RGB565Bytes
	}

	// Clone view image for overlay
	canvas := image.NewRGBA(viewBase.Bounds())
	copy(canvas.Pix, viewBase.Pix)

	w := canvas.Bounds().Dx()
	h := canvas.Bounds().Dy()

	gpuStr := "--°C"
	if gpuTemp > 0 {
		gpuStr = fmt.Sprintf("%.0f°C", gpuTemp)
	}
	items := []struct {
		Label  string
		Val    string
		Accent color.RGBA
	}{
		{"CPU", fmt.Sprintf("%.0f%%", cpuUsage), color.RGBA{59, 130, 246, 255}}, // Sapphire
		{"GPU", gpuStr, color.RGBA{245, 158, 11, 255}},                           // Amber
		{"RAM", fmt.Sprintf("%.0f%%", ramUsage), color.RGBA{16, 185, 129, 255}}, // Emerald
	}

	if style == "strip" {
		stripH := 30
		y := h - stripH - 8
		if pos == "top" {
			y = 8
		} else if pos == "center" {
			y = (h - stripH) / 2
		}
		pad := 12

		// Background dark card
		drawRoundedRect(canvas, pad, y, w-pad, y+stripH, 6, color.RGBA{10, 13, 19, 230}, color.RGBA{38, 48, 64, 255})
		// Top accent line
		drawRoundedRect(canvas, pad+2, y, w-pad-2, y+2, 1, color.RGBA{59, 130, 246, 255}, color.RGBA{0, 0, 0, 0})

		colW := (w - pad*2) / 3
		for i, item := range items {
			cx := pad + i*colW + 12
			p.drawText(canvas, cx, y+16, item.Label, color.RGBA{148, 163, 184, 255}, p.fontLbl)
			p.drawText(canvas, cx+30, y+19, item.Val, color.RGBA{245, 247, 250, 255}, p.fontVal)
		}
	} else {
		// Modern Triple Frosted Badges (Default)
		badgeW := 88
		if w < 300 {
			badgeW = 68
		}
		badgeH := 32
		gap := 6
		startX := (w - (badgeW*3 + gap*2)) / 2
		y := h - badgeH - 10
		if pos == "top" {
			y = 10
		} else if pos == "center" {
			y = (h - badgeH) / 2
		}

		for i, item := range items {
			bx := startX + i*(badgeW+gap)

			// Drop shadow
			drawRoundedRect(canvas, bx+1, y+2, bx+badgeW+1, y+badgeH+2, 6, color.RGBA{0, 0, 0, 120}, color.RGBA{0, 0, 0, 0})
			// Frosted Glass card
			drawRoundedRect(canvas, bx, y, bx+badgeW, y+badgeH, 6, color.RGBA{11, 14, 21, 230}, color.RGBA{42, 52, 70, 255})
			// Accent indicator bar
			drawRoundedRect(canvas, bx+6, y+7, bx+9, y+badgeH-7, 2, item.Accent, color.RGBA{0, 0, 0, 0})
			// Label & Value
			p.drawText(canvas, bx+14, y+13, item.Label, color.RGBA{148, 163, 184, 255}, p.fontLbl)
			p.drawText(canvas, bx+14, y+25, item.Val, color.RGBA{245, 247, 250, 255}, p.fontVal)
		}
	}

	hw := p.mapViewToHardware(canvas)
	rgb565 := p.rgbaToRGB565(hw)
	return canvas, rgb565
}

func (p *Processor) drawText(dst *image.RGBA, x, y int, text string, col color.Color, face font.Face) {
	d := &font.Drawer{
		Dst:  dst,
		Src:  image.NewUniform(col),
		Face: face,
		Dot:  fixed.Point26_6{X: fixed.I(x), Y: fixed.I(y)},
	}
	d.DrawString(text)
}

func drawRoundedRect(dst *image.RGBA, x0, y0, x1, y1, radius int, fill, border color.RGBA) {
	for y := y0; y <= y1; y++ {
		for x := x0; x <= x1; x++ {
			// Basic rounded corner bounding
			isCorner := false
			if x < x0+radius && y < y0+radius {
				dx := x - (x0 + radius)
				dy := y - (y0 + radius)
				if dx*dx+dy*dy > radius*radius {
					isCorner = true
				}
			} else if x > x1-radius && y < y0+radius {
				dx := x - (x1 - radius)
				dy := y - (y0 + radius)
				if dx*dx+dy*dy > radius*radius {
					isCorner = true
				}
			} else if x < x0+radius && y > y1-radius {
				dx := x - (x0 + radius)
				dy := y - (y1 - radius)
				if dx*dx+dy*dy > radius*radius {
					isCorner = true
				}
			} else if x > x1-radius && y > y1-radius {
				dx := x - (x1 - radius)
				dy := y - (y1 - radius)
				if dx*dx+dy*dy > radius*radius {
					isCorner = true
				}
			}

			if isCorner {
				continue
			}

			isBorder := (x == x0 || x == x1 || y == y0 || y == y1) && border.A > 0
			if isBorder {
				blendPixel(dst, x, y, border)
			} else {
				blendPixel(dst, x, y, fill)
			}
		}
	}
}

func blendPixel(dst *image.RGBA, x, y int, src color.RGBA) {
	if src.A == 0 {
		return
	}
	if src.A == 255 {
		dst.SetRGBA(x, y, src)
		return
	}
	orig := dst.RGBAAt(x, y)
	alpha := uint32(src.A)
	invAlpha := 255 - alpha

	r := (uint32(src.R)*alpha + uint32(orig.R)*invAlpha) / 255
	g := (uint32(src.G)*alpha + uint32(orig.G)*invAlpha) / 255
	b := (uint32(src.B)*alpha + uint32(orig.B)*invAlpha) / 255

	dst.SetRGBA(x, y, color.RGBA{R: uint8(r), G: uint8(g), B: uint8(b), A: 255})
}
