try:
    import torch
    HAS_TORCH = True
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
except ImportError:
    HAS_TORCH = False
    device = "cpu"