"""

This is a module for the manipulation of tensors by means of lightweight memory views and 
minimal padding. It extends the native torch functions in ways that I find useful.

All items within this module are functions. They all accept a tensor and parameters, then
do something with it. They also tend to return views to allow efficient memory utilization.

The current functions available are.

view
local


"""

import torch
from torch import nn
from torch.nn import functional as F

import numbers
import numpy as np


def view(tensor, input_shape: "tuple, int", output_shape: "tuple, int"):
    """
    Description:
    
    This function exists as an extension to torch's view.
    
    This will, when passed an input shape and compatible output shape, assume that said shapes 
    refer to the later dimensions in a tensor, as in broadcasting, and will perform a reshape from 
    input shape to output shape while keeping all other dimensions exactly the same.
    
    ---- parameters ---
    
    :param tensor:
        The tensor to be modified.
    :param input_shape: 
        The expected input shape. This can be a list/tuple of ints, or an int. It should represent the shape at the end
        of the input tensor's .shape which will be matched in the tensor input
    :param output_shape:
        The expected output shape. This can be a list/tuple of ints, or an int. It should represent the final shape one
        wishes the tensor to take. It also must be the case that the total size of the input and output shape must be the same.
    ---- Examples ----
    
    
    For tensors of shape:
    
    a = (5,2), b=(3, 4, 5,2), c=(30, 5,2), 
    
    For input_shape = (5,2), output_shape=10, one has
    
    f(a, input_shape, output_shape) = shape(10)
    f(b, input_shape, output_shape) = shape(3, 4, 10)
    f(c, input_shape, output_shape) = shape(30, 10)


    """

    # Convertion

    if isinstance(input_shape, numbers.Number):
        input_shape = [input_shape]
    if isinstance(output_shape, numbers.Number):
        output_shape = [output_shape]

    # Basic sanity testing
    assert np.prod(input_shape) == np.prod(output_shape), "Input shape and output shape were not compatible"

    slice_length = len(input_shape)
    assert np.array_equal(input_shape, tensor.shape[-slice_length:]), "Input shape and tensor shape not compatible"

    # Construct view resize

    new_view = [*tensor.shape[:-slice_length], *output_shape]

    # view. Return
    return tensor.view(new_view)


def local(tensor, kernel_width, stride_rate, dilation_rate, pad=False):
    """

        A function to produce local views of the last dimension of a tensor. These are
        views, indexed along the second to last dimension, with content along the last
        dimension, which are the precursors to convolution, possessing a kernel width,
        stride rate, and dilation rate as defined in the local view class.

        Enabling padding prevents information loss due to striding.
        """

    # Construct shape. Take into account the kernel_width, dilation rate, and stride rate.

    # The kernel width, and dilation rate, together modifies how far off the end of the
    # data buffer a naive implimentation would go, in an additive manner. Striding, meanwhile
    # is a multiplictive factor

    compensation = (kernel_width - 1) * dilation_rate  # calculate dilation-kernel correction
    final_index_shape = tensor.shape[-1] - compensation  # apply
    assert final_index_shape > 0, "Configuration is not possible - final kernel exceeds available tensors"
    final_index_shape = final_index_shape // stride_rate  # Perform striding correction.
    final_shape = (*tensor.shape[:-1], final_index_shape, kernel_width)  # Final shape

    # Construct the stride. The main worry here is to ensure that the dilation striding, and primary
    # striding, now occurs at the correct rate. This is done by taking the current one, multiplying,
    # and putting this in the appropriate location.

    final_stride = (*tensor.stride()[:-1], stride_rate * tensor.stride()[-1], dilation_rate * tensor.stride()[-1])

    # Pad tensor, if requested, to prevent loss of information. All padding goes on the end

    if pad:
        tensor = F.pad(tensor, (0, compensation))

        # Finish by striding and returning

    return tensor.as_strided(final_shape, final_stride)
