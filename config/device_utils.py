"""
Utility functions for device detection and configuration.
Automatically detects and uses GPU if available, otherwise falls back to CPU.
"""
import torch

def get_device():
    """
    Returns the best available device for model inference.
    Returns 'cuda' if GPU is available, otherwise 'cpu'.
    """
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"

def get_device_name():
    """
    Returns a human-readable device name.
    """
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        return f"GPU ({device_name})"
    return "CPU"

def print_device_info():
    """
    Prints information about the available device.
    """
    device = get_device()
    device_name = get_device_name()
    print(f"Using device: {device_name}")
    if device == "cuda":
        print(f"   CUDA Version: {torch.version.cuda}")
        print(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    return device
