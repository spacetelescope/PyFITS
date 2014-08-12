#include <Python.h>
#include <stddef.h>
#include <numpy/arrayobject.h>
#include <numpy/arrayscalars.h>
#include <numpy/ufuncobject.h>


NPY_NO_EXPORT PyTypeObject PyFitsUShortArrType_Type = {
#if defined(NPY_PY3K)
    PyVarObject_HEAD_INIT_(NULL, 0)
#else
    PyObject_HEAD_INIT(NULL)
    0,                                          /* ob_size */
#endif
    "_fitstypes.fits_uint16",                   /* tp_name */
    sizeof(PyShortScalarObject),                /* tp_basicsize */
    0,                                          /* tp_itemsize */
    /* methods */
    0,                                          /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
#if defined(NPY_PY3K)
    0,                                          /* tp_reserved */
#else
    0,                                          /* tp_compare */
#endif
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    0,                                          /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,   /* tp_flags */
    0,                                          /* tp_doc */
    0,                                          /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    0,                                          /* tp_methods */
    0,                                          /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    0,                                          /* tp_init */
    0,                                          /* tp_alloc */
    0,                                          /* tp_new */
    0,                                          /* tp_free */
    0,                                          /* tp_is_gc */
    0,                                          /* tp_bases */
    0,                                          /* tp_mro */
    0,                                          /* tp_cache */
    0,                                          /* tp_subclasses */
    0,                                          /* tp_weaklist */
    0,                                          /* tp_del */
    0,                                          /* tp_version_tag */
};


static PyArray_ArrFuncs fits_ushort_arrfuncs;


#define _ALIGN(type) offsetof(struct {char c; type v;}, v)


PyArray_Descr fits_ushort_descr = {
    PyObject_HEAD_INIT(0)
    &PyFitsUShortArrType_Type,                           /* typeobj */
    NPY_UNSIGNEDLTR,                                     /* kind */
    NPY_USHORTLTR,                                       /* type */
    '>',                                                 /* byteorder */
    0,                                                   /* hasobject */
    0,                                                   /* type_num */
    sizeof(npy_short),                                   /* elsize */
    _ALIGN(npy_short),                                   /* alignment */
    NULL,                                                /* subarray */
    NULL,                                                /* fields */
    NULL,                                                /* names */
    &fits_ushort_arrfuncs                                /* f */
};


#define MAKE_TYPE_TO_FITS_USHORT(TYPE, type)                 \
static void                                                  \
TYPE ## _to_fits_ushort(type *ip, npy_short *op, npy_intp n, \
                        PyArrayObject *NPY_UNUSED(aip),      \
                        PyArrayObject *NPY_UNUSED(aop))      \
{                                                            \
    while (n--) {                                            \
        *op++ = (npy_short) ((*ip++) - 32768);               \
    }                                                        \
}

MAKE_TYPE_TO_FITS_USHORT(FLOAT, npy_uint32);
MAKE_TYPE_TO_FITS_USHORT(DOUBLE, npy_uint64);
MAKE_TYPE_TO_FITS_USHORT(LONGDOUBLE, npy_longdouble);
MAKE_TYPE_TO_FITS_USHORT(BOOL, npy_bool);
MAKE_TYPE_TO_FITS_USHORT(BYTE, npy_byte);
MAKE_TYPE_TO_FITS_USHORT(UBYTE, npy_ubyte);
MAKE_TYPE_TO_FITS_USHORT(SHORT, npy_short);
MAKE_TYPE_TO_FITS_USHORT(USHORT, npy_ushort);
MAKE_TYPE_TO_FITS_USHORT(INT, npy_int);
MAKE_TYPE_TO_FITS_USHORT(UINT, npy_uint);
MAKE_TYPE_TO_FITS_USHORT(LONG, npy_long);
MAKE_TYPE_TO_FITS_USHORT(ULONG, npy_ulong);
MAKE_TYPE_TO_FITS_USHORT(LONGLONG, npy_longlong);
MAKE_TYPE_TO_FITS_USHORT(ULONGLONG, npy_ulonglong);


