# ❄️ Thermalright Warframe AIO Display Controller (Native Go)

[![GitHub Release](https://img.shields.io/github/v/release/devbaoo/Thermalright-Warframe-Display?style=flat-square&color=3B82F6)](https://github.com/devbaoo/Thermalright-Warframe-Display/releases/latest)
[![Go Version](https://img.shields.io/badge/Go-1.24-00ADD8?style=flat-square&logo=go)](https://golang.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-blue?style=flat-square&logo=windows)](https://microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-success?style=flat-square)](README.md)

Ứng dụng điều khiển màn hình tản nhiệt nước **Thermalright Frozen Warframe 360 SE | ARGB Display** được viết lại **100% bằng Golang Native**, tối ưu hóa tối đa phần cứng, thay thế hoàn toàn phần mềm gốc **TRCC (Thermalright Control Center)**.

---

## 📥 Tải Về Cài Đặt (Download)

| Phiên bản | Định dạng | Tải xuống trực tiếp |
| :--- | :--- | :--- |
| **v1.0.1 (Khuyên dùng)** | **Trọn gói `.zip`** (Bao gồm file chạy, preset mẫu và thư viện) | [⬇️ **Tải Thermalright-Warframe-Display-v1.0.1.zip**](https://github.com/devbaoo/Thermalright-Warframe-Display/releases/download/v1.0.1/Thermalright-Warframe-Display-v1.0.1-windows-amd64.zip) |
| **v1.0.1 Standalone** | **File thực thi đơn lẻ `.exe`** (Chỉ cần tải về và chạy) | [⬇️ **Tải ThermalrightWarframe.exe**](https://github.com/devbaoo/Thermalright-Warframe-Display/releases/download/v1.0.1/ThermalrightWarframe.exe) |
| **Tất cả bản phát hành** | Xem lịch sử cập nhật và changelog | [🔗 **GitHub Releases**](https://github.com/devbaoo/Thermalright-Warframe-Display/releases) |

---

## 🚀 So Sánh Hiệu Năng Với TRCC Gốc

| Tiêu chí | Phần Mềm TRCC Gốc | Thermalright Warframe Display (Go) |
| :--- | :--- | :--- |
| **Số tiến trình chạy ngầm** | **4 tiến trình** (`TRCC.exe`, `HWINFO.exe`, `USBLCD.exe`, `USBLCDNEW.exe`) | **1 tiến trình duy nhất** (`ThermalrightWarframe.exe`) |
| **Mức tiêu thụ RAM** | **150 MB – 280 MB+** | **Chỉ ~8 MB – 15 MB** (Tự động giải phóng working set) |
| **Mức tiêu thụ CPU** | **2.0% – 5.0% CPU liên tục** (Polling HWINFO và GDI+ liên tục) | **< 0.1% CPU** (Sử dụng Direct NVML Syscalls & Zero-Alloc Buffer) |
| **Ghi đĩa / Hao mòn SSD** | Gọi `ffmpeg.exe` rã hàng nghìn file `.bmp` ra ổ cứng SSD liên tục | **0 ghi đĩa** — Xử lý, resize và streaming trực tiếp 100% trong RAM |
| **Giao thức USB** | IPC qua 34MB Shared Memory rồi qua bridge LibUsbDotNet | Giao tiếp **WinUSB trực tiếp** tới Bulk Endpoint `0x02` |
| **Độ trễ màn hình** | Trễ 1 – 2 khung hình, dễ treo khi tắt/mở app | **Real-time 60 FPS**, hỗ trợ keep-alive tự hồi phục |
| **Cài đặt & Phụ thuộc** | Bộ cài cồng kềnh ~300MB, yêu cầu .NET Framework, C++ Redist | **Portable 8 MB**, chạy ngay không cần cài đặt bất kỳ phần mềm nào |

---

## ✨ Tính Năng Nổi Bật

1. **Hỗ Trợ Mọi Định Dạng Ảnh & Đồ Họa Động**:
   - Tải nhanh các file `.gif`, `.png`, `.jpg`, `.webp`, `.bmp`.
   - Tự động nhận diện khung hình và độ trễ chuẩn từ file GIF gốc, hỗ trợ ép FPS mượt mà (10, 15, 20, 24, 30 FPS).
2. **Căn Chỉnh & Xoay Màn Hình Đa Hướng**:
   - **Xoay 4 hướng**: 0°, 90°, 180°, 270° phù hợp với mọi hướng lắp đặt tản nhiệt (ống nước hướng sang phải, trái, trên hoặc dưới).
   - **Chế độ vừa khung (Fit Mode)**:
     - `Cắt vừa (Fill)`: Tự động zoom và căn tâm lấp đầy toàn bộ màn hình 320×240 mà không bị viền đen.
     - `Giữ tỷ lệ (Fit)`: Giữ nguyên tỷ lệ gốc của ảnh, bổ sung nền đen trang nhã.
     - `Kéo giãn (Stretch)`: Kéo phủ kín toàn bộ diện tích panel LCD.
   - **Độ sáng (Brightness)**: Tinh chỉnh từ 10% đến 100% bảo vệ màn hình ban đêm.
3. **Hiển Thị Thông Số Phần Cứng (Telemetry Overlay)**:
   - Hiển thị CPU (%), Nhiệt độ GPU (°C), RAM (%) theo phong cách Fluent Frosted Glass hiện đại.
   - Sử dụng **Direct NVML Syscalls** trực tiếp vào `nvml.dll` của NVIDIA driver, **hoàn toàn không spawn tiến trình con `nvidia-smi`**, giảm triệt để CPU về mức 0%.
4. **Tối Ưu & Dọn Dẹp TRCC Tự Động**:
   - Nút **"🛑 Tắt ngay TRCC & HWINFO"**: 1-click quét và đóng toàn bộ các tiến trình xung đột của TRCC cũ.
   - Hỗ trợ tự động chạy ngầm khi bật máy (Auto-start with Windows) và thu nhỏ xuống góc màn hình (System Tray).

---

## 📖 Hướng Dẫn Sử Dụng (Quick Start)

### 1. Khởi chạy
1. Tải file `.zip` từ mục [Releases](https://github.com/devbaoo/Thermalright-Warframe-Display/releases/latest) và giải nén vào thư mục bạn muốn lưu.
2. Nhấp đúp chuột vào file **`ThermalrightWarframe.exe`**.
3. Cửa sổ điều khiển giao diện Dark Mode hiện đại sẽ xuất hiện. Đèn trạng thái góc trên sẽ chuyển sang màu xanh lá cây: **🟢 Đã kết nối AIO (0416:5302)**.

### 2. Thiết lập hiển thị
- **Đổi GIF/Ảnh**: Bấm vào khung preview hoặc bấm nút **"📁 Chọn GIF hoặc Ảnh mới..."** để chọn file của bạn. Hoặc bạn có thể bấm vào các mẫu preset có sẵn ở danh sách bên dưới.
- **Chỉnh hướng xoay**: Bấm các nút **0°, 90°, 180°, 270°** sao cho hình ảnh hiển thị đúng chiều bạn gắn tản nhiệt trên case máy tính.
- **Bật thông số CPU/GPU**: Gạt công tắc **"Hiển thị thông số (Overlay)"** để xem nhiệt độ và mức tải thời gian thực.

> [!TIP]
> **💡 Lưu ý quan trọng về Cửa sổ Giao diện (Control Panel):**
> - Cửa sổ giao diện chỉ là bảng điều khiển tạm thời khi bạn cần đổi ảnh GIF hoặc chỉnh góc xoay / thông số.
> - **Sau khi cài đặt xong, bạn có thể bấm nút `[X]` đóng cửa sổ bất cứ lúc nào!** Màn hình tản nhiệt AIO trên máy bạn **vẫn tiếp tục hiển thị mượt mà 24/7** thông qua tiến trình chạy ngầm `ThermalrightWarframe.exe` với mức tiêu thụ siêu nhẹ: **chỉ ~9.4 MB RAM và < 0.1% CPU**.
> - Khi mở cửa sổ, Windows sẽ gom cửa sổ này vào nhóm "Microsoft Edge" (chỉ chiếm ~30MB của riêng tab, con số hàng trăm MB trên Task Manager là toàn bộ trình duyệt cá nhân của máy). Khi bạn đóng cửa sổ, tab này tắt hoàn toàn (về 0 MB RAM, 0% CPU).
> - Khi bật **"Tự khởi động cùng Windows" (Autostart)**, máy tính khởi động ngầm hoàn toàn với cờ `--minimized` và **không hề mở bất kỳ cửa sổ nào**.

### 3. Tắt ứng dụng gốc TRCC
Nếu trên máy bạn vẫn còn cài TRCC:
- Chuyển sang tab **"⚡ Tối Ưu & Hệ Thống"**.
- Bấm nút **"🛑 Tắt ngay TRCC & HWINFO"**. Ứng dụng sẽ tự động giải phóng cổng USB và tắt toàn bộ các tiến trình ngầm gây tốn tài nguyên của phần mềm gốc.

---

## 🛠️ Dành Cho Lập Trình Viên (Build From Source)

Yêu cầu: Go 1.22+ trên Windows x64.

```powershell
# Clone mã nguồn
git clone https://github.com/devbaoo/Thermalright-Warframe-Display.git
cd Thermalright-Warframe-Display

# Biên dịch binary siêu nhẹ không hiển thị console
go build -ldflags="-H=windowsgui -s -w" -o ThermalrightWarframe.exe main.go
```

---

## 🇺🇸 English Overview

**Thermalright Warframe Display** is an ultra-lightweight, 100% native Golang controller for the **Thermalright Frozen Warframe 360 SE / ARGB AIO LCD Display** (`VID 0x0416, PID 0x5302`), fully replacing the resource-heavy TRCC software.

### Key Highlights:
- **Ultra-low CPU usage (< 0.1%)**: Direct NVML syscalls for GPU telemetry and zero-heap-allocation render caching.
- **Ultra-low RAM (< 10 MB)**: Uses pure Win32 bulk USB transfers without heavy runtime dependencies.
- **100% Portable**: Single ~8MB executable. No Python, no .NET, no WebView2 required.
- **Supported Formats**: Animated GIF, PNG, JPG, WebP, BMP.
- **Orientation Control**: 4-way rotation (0°, 90°, 180°, 270°) with Fill/Fit/Stretch aspect ratios.
- **Telemetry Overlay**: Frosted-glass CPU, GPU Temperature, and RAM badges.

> [!TIP]
> **💡 Important note about the Control Panel window:**
> - The UI window is only a control panel for configuring GIFs, orientation, and overlay options.
> - **You can safely close the window (`[X]`) once configured!** The AIO LCD screen continues streaming 24/7 in the background via `ThermalrightWarframe.exe` using only **~9.4 MB RAM and < 0.1% CPU**.
> - When auto-start on boot is enabled, the app launches silently in the background (`--minimized`) without opening any window.

---

## 📄 Bản Quyền & Giấy Phép (License)

Dự án được phân phối dưới giấy phép **MIT License**. Bạn có thể tự do sử dụng, chỉnh sửa và phân phối lại.
Mọi đóng góp (Pull Request, Issue) đều được chào đón nồng nhiệt!
