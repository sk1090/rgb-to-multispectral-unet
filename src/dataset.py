import os
import cv2
import numpy as np
from torch.utils.data import Dataset
from PIL import Image
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor
from sklearn.model_selection import train_test_split

class PotatoDataset(Dataset):
    
    def __init__(self, rgb_dir, spectral_dir, transform=None, mode='train', align=False, split_ratio=0.8, random_seed=42):
        """Multispectral Potato Detection and Classification Dataset"""
        self.mode = mode
        self.transform = transform
        self.align = align
        self.channels = ['Green_Channel', 'Near_Infrared_Channel', 'Red_Channel', 'Red_Edge_Channel']

        if mode == 'test':
            # Load test data from a separate folder
            self.rgb_files = sorted([f for f in os.listdir(os.path.join(rgb_dir, 'Test_Images')) if f.endswith('.jpg')])
            self.spectral_files = {channel: sorted([
                f for f in os.listdir(os.path.join(spectral_dir, channel, 'Test_Images')) if f.endswith('.jpg')
            ]) for channel in self.channels}
            folder_set = 'Test_Images'
        else:
            # Load training data
            all_rgb_files = sorted([f for f in os.listdir(os.path.join(rgb_dir, 'Train_Images')) if f.endswith('.jpg')])
            spectral_files = {channel: sorted([
                f for f in os.listdir(os.path.join(spectral_dir, channel, 'Train_Images')) if f.endswith('.jpg')
            ]) for channel in self.channels}

            # Split RGB files into train and val sets
            train_files, val_files = train_test_split(all_rgb_files, test_size=1 - split_ratio, random_state=random_seed)

            # Sort train and validation files after the split
            train_files = sorted(train_files)
            val_files = sorted(val_files)

            # Filter spectral files to match RGB splits
            train_spectral_files = {
                channel: [f for f in spectral_files[channel] if os.path.splitext(f)[0] in {os.path.splitext(r)[0] for r in train_files}]
                for channel in self.channels
            }
            val_spectral_files = {
                channel: [f for f in spectral_files[channel] if os.path.splitext(f)[0] in {os.path.splitext(r)[0] for r in val_files}]
                for channel in self.channels
            }

            # Assign files based on mode
            if mode == 'train':
                self.rgb_files = train_files
                self.spectral_files = train_spectral_files
            elif mode == 'val':
                self.rgb_files = val_files
                self.spectral_files = val_spectral_files
            else:
                raise ValueError("Mode must be 'train', 'val', or 'test'")

            folder_set = 'Train_Images'

        # Preload and align images using multiprocessing
        args_list = [
            (rgb_dir, spectral_dir, folder_set, rgb_name, idx, self.channels, self.spectral_files, self.align)
            for idx, rgb_name in enumerate(self.rgb_files)
        ]

        with ProcessPoolExecutor() as executor:
            results = list(tqdm(executor.map(self.process_image, args_list), desc=f"Loading {mode} data", total=len(self.rgb_files)))

        self.data = results

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        rgb_image, spectral_images = self.data[idx]

        # Convert to PIL
        rgb_image = Image.fromarray(rgb_image).convert('RGB')
        spectral_images = [Image.fromarray(img) for img in spectral_images]

        # Apply transformations
        if self.transform:
            rgb_image = self.transform(rgb_image)
            spectral_images = [self.transform(img) for img in spectral_images]

        return (rgb_image, *spectral_images)

    @staticmethod
    def process_image(args):
        """
        Process a single image (alignment and resizing).
        Ensures RGB and spectral images are correctly matched by comparing their base names.
        """
        rgb_dir, spectral_dir, folder_set, rgb_name, idx, channels, spectral_files, align = args

        # Read the RGB image
        rgb_path = os.path.join(rgb_dir, folder_set, rgb_name)
        rgb_im = cv2.imread(rgb_path)

        # Ensure the base names match
        for channel in channels:
            spectral_file = spectral_files[channel][idx]
            if os.path.splitext(rgb_name)[0] != os.path.splitext(spectral_file)[0]:
                raise ValueError(
                    f"Mismatch detected: RGB file '{rgb_name}' does not match spectral file '{spectral_file}' in channel '{channel}'"
                )

        # Resize RGB to match spectral dimensions
        height, width = cv2.imread(
            os.path.join(spectral_dir, channels[0], folder_set, spectral_files[channels[0]][idx]),
            cv2.IMREAD_GRAYSCALE
        ).shape
        rgb_resized = cv2.resize(rgb_im, (width, height), interpolation=cv2.INTER_LINEAR)
        rgb_gray = cv2.cvtColor(rgb_resized, cv2.COLOR_BGR2GRAY)

        # Process spectral images
        spectral_images = []
        for channel in channels:
            spectral_path = os.path.join(spectral_dir, channel, folder_set, spectral_files[channel][idx])
            spectral_im = cv2.imread(spectral_path, cv2.IMREAD_GRAYSCALE)
            if align:
                aligned_image = PotatoDataset.align_images(rgb_gray, spectral_im)
                spectral_images.append(aligned_image)
            else:
                spectral_images.append(spectral_im)

        # Validate size consistency
        for channel, spectral_im in zip(channels, spectral_images):
            assert spectral_im.shape == rgb_resized.shape[:2], \
                f"Size mismatch: RGB {rgb_resized.shape[:2]} vs {channel} {spectral_im.shape}"

        return (rgb_resized, spectral_images)