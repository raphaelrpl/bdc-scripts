# Python Native
from datetime import datetime
import os
import time
# 3rdparty
from numpngw import write_png
from rasterio import Affine, MemoryFile
from rasterio.warp import reproject, Resampling
import numpy
import rasterio
# BDC Scripts
from bdc_db.models import Collection
from bdc_scripts.config import Config


def merge(warped_datacube, tile_id, assets, cols, rows, period, **kwargs):
    datacube = kwargs['datacube']
    nodata = kwargs.get('nodata', None)
    xmin = kwargs.get('xmin')
    ymax = kwargs.get('ymax')
    dataset = kwargs.get('dataset')
    band = assets[0]['band']
    merge_date = kwargs.get('date')
    resx, resy = kwargs.get('resx'), kwargs.get('resy')

    formatted_date = datetime.strptime(merge_date, '%Y-%m-%d').strftime('%Y%m%d')

    srs = kwargs.get('srs', '+proj=aea +lat_1=10 +lat_2=-40 +lat_0=0 +lon_0=-50 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs')

    merge_name = '{}-{}-{}_M_{}_{}'.format(dataset, tile_id, formatted_date, len(assets), band)

    merged_file = os.path.join(Config.DATA_DIR, 'Repository/collections/cubes/{}/{}/{}/{}.tif'.format(warped_datacube, tile_id, period, merge_name))

    transform = Affine(resx, 0, xmin, 0, -resy, ymax)

    # Quality band is resampled by nearest, other are bilinear
    if band == 'quality':
        resampling = Resampling.nearest
    else:
        resampling = Resampling.bilinear

    # For all files
    src = rasterio.open(assets[0]['link'])
    raster = numpy.zeros((rows, cols,), dtype=src.profile['dtype'])
    rasterMerge = numpy.zeros((rows, cols,), dtype=src.profile['dtype'])
    rasterMask = numpy.ones((rows, cols,), dtype=src.profile['dtype'])
    count = 0
    template = None
    for asset in assets:
        count += 1
        with rasterio.Env(CPL_CURL_VERBOSE=False):
            with rasterio.open(asset['link']) as src:
                kwargs = src.meta.copy()
                kwargs.update({
                    'crs': srs,
                    'transform': transform,
                    'width': cols,
                    'height': rows
                })

                if src.profile['nodata'] is not None:
                    nodata = src.profile['nodata']
                elif nodata is None:
                    nodata = 0

                kwargs.update({
                    'nodata': nodata
                })

                with MemoryFile() as mem_file:
                    with mem_file.open(**kwargs) as dst:
                        reproject(
                            source=rasterio.band(src, 1),
                            destination=raster,
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=srs,
                            src_nodata=nodata,
                            dst_nodata=nodata,
                            resampling=resampling)
                        rasterMerge = rasterMerge + raster*rasterMask
                        rasterMask[raster != nodata] = 0
                        if template is None:
                            template = dst.profile

    # Evaluate cloud cover and efficacy if band is quality
    efficacy = 0
    cloudratio = 100
    if band == 'quality':
        rasterMerge, efficacy, cloudratio = getMask(rasterMerge, dataset)
        template.update({'dtype': 'uint8'})

    target_dir = os.path.dirname(merged_file)
    os.makedirs(target_dir, exist_ok=True)

    with rasterio.open(merged_file, 'w', **template) as merge_dataset:
        merge_dataset.write_band(1, rasterMerge)

    return dict(
        band=band,
        file=merged_file,
        efficacy=efficacy,
        cloudratio=cloudratio,
        dataset=dataset,
        resolution=resx,
        period=period,
        date='{}{}'.format(merge_date, dataset),
        datacube=datacube,
        tile_id=tile_id,
        warped_datacube=warped_datacube
    )


