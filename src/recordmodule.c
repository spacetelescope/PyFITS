/*
 *        Recordmodule.c
 */
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include "Python.h"

#ifdef MS_WIN32
#undef DL_IMPORT
#define DL_IMPORT(RTYPE) __declspec(dllexport) RTYPE
#endif

#include "recordmodule.h"

#define VERSION "0.1"

#define IF_NOT(expr) if (!(expr))

static PyObject *RecordError;

/* 
 *        Error Messages
 */

static char seqs_neq[] = "unequal sequence lengths";
/*static char dims_neq[] = "unequal dimension lengths";*/

/*
 *        TYPE ACCESS AND CONVERSION FUNCTIONS
 *
 *  Each record type has an array of functions to cast or coerce data
 *  from other types into its type.  A NULL pointer is used to indicate
 *  that no function exist for coercion between the two types.
 *  
 *  Each record type also has 'set' and 'get' item functions for
 *  converting between record types and builtin Python types, such as
 *  tuples and lists.
 *
 *  All functions handle byte swapping (between different endian
 *  orders) and data alignment issues.
 */

/*
 *        Strings Type
 */

static void
String_from_String(Item *i1, char *p1, Item *i2, char *p2) {
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<i1->size && k<i2->size; k++) p1[k] = p2[k];
    for (; k<i1->size; k++) p1[k] = ' ';
}
static void
String_from_Char8(Item *i1, char *p1, Item *i2, char *p2) {
    register int k; p1 += i1->leng; p2 += i2->leng;
    p1[0] = p2[0];
    for (k=1; k<i1->size; k++) p1[k] = ' ';
}
static ItemCastFunc String_cast[Item_NTYPES] = {
    (ItemCastFunc)String_from_String,
    (ItemCastFunc)String_from_Char8,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
};

static PyObject *
String_get(Item *i1, char *p1) {
    p1 += i1->leng;
    return PyString_FromStringAndSize(p1, i1->size);
}
static int
String_set(Item *i1, char *p1, PyObject *ob) {
    register int k; char *s; p1 += i1->leng;
    IF_NOT(s = PyString_AsString(ob)) return -1;
    for (k=0; k<i1->size && s[k]!='\0'; k++) p1[k] = s[k];
    for (   ; k<i1->size; k++) p1[k] = ' ';
    return 0;
}
static Item_Descr String_descr = {
    Item_STRING, "s", sizeof(char),
    (ItemCastFunc*)String_cast,
    (ItemGetFunc)String_get,
    (ItemSetFunc)String_set};

/*
 *        Char8 Type
 */

static void
Char8_from_String(Item *i1, char *p1, Item *i2, char *p2) {
    p1 += i1->leng; p2 += i2->leng;
    p1[0] = p2[0];
}
static void
Char8_from_Char8(Item *i1, char *p1, Item *i2, char *p2) {
    p1 += i1->leng; p2 += i2->leng;
    p1[0] = p2[0];
}
static ItemCastFunc Char8_cast[Item_NTYPES] = {
    (ItemCastFunc)Char8_from_String,
    (ItemCastFunc)Char8_from_Char8,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
};

static PyObject *
Char8_get(Item *i1, char *p1) {
    p1 += i1->leng;
    return PyString_FromStringAndSize(p1, i1->size);
}
static int
Char8_set(Item *i1, char *p1, PyObject *ob) {
    register int k; char *s; p1 += i1->leng;
    IF_NOT(s = PyString_AsString(ob)) return -1;
    for (k=0; k<i1->size && s[k]!='\0'; k++) p1[k] = s[k];
    for (   ; k<i1->size; k++) p1[k] = ' ';
    return 0;
}
static Item_Descr Char8_descr = {
    Item_CHAR8, "c8", sizeof(char),
    (ItemCastFunc*)Char8_cast,
    (ItemGetFunc)Char8_get,
    (ItemSetFunc)Char8_set};

/*
 *        sInt8 Type
 */

