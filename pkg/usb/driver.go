package usb

import (
	_ "embed"
	"encoding/binary"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

//go:embed libusb-1.0.dll
var embeddedLibusb []byte

const (
	VID             = 0x0416
	PID             = 0x5302
	EPWrite         = 0x02
	ChunkSize       = 512
	PanelWidth      = 240
	PanelHeight     = 320
	PayloadSize     = PanelWidth * PanelHeight * 2 // 153600 bytes
	TotalPacketSize = 154112
	CmdTypePicture  = 0x0002
	ModeRGB565      = 0x0001
)

type Driver struct {
	mu                   sync.Mutex
	dllHandle            syscall.Handle
	procInit             uintptr
	procOpen             uintptr
	procClose            uintptr
	procExit             uintptr
	procSetCfg           uintptr
	procClaimInterface   uintptr
	procReleaseInterface uintptr
	procTransfer         uintptr

	ctx          uintptr
	devHandle    uintptr
	connected    bool
	lastSendTime time.Time
	consecErrors int

	rawPacket []byte
}

func NewDriver() *Driver {
	d := &Driver{
		rawPacket: make([]byte, TotalPacketSize),
	}
	d.initHeader()
	return d
}

func (d *Driver) initHeader() {
	// Magic bytes
	d.rawPacket[0] = 0xDA
	d.rawPacket[1] = 0xDB
	d.rawPacket[2] = 0xDC
	d.rawPacket[3] = 0xDD

	// Header fields (Little Endian)
	binary.LittleEndian.PutUint16(d.rawPacket[4:6], CmdTypePicture)
	binary.LittleEndian.PutUint16(d.rawPacket[6:8], ModeRGB565)
	binary.LittleEndian.PutUint16(d.rawPacket[8:10], PanelWidth)
	binary.LittleEndian.PutUint16(d.rawPacket[10:12], PanelHeight)
	binary.LittleEndian.PutUint32(d.rawPacket[12:16], 0x00000002)
	binary.LittleEndian.PutUint32(d.rawPacket[16:20], PayloadSize)
}

func (d *Driver) loadDLL() error {
	if d.dllHandle != 0 {
		return nil
	}

	// Try next to executable, then Temp directory
	exePath, err := os.Executable()
	var dllPath string
	if err == nil {
		dllPath = filepath.Join(filepath.Dir(exePath), "libusb-1.0.dll")
	}

	if dllPath == "" || !fileExists(dllPath) {
		tempDll := filepath.Join(os.TempDir(), "libusb-1.0.dll")
		if !fileExists(tempDll) && len(embeddedLibusb) > 0 {
			_ = os.WriteFile(tempDll, embeddedLibusb, 0755)
		}
		dllPath = tempDll
	}

	h, err := syscall.LoadLibrary(dllPath)
	if err != nil {
		return fmt.Errorf("failed to load libusb DLL (%s): %w", dllPath, err)
	}

	d.dllHandle = h
	d.procInit, _ = syscall.GetProcAddress(h, "libusb_init")
	d.procOpen, _ = syscall.GetProcAddress(h, "libusb_open_device_with_vid_pid")
	d.procClose, _ = syscall.GetProcAddress(h, "libusb_close")
	d.procExit, _ = syscall.GetProcAddress(h, "libusb_exit")
	d.procSetCfg, _ = syscall.GetProcAddress(h, "libusb_set_configuration")
	d.procClaimInterface, _ = syscall.GetProcAddress(h, "libusb_claim_interface")
	d.procReleaseInterface, _ = syscall.GetProcAddress(h, "libusb_release_interface")
	d.procTransfer, _ = syscall.GetProcAddress(h, "libusb_interrupt_transfer")

	var ctx uintptr
	r, _, _ := syscall.SyscallN(d.procInit, uintptr(unsafe.Pointer(&ctx)))
	if int32(r) != 0 {
		return fmt.Errorf("libusb_init failed: %d", int32(r))
	}
	d.ctx = ctx
	return nil
}

func (d *Driver) Connect() bool {
	d.mu.Lock()
	defer d.mu.Unlock()

	if d.connected && d.devHandle != 0 {
		return true
	}

	if err := d.loadDLL(); err != nil {
		log.Printf("[USB] LoadDLL error: %v", err)
		return false
	}

	handle, _, _ := syscall.SyscallN(d.procOpen, d.ctx, uintptr(VID), uintptr(PID))
	if handle == 0 {
		d.connected = false
		return false
	}

	// Set configuration (ignore error if already set)
	syscall.SyscallN(d.procSetCfg, handle, 1)

	// Claim interface 0 for endpoint 0x02
	if d.procClaimInterface != 0 {
		rClaim, _, _ := syscall.SyscallN(d.procClaimInterface, handle, 0)
		if int32(rClaim) != 0 {
			log.Printf("[USB] Info: libusb_claim_interface res=%d", int32(rClaim))
		}
	}

	d.devHandle = handle
	d.connected = true
	d.consecErrors = 0
	log.Printf("[USB] Successfully connected to Thermalright Frozen Warframe (0x%04X:0x%04X)", VID, PID)
	return true
}

func (d *Driver) Disconnect() {
	d.mu.Lock()
	defer d.mu.Unlock()

	if d.devHandle != 0 {
		if d.procReleaseInterface != 0 {
			syscall.SyscallN(d.procReleaseInterface, d.devHandle, 0)
		}
		syscall.SyscallN(d.procClose, d.devHandle)
		d.devHandle = 0
	}
	d.connected = false
}

func (d *Driver) IsConnected() bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.connected && d.devHandle != 0
}