def blend(activity):
    # Assume that it contains a band and quality band
    numscenes = len(activity['scenes'])

    band = activity['band']

    # Get basic information (profile) of input files
    keys = list(activity['scenes'].keys())

    filename = activity['scenes'][keys[0]]['ARDfiles'][band]

    with rasterio.open(filename) as src:
        profile = src.profile
        tilelist = list(src.block_windows())

    # Order scenes based in efficacy/resolution
    mask_tuples = []

    for key in activity['scenes']:
        scene = activity['scenes'][key]
        efficacy = int(scene['efficacy'])
        resolution = int(scene['resolution'])
        mask_tuples.append((100. * efficacy / resolution, key))

    # Open all input files and save the datasets in two lists, one for masks and other for the current band.
    # The list will be ordered by efficacy/resolution
    masklist = []
    bandlist = []
    for m in sorted(mask_tuples, reverse=True):
        key = m[1]
        efficacy = m[0]
        scene = activity['scenes'][key]

        filename = scene['ARDfiles']['quality']
        try:
            masklist.append(rasterio.open(filename))
        except BaseException as e:
            raise IOError('FileError while opening {} - {}'.format(filename, e))

        filename = scene['ARDfiles'][band]

        try:
            bandlist.append(rasterio.open(filename))
        except BaseException as e:
            raise IOError('FileError while opening {} - {}'.format(filename, e))

    # Build the raster to store the output images.
    width = profile['width']
    height = profile['height']

    # STACK will be generated in memory
    stackRaster = numpy.zeros((height, width), dtype=profile['dtype'])

    datacube = activity.get('datacube')
    period = activity.get('period')
    tile_id = activity.get('tile_id')
    output_name = '{}-{}-{}-{}.tif'.format(datacube, tile_id, period, band)
    #
    # MEDIAN will be generated in local disk
    medianfile = os.path.join(Config.DATA_DIR, 'Repository/collections/cubes/{}/{}/{}/{}'.format(
        datacube, tile_id, period, output_name))

    os.makedirs(os.path.dirname(medianfile), exist_ok=True)

    mediandataset = rasterio.open(medianfile, 'w', **profile)
    count = 0
    for _, window in tilelist:
        # Build the stack to store all images as a masked array. At this stage the array will contain the masked data
        stackMA = numpy.ma.zeros((numscenes, window.height, window.width), dtype=numpy.uint16)

        # notdonemask will keep track of pixels that have not been filled in each step
        notdonemask = numpy.ones(shape=(window.height, window.width), dtype=numpy.bool_)

        # For all pair (quality,band) scenes
        for order in range(numscenes):
            ssrc = bandlist[order]
            msrc = masklist[order]
            raster = ssrc.read(1,window=window)
            mask = msrc.read(1,window=window)
            mask[mask != 1] = 0
            bmask = mask.astype(numpy.bool_)

            # Use the mask to mark the fill (0) and cloudy (2) pixels
            stackMA[order] = numpy.ma.masked_where(numpy.invert(bmask), raster)

            # Evaluate the STACK image
            # Pixels that have been already been filled by previous rasters will be masked in the current raster
            todomask = notdonemask * bmask
            notdonemask = notdonemask * numpy.invert(bmask)
            stackRaster[window.row_off:window.row_off + window.height, window.col_off:window.col_off + window.width] += (raster * todomask).astype(profile['dtype'])

        medianRaster = numpy.ma.median(stackMA,axis=0).data
        mediandataset.write(medianRaster.astype(profile['dtype']), window=window, indexes=1)
        count += 1

    # Close all input dataset
    for order in range(numscenes):
        bandlist[order].close()
        masklist[order].close()

    # Evaluate cloudcover
    cloudcover = 100. * ((height * width - numpy.count_nonzero(stackRaster)) / (height * width))
    #
    # # Close and upload the MEDIAN dataset
    mediandataset.close()
    mediandataset = None
    # key = activity['MEDIANfile']

    # Create and upload the STACK dataset
    # with MemoryFile() as memfile:
    #     with memfile.open(**profile) as dataset:
    #         dataset.write_band(1,stackRaster)
    #         if self.verbose > 2: print ('blend - STACK profile',dataset.profile)

    #     key = activity['STACKfile']
    #     if self.verbose > 1: print('blend - key STACKfile',key)
    #     self.S3client.upload_fileobj(memfile, Bucket=self.bucket_name, Key=key, ExtraArgs={'ACL': 'public-read'})

    activity['efficacy'] = 0
    activity['cloudratio'] = 100
    activity['blends'] = {"MEDIAN": medianfile}

    return activity


def publish_datacube(bands, datacube, tile_id, period, scenes):
    for composite_function in ['MEDIAN']:  # ,'STACK']:
        quick_look_name = '{}-{}-{}_{}'.format(datacube, tile_id, period, composite_function)
        quick_look_file = os.path.join(
            Config.DATA_DIR,
            'Repository/collections/cubes/{}/{}/{}/{}'.format(
                datacube, tile_id, period, quick_look_name
            )
        )

        ql_files = []
        for band in bands:
            ql_files.append(scenes[band][composite_function])

        generate_quick_look(quick_look_file, ql_files)


def publish_merge(bands, datacube, dataset, tile_id, period, date, scenes):
    quick_look_name = '{}-{}-{}'.format(dataset, tile_id, date)
    quick_look_file = os.path.join(
        Config.DATA_DIR,
        'Repository/collections/cubes/{}/{}/{}/{}'.format(
            datacube, tile_id, period, quick_look_name
        )
    )

    ql_files = []
    for band in bands:
        ql_files.append(scenes['ARDfiles'][band])

    generate_quick_look(quick_look_file, ql_files)


def generate_quick_look(file_path, qlfiles):
    with rasterio.open(qlfiles[0]) as src:
        profile = src.profile

    numlin = 768
    numcol = int(float(profile['width'])/float(profile['height'])*numlin)
    image = numpy.ones((numlin,numcol,len(qlfiles),), dtype=numpy.uint8)
    pngname = '{}.png'.format(file_path)

    nb = 0
    for file in qlfiles:
        with rasterio.open(file) as src:
            raster = src.read(1, out_shape=(numlin, numcol))

            # Rescale to 0-255 values
            nodata = raster <= 0
            if raster.min() != 0 or raster.max() != 0:
                raster = raster.astype(numpy.float32)/10000.*255.
                raster[raster > 255] = 255
            image[:, :, nb] = raster.astype(numpy.uint8) * numpy.invert(nodata)
            nb += 1

    write_png(pngname, image, transparent=(0, 0, 0))
    return pngname


