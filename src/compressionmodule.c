/* $Id$ 
*/

/* "compression module */

/*****************************************************************************/
/*                                                                           */
/* The compression software is a python module implemented in C that, when    */
/* accessed through the pyfits module, supports the storage of compressed    */
/* images in FITS binary tables.  An n-dimensional image is divided into a   */
/* rectabgular grid of subimages or 'tiles'.  Each tile is then compressed   */
/* as a continuous block of data, and the resulting compressed byte stream   */
/* is stored in a row of a variable length column in a FITS binary table.    */
/* The default tiling pattern treates each row of a 2-dimensional image      */
/* (or higher dimensional cube) as a tile, such that each tile contains      */
/* NAXIS1 pixels.                                                            */
/*                                                                           */
/* This module contains two functions that are callable from python.  The    */
/* first is compressData.  This function takes a numpy.ndarray object        */
/* containing the uncompressed image data and returns a list of byte streams */
/* in which each element of the list holds the compressed data for a single  */
/* tile of the image.  The second function is decompressData.  It takes a    */
/* list of byte streams that hold the compressed data for each tile in the   */
/* image.  It returns a list containing the decompressed data for each tile  */
/* in the image.                                                             */
/*                                                                           */
/* Copyright (C) 2004 Association of Universities for Research in Astronomy  */
/* (AURA)                                                                    */
/*                                                                           */
/* Redistribution and use in source and binary forms, with or without        */
/* modification, are permitted provided that the following conditions are    */
/* met:                                                                      */
/*                                                                           */
/*    1. Redistributions of source code must retain the above copyright      */
/*      notice, this list of conditions and the following disclaimer.        */
/*                                                                           */
/*    2. Redistributions in binary form must reproduce the above             */
/*      copyright notice, this list of conditions and the following          */
/*      disclaimer in the documentation and/or other materials provided      */
/*      with the distribution.                                               */
/*                                                                           */
/*    3. The name of AURA and its representatives may not be used to         */
/*      endorse or promote products derived from this software without       */
/*      specific prior written permission.                                   */
/*                                                                           */
/* THIS SOFTWARE IS PROVIDED BY AURA ``AS IS'' AND ANY EXPRESS OR IMPLIED    */
/* WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF      */
/* MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE                  */
/* DISCLAIMED. IN NO EVENT SHALL AURA BE LIABLE FOR ANY DIRECT, INDIRECT,    */
/* INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,      */
/* BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS     */
/* OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND    */
/* ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR     */
/* TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE    */
/* USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH          */
/* DAMAGE.                                                                   */
/*                                                                           */
/* Some of the source code used by this module was copied and modified from  */
/* the FITSIO software that was written by William Pence at the High Energy  */
/* Astrophysic Science Archive Research Center (HEASARC) at the NASA Goddard */
/* Space Flight Center.  That software contained the following copyright and */
/* warranty notices:                                                         */
/*                                                                           */
/* Copyright (Unpublished--all rights reserved under the copyright laws of   */
/* the United States), U.S. Government as represented by the Administrator   */
/* of the National Aeronautics and Space Administration.  No copyright is    */
/* claimed in the United States under Title 17, U.S. Code.                   */
/*                                                                           */
/* Permission to freely use, copy, modify, and distribute this software      */
/* and its documentation without fee is hereby granted, provided that this   */
/* copyright notice and disclaimer of warranty appears in all copies.        */
/*                                                                           */
/* DISCLAIMER:                                                               */
/*                                                                           */
/* THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND,        */
/* EITHER EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO,   */
/* ANY WARRANTY THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY        */
/* IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR           */
/* PURPOSE, AND FREEDOM FROM INFRINGEMENT, AND ANY WARRANTY THAT THE         */
/* DOCUMENTATION WILL CONFORM TO THE SOFTWARE, OR ANY WARRANTY THAT THE      */
/* SOFTWARE WILL BE ERROR FREE.  IN NO EVENT SHALL NASA BE LIABLE FOR ANY    */
/* DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT, INDIRECT, SPECIAL OR      */
/* CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM, OR IN ANY WAY      */
/* CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON WARRANTY,         */
/* CONTRACT, TORT , OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED BY     */
/* PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED   */
/* FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR          */
/* SERVICES PROVIDED HEREUNDER."                                             */
/*                                                                           */
/*****************************************************************************/

/* Include the Python C API */

#include "Python.h"
#include <numpy/arrayobject.h>
#include "fitsio2.h"
#include "string.h"

/* Some defines for Python3 support--bytes objects should be used where */
/* strings were previously used                                         */
#if PY_MAJOR_VERSION >= 3
#define PyString_AsString PyBytes_AsString
#define PyString_FromStringAndSize PyBytes_FromStringAndSize
#define PyString_Size PyBytes_Size
#endif


/* These defaults mirror the defaults in pyfits.hdu.compressed */
#define DEFAULT_COMPRESSION_TYPE "RICE_1"
#define DEFAULT_QUANTIZE_LEVEL 16.0
#define DEFAULT_HCOMP_SCALE 0
#define DEFAULT_HCOMP_SMOOTH 0
#define DEFAULT_BLOCK_SIZE 32
#define DEFAULT_BYTE_PIX 4


/* Function to get the input long values from the input list */

static long* get_long_array(PyObject* data, const char* description,
                            int* data_size)
{
   int    i;
   int    size;
   long*  out;
   int    seq;
   char   err_msg[80];

   seq = PyList_Check(data);

   if (!seq)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " argument must be a list.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_TypeError, err_msg);
      return NULL;
   }

   size = PyList_Size(data);

   if (size < 0)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " list has invalid size.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_ValueError, err_msg);
      return NULL;
   }

   if (data_size)
   {
      *data_size = size;
   }

   out = (long*) PyMem_Malloc(size * sizeof(long));

   if(!out)
   {
      PyErr_NoMemory();
      return NULL;
   }

   for (i = 0; i < size; i++)
   {
      out[i] = PyLong_AsLong(PyList_GetItem(data, i));
   }

   if ( PyErr_Occurred())
   {
      PyMem_Free(out);
      out = NULL;
   }

   return out;
}


/* Function to get the input character arrays from the input list */

static unsigned char** get_char_array(PyObject* data, const char* description,
                                      int* data_size, int** dataLen)
{
   int             i;
   int             size;
   unsigned char** out;
   int             seq;
   char            err_msg[80];

   seq = PyList_Check(data);

   if (!seq)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " argument must be a list.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_TypeError, err_msg);
      return NULL;
   }

   size = PyList_Size(data);

   if ( size < 0)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " list has invalid size.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_ValueError, err_msg);
      return NULL;
   }

   if (data_size)
   {
      *data_size = size;
   }

   out = (unsigned char**) PyMem_Malloc(size * sizeof(char*));

   if(!out)
   {
      PyErr_NoMemory();
      return NULL;
   }

   *dataLen = (int*) PyMem_Malloc(size * sizeof(int));

   if(!(*dataLen))
   {
      PyMem_Free(out);
      PyErr_NoMemory();
      return NULL;
   }

   for (i = 0; i < size; i++)
   {
      out[i] = (unsigned char*)PyString_AsString(PyList_GetItem(data, i));
      (*dataLen)[i] = PyString_Size(PyList_GetItem(data, i));
   }

   if (PyErr_Occurred())
   {
      PyMem_Free(out);
      PyMem_Free(*dataLen);
      out = NULL;
   }

   return out;
}

