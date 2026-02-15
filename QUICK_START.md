# 🚀 Quick Launch Guide - QuestGear 3D Studio with NerfStudio

## Status
✅ **NerfStudio GUI Integration Complete!**

The application now has a fully functional GUI for training Gaussian Splatting and NeRF models!

---

## 🎬 How to Launch

### Step 1: Activate Environment
```powershell
cd C:\QuestGear3D\QuestGear3DStudio
.\venv\Scripts\activate
```

### Step 2: Run Application
```powershell
python main.py
```

**Expected Output:**
```
Application starting...
```

Then the GUI window will open with:
- **Tab 1:** "TSDF Reconstruction" (existing functionality)
- **Tab 2:** "NerfStudio" (new!) ⭐

---

## 🎯 First-Time Setup (NerfStudio)

### In the GUI:

1. **Click "NerfStudio" tab**
   - Look for the tab with sparkle ✨ icon

2. **Check Installation Status:**
   - If you see "✅ NerfStudio Installed" - **Skip to "Using NerfStudio"**
   - If you see "❌ NerfStudio Not Found" - **Continue below**

3. **Install NerfStudio:**
   - Click **"Install NerfStudio"** button
   - Progress bar will appear
   - Installation log shows live progress (last 10 lines)
   - **Wait 5-10 minutes** (downloads ~2GB)
   - When done: Status changes to "✅ NerfStudio Installed"
   - Training section becomes enabled

---

## 🎨 Using NerfStudio

### Prerequisites:
- ✅ NerfStudio installed (see above)
- ✅ Scan data loaded (use TSDF tab → "Load Folder" or "Load ZIP")

### Training Steps:

1. **Go to TSDF Reconstruction tab:**
   - Click "Load Folder"
   - Select your scan folder (e.g., `Scan_20260215_221412`)
   - Wait for loading to complete

2. **Go to NerfStudio tab:**
   - Training section should now be enabled

3. **Select Training Method:**
   - **Splatfacto** ⚡ (Recommended) - Fastest, best quality
   - **Nerfacto** 🎯 - Balanced
   - **Instant-NGP** 🚀 - Ultra-fast preview
   - **Depth-Nerfacto** 📊 - Only if depth is valid

4. **Set Iterations:**
   - Default: 30,000 (recommended)
   - Quick test: 10,000
   - High quality: 50,000+

5. **Click "Start Training":**
   - Progress bar appears
   - Real-time metrics:
     - Step counter
     - ETA (estimated time remaining)
     - Loss (training error)
     - PSNR (quality metric)

6. **Monitor Progress:**
   - Check console/terminal for detailed logs
   - Training takes **5-30 minutes** depending on method

7. **When Complete:**
   - Status: "✅ Training completed!"
   - Output path shown
   - **"Open Viewer"** button appears

8. **View Results:**
   - Click **"Open Viewer"**
   - Browser opens to `http://localhost:7007`
   - Interact with 3D model in real-time!

---

## 🔍 Troubleshooting

### GUI Won't Launch
**Error:** `ImportError: No module named 'flet'`
**Fix:**
```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

### "NerfStudio Not Found" After Install
**Fix:** Restart the application:
```powershell
# Close GUI window
python main.py  # Restart
```

### Installation Fails
**Error:** Network timeout or package errors
**Fix:**
```powershell
# Manual install
.\venv\Scripts\activate
pip install nerfstudio
```

### "Please load a scan first"
**Fix:** 
1. Go to "TSDF Reconstruction" tab
2. Click "Load Folder" or "Load ZIP"
3. Select your scan data
4. Return to "NerfStudio" tab

### CUDA Out of Memory
**Fix:**
- Close other GPU applications
- Use "Instant-NGP" method (lighter)
- Reduce image resolution in scan

---

## 📊 Expected Performance

### Installation
- **Time:** 5-10 minutes
- **Size:** ~2GB download
- **Internet:** Required

### Training (Splatfacto, typical scan)
- **Iterations:** 30,000
- **Time:** 5-10 minutes (RTX 3060 or similar)
- **GPU Memory:** 6-8 GB VRAM
- **Output Size:** 50-200 MB

---

## 💡 Tips

### Best Results:
1. Start with **Splatfacto** (best quality/speed)
2. Use **30,000 iterations** for balance
3. Monitor **PSNR** - should reach >25 dB
4. Check **Loss** - should decrease over time

### Quick Testing:
1. Use **Instant-NGP** with **10,000 iterations**
2. Takes only 2-5 minutes
3. Good for previewing before full training

### Advanced:
- Full command-line control still available
- See `NERFSTUDIO_GUIDE.md` for CLI options
- See `NERFSTUDIO_GUI_GUIDE.md` for detailed UI guide

---

## 📁 Where are Results Saved?

### NerfStudio Output:
```
outputs/
└── splatfacto/
    └── scan_name/
        └── 2026-02-15_HHMMSS/
            ├── config.yml
            ├── point_cloud.ply  ← Final model (open in MeshLab/CloudCompare)
            └── nerfstudio_models/  ← Checkpoints
```

### Path shown in GUI after training completes!

---

## 🆘 Need Help?

1. **Check Logs:** Console/Terminal shows detailed output
2. **Check Guides:**
   - `NERFSTUDIO_GUI_GUIDE.md` - GUI usage
   - `NERFSTUDIO_GUIDE.md` - Technical details
   - `ARCHITECTURE.md` - How it works
3. **Test Components:**
   ```powershell
   python test_gui_nerfstudio.py  # Test without launching GUI
   ```

---

## ✨ Summary

```
Launch GUI → Install NerfStudio (one-time) → Load Scan → 
Select Method → Start Training → Watch Progress → Open Viewer → 
Photorealistic 3D! 🎉
```

**Enjoy creating beautiful 3D reconstructions!**

---

*Last Updated: 2026-02-15 | QuestGear 3D Studio v2.0*
