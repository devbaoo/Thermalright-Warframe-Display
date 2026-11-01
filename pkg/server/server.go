package server

import (
	"bytes"
	"encoding/json"
	"fmt"
	"image"
	"image/jpeg"
	"io"
	"io/fs"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"unsafe"

	"thermalright-warframe/pkg/config"
	"thermalright-warframe/pkg/display"
	"thermalright-warframe/pkg/monitor"
	"thermalright-warframe/pkg/usb"
)

type Server struct {
	driver         *usb.Driver
	processor      *display.Processor
	monitor        *monitor.Monitor
	cfgMgr         *config.Manager
	port           int
	webFS          fs.FS
	assetsFS       fs.FS
	onOpenWindow   func()

	mu             sync.RWMutex
	currentPreview []byte
}

func NewServer(
	driver *usb.Driver,
	processor *display.Processor,
	monitor *monitor.Monitor,
	cfgMgr *config.Manager,
	port int,
	webFS fs.FS,
	assetsFS fs.FS,
	onOpenWindow func(),
) *Server {
	s := &Server{
		driver:       driver,
		processor:    processor,
		monitor:      monitor,
		cfgMgr:       cfgMgr,
		port:         port,
		webFS:        webFS,
		assetsFS:     assetsFS,
		onOpenWindow: onOpenWindow,
	}
	return s
}

func (s *Server) SetPreviewImage(img image.Image) {
	if img == nil {
		return
	}
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, img, &jpeg.Options{Quality: 85}); err == nil {
		s.mu.Lock()
		s.currentPreview = buf.Bytes()
		s.mu.Unlock()
	}
}

func (s *Server) Start() error {
	mux := http.NewServeMux()

	// Static web assets
	mux.Handle("/", http.FileServer(http.FS(s.webFS)))

	// API Endpoints - Compatible with both old & new frontend routes
	mux.HandleFunc("/api/status", s.handleStatus)
	mux.HandleFunc("/api/preview", s.handlePreview)
	mux.HandleFunc("/api/preview.jpg", s.handlePreview)

	mux.HandleFunc("/api/set_rotation", s.handleSetRotation)
	mux.HandleFunc("/api/set_fit", s.handleSetFit)
	mux.HandleFunc("/api/set_fit_mode", s.handleSetFit)

	mux.HandleFunc("/api/set_brightness", s.handleSetBrightness)
	mux.HandleFunc("/api/set_fps", s.handleSetFPS)

	mux.HandleFunc("/api/set_mount", s.handleSetMount)
	mux.HandleFunc("/api/set_mount_mode", s.handleSetMount)

	mux.HandleFunc("/api/set_overlay", s.handleSetOverlay)

	mux.HandleFunc("/api/load_preset", s.handleLoadPreset)
	mux.HandleFunc("/api/select_preset", s.handleLoadPreset)

	mux.HandleFunc("/api/select_file", s.handleSelectFile)
	mux.HandleFunc("/api/browse_file", s.handleSelectFile)

	mux.HandleFunc("/api/upload_file", s.handleUploadFile)
	mux.HandleFunc("/api/kill_trcc", s.handleKillTRCC)
	mux.HandleFunc("/api/set_autostart", s.handleSetAutostart)
	mux.HandleFunc("/api/open_window", s.handleOpenWindow)

	// Fallback for custom assets
	mux.Handle("/assets/", http.StripPrefix("/assets/", http.FileServer(http.FS(s.assetsFS))))

	addr := fmt.Sprintf("127.0.0.1:%d", s.port)
	log.Printf("[Server] Starting embedded HTTP server on http://%s", addr)
	return http.ListenAndServe(addr, mux)
}

