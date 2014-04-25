#include <Python.h>
#include <numpy/arrayobject.h>
#include <numpy/arrayscalars.h>


NPY_NO_EXPORT PyTypeObject PyFitsUShortArrType_Type = {
#if defined(NPY_PY3K)
    PyVarObject_HEAD_INIT_(NULL, 0)
#else
    PyObject_HEAD_INIT(NULL)
    0,                                          /* ob_size */
#endif
    "_fitstypes.fits_uint16",                   /* tp_name */
    sizeof(PyUShortScalarObject),               /* tp_basicsize */
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
    NPY_NEEDS_PYAPI | NPY_USE_GETITEM,                   /* hasobject */
    0,                                                   /* type_num */
    sizeof(npy_ushort),                                  /* elsize */
    _ALIGN(npy_ushort),                                  /* alignment */
    NULL,                                                /* subarray */
    NULL,                                                /* fields */
    NULL,                                                /* names */
    &fits_ushort_arrfuncs                                /* f */
};


static PyObject *
fits_ushort_arrtype_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyObject *obj = NULL;
    PyObject *robj;
    PyArrayObject *arr;

    if (!PyArg_ParseTuple(args, "|O", &obj)) {
        return NULL;
    }

    if (obj == NULL) {
        robj = PyArray_Scalar(NULL, &fits_ushort_descr, NULL);
        if (robj == NULL) {
            return NULL;
        }

        memset(&((PyUShortScalarObject *)robj)->obval, 0, sizeof(npy_ushort));
        goto finish;
    }

    Py_INCREF(&fits_ushort_descr);  /* stolen from PyArray_FromAny */
    arr = (PyArrayObject *)PyArray_FromAny(obj, &fits_ushort_descr, 0, 0,
                                           NPY_ARRAY_FORCECAST, NULL);
    if ((arr == NULL) || (PyArray_NDIM(arr) > 0)) {
        return (PyObject *)arr;
    }

    /* 0-d array */
    robj = PyArray_ToScalar(PyArray_DATA(arr), arr);
    Py_DECREF(arr);

finish:
    if ((robj == NULL) || (Py_TYPE(robj) == type)) {
        return robj;
    }

    //obj = PyArray_FromScalar(robj, &fits_ushort_descr);
    //Py_DECREF(robj);
    return obj;
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
    //PyObject *numpy;
    //PyObject *numpy_dict;

    PyArray_Descr *npy_ushort_descr;

    //numpy = PyImport_ImportModule("numpy");
    //numpy_dict = PyModule_GetDict(numpy);

    import_array();

    /* Register PyFitsUShortArrType_Type members */
    PyFitsUShortArrType_Type.tp_base = &PyUShortArrType_Type;
    PyFitsUShortArrType_Type.tp_new = &fits_ushort_arrtype_new;

    if (PyType_Ready(&PyFitsUShortArrType_Type) < 0) {
        return -1;
    }

    npy_ushort_descr = PyArray_DescrFromType(NPY_USHORT);

    /* Initialize fits_uint16 descriptor */
    PyArray_InitArrFuncs(&fits_ushort_arrfuncs);
    fits_ushort_arrfuncs.getitem = npy_ushort_descr->f->getitem;
    fits_ushort_arrfuncs.setitem = npy_ushort_descr->f->setitem;
    fits_ushort_arrfuncs.copyswapn = npy_ushort_descr->f->copyswapn;
    fits_ushort_arrfuncs.copyswap = npy_ushort_descr->f->copyswap;
    fits_ushort_arrfuncs.compare = npy_ushort_descr->f->compare;
    fits_ushort_arrfuncs.argmin = npy_ushort_descr->f->argmin;
    fits_ushort_arrfuncs.argmax = npy_ushort_descr->f->argmax;
    fits_ushort_arrfuncs.dotfunc = npy_ushort_descr->f->dotfunc;
    fits_ushort_arrfuncs.nonzero = npy_ushort_descr->f->nonzero;
    fits_ushort_arrfuncs.fill = npy_ushort_descr->f->fill;
    fits_ushort_arrfuncs.fillwithscalar = npy_ushort_descr->f->fillwithscalar;

    Py_TYPE(&fits_ushort_descr) = &PyArrayDescr_Type;

    int fits_ushort = PyArray_RegisterDataType(&fits_ushort_descr);
    if (fits_ushort < 0) {
        return NULL;
    }

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