/* Function to get the input float values from the input list */

static float* get_float_array(PyObject* data, const char* description,
                              int* data_size)
{
   int    i;
   int    size;
   float* out;
   int    seq;
   char   err_msg[80];

   seq = PyList_Check(data);

   if (!seq)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " argument must be a list.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_TypeError, err_msg);
      return NULL;
   }

   size = PyList_Size(data);

   if (size < 0)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " list has invalid size.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_ValueError, err_msg);
      return NULL;
   }

   if (data_size)
   {
      *data_size = size;
   }

   out = (float*) PyMem_Malloc(size * sizeof(float));

   if(!out)
   {
      PyErr_NoMemory();
      return NULL;
   }

   for (i = 0; i < size; i++)
   {
      out[i] = PyFloat_AsDouble(PyList_GetItem(data, i));
   }

   if ( PyErr_Occurred())
   {
      PyMem_Free(out);
      out = NULL;
   }

   return out;
}

/* Function to get the input double values from the input list */

static double* get_double_array(PyObject* data, const char* description,
                                int* data_size)
{
   int     i;
   int     size;
   double* out;
   int     seq;
   char    err_msg[80];

   seq = PyList_Check(data);

   if (!seq)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " argument must be a list.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_TypeError, err_msg);
      return NULL;
   }

   size = PyList_Size(data);

   if (size < 0)
   {
      strncpy(err_msg, description, 79);
      strncat(err_msg, " list has invalid size.", 79-strlen(err_msg));
      PyErr_SetString(PyExc_ValueError, err_msg);
      return NULL;
   }

   if (data_size)
   {
      *data_size = size;
   }

   out = (double*) PyMem_Malloc(size * sizeof(double));

   if(!out)
   {
      PyErr_NoMemory();
      return NULL;
   }

   for (i = 0; i < size; i++)
   {
      out[i] = PyFloat_AsDouble(PyList_GetItem(data, i));
   }

   if (PyErr_Occurred())
   {
      PyMem_Free(out);
      out = NULL;
   }

   return out;
}

/* Report any error based on the status returned from cfitsio. */

void process_status_err(int status)
{
   PyObject* except_type;
   char      err_msg[81];
   char      def_err_msg[81];

   err_msg[0] = '\0';
   def_err_msg[0] = '\0';

   switch (status)
   {
      case MEMORY_ALLOCATION:
         except_type = PyExc_MemoryError;
         break;
      case OVERFLOW_ERR:
         except_type = PyExc_OverflowError;
         break;
      case BAD_COL_NUM:
         strcpy(def_err_msg, "bad column number");
         except_type = PyExc_ValueError;
         break;
      case BAD_PIX_NUM:
         strcpy(def_err_msg, "bad pixel number");
         except_type = PyExc_ValueError;
         break;
      case NEG_AXIS:
         strcpy(def_err_msg, "negative axis number");
         except_type = PyExc_ValueError;
         break;
      case BAD_DATATYPE:
         strcpy(def_err_msg, "bad data type");
         except_type = PyExc_TypeError;
         break;
      case NO_COMPRESSED_TILE:
         strcpy(def_err_msg, "no compressed or uncompressed data for tile.");
         except_type = PyExc_ValueError;
         break;
      default:
         except_type = PyExc_RuntimeError;
   }

   if (fits_read_errmsg(err_msg))
   {
      PyErr_SetString(except_type, err_msg);
   }
   else if (*def_err_msg)
   {
      PyErr_SetString(except_type, def_err_msg);
   }
   else
   {
      PyErr_SetString(except_type, "unknown error.");
   }
}

/* Wrapper for the fits_write_img() function */

