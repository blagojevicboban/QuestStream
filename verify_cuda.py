import open3d as o3d
import sys
import os

log_file = "verify_log.txt"

def log(msg):
    print(msg)
    with open(log_file, "a") as f:
        f.write(msg + "\n")

# Clear log file
with open(log_file, "w") as f:
    f.write("")

log(f"Python Version: {sys.version}")
log(f"Open3D Version: {o3d.__version__}")

try:
    import torch
    log(f"PyTorch Version: {torch.__version__}")
    log("-" * 20)
    log("PyTorch CUDA Check:")
    if torch.cuda.is_available():
        log(f"  CUDA Available: YES")
        log(f"  Device Count: {torch.cuda.device_count()}")
        log(f"  Current Device: {torch.cuda.current_device()}")
        log(f"  Device Name: {torch.cuda.get_device_name(0)}")
        try:
            x = torch.rand(5, 3).cuda()
            log(f"  Test Tensor on CUDA: {x}")
        except Exception as e:
            log(f"  Test Tensor on CUDA failed: {e}")
    else:
        log("  CUDA Available: NO")
except ImportError:
    log("PyTorch Version: NOT INSTALLED")

log("-" * 20)
log("Open3D CUDA Check:")

# Check legacy CUDA support (if compiled with it)
try:
    # Use getattr to avoid AttributeError on older versions safely
    if hasattr(o3d.core, "cuda") and o3d.core.cuda.is_available():
        log("  Open3D Core CUDA: AVAILABLE")
        log(f"  Device Count: {o3d.core.cuda.device_count()}")
    else:
        log("  Open3D Core CUDA: NOT AVAILABLE (is_available() returned False)")
except Exception as e:
    log(f"  Open3D Core CUDA Check Failed: {e}")

# Attempt to create a CUDA device
log("\nAttempting to create Open3D CUDA device...")
try:
    device = o3d.core.Device("CUDA:0")
    log(f"  Successfully created CUDA device: {device}")
    
    # Try a small tensor operation
    val = o3d.core.Tensor([1.0], device=device)
    log(f"  Test Tensor on CUDA: {val}")
    
except Exception as e:
    log(f"  Failed: {e}")
    
log("-" * 20)
log("Build Information:")
try:
    log(str(o3d._build_config)) 
except:
    log("Build config not available directly.")