func (s *Server) handleStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	stats := s.monitor.GetStats()
	cfg := s.cfgMgr.Get()

	fileName := "sample_core.gif"
	if cfg.LastFile != "" {
		fileName = filepath.Base(cfg.LastFile)
	}

	presets := []map[string]string{
		{"id": "sample_core", "name": "Sci-Fi Plasma Core", "file": "assets/sample_core.gif"},
		{"id": "matrix_rain", "name": "Matrix Digital Rain", "file": "assets/presets/matrix_rain.gif"},
		{"id": "synthwave", "name": "Synthwave Horizon", "file": "assets/presets/synthwave.gif"},
		{"id": "radar_telemetry", "name": "AIO Radar Telemetry", "file": "assets/presets/radar_telemetry.gif"},
	}

	resp := map[string]interface{}{
		"connected":        s.driver.IsConnected(),
		"device_name":      "Thermalright Frozen Warframe 360 SE",
		"device_id":        "0416:5302",
		"file_name":        fileName,
		"total_frames":     s.processor.FrameCount(),
		"rotation":         cfg.Rotation,
		"fit_mode":         cfg.FitMode,
		"fps":              cfg.FPSOverride,
		"fps_override":     cfg.FPSOverride,
		"brightness":       int(cfg.Brightness * 100),
		"mount_mode":       cfg.MountMode,
		"overlay_enabled":  cfg.OverlayEnabled,
		"overlay_position": cfg.OverlayPosition,
		"overlay_style":    cfg.OverlayStyle,
		"minimize_to_tray": cfg.MinimizeToTray,
		"autostart":        cfg.Autostart,
		"trcc_running":     config.IsTRCCRunning(),
		"stats":            stats,
		"cpu_usage":        stats.CPUUsage,
		"ram_usage":        stats.RAMUsage,
		"gpu_temp":         stats.GPUTemp,
		"gpu_usage":        stats.GPUUsage,
		"presets":          presets,
	}
	_ = json.NewEncoder(w).Encode(resp)
}

func (s *Server) handlePreview(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	data := s.currentPreview
	s.mu.RUnlock()

	w.Header().Set("Content-Type", "image/jpeg")
	w.Header().Set("Cache-Control", "no-cache, no-store, must-revalidate")
	if len(data) > 0 {
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(data)))
		_, _ = w.Write(data)
	} else {
		w.WriteHeader(http.StatusNoContent)
	}
}

func (s *Server) handleSetRotation(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Rotation int `json:"rotation"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
		s.processor.SetRotation(req.Rotation)
		s.cfgMgr.Update(func(c *config.Config) {
			c.Rotation = req.Rotation
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "ok", "rotation": req.Rotation})
}

func (s *Server) handleSetFit(w http.ResponseWriter, r *http.Request) {
	var req struct {
		FitMode string `json:"fit_mode"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
		s.processor.SetFitMode(req.FitMode)
		s.cfgMgr.Update(func(c *config.Config) {
			c.FitMode = req.FitMode
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "ok", "fit_mode": req.FitMode})
}

func (s *Server) handleSetBrightness(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Brightness float64 `json:"brightness"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
		bri := req.Brightness
		if bri > 1.0 {
			bri = bri / 100.0
		}
		if bri < 0.1 {
			bri = 0.1
		}
		if bri > 1.0 {
			bri = 1.0
		}
		s.processor.SetBrightness(bri)
		s.cfgMgr.Update(func(c *config.Config) {
			c.Brightness = bri
		})
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "ok", "brightness": int(bri * 100)})
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (s *Server) handleSetFPS(w http.ResponseWriter, r *http.Request) {
	var req struct {
		FPS int `json:"fps"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
		s.processor.SetFPS(req.FPS)
		s.cfgMgr.Update(func(c *config.Config) {
			c.FPSOverride = req.FPS
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "ok", "fps": req.FPS})
}

func (s *Server) handleSetMount(w http.ResponseWriter, r *http.Request) {
	var req struct {
		MountMode string `json:"mount_mode"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
		s.processor.SetMountMode(req.MountMode)
		s.cfgMgr.Update(func(c *config.Config) {
			c.MountMode = req.MountMode
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "ok", "mount_mode": req.MountMode})
}

func (s *Server) handleSetOverlay(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Enabled  bool   `json:"enabled"`
		Position string `json:"position"`
		Style    string `json:"style"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err == nil {
		s.cfgMgr.Update(func(c *config.Config) {
			c.OverlayEnabled = req.Enabled
			if req.Position != "" {
				c.OverlayPosition = req.Position
			}
			if req.Style != "" {
				c.OverlayStyle = req.Style
			}
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status":   "ok",
		"enabled":  req.Enabled,
		"position": req.Position,
		"style":    req.Style,
	})
}

func (s *Server) handleLoadPreset(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ID       string `json:"id"`
		PresetID string `json:"preset_id"`
	}
	_ = json.NewDecoder(r.Body).Decode(&req)

	targetID := req.ID
	if targetID == "" {
		targetID = req.PresetID
	}

	presetFiles := map[string]string{
		"sample_core":     "assets/sample_core.gif",
		"matrix_rain":     "assets/presets/matrix_rain.gif",
		"synthwave":       "assets/presets/synthwave.gif",
		"radar_telemetry": "assets/presets/radar_telemetry.gif",
	}

	target, exists := presetFiles[targetID]
	if !exists {
		target = "assets/sample_core.gif"
	}

	s.loadFile(target)

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status":   "ok",
		"file":     target,
		"filename": filepath.Base(target),
	})
}