//PyObject* compression_compressData(PyObject* self, PyObject* args)
//{
//   int             status;
//   PyObject*       naxesObj;
//   PyObject*       tileSizeObj;
//   PyObject*       zvalObj;
//   PyObject*       outList;
//   PyObject*       outStr;
//   PyObject*       outScale;
//   PyObject*       outZero;
//   PyObject*       outUncompressed;
//   PyObject*       uncompressedTileDataList;
//   PyObject*       returnTuple = NULL;
//   long*           tileSize = 0;
//   long*           zval = 0;
//   int             i;
//   int             loop;
//   int             numzVals;
//   char*           compressTypeStr = "";
//   int             datatype;
//   int             bitpix;
//   int             firstelem;
//   int             naxis;
//   int             ntiles;
//   int             ii;
//   int             zblank;
//   int             cn_zblank;
//   int             cn_zscale;
//   int             cn_zzero;
//   int             cn_uncompressed;
//   double          cn_bscale;
//   double          cn_bzero;
//   double          quantize_level;
//   double          hcomp_scale;
//   long*           naxes = 0;
//   long            nelem;
//
//   FITSfile        fileParms;
//   fitsfile        theFile;
//
//   PyArrayObject*  array;
//
//   status = 0;
//
//   /* Get Python arguments */
//
//   if (!PyArg_ParseTuple(args, "O!iOOiiddiiiddOsiil:compression.compressData",
//                         &PyArray_Type, &array, &naxis, &naxesObj,
//                         &tileSizeObj, &cn_zblank, &zblank, &cn_bscale, 
//                         &cn_bzero, &cn_zscale, &cn_zzero, &cn_uncompressed,
//                         &quantize_level, &hcomp_scale, &zvalObj,
//                         &compressTypeStr, &bitpix, &firstelem, &nelem))
//   {
//      PyErr_SetString(PyExc_TypeError, "Couldn't parse agruments");
//      return NULL;
//   }
//
//   /* Determine the data type based on the bitpix value from the header */
//
//   switch (bitpix)
//   {
//      case BYTE_IMG:
//         datatype = TBYTE;
//         break;
//      case SHORT_IMG:
//         datatype = TSHORT;
//         break;
//      case LONG_IMG:
//         datatype = TINT;
//         break;
//      case LONGLONG_IMG:
//         datatype = TLONGLONG;
//         break;
//      case FLOAT_IMG:
//         datatype = TFLOAT;
//         break;
//      case DOUBLE_IMG:
//         datatype = TDOUBLE;
//         break;
//      default:
//         PyErr_SetString(PyExc_ValueError, "Invalid value for BITPIX");
//         return NULL;
//   }
//
//   /* Initialize allocated array pointers to zero so we can free them */
//   /* without allocating memory for them.                             */
//
//   theFile.Fptr = &fileParms;
//   (theFile.Fptr)->cn_zscale = 0;
//   (theFile.Fptr)->cn_zzero = 0;
//   (theFile.Fptr)->ucDataLen = 0;
//   (theFile.Fptr)->ucData = 0;
//   (theFile.Fptr)->dataLen = 0;
//   (theFile.Fptr)->data = 0;
//
//   /* The loop allows you to break out if there is an error */
//
//   for (loop = 0; loop == 0; loop++)
//   {
//      /* Convert the NAXISn, ZTILEn, and ZVALn lists into a C type arrays */
//
//      naxes = get_long_array(naxesObj, "ZNAXISn", NULL);
//
//      if (!naxes)
//      {
//         break;
//      }
//
//      tileSize = get_long_array(tileSizeObj, "ZTILEn", NULL);
//
//      if (!tileSize)
//      {
//         break;
//      }
//
//      zval = get_long_array(zvalObj, "ZVALn", &numzVals);
//
//      if (!zval)
//      {
//         break;
//      }
//
//      /* Set up the fitsfile object */
//      /* Store the compression type and compression parameters */
//
//      (theFile.Fptr)->hcomp_smooth = 0;
//      (theFile.Fptr)->rice_blocksize = 32;
//      (theFile.Fptr)->rice_bytepix = 4;
//
//      if (strcmp(compressTypeStr, "RICE_1") == 0)
//      {
//         (theFile.Fptr)->compress_type = RICE_1;
//
//         if (numzVals > 0)
//         {
//            (theFile.Fptr)->rice_blocksize = zval[0];
//
//            if (numzVals > 1)
//            {
//               (theFile.Fptr)->rice_bytepix = zval[1];
// 
//            }
//         }
//      }
//      else if (strcmp(compressTypeStr, "GZIP_1") == 0)
//      {
//         (theFile.Fptr)->compress_type = GZIP_1;
//
//      }
//      else if (strcmp(compressTypeStr, "HCOMPRESS_1") == 0)
//      {
//         (theFile.Fptr)->compress_type = HCOMPRESS_1;
//
//         if (numzVals > 0)
//         {
//           (theFile.Fptr)->hcomp_smooth = zval[1];
//         }
//      }
//      else if (strcmp(compressTypeStr, "PLIO_1") == 0)
//      {
//         (theFile.Fptr)->compress_type = PLIO_1;
//
//      }
//      else
//      {
//         (theFile.Fptr)->compress_type = 0;
//      }
//
//      (theFile.Fptr)->zndim = naxis;
//      (theFile.Fptr)->maxtilelen = 1;
//      (theFile.Fptr)->zbitpix = bitpix;
//      (theFile.Fptr)->cn_zblank = cn_zblank;
//      (theFile.Fptr)->zblank = zblank;
//      (theFile.Fptr)->cn_bscale = cn_bscale;
//      (theFile.Fptr)->cn_bzero = cn_bzero;
//      (theFile.Fptr)->cn_zscale = cn_zscale;
//      (theFile.Fptr)->cn_zzero = cn_zzero;
//      (theFile.Fptr)->quantize_level = quantize_level;
//      (theFile.Fptr)->hcomp_scale = hcomp_scale;
//
//      /* Initialize arrays */
//
//      for (ii = 0; ii < MAX_COMPRESS_DIM; ii++)
//      {
//         ((theFile.Fptr)->tilesize)[ii] = 1;
//         ((theFile.Fptr)->znaxis)[ii] = 1;
//      }
//
//      ntiles = 1;
//
//      for (ii = 0; ii < naxis; ii++)
//      {
//         ((theFile.Fptr)->znaxis)[ii] = naxes[ii];
//         ((theFile.Fptr)->tilesize)[ii] = tileSize[ii];
//         (theFile.Fptr)->maxtilelen *= tileSize[ii];
//         ntiles *= (naxes[ii] - 1) / tileSize[ii] + 1;
//      }
//
//      (theFile.Fptr)->maxelem = imcomp_calc_max_elem(
//                                 (theFile.Fptr)->compress_type,
//                                 (theFile.Fptr)->maxtilelen,
//                                 (theFile.Fptr)->zbitpix,
//                                 (theFile.Fptr)->rice_blocksize);
//
//      if (cn_zscale > 0)
//      {
//         (theFile.Fptr)->cn_zscale =
//                         (double*)PyMem_Malloc(ntiles * sizeof(double));
//         (theFile.Fptr)->cn_zzero =
//                         (double*)PyMem_Malloc(ntiles * sizeof(double));
//
//         if(!(theFile.Fptr)->cn_zzero)
//         {
//            PyErr_NoMemory();
//            break;
//         }
//      }
//
//      (theFile.Fptr)->cn_uncompressed = cn_uncompressed;
//
//      if (cn_uncompressed > 0)
//      {
//         (theFile.Fptr)->ucDataLen = 
//                          (int*)PyMem_Malloc(ntiles * sizeof(int));
//         (theFile.Fptr)->ucData =
//                          (void**)PyMem_Malloc(ntiles * sizeof(double*));
//
//         if(!(theFile.Fptr)->ucData)
//         {
//            PyErr_NoMemory();
//            break;
//         }
//
//         for (i = 0; i < ntiles; i++)
//         {
//            (theFile.Fptr)->ucDataLen[i] = 0;
//            (theFile.Fptr)->ucData[i] = 0;
//         }
//      }
//
//      (theFile.Fptr)->dataLen = 
//                         (int*) PyMem_Malloc(ntiles * sizeof(int));
//      (theFile.Fptr)->data =
//                         (unsigned char**) PyMem_Malloc(ntiles*sizeof(char*));
//
//      if(!(theFile.Fptr)->data)
//      {
//         PyErr_NoMemory();
//         break;
//      }
//
//      for (i = 0; i < ntiles; i++)
//      {
//         (theFile.Fptr)->dataLen[i] = 0;
//         (theFile.Fptr)->data[i] = 0;
//      }
//
//      status = fits_write_img(&theFile, datatype, firstelem, nelem,
//                              (void*)array->data, &status);
//
//      if (status == 0)
//      {
//         outList = PyList_New(0);
//         outScale = PyList_New(0);
//         outZero = PyList_New(0);
//         outUncompressed = PyList_New(0);
//
//         for ( i = 0; i < ntiles; i++)
//         {
//            outStr = PyString_FromStringAndSize(
//                (const char*)((theFile.Fptr)->data[i]),
//                (theFile.Fptr)->dataLen[i]);
//
//            PyList_Append(outList, outStr);
//
//            Py_DECREF(outStr);
//
//            free((theFile.Fptr)->data[i]);
//
//            if (cn_zscale > 0)
//            {
//               PyList_Append(outScale,
//                             PyFloat_FromDouble((theFile.Fptr)->cn_zscale[i]));
//               PyList_Append(outZero,
//                             PyFloat_FromDouble((theFile.Fptr)->cn_zzero[i]));
//            }
//
//            if (cn_uncompressed > 0)
//            {
//               uncompressedTileDataList = PyList_New(0);
//
//               for (ii = 0; ii < (theFile.Fptr)->ucDataLen[i]; ii++)
//               {
//                   PyList_Append(uncompressedTileDataList,
//                   PyFloat_FromDouble(
//                               ((double**)((theFile.Fptr)->ucData))[i][ii]));
//               }
//
//               free((theFile.Fptr)->ucData[i]);
//               PyList_Append(outUncompressed, uncompressedTileDataList);
//            }
//         }
//      }
//      else
//      {
//         process_status_err(status);
//         break;
//      }
//
//      returnTuple = PyTuple_New(5);
//      PyTuple_SetItem(returnTuple, 0, Py_BuildValue("i", status));
//      PyTuple_SetItem(returnTuple, 1, outList);
//      PyTuple_SetItem(returnTuple, 2, outScale);
//      PyTuple_SetItem(returnTuple, 3, outZero);
//      PyTuple_SetItem(returnTuple, 4, outUncompressed);
//   }
//
//   /* Free any allocated memory */
//
//   PyMem_Free((theFile.Fptr)->dataLen);
//   PyMem_Free((theFile.Fptr)->data);
//   PyMem_Free((theFile.Fptr)->cn_zscale);
//   PyMem_Free((theFile.Fptr)->cn_zzero);
//   PyMem_Free((theFile.Fptr)->ucData);
//   PyMem_Free((theFile.Fptr)->ucDataLen);
//   PyMem_Free(naxes);
//   PyMem_Free(tileSize);
//   PyMem_Free(zval);
//
//   if (loop == 0)
//   {
//      /* Error has occurred */
//
//      return NULL;
//   }
//   else
//   {
//      return returnTuple;
//   }
//}
//
///* Wrapper for the fits_read_img() function */
//
//PyObject* compression_decompressData(PyObject* self, PyObject* args)
//{
//   int             status;
//   int             nUcTiles = 0;
//   int             naxis;
//   int             numzVals;
//   int*            numUncompressedVals = 0;
//   int             cn_zblank;
//   int             cn_zscale;
//   int             cn_zzero;
//   int             cn_uncompressed;
//   int             bitpix;
//   int             datatype;
//   int             firstelem;
//   int             anynul;
//   long            nelem;
//   long*           naxes = 0;
//   long*           tileSize = 0;
//   long*           zval = 0;
//   double          nulval;
//   double          zscale;
//   double          zzero;
//   int             zblank;
//   double          quantize_level;
//   double          hcomp_scale;
//   void**          uncompressedData = 0;
//   int             i;
//   int             ii;
//   char*           compressTypeStr = "";
//
//   PyObject*       naxesObj;
//   PyObject*       tileSizeObj;
//   PyObject*       uncompressedDataObj;
//   PyObject*       zvalObj;
//
//   FITSfile        fileParms;
//   fitsfile        theFile;
//
//   PyArrayObject*  decompDataArray;
//
//   /* Get Python arguments */
//
//   if (!PyArg_ParseTuple(args, 
//                         "iOOididiiOiddOsiildO!:compression.decompressData",
//                         &naxis, &naxesObj, &tileSizeObj, &cn_zscale, &zscale,
//                         &cn_zzero, &zzero, &cn_zblank, &zblank, &uncompressedDataObj,
//                         &cn_uncompressed, &quantize_level, &hcomp_scale,
//                         &zvalObj, &compressTypeStr, &bitpix, &firstelem,
//                         &nelem, &nulval, &PyArray_Type, &decompDataArray))
//   {
//      PyErr_SetString(PyExc_TypeError, "Couldn't parse arguments");
//      return NULL;
//   }
//
//   naxes = get_long_array(naxesObj, "ZNAXISn", NULL);
//
//   if (!naxes)
//   {
//      goto error;
//   }
//
//   tileSize = get_long_array(tileSizeObj, "ZTILEn", NULL);
//
//   if (!tileSize)
//   {
//      goto error;
//   }
//
//   zval = get_long_array(zvalObj, "ZVALn", &numzVals);
//
//   if (!zval)
//   {
//      goto error;
//   }
//
//   switch (bitpix)
//   {
//      case BYTE_IMG:
//         datatype = TBYTE;
//         break;
//      case SHORT_IMG:
//         datatype = TSHORT;
//         break;
//      case LONG_IMG:
//         datatype = TINT;
//         break;
//      case LONGLONG_IMG:
//         datatype = TLONGLONG;
//         break;
//      case FLOAT_IMG:
//         datatype = TFLOAT;
//
//         if (cn_uncompressed == 1)
//         {
//            nUcTiles = PyList_Size(uncompressedDataObj);
//            uncompressedData = (void**) PyMem_Malloc(nUcTiles*sizeof(float*));
//
//            if (!uncompressedData)
//            {
//               goto error;
//            }
//
//            numUncompressedVals = PyMem_Malloc(nUcTiles*sizeof(int));
//
//            if (!numUncompressedVals)
//            {
//               goto error;
//            }
//
//            for (i = 0; i < nUcTiles; i++)
//            {
//                uncompressedData[i] = 
//                       get_float_array(PyList_GetItem(uncompressedDataObj, i),
//                                       "Uncompressed Data",
//                                       &numUncompressedVals[i]);
//
//                if (!uncompressedData[i])
//                {
//                   goto error;
//                }
//            }
//         }
//         break;
//      case DOUBLE_IMG:
//         datatype = TDOUBLE;
//
//         if (cn_uncompressed == 1)
//         {
//            nUcTiles = PyList_Size(uncompressedDataObj);
//            uncompressedData = (void**) PyMem_Malloc(nUcTiles*sizeof(double*));
//
//            if (!uncompressedData)
//            {
//               goto error;
//            }
//
//            numUncompressedVals = PyMem_Malloc(nUcTiles*sizeof(int));
//
//            if (!numUncompressedVals)
//            {
//               goto error;
//            }
//
//            for (i = 0; i < nUcTiles; i++)
//            {
//                uncompressedData[i] = 
//                       get_double_array(PyList_GetItem(uncompressedDataObj, i),
//                                        "Uncompressed Data",
//                                        &numUncompressedVals[i]);
//
//                if (!uncompressedData[i])
//                {
//                   goto error;
//                }
//            }
//         }
//         break;
//      default:
//         PyErr_SetString(PyExc_ValueError, "Invalid value for BITPIX");
//         return NULL;
//   }
//
//   /* Set up the fitsfile object */
//
//   theFile.Fptr = &fileParms;
//
//   (theFile.Fptr)->rice_blocksize = 32;
//   (theFile.Fptr)->hcomp_smooth = 0;
//   (theFile.Fptr)->rice_bytepix = 4;
//
//   if (strcmp(compressTypeStr, "RICE_1") == 0)
//   {
//      (theFile.Fptr)->compress_type = RICE_1;
//
//      if (numzVals > 0)
//      {
//         (theFile.Fptr)->rice_blocksize = zval[0];
//
//         if (numzVals > 1)
//         {
//            (theFile.Fptr)->rice_bytepix = zval[1];
//         }
//      }
//   }
//   else if (strcmp(compressTypeStr, "GZIP_1") == 0)
//   {
//      (theFile.Fptr)->compress_type = GZIP_1;
//   }
//   else if (strcmp(compressTypeStr, "HCOMPRESS_1") == 0)
//   {
//      (theFile.Fptr)->compress_type = HCOMPRESS_1;
//
//      if (numzVals > 0)
//      {
//        (theFile.Fptr)->hcomp_smooth = zval[1];
//      }
//   }
//   else if (strcmp(compressTypeStr, "PLIO_1") == 0)
//   {
//      (theFile.Fptr)->compress_type = PLIO_1;
//   }
//   else
//   {
//      (theFile.Fptr)->compress_type = 0;
//   }
//
//   (theFile.Fptr)->zndim = naxis;
//   (theFile.Fptr)->maxtilelen = 1;
//   (theFile.Fptr)->zbitpix = bitpix;
//
//   (theFile.Fptr)->cn_zscale = cn_zscale;
//   (theFile.Fptr)->quantize_level = quantize_level;
//   (theFile.Fptr)->hcomp_scale = hcomp_scale;
//
//   if (cn_zscale == -1)
//   {
//      (theFile.Fptr)->zscale = zscale;
//      (theFile.Fptr)->cn_bscale = zscale;
//   }
//   else
//   {
//      (theFile.Fptr)->zscale = 1.0;
//      (theFile.Fptr)->cn_bscale = 1.0;
//   }
//
//   (theFile.Fptr)->cn_zzero = cn_zzero;
//
//   if (cn_zzero == -1)
//   {
//      (theFile.Fptr)->zzero = zzero;
//      (theFile.Fptr)->cn_bzero = zzero;
//   }
//   else
//   {
//      (theFile.Fptr)->zzero = 0.0;
//      (theFile.Fptr)->cn_bzero = 0.0;
//   }
//
//   (theFile.Fptr)->zblank = zblank;
//   (theFile.Fptr)->cn_zblank = cn_zblank;
//
//   if (cn_zblank == -1)
//   {
//      (theFile.Fptr)->zblank = zblank;
//   }
//   else
//   {
//      (theFile.Fptr)->zblank = 0;
//   }
//
//   /* Initialize arrays */
//
//   for (ii = 0; ii < MAX_COMPRESS_DIM; ii++)
//   {
//      ((theFile.Fptr)->tilesize)[ii] = 1;
//      ((theFile.Fptr)->znaxis)[ii] = 1;
//   }
//
//   for (ii = 0; ii < naxis; ii++)
//   {
//      ((theFile.Fptr)->znaxis)[ii] = naxes[ii];
//      ((theFile.Fptr)->tilesize)[ii] = tileSize[ii];
//      (theFile.Fptr)->maxtilelen *= tileSize[ii];
//   }
//
//   (theFile.Fptr)->cn_uncompressed = cn_uncompressed;
//
//   if (cn_uncompressed == 1)
//   {
//       (theFile.Fptr)->ucData = uncompressedData;
//       (theFile.Fptr)->ucDataLen = numUncompressedVals;
//   }
//
//   /* Call the C function */
//
//   status = 0;
//   status = fits_read_img(&theFile, datatype, firstelem, nelem, &nulval,
//                          decompDataArray->data, &anynul, &status);
//
//   if (status != 0)
//   {
//      process_status_err(status);
//   }
//
//   error:
//      PyMem_Free(naxes);
//      PyMem_Free(tileSize);
//      PyMem_Free(zval);
//
//      if (cn_uncompressed == 1)
//      {
//         for (i = 0; i < nUcTiles; i++)
//         {
//             PyMem_Free(uncompressedData[i]);
//         }
//
//         PyMem_Free(uncompressedData);
//         PyMem_Free(numUncompressedVals);
//      }
//
//      if (status != 0)
//      {
//         return NULL;
//      }
//      else
//      {
//         return Py_BuildValue("i", status);
//      }
//}


