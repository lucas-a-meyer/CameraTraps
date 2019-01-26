#
# ocr_sandbox.py
#
# sandbox for experimenting with using OCR to pull metadata from camera trap images
#

#%% Constants and imports

import os
import pytesseract
import warnings
import glob
import cv2
import numpy as np
import ntpath
from iptcinfo3 import IPTCInfo # pip install IPTCInfo3
from PIL import Image
import logging

import write_html_image_list        

# ignoring all "PIL cannot read EXIF metainfo for the images" warnings
warnings.filterwarnings("ignore", "(Possibly )?corrupt EXIF data", UserWarning)
# Metadata Warning, tag 256 had too many entries: 42, expected 1
warnings.filterwarnings("ignore", "Metadata warning", UserWarning)

baseDir = r'd:\temp\camera_trap_images_for_metadata_extraction'


#%% Support functions

from PIL.ExifTags import TAGS
def get_exif(img):
    
    ret = {}
    if isinstance(img,str):
        img = Image.open(img)
    info = img._getexif()
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        ret[decoded] = value
    return ret


#%% Load some images, pull EXIF and IPTC data

images = []
exifInfo = []
iptcInfo = []

logger = logging.getLogger('iptcinfo')
logger.disabled = True

imageFileNames = glob.glob(os.path.join(baseDir,'*.jpg'))

for fn in imageFileNames:
    
    img = Image.open(fn)
    exifInfo.append(get_exif(img))
    images.append(img)
    iptc = []
    try:
        iptc = IPTCInfo(fn)                
    except:
        pass
    iptcInfo.append(iptc)        


#%% Crop images

# This will be a list of two-element lists (image top, image bottom)
imageRegions = []
    
imageCropFraction = [0.045 , 0.045]

# image = images[0]
for image in images:
    
    exif_data = image._getexif()
    h = image.height
    w = image.width
    
    cropHeightTop = round(imageCropFraction[0] * h)
    cropHeightBottom = round(imageCropFraction[1] * h)
    
    # l,t,r,b
    #
    # 0,0 is upper-left
    topCrop = image.crop([0,0,w,cropHeightTop])
    bottomCrop = image.crop([0,h-cropHeightBottom,w,h])
    imageRegions.append([topCrop,bottomCrop])    


#%% Close-crop around the text, return a revised image and success metric
    
def crop_to_solid_region(image):
    """   
    croppedImage,pSuccess = crop_to_solid_region(image):

    The success metric is totally arbitrary right now, but is a placeholder.
    """
           
    # Our tolerance around the median value
    rangeWidth = 2
    
    analysisImage = image.astype('uint8')     
    analysisImage = cv2.medianBlur(analysisImage,3) 
    pixelValues = analysisImage.flatten()
    counts = np.bincount(pixelValues)
    backgroundValue = int(np.argmax(counts))
    
    # Did we find a sensible mode that looks like a background value?
    backgroundValueCount = int(np.max(counts))
    pBackGroundValue = backgroundValueCount / np.sum(counts)
    
    # This looks very scientific, right?
    if (pBackGroundValue < 0.3):
        pSuccess = 0.0
    else:
        pSuccess = 1.0
        
    analysisImage = cv2.inRange(analysisImage,
                                backgroundValue-rangeWidth,backgroundValue+rangeWidth)
    
    # analysisImage = cv2.blur(analysisImage, (3,3))
    # analysisImage = cv2.medianBlur(analysisImage,5) 
    # analysisImage = cv2.Canny(analysisImage,100,100)
    # imagePil = Image.fromarray(analysisImage); imagePil
    
    # Using row heuristics
    if True:
        
        h = analysisImage.shape[0]
        w = analysisImage.shape[1]
        
        minX = 0
        minY = -1
        maxX = w
        maxY = -1
        
        for y in range(h):
            rowCount = 0
            for x in range(w):
                if analysisImage[y][x] > 0:
                    rowCount += 1
            rowFraction = rowCount / w
            if rowFraction > 0.75:
                if minY == -1:
                    minY = y
                maxY = y
        
        x = minX
        y = minY
        w = maxX-minX
        h = maxY-minY
        
        x = minX
        y = minY
        w = maxX-minX
        h = maxY-minY
    
    # Crop the image
    croppedImage = image[y:y+h,x:x+w]
      
    # imagePil = Image.fromarray(croppedImage); imagePil
    
    return croppedImage,pSuccess
    
    
#%% Go to OCR-town

imageText = []
processedRegions = []
    
# iImage = 3; iRegion = 1; regionSet = imageRegions[iImage]; region = regionSet[iRegion]

pCropSuccessThreshold = 0.5
borderWidth = 10        
minTextLength = 4