def getMask(raster, dataset):
    from skimage import morphology
    # Output Cloud Mask codes
    # 0 - fill
    # 1 - clear data
    # 0 - cloud
    if dataset == 'LC8SR':
        # Input pixel_qa codes
        fill    = 1 				# warped images have 0 as fill area
        terrain = 2					# 0000 0000 0000 0010
        radsat  = 4+8				# 0000 0000 0000 1100
        cloud   = 16+32+64			# 0000 0000 0110 0000
        shadow  = 128+256			# 0000 0001 1000 0000
        snowice = 512+1024			# 0000 0110 0000 0000
        cirrus  = 2048+4096			# 0001 1000 0000 0000

        unique, counts = numpy.unique(raster, return_counts=True)

        # Start with a zeroed image imagearea
        imagearea = numpy.zeros(raster.shape, dtype=numpy.bool_)
        # Mark with True the pixels that contain valid data
        imagearea = imagearea + raster > fill
        # Create a notcleararea mask with True where the quality criteria is as follows
        notcleararea = 	(raster & radsat > 4) + \
                    (raster & cloud > 64) + \
                    (raster & shadow > 256) + \
                    (raster & snowice > 512) + \
                    (raster & cirrus > 4096)

        strel = morphology.selem.square(6)
        notcleararea = morphology.binary_dilation(notcleararea,strel)
        morphology.remove_small_holes(notcleararea, area_threshold=80, connectivity=1, in_place=True)

        # Clear area is the area with valid data and with no Cloud or Snow
        cleararea = imagearea * numpy.invert(notcleararea)
        # Code the output image rastercm as the output codes
        rastercm = (2*notcleararea + cleararea).astype(numpy.uint8)

    elif dataset == 'MOD13Q1' or dataset == 'MYD13Q1':
        # MOD13Q1 Pixel Reliability !!!!!!!!!!!!!!!!!!!!
        # Note that 1 was added to this image in downloadModis because of warping
        # Rank/Key Summary QA 		Description
        # -1 		Fill/No Data 	Not Processed
        # 0 		Good Data 		Use with confidence
        # 1 		Marginal data 	Useful, but look at other QA information
        # 2 		Snow/Ice 		Target covered with snow/ice
        # 3 		Cloudy 			Target not visible, covered with cloud
        fill    = 0 	# warped images have 0 as fill area
        lut = numpy.array([0,1,1,2,2],dtype=numpy.uint8)
        rastercm = numpy.take(lut,raster+1).astype(numpy.uint8)

    elif dataset == 'S2SR_SEN28':
        # S2 sen2cor - The generated classification map is specified as follows:
        # Label Classification
        #  0		NO_DATA
        #  1		SATURATED_OR_DEFECTIVE
        #  2		DARK_AREA_PIXELS
        #  3		CLOUD_SHADOWS
        #  4		VEGETATION
        #  5		NOT_VEGETATED
        #  6		WATER
        #  7		UNCLASSIFIED
        #  8		CLOUD_MEDIUM_PROBABILITY
        #  9		CLOUD_HIGH_PROBABILITY
        # 10		THIN_CIRRUS
        # 11		SNOW
        # 0 1 2 3 4 5 6 7 8 9 10 11
        lut = numpy.array([0,0,2,2,1,1,1,2,2,2,1, 1],dtype=numpy.uint8)
        rastercm = numpy.take(lut,raster).astype(numpy.uint8)

    elif dataset == 'CB4_AWFI' or dataset == 'CB4_MUX':
        # Key 		Summary QA 		Description
        # 0 		Fill/No Data 	Not Processed
        # 127 		Good Data 		Use with confidence
        # 255 		Cloudy 			Target not visible, covered with cloud
        fill = 0 		# warped images have 0 as fill area
        lut = numpy.zeros(256,dtype=numpy.uint8)
        lut[127] = 1
        lut[255] = 2
        rastercm = numpy.take(lut,raster).astype(numpy.uint8)

    unique, counts = numpy.unique(rastercm, return_counts=True)

    totpix   = rastercm.size
    fillpix  = numpy.count_nonzero(rastercm==0)
    clearpix = numpy.count_nonzero(rastercm==1)
    cloudpix = numpy.count_nonzero(rastercm==2)
    imagearea = clearpix+cloudpix
    clearratio = 0
    cloudratio = 100
    if imagearea != 0:
        clearratio = round(100.*clearpix/imagearea,1)
        cloudratio = round(100.*cloudpix/imagearea,1)
    efficacy = round(100.*clearpix/totpix,2)

    return rastercm,efficacy,cloudratio