void bitpix_to_datatypes(int bitpix, int* datatype, int* npdatatype) {
    /* Given a FITS BITPIX value, returns the appropriate CFITSIO type code and
       Numpy type code for that BITPIX into datatype and npdatatype
       respectively.
     */
    switch (bitpix) {
        case BYTE_IMG:
            *datatype = TBYTE;
            *npdatatype = NPY_INT8;
            break;
        case SHORT_IMG:
            *datatype = TSHORT;
            *npdatatype = NPY_INT16;
            break;
        case LONG_IMG:
            *datatype = TINT;
            *npdatatype = NPY_LONG;
            break;
        case LONGLONG_IMG:
            *datatype = TLONGLONG;
            *npdatatype = NPY_LONGLONG;
            break;
        case FLOAT_IMG:
            *datatype = TFLOAT;
            *npdatatype = NPY_FLOAT;
            break;
        case DOUBLE_IMG:
            *datatype = TDOUBLE;
            *npdatatype = NPY_DOUBLE;
            break;
        default:
            PyErr_SetString(PyExc_ValueError, "Invalid value for BITPIX");
   }

   return;
}

// TODO: It might be possible to simplify these further by making the
// conversion function (eg. PyString_AsString) an argument to a macro or
// something, but I'm not sure yet how easy it is to generalize the error
// handling
int get_header_string(PyObject* header, char* keyword, char** val, char* def) {
    PyObject* keystr;
    PyObject* keyval;
    int retval;

    keystr = PyString_FromString(keyword);
    keyval = PyObject_GetItem(header, keystr);

    if (keyval != NULL) {
        *val = PyString_AsString(keyval);
        retval = 0;
    }
    else {
        PyErr_Clear();
        *val = def;
        retval = 1;
    }

    Py_DECREF(keystr);
    Py_XDECREF(keyval);
    return retval;
}