#define MAKE_FITS_USHORT_TO_TYPE(TYPE, type)                 \
static void                                                  \
fits_ushort_to_ ## TYPE(npy_short *ip, type *op, npy_intp n, \
                        PyArrayObject *NPY_UNUSED(aip),      \
                        PyArrayObject *NPY_UNUSED(aop))      \
{                                                            \
    while (n--) {                                            \
        *op++ = (type) ((*ip++) + 32768);                    \
    }                                                        \
}

MAKE_FITS_USHORT_TO_TYPE(FLOAT, npy_uint32);
MAKE_FITS_USHORT_TO_TYPE(DOUBLE, npy_uint64);
MAKE_FITS_USHORT_TO_TYPE(LONGDOUBLE, npy_longdouble);
MAKE_FITS_USHORT_TO_TYPE(BOOL, npy_bool);
MAKE_FITS_USHORT_TO_TYPE(BYTE, npy_byte);
MAKE_FITS_USHORT_TO_TYPE(UBYTE, npy_ubyte);
MAKE_FITS_USHORT_TO_TYPE(SHORT, npy_short);
MAKE_FITS_USHORT_TO_TYPE(USHORT, npy_ushort);
MAKE_FITS_USHORT_TO_TYPE(INT, npy_int);
MAKE_FITS_USHORT_TO_TYPE(UINT, npy_uint);
MAKE_FITS_USHORT_TO_TYPE(LONG, npy_long);
MAKE_FITS_USHORT_TO_TYPE(ULONG, npy_ulong);
MAKE_FITS_USHORT_TO_TYPE(LONGLONG, npy_longlong);
MAKE_FITS_USHORT_TO_TYPE(ULONGLONG, npy_ulonglong);

static void register_cast_function(int source_type, int dest_type,
                                   PyArray_VectorUnaryFunc *castfunc)
{
    PyArray_Descr *descr = PyArray_DescrFromType(source_type);
    PyArray_RegisterCastFunc(descr, dest_type, castfunc);
    PyArray_RegisterCanCast(descr, dest_type, NPY_NOSCALAR);
    Py_DECREF(descr);
}


#define IS_BINARY_REDUCE ((args[0] == args[2])\
        && (steps[0] == steps[2])\
        && (steps[0] == 0))


#define BINARY_REDUCE_LOOP_INNER\
    char *ip2 = args[1]; \
    npy_intp is2 = steps[1]; \
    npy_intp n = dimensions[0]; \
    npy_intp i; \
    for(i = 0; i < n; i++, ip2 += is2)

#define BINARY_REDUCE_LOOP(TYPE)\
    char *iop1 = args[0]; \
    TYPE io1 = *(TYPE *)iop1; \
    BINARY_REDUCE_LOOP_INNER


#define BINARY_LOOP\
    char *ip1 = args[0], *ip2 = args[1], *op1 = args[2];\
    npy_intp is1 = steps[0], is2 = steps[1], os1 = steps[2];\
    npy_intp n = dimensions[0];\
    npy_intp i;\
    for(i = 0; i < n; i++, ip1 += is1, ip2 += is2, op1 += os1)


static void
fits_ushort_maximum_ufunc(char **args, npy_intp *dimensions, npy_intp *steps,
                          void *NPY_UNUSED(func))
{
    if (IS_BINARY_REDUCE) {
        BINARY_REDUCE_LOOP(npy_short) {
            const npy_short in2 = *(npy_short *)ip2;
            io1 = (io1 > in2) ? io1 : in2;
        }
        *((npy_short *)iop1) = io1;
    }
    else {
        BINARY_LOOP {
            const npy_short in1 = *(npy_short *)ip1;
            const npy_short in2 = *(npy_short *)ip2;
            *((npy_short *)op1) = (in1 > in2) ? in1 : in2;
        }
    }
}


