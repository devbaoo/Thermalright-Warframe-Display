package ui

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"
)

var browserPaths = []string{
	`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`,
	`C:\Program Files\Microsoft\Edge\Application\msedge.exe`,
	`C:\Program Files\Google\Chrome\Application\chrome.exe`,
	`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`,
}

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

func LaunchAppWindow(port int) (*exec.Cmd, error) {
	url := fmt.Sprintf("http://127.0.0.1:%d", port)
	var browserExe string
	for _, p := range browserPaths {
		if fileExists(p) {
			browserExe = p
			break
		}
	}

	if browserExe != "" {
		profileDir := filepath.Join(os.TempDir(), "WarframeAIO_EdgeApp")
		cmd := exec.Command(
			browserExe,
			fmt.Sprintf("--app=%s", url),
			fmt.Sprintf("--user-data-dir=%s", profileDir),
			"--window-size=1080,720",
			"--disable-features=TranslateUI",
		)
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: false}
		err := cmd.Start()
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