int get_header_int(PyObject* header, char* keyword, int* val, int def) {
    PyObject* keystr;
    PyObject* keyval;
    int retval;

    keystr = PyString_FromString(keyword);
    keyval = PyObject_GetItem(header, keystr);

    if (keyval != NULL) {
        *val = (int) PyInt_AsLong(keyval);
        retval = 0;
    }
    else {
        PyErr_Clear();
        *val = def;
        retval = 1;
    }

    Py_DECREF(keystr);
    Py_XDECREF(keyval);
    return retval;
}


int get_header_long(PyObject* header, char* keyword, long* val, long def) {
    PyObject* keystr;
    PyObject* keyval;
    int retval;

    keystr = PyString_FromString(keyword);
    keyval = PyObject_GetItem(header, keystr);

    if (keyval != NULL) {
        *val = PyLong_AsLong(keyval);
        retval = 0;
    }
    else {
        PyErr_Clear();
        *val = def;
        retval = 1;
    }

    Py_DECREF(keystr);
    Py_XDECREF(keyval);
    return retval;
}


int get_header_float(PyObject* header, char* keyword, float* val,
                     float def) {
    PyObject* keystr;
    PyObject* keyval;
    int retval;

    keystr = PyString_FromString(keyword);
    keyval = PyObject_GetItem(header, keystr);

    if (keyval != NULL) {
        *val = (float) PyFloat_AsDouble(keyval);
        retval = 0;
    }
    else {
        PyErr_Clear();
        *val = def;
        retval = 1;
    }

    Py_DECREF(keystr);
    Py_XDECREF(keyval);
    return retval;
}