static void
sInt8_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt8_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc sInt8_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)sInt8_from_uInt8,
    (ItemCastFunc)sInt8_from_sInt8,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
};
static PyObject *
sInt8_get(Item *i1, char *p1) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyInt_FromLong(t1.v);
}
static int
sInt8_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyInt_AsLong(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr sInt8_descr = {
    Item_SINT8, "i8", sizeof(signed char),
    (ItemCastFunc*)sInt8_cast,
    (ItemGetFunc)sInt8_get,
    (ItemSetFunc)sInt8_set};

/*
 *        uInt8 Type
 */

static void
uInt8_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt8_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc uInt8_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)uInt8_from_uInt8,
    (ItemCastFunc)uInt8_from_sInt8,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
};
static PyObject *
uInt8_get(Item *i1, char *p1) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyInt_FromLong(t1.v);
}
static int
uInt8_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyInt_AsLong(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr uInt8_descr = {
    Item_UINT8, "I8", sizeof(unsigned char),
    (ItemCastFunc*)uInt8_cast,
    (ItemGetFunc)uInt8_get,
    (ItemSetFunc)uInt8_set};

/*
 *        sInt16 Type
 */

static void
sInt16_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t1;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt16_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t1;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt16_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt16_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc sInt16_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)sInt16_from_uInt8,
    (ItemCastFunc)sInt16_from_sInt8,
    (ItemCastFunc)sInt16_from_uInt16,
    (ItemCastFunc)sInt16_from_sInt16,
    0,
    0,
    0,
    0,
    0,
    0,
};
static PyObject *
sInt16_get(Item *i1, char *p1) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyInt_FromLong(t1.v);
}
static int
sInt16_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyInt_AsLong(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr sInt16_descr = {
    Item_SINT16, "i16", sizeof(signed short),
    (ItemCastFunc*)sInt16_cast,
    (ItemGetFunc)sInt16_get,
    (ItemSetFunc)sInt16_set};

/*
 *        uInt16 Type
 */

static void
uInt16_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t1;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt16_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t1;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt16_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt16_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc uInt16_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)uInt16_from_uInt8,
    (ItemCastFunc)uInt16_from_sInt8,
    (ItemCastFunc)uInt16_from_uInt16,
    (ItemCastFunc)uInt16_from_sInt16,
    0,
    0,
    0,
    0,
    0,
    0,
};
static PyObject *
uInt16_get(Item *i1, char *p1) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyInt_FromLong(t1.v);
}
static int
uInt16_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyInt_AsLong(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr uInt16_descr = {
    Item_UINT16, "I16", sizeof(unsigned short),
    (ItemCastFunc*)uInt16_cast,
    (ItemGetFunc)uInt16_get,
    (ItemSetFunc)uInt16_set};

/*
 *        sInt32 Type
 */

static void
sInt32_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int); 
    union {char s[sizeof(int)]; signed int v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt32_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int); 
    union {char s[sizeof(int)]; signed int v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt32_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);  
    union {char s[sizeof(int)]; signed int v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt32_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);  
    union {char s[sizeof(int)]; signed int v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt32_from_sInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; signed int v;} t1;
    const int s2=sizeof(int);
    union {char s[sizeof(int)]; signed int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
sInt32_from_uInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; signed int v;} t1;
    const int s2=sizeof(int);
    union {char s[sizeof(int)]; unsigned int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc sInt32_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)sInt32_from_uInt8,
    (ItemCastFunc)sInt32_from_sInt8,
    (ItemCastFunc)sInt32_from_uInt16,
    (ItemCastFunc)sInt32_from_sInt16,
    (ItemCastFunc)sInt32_from_uInt32,
    (ItemCastFunc)sInt32_from_sInt32,
    0,
    0,
    0,
    0,
};
static PyObject *
sInt32_get(Item *i1, char *p1) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; signed int v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyInt_FromLong(t1.v);
}
static int
sInt32_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; signed int v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyInt_AsLong(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr sInt32_descr = {
    Item_SINT32, "i32", sizeof(signed int),
    (ItemCastFunc*)sInt32_cast,
    (ItemGetFunc)sInt32_get,
    (ItemSetFunc)sInt32_set};

/*
 *        uInt32 Type
 */

static void
uInt32_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int); 
    union {char s[sizeof(int)]; unsigned int v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt32_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int); 
    union {char s[sizeof(int)]; unsigned int v;} t1;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt32_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);  
    union {char s[sizeof(int)]; unsigned int v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt32_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);  
    union {char s[sizeof(int)]; unsigned int v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt32_from_sInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; unsigned int v;} t1;
    const int s2=sizeof(int);
    union {char s[sizeof(int)]; signed int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
uInt32_from_uInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; unsigned int v;} t1;
    const int s2=sizeof(int);
    union {char s[sizeof(int)]; unsigned int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc uInt32_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)uInt32_from_uInt8,
    (ItemCastFunc)uInt32_from_sInt8,
    (ItemCastFunc)uInt32_from_uInt16,
    (ItemCastFunc)uInt32_from_sInt16,
    (ItemCastFunc)uInt32_from_uInt32,
    (ItemCastFunc)uInt32_from_sInt32,
    0,
    0,
    0,
    0,
};
static PyObject *
uInt32_get(Item *i1, char *p1) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; unsigned int v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyInt_FromLong(t1.v);
}
static int
uInt32_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(int);
    union {char s[sizeof(int)]; unsigned int v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyInt_AsLong(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr uInt32_descr = {
    Item_UINT32, "I32", sizeof(unsigned int),
    (ItemCastFunc*)uInt32_cast,
    (ItemGetFunc)uInt32_get,
    (ItemSetFunc)uInt32_set};

/*
 *        Float32 Type
 */

static void
Float32_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float32_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float32_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float32_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float32_from_sInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(int);  
    union {char s[sizeof(int)]; signed int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float32_from_uInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(int);  
    union {char s[sizeof(int)]; unsigned int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float32_from_Float32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(float);
    union {char s[sizeof(float)]; float v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float32_from_Float64(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float); 
    union {char s[sizeof(float)]; float v;} t1;
    const int s2=sizeof(double);
    union {char s[sizeof(double)]; double v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc Float32_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)Float32_from_uInt8,
    (ItemCastFunc)Float32_from_sInt8,
    (ItemCastFunc)Float32_from_uInt16,
    (ItemCastFunc)Float32_from_sInt16,
    (ItemCastFunc)Float32_from_uInt32,
    (ItemCastFunc)Float32_from_sInt32,
    (ItemCastFunc)Float32_from_Float32,
    (ItemCastFunc)Float32_from_Float64,
    0,
    0,
};
static PyObject *
Float32_get(Item *i1, char *p1) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyFloat_FromDouble(t1.v);
}
static int
Float32_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyFloat_AsDouble(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr Float32_descr = {
    Item_FLOAT32, "f32", sizeof(float),
    (ItemCastFunc*)Float32_cast,
    (ItemGetFunc)Float32_get,
    (ItemSetFunc)Float32_set};

/*
 *        Float64 Type
 */

static void
Float64_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(char);  
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float64_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(char);  
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float64_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(short); 
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float64_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(short); 
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float64_from_sInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(int);   
    union {char s[sizeof(int)]; signed int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float64_from_uInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(int);   
    union {char s[sizeof(int)]; unsigned int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float64_from_Float32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(float); 
    union {char s[sizeof(float)]; float v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static void
Float64_from_Float64(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    const int s2=sizeof(double);
    union {char s[sizeof(double)]; double v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1.v = t2.v;
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
}
static ItemCastFunc Float64_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)Float64_from_uInt8,
    (ItemCastFunc)Float64_from_sInt8,
    (ItemCastFunc)Float64_from_uInt16,
    (ItemCastFunc)Float64_from_sInt16,
    (ItemCastFunc)Float64_from_uInt32,
    (ItemCastFunc)Float64_from_sInt32,
    (ItemCastFunc)Float64_from_Float32,
    (ItemCastFunc)Float64_from_Float64,
    0,
    0,
};
static PyObject *
Float64_get(Item *i1, char *p1) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) t1.s[k] = i1->swap? p1[s1-k-1]: p1[k];
    return PyFloat_FromDouble(t1.v);
}
static int
Float64_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1;
    register int k; p1 += i1->leng;
    t1.v = PyFloat_AsDouble(ob);
    for (k=0; k<s1; k++) p1[k] = i1->swap? t1.s[s1-k-1]: t1.s[k];
    return 0;
}
static Item_Descr Float64_descr = {
    Item_FLOAT64, "f64", sizeof(double),
    (ItemCastFunc*)Float64_cast,
    (ItemGetFunc)Float64_get,
    (ItemSetFunc)Float64_set};

/*
 *        Complex32 Type
 */

static void
Complex32_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(char); 
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(short);
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(short); 
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_sInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(int);  
    union {char s[sizeof(int)]; signed int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_uInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(int);  
    union {char s[sizeof(int)]; unsigned int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_Float32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(float);
    union {char s[sizeof(float)]; float v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_Float64(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float); 
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(double);
    union {char s[sizeof(double)]; double v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_Complex32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(float);
    union {char s[sizeof(float)]; float v;} t2r, t2i;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) {
        t2r.s[k] = i2->swap? p2[s2-k-1]: p2[k];
        t2i.s[k] = i2->swap? (p2+s2)[s2-k-1]: (p2+s2)[k];
    }
    t1r.v = t2r.v; t1i.v = t2i.v;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex32_from_Complex64(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(float); 
    union {char s[sizeof(float)]; float v;} t1r, t1i;
    const int s2=sizeof(double);
    union {char s[sizeof(double)]; double v;} t2r, t2i;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) {
        t2r.s[k] = i2->swap? p2[s2-k-1]: p2[k];
        t2i.s[k] = i2->swap? (p2+s2)[s2-k-1]: (p2+s2)[k];
    }
    t1r.v = t2r.v; t1i.v = t2i.v;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static ItemCastFunc Complex32_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)Complex32_from_uInt8,
    (ItemCastFunc)Complex32_from_sInt8,
    (ItemCastFunc)Complex32_from_uInt16,
    (ItemCastFunc)Complex32_from_sInt16,
    (ItemCastFunc)Complex32_from_uInt32,
    (ItemCastFunc)Complex32_from_sInt32,
    (ItemCastFunc)Complex32_from_Float32,
    (ItemCastFunc)Complex32_from_Float64,
    (ItemCastFunc)Complex32_from_Complex32,
    (ItemCastFunc)Complex32_from_Complex64,
};
static PyObject *
Complex32_get(Item *i1, char *p1) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} r, i;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) {
        r.s[k] = i1->swap? p1[s1-k-1]: p1[k];
        i.s[k] = i1->swap? (p1+s1)[s1-k-1]: (p1+s1)[k];
    }
    return PyComplex_FromDoubles(r.v, i.v);
}
static int
Complex32_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(float);
    union {char s[sizeof(float)]; float v;} r, i;
    register int k; p1 += i1->leng;
    r.v = PyComplex_RealAsDouble(ob); i.v = PyComplex_ImagAsDouble(ob);
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? r.s[s1-k-1]: r.s[k];
        (p1+s1)[k] = i1->swap? i.s[s1-k-1]: i.s[k];
    }
    return 0;
}
static Item_Descr Complex32_descr = {
    Item_COMPLEX32, "F32", 2*sizeof(float),
    (ItemCastFunc*)Complex32_cast,
    (ItemGetFunc)Complex32_get,
    (ItemSetFunc)Complex32_set};

/*
 *        Complex64 Type
 */

