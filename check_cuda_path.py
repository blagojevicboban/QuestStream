
import os
import sys

def check_cuda_path():
    possible_paths = [
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2",
    ]
    
    found = None
    for p in possible_paths:
        if os.path.exists(p):
            print(f"Found CUDA at: {p}")
            found = p
            # We prefer 11.8 if multiple found, dealing with that loop logic later
            if "v11.8" in p:
                break
    
    if found:
        bin_path = os.path.join(found, "bin")
        print(f"Bin path: {bin_path}")
        
        # Try to modify path and import open3d checks
        os.environ['PATH'] = bin_path + os.pathsep + os.environ['PATH']
        
        # Python 3.8+ on Windows requires add_dll_directory for DLL search
        try:
            os.add_dll_directory(bin_path)
            print(f"Added DLL directory: {bin_path}")
        except AttributeError:
             pass # Python < 3.8

        print("Updated PATH and DLL dirs. Checking Open3D...")
        
        try:
            import open3d.core as o3c
            if hasattr(o3c, "cuda") and o3c.cuda.is_available():
                print("SUCCESS: CUDA detected after PATH update!")
            else:
                print("FAILURE: CUDA still not detected.")
        except Exception as e:
            print(f"Error importing open3d: {e}")
    else:
        print("Could not find standard CUDA 11.8/12.x installation directories.")

if __name__ == "__main__":
    check_cuda_path()
