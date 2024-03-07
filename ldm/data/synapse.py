import os
import sys

import numpy as np
import PIL
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms
import glob
from sklearn.metrics.pairwise import pairwise_distances
import torch.nn.functional as F
import nibabel as nib

train_pixel_distribution = np.array(
    [9.54271542e-01, 5.38177007e-03, 2.30164099e-03, 2.31975002e-03,
    4.22884468e-04, 2.51331787e-04, 2.44881894e-02, 5.99445428e-03,
    1.59142062e-03, 1.18954373e-03, 5.27832639e-04, 1.12456102e-03,
    5.87094159e-05, 7.63698597e-05]
) 

def softmax(array):
    """softmax for 1-D array"""
    return np.array(array) / np.sum(np.array(array))

def sampling_rate(cls_id):
    if len(cls_id)>1:
        return [0.07] + list(softmax(1-train_pixel_distribution[cls_id[1:]]) * 0.93)
    else:
        return[1]   # only class 0

COLOR_MAP = np.array([
            [  0.,   0.,   0.],
            [255.,   0.,   0.],
            [  0., 255.,   0.],
            [  0.,   0., 255.],
            [255., 255.,   0.],
            [  0., 255., 255.],
            [255.,   0., 255.],
            [255., 239., 213.],
            [  0.,   0., 205.],
            [205., 133.,  63.],
            [210., 180., 140.],
            [102., 205., 170.],
            [  0.,   0., 128.],
            [  0., 139., 139.],
        ])


def quantize_mapping(colored_outuput, colormap=None):
    if colormap is not None:
        sim = 1 - pairwise_distances(colored_outuput.reshape(-1, 3), colormap)\
            .reshape(*colored_outuput.shape[:2], colormap.shape[0])
        sim_logits = torch.softmax(torch.tensor(sim), dim=2)
        sim_class = torch.argmax(sim_logits, dim=2).unsqueeze(2).repeat((1, 1, 3))
        sim_class = np.array(sim_class)
    else:
        sim_class = np.rint(colored_outuput)
    return sim_class


def colorize(seg, num_classes=14):
    """ seg (H W C)"""
    if num_classes == 2:
        return seg * 255
    for idx in range(1, 14):
        seg[seg[:, :, 0] == idx] = COLOR_MAP[idx]
    return seg


def decolorize(seg):
    for idx in range(1, 14):
        seg[(seg == COLOR_MAP[idx]).all(2)] = idx
    return seg


