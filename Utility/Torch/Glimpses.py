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
import numbers
import numpy as np


def view(tensor, input_shape: "tuple, int", output_shape: "tuple, int"):
    """
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

    # Raw  conversion

    if isinstance(input_shape, numbers.Number):
        input_shape = [input_shape]
    if isinstance(output_shape, numbers.Number):
        output_shape = [output_shape]

    # Basic sanity testing
    assert np.prod(input_shape) == np.prod(
        output_shape), "Shapes incompatible: Input shape and output shape were not compatible: "

    slice_length = len(input_shape)
    assert np.array_equal(input_shape, tensor.shape[-slice_length:]), "Input shape and tensor shape not compatible"

    # Construct view resize

    new_view = [*tensor.shape[:-slice_length], *output_shape]

    # view. Return
    return tensor.view(new_view)


def local(tensor, kernel_width: int, stride_rate: int, dilation_rate: int):
    """

    Description:

    This is a function designed to extract a series of kernels generated by standard convolutional
    keyword conventions which could, by broadcasted application of weights, be used to actually perform
    a convolution. The name "local" is due to the fact that the kernels generated are inherently a
    somewhat local phenomenon.

    When calling this function, a series of kernels with shape determined by dilation_rate and kernel_width,
    and with number determined by stride_rate, will be generated along the last dimension of the input tensor.
    The output will be a tensor with an additional dimension on the end, with width equal to the size of
    the kernel, and the second-to-last dimension then indices these kernels.

    Note that the different between initial and final indexing dimensions is:
        compensation = (kernel_width - 1) * dilation_rate

    Padding by this much is guaranteed to prevent information loss.

    """

    # Input Validation

    assert torch.is_tensor(tensor), "Input 'tensor' was not a torch tensor"

    assert isinstance(kernel_width, numbers.Integral), "kernel_width was not an integer. Was %s" % type(kernel_width)
    assert isinstance(stride_rate, numbers.Integral), "stride_rate was not an integer. Was %s" % type(stride_rate)
    assert isinstance(dilation_rate, numbers.Integral), "dilation_rate was not an integer. Was %s" % type(dilation_rate)

    assert kernel_width >= 1, "kernel_width should be greater than or equal to 1"
    assert stride_rate >= 1, "stride_rate should be greater than or equal to 1"
    assert dilation_rate >= 1, "dilation_rate should be greater than or equal to 1"

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

    # perform extraction

    return tensor.as_strided(final_shape, final_stride)


def block(tensor, number):
    """

    Descrption:

    The purpose of this function is to split up the tensor
    into number equally sized units as a view.

    Excess is simply discarded.

    :param tensor:
    :param blocks:
    :return:
    """
    pass

def compress_decompress(compress_dimensions_prior_to : int):
    """
    Description

    The purpose of this function is to return a pair of functions
    designed to compress a tensor down to a retain_dims + 1
    tensor, and decompress them back to the original format
    when called in sequence.


    :param tensor: The tensor to compress dims on, and decompress dims on
    :param compress_dimensions_prior_to: an int, indicating what dimension to retain dimensions beyond.
    :return: Two functions, called compress and decompress.
    """

    #Define the shared memory used by the two functions
    memory = []

    #Define the compression and decompression function
    def compression(tensor):
        """

        Compresses a tensor's extra dimensions. Then returns the compressed tensor,
        and updates decompressed to decompress that point in the stack.

        :param tensor: A tensorflow tensor. Will be compressed up to the indicated
            compress_dimensions_prior_to, declared during compress_decompress.
        :return: A tensorflow tensor. Now has rank equal to compress_dimensions_prior_to + 1
        """
        # Compress the tensor. Do this by first getting and storing the compress shape
        # for decompression, then flattening everything in the compression region.

        compress_shape = tensor.shape[:compress_dimensions_prior_to] #Get restoration shape
        retain_shape = tensor.shape[compress_dimensions_prior_to:] #Get retained shape
        final_shape = [-1, *retain_shape] #Create flattening shape

        memory.append(compress_shape) #Store restore shape
        return tensor.view(final_shape) #Return
    def decompression(tensor):
        """
        Takes the last dimension of a tensor and, based off what the last compression was,
        restores those dimensions. Then discards decompression information information.

        :param tensor: A tensorflow tensor. Should have a first dimension of size equal to
            the product of the compressed dimension shapes.
        :return: A tensorflow tensor. All compressed dimensions have been restored.
        """

        decompression_shape = memory.pop()
        decompression_shape = [*decompression_shape, *tensor.shape[1:]]
        return tensor.view(decompression_shape)
    #Return the functions

    return compression, decompression


