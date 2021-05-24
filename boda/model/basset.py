import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F

import pytorch_lightning as ptl

import sys
from ..common import utils 

def get_padding(kernel_size):
    left = (kernel_size - 1) // 2
    right= kernel_size - 1 - left
    return [ max(0,x) for x in [left,right] ]

class Conv1dNorm(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, 
                 stride=1, padding=0, dilation=1, groups=1, 
                 bias=True, batch_norm=True, weight_norm=True):
        super(Conv1dNorm, self).__init__()
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, 
                              stride, padding, dilation, groups, bias)
        if weight_norm:
            self.conv = nn.utils.weight_norm(self.conv)
        if batch_norm:
            self.bn_layer = nn.BatchNorm1d(out_channels, eps=1e-05, momentum=0.1, 
                                           affine=True, track_running_stats=True)
    def forward(self, input):
        try:
            return self.bn_layer( self.conv( input ) )
        except AttributeError:
            return self.conv( input )
        
class LinearNorm(nn.Module):
    def __init__(self, in_features, out_features, bias=True, 
                 batch_norm=True, weight_norm=True):
        super(LinearNorm, self).__init__()
        self.linear  = nn.Linear(in_features, out_features, bias=True)
        if weight_norm:
            self.linear = nn.utils.weight_norm(self.linear)
        if batch_norm:
            self.bn_layer = nn.BatchNorm1d(out_features, eps=1e-05, momentum=0.1, 
                                           affine=True, track_running_stats=True)
    def forward(self, input):
        try:
            return self.bn_layer( self.linear( input ) )
        except AttributeError:
            return self.linear( input )

