#ifndef RECORDOBJECT_H
#define RECORDOBJECT_H

#define NAME_LEN 20

enum Endians {NAT='=', LIL='<', BIG='>', NET='!'};

enum Item_Types {
    Item_STRING,    Item_CHAR8,
    Item_UINT8,     Item_SINT8,
    Item_UINT16,    Item_SINT16,
    Item_UINT32,    Item_SINT32,
    Item_FLOAT32,   Item_FLOAT64,
    Item_COMPLEX32, Item_COMPLEX64,
    Item_NTYPES,    Item_UNTYPED
};

typedef void (*ItemCastFunc) Py_PROTO((void *, char *, void *, char *));
typedef PyObject * (*ItemGetFunc) Py_PROTO((void *, char *));
typedef int (*ItemSetFunc) Py_PROTO((void *, char *, PyObject *));

/* Item descriptor structure */

typedef struct {
    int      type;
    char     repr[4];
    int      size;
    ItemCastFunc *cast;
    ItemGetFunc get;
    ItemSetFunc set;
} Item_Descr;

/* Item structure */

typedef struct {
    int      leng;           /* first byte from start of record */
    int      type;           /* type of item */
    int      size;           /* size, in bytes, of item type */
    int      swap;           /* byte swap flag */
    ItemCastFunc *cast;      /* function for casting item1 to item2 */
    ItemGetFunc get;         /* function for reading item */
    ItemSetFunc set;         /* function for writing item */
} Item;

/* Dimen structure */

typedef struct {
    int      start;          /* starting index */
    int      stop;           /* stopping index */
    int      step;           /* stepping index */
    int      leng;           /* length of dimension */
    int      size;           /* size, in bytes, of dimension */
    int      flag;           /* flag */
} Dimen;

/* Item object structure */

typedef struct {
    PyObject_HEAD
    char     endn;           /* endianness of data */
    Dimen    *dimn;          /* tuple of record array dimensions */
    Item     *item;          /* tuple of record items */
    char     *pntr;          /* pointer offset into data buffer */
    PyObject *data;          /* data buffer */
} RecordObject;

extern DL_IMPORT(PyTypeObject) Item_Type;
extern DL_IMPORT(PyTypeObject) Record_Type;
extern DL_IMPORT(PyTypeObject) RecArray_Type;

#define Item_Check(op) ((op)->ob_type == &Item_Type)
#define Record_Check(op) ((op)->ob_type == &Record_Type)
#define RecArray_Check(op) ((op)->ob_type == &RecArray_Type)

/*
extern int Format_Name Py_PROTO((char *, char *));
extern int Format_Length Py_PROTO((char *));
extern int Format_Type Py_PROTO((char *));
extern int Format_Size Py_PROTO((char *));
extern int Format_Endian Py_PROTO((char *));
extern char *Format_Next Py_PROTO((char *));
extern int Format_StringLength Py_PROTO((char *));
extern int Format_StringSize Py_PROTO((char *));

extern int Item_FromFormat Py_PROTO((Item *, char, char *, int));
extern int Item_FromItem Py_PROTO((Item *, Item *, int));
extern void Item_Del Py_PROTO((PyObject *));
extern char *Item_Name Py_PROTO((PyObject *));
extern int Item_Offset Py_PROTO((PyObject *));
extern int Item_Length Py_PROTO((PyObject *));
extern char *Item_TypeString Py_PROTO((Item *));
extern int Item_Size Py_PROTO((PyObject *));
extern PyObject *Item_GetItem Py_PROTO((Item *, int, char *));
extern int Item_SetItem Py_PROTO((Item *, int, char *, PyObject *));
extern PyObject *Item_GetSlice Py_PROTO((PyObject *, int, int, char *));
extern int Item_SetSlice Py_PROTO((Item *, char *, int, int, PyObject *));
*/
/* Macro, trading safety for speed */
/*
#define Item_NAME(ip) (((Item *)(ip))->name)
#define Item_OFFSET(ip) (((Item *)(ip))->offset)
#define Item_LENGTH(ip) (((Item *)(ip))->length)
#define Item_TYPE(ip) (((Item *)(ip))->type)
#define Item_SIZE(ip) (((Item *)(ip))->size)

extern Item *Record_FromFormat Py_PROTO((char, char *));
extern Item *Record_FromRecord Py_PROTO((Item *, int, int));
extern PyObject *Record_FormatString Py_PROTO((Dimen *, char, Item *));

extern PyObject *RecObj_FromFormat Py_PROTO((char *, char *, PyObject *));
extern PyObject *RecObj_FromRecord Py_PROTO((Item *, char, int, char *, PyObject *));

extern int Record_Size Py_PROTO((PyObject *));
extern int Record_Length Py_PROTO((PyObject *));
extern PyObject *Record_Format Py_PROTO((PyObject *));
extern char *Record_GetData Py_PROTO((PyObject *));
extern PyObject *Record_GetItem Py_PROTO((PyObject *, int));
extern int Record_SetItem Py_PROTO((PyObject *, int, PyObject *));
extern PyObject *Record_GetSlice Py_PROTO((PyObject *, int, int));
extern int Record_SetSlice Py_PROTO((PyObject *, int, int, PyObject *));
*/

#endif /* RECORDOBJECT_H */