int get_header_double(PyObject* header, char* keyword, double* val,
                      double def) {
    PyObject* keystr;
    PyObject* keyval;
    int retval;

    keystr = PyString_FromString(keyword);
    keyval = PyObject_GetItem(header, keystr);

    if (keyval != NULL) {
        *val = PyFloat_AsDouble(keyval);
        retval = 0;
    }
    else {
        PyErr_Clear();
        *val = def;
        retval = 1;
    }

    Py_DECREF(keystr);
    Py_XDECREF(keyval);
    return retval;
}


int get_header_longlong(PyObject* header, char* keyword, long long* val,
                        long long def) {
    PyObject* keystr;
    PyObject* keyval;
    int retval;

    keystr = PyString_FromString(keyword);
    keyval = PyObject_GetItem(header, keystr);

    if (keyval != NULL) {
        *val = PyLong_AsLongLong(keyval);
        retval = 0;
    }
    else {
        PyErr_Clear();
        *val = def;
        retval = 1;
    }

    Py_DECREF(keystr);
    Py_XDECREF(keyval);
    return retval;
}


void tcolumns_from_header(PyObject* header, tcolumn** columns, long* tfields) {
    // Creates the array of tcolumn structures from the table column keywords
    // read from the PyFITS Header object; caller is responsible for freeing
    // the memory allocated for this array

    tcolumn* column;
    char tkw[9];
    unsigned int idx;

    char* ttype;
    char* tform;
    int dtcode;
    long trepeat;
    long twidth;
    int status;
    status = 0;

    get_header_long(header, "TFIELDS", tfields, 0);

    *columns = column = PyMem_New(tcolumn, (size_t) *tfields);
    if (column == NULL) {
        return;
    }


    for (idx = 1; idx <= *tfields; idx++, column++) {
        /* set some invalid defaults */
        column->ttype[0] = '\0';
        column->tbcol = 0;
        column->tdatatype = -9999; /* this default used by cfitsio */
        column->trepeat = 1;
        column->strnull[0] = '\0';
        column->tform[0] = '\0';
        column->twidth = 0;

        snprintf(tkw, 9, "TTYPE%u", idx);
        get_header_string(header, tkw, &ttype, "");
        strncpy(column->ttype, ttype, 69);
        column->ttype[69] = '\0';

        // TODO: I think TBCOL is usually inferred rather than specified in the
        // header keyword; see what CFITSIO does here.
        snprintf(tkw, 9, "TBCOL%u", idx);
        get_header_longlong(header, tkw, &(column->tbcol), 0);

        // TODO: I think TBCOL is usually inferred rather than specified in the
        // header keyword; see what CFITSIO does here.
        snprintf(tkw, 9, "TFORM%u", idx);
        get_header_string(header, tkw, &tform, "");
        strncpy(column->tform, tform, 9);
        column->tform[9] = '\0';
        fits_binary_tform(tform, &dtcode, &trepeat, &twidth, &status);
        if (status != 0) {
            process_status_err(status);
            return;
        }
        column->tdatatype = dtcode;
        column->trepeat = trepeat;
        column->twidth = twidth;

        snprintf(tkw, 9, "TSCAL%u", idx);
        get_header_double(header, tkw, &(column->tscale), 1.0);

        snprintf(tkw, 9, "TZERO%u", idx);
        get_header_double(header, tkw, &(column->tzero), 0.0);

        snprintf(tkw, 9, "TNULL%u", idx);
        get_header_longlong(header, tkw, &(column->tnull), NULL_UNDEFINED);
    }

    return;
}



