package main

import (
	"embed"
	"flag"
	"image"
	"io/fs"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"thermalright-warframe/pkg/config"
	"thermalright-warframe/pkg/display"
	"thermalright-warframe/pkg/monitor"
	"thermalright-warframe/pkg/server"
	"thermalright-warframe/pkg/ui"
	"thermalright-warframe/pkg/usb"
)

//go:embed web/*
var embeddedWeb embed.FS

//go:embed assets/*
var embeddedAssets embed.FS

const (
	Port = 28765
)

func main() {
	minimized := flag.Bool("minimized", false, "Start minimized to background")
	flag.Parse()

	exePath, err := os.Executable()
	var logDir string
	if err == nil {
		logDir = filepath.Dir(exePath)
	} else {
		logDir = "."
	}
	logFile, err := os.OpenFile(filepath.Join(logDir, "app.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err == nil {
		log.SetOutput(logFile)
		defer logFile.Close()
	}

	// 1. Single Instance Check
	if ui.IsServerAlive(Port) {
		log.Println("[App] Found existing Warframe Display instance already active. Launching UI window...")
		if !*minimized {
			if !ui.BringWindowToFront() {
				_, _ = ui.LaunchAppWindow(Port)
			}
			time.Sleep(500 * time.Millisecond)
		}
		os.Exit(0)
	}

	log.Println("[App] Initializing Thermalright Frozen Warframe Native Go Controller...")

	// 2. Initialize Core Subsystems
	cfgMgr := config.NewManager()
	cfg := cfgMgr.Get()

	driver := usb.NewDriver()
	connected := driver.Connect()
	if !connected {
		log.Println("[App] Hardware display not immediately detected. Background loop will keep retrying...")
	}

	mon := monitor.NewMonitor(1500 * time.Millisecond)
	mon.Start()
	defer mon.Stop()

	processor := display.NewProcessor()

	// 3. Load initial media
	initialFile := cfg.LastFile
	if initialFile == "" || !fileExists(initialFile) {
		initialFile = "assets/sample_core.gif"
	}
	if fileExists(initialFile) {
		_ = processor.LoadFile(initialFile, cfg.Rotation, cfg.FitMode, cfg.Brightness, cfg.FPSOverride, cfg.MountMode)
	}

	// 4. Setup embedded file systems
	webSub, err := fs.Sub(embeddedWeb, "web")
	if err != nil {
		log.Fatalf("Failed to extract web FS: %v", err)
	}
	assetsSub, err := fs.Sub(embeddedAssets, "assets")
	if err != nil {
		log.Fatalf("Failed to extract assets FS: %v", err)
	}

	// 5. Setup and start HTTP API server
	openWindowFunc := func() {
		_, _ = ui.LaunchAppWindow(Port)
	}

	srv := server.NewServer(
		driver,
		processor,
		mon,
		cfgMgr,
		Port,
		webSub,
		assetsSub,
		openWindowFunc,
	)

	go func() {
		if err := srv.Start(); err != nil {
			log.Printf("[Server] Error: %v", err)
		}
	}()

	// 6. Wait for HTTP server to become responsive
	if !ui.WaitForServer(Port, 3*time.Second) {
		log.Println("[Server] Warning: Web server took longer than expected to bind.")
	}

	// 7. Start Display Streaming Loop in background
	stopStreaming := make(chan struct{})
	go runDisplayLoop(driver, processor, mon, cfgMgr, srv, stopStreaming)

	// 8. Launch Native Desktop Window if not minimized
	if !*minimized {
		go func() {
			time.Sleep(300 * time.Millisecond)
			_, _ = ui.LaunchAppWindow(Port)
		}()
	}

	// 9. Block until termination signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	<-sigCh

	log.Println("[App] Shutting down Thermalright Controller...")
	close(stopStreaming)
	driver.Disconnect()
}

func runDisplayLoop(
	driver *usb.Driver,
	processor *display.Processor,
	mon *monitor.Monitor,
	cfgMgr *config.Manager,
	srv *server.Server,
	stopCh <-chan struct{},
) {
	frameIdx := 0
	lastWebPreview := time.Now()
	lastReconnectAttempt := time.Now()
	lastFrameAdvance := time.Now()

	for {
		select {
		case <-stopCh:
			return
		default:
			totalFrames := processor.FrameCount()
			if totalFrames == 0 {
				time.Sleep(50 * time.Millisecond)
				continue
			}

			cfg := cfgMgr.Get()
			frame := processor.GetFrame(frameIdx)
			if frame == nil {
				time.Sleep(50 * time.Millisecond)
				continue
			}

			durMS := frame.DurationMS
			if durMS <= 0 {
				durMS = 50
			}

			var rgb565 []byte
			var previewImg image.Image

			if cfg.OverlayEnabled {
				stats := mon.GetStats()
				previewImg, rgb565 = processor.RenderOverlayFrame(
					frameIdx,
					stats.CPUUsage,
					stats.GPUTemp,
					stats.RAMUsage,
					cfg.OverlayPosition,
					cfg.OverlayStyle,
				)
			} else {
				previewImg = frame.PreviewImage
				rgb565 = frame.RGB565Bytes
			}

			// 1. Send continuously to hardware LCD over USB to prevent hardware watchdog timeout (~2s)
			if !driver.IsConnected() {
				if time.Since(lastReconnectAttempt) > 1*time.Second {
					lastReconnectAttempt = time.Now()
					driver.Connect()
				}
			} else if len(rgb565) == usb.PayloadSize {
				driver.SendFrame(rgb565)
			}

			// 2. Update web preview at ~10 FPS
			if time.Since(lastWebPreview) >= 100*time.Millisecond {
				lastWebPreview = time.Now()
				if previewImg != nil {
					srv.SetPreviewImage(previewImg)
				}
			}

			// 3. Advance frame index when frame duration has elapsed
			if totalFrames > 1 {
				if time.Since(lastFrameAdvance) >= time.Duration(durMS)*time.Millisecond {
					frameIdx = (frameIdx + 1) % totalFrames
					lastFrameAdvance = time.Now()
				}
			} else {
				frameIdx = 0
			}

			// 4. Keep-alive sleep: stream at 20 FPS (50ms) to ensure hardware watchdog never resets,
			// or faster if animated GIF specifies lower frame duration.
			streamDelay := 50 * time.Millisecond
			if totalFrames > 1 && durMS > 0 && durMS < 50 && durMS >= 15 {
				streamDelay = time.Duration(durMS) * time.Millisecond
			}
			time.Sleep(streamDelay)
		}
	}
}

func fileExists(p string) bool {
	info, err := os.Stat(p)
	return err == nil && !info.IsDir()
}
