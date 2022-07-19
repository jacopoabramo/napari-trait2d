import numpy as np
import warnings
from scipy.ndimage import gaussian_laplace
from scipy.signal import convolve2d
from skimage.feature import peak_local_max
from napari_trait2d.common import Point, TRAIT2DParams

def get_patch(frame: np.ndarray, point: Point, patch_size: int, full_search: bool = False) -> np.ndarray:
    """ Creates a patch of the specified input frame to use for radial symmetry center calculation of a particle
    on a specified point.

    Args:
        frame (np.ndarray): input frame
        point (Point): coordinates of the point to use for radial symmetry centre search.
        patch_size (int): width/height of the region to search
        full_search (bool, optional): if True, search radius will be extended to the overall specified patch_size. Defaults to False.

    Returns:
        np.ndarray: _description_
    """
    x_shape, y_shape = frame.shape
    data = np.zeros((patch_size, patch_size))

    #start point
    start_x, start_y = int(point.x - patch_size/2), int(point.y - patch_size/2)

    #end point
    end_x, end_y = int(point.x + patch_size/2), int(point.y + patch_size/2)

    x_0, x_1 = 0, patch_size
    y_0, y_1 = 0, patch_size

    # define ROI coordinates
    if not full_search:
        if start_x < 0:
            start_x = 0
            x_0 = int(patch_size/2 - point.x)
            
        if start_y < 0:
            start_y = 0
            y_0 = int(patch_size/2 - point.y) 
            
        if end_x > x_shape:
            end_x = x_shape
            x_1 = int(x_shape - point.x + patch_size/2)

        if end_y > y_shape:
            end_y = y_shape
            y_1 = int(y_shape - point.y + patch_size/2)
    else:
        if start_x<0:
            start_x = 0
            end_x = patch_size
            
        if start_y < 0:
            start_y = 0
            end_y = patch_size
            
        if end_x > x_shape:
            end_x = x_shape
            start_x = x_shape - patch_size

        if end_y > y_shape:
            end_y = y_shape
            start_y = y_shape - patch_size

    data[x_0 : x_1, y_0 : y_1] = frame[start_x : end_x, start_y : end_y]

    return data

def ls_radial_center_fit(m: np.ndarray, b: np.ndarray, w: np.ndarray):
    '''
    least squares solution to determine the radial symmetry center
    '''
    wm2p1 = np.divide(w, (np.multiply(m, m)+1))
    sw = np.sum(wm2p1)
    smmw = np.sum(np.multiply(np.multiply(m, m), wm2p1))
    smw = np.sum(np.multiply(m, wm2p1))
    smbw = np.sum(np.multiply(np.multiply(m, b), wm2p1))
    sbw = np.sum(np.multiply(b, wm2p1))
    det = smw*smw - smmw*sw
    xc = (smbw*sw - smw*sbw)/det  # relative to image center
    yc = (smbw*smw - smmw*sbw)/det  # relative to image center

    return xc, yc

def spot_enhancing_filter(img: np.ndarray, sigma: int, threshold: float) -> tuple:
    '''
    Spot enhancing filter implementation.
    '''
    img_filtered = img*np.ones(img.shape)

    # calculate laplacian of gaussian
    img_sef1 = gaussian_laplace(img_filtered, sigma)
    
    # remove negative values keeping the proportion b/w pixels
    img_sef1 = abs(img_sef1 - np.abs(np.max(img_sef1)))

    # thresholding
    img_threshold = np.mean(img_sef1) + threshold*np.std(img_sef1)  # calculate threshold value
    img_sef = np.copy(img_sef1)  # copy the image
    img_sef[img_sef < img_threshold] = 0  # thresholding

    return img_sef

def radial_symmetry_centre(img: np.ndarray) -> Point:
    '''
    Calculates the center of a 2D intensity distribution (calculation of radial symmetry centers)  

    '''
    # GRID
    # number of grid points
    Ny, Nx = img.shape

    # for x
    val = int((Nx-1)/2.0-0.5)
    xm_onerow = np.asarray(range(-val, val+1))
    xm = np.ones((Nx-1, Nx-1))*xm_onerow

    # for y
    val = int((Ny-1)/2.0-0.5)
    ym_onerow = np.asarray(range(-val, val+1))
    ym = (np.ones((Ny-1, Ny-1))*ym_onerow).transpose()

    # derivate along 45-degree shidted coordinates

    dIdu = np.subtract(img[0:Nx-1, 1:Ny].astype(float), img[1:Nx, 0:Ny-1].astype(float))
    dIdv = np.subtract(img[0:Nx-1, 0:Ny-1].astype(float), img[1:Nx, 1:Ny].astype(float))

    # smoothing
    filter_core = np.ones((3, 3))/9
    fdu = convolve2d(dIdu, filter_core, mode='same', boundary='fill', fillvalue=0)
    fdv = convolve2d(dIdv, filter_core, mode='same', boundary='fill', fillvalue=0)

    dImag2 = np.multiply(fdu, fdu)+np.multiply(fdv, fdv)

    # slope of the gradient
    m = np.divide(-(fdv + fdu), (fdu-fdv))

    # if some of values in m is NaN
    m[np.isnan(m)] = np.divide(dIdv+dIdu, dIdu-dIdv)[np.isnan(m)]

    # if some of values in m is still NaN
    m[np.isnan(m)] = 0

    # if some of values in m  are inifinite

    m[np.isinf(m)] = 10*np.max(m)

    # shortband b
    b = ym - m*xm

    # weighting
    sdI2 = np.sum(dImag2)

    xcentroid = np.sum(np.multiply(dImag2, xm))/sdI2
    ycentroid = np.sum(np.multiply(dImag2, ym))/sdI2
    w = np.divide(dImag2, np.sqrt(np.multiply((xm-xcentroid), (xm-xcentroid))+np.multiply((ym-ycentroid), (ym-ycentroid))))

    # least square minimisation
    xc, yc = ls_radial_center_fit(m, b, w)

    # output replated to upper left coordinate
    x = xc + (Nx+1)/2  # xc + (Nx+1)/2
    y = yc + (Ny+1)/2  # yc + (Ny+1)/2

    return Point(x, y)

def detect(frame: np.ndarray, params: TRAIT2DParams) -> list:
    '''
    Detect vesicles in input image "frame"
    '''
    # Spot enhancing filter
    img_sef = spot_enhancing_filter(frame, params.SEF_sigma, params.SEF_threshold)

    # find local maximum
    # min distance between peaks and threshold_rel - min value of the peak - in relation to the max value
    peak_coordinates = [Point(x, y) for x, y in peak_local_max(img_sef, min_distance=params.SEF_min_dist, threshold_rel=params.SEF_min_peak)]

    coordinates = []
    for point in peak_coordinates:
        # radial symmetry centers
        subpix = radial_symmetry_centre(get_patch(frame, point, params.patch_size))

        # check that the centre is inside of the spot
        if subpix < Point(params.patch_size, params.patch_size) and subpix >= Point(0, 0):
            coordinates.append(
                Point(subpix.x + int(point.x - params.patch_size/2), subpix.y + int(point.y - params.patch_size/2))
            )
    return coordinates