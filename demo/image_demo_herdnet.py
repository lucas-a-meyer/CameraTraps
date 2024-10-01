# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
""" Demo for Herdnet image detection"""

# Importing necessary basic libraries and modules
import os
os.environ['WANDB_MODE'] = 'disabled'  

# PyTorch imports 
import torch

# Importing the model, dataset, transformations and utility functions from PytorchWildlife
from PytorchWildlife.models.detection.herdnet.animaloc import models as animaloc_models
from PytorchWildlife.models import detection as pw_detection
from PytorchWildlife import utils as pw_utils

# Setting the device to use for computations ('cuda' indicates GPU)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

img_path = os.path.join(".","demo_data","herdnet_imgs","S_11_05_16_DSC01556.JPG")
weights_path = "../20220413_HerdNet_General_dataset_2022.pth"
model = animaloc_models.HerdNet(num_classes=7, pretrained=False) # Architecture of the model
model = animaloc_models.LossWrapper(model, []) # Model wrapper
detection_model = pw_detection.herdnet.HerdNet(weights=weights_path, device=DEVICE, model=model)

# Running the model on the image
detection_model.eval()
with torch.no_grad():
    results = detection_model.single_image_detection(img=img_path)

pw_utils.save_detection_images_dots(results, os.path.join(".","herdnet_demo_output"), overwrite=False)

## Batch image detection
folder_path = os.path.join(".","demo_data","herdnet_imgs")
with torch.no_grad():
    results = detection_model.batch_image_detection(folder_path, batch_size=1, extension="JPG") # NOTE: Only use batch size 1 because each image is divided into patches and this batch is enough. 
# Saving the batch detection results as annotated images
pw_utils.save_detection_images_dots(results, "herdnet_demo_batch_output", folder_path, overwrite=False)

'''# Saving the detected objects as cropped images
#pw_utils.save_crop_images(results, "demo_crop_output", folder_path, overwrite=False) # TODO: This does not work for dots format'''

# Saving the detection results in JSON format
pw_utils.save_detection_json_as_dots(results, os.path.join(".","herdnet_demo_batch_output.json"),
                             categories=detection_model.CLASS_NAMES,
                             exclude_category_ids=[], # Category IDs can be found in the definition of each model.
                             exclude_file_path=None)