class Basset(ptl.LightningModule):
    r"""Write docstring here.
    """
    
    @staticmethod
    def add_model_specific_args(parent_parser):
        parser = argparse.ArgumentParser(parents=[parent_parser], add_help=False)
        group  = parser.add_argument_group('Model Module args')
        
        group.add_argument('--conv1_channels', type=int, default=300)
        group.add_argument('--conv1_kernel_size', type=int, default=19)
        
        group.add_argument('--conv2_channels', type=int, default=200)
        group.add_argument('--conv2_kernel_size', type=int, default=11)
        
        group.add_argument('--conv3_channels', type=int, default=200)
        group.add_argument('--conv3_kernel_size', type=int, default=7)
        
        group.add_argument('--linear1_channels', type=int, default=1000)
        group.add_argument('--linear2_channels', type=int, default=1000)
        group.add_argument('--n_outputs', type=int, default=280)
        
        group.add_argument('--dropout_p', type=float, default=0.3)
        group.add_argument('--use_batch_norm', type=utils.str2bool, default=True)
        group.add_argument('--use_weight_norm',type=utils.str2bool, default=False)
        
        group.add_argument('--loss_criterion',type=str, default='CrossEntropyLoss')
        
        return parser
    
    @staticmethod
    def add_conditional_args(parser, known_args):
        return parser

    @staticmethod
    def process_args(grouped_args):
        model_args   = grouped_args['Model Module args']
        return model_args

    def __init__(self, conv1_channels=300, conv1_kernel_size=19, 
                 conv2_channels=200, conv2_kernel_size=11, 
                 conv3_channels=200, conv3_kernel_size=7, 
                 linear1_channels=1000, linear2_channels=1000, 
                 n_outputs=280, activation='ReLU', 
                 dropout_p=0.3, use_batch_norm=True, use_weight_norm=False,
                 loss_criterion='CrossEntropyLoss'):                                                
        super().__init__()        
        
        self.conv1_channels    = conv1_channels
        self.conv1_kernel_size = conv1_kernel_size
        self.conv1_pad = get_padding(conv1_kernel_size)
        
        self.conv2_channels    = conv2_channels
        self.conv2_kernel_size = conv2_kernel_size
        self.conv2_pad = get_padding(conv2_kernel_size)

        
        self.conv3_channels    = conv3_channels
        self.conv3_kernel_size = conv3_kernel_size
        self.conv3_pad = get_padding(conv3_kernel_size)
        
        self.linear1_channels  = linear1_channels
        self.linear2_channels  = linear2_channels
        self.n_outputs         = n_outputs
        
        self.activation        = activation
        
        self.dropout_p         = dropout_p
        self.use_batch_norm    = use_batch_norm
        self.use_weight_norm   = use_weight_norm
        
        self.loss_criterion    = loss_criterion
        
        self.pad1  = nn.ConstantPad1d(self.conv1_pad, 0.)
        self.conv1 = Conv1dNorm(4, 
                                self.conv1_channels, self.conv1_kernel_size, 
                                stride=1, padding=0, dilation=1, groups=1, 
                                bias=True, 
                                batch_norm=self.use_batch_norm, 
                                weight_norm=self.use_weight_norm)
        self.pad2  = nn.ConstantPad1d(self.conv2_pad, 0.)
        self.conv2 = Conv1dNorm(self.conv1_channels, 
                                self.conv2_channels, self.conv2_kernel_size, 
                                stride=1, padding=0, dilation=1, groups=1, 
                                bias=True, 
                                batch_norm=self.use_batch_norm, 
                                weight_norm=self.use_weight_norm)
        self.pad3  = nn.ConstantPad1d(self.conv3_pad, 0.)
        self.conv3 = Conv1dNorm(self.conv2_channels, 
                                self.conv3_channels, self.conv3_kernel_size, 
                                stride=1, padding=0, dilation=1, groups=1, 
                                bias=True, 
                                batch_norm=self.use_batch_norm, 
                                weight_norm=self.use_weight_norm)
        
        self.pad4 = nn.ConstantPad1d((1,1), 0.)

        self.maxpool_3 = nn.MaxPool1d(3, padding=0)
        self.maxpool_4 = nn.MaxPool1d(4, padding=0)
        
        self.linear1 = LinearNorm(self.conv3_channels*13, self.linear1_channels, 
                                  bias=True, 
                                  batch_norm=self.use_batch_norm, 
                                  weight_norm=self.use_weight_norm)
        self.linear2 = LinearNorm(self.linear1_channels, self.linear2_channels, 
                                  bias=True, 
                                  batch_norm=self.use_batch_norm, 
                                  weight_norm=self.use_weight_norm)
        self.output  = nn.Linear(self.linear2_channels, self.n_outputs)
        
        self.nonlin  = getattr(nn, self.activation)()                               
        
        self.dropout = nn.Dropout(p=self.dropout_p)
        
        self.criterion = getattr(nn,self.loss_criterion)()
        
    def encode(self, x):
        hook = self.nonlin( self.conv1( self.pad1( x ) ) )
        hook = self.maxpool_3( hook )
        hook = self.nonlin( self.conv2( self.pad2( hook ) ) )
        hook = self.maxpool_4( hook )
        hook = self.nonlin( self.conv3( self.pad3( hook ) ) )
        hook = self.maxpool_4( self.pad4( hook ) )        
        hook = torch.flatten( hook, start_dim=1 )
        return hook
    
    def decode(self, x):
        hook = self.dropout( self.nonlin( self.linear1( x ) ) )
        hook = self.dropout( self.nonlin( self.linear2( hook ) ) )
        return hook
    
    def classify(self, x):
        output = self.output( x )
        return output
        
    def forward(self, x):
        encoded = self.encode(x)
        decoded = self.decode(encoded)
        output  = self.classify(decoded)
        return output

