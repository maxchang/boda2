import argparse
import sys
import random
import math

import numpy as np
import torch

from . import constants 

def set_all_seeds(seed):
    """Fixes all random seeds
    
    Parameters
    ----------
    seed : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    np.random.seed(seed)
    torch.manual_seed(seed)
    random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)


def str2bool(v):
    """Pulled from https://stackoverflow.com/a/43357954
    """
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')
        
        
def dna2tensor(sequence_str, vocab_list=constants.STANDARD_NT):
    """
    
    Parameters
    ----------
    sequence_str : str
        A nucleotide letter sequence.
    vocab_list : list, optional
        Nucleotide vocabulary. The default is constants.STANDARD_NT.

    Returns
    -------
    seq_tensor : torch tensor
        Tokenized tensor.
        
    """
    seq_tensor = np.zeros((len(vocab_list), len(sequence_str)))
    for letterIdx, letter in enumerate(sequence_str):
        seq_tensor[vocab_list.index(letter), letterIdx] = 1
    seq_tensor = torch.Tensor(seq_tensor)
    return seq_tensor
    

def create_paddingTensors(num_sequences, padding_len, num_st_samples=1, for_multi_sampling=True):
    """
    
    Parameters
    ----------
    num_sequences : int
        Number of sequences that will be padded.
    padding_len : int
        Total length of padding (maximally evenly distributed in up and down stream).
    num_st_samples: int
        Number of straight-through samples per sequence that will be padded.
        The default is 1.
    for_multi_sampling: bool
        Whether or not the tensor will pad multi-sampled sequences.
        The defaul is True.

    Returns
    -------
    upPad_logits : torch tensor
        Tokenized tensor of correct length from up stream DNA.
    downPad_logits : torch tensor
        Tokenized tensor of correct length from down stream DNA.
        
    """
    assert padding_len >= 0 and type(padding_len) == int, 'Padding must be a nonnegative integer'
    upPad_logits, downPad_logits = None, None  
    if padding_len > 0:
        assert padding_len <= (len(constants.MPRA_UPSTREAM) + len(constants.MPRA_DOWNSTREAM)), 'Not enough padding available'
        upPad_logits, downPad_logits = dna2tensor(constants.MPRA_UPSTREAM), \
                                     dna2tensor(constants.MPRA_DOWNSTREAM)
        upPad_logits, downPad_logits = upPad_logits[:,-padding_len//2 + padding_len%2:], \
                                     downPad_logits[:,:padding_len//2 + padding_len%2]
        if for_multi_sampling:
            upPad_logits, downPad_logits = upPad_logits.repeat(num_st_samples, num_sequences, 1, 1), \
                                        downPad_logits.repeat(num_st_samples, num_sequences, 1, 1)                                     
        else:
            upPad_logits, downPad_logits = upPad_logits.repeat(num_sequences, 1, 1), \
                                         downPad_logits.repeat(num_sequences, 1, 1)  
    return upPad_logits, downPad_logits
        

def first_token_rewarder(sequences, pct=1.):
    """Predictor for dummy examples

    Parameters
    ----------
    sequences : torch tensor
        Tokenized tensor.

    Returns
    -------
    rewards : 1-D tensor
        Percentage of presence of first token.

    """
    weights = torch.zeros_like(sequences)
    weights[:,0,:] = 1
    rewards = (weights * sequences).sum(2).sum(1).div(sequences.shape[2])
    rewards = rewards.view(-1, 1)
    return 1 - abs(rewards - pct)


def neg_reward_loss(x):
    """Loss for dummy examples
    For maximizing avg reward
    """
    return -torch.sum(x)

def organize_args(parser, args):
    arg_groups={}
    for group in parser._action_groups:
        group_dict={a.dest:getattr(args,a.dest,None) for a in group._group_actions}
        arg_groups[group.title]=argparse.Namespace(**group_dict)
    return arg_groups

'''
def reset_parameters(self) -> None:
    init.kaiming_uniform_(self.weight, a=math.sqrt(5))
    if self.bias is not None:
        fan_in, _ = init._calculate_fan_in_and_fan_out(self.weight)
        bound = 1 / math.sqrt(fan_in) if fan_in > 0 else 0
        init.uniform_(self.bias, -bound, bound)
        
def reset_weight(w):
    torch.nn.init.kaiming_uniform_(w, a=math.sqrt(5))
    
def reset_bias(b, w=None):
    if w is None:
        bound = 1 / math.sqrt(b.numel())
    else:
        fan_in, _ = torch.nn.init._calculate_fan_in_and_fan_out(w)
        bound = 1 / math.sqrt(fan_in) if fan_in > 0 else 0
    torch.nn.init.uniform_(b, -bound, bound)

def reshape_and_load_weights(model, state_dict):
    model_dict = model.state_dict()
    return NotImplementedError

def replace_and_load_weights(model, state_dict):
    return NotImplementedError

loaded_weights = torch.load('../../artifacts/my-model.epoch_5-step_19885.pkl')
model.load_state_dict(loaded_weights, strict=False)

pretrained_dict = ...
model_dict = model.state_dict()

# 1. filter out unnecessary keys
pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict}
# 2. overwrite entries in the existing state dict
model_dict.update(pretrained_dict) 
# 3. load the new state dict
model.load_state_dict(pretrained_dict)
'''