void configure_compression(fitsfile* fileptr, tcolumn* columns, long tfields,
                           PyObject* header) {
    /* Configure the compression-related elements in the fitsfile struct
       using values in the FITS header. */

    FITSfile* Fptr;

    char keyword[9];
    char* zname;
    int znaxis;
    char* tmp;

    unsigned int idx;
    unsigned int found;

    Fptr = fileptr->Fptr;

    // Get the ZBITPIX header value; if this is missing we're in trouble
    if (0 != get_header_int(header, "ZBITPIX", &(Fptr->zbitpix), 0)) {
        return;
    }

    // By default assume there is no ZBLANK column and check for ZBLANK or
    // BLANK in the header
    Fptr->cn_zblank = Fptr->cn_zzero = Fptr->cn_zscale = -1;
    Fptr->cn_uncompressed = 0;

    found = 0;
    // Check for a ZBLANK, ZZERO, and UNCOMPRESSED_DATA columns in the
    // compressed data table
    for (idx = 1; idx <= tfields; idx++) {
        if (0 == strncmp(columns[idx].ttype, "ZBLANK", 7)) {
            Fptr->cn_zblank = 1;
            found++;
        } else if (0 == strncmp(columns[idx].ttype, "ZZERO", 6)) {
            Fptr->cn_zzero = 1;
            found++;
        } else if (0 == strncmp(columns[idx].ttype, "UNCOMPRESSED_DATA", 18)) {
            Fptr->cn_uncompressed = 1;
            found++;
        }

        if (found == 3) {
            break;
        }
    }

    Fptr->zblank = 0;
    if (Fptr->cn_zblank != 1) {
        // No ZBLANK column--check the ZBLANK and BLANK heard keywords
        if(0 != get_header_int(header, "ZBLANK", &(Fptr->zblank), 0)) {
            // ZBLANK keyword not found
            get_header_int(header, "BLANK", &(Fptr->zblank), 0);
        }
    }

    for (idx = 1; idx <= tfields; idx++) {
        if (0 == strncmp(columns[idx].ttype, "ZSCALE", 69)) {
            Fptr->cn_zscale = 1;
            break;
        }
    }

    Fptr->zscale = 1.0;
    if (Fptr->cn_zscale != 1) {
        if (0 != get_header_double(header, "ZSCALE", &(Fptr->zscale), 1.0)) {
            Fptr->cn_zscale = 0;
        }
    }
    Fptr->cn_bscale = Fptr->zscale;

    for (idx = 1; idx <= tfields; idx++) {
        if (0 == strncmp(columns[idx].ttype, "ZZERO", 69)) {
            Fptr->cn_zzero = 1;
            break;
        }
    }

    Fptr->zzero = 0.0;
    if (Fptr->cn_zzero != 1) {
        if (0 != get_header_double(header, "ZZERO", &(Fptr->zzero), 0.0)) {
            Fptr->cn_zzero = 0;
        }
    }
    Fptr->cn_bzero = Fptr->zzero;

    get_header_string(header, "ZCMPTYPE", &tmp, DEFAULT_COMPRESSION_TYPE);
    strncpy(Fptr->zcmptype, tmp, 11);
    Fptr->zcmptype[strnlen(tmp, 11)] = '\0';

    if (0 == strcmp(Fptr->zcmptype, "RICE_1")) {
        Fptr->compress_type = RICE_1;
    } else if (0 == strcmp(Fptr->zcmptype, "GZIP_1")) {
        Fptr->compress_type = GZIP_1;
    } else if (0 == strcmp(Fptr->zcmptype, "PLIO_1")) {
        Fptr->compress_type = PLIO_1;
    } else if (0 == strcmp(Fptr->zcmptype, "HCOMPRESS_1")) {
        Fptr->compress_type = HCOMPRESS_1;
    } else {
        PyErr_Format(PyExc_ValueError, "Unrecognized compression type: %s",
                     Fptr->zcmptype);
        return;
    }

    get_header_int(header, "ZNAXIS", &znaxis, 0);
    Fptr->zndim = znaxis;

    if (znaxis > MAX_COMPRESS_DIM) {
        // The CFITSIO compression code currently only supports up to 6
        // dimensions by default.
        znaxis = MAX_COMPRESS_DIM;
    }

    Fptr->maxtilelen = 0;
    for (idx = 1; idx <= znaxis; idx++) {
        snprintf(keyword, 9, "ZNAXIS%u", idx);
        get_header_long(header, keyword, Fptr->znaxis + idx - 1, 0);
        snprintf(keyword, 9, "ZTILE%u", idx);
        get_header_long(header, keyword, Fptr->tilesize + idx - 1, 0);
        if (Fptr->tilesize[idx - 1] > Fptr->maxtilelen) {
            Fptr->maxtilelen = Fptr->tilesize[idx - 1];
        }
    }

    // Set some more default compression options
    Fptr->rice_blocksize = DEFAULT_BLOCK_SIZE;
    Fptr->rice_bytepix = DEFAULT_BYTE_PIX;
    Fptr->quantize_level = DEFAULT_QUANTIZE_LEVEL;
    Fptr->hcomp_smooth = DEFAULT_HCOMP_SMOOTH;
    Fptr->hcomp_scale = DEFAULT_HCOMP_SCALE;

    // Now process the ZVALn keywords
    idx = 1;
    while (1) {
        snprintf(keyword, 9, "ZNAME%u", idx);
        // Assumes there are no gaps in the ZNAMEn keywords; this same
        // assumption was made in the Python code.  This could be done slightly
        // more flexibly by using a wildcard slice of the header
        if (0 != get_header_string(header, keyword, &zname, "")) {
            break;
        }
        snprintf(keyword, 9, "ZVAL%u", idx);
        if (Fptr->compress_type == RICE_1) {
            if (0 == strcmp(zname, "BLOCKSIZE")) {
                get_header_int(header, keyword, &(Fptr->rice_blocksize),
                               DEFAULT_BLOCK_SIZE);
            } else if (0 == strcmp(zname, "BYTEPIX")) {
                get_header_int(header, keyword, &(Fptr->rice_bytepix),
                               DEFAULT_BYTE_PIX);
            }
        } else if (Fptr->compress_type == HCOMPRESS_1) {
            if (0 == strcmp(zname, "SMOOTH")) {
                get_header_int(header, keyword, &(Fptr->hcomp_smooth),
                               DEFAULT_HCOMP_SMOOTH);
            } else if (0 == strcmp(zname, "SCALE")) {
                get_header_float(header, keyword, &(Fptr->hcomp_scale),
                                 DEFAULT_HCOMP_SCALE);
            }
        } else if (Fptr->zbitpix < 0 && 0 == strcmp(zname, "NOISEBIT")) {
             get_header_float(header, keyword, &(Fptr->quantize_level),
                              DEFAULT_QUANTIZE_LEVEL);
        }

        idx++;
    }


    Fptr->compressimg = 1;
    Fptr->maxelem = imcomp_calc_max_elem(Fptr->compress_type,
                                         Fptr->maxtilelen,
                                         Fptr->zbitpix,
                                         Fptr->rice_blocksize);
    Fptr->cn_compressed = 1;
    Fptr->cn_gzip_data = -1;
    return;
}


void open_from_filename(fitsfile** fileptr, char* filename) {
    int status;
    status = 0;
    // TODO: This function should probably actually return the status code for
    // error handling
    fits_open_data(fileptr, filename, 0, &status);
    return;
}


void open_from_pyfits_hdu(fitsfile** fileptr, void** buf, size_t* bufsize,
                          PyObject* hdu, tcolumn* columns) {
    PyObject* header;
    PyArrayObject* data;
    PyArrayObject* base;
    PyArrayObject* tmp;
    FITSfile* Fptr;

    int status;
    long tfields;
    long long rowlen;
    long long nrows;
    long long heapsize;
    long long theap;

    header = PyObject_GetAttrString(hdu, "_header");
    if (header == NULL) {
        goto fail;
    }

    data = (PyArrayObject*) PyObject_GetAttrString(hdu, "compData");
    if (data == NULL) {
        goto fail;
    }


    tcolumns_from_header(header, &columns, &tfields);
    if (PyErr_Occurred()) {
        goto fail;
    }

    get_header_longlong(header, "NAXIS1", &rowlen, 0);
    get_header_longlong(header, "NAXIS2", &nrows, 0);

    // The PCOUNT keyword contains the number of bytes in the table heap
    get_header_longlong(header, "PCOUNT", &heapsize, 0);

    // The THEAP keyword gives the offset of the heap from the beginning of
    // the HDU data portion; normally this offset is 0 but it can be set
    // to something else with THEAP
    get_header_longlong(header, "THEAP", &theap, 0);


    // Walk the array data bases until we find the lowest ndarray base; for
    // CompImageHDUs there should always be at least one contiguous byte array
    // allocated for the table and its heap
    if (!PyObject_TypeCheck(data, &PyArray_Type)) {
        PyErr_SetString(PyExc_TypeError,
                        "CompImageHDU.compData must be a numpy.ndarray");
        goto fail;
    }

    tmp = base = data;
    while (PyObject_TypeCheck((PyObject*) tmp, &PyArray_Type)) {
        base = tmp;
        *bufsize = (size_t) PyArray_NBYTES(base);
        tmp = (PyArrayObject*) PyArray_BASE(base);
        if (tmp == NULL) {
            break;
        }
    }

    *buf = PyArray_DATA(base);

    // This shouldn't happen, but just for sanity's sake
    if (*bufsize < 2880) {
        *bufsize = 2880;
    }

    fits_create_memfile(fileptr, buf, bufsize, 0, PyArray_realloc, &status);

    if (status != 0) {
        process_status_err(status);
        goto fail;
    }

    Fptr = (*fileptr)->Fptr;

    // Now we have some fun munging some of the elements in the fitsfile struct
    Fptr->tableptr = columns;
    Fptr->hdutype = BINARY_TBL;  /* This is a binary table HDU */
    Fptr->lasthdu = 1;
    Fptr->headstart[0] = 0;
    Fptr->headend = 0;
    Fptr->datastart = 0;  /* There is no header, data starts at 0 */
    Fptr->tfield = tfields;
    Fptr->origrows = Fptr->numrows = nrows;
    Fptr->rowlength = rowlen;
    if (theap != 0) {
        Fptr->heapstart = theap;
    } else {
        Fptr->heapstart = rowlen * nrows;
    }

    Fptr->heapsize = heapsize;

    // If any errors occur in this function they'll bubble up from here to
    // compression_decompress_hdu
    configure_compression(*fileptr, columns, tfields, header);

fail:
    Py_XDECREF(header);
    Py_XDECREF(data);
    return;
}