static void
fits_ushort_minimum_ufunc(char **args, npy_intp *dimensions, npy_intp *steps,
                          void *NPY_UNUSED(func))
{
    if (IS_BINARY_REDUCE) {
        BINARY_REDUCE_LOOP(npy_short) {
            const npy_short in2 = *(npy_short *)ip2;
            io1 = (io1 < in2) ? io1 : in2;
        }
        *((npy_short *)iop1) = io1;
    }
    else {
        BINARY_LOOP {
            const npy_short in1 = *(npy_short *)ip1;
            const npy_short in2 = *(npy_short *)ip2;
            *((npy_short *)op1) = (in1 < in2) ? in1 : in2;
        }
    }
}


/* This is basically copied from the @name@_arrtype_new template in
 * numpy/core/src/multiarray/scalartypes.c.src specifially the version from
 * Numpy 1.8.2.  For general use it might be desireable to simply this
 * somewhat rather than maintain more complex versions that happen to work
 * with all supported Numpy versions.  In other words, it may not be necessary
 * for the fits_ types to retain *all* the functionality of the builtin scalar
 * types
 */
static PyObject *
fits_ushort_arrtype_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyObject *obj = NULL;
    PyObject *robj;
    PyArrayObject *arr;
    PyArray_Descr *descr = &fits_ushort_descr;

    int itemsize;
    void *dest, *src;

    if (!PyArg_ParseTuple(args, "|O", &obj)) {
        return NULL;
    }

    Py_INCREF(descr);

    if (obj == NULL) {
        robj = PyArray_Scalar(NULL, descr, NULL);
        if (robj == NULL) {
            Py_DECREF(descr);
            return NULL;
        }
        // Set to "zero"
        memset(&((PyShortScalarObject *)robj)->obval, -32768,
                sizeof(npy_short));
        Py_DECREF(descr);
        goto finish;
    }

    arr = (PyArrayObject *)PyArray_FromAny(obj, &fits_ushort_descr,
                                           0, 0, NPY_ARRAY_FORCECAST, NULL);
    if ((arr == NULL) || (PyArray_NDIM(arr) > 0)) {
        return (PyObject *)arr;
    }

    robj = PyArray_ToScalar(PyArray_DATA(arr), arr);
    Py_DECREF(arr);
finish:
    if ((robj == NULL) || (Py_TYPE(robj) == type)) {
        return robj;
    }

    if (type->tp_itemsize) {
        itemsize = PyBytes_GET_SIZE(robj);
    }
    else {
        itemsize = 0;
    }
    obj = type->tp_alloc(type, itemsize);
    if (obj == NULL) {
        Py_DECREF(robj);
        return NULL;
    }

    dest = &(((PyShortScalarObject *)obj)->obval);
    src = &(((PyShortScalarObject *)robj)->obval);
    *((npy_short *)dest) = *((npy_short *)src);
    Py_DECREF(robj);
    return obj;
}


static PyObject *
fits_ushort_getitem(char *ip, PyArrayObject *ap) {
    npy_ushort t1;

    if (ap == NULL) {
        t1 = *((npy_ushort *)ip) + 32768;
        return PyInt_FromLong((long)t1);
    } else {
        PyArray_DESCR(ap)->f->copyswap(&t1, ip, PyArray_ISNOTSWAPPED(ap), ap);
        t1 += 32768;
        return PyInt_FromLong((long)t1);
    }
}


PyMethodDef module_methods[] = {
    {0} /* module provides no methods, only types */
};


#if defined(NPY_PY3K)
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_fitstypes",
    NULL,
    -1,
    module_methods,
    NULL,
    NULL,
    NULL,
    NULL
};
#endif


