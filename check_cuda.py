
import open3d as o3d
try:
    import open3d.core as o3c
    print(f"Open3D Version: {o3d.__version__}")
    
    if hasattr(o3c, "cuda") and o3c.cuda.is_available():
        print("✅ CUDA IS AVAILABLE")
        print(f"Device Count: {o3c.cuda.device_count()}")
        # Check first device
        dev = o3c.Device("CUDA:0")
        print(f"Using: {dev}")
    else:
        print("❌ CUDA IS NOT AVAILABLE")
        print("Using CPU Only.")
        
        # Try fallback check
        try:
            o3c.Device("CUDA:0")
            print("⚠️ WARNING: o3c.Device('CUDA:0') created without error, but is_available() was false.")
        except:
            print("Confirmed: Cannot create CUDA device.")

except ImportError:
    print("Open3D Tensor API (core) not installed.")
except Exception as e:
    print(f"Error checking CUDA: {e}")
