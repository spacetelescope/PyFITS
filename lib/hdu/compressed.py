import warnings

import numpy as np

from pyfits import rec
from pyfits.column import Column, ColDefs
from pyfits.fitsrec import FITS_rec
from pyfits.hdu.extension import _ExtensionHDU
from pyfits.hdu.image import _ImageBaseHDU, ImageHDU
from pyfits.hdu.table import BinTableHDU

try:
    from pyfits import pyfitsComp
    COMPRESSION_SUPPORTED = True
except:
    COMPRESSION_SUPPORTED = False
    raise

if COMPRESSION_SUPPORTED:
    # If compression object library imports properly then define the
    # CompImageHDU class.

    # Default compression parameter values

    def_compressionType = 'RICE_1'
    def_quantizeLevel = 16.
    def_hcompScale = 0.
    def_hcompSmooth = 0
    def_blockSize = 32
    def_bytePix = 4

    class CompImageHDU(BinTableHDU):
        """
        Compressed Image HDU class.
        """
        def __init__(self, data=None, header=None, name=None,
                     compressionType=def_compressionType,
                     tileSize=None,
                     hcompScale=def_hcompScale,
                     hcompSmooth=def_hcompSmooth,
                     quantizeLevel=def_quantizeLevel):
            """
            Parameters
            ----------
            data : array, optional
                data of the image

            header : Header instance, optional
                header to be associated with the image; when reading
                the HDU from a file ( `data` = "DELAYED" ), the header
                read from the file

            name : str, optional
                the ``EXTNAME`` value; if this value is `None`, then
                the name from the input image header will be used; if
                there is no name in the input image header then the
                default name ``COMPRESSED_IMAGE`` is used.

            compressionType : str, optional
                compression algorithm 'RICE_1', 'PLIO_1', 'GZIP_1',
                'HCOMPRESS_1'

            tileSize : int, optional
                compression tile sizes.  Default treats each row of
                image as a tile.

            hcompScale : float, optional
                HCOMPRESS scale parameter

            hcompSmooth : float, optional
                HCOMPRESS smooth parameter

            quantizeLevel : float, optional
                floating point quantization level; see note below

            Notes
            -----
            The pyfits module supports 2 methods of image compression.

                1) The entire FITS file may be externally compressed
                   with the gzip or pkzip utility programs, producing
                   a ``*.gz`` or ``*.zip`` file, respectively.  When
                   reading compressed files of this type, pyfits first
                   uncompresses the entire file into a temporary file
                   before performing the requested read operations.
                   The pyfits module does not support writing to these
                   types of compressed files.  This type of
                   compression is supported in the `_File` class, not
                   in the `CompImageHDU` class.  The file compression
                   type is recognized by the ``.gz`` or ``.zip`` file
                   name extension.

                2) The `CompImageHDU` class supports the FITS tiled
                   image compression convention in which the image is
                   subdivided into a grid of rectangular tiles, and
                   each tile of pixels is individually compressed.
                   The details of this FITS compression convention are
                   described at the `FITS Support Office web site
                   <http://fits.gsfc.nasa.gov/registry/tilecompression.html>`_.
                   Basically, the compressed image tiles are stored in
                   rows of a variable length arrray column in a FITS
                   binary table.  The pyfits module recognizes that
                   this binary table extension contains an image and
                   treats it as if it were an image extension.  Under
                   this tile-compression format, FITS header keywords
                   remain uncompressed.  At this time, pyfits does not
                   support the ability to extract and uncompress
                   sections of the image without having to uncompress
                   the entire image.

            The `pyfits` module supports 3 general-purpose compression
            algorithms plus one other special-purpose compression
            technique that is designed for data masks with positive
            integer pixel values.  The 3 general purpose algorithms
            are GZIP, Rice, and HCOMPRESS, and the special-purpose
            technique is the IRAF pixel list compression technique
            (PLIO).  The `compressionType` parameter defines the
            compression algorithm to be used.

            The FITS image can be subdivided into any desired
            rectangular grid of compression tiles.  With the GZIP,
            Rice, and PLIO algorithms, the default is to take each row
            of the image as a tile.  The HCOMPRESS algorithm is
            inherently 2-dimensional in nature, so the default in this
            case is to take 16 rows of the image per tile.  In most
            cases, it makes little difference what tiling pattern is
            used, so the default tiles are usually adequate.  In the
            case of very small images, it could be more efficient to
            compress the whole image as a single tile.  Note that the
            image dimensions are not required to be an integer
            multiple of the tile dimensions; if not, then the tiles at
            the edges of the image will be smaller than the other
            tiles.  The `tileSize` parameter may be provided as a list
            of tile sizes, one for each dimension in the image.  For
            example a `tileSize` value of ``[100,100]`` would divide a
            300 X 300 image into 9 100 X 100 tiles.

            The 4 supported image compression algorithms are all
            'loss-less' when applied to integer FITS images; the pixel
            values are preserved exactly with no loss of information
            during the compression and uncompression process.  In
            addition, the HCOMPRESS algorithm supports a 'lossy'
            compression mode that will produce larger amount of image
            compression.  This is achieved by specifying a non-zero
            value for the `hcompScale` parameter.  Since the amount of
            compression that is achieved depends directly on the RMS
            noise in the image, it is usually more convenient to
            specify the `hcompScale` factor relative to the RMS noise.
            Setting `hcompScale` = 2.5 means use a scale factor that
            is 2.5 times the calculated RMS noise in the image tile.
            In some cases it may be desirable to specify the exact
            scaling to be used, instead of specifying it relative to
            the calculated noise value.  This may be done by
            specifying the negative of the desired scale value
            (typically in the range -2 to -100).

            Very high compression factors (of 100 or more) can be
            achieved by using large `hcompScale` values, however, this
            can produce undesireable 'blocky' artifacts in the
            compressed image.  A variation of the HCOMPRESS algorithm
            (called HSCOMPRESS) can be used in this case to apply a
            small amount of smoothing of the image when it is
            uncompressed to help cover up these artifacts.  This
            smoothing is purely cosmetic and does not cause any
            significant change to the image pixel values.  Setting the
            `hcompSmooth` parameter to 1 will engage the smoothing
            algorithm.

            Floating point FITS images (which have ``BITPIX`` = -32 or
            -64) usually contain too much 'noise' in the least
            significant bits of the mantissa of the pixel values to be
            effectively compressed with any lossless algorithm.
            Consequently, floating point images are first quantized
            into scaled integer pixel values (and thus throwing away
            much of the noise) before being compressed with the
            specified algorithm (either GZIP, RICE, or HCOMPRESS).
            This technique produces much higher compression factors
            than simply using the GZIP utility to externally compress
            the whole FITS file, but it also means that the original
            floating point value pixel values are not exactly
            perserved.  When done properly, this integer scaling
            technique will only discard the insignificant noise while
            still preserving all the real imformation in the image.
            The amount of precision that is retained in the pixel
            values is controlled by the `quantizeLevel` parameter.
            Larger values will result in compressed images whose
            pixels more closely match the floating point pixel values,
            but at the same time the amount of compression that is
            achieved will be reduced.  Users should experiment with
            different values for this parameter to determine the
            optimal value that preserves all the useful information in
            the image, without needlessly preserving all the 'noise'
            which will hurt the compression efficiency.

            The default value for the `quantizeLevel` scale factor is
            16, which means that scaled integer pixel values will be
            quantized such that the difference between adjacent
            integer values will be 1/16th of the noise level in the
            image background.  An optimized algorithm is used to
            accurately estimate the noise in the image.  As an
            example, if the RMS noise in the background pixels of an
            image = 32.0, then the spacing between adjacent scaled
            integer pixel values will equal 2.0 by default.  Note that
            the RMS noise is independently calculated for each tile of
            the image, so the resulting integer scaling factor may
            fluctuate slightly for each tile.  In some cases, it may
            be desireable to specify the exact quantization level to
            be used, instead of specifying it relative to the
            calculated noise value.  This may be done by specifying
            the negative of desired quantization level for the value
            of `quantizeLevel`.  In the previous example, one could
            specify `quantizeLevel`=-2.0 so that the quantized integer
            levels differ by 2.0.  Larger negative values for
            `quantizeLevel` means that the levels are more
            coarsely-spaced, and will produce higher compression
            factors.
            """

            from pyfits.core import DELAYED

            self._file, self._datLoc = None, None

            if data is DELAYED:
                # Reading the HDU from a file
                BinTableHDU.__init__(self, data=data, header=header)
            else:
                # Create at least a skeleton HDU that matches the input
                # header and data (if any were input)
                BinTableHDU.__init__(self, data=None, header=header)

                # Store the input image data
                self.data = data

                # Update the table header (_header) to the compressed
                # image format and to match the input data (if any);
                # Create the image header (_imageHeader) from the input
                # image header (if any) and ensure it matches the input
                # data; Create the initially empty table data array to
                # hold the compressed data.
                self.updateHeaderData(header, name, compressionType,
                                      tileSize, hcompScale, hcompSmooth,
                                      quantizeLevel)

            # store any scale factors from the table header
            self._bzero = self._header.get('BZERO', 0)
            self._bscale = self._header.get('BSCALE', 1)
            self._bitpix = self._header['ZBITPIX']

            # Maintain a reference to the table header in the image header.
            # This reference will be used to update the table header whenever
            # a card in the image header is updated.
            self.header._tableHeader = self._header

        def updateHeaderData(self, imageHeader,
                             name=None,
                             compressionType=None,
                             tileSize=None,
                             hcompScale=None,
                             hcompSmooth=None,
                             quantizeLevel=None):
            """
            Update the table header (`_header`) to the compressed
            image format and to match the input data (if any).  Create
            the image header (`_imageHeader`) from the input image
            header (if any) and ensure it matches the input
            data. Create the initially-empty table data array to hold
            the compressed data.

            This method is mainly called internally, but a user may wish to
            call this method after assigning new data to the `CompImageHDU`
            object that is of a different type.

            Parameters
            ----------
            imageHeader : Header instance
                header to be associated with the image

            name : str, optional
                the ``EXTNAME`` value; if this value is `None`, then
                the name from the input image header will be used; if
                there is no name in the input image header then the
                default name 'COMPRESSED_IMAGE' is used

            compressionType : str, optional
                compression algorithm 'RICE_1', 'PLIO_1', 'GZIP_1',
                'HCOMPRESS_1'; if this value is `None`, use value
                already in the header; if no value already in the
                header, use 'RICE_1'

            tileSize : sequence of int, optional
                compression tile sizes as a list; if this value is
                `None`, use value already in the header; if no value
                already in the header, treat each row of image as a
                tile

            hcompScale : float, optional
                HCOMPRESS scale parameter; if this value is `None`,
                use the value already in the header; if no value
                already in the header, use 1

            hcompSmooth : float, optional
                HCOMPRESS smooth parameter; if this value is `None`,
                use the value already in the header; if no value
                already in the header, use 0

            quantizeLevel : float, optional
                floating point quantization level; if this value
                is `None`, use the value already in the header; if
                no value already in header, use 16
            """

            from pyfits.core import _makep

            # Construct an ImageBaseHDU object using the input header
            # and data so that we can ensure that the input image header
            # matches the input image data.  Store the header from this
            # temporary HDU object as the image header for this object.

            self._imageHeader = \
              ImageHDU(data=self.data, header=imageHeader).header
            self._imageHeader._tableHeader = self._header

            # Update the extension name in the table header

            if not name and not self._header.has_key('EXTNAME'):
                name = 'COMPRESSED_IMAGE'

            if name:
                self._header.update('EXTNAME', name,
                                    'name of this binary table extension',
                                    after='TFIELDS')
                self.name = name
            else:
                self.name = self._header['EXTNAME']

            # Set the compression type in the table header.

            if compressionType:
                if compressionType not in ['RICE_1','GZIP_1','PLIO_1',
                                           'HCOMPRESS_1']:
                    warnings.warn('Warning: Unknown compression type provided.'+
                                  '  Default RICE_1 compression used.')
                    compressionType = 'RICE_1'

                self._header.update('ZCMPTYPE', compressionType,
                                    'compression algorithm',
                                    after='TFIELDS')
            else:
                compressionType = self._header.get('ZCMPTYPE', 'RICE_1')

            # If the input image header had BSCALE/BZERO cards, then insert
            # them in the table header.

            if imageHeader:
                bzero = imageHeader.get('BZERO', 0.0)
                bscale = imageHeader.get('BSCALE', 1.0)
                afterCard = 'EXTNAME'

                if bscale != 1.0:
                    self._header.update('BSCALE',bscale,after=afterCard)
                    afterCard = 'BSCALE'

                if bzero != 0.0:
                    self._header.update('BZERO',bzero,after=afterCard)

                bitpix_comment = imageHeader.ascardlist()['BITPIX'].comment
                naxis_comment =  imageHeader.ascardlist()['NAXIS'].comment
            else:
                bitpix_comment = 'data type of original image'
                naxis_comment = 'dimension of original image'

            # Set the label for the first column in the table

            self._header.update('TTYPE1', 'COMPRESSED_DATA',
                                'label for field 1', after='TFIELDS')

            # Set the data format for the first column.  It is dependent
            # on the requested compression type.

            if compressionType == 'PLIO_1':
                tform1 = '1PI'
            else:
                tform1 = '1PB'

            self._header.update('TFORM1', tform1,
                                'data format of field: variable length array',
                                after='TTYPE1')

            # Create the first column for the table.  This column holds the
            # compressed data.
            col1 = Column(name=self._header['TTYPE1'], format=tform1)

            # Create the additional columns required for floating point
            # data and calculate the width of the output table.

            if self._imageHeader['BITPIX'] < 0:
                # floating point image has 'COMPRESSED_DATA',
                # 'UNCOMPRESSED_DATA', 'ZSCALE', and 'ZZERO' columns.
                ncols = 4

                # Set up the second column for the table that will hold
                # any uncompressable data.
                self._header.update('TTYPE2', 'UNCOMPRESSED_DATA',
                                    'label for field 2', after='TFORM1')

                if self._imageHeader['BITPIX'] == -32:
                    tform2 = '1PE'
                else:
                    tform2 = '1PD'

                self._header.update('TFORM2', tform2,
                                 'data format of field: variable length array',
                                 after='TTYPE2')
                col2 = Column(name=self._header['TTYPE2'],format=tform2)

                # Set up the third column for the table that will hold
                # the scale values for quantized data.
                self._header.update('TTYPE3', 'ZSCALE',
                                    'label for field 3', after='TFORM2')
                self._header.update('TFORM3', '1D',
                                 'data format of field: 8-byte DOUBLE',
                                 after='TTYPE3')
                col3 = Column(name=self._header['TTYPE3'],
                              format=self._header['TFORM3'])

                # Set up the fourth column for the table that will hold
                # the zero values for the quantized data.
                self._header.update('TTYPE4', 'ZZERO',
                                    'label for field 4', after='TFORM3')
                self._header.update('TFORM4', '1D',
                                 'data format of field: 8-byte DOUBLE',
                                 after='TTYPE4')
                after = 'TFORM4'
                col4 = Column(name=self._header['TTYPE4'],
                              format=self._header['TFORM4'])

                # Create the ColDefs object for the table
                cols = ColDefs([col1, col2, col3, col4])
            else:
                # default table has just one 'COMPRESSED_DATA' column
                ncols = 1
                after = 'TFORM1'

                # remove any header cards for the additional columns that
                # may be left over from the previous data
                keyList = ['TTYPE2', 'TFORM2', 'TTYPE3', 'TFORM3', 'TTYPE4',
                           'TFORM4']

                for k in keyList:
                    del self._header[k]

                # Create the ColDefs object for the table
                cols = ColDefs([col1])

            # Update the table header with the width of the table, the
            # number of fields in the table, the indicator for a compressed
            # image HDU, the data type of the image data and the number of
            # dimensions in the image data array.
            self._header.update('NAXIS1', ncols*8, 'width of table in bytes')
            self._header.update('TFIELDS', ncols,
                                'number of fields in each row')
            self._header.update('ZIMAGE', True,
                                'extension contains compressed image',
                                after = after)
            self._header.update('ZBITPIX', self._imageHeader['BITPIX'],
                                bitpix_comment,
                                after = 'ZIMAGE')
            self._header.update('ZNAXIS', self._imageHeader['NAXIS'],
                                naxis_comment,
                                after = 'ZBITPIX')

            # Strip the table header of all the ZNAZISn and ZTILEn keywords
            # that may be left over from the previous data

            i = 1

            while 1:
                try:
                    del self._header.ascardlist()['ZNAXIS'+`i`]
                    del self._header.ascardlist()['ZTILE'+`i`]
                    i += 1
                except KeyError:
                    break

            # Verify that any input tile size parameter is the appropriate
            # size to match the HDU's data.

            if not tileSize:
                tileSize = []
            elif len(tileSize) != self._imageHeader['NAXIS']:
                warnings.warn('Warning: Provided tile size not appropriate ' +
                              'for the data.  Default tile size will be used.')
                tileSize = []

            # Set default tile dimensions for HCOMPRESS_1

            if compressionType == 'HCOMPRESS_1':
                if self._imageHeader['NAXIS'] < 2:
                    raise ValueError, 'Hcompress cannot be used with ' + \
                                      '1-dimensional images.'
                elif self._imageHeader['NAXIS1'] < 4 or \
                self._imageHeader['NAXIS2'] < 4:
                    raise ValueError, 'Hcompress minimum image dimension is' + \
                                      ' 4 pixels'
                elif tileSize and (tileSize[0] < 4 or tileSize[1] < 4):
                    # user specified tile size is too small
                    raise ValueError, 'Hcompress minimum tile dimension is' + \
                                      ' 4 pixels'

                if tileSize and (tileSize[0] == 0 and tileSize[1] == 0):
                    #compress the whole image as a single tile
                    tileSize[0] = self._imageHeader['NAXIS1']
                    tileSize[1] = self._imageHeader['NAXIS2']

                    for i in range(2, self._imageHeader['NAXIS']):
                        # set all higher tile dimensions = 1
                        tileSize[i] = 1
                elif not tileSize:
                    # The Hcompress algorithm is inherently 2D in nature, so
                    # the row by row tiling that is used for other compression
                    # algorithms is not appropriate.  If the image has less
                    # than 30 rows, then the entire image will be compressed
                    # as a single tile.  Otherwise the tiles will consist of
                    # 16 rows of the image.  This keeps the tiles to a
                    # reasonable size, and it also includes enough rows to
                    # allow good compression efficiency.  It the last tile of
                    # the image happens to contain less than 4 rows, then find
                    # another tile size with between 14 and 30 rows
                    # (preferably even), so that the last tile has at least
                    # 4 rows.

                    # 1st tile dimension is the row length of the image
                    tileSize.append(self._imageHeader['NAXIS1'])

                    if self._imageHeader['NAXIS2'] <= 30:
                        tileSize.append(self._imageHeader['NAXIS1'])
                    else:
                        # look for another good tile dimension
                        if self._imageHeader['NAXIS2'] % 16 == 0 or \
                        self._imageHeader['NAXIS2'] % 16 > 3:
                            tileSize.append(16)
                        elif self._imageHeader['NAXIS2'] % 24 == 0 or \
                        self._imageHeader['NAXIS2'] % 24 > 3:
                            tileSize.append(24)
                        elif self._imageHeader['NAXIS2'] % 20 == 0 or \
                        self._imageHeader['NAXIS2'] % 20 > 3:
                            tileSize.append(20)
                        elif self._imageHeader['NAXIS2'] % 30 == 0 or \
                        self._imageHeader['NAXIS2'] % 30 > 3:
                            tileSize.append(30)
                        elif self._imageHeader['NAXIS2'] % 28 == 0 or \
                        self._imageHeader['NAXIS2'] % 28 > 3:
                            tileSize.append(28)
                        elif self._imageHeader['NAXIS2'] % 26 == 0 or \
                        self._imageHeader['NAXIS2'] % 26 > 3:
                            tileSize.append(26)
                        elif self._imageHeader['NAXIS2'] % 22 == 0 or \
                        self._imageHeader['NAXIS2'] % 22 > 3:
                            tileSize.append(22)
                        elif self._imageHeader['NAXIS2'] % 18 == 0 or \
                        self._imageHeader['NAXIS2'] % 18 > 3:
                            tileSize.append(18)
                        elif self._imageHeader['NAXIS2'] % 14 == 0 or \
                        self._imageHeader['NAXIS2'] % 14 > 3:
                            tileSize.append(14)
                        else:
                            tileSize.append(17)
                # check if requested tile size causes the last tile to have
                # less than 4 pixels

                remain = self._imageHeader['NAXIS1'] % tileSize[0] # 1st dimen

                if remain > 0 and remain < 4:
                    tileSize[0] += 1 # try increasing tile size by 1

                    remain = self._imageHeader['NAXIS1'] % tileSize[0]

                    if remain > 0 and remain < 4:
                        raise ValueError, 'Last tile along 1st dimension ' + \
                                          'has less than 4 pixels'

                remain = self._imageHeader['NAXIS2'] % tileSize[1] # 2nd dimen

                if remain > 0 and remain < 4:
                    tileSize[1] += 1 # try increasing tile size by 1

                    remain = self._imageHeader['NAXIS2'] % tileSize[1]

                    if remain > 0 and remain < 4:
                        raise ValueError, 'Last tile along 2nd dimension ' + \
                                          'has less than 4 pixels'

            # Set up locations for writing the next cards in the header.
            after = 'ZNAXIS'

            if self._imageHeader['NAXIS'] > 0:
                after1 = 'ZNAXIS1'
            else:
                after1 = 'ZNAXIS'

            # Calculate the number of rows in the output table and
            # write the ZNAXISn and ZTILEn cards to the table header.
            nrows = 1

            for i in range(0, self._imageHeader['NAXIS']):
                if tileSize:
                    ts = tileSize[i]
                elif not self._header.has_key('ZTILE'+`i+1`):
                    # Default tile size
                    if not i:
                        ts = self._imageHeader['NAXIS1']
                    else:
                        ts = 1
                else:
                    ts = self._header['ZTILE'+`i+1`]

                naxisn = self._imageHeader['NAXIS'+`i+1`]
                nrows = nrows * ((naxisn - 1) // ts + 1)

                if imageHeader and imageHeader.has_key('NAXIS'+`i+1`):
                    self._header.update('ZNAXIS'+`i+1`, naxisn,
                              imageHeader.ascardlist()['NAXIS'+`i+1`].comment,
                              after=after)
                else:
                    self._header.update('ZNAXIS'+`i+1`, naxisn,
                              'length of original image axis',
                              after=after)

                self._header.update('ZTILE'+`i+1`, ts,
                                    'size of tiles to be compressed',
                                    after=after1)
                after = 'ZNAXIS'+`i+1`
                after1 = 'ZTILE'+`i+1`

            # Set the NAXIS2 header card in the table hdu to the number of
            # rows in the table.
            self._header.update('NAXIS2', nrows, 'number of rows in table')

            # Create the record array to be used for the table data.
            self.columns = cols
            self.compData = FITS_rec(rec.array(None,
                                             formats=",".join(cols._recformats),
                                             names=cols.names, shape=nrows))
            self.compData._coldefs = self.columns
            self.compData.formats = self.columns.formats

            # Set up and initialize the variable length columns.  There will
            # either be one (COMPRESSED_DATA) or two (COMPRESSED_DATA,
            # UNCOMPRESSED_DATA) depending on whether we have floating point
            # data or not.  Note: the ZSCALE and ZZERO columns are fixed
            # length columns.
            for i in range(min(2,len(cols))):
                self.columns._arrays[i] = rec.recarray.field(self.compData,i)
                rec.recarray.field(self.compData,i)[0:] = 0
                self.compData._convert[i] = _makep(self.columns._arrays[i],
                                            rec.recarray.field(self.compData,i),
                                            self.columns._recformats[i]._dtype)

            # Set the compression parameters in the table header.

            # First, setup the values to be used for the compression parameters
            # in case none were passed in.  This will be either the value
            # already in the table header for that parameter or the default
            # value.
            i = 1

            while self._header.has_key('ZNAME'+`i`):
                if self._header['ZNAME'+`i`] == 'NOISEBIT':
                    if quantizeLevel == None:
                        quantizeLevel = self._header['ZVAL'+`i`]
                if self._header['ZNAME'+`i`] == 'SCALE   ':
                    if hcompScale == None:
                        hcompScale = self._header['ZVAL'+`i`]
                if self._header['ZNAME'+`i`] == 'SMOOTH  ':
                    if hcompSmooth == None:
                        hcompSmooth = self._header['ZVAL'+`i`]
                i += 1

            if quantizeLevel == None:
                quantizeLevel = def_quantizeLevel

            if hcompScale == None:
                hcompScale = def_hcompScale

            if hcompSmooth == None:
                hcompSmooth = def_hcompScale

            # Next, strip the table header of all the ZNAMEn and ZVALn keywords
            # that may be left over from the previous data

            i = 1

            while self._header.has_key('ZNAME'+`i`):
                del self._header.ascardlist()['ZNAME'+`i`]
                del self._header.ascardlist()['ZVAL'+`i`]
                i += 1

            # Finally, put the appropriate keywords back based on the
            # compression type.

            afterCard = 'ZCMPTYPE'
            i = 1

            if compressionType == 'RICE_1':
                self._header.update('ZNAME1', 'BLOCKSIZE',
                                    'compression block size',
                                    after=afterCard)
                self._header.update('ZVAL1', def_blockSize,
                                    'pixels per block',
                                    after='ZNAME1')

                self._header.update('ZNAME2', 'BYTEPIX',
                                    'bytes per pixel (1, 2, 4, or 8)',
                                    after='ZVAL1')

                if self._header['ZBITPIX'] == 8:
                    bytepix = 1
                elif self._header['ZBITPIX'] == 16:
                    bytepix = 2
                else:
                    bytepix = def_bytePix

                self._header.update('ZVAL2', bytepix,
                                    'bytes per pixel (1, 2, 4, or 8)',
                                        after='ZNAME2')
                afterCard = 'ZVAL2'
                i = 3
            elif compressionType == 'HCOMPRESS_1':
                self._header.update('ZNAME1', 'SCALE',
                                    'HCOMPRESS scale factor',
                                    after=afterCard)
                self._header.update('ZVAL1', hcompScale,
                                    'HCOMPRESS scale factor',
                                    after='ZNAME1')
                self._header.update('ZNAME2', 'SMOOTH',
                                    'HCOMPRESS smooth option',
                                    after='ZVAL1')
                self._header.update('ZVAL2', hcompSmooth,
                                    'HCOMPRESS smooth option',
                                    after='ZNAME2')
                afterCard = 'ZVAL2'
                i = 3

            if self._imageHeader['BITPIX'] < 0:   # floating point image
                self._header.update('ZNAME'+`i`, 'NOISEBIT',
                                    'floating point quantization level',
                                    after=afterCard)
                self._header.update('ZVAL'+`i`, quantizeLevel,
                                    'floating point quantization level',
                                    after='ZNAME'+`i`)

            if imageHeader:
                # Move SIMPLE card from the image header to the
                # table header as ZSIMPLE card.

                if imageHeader.has_key('SIMPLE'):
                    self._header.update('ZSIMPLE',
                            imageHeader['SIMPLE'],
                            imageHeader.ascardlist()['SIMPLE'].comment)

                # Move EXTEND card from the image header to the
                # table header as ZEXTEND card.

                if imageHeader.has_key('EXTEND'):
                    self._header.update('ZEXTEND',
                            imageHeader['EXTEND'],
                            imageHeader.ascardlist()['EXTEND'].comment)

                # Move BLOCKED card from the image header to the
                # table header as ZBLOCKED card.

                if imageHeader.has_key('BLOCKED'):
                    self._header.update('ZBLOCKED',
                            imageHeader['BLOCKED'],
                            imageHeader.ascardlist()['BLOCKED'].comment)

                # Move XTENSION card from the image header to the
                # table header as ZTENSION card.

                # Since we only handle compressed IMAGEs, ZTENSION should
                # always be IMAGE, even if the caller has passed in a header
                # for some other type of extension.
                if imageHeader.has_key('XTENSION'):
                    self._header.update('ZTENSION',
                            'IMAGE',
                            imageHeader.ascardlist()['XTENSION'].comment)

                # Move PCOUNT and GCOUNT cards from image header to the table
                # header as ZPCOUNT and ZGCOUNT cards.

                if imageHeader.has_key('PCOUNT'):
                    self._header.update('ZPCOUNT',
                            imageHeader['PCOUNT'],
                            imageHeader.ascardlist()['PCOUNT'].comment)

                if imageHeader.has_key('GCOUNT'):
                    self._header.update('ZGCOUNT',
                            imageHeader['GCOUNT'],
                            imageHeader.ascardlist()['GCOUNT'].comment)

                # Move CHECKSUM and DATASUM cards from the image header to the
                # table header as XHECKSUM and XDATASUM cards.

                if imageHeader.has_key('CHECKSUM'):
                    self._header.update('ZHECKSUM',
                            imageHeader['CHECKSUM'],
                            imageHeader.ascardlist()['CHECKSUM'].comment)

                if imageHeader.has_key('DATASUM'):
                    self._header.update('ZDATASUM',
                            imageHeader['DATASUM'],
                            imageHeader.ascardlist()['DATASUM'].comment)
            else:
                # Move XTENSION card from the image header to the
                # table header as ZTENSION card.

                # Since we only handle compressed IMAGEs, ZTENSION should
                # always be IMAGE, even if the caller has passed in a header
                # for some other type of extension.
                if self._imageHeader.has_key('XTENSION'):
                    self._header.update('ZTENSION',
                            'IMAGE',
                            self._imageHeader.ascardlist()['XTENSION'].comment)

                # Move PCOUNT and GCOUNT cards from image header to the table
                # header as ZPCOUNT and ZGCOUNT cards.

                if self._imageHeader.has_key('PCOUNT'):
                    self._header.update('ZPCOUNT',
                            self._imageHeader['PCOUNT'],
                            self._imageHeader.ascardlist()['PCOUNT'].comment)

                if self._imageHeader.has_key('GCOUNT'):
                    self._header.update('ZGCOUNT',
                            self._imageHeader['GCOUNT'],
                            self._imageHeader.ascardlist()['GCOUNT'].comment)


            # When we have an image checksum we need to ensure that the same
            # number of blank cards exist in the table header as there were in
            # the image header.  This allows those blank cards to be carried
            # over to the image header when the hdu is uncompressed.

            if self._header.has_key('ZHECKSUM'):
                imageHeader.ascardlist().count_blanks()
                self._imageHeader.ascardlist().count_blanks()
                self._header.ascardlist().count_blanks()
                requiredBlankCount = imageHeader.ascardlist()._blanks
                imageBlankCount = self._imageHeader.ascardlist()._blanks
                tableBlankCount = self._header.ascardlist()._blanks

                for i in range(requiredBlankCount - imageBlankCount):
                    self._imageHeader.add_blank()
                    tableBlankCount = tableBlankCount + 1

                for i in range(requiredBlankCount - tableBlankCount):
                    self._header.add_blank()


        def __getattr__(self, attr):
            """
            Get an HDU attribute.
            """
            if attr == 'data':
                # The data attribute is the image data (not the table data).

                # First we will get the table data (the compressed
                # data) from the file, if there is any.
                self.compData = BinTableHDU.__getattr__(self, attr)

                # Now that we have the compressed data, we need to uncompress
                # it into the image data.
                dataList = []
                naxesList = []
                tileSizeList = []
                zvalList = []
                uncompressedDataList = []

                # Set up an array holding the integer value that represents
                # undefined pixels.  This could come from the ZBLANK column
                # from the table, or from the ZBLANK header card (if no
                # ZBLANK column (all null values are the same for each tile)),
                # or from the BLANK header card.
                if not 'ZBLANK' in self.compData.names:
                    if self._header.has_key('ZBLANK'):
                        nullDvals = np.array(self._header['ZBLANK'],
                                             dtype='int32')
                        cn_zblank = -1 # null value is a constant
                    elif self._header.has_key('BLANK'):
                        nullDvals = np.array(self._header['BLANK'],
                                             dtype='int32')
                        cn_zblank = -1 # null value is a constant
                    else:
                        cn_zblank = 0 # no null value given so don't check
                        nullDvals = np.array(0,dtype='int32')
                else:
                    cn_zblank = 1  # null value supplied as a column

                    #if sys.byteorder == 'little':
                    #    nullDvals = self.compData.field('ZBLANK').byteswap()
                    #else:
                    #    nullDvals = self.compData.field('ZBLANK')
                    nullDvals = self.compData.field('ZBLANK')

                # Set up an array holding the linear scale factor values
                # This could come from the ZSCALE column from the table, or
                # from the ZSCALE header card (if no ZSCALE column (all
                # linear scale factor values are the same for each tile)).

                if self._header.has_key('BSCALE'):
                    self._bscale = self._header['BSCALE']
                    del self._header['BSCALE']
                else:
                    self._bscale = 1.

                if not 'ZSCALE' in self.compData.names:
                    if self._header.has_key('ZSCALE'):
                        zScaleVals = np.array(self._header['ZSCALE'],
                                              dtype='float64')
                        cn_zscale = -1 # scale value is a constant
                    else:
                        cn_zscale = 0 # no scale factor given so don't scale
                        zScaleVals = np.array(1.0,dtype='float64')
                else:
                    cn_zscale = 1 # scale value supplied as a column

                    #if sys.byteorder == 'little':
                    #    zScaleVals = self.compData.field('ZSCALE').byteswap()
                    #else:
                    #    zScaleVals = self.compData.field('ZSCALE')
                    zScaleVals = self.compData.field('ZSCALE')

                # Set up an array holding the zero point offset values
                # This could come from the ZZERO column from the table, or
                # from the ZZERO header card (if no ZZERO column (all
                # zero point offset values are the same for each tile)).

                if self._header.has_key('BZERO'):
                    self._bzero = self._header['BZERO']
                    del self._header['BZERO']
                else:
                    self._bzero = 0.

                if not 'ZZERO' in self.compData.names:
                    if self._header.has_key('ZZERO'):
                        zZeroVals = np.array(self._header['ZZERO'],
                                             dtype='float64')
                        cn_zzero = -1 # zero value is a constant
                    else:
                        cn_zzero = 0 # no zero value given so don't scale
                        zZeroVals = np.array(1.0,dtype='float64')
                else:
                    cn_zzero = 1 # zero value supplied as a column

                    #if sys.byteorder == 'little':
                    #    zZeroVals = self.compData.field('ZZERO').byteswap()
                    #else:
                    #    zZeroVals = self.compData.field('ZZERO')
                    zZeroVals = self.compData.field('ZZERO')

                # Is uncompressed data supplied in a column?
                if not 'UNCOMPRESSED_DATA' in self.compData.names:
                    cn_uncompressed = 0 # no uncompressed data supplied
                else:
                    cn_uncompressed = 1 # uncompressed data supplied as column

                # Take the compressed data out of the array and put it into
                # a list as character bytes to pass to the decompression
                # routine.
                for i in range(0,len(self.compData)):
                    dataList.append(
                         self.compData[i].field('COMPRESSED_DATA').tostring())

                    # If we have a column with uncompressed data then create
                    # a list of lists of the data in the coulum.  Each
                    # underlying list contains the uncompressed data for a
                    # pixel in the tile.  There are one of these lists for
                    # each tile in the image.
                    if 'UNCOMPRESSED_DATA' in self.compData.names:
                        tileUncDataList = []

                        for j in range(0,
                             len(self.compData.field('UNCOMPRESSED_DATA')[i])):
                            tileUncDataList.append(
                             self.compData.field('UNCOMPRESSED_DATA')[i][j])

                        uncompressedDataList.append(tileUncDataList)

                # Calculate the total number of elements (pixels) in the
                # resulting image data array.  Create a list of the number
                # of pixels along each axis in the image and a list of the
                # number of pixels along each axis in the compressed tile.
                nelem = 1

                for i in range(0,self._header['ZNAXIS']):
                    naxesList.append(self._header['ZNAXIS'+`i+1`])
                    tileSizeList.append(self._header['ZTILE'+`i+1`])
                    nelem = nelem * self._header['ZNAXIS'+`i+1`]

                # Create a list for the compression parameters.  The contents
                # of the list is dependent on the compression type.

                if self._header['ZCMPTYPE'] == 'RICE_1':
                    i = 1
                    blockSize = def_blockSize
                    bytePix = def_bytePix

                    while self._header.has_key('ZNAME'+`i`):
                        if self._header['ZNAME'+`i`] == 'BLOCKSIZE':
                            blockSize = self._header['ZVAL'+`i`]
                        if self._header['ZNAME'+`i`] == 'BYTEPIX':
                            bytePix = self._header['ZVAL'+`i`]
                        i += 1

                    zvalList.append(blockSize)
                    zvalList.append(bytePix)
                elif self._header['ZCMPTYPE'] == 'HCOMPRESS_1':
                    i = 1
                    hcompSmooth = def_hcompSmooth

                    while self._header.has_key('ZNAME'+`i`):
                        if self._header['ZNAME'+`i`] == 'SMOOTH':
                            hcompSmooth = self._header['ZVAL'+`i`]
                        i += 1

                    zvalList.append(hcompSmooth)

                # Treat the NOISEBIT and SCALE parameters separately because
                # they are floats instead of integers

                quantizeLevel = def_quantizeLevel

                if self._header['ZBITPIX'] < 0:
                    i = 1

                    while self._header.has_key('ZNAME'+`i`):
                        if self._header['ZNAME'+`i`] == 'NOISEBIT':
                            quantizeLevel = self._header['ZVAL'+`i`]
                        i += 1

                hcompScale = def_hcompScale

                if self._header['ZCMPTYPE'] == 'HCOMPRESS_1':
                    i = 1

                    while self._header.has_key('ZNAME'+`i`):
                        if self._header['ZNAME'+`i`] == 'SCALE':
                            hcompScale = self._header['ZVAL'+`i`]
                        i += 1

                # Create an array to hold the decompressed data.
                naxesList.reverse()
                data = np.empty(shape=naxesList,
                           dtype=_ImageBaseHDU.NumCode[self._header['ZBITPIX']])
                naxesList.reverse()

                # Call the C decompression routine to decompress the data.
                # Note that any errors in this routine will raise an
                # exception.
                status = pyfitsComp.decompressData(dataList,
                                                 self._header['ZNAXIS'],
                                                 naxesList, tileSizeList,
                                                 zScaleVals, cn_zscale,
                                                 zZeroVals, cn_zzero,
                                                 nullDvals, cn_zblank,
                                                 uncompressedDataList,
                                                 cn_uncompressed,
                                                 quantizeLevel,
                                                 hcompScale,
                                                 zvalList,
                                                 self._header['ZCMPTYPE'],
                                                 self._header['ZBITPIX'], 1,
                                                 nelem, 0.0, data)

                # Scale the data if necessary
                if (self._bzero != 0 or self._bscale != 1):
                    if self.header['BITPIX'] == -32:
                        data = np.array(data,dtype=np.float32)
                    else:
                        data = np.array(data,dtype=np.float64)

                    if cn_zblank:
                        blanks = (data == nullDvals)

                    if self._bscale != 1:
                        np.multiply(data, self._bscale, data)
                    if self._bzero != 0:
                        data += self._bzero

                    if cn_zblank:
                        data = np.where(blanks, np.nan, data)

                self.__dict__[attr] = data

            elif attr == 'compData':
                # In order to create the compressed data we will reference the
                # image data.  Referencing the image data will cause the
                # compressed data to be read from the file.
                data = self.data
            elif attr == 'header':
                # The header attribute is the header for the image data.  It
                # is not actually stored in the object dictionary.  Instead,
                # the _imageHeader is stored.  If the _imageHeader attribute
                # has already been defined we just return it.  If not, we nust
                # create it from the table header (the _header attribute).
                if not hasattr(self, '_imageHeader'):
                    # Start with a copy of the table header.
                    self._imageHeader = self._header.copy()
                    cardList = self._imageHeader.ascardlist()

                    try:
                        # Set the extension type to IMAGE
                        cardList['XTENSION'].value = 'IMAGE'
                        cardList['XTENSION'].comment = 'extension type'
                    except KeyError:
                        pass

                    # Delete cards that are related to the table.  And move
                    # the values of those cards that relate to the image from
                    # their corresponding table cards.  These include
                    # ZBITPIX -> BITPIX, ZNAXIS -> NAXIS, and ZNAXISn -> NAXISn.
                    try:
                        del cardList['ZIMAGE']
                    except KeyError:
                        pass

                    try:
                        del cardList['ZCMPTYPE']
                    except KeyError:
                        pass

                    try:
                        del cardList['ZBITPIX']
                        _bitpix = self._header['ZBITPIX']
                        cardList['BITPIX'].value = self._header['ZBITPIX']

                        if (self._bzero != 0 or self._bscale != 1):
                            if _bitpix > 16:  # scale integers to Float64
                                cardList['BITPIX'].value = -64
                            elif _bitpix > 0:  # scale integers to Float32
                                cardList['BITPIX'].value = -32

                        cardList['BITPIX'].comment = \
                                   self._header.ascardlist()['ZBITPIX'].comment
                    except KeyError:
                        pass

                    try:
                        del cardList['ZNAXIS']
                        cardList['NAXIS'].value = self._header['ZNAXIS']
                        cardList['NAXIS'].comment = \
                                 self._header.ascardlist()['ZNAXIS'].comment

                        for i in range(cardList['NAXIS'].value):
                            del cardList['ZNAXIS'+`i+1`]
                            self._imageHeader.update('NAXIS'+`i+1`,
                              self._header['ZNAXIS'+`i+1`],
                              self._header.ascardlist()['ZNAXIS'+`i+1`].comment,
                              after='NAXIS'+`i`)
                            lastNaxisCard = 'NAXIS'+`i+1`

                        if lastNaxisCard == 'NAXIS1':
                            # There is only one axis in the image data so we
                            # need to delete the extra NAXIS2 card.
                            del cardList['NAXIS2']
                    except KeyError:
                        pass

                    try:
                        for i in range(self._header['ZNAXIS']):
                            del cardList['ZTILE'+`i+1`]

                    except KeyError:
                        pass

                    try:
                        del cardList['ZPCOUNT']
                        self._imageHeader.update('PCOUNT',
                                 self._header['ZPCOUNT'],
                                 self._header.ascardlist()['ZPCOUNT'].comment)
                    except KeyError:
                        try:
                            del cardList['PCOUNT']
                        except KeyError:
                            pass

                    try:
                        del cardList['ZGCOUNT']
                        self._imageHeader.update('GCOUNT',
                                 self._header['ZGCOUNT'],
                                 self._header.ascardlist()['ZGCOUNT'].comment)
                    except KeyError:
                        try:
                            del cardList['GCOUNT']
                        except KeyError:
                            pass

                    try:
                        del cardList['ZEXTEND']
                        self._imageHeader.update('EXTEND',
                                 self._header['ZEXTEND'],
                                 self._header.ascardlist()['ZEXTEND'].comment,
                                 after = lastNaxisCard)
                    except KeyError:
                        pass

                    try:
                        del cardList['ZBLOCKED']
                        self._imageHeader.update('BLOCKED',
                                 self._header['ZBLOCKED'],
                                 self._header.ascardlist()['ZBLOCKED'].comment)
                    except KeyError:
                        pass

                    try:
                        del cardList['TFIELDS']

                        for i in range(self._header['TFIELDS']):
                            del cardList['TFORM'+`i+1`]

                            if self._imageHeader.has_key('TTYPE'+`i+1`):
                                del cardList['TTYPE'+`i+1`]

                    except KeyError:
                        pass

                    i = 1

                    while 1:
                        try:
                            del cardList['ZNAME'+`i`]
                            del cardList['ZVAL'+`i`]
                            i += 1
                        except KeyError:
                            break

                    # delete the keywords BSCALE and BZERO

                    try:
                        del cardList['BSCALE']
                    except KeyError:
                        pass

                    try:
                        del cardList['BZERO']
                    except KeyError:
                        pass

                    # Move the ZHECKSUM and ZDATASUM cards to the image header
                    # as CHECKSUM and DATASUM
                    try:
                        del cardList['ZHECKSUM']
                        self._imageHeader.update('CHECKSUM',
                                self._header['ZHECKSUM'],
                                self._header.ascardlist()['ZHECKSUM'].comment)
                    except KeyError:
                        pass

                    try:
                        del cardList['ZDATASUM']
                        self._imageHeader.update('DATASUM',
                                self._header['ZDATASUM'],
                                self._header.ascardlist()['ZDATASUM'].comment)
                    except KeyError:
                        pass

                    try:
                        del cardList['ZSIMPLE']
                        self._imageHeader.update('SIMPLE',
                                self._header['ZSIMPLE'],
                                self._header.ascardlist()['ZSIMPLE'].comment,
                                before=1)
                        del cardList['XTENSION']
                    except KeyError:
                        pass

                    try:
                        del cardList['ZTENSION']
                        if self._header['ZTENSION'] != 'IMAGE':
                            warnings.warn("ZTENSION keyword in compressed extension != 'IMAGE'")
                        self._imageHeader.update('XTENSION',
                                'IMAGE',
                                self._header.ascardlist()['ZTENSION'].comment)
                    except KeyError:
                        pass

                    # Remove the EXTNAME card if the value in the table header
                    # is the default value of COMPRESSED_IMAGE.

                    if self._header.has_key('EXTNAME') and \
                       self._header['EXTNAME'] == 'COMPRESSED_IMAGE':
                           del cardList['EXTNAME']

                    # Look to see if there are any blank cards in the table
                    # header.  If there are, there should be the same number
                    # of blank cards in the image header.  Add blank cards to
                    # the image header to make it so.
                    self._header.ascardlist().count_blanks()
                    tableHeaderBlankCount = self._header.ascardlist()._blanks
                    self._imageHeader.ascardlist().count_blanks()
                    imageHeaderBlankCount=self._imageHeader.ascardlist()._blanks

                    for i in range(tableHeaderBlankCount-imageHeaderBlankCount):
                        self._imageHeader.add_blank()

                try:
                    return self._imageHeader
                except KeyError:
                    raise AttributeError(attr)
            else:
                # Call the base class __getattr__ method.
                return BinTableHDU.__getattr__(self,attr)

            try:
                return self.__dict__[attr]
            except KeyError:
                raise AttributeError(attr)

        def __setattr__(self, attr, value):
            """
            Set an HDU attribute.
            """
            if attr == 'data':
                if (value != None) and (not isinstance(value,np.ndarray) or
                                        value.dtype.fields != None):
                    raise TypeError, "CompImageHDU data has incorrect type"

            _ExtensionHDU.__setattr__(self,attr,value)

        def _summary(self):
            """
            Summarize the HDU: name, dimensions, and formats.
            """
            class_name  = str(self.__class__)
            type  = class_name[class_name.rfind('.')+1:-2]

            # if data is touched, use data info.

            if 'data' in dir(self):
                if self.data is None:
                    _shape, _format = (), ''
                else:

                    # the shape will be in the order of NAXIS's which is the
                    # reverse of the numarray shape
                    _shape = list(self.data.shape)
                    _format = self.data.dtype.name
                    _shape.reverse()
                    _shape = tuple(_shape)
                    _format = _format[_format.rfind('.')+1:]

            # if data is not touched yet, use header info.
            else:
                _shape = ()

                for j in range(self.header['NAXIS']):
                    _shape += (self.header['NAXIS'+`j+1`],)

                _format = _ImageBaseHDU.NumCode[self.header['BITPIX']]

            return "%-10s  %-12s  %4d  %-12s  %s" % \
               (self.name, type, len(self.header.ascard), _shape, _format)

        def updateCompressedData(self):
            """
            Compress the image data so that it may be written to a file.
            """
            naxesList = []
            tileSizeList = []
            zvalList = []

            # Check to see that the imageHeader matches the image data
            if self.header.get('NAXIS',0) != len(self.data.shape) or \
               self.header.get('BITPIX',0) != \
               _ImageBaseHDU.ImgCode[self.data.dtype.name]:
                self.updateHeaderData(self.header)

            # Create lists to hold the number of pixels along each axis of
            # the image data and the number of pixels in each tile of the
            # compressed image.
            for i in range(0,self._header['ZNAXIS']):
                naxesList.append(self._header['ZNAXIS'+`i+1`])
                tileSizeList.append(self._header['ZTILE'+`i+1`])

            # Indicate if the linear scale factor is from a column, a single
            # scale value, or not given.
            if 'ZSCALE' in self.compData.names:
                cn_zscale = 1 # there is a scaled column
            elif self._header.has_key('ZSCALE'):
                cn_zscale = -1 # scale value is a constant
            else:
                cn_zscale = 0 # no scale value given so don't scale

            # Indicate if the zero point offset value is from a column, a
            # single value, or not given.
            if 'ZZERO' in self.compData.names:
                cn_zzero = 1 # there is a scaled column
            elif self._header.has_key('ZZERO'):
                cn_zzero = -1 # zero value is a constant
            else:
                cn_zzero = 0 # no zero value given so don't scale

            # Indicate if there is a UNCOMPRESSED_DATA column in the
            # compressed data table.
            if 'UNCOMPRESSED_DATA' in self.compData.names:
                cn_uncompressed = 1 # there is a uncompressed data column
            else:
                cn_uncompressed = 0 # there is no uncompressed data column

            # Create a list for the compression parameters.  The contents
            # of the list is dependent on the compression type.
            if self._header['ZCMPTYPE'] == 'RICE_1':
                i = 1
                blockSize = def_blockSize
                bytePix = def_bytePix

                while self._header.has_key('ZNAME'+`i`):
                    if self._header['ZNAME'+`i`] == 'BLOCKSIZE':
                        blockSize = self._header['ZVAL'+`i`]
                    if self._header['ZNAME'+`i`] == 'BYTEPIX':
                        bytePix = self._header['ZVAL'+`i`]
                    i += 1

                zvalList.append(blockSize)
                zvalList.append(bytePix)
            elif self._header['ZCMPTYPE'] == 'HCOMPRESS_1':
                i = 1
                hcompSmooth = def_hcompSmooth

                while self._header.has_key('ZNAME'+`i`):
                    if self._header['ZNAME'+`i`] == 'SMOOTH':
                        hcompSmooth = self._header['ZVAL'+`i`]
                    i += 1

                zvalList.append(hcompSmooth)

            # Treat the NOISEBIT and SCALE parameters separately because
            # they are floats instead of integers

            quantizeLevel = def_quantizeLevel

            if self._header['ZBITPIX'] < 0:
                i = 1

                while self._header.has_key('ZNAME'+`i`):
                    if self._header['ZNAME'+`i`] == 'NOISEBIT':
                        quantizeLevel = self._header['ZVAL'+`i`]
                    i += 1

            hcompScale = def_hcompScale

            if self._header['ZCMPTYPE'] == 'HCOMPRESS_1':
                i = 1

                while self._header.has_key('ZNAME'+`i`):
                    if self._header['ZNAME'+`i`] == 'SCALE':
                        hcompScale = self._header['ZVAL'+`i`]
                    i += 1

            # Indicate if the null value is a constant or if no null value
            # is provided.
            if self._header.has_key('ZBLANK'):
                cn_zblank = -1 # null value is a constant
                zblank = self._header['ZBLANK']
            else:
                cn_zblank = 0 # no null value so don't use
                zblank = 0

            if self._header.has_key('BSCALE') and self.data.dtype.str[1] == 'f':
                # If this is scaled data (ie it has a BSCALE value and it is
                # floating point data) then pass in the BSCALE value so the C
                # code can unscale it before compressing.
                cn_bscale = self._header['BSCALE']
            else:
                cn_bscale = 1.0

            if self._header.has_key('BZERO') and self.data.dtype.str[1] == 'f':
                cn_bzero = self._header['BZERO']
            else:
                cn_bzero = 0.0

            # put data in machine native byteorder on little endian machines

            byteswapped = False

            if self.data.dtype.str[0] == '>' and sys.byteorder == 'little':
                byteswapped = True
                self.data = self.data.byteswap(True)
                self.data.dtype = self.data.dtype.newbyteorder('<')

            try:
                # Compress the data.
                status, compDataList, scaleList, zeroList, uncompDataList =  \
                   pyfitsComp.compressData(self.data,
                                           self._header['ZNAXIS'],
                                           naxesList, tileSizeList,
                                           cn_zblank, zblank,
                                           cn_bscale, cn_bzero, cn_zscale,
                                           cn_zzero, cn_uncompressed,
                                           quantizeLevel,
                                           hcompScale,
                                           zvalList,
                                           self._header['ZCMPTYPE'],
                                           self.header['BITPIX'], 1,
                                           self.data.size)
            finally:
                # if data was byteswapped return it to its original order

                if byteswapped:
                    self.data = self.data.byteswap(True)
                    self.data.dtype = self.data.dtype.newbyteorder('>')

            if status != 0:
                raise RuntimeError, 'Unable to write compressed image'

            # Convert the compressed data from a list of byte strings to
            # an array and set it in the COMPRESSED_DATA field of the table.
            colDType = 'uint8'

            if self._header['ZCMPTYPE'] == 'PLIO_1':
                colDType = 'i2'

            for i in range(0,len(compDataList)):
                self.compData[i].setfield('COMPRESSED_DATA',np.fromstring(
                                                            compDataList[i],
                                                            dtype=colDType))

            # Convert the linear scale factor values from a list to an
            # array and set it in the ZSCALE field of the table.
            if cn_zscale > 0:
                for i in range (0,len(scaleList)):
                    self.compData[i].setfield('ZSCALE',scaleList[i])

            # Convert the zero point offset values from a list to an
            # array and set it in the ZZERO field of the table.
            if cn_zzero > 0:
                for i in range (0,len(zeroList)):
                    self.compData[i].setfield('ZZERO',zeroList[i])

            # Convert the uncompressed data values from a list to an
            # array and set it in the UNCOMPRESSED_DATA field of the table.
            if cn_uncompressed > 0:
                for i in range(0,len(uncompDataList)):
                    self.compData[i].setfield('UNCOMPRESSED_DATA',
                                              uncompDataList[i])

            # Update the table header cards to match the compressed data.
            self.updateHeader()

        def updateHeader(self):
            """
            Update the table header cards to match the compressed data.
            """

            from pyfits.core import _FormatP

            # Get the _heapsize attribute to match the data.
            self.compData._scale_back()

            # Check that TFIELDS and NAXIS2 match the data.
            self._header['TFIELDS'] = self.compData._nfields
            self._header['NAXIS2'] = self.compData.shape[0]

            # Calculate PCOUNT, for variable length tables.
            _tbsize = self._header['NAXIS1']*self._header['NAXIS2']
            _heapstart = self._header.get('THEAP', _tbsize)
            self.compData._gap = _heapstart - _tbsize
            _pcount = self.compData._heapsize + self.compData._gap

            if _pcount > 0:
                self._header['PCOUNT'] = _pcount

            # Update TFORM for variable length columns.
            for i in range(self.compData._nfields):
                if isinstance(self.compData._coldefs.formats[i], _FormatP):
                    key = self._header['TFORM'+`i+1`]
                    self._header['TFORM'+`i+1`] = key[:key.find('(')+1] + \
                                              `hdu.compData.field(i)._max` + ')'
            # Insure that for RICE_1 that the BLOCKSIZE and BYTEPIX cards
            # are present and set to the hard coded values used by the
            # compression algorithm.
            if self._header['ZCMPTYPE'] == 'RICE_1':
                self._header.update('ZNAME1', 'BLOCKSIZE',
                                    'compression block size',
                                    after='ZCMPTYPE')
                self._header.update('ZVAL1', def_blockSize,
                                    'pixels per block',
                                    after='ZNAME1')

                self._header.update('ZNAME2', 'BYTEPIX',
                                    'bytes per pixel (1, 2, 4, or 8)',
                                    after='ZVAL1')

                if self._header['ZBITPIX'] == 8:
                    bytepix = 1
                elif self._header['ZBITPIX'] == 16:
                    bytepix = 2
                else:
                    bytepix = def_bytePix

                self._header.update('ZVAL2', bytepix,
                                    'bytes per pixel (1, 2, 4, or 8)',
                                        after='ZNAME2')

        def scale(self, type=None, option="old", bscale=1, bzero=0):
            """
            Scale image data by using ``BSCALE`` and ``BZERO``.

            Calling this method will scale `self.data` and update the
            keywords of ``BSCALE`` and ``BZERO`` in `self._header` and
            `self._imageHeader`.  This method should only be used
            right before writing to the output file, as the data will
            be scaled and is therefore not very usable after the call.

            Parameters
            ----------

            type : str, optional
                destination data type, use a string representing a numpy
                dtype name, (e.g. ``'uint8'``, ``'int16'``, ``'float32'``
                etc.).  If is `None`, use the current data type.

            option : str, optional
                how to scale the data: if ``"old"``, use the original
                ``BSCALE`` and ``BZERO`` values when the data was
                read/created. If ``"minmax"``, use the minimum and maximum
                of the data to scale.  The option will be overwritten
                by any user-specified bscale/bzero values.

            bscale, bzero : int, optional
                user specified ``BSCALE`` and ``BZERO`` values.
            """

            if self.data is None:
                return

            # Determine the destination (numpy) data type
            if type is None:
                type = _ImageBaseHDU.NumCode[self._bitpix]
            _type = getattr(np, type)

            # Determine how to scale the data
            # bscale and bzero takes priority
            if (bscale != 1 or bzero !=0):
                _scale = bscale
                _zero = bzero
            else:
                if option == 'old':
                    _scale = self._bscale
                    _zero = self._bzero
                elif option == 'minmax':
                    if isinstance(_type, np.floating):
                        _scale = 1
                        _zero = 0
                    else:

                        # flat the shape temporarily to save memory
                        dims = self.data.shape
                        self.data.shape = self.data.size
                        min = np.minimum.reduce(self.data)
                        max = np.maximum.reduce(self.data)
                        self.data.shape = dims

                        if _type == np.uint8:  # uint8 case
                            _zero = min
                            _scale = (max - min) / (2.**8 - 1)
                        else:
                            _zero = (max + min) / 2.

                            # throw away -2^N
                            _scale = (max - min) / (2.**(8*_type.bytes) - 2)

            # Do the scaling
            if _zero != 0:
                self.data += -_zero # 0.9.6.3 to avoid out of range error for
                                    # BZERO = +32768

            if _scale != 1:
                self.data /= _scale

            if self.data.dtype.type != _type:
                self.data = np.array(np.around(self.data), dtype=_type) #0.7.7.1
            #
            # Update the BITPIX Card to match the data
            #
            self.header['BITPIX']=_ImageBaseHDU.ImgCode[self.data.dtype.name]

            #
            # Update the table header to match the scaled data
            #
            self.updateHeaderData(self.header)

            #
            # Set the BSCALE/BZERO header cards
            #
            if _zero != 0:
                self.header.update('BZERO', _zero)
            else:
                del self.header['BZERO']

            if _scale != 1:
                self.header.update('BSCALE', _scale)
            else:
                del self.header['BSCALE']

        def _calculate_datasum(self, blocking):
            """
            Calculate the value for the ``DATASUM`` card in the HDU.
            """
            if self.__dict__.has_key('data') and self.data != None:
                # We have the data to be used.
                return self._calculate_datasum_from_data(self.compData, blocking)
            else:
                # This is the case where the data has not been read from the
                # file yet.  We can handle that in a generic manner so we do
                # it in the base class.  The other possibility is that there
                # is no data at all.  This can also be handled in a gereric
                # manner.
                return super(CompImageHDU,self)._calculate_datasum(blocking)


else:
    # Compression object library failed to import so define it as an
    # empty BinTableHDU class.  This way the code will run when the object
    # library is not present.

    class CompImageHDU(BinTableHDU):
        pass