func (s *Server) handleSelectFile(w http.ResponseWriter, r *http.Request) {
	filePath := openWindowsFileDialog()
	w.Header().Set("Content-Type", "application/json")
	if filePath != "" {
		s.loadFile(filePath)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"status":   "ok",
			"path":     filePath,
			"filename": filepath.Base(filePath),
		})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "cancelled"})
}

func (s *Server) handleUploadFile(w http.ResponseWriter, r *http.Request) {
	_ = r.ParseMultipartForm(32 << 20) // 32MB max
	file, handler, err := r.FormFile("file")
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "error", "message": err.Error()})
		return
	}
	defer file.Close()

	userDir := filepath.Join("assets", "user_uploads")
	_ = os.MkdirAll(userDir, 0755)
	destPath := filepath.Join(userDir, handler.Filename)

	dst, err := os.Create(destPath)
	if err == nil {
		_, _ = io.Copy(dst, file)
		dst.Close()
		s.loadFile(destPath)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"status":   "ok",
			"path":     destPath,
			"filename": handler.Filename,
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "error", "message": "Failed to save file"})
}

func (s *Server) handleKillTRCC(w http.ResponseWriter, r *http.Request) {
	count := config.KillTRCCProcesses()
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status":       "ok",
		"killed_count": count,
	})
}

func (s *Server) handleSetAutostart(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Enabled bool `json:"enabled"`
	}
	_ = json.NewDecoder(r.Body).Decode(&req)
	_ = s.cfgMgr.SetAutostart(req.Enabled)
	s.cfgMgr.Update(func(c *config.Config) {
		c.Autostart = req.Enabled
	})
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "ok",
		"autostart": req.Enabled,
	})
}

func (s *Server) handleOpenWindow(w http.ResponseWriter, r *http.Request) {
	if s.onOpenWindow != nil {
		go s.onOpenWindow()
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (s *Server) loadFile(path string) {
	cfg := s.cfgMgr.Get()
	if err := s.processor.LoadFile(path, cfg.Rotation, cfg.FitMode, cfg.Brightness, cfg.FPSOverride, cfg.MountMode); err == nil {
		s.cfgMgr.Update(func(c *config.Config) {
			c.LastFile = path
		})
	}
}

// Windows native file dialog via comdlg32.dll
var (
	modComdlg32          = syscall.NewLazyDLL("comdlg32.dll")
	procGetOpenFileNameW = modComdlg32.NewProc("GetOpenFileNameW")
)

type openFileNameW struct {
	StructSize    uint32
	HwndOwner     uintptr
	HInstance     uintptr
	Filter        *uint16
	CustomFilter  *uint16
	MaxCustFilter uint32
	FilterIndex   uint32
	File          *uint16
	MaxFile       uint32
	FileTitle     *uint16
	MaxFileTitle  uint32
	InitialDir    *uint16
	Title         *uint16
	Flags         uint32
	FileOffset    uint16
	FileExtension uint16
	DefExt        *uint16
	CustData      uintptr
	FnHook        uintptr
	TemplateName  *uint16
	PvReserved    uintptr
	DwReserved    uint32
	FlagsEx       uint32
}

func openWindowsFileDialog() string {
	filter, _ := syscall.UTF16PtrFromString("Media Files (*.gif;*.png;*.jpg;*.jpeg;*.webp)\x00*.gif;*.png;*.jpg;*.jpeg;*.webp\x00All Files (*.*)\x00*.*\x00\x00")
	title, _ := syscall.UTF16PtrFromString("Select Image / GIF for Warframe LCD")

	fileBuf := make([]uint16, 1024)
	ofn := openFileNameW{
		StructSize: uint32(unsafe.Sizeof(openFileNameW{})),
		Filter:     filter,
		File:       &fileBuf[0],
		MaxFile:    uint32(len(fileBuf)),
		Title:      title,
		Flags:      0x00001000 | 0x00000800 | 0x00000008, // OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR
	}

	r, _, _ := procGetOpenFileNameW.Call(uintptr(unsafe.Pointer(&ofn)))
	if r == 0 {
		return ""
	}
	return syscall.UTF16ToString(fileBuf)
}
