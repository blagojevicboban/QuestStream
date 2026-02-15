
import os
import sys
import ssl
import certifi

print("[Launcher] Applying SSL fixes for Windows...")

# --- SSL MONKEY PATCH START ---
# Fix for ssl.SSLError: [ASN1] nested asn1 error (_ssl.c:4047)
# This error occurs when Python tries to load certificates from a corrupted Windows Certificate Store.
# We override the context creation to ONLY use the 'certifi' certificate bundle and IGNORE the Windows store.

def patched_create_default_context(purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None):
    """
    Custom SSL context creator that avoids loading Windows Store certificates.
    Instead, it strictly uses the certifi CA bundle.
    """
    # Create a raw TLS client context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    
    # Secure default options
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_COMPRESSION
    
    # Load the reliable certifi bundle
    try:
        context.load_verify_locations(cafile=certifi.where())
        # print(f"[Launcher] Loaded certificates from: {certifi.where()}")
    except Exception as e:
        print(f"[Launcher] WARNING: Failed to load certifi bundle: {e}")
    
    # Set verification mode
    if purpose == ssl.Purpose.SERVER_AUTH:
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
    
    return context

# Apply the patch to both the public and internal function used by urllib/http.client
ssl.create_default_context = patched_create_default_context
ssl._create_default_https_context = patched_create_default_context
# --- SSL MONKEY PATCH END ---

# Ensure critical dependencies are in path (fixes ModuleNotFoundError for some setups)
# We append the current directory to path just in case
sys.path.append(os.getcwd())

if __name__ == "__main__":
    try:
        print(f"[Launcher] Starting NerfStudio training with arguments: {sys.argv[1:]}")
        from nerfstudio.scripts.train import entrypoint
        sys.exit(entrypoint())
    except ImportError as e:
        print(f"[Launcher] CRITICAL ERROR: Could not import NerfStudio: {e}")
        print("Please ensure nerfstudio is installed: pip install nerfstudio")
        sys.exit(1)
    except Exception as e:
        print(f"[Launcher] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