class SynapseBase(Dataset):
    """Synapse Dataset Base
    Notes:
        - `segmentation` is for the diffusion training stage (range binary -1 and 1)
        - `image` is for conditional signal to guided final seg-map (range -1 to 1)
    TODO:
        - extend to multi-label segmentation.
        - extend to fit 13 organs and 8 organs.
    """
    def __init__(self, data_root, size=256, interpolation="nearest", mode=None, num_classes=2):
        self.mode = mode
        self.num_classes = num_classes
        print(f"[Dataset]: Synapse with {self.num_classes} classes, in {self.mode} mode")
        assert mode in ["train", "val", "test_vol"]

        self.data_root = data_root
        if mode == "test_vol":
            self.data_paths = glob.glob(os.path.join(self.data_root, "img*"))#[:2]
        else:
            self.data_paths = glob.glob(os.path.join(self.data_root, "*.png"))  # seg map, img slice with *.npy postfix
        self._length = len(self.data_paths)

        self.labels = dict(
            # relative_file_path_=[l for l in self.data_paths],
            file_path_=[path for path in self.data_paths],
        )
        self.size = size
        self.interpolation = dict(nearest=PIL.Image.NEAREST)[interpolation]   # for segmentation slice
        self.transform = transforms.Compose([
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.5),
            # transforms.CenterCrop(size=(256, 256)),
            # transforms.Resize(size=(256, 256), interpolation=self.interpolation),
            # transforms.RandomResizedCrop(size=(256, 256), 
            #                              scale=(0.2, 1),
            #                              interpolation=self.interpolation),
        ])

    def __len__(self):
        return self._length

    def __getitem__(self, i):
        # read segmentation and images
        example = dict((k, self.labels[k][i]) for k in self.labels)

        if self.mode == "test_vol":     # 3-D volume
            image = nib.load(example["file_path_"]).get_fdata()
            segmentation = nib.load(example["file_path_"].replace("img", "label")).get_fdata()

            image[image < -125] = -125  # window-level window width
            image[image > 275] = 275
            image = (image - image.min()) / (image.max() - image.min())     # [-125, 275] -> [0, 1]
            image = (image * 2) - 1     # [0, 1] -> [-1, 1]

            if self.num_classes == 2:
                segmentation = self.transfer_to_9(segmentation) # 14 -> 9 -> 2
                segmentation = np.where(segmentation > 0, 1, 0)  # TODO: extend to multi-label segmentation
            elif self.num_classes == 9:
                segmentation = self.transfer_to_9(segmentation)
            else:
                pass

            example["image"] = image
            example["segmentation"] = segmentation
            # example["segmentation_onehot"] = \
            #     F.one_hot(torch.tensor(segmentation)[:, :, 0].long(), num_classes=self.num_classes).numpy()
            return example

        segmentation = np.array(Image.open(example["file_path_"]))
        image = np.load(example["file_path_"].replace("png", "npy"))    # same name, different postfix
        segmentation = torch.tensor(segmentation.transpose([2, 0, 1]))
        image = torch.tensor(image.transpose([2, 0, 1]))

        if self.mode == "train":
            state = torch.get_rng_state()
            segmentation = self.transform(segmentation)
            torch.set_rng_state(state)
            image = self.transform(image)

        segmentation = np.array(segmentation.permute(1, 2, 0))      # h w c
        image = np.array(image.permute(1, 2, 0))        # h w c

        if self.num_classes == 2:
            segmentation = self.transfer_to_9(segmentation) # 14 -> 9 -> 2
            segmentation = np.where(segmentation > 0, 1, 0)
            class_id = np.array([-1]) # doesn't matter for binary seg
        else:
            if self.num_classes == 9:
                segmentation = self.transfer_to_9(segmentation)
            # # handle segmentation map
            # example["segmentation_onehot"] = \
            #     F.one_hot(torch.tensor(segmentation)[:, :, 0].long(), num_classes=self.num_classes).numpy()

            # handle random class
            exist_class = sorted(list(set(segmentation.flatten())))
            class_id = np.random.choice(np.array(exist_class), size=1, 
                                        p=None).astype(np.int64)

            # # choose class from id (3 channel, 1 class)
            if class_id != 0:
                segmentation = (segmentation == class_id)   # for multi, get a random class (existed) except 0
            else:
                segmentation = (segmentation != class_id)   # (empty slice) or (not empty slice & class_id==0)

        # turn segmentation map [0, 1] -> [-1, 1]
        example["class_id"] = class_id
        example["segmentation"] = ((segmentation.astype(np.float32) * 2) - 1)   # range: -1 and 1
        example["image"] = image     # range from -1 to 1, np.float32
        assert (-1 <= example["image"].all() <= 1), (example["image"].min(), example["image"].max())
        assert (-1 <= example["segmentation"].all() <= 1), (example["segmentation"].min(), example["segmentation"].max())
        return example
    
    @staticmethod
    def transfer_to_9(gts):
        # 0 1 2 3 4 5 6 7 8 9 10 11 12 13
        # 0 1 2 3 4   6 7 8      11
        # 0 1 2 3 4   5 6 7      8
        # extract the 8 target classes (total 9 classes)for training
        gts[gts == 5] = 0
        gts[gts == 6] = 5
        gts[gts == 7] = 6
        gts[gts == 8] = 7
        gts[gts == 9] = 0
        gts[gts == 10] = 0
        gts[gts == 11] = 8
        gts[gts == 12] = 0
        gts[gts == 13] = 0
        return gts

class SynapseTrain(SynapseBase):
    def __init__(self, **kwargs):
        super().__init__(data_root="data/synapse/train", mode="train", **kwargs)


class SynapseValidation(SynapseBase):
    def __init__(self, **kwargs):
        super().__init__(data_root="data/synapse/test", mode="val", **kwargs)


class SynapseValidationVolume(SynapseBase):
    def __init__(self, **kwargs):
        super().__init__(data_root="data/synapse/test_vol", mode="test_vol", **kwargs)

class SynapseValidationVolume4test(SynapseBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# from Swin-UNETR:

# "validation": [
#         {
#             "image": "imagesTr/img0035.nii.gz",
#             "label": "labelsTr/label0035.nii.gz"
#         },
#         {
#             "image": "imagesTr/img0036.nii.gz",
#             "label": "labelsTr/label0036.nii.gz"
#         },
#         {
#             "image": "imagesTr/img0037.nii.gz",
#             "label": "labelsTr/label0037.nii.gz"
#         },
#         {
#             "image": "imagesTr/img0038.nii.gz",
#             "label": "labelsTr/label0038.nii.gz"
#         },
#         {
#             "image": "imagesTr/img0039.nii.gz",
#             "label": "labelsTr/label0039.nii.gz"
#         },
#         {
#             "image": "imagesTr/img0040.nii.gz",
#             "label": "labelsTr/label0040.nii.gz"
#         }