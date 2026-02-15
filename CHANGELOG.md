# QuestGear3DStudio - Changelog

## 2026-02-15: NerfStudio Integration + QuestGear3DScan Support

### 🎯 Summary
Added **NerfStudio training integration** for color-only reconstruction and full support for the new **QuestGear3DScan** data format. QuestGear3DStudio can now train Gaussian Splatting and NeRF models directly from the GUI while maintaining backward compatibility with legacy formats.

**🐛 Bug Fixes:**
- Fixed `AssertionError` in `page.run_task()` by using direct `page.update()` calls (thread-safe in Flet)
- Fixed initialization order to prevent crashes on GUI startup
- **Fixed Windows file locking during NerfStudio installation** (WinError 5: Access is denied)
  - Implemented lazy cv2 loading to avoid file locks
  - Two-step installation: core first (`--no-deps`), then dependencies
  - Uses separate Python process with `--force-reinstall` flag
  - Users can now install from GUI while it's running!


### ✨ Changes

#### 1. **`modules/quest_adapter.py`**
- ✅ Added `detect_scan_format()` - Auto-detects scan format (new vs old)
- ✅ Added `_adapt_new_format()` - Converts `scan_data.json` → `frames.json`
- ✅ Added `_adapt_old_format()` - Handles legacy `hmd_poses.csv` format
- ✅ Loads camera intrinsics from `transforms.json` (NerfStudio format)
- ✅ Converts 4x4 pose matrices to position + quaternion format
- ℹ️ Supports single camera mode (`center` camera from Camera 1)

#### 2. **`modules/quest_image_processor.py`**
- ✅ Added auto-detection for image formats (JPG/PNG vs YUV/RAW)
- ✅ Added JPG/PNG loading support for new scans
- ✅ Added 16-bit PNG depth map support
- ✅ Maintains backward compatibility with YUV_420_888 conversion
- ℹ️ Automatically converts depth from 16-bit to float32

#### 3. **`modules/reconstruction.py`**
- ✅ Added depth validation before integration
- ✅ Skips frames with empty/invalid depth data (prevents Open3D HashMap errors)
- ✅ **Detects uniform depth values** (all pixels identical = invalid data)
- ✅ Warns when <1% of depth pixels are valid
- 🐛 **Fixes:** `HashMap.cpp:359: Input number of keys should > 0` error

#### 4. **`generate_color_only.py`** (New)
-  ✅ Generates camera trajectory visualization (PLY file)
- ✅ Creates reconstruction options guide when depth is unavailable
- ✅ Fallback workflow for color-only reconstruction (NerfStudio/COLMAP)
- ℹ️ **Use when:** Quest Depth API returns placeholder data (uniform values)

#### 5. **`modules/nerfstudio_trainer.py`** (New) ⭐
- ✅ **Subprocess management** for NerfStudio training
- ✅ **Real-time progress tracking** via log parsing (step, loss, PSNR, ETA)
- ✅ **Multiple methods supported:** Splatfacto, Nerfacto, Instant-NGP, Depth-Nerfacto
- ✅ **Callback system** for GUI integration (progress + completion hooks)
- ✅ **Auto-detection** of NerfStudio installation
- ✅ **Output path discovery** for trained models
- 🎯 **Enables:** High-quality color-only reconstruction (no depth required!)

#### 6. **`modules/nerfstudio_gui.py`** (New) 🎨
- ✅ **Complete Flet UI** for NerfStudio integration
- ✅ **Installation manager** - Install/update NerfStudio from GUI
- ✅ **Training controls** - Method selection, iterations, start/stop
- ✅ **Real-time progress** - Progress bar, ETA, loss, PSNR display
- ✅ **Results viewer** - Open NerfStudio viewer with one click
- ✅ **Tab navigation** - Seamlessly integrated into main GUI

#### 7. **`modules/gui.py`** (Updated)
- ✅ **Tab navigation system** - TSDF Reconstruction tab + NerfStudio tab
- ✅ **Updated title** - "QuestGear 3D Studio" (from "QuestStream 3D Processor")
- ✅ **NerfStudio integration** - Automatic initialization of NerfStudio UI



### 📂 Format Support

#### **New Format (QuestGear3DScan)**
```
Scan_YYYYMMDD_HHMMSS/
├── scan_data.json          # Frame metadata + poses (4x4 matrices)
├── transforms.json         # NerfStudio format (camera intrinsics)
├── color/
│   └── frame_XXXXXX.jpg   # Color images (JPG)
└── depth/
    └── frame_XXXXXX.png   # Depth maps (16-bit PNG)
```

#### **Legacy Format (Quest Recording Manager)**
```
quest_recording/
├── hmd_poses.csv
├── left_camera_raw/
│   └── *.yuv
├── right_camera_raw/
│   └── *.yuv
├── left_depth/
│   └── *.raw
└── right_depth/
    └── *.raw
```

### 🧪 Testing
Use `test_new_scan_format.py` to verify compatibility:
```bash
python test_new_scan_format.py
```

### 🔄 Migration Notes
- **No breaking changes** - Old scans continue to work
- **Automatic detection** - No manual configuration needed
- **Single camera mode** - New scans use `center` camera instead of `left`/`right`

### 🚀 Next Steps
- Consider adding depth filtering for new format (currently depth maps may be empty)
- Add GUI indicator to show which format is detected
- Add progress bar for large scan conversions

---
*Updated on 2026-02-15 by Antigravity*
