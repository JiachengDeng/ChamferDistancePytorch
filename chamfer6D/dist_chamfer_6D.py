from torch import nn
from torch.autograd import Function
import torch
import importlib
import os

chamfer_found = importlib.find_loader("chamfer_6D") is not None
if not chamfer_found:
    ## Cool trick from https://github.com/chrdiller
    print("Jitting Chamfer 6D")

    from torch.utils.cpp_extension import load
    chamfer_6D = load(name="chamfer_6D",
                      sources=[
                          "/".join(os.path.abspath(__file__).split('/')[:-1] + ["chamfer_cuda.cpp"]),
                          "/".join(os.path.abspath(__file__).split('/')[:-1] + ["chamfer6D.cu"]),
                      ])
    print("Loaded JIT 6D CUDA chamfer distance")

else:
    import chamfer_6D
    print("Loaded compiled 6D CUDA chamfer distance")


# Chamfer's distance module @thibaultgroueix
# GPU tensors only
class chamfer_6DFunction(Function):
    @staticmethod
    def forward(ctx, xyz1, xyz2):
        batchsize, n, dim = xyz1.size()
        assert dim==6, "Wrong last dimension for the chamfer distance 's input! Check with .size()"
        _, m, dim = xyz2.size()
        assert dim==6, "Wrong last dimension for the chamfer distance 's input! Check with .size()"
        device = xyz1.device

        device = xyz1.device

        dist1 = torch.zeros(batchsize, n)
        dist2 = torch.zeros(batchsize, m)

        idx1 = torch.zeros(batchsize, n).type(torch.IntTensor)
        idx2 = torch.zeros(batchsize, m).type(torch.IntTensor)

        dist1 = dist1.to(device)
        dist2 = dist2.to(device)
        idx1 = idx1.to(device)
        idx2 = idx2.to(device)
        torch.cuda.set_device(device)

        chamfer_6D.forward(xyz1, xyz2, dist1, dist2, idx1, idx2)
        ctx.save_for_backward(xyz1, xyz2, idx1, idx2)
        return dist1, dist2, idx1, idx2

    @staticmethod
    def backward(ctx, graddist1, graddist2, gradidx1, gradidx2):
        xyz1, xyz2, idx1, idx2 = ctx.saved_tensors
        graddist1 = graddist1.contiguous()
        graddist2 = graddist2.contiguous()
        device = graddist1.device

        gradxyz1 = torch.zeros(xyz1.size())
        gradxyz2 = torch.zeros(xyz2.size())

        gradxyz1 = gradxyz1.to(device)
        gradxyz2 = gradxyz2.to(device)
        chamfer_6D.backward(
            xyz1, xyz2, gradxyz1, gradxyz2, graddist1, graddist2, idx1, idx2
        )
        return gradxyz1, gradxyz2


class chamfer_6DDist(nn.Module):
    def __init__(self):
        super(chamfer_6DDist, self).__init__()

    def forward(self, input1, input2):
        input1 = input1.contiguous()
        input2 = input2.contiguous()
        return chamfer_6DFunction.apply(input1, input2)