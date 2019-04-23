#
# visualize_bbox_db.py
# 
# Outputs an HTML page visualizing bounding boxes on a sample of images in a bbox database
# in the COCO Camera Trap format (output of data_management/annotations/add_bounding_boxes_to_json.py).
#

#%% Imports

import json
import os
import pandas as pd
import math
from tqdm import tqdm
import visualization_utils as vis_utils
from itertools import compress
import sys

# Assumes ai4eutils is on the path (github.com/Microsoft/ai4eutils)
#
# sys.path.append('/home/yasiyu/repos/ai4eutils')
# sys.path.append(r'd:\git\CameraTraps\visualization')
from write_html_image_list import write_html_image_list


#%% Settings

# Set to None to visualize all images
num_to_visualize = 100; # None

# Target size for rendering; set either dimension to -1 to preserve aspect ratio
viz_size = (675, -1)
bbox_db_path = r'e:\wildlife_data\missouri_camera_traps\missouri_camera_traps_set2.json'
output_dir = r'd:\temp\tmp'
image_base_dir = r'e:\wildlife_data\missouri_camera_traps'
htmlOptions = write_html_image_list()
bSortByFilename = True
bTrimToImagesWithBboxes = False
randomSeed = 0; # None

# We sometimes flatten image directories by replacing a path separator with 
# another character.  Leave blank for the typical case where this isn't necessary.
pathsep_replacement = '' # '~'


#%% Helper functions

# Translate the file name in an image entry in the json database to a path, possibly doing
# some manipulation of path separators
def image_file_name_to_path(image_file_name, image_base_dir):
    
    if len(pathsep_replacement) > 0:
        image_file_name = os.path.normpath(image_file_name).replace(os.pathsep,pathsep_replacement)        
    return os.path.join(image_base_dir, image_file_name)


#%% Processing images

os.makedirs(os.path.join(output_dir, 'rendered_images'), exist_ok=True)
assert(os.path.isfile(bbox_db_path))
assert(os.path.isdir(image_base_dir))

print('Loading the database...')
bbox_db = json.load(open(bbox_db_path))
print('...done')

annotations = bbox_db['annotations']
images = bbox_db['images']
categories = bbox_db['categories']

# Optionally remove all images without bounding boxes, *before* sampling
if bTrimToImagesWithBboxes:
    
    bHasBbox = [False] * len(annotations)
    for iAnn,ann in enumerate(annotations):
        if 'bbox' in ann:
            assert isinstance(ann['bbox'],list)
            bHasBbox[iAnn] = True
    annotationsWithBboxes = list(compress(annotations, bHasBbox))
    
    imageIDsWithBboxes = [x['image_id'] for x in annotationsWithBboxes]
    imageIDsWithBboxes = set(imageIDsWithBboxes)
    
    bImageHasBbox = [False] * len(images)
    for iImage,image in enumerate(images):
        imageID = image['id']
        if imageID in imageIDsWithBboxes:
            bImageHasBbox[iImage] = True
    imagesWithBboxes = list(compress(images, bImageHasBbox))
    images = imagesWithBboxes
    
# put the annotations in a dataframe so we can select all annotations for a given image
df_anno = pd.DataFrame(annotations)
df_img = pd.DataFrame(images)

# construct label map
label_map = {}
for cat in categories:
    label_map[int(cat['id'])] = cat['name']

# take a sample of images
if num_to_visualize is not None:
    df_img = df_img.sample(n=num_to_visualize,random_state=randomSeed)

images_html = []

# iImage = 0
for iImage in tqdm(range(len(df_img))):
    
    img_id = df_img.iloc[iImage]['id']
    img_relative_path = df_img.iloc[iImage]['file_name']
    img_path = os.path.join(image_base_dir, image_file_name_to_path(img_relative_path, image_base_dir))

    if not os.path.exists(img_path):
        print('Image {} cannot be found'.format(img_path))
        continue

    annos_i = df_anno.loc[df_anno['image_id'] == img_id, :]  # all annotations on this image

    try:
        originalImage = vis_utils.open_image(img_path)
        original_size = originalImage .size
        image = vis_utils.resize_image(originalImage , viz_size[0], viz_size[1])
    except Exception as e:
        print('Image {} failed to open. Error: {}'.format(img_path, e))
        continue

    bboxes = []
    boxClasses = []
    
    # All the class labels we've seen for this image (with out without bboxes)
    imageCategories = set()
    
    # Iterate over annotations for this image
    # iAnn = 0; anno = annos_i.iloc[iAnn]
    for iAnn,anno in annos_i.iterrows():
    
        categoryID = anno['category_id']
        categoryName = label_map[categoryID]
        imageCategories.add(categoryName)
        
        bbox = anno['bbox']        
        if isinstance(bbox,float):
            assert math.isnan(bbox), 'I shouldn''t see a bbox that''s neither a box nor NaN'
            continue
        bboxes.append(bbox)
        boxClasses.append(anno['category_id'])
    
    imageClasses = ', '.join(imageCategories)
    
    # render bounding boxes in-place
    vis_utils.render_db_bounding_boxes(bboxes, boxClasses, image, original_size, label_map)  
    
    file_name = '{}_gtbbox.jpg'.format(img_id.lower().split('.jpg')[0])
    file_name = file_name.replace('/', '~')
    image.save(os.path.join(output_dir, 'rendered_images', file_name))

    images_html.append({
        'filename': '{}/{}'.format('rendered_images', file_name),
        'title': '{}<br/>{}, number of boxes: {}, class labels: {}'.format(img_relative_path,img_id, len(bboxes), imageClasses),
        'textStyle': 'font-family:verdana,arial,calibri;font-size:80%;text-align:left;margin-top:20;margin-bottom:5'
    })

# ...for each image

    
#%% Write to HTML

if bSortByFilename:    
    images_html = sorted(images_html, key=lambda x: x['filename'])
    
htmlOptions['headerHtml'] = '<h1>Sample annotations from {}</h1>'.format(bbox_db_path)
write_html_image_list(
        filename=os.path.join(output_dir, 'index.html'),
        images=images_html,
        options=htmlOptions)

print('Visualized {} images.'.format(len(images_html)))