PyObject* compression_compress_hdu(PyObject* self, PyObject* args)
{
    PyObject* hdu;
    tcolumn* columns = NULL;

    void* outbuf;
    size_t outbufsize;

    PyArrayObject* indata;
    int datatype;
    int npdatatype;

    fitsfile* fileptr;
    int status = 0;

    if (!PyArg_ParseTuple(args, "O:compression.decompress_hdu", &hdu))
    {
        PyErr_SetString(PyExc_TypeError, "Couldn't parse arguments");
        return NULL;
    }

    // For HDU compression never use CFITSIO to write directly to the file;
    // although there's nothing wrong with CFITSIO, right now that would cause
    // too much confusion to PyFITS' internal book keeping.
    // We just need to get the compressed bytes and PyFITS will handle the
    // writing of them.
    open_from_pyfits_hdu(&fileptr, &outbuf, &outbufsize, hdu, columns);
    if (PyErr_Occurred()) {
        return NULL;
    }

    bitpix_to_datatypes(fileptr->Fptr->zbitpix, &datatype, &npdatatype);
    if (PyErr_Occurred()) {
        return NULL;
    }

    indata = (PyArrayObject*) PyObject_GetAttrString(hdu, "data");

    // Test values
    fits_write_img(fileptr, datatype, 1, PyArray_SIZE(indata), indata->data,
                   &status);
    if (status != 0) {
        process_status_err(status);
        goto fail;
    }

    status = 0;
    fits_flush_buffer(fileptr, 1, &status);

    if (columns != NULL) {
        PyMem_Free(columns);
    }
    Py_XDECREF(indata);

    return Py_None;

fail:
    // TODO: Reconsider how to handle memory allocation/cleanup in a clean way
    if (columns != NULL) {
        PyMem_Free(columns);
        Py_XDECREF(indata);
    }

    return NULL;
}


PyObject* compression_decompress_hdu(PyObject* self, PyObject* args)
{
    PyObject* hdu;
    PyObject* fileobj = NULL;
    PyObject* filename = NULL;
    tcolumn* columns = NULL;

    void* inbuf;
    size_t inbufsize;

    PyArrayObject* outdata;
    int datatype;
    int npdatatype;
    int zndim;
    long* znaxis;
    long arrsize;
    unsigned int idx;

    fitsfile* fileptr;
    int anynul = 0;
    int status = 0;

    if (!PyArg_ParseTuple(args, "O:compression.decompress_hdu", &hdu))
    {
        PyErr_SetString(PyExc_TypeError, "Couldn't parse arguments");
        return NULL;
    }

    // TODO: Error checking, obviously...; type check that the passed in HDU is
    // a CompImageHDU
    // Use '_header' instead of 'header' since the latter returns the header
    // for the compressed image when returned from CompImageHDU, instead of the
    // original header
    fileobj = PyObject_GetAttrString(hdu, "_file");
    if (fileobj != Py_None) {
        filename = PyObject_GetAttrString(fileobj, "name");
        // TODO: Check that the file exists and is readable
        open_from_filename(&fileptr, PyString_AsString(filename));
    }
    else {
        open_from_pyfits_hdu(&fileptr, &inbuf, &inbufsize, hdu, columns);
        if (PyErr_Occurred()) {
            return NULL;
        }
    }

    Py_DECREF(fileobj);
    Py_XDECREF(filename);

    bitpix_to_datatypes(fileptr->Fptr->zbitpix, &datatype, &npdatatype);
    if (PyErr_Occurred()) {
        return NULL;
    }

    zndim = fileptr->Fptr->zndim;
    znaxis = (long*) PyMem_Malloc(sizeof(long) * zndim);
    arrsize = 1;
    for (idx = 0; idx < zndim; idx++) {
        znaxis[zndim - idx - 1] = fileptr->Fptr->znaxis[idx];
        arrsize *= fileptr->Fptr->znaxis[idx];
    }

    /* Create and allocate a new array for the decompressed data */
    outdata = (PyArrayObject*) PyArray_SimpleNew(zndim, znaxis, npdatatype);

    // Test values
    fits_read_img(fileptr, datatype, 1, arrsize, NULL, outdata->data, &anynul,
                  &status);

    // TODO: Reconsider how to handle memory allocation/cleanup in a clean way
    if (columns != NULL) {
        PyMem_Free(columns);
    }

    PyMem_Free(znaxis);
    fits_close_file(fileptr, &status);

    return (PyObject*) outdata;
}


/* Method table mapping names to wrappers */
static PyMethodDef compression_methods[] =
{
   /*{"decompressData", compression_decompressData, METH_VARARGS},
   {"compressData", compression_compressData, METH_VARARGS},*/
   {"compress_hdu", compression_compress_hdu, METH_VARARGS},
   {"decompress_hdu", compression_decompress_hdu, METH_VARARGS},
   {NULL, NULL}
};

#if PY_MAJOR_VERSION >=3
static struct PyModuleDef compressionmodule = {
    PyModuleDef_HEAD_INIT,
    "compression",
    "pyfits.compression module",
    -1, /* No global state */
    compression_methods
};

PyObject *
PyInit_compression(void)
{
    PyObject *module = PyModule_Create(&compressionmodule);
    import_array();
    return module;
}
#else
PyMODINIT_FUNC initcompression(void)
{
   Py_InitModule4("compression", compression_methods, "compression module",
                  NULL, PYTHON_API_VERSION);
   import_array();
}
#endif
