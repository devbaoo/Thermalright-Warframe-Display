package config

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"syscall"

	"golang.org/x/sys/windows/registry"
)

const (
	AppName    = "WarframeAIO_Display"
	RunRegKey  = `Software\Microsoft\Windows\CurrentVersion\Run`
	ConfigFile = "config.json"
)

type Config struct {
	LastFile        string  `json:"last_file"`
	Rotation        int     `json:"rotation"`
	MountMode       string  `json:"mount_mode"`
	FitMode         string  `json:"fit_mode"`
	Brightness      float64 `json:"brightness"`
	FPSOverride     int     `json:"fps_override"`
	OverlayEnabled  bool    `json:"overlay_enabled"`
	OverlayPosition string  `json:"overlay_position"`
	OverlayStyle    string  `json:"overlay_style"`
	MinimizeToTray  bool    `json:"minimize_to_tray"`
	Autostart       bool    `json:"autostart"`
}

func DefaultConfig() Config {
	return Config{
		LastFile:        "",
		Rotation:        0,
		MountMode:       "landscape",
		FitMode:         "fill",
		Brightness:      1.0,
		FPSOverride:     20,
		OverlayEnabled:  false,
		OverlayPosition: "bottom",
		OverlayStyle:    "badges",
		MinimizeToTray:  true,
		Autostart:       false,
	}
}

type Manager struct {
	mu       sync.RWMutex
	cfg      Config
	filePath string
}

func NewManager() *Manager {
	exePath, err := os.Executable()
	dir := "."
	if err == nil {
		dir = filepath.Dir(exePath)
	}

	m := &Manager{
		cfg:      DefaultConfig(),
		filePath: filepath.Join(dir, ConfigFile),
	}
	m.Load()
	return m
}

func (m *Manager) Load() {
	m.mu.Lock()
	defer m.mu.Unlock()

	data, err := os.ReadFile(m.filePath)
	if err != nil {
		return
	}
	_ = json.Unmarshal(data, &m.cfg)
}

func (m *Manager) Save() {
	m.mu.RLock()
	defer m.mu.RUnlock()

	data, err := json.MarshalIndent(m.cfg, "", "  ")
	if err != nil {
		return
	}
	_ = os.WriteFile(m.filePath, data, 0644)
}

func (m *Manager) Get() Config {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.cfg
}

func (m *Manager) Update(fn func(c *Config)) {
	m.mu.Lock()
	fn(&m.cfg)
	m.mu.Unlock()
	m.Save()
}

func (m *Manager) SetAutostart(enable bool) error {
	k, err := registry.OpenKey(registry.CURRENT_USER, RunRegKey, registry.SET_VALUE)
	if err != nil {
		return err
	}
	defer k.Close()

	exePath, err := os.Executable()
	if err != nil {
		return err
	}

	if enable {
		val := fmt.Sprintf(`"%s" --minimized`, exePath)
		return k.SetStringValue(AppName, val)
	} else {
		_ = k.DeleteValue(AppName)
		return nil
	}
}

func IsTRCCRunning() bool {
	cmd := exec.Command("tasklist", "/FO", "CSV", "/NH")
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	s := strings.ToLower(string(out))
	for _, name := range []string{"trcc.exe", "hwinfo.exe", "usblcd.exe", "usblcdnew.exe"} {
		if strings.Contains(s, name) {
			return true
		}
	}
	return false
}

func KillTRCCProcesses() int {
	killed := 0
	// 1. Terminate scheduled task first
	schCmd := exec.Command("schtasks", "/End", "/TN", "TRCCAppStartup")
	schCmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	_ = schCmd.Run()

	// 2. Kill any stray processes
	for _, name := range []string{"trcc.exe", "hwinfo.exe", "usblcd.exe", "usblcdnew.exe"} {
		cmd := exec.Command("taskkill", "/F", "/IM", name)
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
		if err := cmd.Run(); err == nil {
			killed++
		}
	}
	return killed
}