#if defined(NPY_PY3K)
PyMODINIT_FUNC PyInit_fitstypes(void) {
#else
PyMODINIT_FUNC init_fitstypes(void) {
#endif

    PyObject *fitstypes_module;
    PyObject *numpy;
    PyObject *numpy_dict;

    PyArray_Descr *npy_short_descr;

    numpy = PyImport_ImportModule("numpy");
    numpy_dict = PyModule_GetDict(numpy);

    import_array();
    import_umath();

    /* Register PyFitsUShortArrType_Type members */
    PyFitsUShortArrType_Type.tp_base = &PyUShortArrType_Type;
    PyFitsUShortArrType_Type.tp_new = &fits_ushort_arrtype_new;

    if (PyType_Ready(&PyFitsUShortArrType_Type) < 0) {
        return -1;
    }

    npy_short_descr = PyArray_DescrFromType(NPY_SHORT);

    /* Initialize fits_uint16 descriptor */
    PyArray_InitArrFuncs(&fits_ushort_arrfuncs);
    fits_ushort_arrfuncs.getitem = &fits_ushort_getitem;
    fits_ushort_arrfuncs.setitem = npy_short_descr->f->setitem;
    fits_ushort_arrfuncs.copyswapn = npy_short_descr->f->copyswapn;
    fits_ushort_arrfuncs.copyswap = npy_short_descr->f->copyswap;
    fits_ushort_arrfuncs.compare = npy_short_descr->f->compare;
    fits_ushort_arrfuncs.argmin = npy_short_descr->f->argmin;
    fits_ushort_arrfuncs.argmax = npy_short_descr->f->argmax;
    fits_ushort_arrfuncs.dotfunc = npy_short_descr->f->dotfunc;
    fits_ushort_arrfuncs.nonzero = npy_short_descr->f->nonzero;
    fits_ushort_arrfuncs.fill = npy_short_descr->f->fill;
    fits_ushort_arrfuncs.fillwithscalar = npy_short_descr->f->fillwithscalar;

    Py_TYPE(&fits_ushort_descr) = &PyArrayDescr_Type;

    int fits_ushort = PyArray_RegisterDataType(&fits_ushort_descr);
    if (fits_ushort < 0) {
        return NULL;
    }

#define REGISTER_CAST(TYPE)                                      \
    register_cast_function(NPY_ ## TYPE, fits_ushort,            \
            (PyArray_VectorUnaryFunc*) TYPE ## _to_fits_ushort); \
    register_cast_function(fits_ushort, NPY_ ## TYPE,            \
            (PyArray_VectorUnaryFunc*) fits_ushort_to_ ## TYPE); \

    REGISTER_CAST(BOOL);
    REGISTER_CAST(BYTE);
    REGISTER_CAST(UBYTE);
    REGISTER_CAST(SHORT);
    REGISTER_CAST(USHORT);
    REGISTER_CAST(INT);
    REGISTER_CAST(UINT);
    REGISTER_CAST(LONG);
    REGISTER_CAST(ULONG);
    REGISTER_CAST(LONGLONG);
    REGISTER_CAST(ULONGLONG);
    REGISTER_CAST(FLOAT);
    REGISTER_CAST(DOUBLE);
    REGISTER_CAST(LONGDOUBLE);

#define REGISTER_UFUNC(name)\
    PyUFunc_RegisterLoopForType(\
        (PyUFuncObject *)PyDict_GetItemString(numpy_dict, #name),\
            fits_ushort, fits_ushort_##name##_ufunc, NULL, NULL)

    REGISTER_UFUNC(maximum);
    REGISTER_UFUNC(minimum);

    /* Support dtype(fits_uint16) syntax */
    if (PyDict_SetItemString(PyFitsUShortArrType_Type.tp_dict, "dtype",
                (PyObject*) &fits_ushort_descr) < 0) {
        return NULL;
    }

#if defined(NPY_PY3K)
    fitstypes_module = PyModule_Create(&moduledef);
#else
    fitstypes_module = Py_InitModule("_fitstypes", module_methods);
#endif

    if (!fitstypes_module) {
        return NULL;
    }

    /* Add fits_uint16 type */
    Py_INCREF(&PyFitsUShortArrType_Type);
    PyModule_AddObject(fitstypes_module, "fits_uint16",
            (PyObject*) &PyFitsUShortArrType_Type);

    return fitstypes_module;
}
