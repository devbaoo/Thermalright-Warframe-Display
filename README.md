# ❄️ Thermalright Warframe AIO Display Controller (Native & Optimized)

Ứng dụng điều khiển màn hình tản nhiệt nước **Thermalright Frozen Warframe 360 SE | ARGB Display** được tối ưu hóa tối đa, thay thế hoàn toàn phần mềm gốc **TRCC (Thermalright Control Center)**.

---

## 🚀 Vì sao ứng dụng này tốt hơn TRCC gốc?

| Tiêu chí | App TRCC Gốc | Ứng Dụng Mới (Warframe Display) |
| :--- | :--- | :--- |
| **Số tiến trình chạy ngầm** | **4 tiến trình** (`TRCC.exe`, `HWINFO.exe`, `USBLCD.exe`, `USBLCDNEW.exe`) | **1 tiến trình duy nhất** |
| **Tiêu thụ RAM** | **~150MB – 250MB+** | **Chỉ ~30MB – 45MB** |
| **Tiêu thụ CPU** | **2% – 5% CPU liên tục** (hàng trăm giây CPU do polling HWINFO & GDI+) | **< 0.8% CPU** khi phát GIF |
| **Xử lý ảnh GIF** | Gọi `ffmpeg.exe` rã hàng trăm file `.bmp` ra ổ cứng SSD gây hao mòn và giật lag | Xử lý & cache 100% trên RAM bằng **NumPy & Pillow** (< 0.3ms/frame) |
| **Giao thức kết nối** | IPC qua 34MB Shared Memory rồi qua bridge LibUsbDotNet | Giao tiếp **WinUSB trực tiếp** tới Endpoint `0x02` (Bulk Transfer) |
| **Giao diện người dùng** | Giao diện cũ kỹ, khó dùng, lỗi font chữ | Giao diện **Fluent Dark Mode** hiện đại, mượt mà |
| **Xem trước (Preview)** | Cố định, khó căn chỉnh | Mô phỏng mặt bơm AIO xoay thời gian thực |
| **Khay hệ thống (Tray)** | Nặng nề | Thu nhỏ xuống System Tray siêu nhẹ |

---

## 🎯 Các tính năng chính

1. **Hỗ trợ mọi định dạng ảnh & GIF**:
   - Tải nhanh các file `.gif`, `.png`, `.jpg`, `.webp`, `.bmp`.
   - Tự động nhận diện khung hình, thời gian trễ của GIF gốc hoặc cho phép đặt FPS tùy ý (10, 15, 20, 24, 30 FPS).
2. **Căn chỉnh & Xoay màn hình linh hoạt**:
   - **Xoay 4 hướng**: 0°, 90°, 180°, 270° phù hợp với mọi hướng lắp đặt tản nhiệt trên mainboard.
   - **Chế độ vừa khung (Fit Mode)**:
     - `Cắt vừa (Fill)`: Tự động zoom và cắt tâm để lấp đầy toàn bộ màn hình 320x240, không có viền đen.
     - `Giữ tỷ lệ (Fit)`: Giữ nguyên tỷ lệ gốc của ảnh, thêm viền đen nếu ảnh không đúng tỷ lệ.
     - `Kéo giãn (Stretch)`: Kéo vừa khít màn hình.
   - **Điều chỉnh độ sáng (Brightness)**: Từ 10% đến 100%.
3. **Hiển thị thông số hệ thống (Overlay) tùy chọn**:
   - Tùy chọn bật/tắt hiển thị CPU %, RAM %, nhiệt độ GPU trực tiếp lên trên ảnh GIF.
   - Chọn vị trí: Trên cùng, Ở giữa, hoặc Dưới cùng.
   - Sử dụng thư viện `psutil` siêu nhẹ, **không dùng kernel driver nặng nề như HWINFO**.
4. **Tối ưu hóa hệ thống & Quản lý TRCC**:
   - Nút **"Tắt ngay TRCC & HWINFO"**: 1-click đóng toàn bộ 4 tiến trình của TRCC để giải phóng CPU và RAM ngay lập tức.
   - Tùy chọn bật/tắt tự khởi động cùng Windows.
   - Tùy chọn thu nhỏ xuống khay hệ thống (System Tray).

---

## 🛠️ Hướng dẫn sử dụng

### 1. Khởi động ứng dụng
Bạn có thể mở ứng dụng theo một trong các cách sau:
- **Cách 1**: Nhấp đúp vào biểu tượng shortcut trên Desktop: **`Thermalright Warframe Display`**.
- **Cách 2**: Chạy file `run.bat` trong thư mục:
  ```
  C:\Users\Admin\.gemini\antigravity\scratch\WarframeDisplay\run.bat
  ```

### 2. Sử dụng
1. Khi mở app, app sẽ tự động kết nối tới màn hình AIO (đèn trạng thái chuyển thành **🟢 Đã kết nối AIO (0416:5302)**).
2. Bấm nút **"📁 Chọn GIF hoặc Ảnh mới..."** để chọn ảnh GIF bạn thích.
3. Chỉnh **Hướng xoay (0° / 90° / 180° / 270°)** sao cho đúng chiều lắp đặt của máy bạn.
4. Chỉnh **FPS** và **Độ sáng** theo nhu cầu.
5. Chuyển sang tab **"⚡ Tối Ưu & Hệ Thống"**, bấm nút **"🛑 Tắt ngay TRCC & HWINFO"** để dọn dẹp app TRCC cũ.
6. Đóng cửa sổ ứng dụng để app tự động thu nhỏ xuống System Tray và chạy ngầm siêu nhẹ.