func (d *Driver) SendFrame(rgb565Data []byte) bool {
	d.mu.Lock()
	defer d.mu.Unlock()

	if !d.connected || d.devHandle == 0 {
		return false
	}

	if len(rgb565Data) != PayloadSize {
		return false
	}

	// Copy RGB565 data right after 20-byte header
	copy(d.rawPacket[20:20+PayloadSize], rgb565Data)

	// Stream all 154,112 bytes in 512-byte chunks
	var transferred int32
	ptrTransferred := uintptr(unsafe.Pointer(&transferred))
	basePtr := uintptr(unsafe.Pointer(&d.rawPacket[0]))

	for offset := uintptr(0); offset < TotalPacketSize; offset += ChunkSize {
		chunkPtr := basePtr + offset
		var lastErr int32
		chunkOk := false

		// Retry chunk up to 3 times with 500ms timeout
		for retry := 0; retry < 3; retry++ {
			r, _, _ := syscall.SyscallN(
				d.procTransfer,
				d.devHandle,
				uintptr(EPWrite),
				chunkPtr,
				uintptr(ChunkSize),
				ptrTransferred,
				uintptr(500), // 500ms timeout
			)
			lastErr = int32(r)
			if lastErr == 0 {
				chunkOk = true
				break
			}
			time.Sleep(1 * time.Millisecond)
		}

		if !chunkOk {
			d.consecErrors++
			log.Printf("[USB] Transfer error code %d at chunk %d/301 (consec: %d)", lastErr, offset/ChunkSize, d.consecErrors)
			// Disconnect only on repeated failures or device detached
			if d.consecErrors >= 3 || lastErr == -4 { // -4: LIBUSB_ERROR_NO_DEVICE
				if d.devHandle != 0 {
					if d.procReleaseInterface != 0 {
						syscall.SyscallN(d.procReleaseInterface, d.devHandle, 0)
					}
					syscall.SyscallN(d.procClose, d.devHandle)
					d.devHandle = 0
				}
				d.connected = false
			}
			return false
		}
	}

	d.consecErrors = 0
	d.lastSendTime = time.Now()
	return true
}

func fileExists(p string) bool {
	info, err := os.Stat(p)
	return err == nil && !info.IsDir()
}