class BassetVL(ptl.LightningModule):
    r"""Write docstring here.
    """
    
    @staticmethod
    def add_model_specific_args(parent_parser):
        parser = argparse.ArgumentParser(parents=[parent_parser], add_help=False)
        group  = parser.add_argument_group('Model Module args')
        
        group.add_argument('--conv1_channels', type=int, default=300)
        group.add_argument('--conv1_kernel_size', type=int, default=19)
        
        group.add_argument('--conv2_channels', type=int, default=200)
        group.add_argument('--conv2_kernel_size', type=int, default=11)
        
        group.add_argument('--conv3_channels', type=int, default=200)
        group.add_argument('--conv3_kernel_size', type=int, default=7)
        
        group.add_argument('--n_linear_layers', type=int, default=2)
        group.add_argument('--linear_channels', type=int, default=1000)
        group.add_argument('--n_outputs', type=int, default=280)
        
        group.add_argument('--dropout_p', type=float, default=0.3)
        group.add_argument('--use_batch_norm', type=utils.str2bool, default=True)
        group.add_argument('--use_weight_norm',type=utils.str2bool, default=False)
        
        group.add_argument('--loss_criterion',type=str, default='CrossEntropyLoss')
        
        return parser
    
    @staticmethod
    def add_conditional_args(parser, known_args):
        return parser

    @staticmethod
    def process_args(grouped_args):
        model_args   = grouped_args['Model Module args']
        return model_args

    def __init__(self, conv1_channels=300, conv1_kernel_size=19, 
                 conv2_channels=200, conv2_kernel_size=11, 
                 conv3_channels=200, conv3_kernel_size=7, 
                 n_linear_layers=2, linear_channels=1000, 
                 n_outputs=280, activation='ReLU', 
                 dropout_p=0.3, use_batch_norm=True, use_weight_norm=False,
                 loss_criterion='MSELoss'):                                                
        super().__init__()        
        
        self.conv1_channels    = conv1_channels
        self.conv1_kernel_size = conv1_kernel_size
        self.conv1_pad = get_padding(conv1_kernel_size)
        
        self.conv2_channels    = conv2_channels
        self.conv2_kernel_size = conv2_kernel_size
        self.conv2_pad = get_padding(conv2_kernel_size)

        
        self.conv3_channels    = conv3_channels
        self.conv3_kernel_size = conv3_kernel_size
        self.conv3_pad = get_padding(conv3_kernel_size)
        
        self.n_linear_layers   = n_linear_layers
        self.linear_channels   = linear_channels
        self.n_outputs         = n_outputs
        
        self.activation        = activation
        
        self.dropout_p         = dropout_p
        self.use_batch_norm    = use_batch_norm
        self.use_weight_norm   = use_weight_norm
        
        self.loss_criterion    = loss_criterion
        
        self.pad1  = nn.ConstantPad1d(self.conv1_pad, 0.)
        self.conv1 = Conv1dNorm(4, 
                                self.conv1_channels, self.conv1_kernel_size, 
                                stride=1, padding=0, dilation=1, groups=1, 
                                bias=True, 
                                batch_norm=self.use_batch_norm, 
                                weight_norm=self.use_weight_norm)
        self.pad2  = nn.ConstantPad1d(self.conv2_pad, 0.)
        self.conv2 = Conv1dNorm(self.conv1_channels, 
                                self.conv2_channels, self.conv2_kernel_size, 
                                stride=1, padding=0, dilation=1, groups=1, 
                                bias=True, 
                                batch_norm=self.use_batch_norm, 
                                weight_norm=self.use_weight_norm)
        self.pad3  = nn.ConstantPad1d(self.conv3_pad, 0.)
        self.conv3 = Conv1dNorm(self.conv2_channels, 
                                self.conv3_channels, self.conv3_kernel_size, 
                                stride=1, padding=0, dilation=1, groups=1, 
                                bias=True, 
                                batch_norm=self.use_batch_norm, 
                                weight_norm=self.use_weight_norm)
        
        self.pad4 = nn.ConstantPad1d((1,1), 0.)

        self.maxpool_3 = nn.MaxPool1d(3, padding=0)
        self.maxpool_4 = nn.MaxPool1d(4, padding=0)
        
        next_in_channels = self.conv3_channels*13
        
        for i in range(self.n_linear_layers):
            
            setattr(self, f'linear{i+1}', 
                    LinearNorm(next_in_channels, self.linear_channels, 
                               bias=True, 
                               batch_norm=self.use_batch_norm, 
                               weight_norm=self.use_weight_norm)
                   )
            next_in_channels = self.linear_channels

        self.output  = nn.Linear(next_in_channels, self.n_outputs)
        
        self.nonlin  = getattr(nn, self.activation)()                               
        
        self.dropout = nn.Dropout(p=self.dropout_p)
        
        self.criterion = getattr(nn,self.loss_criterion)()
        
    def encode(self, x):
        hook = self.nonlin( self.conv1( self.pad1( x ) ) )
        hook = self.maxpool_3( hook )
        hook = self.nonlin( self.conv2( self.pad2( hook ) ) )
        hook = self.maxpool_4( hook )
        hook = self.nonlin( self.conv3( self.pad3( hook ) ) )
        hook = self.maxpool_4( self.pad4( hook ) )        
        hook = torch.flatten( hook, start_dim=1 )
        return hook
    
    def decode(self, x):
        hook = x
        for i in range(self.n_linear_layers):
            hook = self.dropout( 
                self.nonlin( 
                    getattr(self,f'linear{i+1}')(hook)
                )
            )
        return hook
    
    def classify(self, x):
        output = self.output( x )
        return output
        
    def forward(self, x):
        encoded = self.encode(x)
        decoded = self.decode(encoded)
        output  = self.classify(decoded)
        return output

