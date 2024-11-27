import torch
import torch.nn as nn

class DoubleConv(nn.Module):
    
    def __init__(self, in_channels, out_channels):
        super().__init__()
        
        # two convolutions with 3x3 kernel
        self.conv_op = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True)
        )
    
    def forward(self, x):
        
        return self.conv_op(x)
    
class Downsample(nn.Module):
    
    def __init__(self, in_channels, out_channels):
        super().__init__()
        
        self.double_conv = DoubleConv(in_channels, out_channels)
        self.max_pool = nn.MaxPool2d(kernel_size=2, stride=2)
        
    def forward(self, x):
        down = self.double_conv(x)
        p = self.max_pool(down)
        
        return down, p
    
class Upsample(nn.Module):
    
    def __init__(self, in_channels, out_channels):
        super().__init__()
        
        self.up = nn.ConvTranspose2d(in_channels, in_channels//2, kernel_size=2, stride=2)
        self.double_conv = DoubleConv(in_channels, out_channels)
        
    def forward(self, x1, x2):
        x1 = self.up(x1)
        x = torch.cat([x1, x2], 1)
        
        return self.double_conv(x)
    
class UNet(nn.Module):
    
    def __init__(self, in_channels, out_channels):
        super().__init__()
        
        # decoder
        self.down_conv_1 = Downsample(in_channels, out_channels=64)
        self.down_conv_2 = Downsample(in_channels=64, out_channels=128)
        self.down_conv_3 = Downsample(in_channels=128, out_channels=256)
        self.down_conv_4 = Downsample(in_channels=256, out_channels=512)
        
        # bottleneck
        self.bottle_neck = DoubleConv(in_channels=512, out_channels=1024)
        
        # encoder
        self.up_conv_1 = Upsample(in_channels=1024, out_channels=512)
        self.up_conv_2 = Upsample(in_channels=512, out_channels=256)
        self.up_conv_3 = Upsample(in_channels=256, out_channels=128)
        self.up_conv_4 = Upsample(in_channels=128, out_channels=64)
        
        # output layer
        self.out = nn.Conv2d(in_channels=64, out_channels=out_channels, kernel_size=1)
        
    def forward(self, x):
        
        # decoder
        down_1, p1 = self.down_conv_1(x)
        down_2, p2 = self.down_conv_2(p1)
        down_3, p3 = self.down_conv_3(p2)
        down_4, p4 = self.down_conv_4(p3)
        
        # bottleneck
        b = self.bottle_neck(p4)
        
        # encoder
        up_1 = self.up_conv_1(b, down_4)
        up_2 = self.up_conv_2(up_1, down_3)
        up_3 = self.up_conv_3(up_2, down_2)
        up_4 = self.up_conv_4(up_3, down_1)
        
        # output layer
        out = self.out(up_4)
        return out