for iImage,regionSet in enumerate(imageRegions):
    
    regionText = []
    processedRegionsThisImage = []
        
    for iRegion,region in enumerate(regionSet):

        # text = pytesseract.image_to_string(region)

        # pil --> cv2        
        image = np.array(region) 
        image = image[:, :, ::-1].copy()         
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # image = cv2.medianBlur(image, 3)        
        # image = cv2.erode(image, None, iterations=2)
        # image = cv2.dilate(image, None, iterations=4)
        # image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        # image = cv2.blur(image, (3,3))
        # image = cv2.copyMakeBorder(image,10,10,10,10,cv2.BORDER_CONSTANT,value=[0,0,0])
        
        image,pSuccess = crop_to_solid_region(image)
        
        if pSuccess < pCropSuccessThreshold:
            continue
        
        # For some reason, tesseract doesn't like characters really close to the edge
        image = cv2.copyMakeBorder(image,borderWidth,borderWidth,borderWidth,borderWidth,
                                   cv2.BORDER_CONSTANT,value=[0,0,0])
        
        imagePil = Image.fromarray(image)
        processedRegionsThisImage.append(imagePil)
        # text = pytesseract.image_to_string(imagePil, lang='eng')
        # https://github.com/tesseract-ocr/tesseract/wiki/Command-Line-Usage
        
        # psm 6: "assume a single uniform block of text"
        #
        text = pytesseract.image_to_string(imagePil, lang='eng', config='--psm 6') 
        
        text = text.replace('\n', ' ').replace('\r', '').strip()

        regionText.append(text)
        
        if len(text) > minTextLength:
            print('Image {} ({}), region {}:\n{}\n'.format(iImage,imageFileNames[iImage],
                  iRegion,text))

    # ...for each cropped region
    
    imageText.append(regionText)
    processedRegions.append(processedRegionsThisImage)
    
# ...for each image
    
    
#%% Write results
 
def resizeImage(img):
    
    targetWidth = 800
    wpercent = (targetWidth / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    imgResized = img.resize((targetWidth, hsize), Image.ANTIALIAS)
    return imgResized
 
    
outputDir = r'd:\temp\ocrTest'
os.makedirs(outputDir,exist_ok=True)

outputSummaryFile = os.path.join(outputDir,'summary.html')

htmlImageList = []
htmlTitleList = []

for iImage,regionSet in enumerate(imageRegions):
        
    image = resizeImage(images[iImage])
    fn = os.path.join(outputDir,'img_{}_base.png'.format(iImage))
    image.save(fn)
    
    htmlImageList.append(fn)
    htmlTitleList.append('Image: {}'.format(ntpath.basename(imageFileNames[iImage])))
        
    for iRegion,region in enumerate(regionSet):
            
        text = imageText[iImage][iRegion].strip()
        if (len(text) == 0):
            continue
        
        if False:
            image = resizeImage(region)
            fn = os.path.join(outputDir,'img_{}_r{}_raw.png'.format(iImage,iRegion))
            image.save(fn)
            htmlImageList.append(fn)
            htmlTitleList.append('Result: [' + text + ']')
        
        image = resizeImage(processedRegions[iImage][iRegion])
        fn = os.path.join(outputDir,'img_{}_r{}_processed.png'.format(iImage,iRegion))
        image.save(fn)
        htmlImageList.append(fn)
        htmlTitleList.append('Result: [' + text + ']')
        
htmlOptions = {}
htmlOptions['makeRelative'] = True
write_html_image_list.write_html_image_list(outputSummaryFile,
                                            htmlImageList,
                                            htmlTitleList,
                                            htmlOptions)
os.startfile(outputSummaryFile)


#%% Scrap

# Alternative approaches to finding the text/background  region
# Using findCountours()
    if False:
    
        # imagePil = Image.fromarray(analysisImage); imagePil
        
        # analysisImage = cv2.erode(analysisImage, None, iterations=3)
        # analysisImage = cv2.dilate(analysisImage, None, iterations=3)
    
        # analysisImage = cv2.threshold(analysisImage, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        im2, contours, hierarchy = cv2.findContours(analysisImage,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        
        # Find object with the biggest bounding box
        mx = (0,0,0,0)      # biggest bounding box so far
        mx_area = 0
        for cont in contours:
            x,y,w,h = cv2.boundingRect(cont)
            area = w*h
            if area > mx_area:
                mx = x,y,w,h
                mx_area = area
        x,y,w,h = mx
       
    # Using connectedComponents()
    if False:
        
        # analysisImage = image
        nb_components, output, stats, centroids = \
            cv2.connectedComponentsWithStats(analysisImage, connectivity = 4)
        # print('Found {} components'.format(nb_components))
        sizes = stats[:, -1]
    
        max_label = 1
        max_size = sizes[1]
        for i in range(2, nb_components):
            if sizes[i] > max_size:
                max_label = i
                max_size = sizes[i]
    
        # We just want the *background* image
        max_label = 0
        
        maskImage = np.zeros(output.shape)
        maskImage[output == max_label] = 255
        
        thresh = 127
        binaryImage = cv2.threshold(maskImage, thresh, 255, cv2.THRESH_BINARY)[1]
        
        minX = -1
        minY = -1
        maxX = -1
        maxY = -1
        h = binaryImage.shape[0]
        w = binaryImage.shape[1]
        for y in range(h):
            for x in range(w):
                if binaryImage[y][x] > thresh:
                    if minX == -1:
                        minX = x
                    if minY == -1:
                        minY = y
                    if x > maxX:
                        maxX = x
                    if y > maxY:
                        maxY = y
        
    