def _register_patched_dtype_reduce():
    """
    Numpy < 1.7 has a bug when copying/pickling dtype objects with a
    zero-width void type--i.e. ``np.dtype('V0')``.  Specifically, although
    creating a void type is perfectly valid, it crashes when instantiating
    a dtype using a format string of 'V0', which is what is normally returned
    by dtype.__reduce__() for these dtypes.

    See https://github.com/astropy/astropy/pull/3283#issuecomment-81667461
    """

    from distutils.version import LooseVersion as V

    try:
        import numpy as np
    except ImportError:
        NUMPY_LT_1_7 = False
    else:
        NUMPY_LT_1_7 = V(np.__version__) < V('1.7.0')

    if NUMPY_LT_1_7:
        import copy_reg

        # Originally this created an alternate constructor that fixed this
        # issue, and returned that constructor from the new reduce_dtype;
        # however that broke pickling since functions can't be pickled, so now
        # we fix the issue directly within the custom __reduce__

        def reduce_dtype(obj):
            info = obj.__reduce__()
            args = info[1]
            if args[0] == 'V0':
                args = ('V',) + args[1:]
                info = (info[0], args) + info[2:]
            return info

        copy_reg.pickle(np.dtype, reduce_dtype)


_register_patched_dtype_reduce()
