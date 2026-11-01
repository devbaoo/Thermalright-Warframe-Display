package monitor

import (
	"bytes"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

var (
	modKernel32            = syscall.NewLazyDLL("kernel32.dll")
	procGetSystemTimes     = modKernel32.NewProc("GetSystemTimes")
	procGlobalMemoryStatus = modKernel32.NewProc("GlobalMemoryStatusEx")
)

type fileTime struct {
	LowDateTime  uint32
	HighDateTime uint32
}

func (ft fileTime) toUint64() uint64 {
	return (uint64(ft.HighDateTime) << 32) | uint64(ft.LowDateTime)
}

type memoryStatusEx struct {
	Length               uint32
	MemoryLoad           uint32
	TotalPhys            uint64
	AvailPhys            uint64
	TotalPageFile        uint64
	AvailPageFile        uint64
	TotalVirtual         uint64
	AvailVirtual         uint64
	AvailExtendedVirtual uint64
}

type Stats struct {
	CPUUsage float64 `json:"cpu_usage"`
	RAMUsage float64 `json:"ram_usage"`
	GPUTemp  float64 `json:"gpu_temp"`
	GPUUsage float64 `json:"gpu_usage"`
	TimeStr  string  `json:"time_str"`
	DateStr  string  `json:"date_str"`
}

type Monitor struct {
	mu         sync.RWMutex
	stats      Stats
	running    bool
	stopCh     chan struct{}
	interval   time.Duration

	prevIdle   uint64
	prevKernel uint64
	prevUser   uint64
}

func NewMonitor(interval time.Duration) *Monitor {
	if interval <= 0 {
		interval = 1500 * time.Millisecond
	}
	return &Monitor{
		interval: interval,
		stopCh:   make(chan struct{}),
	}
}

func (m *Monitor) Start() {
	m.mu.Lock()
	if m.running {
		m.mu.Unlock()
		return
	}
	m.running = true
	m.mu.Unlock()

	// Initial reading
	m.readSystemTimes()

	go m.loop()
}

func (m *Monitor) Stop() {
	m.mu.Lock()
	if !m.running {
		m.mu.Unlock()
		return
	}
	m.running = false
	close(m.stopCh)
	m.mu.Unlock()
}

func (m *Monitor) GetStats() Stats {
	m.mu.RLock()
	defer m.mu.RUnlock()
	s := m.stats
	now := time.Now()
	s.TimeStr = now.Format("15:04")
	s.DateStr = now.Format("01/02")
	return s
}

func (m *Monitor) readSystemTimes() (idle, kernel, user uint64, ok bool) {
	var ftIdle, ftKernel, ftUser fileTime
	r, _, _ := procGetSystemTimes.Call(
		uintptr(unsafe.Pointer(&ftIdle)),
		uintptr(unsafe.Pointer(&ftKernel)),
		uintptr(unsafe.Pointer(&ftUser)),
	)
	if r == 0 {
		return 0, 0, 0, false
	}
	return ftIdle.toUint64(), ftKernel.toUint64(), ftUser.toUint64(), true
}

func (m *Monitor) queryCPU() float64 {
	idle, kernel, user, ok := m.readSystemTimes()
	if !ok {
		return 0
	}

	if m.prevKernel == 0 && m.prevUser == 0 {
		m.prevIdle, m.prevKernel, m.prevUser = idle, kernel, user
		return 0
	}

	deltaIdle := idle - m.prevIdle
	deltaKernel := kernel - m.prevKernel
	deltaUser := user - m.prevUser

	m.prevIdle, m.prevKernel, m.prevUser = idle, kernel, user

	total := deltaKernel + deltaUser
	if total == 0 {
		return 0
	}

	busy := total - deltaIdle
	usage := (float64(busy) / float64(total)) * 100.0
	if usage < 0 {
		usage = 0
	}
	if usage > 100 {
		usage = 100
	}
	return usage
}

func (m *Monitor) queryRAM() float64 {
	var mem memoryStatusEx
	mem.Length = uint32(unsafe.Sizeof(mem))
	r, _, _ := procGlobalMemoryStatus.Call(uintptr(unsafe.Pointer(&mem)))
	if r == 0 {
		return 0
	}
	return float64(mem.MemoryLoad)
}

func (m *Monitor) queryGPU() (temp float64, usage float64) {
	cmd := exec.Command("nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits")
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}

	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		return 0, 0
	}

	str := strings.TrimSpace(out.String())
	parts := strings.Split(str, ",")
	if len(parts) >= 2 {
		t, _ := strconv.ParseFloat(strings.TrimSpace(parts[0]), 64)
		u, _ := strconv.ParseFloat(strings.TrimSpace(parts[1]), 64)
		return t, u
	}
	return 0, 0
}

func (m *Monitor) loop() {
	ticker := time.NewTicker(m.interval)
	defer ticker.Stop()

	for {
		select {
		case <-m.stopCh:
			return
		case <-ticker.C:
			cpu := m.queryCPU()
			ram := m.queryRAM()
			gpuTemp, gpuUsage := m.queryGPU()

			m.mu.Lock()
			if m.stats.CPUUsage <= 0 {
				m.stats.CPUUsage = cpu
			} else {
				// Smooth Exponential Moving Average to prevent jumping numbers
				m.stats.CPUUsage = m.stats.CPUUsage*0.65 + cpu*0.35
			}
			m.stats.RAMUsage = ram
			if gpuTemp > 0 {
				m.stats.GPUTemp = gpuTemp
				m.stats.GPUUsage = gpuUsage
			}
			m.mu.Unlock()
		}
	}
}

