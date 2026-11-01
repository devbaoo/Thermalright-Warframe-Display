package ui

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var browserPaths = []string{
	`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`,
	`C:\Program Files\Microsoft\Edge\Application\msedge.exe`,
	`C:\Program Files\Google\Chrome\Application\chrome.exe`,
	`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`,
}

var (
	modUser32               = syscall.NewLazyDLL("user32.dll")
	procEnumWindows          = modUser32.NewProc("EnumWindows")
	procGetWindowTextW       = modUser32.NewProc("GetWindowTextW")
	procGetWindowTextLengthW = modUser32.NewProc("GetWindowTextLengthW")
	procPostMessageW         = modUser32.NewProc("PostMessageW")
	procLoadImageW           = modUser32.NewProc("LoadImageW")
	procSetForegroundWindow  = modUser32.NewProc("SetForegroundWindow")
	procShowWindow           = modUser32.NewProc("ShowWindow")
)

const (
	WM_SETICON      = 0x0080
	ICON_SMALL      = 0
	ICON_BIG        = 1
	IMAGE_ICON      = 1
	LR_LOADFROMFILE = 0x00000010
	LR_DEFAULTSIZE  = 0x00000040
	SW_RESTORE      = 9
)

func IsServerAlive(port int) bool {
	url := fmt.Sprintf("http://127.0.0.1:%d/api/status", port)
	client := http.Client{Timeout: 600 * time.Millisecond}
	resp, err := client.Get(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func RequestOpenWindow(port int) bool {
	url := fmt.Sprintf("http://127.0.0.1:%d/api/open_window", port)
	client := http.Client{Timeout: 1000 * time.Millisecond}
	resp, err := client.Post(url, "application/json", nil)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func WaitForServer(port int, maxWait time.Duration) bool {
	deadline := time.Now().Add(maxWait)
	addr := fmt.Sprintf("127.0.0.1:%d", port)
	for time.Now().Before(deadline) {
		conn, err := net.DialTimeout("tcp", addr, 150*time.Millisecond)
		if err == nil {
			_ = conn.Close()
			return true
		}
		time.Sleep(50 * time.Millisecond)
	}
	return false
}

func BringWindowToFront() bool {
	found := false
	cb := syscall.NewCallback(func(hwnd uintptr, lparam uintptr) uintptr {
		lenText, _, _ := procGetWindowTextLengthW.Call(hwnd)
		if lenText > 0 {
			buf := make([]uint16, lenText+1)
			procGetWindowTextW.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), lenText+1)
			title := syscall.UTF16ToString(buf)
			if strings.Contains(title, "Thermalright") || strings.Contains(title, "Warframe") {
				procShowWindow.Call(hwnd, uintptr(SW_RESTORE))
				procSetForegroundWindow.Call(hwnd)
				found = true
				return 0 // Stop enumeration
			}
		}
		return 1 // Continue enumeration
	})
	procEnumWindows.Call(cb, 0)
	return found
}

func applyWindowIcon(iconPath string) {
	if !fileExists(iconPath) {
		return
	}
	pStr, err := syscall.UTF16PtrFromString(iconPath)
	if err != nil {
		return
	}

	hIcon, _, _ := procLoadImageW.Call(
		0,
		uintptr(unsafe.Pointer(pStr)),
		uintptr(IMAGE_ICON),
		0,
		0,
		uintptr(LR_LOADFROMFILE|LR_DEFAULTSIZE),
	)
	if hIcon == 0 {
		return
	}

	cb := syscall.NewCallback(func(hwnd uintptr, lparam uintptr) uintptr {
		lenText, _, _ := procGetWindowTextLengthW.Call(hwnd)
		if lenText > 0 {
			buf := make([]uint16, lenText+1)
			procGetWindowTextW.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), lenText+1)
			title := syscall.UTF16ToString(buf)
			if strings.Contains(title, "Thermalright") || strings.Contains(title, "Warframe") {
				procPostMessageW.Call(hwnd, uintptr(WM_SETICON), uintptr(ICON_BIG), hIcon)
				procPostMessageW.Call(hwnd, uintptr(WM_SETICON), uintptr(ICON_SMALL), hIcon)
			}
		}
		return 1
	})

	for i := 0; i < 15; i++ {
		time.Sleep(200 * time.Millisecond)
		procEnumWindows.Call(cb, 0)
	}
}

func LaunchAppWindow(port int) (*exec.Cmd, error) {
	// 1. If an existing window is open/minimized, restore and bring it to front
	if BringWindowToFront() {
		return nil, nil
	}

	url := fmt.Sprintf("http://127.0.0.1:%d", port)
	var browserExe string
	for _, p := range browserPaths {
		if fileExists(p) {
			browserExe = p
			break
		}
	}

	exePath, _ := os.Executable()
	baseDir := "."
	if exePath != "" {
		baseDir = filepath.Dir(exePath)
	}
	iconPath := filepath.Join(baseDir, "assets", "app_icon.ico")

	if browserExe != "" {
		profileDir := filepath.Join(os.TempDir(), "WarframeDisplay_NativeApp")
		cmd := exec.Command(
			browserExe,
			fmt.Sprintf("--app=%s", url),
			fmt.Sprintf("--user-data-dir=%s", profileDir),
			"--window-size=1100,740",
			"--no-first-run",
			"--no-default-browser-check",
			"--disable-features=TranslateUI",
		)
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: false}
		err := cmd.Start()
		if err == nil {
			go applyWindowIcon(iconPath)
		}
		return cmd, err
	}

	// Fallback: ShellExecute
	cmd := exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	err := cmd.Start()
	return cmd, err
}

func fileExists(p string) bool {
	info, err := os.Stat(p)
	return err == nil && !info.IsDir()
}
