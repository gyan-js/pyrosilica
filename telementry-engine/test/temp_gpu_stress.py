
import torch
import time

device = torch.device("cuda:0")
print(f"Using: {torch.cuda.get_device_name(device)}")


a = torch.randn(4096, 4096, device=device)
b = torch.randn(4096, 4096, device=device)

print("Running matmul loop... Ctrl+C to stop")
try:
    while True:
        c = torch.matmul(a, b)
        torch.cuda.synchronize() 
except KeyboardInterrupt:
    print("Stopped")