static void
Complex64_from_sInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(char);  
    union {char s[sizeof(char)]; signed char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_uInt8(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(char);
    union {char s[sizeof(char)]; unsigned char v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_sInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(short); 
    union {char s[sizeof(short)]; signed short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_uInt16(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(short); 
    union {char s[sizeof(short)]; unsigned short v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_sInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(int);   
    union {char s[sizeof(int)]; signed int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_uInt32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(int);
    union {char s[sizeof(int)]; unsigned int v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_Float32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(float); 
    union {char s[sizeof(float)]; float v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_Float64(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(double);
    union {char s[sizeof(double)]; double v;} t2;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) t2.s[k] = i2->swap? p2[s2-k-1]: p2[k];
    t1r.v = t2.v; t1i.v = 0.0;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_Complex32(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(float); 
    union {char s[sizeof(float)]; float v;} t2r, t2i;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) {
        t2r.s[k] = i2->swap? p2[s2-k-1]: p2[k];
        t2i.s[k] = i2->swap? (p2+s2)[s2-k-1]: (p2+s2)[k];
    }
    t1r.v = t2r.v; t1i.v = t2i.v;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static void
Complex64_from_Complex64(Item *i1, char *p1, Item *i2, char *p2) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} t1r, t1i;
    const int s2=sizeof(double);
    union {char s[sizeof(double)]; double v;} t2r, t2i;
    register int k; p1 += i1->leng; p2 += i2->leng;
    for (k=0; k<s2; k++) {
        t2r.s[k] = i2->swap? p2[s2-k-1]: p2[k];
        t2i.s[k] = i2->swap? (p2+s2)[s2-k-1]: (p2+s2)[k];
    }
    t1r.v = t2r.v; t1i.v = t2i.v;
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? t1r.s[s1-k-1]: t1r.s[k];
        (p1+s1)[k] = i1->swap? t1i.s[s1-k-1]: t1i.s[k];
    }
}
static ItemCastFunc Complex64_cast[Item_NTYPES] = {
    0,
    0,
    (ItemCastFunc)Complex64_from_uInt8,
    (ItemCastFunc)Complex64_from_sInt8,
    (ItemCastFunc)Complex64_from_uInt16,
    (ItemCastFunc)Complex64_from_sInt16,
    (ItemCastFunc)Complex64_from_uInt32,
    (ItemCastFunc)Complex64_from_sInt32,
    (ItemCastFunc)Complex64_from_Float32,
    (ItemCastFunc)Complex64_from_Float64,
    (ItemCastFunc)Complex64_from_Complex32,
    (ItemCastFunc)Complex64_from_Complex64,
};
static PyObject *
Complex64_get(Item *i1, char *p1) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} r, i;
    register int k; p1 += i1->leng;
    for (k=0; k<s1; k++) {
        r.s[k] = i1->swap? p1[s1-k-1]: p1[k];
        i.s[k] = i1->swap? (p1+s1)[s1-k-1]: (p1+s1)[k];
    }
    return PyComplex_FromDoubles(r.v, i.v);
}
static int
Complex64_set(Item *i1, char *p1, PyObject *ob) {
    const int s1=sizeof(double);
    union {char s[sizeof(double)]; double v;} r, i;
    register int k; p1 += i1->leng;
    r.v = PyComplex_RealAsDouble(ob); i.v = PyComplex_ImagAsDouble(ob);
    for (k=0; k<s1; k++) {
        p1[k]      = i1->swap? r.s[s1-k-1]: r.s[k];
        (p1+s1)[k] = i1->swap? i.s[s1-k-1]: i.s[k];
    }
    return 0;
}
static Item_Descr Complex64_descr = {
    Item_COMPLEX64, "F64", 2*sizeof(double),
    (ItemCastFunc*)Complex64_cast,
    (ItemGetFunc)Complex64_get,
    (ItemSetFunc)Complex64_set};

/*
 *        Type Description Table
 *
 *  This table is essentially an array of arrays to functions.  The 
 *  first axis is the destination type and the second axis the source
 *  type.
 */

static Item_Descr *descr_table[Item_NTYPES] = {
    &String_descr,    &Char8_descr,
    &uInt8_descr,     &sInt8_descr,
    &uInt16_descr,    &sInt16_descr,
    &uInt32_descr,    &sInt32_descr,
    &Float32_descr,   &Float64_descr,
    &Complex32_descr, &Complex64_descr,
};

/*
 *        FORMAT STRING FUNCTIONS
 */

/*  A format string is of the form,   "ETss, Tss, Tss",   where
 *    E :  endian of item type
 *         (Default is native endian order.)
 *    T :  type of item (required), and
 *    ss:  size of item type
 *         (Default is largest size of type class, e.g. Int == Int32.)
 */

/*
 *  Utility functions for private format type.
 */

static char *
skip_space(char *fmt) {
    /*
     *  Skips over spaces when parsing the format string.
     */
    for (; *fmt == ' '; fmt++)
        ;
    return fmt;
}

static char
format_swap(char endian) {
    /* 
     *  Return 1, meaning data buffer is to be byte-swapped, when the
     *  endianness of the data type and machine type differ.  This
     *  function tests for the native (machine) endian order.
     */
    int one=1, res=0;

    if (endian == LIL)
        res = ((char *)&one)[0] ^ 1;
    else if (endian == BIG || endian == NET)
        res = ((char *)&one)[0] ^ 0;
    else if (endian == NAT)
        res = 0;
    return res;
}

static char *
format_endian(char *fmt, char *endian) {
    /*
     *  Return endian code if present or native if default.
     */
    *endian = (*fmt==LIL || *fmt==BIG ||
               *fmt==NET || *fmt==NAT)? *fmt++: '=';
    return fmt;
}

static int
type_check(char *fmt, char *dsc) {
    /*
     *  Parses format string and checks for a valid record type.
     */
    if (fmt[0]==dsc[0] && (fmt[1] == ' ' || fmt[1]==',' ||
                           fmt[1]=='\0' || type_check(fmt+1, dsc+1)))
        return 1;
    else
        return 0;
}

static char *
format_type_and_size(char *fmt, int *type, int *size) {
    /*
     *  Parses format string, returning a type's integer identifier
     *  and size when found.
     */
    char c, *r;
    int cnt=0, i;

    for (i=Item_NTYPES-1; i>=0; i--) {
        r = descr_table[i]->repr;
        if (type_check(fmt, r) || (fmt[0]==r[0] && i<=Item_STRING)) {
            *type = i;
            break;
        }
    }
    if (i < 0)
        return 0;
    while (('0' <= (c=*++fmt)) && (c <= '9'))
        cnt = 10*cnt + (c-'0');
    *size = (*type==Item_STRING)? cnt: descr_table[*type]->size;
    return fmt;
}

static char *
Format_Next(char *fmt)
{
    /*
     *  Returns a pointer to the next format type.
     */
    while (*fmt != ',' && *fmt != '\0') fmt++;
    return (*fmt == ','? ++fmt: fmt);
}

static int
Format_StringLength(char *fmt)
{
    /*
     *  Returns the length in bytes of the format string.
     */
    int len;
    for (len=0; *fmt != '\0'; fmt=Format_Next(fmt), len++) ;
    return len;
}

static char *
Format_FromObject(PyObject *data, char *fmt)
{
    /*
     *  Recursively scans a (nested) Python sequence and constructs
     *  an appropriate format string.
     */
    PyObject *obj;
    char str[100];
    int j, size=0, type=0;

    IF_NOT(fmt) {
        IF_NOT(fmt = (char *)PyMem_Malloc(1024))
            return 0;
    }
    if (PyTuple_Check(data)) {
        for (j=0; j<PyTuple_Size(data); j++) {
            if (j > 0)
                strcat(fmt, ", ");
            Format_FromObject(PyTuple_GetItem(data, j), fmt);
        }
    }
    else if (PyList_Check(data) && !PyTuple_Check(PyList_GetItem(data, 0))) {
        for (j=0; j < PyList_Size(data); j++) {
            obj = PyList_GetItem(data, j);
            if      (type <= Item_COMPLEX64 && PyComplex_Check(obj))
                type = Item_COMPLEX64;
            else if (type <= Item_FLOAT64 && PyFloat_Check(obj))
                type = Item_FLOAT64;
            else if (type <= Item_SINT32 && PyInt_Check(obj))
                type = Item_SINT32;
            else if (type <= Item_STRING && PyString_Check(obj)) {
                type = Item_STRING;
                size = PyString_Size(obj) > size? PyString_Size(obj): size;
            }
        }
        if (type == Item_STRING)
            sprintf(str, "%d%s%d", PyList_Size(data), descr_table[type]->repr,
                    size);
        else
            sprintf(str, "%d%s", PyList_Size(data), descr_table[type]->repr);
        strcat(fmt, str);
    }
    else {
        PyErr_SetString(RecordError, "cannot create format string from data");
        if (fmt)
            PyMem_Free(fmt);
        return 0;
    }
    return fmt;
}

/* 
*	List utility function to support Python 2.0.
* 	This code was produced an an official patch to Python 2.0
*	by G. vanRossum and extracted from the CVS archive on SourceForge.
*	This code will be built into Python 2.1 and was not necessary for
*	Python 1.5.2 or earlier.
* 	Revision added by: WJH 15 Feb 2001
*	
*/
static void
_listreverse20(PyListObject *self)
{
	register PyObject **p, **q;
	register PyObject *tmp;
	
	if (self->ob_size > 1) {
		for (p = self->ob_item, q = self->ob_item + self->ob_size - 1;
		     p < q;
		     p++, q--)
		{
			tmp = *p;
			*p = *q;
			*q = tmp;
		}
	}
}


int
PyList_Reverse_v20(PyObject *v)
{
	if (v == NULL || !PyList_Check(v)) {
		PyErr_BadInternalCall();
		return -1;
	}
	_listreverse20((PyListObject *)v);
	return 0;
}

/*
 *        RECORD OBJECT
 */

/*
 *        API functions
*/

static Item *
item_FromFormat(char endian, char *format)
{
    /*
     *  Return an array of Item structs given a format string.
     */
    Item *new;
    char *fmt;
    int j, n_item=0;

    IF_NOT(n_item = Format_StringLength(format))
        return 0; /* format error */
    IF_NOT(new = PyMem_Malloc(sizeof(Item)*(n_item+1)))
        return 0;
    new[0].leng = n_item;
    new[0].size  = 0;
    for (fmt=format, j=1; *fmt!='\0'; fmt=Format_Next(fmt), j++) {
        new[j].swap = format_swap(endian);
        new[j].leng = new[0].size;
        fmt = skip_space(fmt);
        IF_NOT(fmt = format_type_and_size(fmt, &new[j].type, &new[j].size)) {
            PyErr_SetString(RecordError, "bad format type");
            PyMem_Free(new);
            return 0;
        }
        new[j].cast = descr_table[new[j].type]->cast;
        new[j].get  = descr_table[new[j].type]->get;
        new[j].set  = descr_table[new[j].type]->set;
        new[0].size += new[j].size;
    }
    return new;
}

static Item *
item_FromItem(Item *i1, char endian)
{
    /*
     *  Return an Item type from Item data (ie. a copy)
     */
    Item *new;
    int j;
    
    IF_NOT(new = PyMem_Malloc(sizeof(Item)*(i1[0].leng+1)))
        return 0;
    new[0].leng = i1[0].leng;
    new[0].size = 0;
    for (j=1; j <= i1[0].leng; j++) {
        new[j].leng = new[0].size;
        new[j].type = i1[j].type;
        new[j].size = i1[j].size;
        new[j].swap = format_swap(endian);
        new[j].cast = i1[j].cast;
        new[j].get  = i1[j].get;
        new[j].set  = i1[j].set;
        new[0].size += new[j].size;
    }
    return new;
}

static Item *
item_FromItemAndDimen(Item *i1, Dimen *d1, char endian)
{
    /*
     *  Return an Item type from Item and Dimen data.
     */
    Item *new;
    int j, k, leng=0, start=d1[1].start, stop=d1[1].stop, step=d1[1].step;

    leng = 0;
    for (j=start; step < 0? j > stop: j < stop; j+=step)
        leng++;
    IF_NOT(new = PyMem_Malloc(sizeof(Item)*(leng+1)))
        return 0;
    new[0].leng = leng;
    new[0].size = 0;
    for (j=1, k=start; step < 0? k > stop: k < stop; j++, k+=step) {
        new[j].leng = new[0].size;
        new[j].type = i1[k+1].type;
        new[j].size = i1[k+1].size;
        new[j].swap = format_swap(endian);
        new[j].cast = i1[k+1].cast;
        new[j].get  = i1[k+1].get;
        new[j].set  = i1[k+1].set;
        new[0].size += new[j].size;
    }
    return new;
}

static PyObject *
item_asformat(Dimen *d1, char endian, Item *i1)
{
    /*
     *  Create a string representation of an Item type.
     */
    PyObject *format;
    int j, start=d1[1].start, stop=d1[1].stop, step=d1[1].step;
    char str[80];

    sprintf(str, "%c", endian);
    format = PyString_FromString(str);
    for (j=start; step < 0? j > stop: j < stop; j+=step) {
        sprintf(str, "%s", descr_table[i1[j+1].type]->repr);
        PyString_ConcatAndDel(&format, PyString_FromString(str));
        if (strcmp(str, "s") == 0) {
            sprintf(str, "%d", i1[j+1].size);
            PyString_ConcatAndDel(&format, PyString_FromString(str));
        }
        if (j < stop-step) {
            PyString_ConcatAndDel(&format, PyString_FromString(","));
        }
    }
    return format;
}

/*
 *        RecordObject
 */

#ifdef DEBUG
static void
print_dimensions(Dimen *dimen)
{
    /*
     *  This function is only for debug purposes.
     */
    int j;
    for (j=0; j <= dimen[0].leng; j++)
        printf("  %2d: %2d %2d %2d, %2d %d %d\n", j,
               dimen[j].start, dimen[j].stop, dimen[j].step,
               dimen[j].leng, dimen[j].flag, dimen[j].size);
}
#endif

static int *
get_valid_dimens(Dimen *d1)
{
    /* 
     *  Return an integer array of valid dimensions.
     *    dim[0]   is the number of valid dimensions (N),
     *      where N == 0 is a scalar.
     *    dim[1:N] is the array of valid dimensions.
     */
    int *dims, j, k, leng=0;

    for (j=1; j <= d1[0].leng; j++)
        if (d1[j].flag)
            leng++;
    IF_NOT(dims = PyMem_Malloc(sizeof(int)*(leng+1)))
        return 0;
    dims[0] = leng;
    for (j=k=1; j<=d1[0].leng || k<=leng; j++)
        if (d1[j].flag)
            dims[k++] = j;
    return dims;
}

static int
dimen_length(Dimen *d1, int k)
{
    /*  
     *  Return the length of dimension k.
     */
    int leng=0, j, start=d1[k].start, stop=d1[k].stop, step=d1[k].step;
    for (j=start; step < 0? j > stop: j < stop; j+=step)
        leng++;
    return leng;
}

static int
set_index(Dimen *dimen, int k, int ndx)
{
    /*
     *  Set the index of dimension k.
     */
    if (ndx < 0 || ndx >= dimen_length(dimen, k)) {
        PyErr_SetString(PyExc_IndexError, "record index out of range");
        return -1;
    }
    dimen[k].start = ndx;
    dimen[k].stop = ndx+1;
    dimen[k].step = 1;
    dimen[k].flag = 0;
    return 0;
}

static int
set_seq_slice(Dimen *dimen, int k, int min, int max)
{
    /*
     *  Set the min and max data of dimension k
     */
    int leng = dimen[k].stop;
    min = min < 0 ? 0: (min > leng ? leng: min);
    max = max < 0 ? 0: (max > leng ? leng: max);
    if (max < min) max = min;
    dimen[k].start = min;
    dimen[k].stop = max;
    return 0;
}

static int
set_map_slice(Dimen *dimen, int k, PyObject *item)
{
    /*
     *  Set slice data (min, max, step) of dimension k from a
     *  slice object.
     */
    PySliceObject *slice;
    int ndx;

    if (PyInt_Check(item)) {
        ndx = PyInt_AsLong(item);
        if (set_index(dimen, k, ndx))
            return -1;
    }
    else if (PySlice_Check(item)) {
        slice = (PySliceObject *)item;
        if (PySlice_GetIndices(slice, dimen_length(dimen,k), &(dimen[k].start),
                               &(dimen[k].stop), &(dimen[k].step))) {
            PyErr_SetString(PyExc_IndexError, "record index out of range");
            return -1;
        }
        dimen[k].flag = 1;
    }
    else {
        PyErr_SetString(PyExc_IndexError, "bad index type");
        return -1;
    }
    return 0;
}

static int
set_indices(Dimen *dimen, PyObject *key)
{
    /*
     *  Set slice data (min, max, step) for all dimensions.
     */
    int j, k, *dim;

    if (PyTuple_Check(key)) {
        dim = get_valid_dimens(dimen);
        if (PyTuple_Size(key) > dim[0]) {
            PyErr_SetString(PyExc_IndexError, "too many indices");
            return -1;
        }
        for (j=0, k=dim[0]; j < PyTuple_Size(key); j++, k--)
            if (set_map_slice(dimen, dim[k], PyTuple_GetItem(key, j)))
                return -1;
        PyMem_Free(dim);
    }
    else {
        if (set_map_slice(dimen, dimen[0].stop, key))
            return -1;
    }
    dim = get_valid_dimens(dimen);
    if (dim[0] > 0)
        dimen[0].stop = dim[dim[0]];
    else
        dimen[0].stop = dimen[0].flag = 0;
    PyMem_Free(dim);
    return 0;
}

static Dimen *
dimen_fromshape(int *shape, int itemsize)
{
    /*
     *  Create a Dimen array from an integer shape array
     */
    Dimen *new; int j;

    IF_NOT(new = PyMem_Malloc(sizeof(Dimen)*(shape[0]+1)))
        return 0;
    for (j=0; j <= shape[0]; j++) {
        new[j].start = 0;
        new[j].step  = new[j].flag = 1;
        new[j].stop  = new[j].leng = shape[j];
    }
    new[0].size = itemsize;
    if (shape[0] > 0)
        new[1].size = 0;
    for (j=2; j <= shape[0]; j++) {
        new[j].size  = new[0].size;
        new[0].size *= new[j].leng;
    }
    return new;
}

static Dimen *
dimen_FromCopy(Dimen *d1, int itemsize)
{
    /*
     *  Copy a Dimen array, reducing dimensions if necessary
     */
    Dimen *new;
    int j, k, leng, n_dimn;

    n_dimn = 1;
    for (j=2; j <= d1[0].leng; j++) {
        if (d1[j].flag)
            n_dimn++;
    }
    IF_NOT(new = PyMem_Malloc(sizeof(Dimen)*(n_dimn+1)))
        return 0;
    for (j=0, k=0; j <= n_dimn; j++, k++) {
        if (j == 0)
            leng = n_dimn;
        else if (j == 1)
            leng = d1[1].flag? dimen_length(d1, 1): 1;
        else {
            while (d1[k].flag == 0) k++;
            leng = dimen_length(d1, k);
        }
        new[j].start = new[j].size = 0;
        new[j].step  = new[j].flag = 1;
        new[j].stop  = new[j].leng = leng;
    }
    new[1].flag = d1[1].flag;
    new[0].size = itemsize;
    new[1].size = 0;
    for (j=2; j <= n_dimn; j++) {
        new[j].size  = new[0].size;
        new[0].size *= new[j].leng;
    }
    return new;
}

static Dimen *
dimen_FromClone(Dimen *d1)
{
    /*
     *  Clone a Dimen array
     */
    Dimen *new;
    int j;

    IF_NOT(new = PyMem_Malloc(sizeof(Dimen)*(d1[0].leng+1)))
        return 0;
    for (j=0; j < d1[0].leng+1; j++) {
        new[j].start = d1[j].start;
        new[j].stop = d1[j].stop;
        new[j].step = d1[j].step;
        new[j].flag = d1[j].flag;
        new[j].leng = d1[j].leng;
        new[j].size = d1[j].size;
    }
    return new;
}

static int
get_array_shape(int dim, PyObject *data, PyObject *shape)
{
    /*
     *  Determine shape of a list of tuples
     */
    PyObject *obj, *tupl;
    int j, leng, size, type, ret=0;

    if (PyTuple_Check(data)) {
        leng = PyTuple_Size(data);
        if (PyList_Size(shape) < dim) {
            tupl = PyTuple_New(leng);
            for (j=0; j < leng; j++)
                PyTuple_SetItem(tupl, j, PyInt_FromLong(0));
            PyList_Append(shape, tupl);
            Py_DECREF(tupl);
        }
        else if (PyTuple_Size(PyList_GetItem(shape, dim-1)) != leng)
            return -1;
        tupl = PyList_GetItem(shape, dim-1);
        for (j=0; j < leng; j++) {
            type = PyInt_AsLong(PyTuple_GetItem(tupl, j));
            obj  = PyTuple_GetItem(data, j);
            if (PyString_Check(obj)) {
                size = PyString_Size(obj);
                if (-size < type)
                    PyTuple_SetItem(tupl, j, PyInt_FromLong(-size));
            }
            else if (PyInt_Check(obj) && (0<=type && type<Item_SINT32))
                PyTuple_SetItem(tupl, j, PyInt_FromLong(Item_SINT32));
            else if (PyFloat_Check(obj) && (0<=type && type<Item_FLOAT64))
                PyTuple_SetItem(tupl, j, PyInt_FromLong(Item_FLOAT64));
            else if (PyComplex_Check(obj) && (0<=type && type<Item_COMPLEX64))
                PyTuple_SetItem(tupl, j, PyInt_FromLong(Item_COMPLEX64));
        }
    }
    else if (PyList_Check(data)) {
        leng = PyList_Size(data);
        if (PyList_Size(shape) < dim) {
            PyList_Append(shape, PyInt_FromLong(leng));
        }
        else if (PyInt_AsLong(PyList_GetItem(shape, dim-1)) != leng)
            return -1;
        for (j=0; j < leng; j++) {
            if ((ret = get_array_shape(dim+1, PyList_GetItem(data, j), shape)))
                return -1;
        }
    }
    else {
        return -1;
    }
    return 0;
}

static int
compare_record(Dimen *d1, Item *i1, Dimen *d2, Item *i2)
{
    /*
     *  Return true if array shapes match and array types can be cast.
     */
    int start1 = d1[1].start, stop1 = d1[1].stop, step1=d1[1].step;
    int start2 = d2[1].start, stop2 = d2[1].stop, step2=d2[1].step;
    int j1, j2, *dim1=0, *dim2=0;

    IF_NOT(dim1 = get_valid_dimens(d1))
        goto error;
    IF_NOT(dim2 = get_valid_dimens(d2))
        goto error;
    if (dim1[0] != dim2[0]) {
        PyErr_SetString(RecordError, "array shapes are not equal");
        goto error;
    }
    for (j1=1; j1 <= dim1[0]; j1++) {
#ifdef DEBUG
        printf("compare_record: %d\n", j1);
#endif
        if (dimen_length(d1, dim1[j1]) != dimen_length(d2, dim2[j1])) {
            PyErr_SetString(RecordError, seqs_neq);
            goto error;
        }
    }
    for (j1=start1, j2=start2;
         (step1<0? j1>stop1: j1<stop1) && (step2<0? j2>stop2: j2<stop2);
         j1+=step1, j2+=step2) {
        if (i1[j1+1].cast[i2[j2+1].type] == 0) {
            PyErr_SetString(RecordError, "cannot cast items");
            goto error;
        }
    }
    PyMem_Free(dim1);
    PyMem_Free(dim2);
    return 1;
 error:
    if (dim1) PyMem_Free(dim1);
    if (dim2) PyMem_Free(dim2);
    return 0;
}

static int
cast_record(int dim1, Dimen *d1, Item *i1, char *p1,
            int dim2, Dimen *d2, Item *i2, char *p2)
{
    /*
     *  Recursively descend the Record array and coerce the data of
     *  one record type into another record type.
     */
    int j1, j2;

    while((dim1 > 1) && (d1[dim1].flag == 0)) {
        p1 += d1[dim1].size*d1[dim1].start;
        dim1--;
    }
    while((dim2 > 1) && (d2[dim2].flag == 0)) {
        p2 += d2[dim2].size*d2[dim2].start;
        dim2--;
    }
    if (dim1 == 1 && dim2 == 1) {
        for (j1=d1[dim1].start, j2=d2[dim2].start;
             d1[dim1].step < 0? j1 > d1[dim1].stop: j1 < d1[dim1].stop;
             j1+=d1[dim1].step, j2+=d2[dim2].step)
            (*i1[j1+1].cast[i2[j2+1].type])(&i1[j1+1], p1, &i2[j2+1], p2);
    }
    else if (dim1 > 1 && dim2 > 1) {
        for (j1=d1[dim1].start, j2=d2[dim2].start;
             d1[dim1].step < 0? j1 > d1[dim1].stop: j1 < d1[dim1].stop;
             j1+=d1[dim1].step, j2+=d2[dim2].step)
            if (cast_record(dim1-1, d1, i1, p1+d1[dim1].size*j1,
                            dim2-1, d2, i2, p2+d2[dim2].size*j2))
                goto error;
    }
    else {
        PyErr_SetString(RecordError, "Internal Record error while casting");
        goto error;
    }
    return 0;
 error:
    return -1;
}

static PyObject *
get_record(int dim, Dimen *d1, Item *i1, char *p1) {
    /*
     *  Convert a Record to a Python sequence.
     */
    PyObject *obj;
    int start=d1[dim].start, stop=d1[dim].stop, step=d1[dim].step;
    int j, k, leng, size=d1[dim].size;

    for (k=start, leng=0; step < 0? k > stop: k < stop; k+=step, leng++);
    if (dim == 1) {
        if (d1[dim].flag) {
            IF_NOT(obj = PyTuple_New(leng))
                return PyErr_NoMemory();
            for (k=start, j=0; step < 0? k > stop: k < stop; k+=step, j++)
                PyTuple_SetItem(obj, j, (*i1[k+1].get)(&i1[k+1], p1));
        }
        else
            obj = (*i1[start+1].get)(&i1[start+1], p1);
    }
    else {
        if (d1[dim].flag) {
            IF_NOT(obj = PyList_New(leng))
                return PyErr_NoMemory();
            for (k=start, j=0; step < 0? k > stop: k < stop; k+=step, j++)
                PyList_SetItem(obj, j, get_record(dim-1, d1, i1, p1+size*k));
        }
        else
            obj = get_record(dim-1, d1, i1, p1+size*start);
    }
    return obj;
}

static int
set_record(int dim, Dimen *d1, Item *i1, char *p1, PyObject *obj) {
    /*
     *  Convert a Python sequence to a Record.
     */
    int start=d1[dim].start, stop=d1[dim].stop, step=d1[dim].step;
    int j, k, size=d1[dim].size, result=0;

    if (dim == 1) {
        if (PyTuple_Check(obj)) {
            for (k=start, j=0;
                 (step < 0 ? k > stop: k < stop) && (result==0);
                 k+=step, j++)
                result = (*i1[k+1].set)(&i1[k+1], p1, PyTuple_GetItem(obj, j));
        }
        else
            result = (*i1[start+1].set)(&i1[start+1], p1, obj);
    }
    else {
        if (PyList_Check(obj)) {
            for (k=start, j=0;
                 (step < 0 ? k > stop: k < stop) && (result == 0);
                 k+=step, j++)
                result = set_record(dim-1, d1, i1, p1+size*k,
                                 PyList_GetItem(obj, j));
        }
        else
            result = set_record(dim-1, d1, i1, p1+size*start, obj);
    }
    return result;
}

static PyObject *
new_record(Dimen *dimn, Item *item, char endn, char *pntr, PyObject *data)
{
    /*
     *  Create a new record object from given Dimen, Item, and Data
     */
    RecordObject *new;

    IF_NOT(new = PyObject_NEW(RecordObject, &Record_Type))
        return 0;
    new->dimn = dimn;
    new->item = item;
    new->endn = endn;
    new->pntr = pntr;
    new->data = data;
    Py_INCREF(data);
    return (PyObject *)new;
}

/*
 *        Standard object methods
 */
static PyObject *
record_new(PyObject *this, PyObject *args, PyObject *opts)
{
    /*
     *  Create new record object from a nested list of tuples and an
     *  optional format string.
     */
    char *keys[] = {"data", "format", 0};
    PyObject *data=0;
    char *format=0;
    Dimen *dimen=0;
    Item *item=0;
    PyObject *new=0, *shape=0, *buffer=0, *tuple;
    char endian, *fmt, *pntr, str[20];
    int j, n_dimn, n_item, type, *dims;
    double size;

#ifdef DEBUG
    printf("record_new: this=%p\n", this);
#endif
    /* get constructor arguments and keywords */
    IF_NOT(PyArg_ParseTupleAndKeywords(args, opts, "O|s", keys,
                                       &data, &format))
        goto error;
    /*  check shape for sequence or scalar  */
    shape = PyList_New(0);
    /*  clean up get_array_shape use PyList_Insert to add dims  */
    if (get_array_shape(1, data, shape)) {
        PyErr_SetString(PyExc_ValueError, "Cannot determine shape of data");
        goto error;
    }
    n_dimn = PyList_Size(shape);

    /*  create record list  */
    if (format) {
        fmt = skip_space(format);
        fmt = format_endian(fmt, &endian);
        IF_NOT(item = item_FromFormat(endian, fmt))
            goto error; /* memory error or format error */
    }
    else {
        endian = NAT;
        tuple = PyList_GetItem(shape, n_dimn-1);
        n_item = PyTuple_Size(tuple);
        IF_NOT(fmt = PyMem_Malloc(20*sizeof(char)*n_item))
            goto error;
        for (j=0; j < 20*sizeof(char)*n_item; j++)
            fmt[j] = '\0';
        for (j=0; j < n_item; j++) {
            type = PyInt_AsLong(PyTuple_GetItem(tuple, j));
            if (type < 0) {
                sprintf(str, "s%d", -type);
                strcat(fmt, str);
            }
            else if (type == Item_SINT32)
                strcat(fmt, "i32");
            else if (type == Item_FLOAT64)
                strcat(fmt, "f64");
            else if (type == Item_COMPLEX64)
                strcat(fmt, "F64");
            else {
                PyErr_SetString(RecordError, "Unkown format type");
                goto error;
            }
            if (j < n_item-1)
                strcat(fmt, ",");
        }
        IF_NOT(item = item_FromFormat(endian, fmt))
            goto error; /*  memory error or format error  */
        PyMem_Free(fmt);
    }
    if (PyList_Reverse(shape)) {
        PyErr_BadInternalCall();
        goto error;
    }
#ifdef PyVer20
	PyList_Reverse_v20(shape);
#else
	PyList_Reverse(shape);
#endif
    PyList_SetItem(shape, 0, PyInt_FromLong(item[0].leng));
    size = item[0].size;
    for (j = 1; j < n_dimn; j++)
        size *= PyInt_AsLong(PyList_GetItem(shape, j));
    if (size > INT_MAX) {
        PyErr_SetString(PyExc_ValueError, "string size >2GB");
        goto error;
    }
    /*  create dimen list  */
    IF_NOT(dims = PyMem_Malloc(sizeof(int)*(n_dimn+1)))
        goto error;
    for (j=0; j <= n_dimn; j++)
        dims[j] = j == 0? n_dimn: PyInt_AsLong(PyList_GetItem(shape, j-1));
    IF_NOT(dimen = dimen_fromshape(dims, item[0].size))
        goto error;
    dimen[1].leng = item[0].leng;
    Py_DECREF(shape);
    PyMem_Free(dims);
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    /*  create and initialize data  */
    IF_NOT(buffer = PyString_FromStringAndSize(0, dimen[0].size))
        goto error;
    pntr = PyString_AsString(buffer);
    IF_NOT(new = new_record(dimen, item, endian, pntr, buffer))
        goto error;
    Py_DECREF(buffer);
    if (set_record(n_dimn, dimen, item, pntr, data))
        goto error;
    return new;
 error:
    if (new) {Py_DECREF(new);}
    if (buffer) PyMem_Free(buffer);
    if (dimen) PyMem_Free(dimen);
    if (item)  PyMem_Free(item);
    return 0;
}

static void
record_dealloc(RecordObject *this)
{
    /*
     *  De-allocate a record's memory
     */
    if (this->data) {
        Py_DECREF(this->data);
    }
    else {
        printf("recordarray data ptr is null\n");
    }
    PyMem_Free(this->dimn);
    PyMem_Free(this->item);
    PyMem_Free(this);
}

static PyObject *
record_print(RecordObject *this, FILE *file, int flags)
{
    /*
     *  Print a record, nicely
     */
    PyObject *obj;
    obj = get_record(this->dimn[0].leng, this->dimn, this->item, this->pntr);
    PyObject_Print(obj, file, flags);
    Py_DECREF(obj);
    return 0;
}

/*
 *        Additional object methods
 */
static PyObject *
record_copy(RecordObject *this, PyObject *args, PyObject *opts)
{
    /*
     *  Return a copy of this object
     */
    char *keys[]={"endian", 0};
    PyObject *new=0, *buffer=0;
    Dimen *dimen=0;  Item *item=0;
    char endian, *endn=0, *pntr;

    IF_NOT(PyArg_ParseTupleAndKeywords(args, opts, "|s", keys, &endn))
        goto error;
    if (endn) {
        if (endn[0]==LIL || endn[0]==BIG || endn[0]==NET || endn[0]==NAT)
            endian = endn[0];
        else {
            PyErr_SetString(RecordError, "Unknown endian type");
            goto error;
        }
    }
    else
        endian = this->endn;
    /* create new item and dimen structures */
    IF_NOT(item = item_FromItemAndDimen(this->item, this->dimn, endian))
        goto error;
    IF_NOT(dimen = dimen_FromCopy(this->dimn, item[0].size))
        goto error;
#ifdef DEBUG
    print_dimensions(dimen);
    print_dimensions(this->dimn);
#endif
    IF_NOT(buffer = PyString_FromStringAndSize(0, dimen[0].size))
        goto error;
    pntr = PyString_AsString(buffer);
    IF_NOT(compare_record(dimen, item, this->dimn, this->item))
        goto error;
    if (cast_record(dimen[0].leng, dimen, item, pntr,
                    this->dimn[0].leng, this->dimn, this->item, this->pntr))
        goto error;
    IF_NOT(new = new_record(dimen, item, endian, pntr, buffer))
        goto error;
    Py_DECREF(buffer);
    return new;
 error:
    if (buffer) PyMem_Free(buffer);
    if (dimen)  PyMem_Free(dimen);
    if (item)   PyMem_Free(item);
    return 0;
}

static PyObject *
record_tostring(RecordObject *this, PyObject *args, PyObject *opts)
{
    /*
     *  Return data as a string object
     */
    char *keys[]={"endian", 0};
    PyObject *new;
    Dimen *dimen=0;  Item *item=0;
    int  *dims=0, *shape=0;
    char endian, *endn=0, *pntr;

    IF_NOT(PyArg_ParseTupleAndKeywords(args, opts, "|s", keys, &endn))
        goto error;
    if (endn) {
        if (endn[0]==LIL || endn[0]==BIG || endn[0]==NET || endn[0]==NAT)
            endian = endn[0];
        else {
            PyErr_SetString(RecordError, "Unknown endian type");
            goto error;
        }
    }
    else
        endian = this->endn;

    IF_NOT(item = item_FromItemAndDimen(this->item, this->dimn, endian))
        goto error;
    IF_NOT(dimen = dimen_FromCopy(this->dimn, item[0].size))
        goto error;
    IF_NOT(new = PyString_FromStringAndSize(0, dimen[0].size))
        goto error;
    pntr = PyString_AsString(new);
#ifdef DEBUG
    print_dimensions(dimen);
    print_dimensions(this->dimn);
#endif
    IF_NOT(compare_record(dimen, item, this->dimn, this->item))
        goto error;
    if (cast_record(dimen[0].leng, dimen, item, pntr,
                    this->dimn[0].leng, this->dimn, this->item, this->pntr))
        goto error;
    PyMem_Free(dimen);
    PyMem_Free(shape);
    PyMem_Free(dims);
    PyMem_Free(item);
    return new;
 error:
    if (dimen) PyMem_Free(dimen);
    if (shape) PyMem_Free(shape);
    if (dims)  PyMem_Free(dims);
    if (item)  PyMem_Free(item);
    return 0;
}

static PyMethodDef record_methods[]=
{
    {"copy",       (PyCFunction)record_copy,      METH_VARARGS|METH_KEYWORDS,
     "copy()"                                     /* rec.copy() */
    },
    {"tostring",   (PyCFunction)record_tostring,  METH_VARARGS|METH_KEYWORDS,
     "tostring()"                                 /* rec.tostring() */
    },
    {0,            0}
};

static PyObject *
record_getattr(RecordObject *this, char *name)
{
    /*
     *  Return record attributes
     */
    PyObject *ret=0;
    int j, *dim, leng;

    /*  shape attribute  */
    if (strcmp(name, "shape") == 0) {
        dim = get_valid_dimens(this->dimn);
        IF_NOT(ret = PyTuple_New(dim[0]))
            return 0;
        for (j=0; j < dim[0]; j++) {
            leng = dimen_length(this->dimn, dim[dim[0]-j]);
            PyTuple_SetItem(ret, j, PyInt_FromLong(leng));
        }
        PyMem_Free(dim);
    }
    /*  format attribute  */
    else if (strcmp(name, "format") == 0) {
        ret = item_asformat(this->dimn, this->endn, this->item);
    }
    else {
        ret = Py_FindMethod(record_methods, (PyObject *)this, name);
    }
    return ret;
}

static int
record_setattr(RecordObject *this, char *name, PyObject *obj)
{
    /*
     *  Set a record attribute
     */
    char *format, *fmt, endian;
    Item *item=0;
    Dimen *dimen=0;
    int  *dims=0, j, n_dimn;

    /*  shape attribute  */
    if (strcmp(name, "shape") == 0) {
        IF_NOT(PyTuple_Check(obj)) {
            PyErr_SetString(PyExc_ValueError, "expecting tuple type");
            goto error;
        }
        n_dimn = PyTuple_Size(obj);
        IF_NOT(dims = PyMem_Malloc(sizeof(int)*(n_dimn+1)))
            goto error;
        for (j=0; j <= n_dimn; j++) {
            dims[j] = j == 0? n_dimn:
                PyInt_AsLong(PyTuple_GetItem(obj, n_dimn-j));
        }
        IF_NOT(dimen = dimen_fromshape(dims, this->item[0].size))
            goto error;
#ifdef DEBUG
        print_dimensions(dimen);
#endif
        if (dimen[0].size != this->dimn[0].size) {
            PyErr_SetString(RecordError, "array shapes not equal");
            goto error;
        }
        PyMem_Free(dims);
        PyMem_Free(this->dimn);
        this->dimn = dimen;
    }
    /*  format attribute  */
    else if (strcmp(name, "format") == 0) {
        IF_NOT(PyString_Check(obj)) {
            PyErr_SetString(PyExc_ValueError, "expecting string type");
            goto error;
        }
        format = PyString_AsString(obj);
        fmt = skip_space(format);
        fmt = format_endian(fmt, &endian);
        IF_NOT(item = item_FromFormat(endian, fmt))
            goto error; /* memory error or format error */
        if (item[0].size != this->item[0].size) {
            PyErr_SetString(RecordError, "format string lengths not equal");
            goto error;
        }
        if (item[0].leng != dimen_length(this->dimn, 1)) {
            if (this->dimn[1].flag == 0 || this->dimn[1].start != 0 || 
                this->dimn[1].step != 1) {
                PyErr_SetString(RecordError, "cannot change format "
                                "of non-contiguous array");
                goto error;
            }
            this->dimn[1].stop = this->dimn[1].leng = item[0].leng;
        }
        PyMem_Free(this->item);
        this->item = item;
    }
    else {
        PyErr_SetString(PyExc_AttributeError, name);
        return -1;
    }
    return 0;
 error:
    if (dims) PyMem_Free(dims);
    if (dimen) PyMem_Free(dimen);
    if (item) PyMem_Free(item);
    return -1;
}

static PyObject *
record_repr(RecordObject *this)
{
    /*
     *  Return a representation the record type, ie. a string that
     *  can be eval-ed.
     */
    PyObject *new, *obj;

    new = PyString_FromString("record(");
    obj = get_record(this->dimn[0].leng, this->dimn, this->item, this->pntr);
    PyString_ConcatAndDel(&new, PyObject_Repr(obj));
    Py_DECREF(obj);
    PyString_ConcatAndDel(&new, PyString_FromString(", format='"));
    PyString_ConcatAndDel(&new, item_asformat(this->dimn, this->endn,
                                                    this->item));
    PyString_ConcatAndDel(&new, PyString_FromString("')"));
    return new;
}
/*
 *        Sequence Type
 */
static int
record_length(RecordObject *this)
{
    /*
     *  Return length of highest valid dimension.
     *  (Return 1 for 0-D arrays because a[0] works.)
     */
    return dimen_length(this->dimn, this->dimn[0].stop);
}

static PyObject *
record_getseqitem(RecordObject *this, int ndx)
{
    /*
     *  Get items from an array of records, slice notation a[i:j].
     */
    PyObject *obj=0; Dimen *dimen=0; Item *item=0;
#ifdef DEBUG
    printf("record_getseqitem: this=%p, slice=%d\n", this, ndx);
#endif
    IF_NOT(dimen = dimen_FromClone(this->dimn))
        goto error;
    if (set_index(dimen, dimen[0].stop, ndx))
        goto error;
    dimen[0].stop--;
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    if (dimen[0].flag) {
        IF_NOT(item = item_FromItem(this->item, this->endn))
            goto error;
        obj = new_record(dimen, item, this->endn, this->pntr, this->data);
    }
    else { /* return a scalar object */
        obj = get_record(dimen[0].leng, dimen, this->item, this->pntr);
        PyMem_Free(dimen);
    }
    return obj;
 error:
    if (dimen) PyMem_Free(dimen);
    return 0;
}

static PyObject *
record_getseqslice(RecordObject *this, int min, int max)
{
    /*
     *  Get items from an array of records, slice notation a[i:j].
     */
    PyObject *obj=0; Dimen *dimen=0; Item *item=0;
#ifdef DEBUG
    printf("record_getseqslice: this=%p, slice=%d, %d\n", this, min, max);
#endif
    IF_NOT(dimen = dimen_FromClone(this->dimn))
        goto error;
    if (set_seq_slice(dimen, dimen[0].stop, min, max))
        goto error;
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    if (dimen[0].flag) {
        IF_NOT(item = item_FromItem(this->item, this->endn))
            goto error;
        obj = new_record(dimen, item, this->endn, this->pntr, this->data);
    }
    else { /* return a scalar object */
        obj = get_record(dimen[0].leng, dimen, this->item, this->pntr);
        PyMem_Free(dimen);
    }
    return obj;
 error:
    if (dimen) PyMem_Free(dimen);
    return 0;
}

static int
record_setseqitem(RecordObject *this, int ndx, PyObject *obj)
{
    /*
     *  Assign items to an array of records, for slice notation, a[i:j].
     */
    RecordObject *robj=0; Dimen *dimen=0;
#ifdef DEBUG
    printf("record_setseqitem: this=%p, slice=%d\n", this, ndx);
#endif
    if (obj == 0) {
        PyErr_SetString(PyExc_ValueError, "cannot delete record items");
        goto error;
    }
    IF_NOT(dimen = dimen_FromClone(this->dimn))
        goto error;
    if (set_index(dimen, dimen[0].stop, ndx))
        goto error;
    dimen[0].stop--;
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    if (Record_Check(obj)) {
        robj = (RecordObject *)obj;
        IF_NOT(compare_record(dimen, this->item, robj->dimn, robj->item))
            goto error;
        if (cast_record(dimen[0].leng, dimen, this->item, this->pntr,
                        robj->dimn[0].leng, robj->dimn, robj->item,
                        robj->pntr))
            goto error;
    }
    else {
        if (set_record(dimen[0].leng, dimen, this->item, this->pntr, obj))
            goto error;
    }
    PyMem_Free(dimen);
    return 0;
 error:
    if (dimen) PyMem_Free(dimen);
    return -1;
}

static int
record_setseqslice(RecordObject *this, int min, int max, PyObject *obj)
{
    /*
     *  Assign items to an array of records, for slice notation, a[i:j].
     */
    RecordObject *robj=0; Dimen *dimen=0;
#ifdef DEBUG
    printf("record_setseqslice: this=%p, slice=%d, %d\n", this, min,max);
#endif
    if (obj == 0) {
        PyErr_SetString(PyExc_ValueError, "cannot delete record items");
        goto error;
    }
    IF_NOT(dimen = dimen_FromClone(this->dimn))
        goto error;
    set_seq_slice(dimen, dimen[0].stop, min, max);
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    if (Record_Check(obj)) {
        robj = (RecordObject *)obj;
        IF_NOT(compare_record(dimen, this->item, robj->dimn, robj->item))
            goto error;
        if (cast_record(dimen[0].leng, dimen, this->item, this->pntr,
                        robj->dimn[0].leng, robj->dimn, robj->item,
                        robj->pntr))
            goto error;
    }
    else {
        if (set_record(dimen[0].leng, dimen, this->item, this->pntr, obj))
            goto error;
    }
    PyMem_Free(dimen);
    return 0;
 error:
    if (dimen) PyMem_Free(dimen);
    return -1;
}

/*
 *  Function table for Python sequence behavior.
 *
 *  This table is mainly used to handle x[i:j], x[i:j] = y, and 
 *  len(x) semantics.  Mapping behavior handles the remaining
 *  Python semantics.
 */

static PySequenceMethods record_as_sequence = {
    (inquiry)         record_length,          /* seq_length    "len(x)"   */
    0,/*(binaryfunc)record_concat,*/          /* seq_concat    "x + y"    */
    0,/*(intargfunc)record_repeat,*/          /* seq_repeat    "x * y"    */
    (intargfunc)      record_getseqitem,      /* seq_get_item  "x[i], in" */
    (intintargfunc)   record_getseqslice,     /* seq_get_slice "x[i:j]"   */
    (intobjargproc)   record_setseqitem,      /* seq_set_item  "x[i] = y" */
    (intintobjargproc)record_setseqslice,     /* seq_set_slice "x[i:j]=y" */
};

/*
 *        Mapping Type
 */

static PyObject *
record_getmapitem(RecordObject *this, PyObject *key)
{
    /*
     *  Get items from an array of records
     */
    PyObject *obj;
    Dimen *dimen=0;
    Item *item=0;
#ifdef DEBUG
    printf("record_getmapitem: this=%p, key=%p\n", this, key);
#endif
    IF_NOT(dimen = dimen_FromClone(this->dimn))
        goto error;
    if (set_indices(dimen, key))
        goto error;
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    if (dimen[0].flag) {
        IF_NOT(item = item_FromItem(this->item, this->endn))
            goto error;
        obj = new_record(dimen, item, this->endn, this->pntr, this->data);
    }
    else { /* return a scalar object */
        obj = get_record(dimen[0].leng, dimen, this->item, this->pntr);
        PyMem_Free(dimen);
    }
    return obj;
 error:
    if (dimen) PyMem_Free(dimen);
    return 0;
}

static int
record_setmapitem(RecordObject *this, PyObject *key, PyObject *obj)
{
    /*
     *  Assign items to an array of records
     */
    RecordObject *robj=0; Dimen *dimen=0;
#ifdef DEBUG
    printf("record_setmapitem: this=%p\n", this);
#endif
    if (obj == 0) {
        PyErr_SetString(PyExc_ValueError, "cannot delete record items");
        goto error;
    }
    IF_NOT(dimen = dimen_FromClone(this->dimn))
        goto error;
    if (set_indices(dimen, key))
        goto error;
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    if (Record_Check(obj)) {
        robj = (RecordObject *)obj;
        IF_NOT(compare_record(dimen, this->item, robj->dimn, robj->item))
            goto error;
        if (cast_record(dimen[0].leng, dimen, this->item, this->pntr,
                        robj->dimn[0].leng, robj->dimn, robj->item,
                        robj->pntr))
            goto error;
    }
    else {
        if (set_record(dimen[0].leng, dimen, this->item, this->pntr, obj))
            goto error;
    }
    PyMem_Free(dimen);
    return 0;
 error:
    if (dimen) PyMem_Free(dimen);
    return -1;
}

/*
 *  Function table for Python mapping behavior.
 */

static PyMappingMethods record_as_mapping = {
    (inquiry)record_length,            /* mp_length    "len(x)"   */
    (binaryfunc)record_getmapitem,     /* mp_get_item  "x[k]"     */
    (objobjargproc)record_setmapitem,  /* mp_set_item  "x[k] = y  */
};

/* Record Array Type Attributes */

PyTypeObject Record_Type = {
    /* definition */
    PyObject_HEAD_INIT(0)
    0,                                 /* ob_size */
    "record",                          /* tp_name */
    sizeof(RecordObject),              /* tp_size */
    0,                                 /* tp_itemsize */
    /* methods */
    (destructor)record_dealloc,        /* tp_dealloc */
    (printfunc)record_print,           /* tp_print */
    (getattrfunc)record_getattr,       /* tp_getattr */
    (setattrfunc)record_setattr,       /* tp_setattr */
    0,                                 /* tp_compare */
    (reprfunc)record_repr,             /* tp_repr */
    0,                                 /* tp_as_number */
    &record_as_sequence,               /* tp_as_sequence */
    &record_as_mapping,                /* tp_as_mapping */
    0,                                 /* tp_hash */
    0,                                 /* tp_call */
    0,                                 /* tp_str */
    0,                                 /* tp_getattro */
    0,                                 /* tp_setattro */
    0,                                 /* tp_as_buffer */
    0,                                 /* tp_xxx4 */
    0,                                 /* tp_doc */
};

static PyObject *
record_fromstring(PyObject *this, PyObject *args, PyObject *opts)
{
    /*
     *  Create a record object from a string object and optional
     *  item count and format.  This implies that the length of
     *  the string can be greater than the record data buffer.
     */
    char *keys[]={"data", "count", "format", 0};
    PyObject *data=0; int count=-1; char *format=0;
    Dimen *dimen=0; Item *item=0;
    char endian, *fmt, *pntr; int shape[3];

#ifdef DEBUG
    printf("record_fromstring: this=%p\n", this);
#endif
    IF_NOT(PyArg_ParseTupleAndKeywords(args, opts, "S|is", keys,
                                       &data, &count, &format))
        goto error;
    if ((unsigned)PyString_Size(data) > INT_MAX) {
        PyErr_SetString(PyExc_ValueError, "string size >2GB");
        goto error;
    }
    /*  create record list  */
    if (format) {
        fmt = skip_space(format);
        fmt = format_endian(fmt, &endian);
        IF_NOT(item = item_FromFormat(endian, fmt))
            goto error; /* memory error or format error */
    }
    else {
        endian = NAT;
        IF_NOT(item = item_FromFormat(endian, "c"))
            goto error;
    }
    /*  calculate record count and check string size  */
    if (count < 0) {
        if (PyString_Size(data)%item[0].size) {
            PyErr_SetString(PyExc_ValueError,
                            "string size not multiple of record size");
            goto error;
        }
        count = PyString_Size(data)/item[0].size;
    }
    else {
        if (PyString_Size(data) < count*item[0].size) {
            PyErr_SetString(RecordError,
                            "string size is less than requested size");
            goto error;
        }
    }
    /*  create dimension list  */
    shape[0] = 2; shape[1] = item[0].leng, shape[2] = count;
    IF_NOT(dimen = dimen_fromshape(shape, item[0].size))
        goto error;
#ifdef DEBUG
    print_dimensions(dimen);
#endif
    pntr = PyString_AsString(data);
    return (PyObject *)new_record(dimen, item, endian, pntr, data);
 error:
    if (dimen) PyMem_Free(dimen);
    if (item) PyMem_Free(item);
    return 0;
}

/*
 *  Record methods
 */

static PyMethodDef record_init_methods[] =
{
    {"record",     (PyCFunction)record_new,        METH_VARARGS|METH_KEYWORDS,
     "record(data, [format-string])"
    },
    {"fromstring", (PyCFunction)record_fromstring, METH_VARARGS|METH_KEYWORDS,
     "fromstring(data, [format-string])"
    },
    {0,            0}                             /* sentinel */
};

void initrecord(void) {
    /*
     *  Initialize the record module and define its methods and 
     *  attributes.
     */
    PyObject *m, *d;

    Record_Type.ob_type = &PyType_Type;
    m = Py_InitModule("record", record_init_methods);
    d = PyModule_GetDict(m);

    IF_NOT(RecordError = PyErr_NewException("record.error", 0, 0))
        return;
    PyDict_SetItemString(d, "error", RecordError);
    PyDict_SetItemString(d, "__version__", PyString_FromString(VERSION));
}
