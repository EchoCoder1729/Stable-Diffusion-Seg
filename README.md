# Stable Diffusion Segmentation
This is the repo of **Stable Diffusion Segmentation for Biomedical Images with Single-step Reverse Process**.



## Requirements

A suitable [conda](https://conda.io/) environment named `sdseg` can be created
and activated with:

```
conda env create -f environment.yaml
conda activate sdseg
```

> WARNING: `environment.yaml` has not been tested yet, but will be tested and updated soon.



## SDSeg Framework

SDSeg is built on Stable Diffusion V1, with a downsampling-factor 8 autoencoder, an denoising UNet and trainable vision encoder (with the same architecture of the encoder in the f=8 autoencoder).

<img src="assets/framework.jpg" alt="framework" style="zoom:67%;" />

### Dataset Settings

The image data should be place at `./data/`, while the dataloaders are at `./ldm/data/`

We evaluate SDSeg on the following medical image datasets:

1. `BTCV`
    - URL: https://www.synapse.org/#!Synapse:syn3193805/wiki/217752
    - Preprocess: use the code in `./data/synapse/nii2format.py`

2. `STS-3D`:
    - URL: https://toothfairychallenges.github.io/
    - Preprocess: N/A

3. `REFUGE2`:
    - URL: https://refuge.grand-challenge.org/
    - Preprocess: following https://github.com/HzFu/MNet_DeepCDR

4. `CVC-ClinicDB`:
    - URL: https://polyp.grand-challenge.org/CVCClinicDB/
    - Preprocess: N/A

5. `Kvasir-SEG`:
    - URL: https://datasets.simula.no/kvasir-seg/
    - Preprocess: None


### Downloading Pre-trained Models

SDSeg use pre-trained weights from SD to initialize before training.

For pre-trained weights of the autoencoder and conditioning model, run

```
bash scripts/download_first_stages_f8.sh
```

For pre-trained wights of the denoising UNet, run

```
bash scripts/download_models_lsun_churches.sh
```

### Model Weights

> The model weights will be available soon.

### Training Scripts

Take CVC dataset as an example, run

```
nohup python -u main.py --base configs/latent-diffusion/cvc-ldm-kl-8.yaml -t --gpus 0, --name experiment_name > nohup/experiment_name.log 2>&1 &
```

You can check the training log by 

```
tail -f nohup/experiment_name.log
```

Also, tensorboard will be on automatically. You can start a tensorboard session with `--logdir=./logs/`



### Testing Scripts

After training an SDSeg model, you should **manually modify the run paths** in`scripts/slice2seg.py`, and begin an inference process like

```
python -u scripts/slice2seg.py --dataset cvc
```



### Stability Evaluaition

To conduct an stability evaluation process mentioned in the paper, you can start the test by

```
python -u scripts/slice2seg.py --dataset cvc --times 10 --save_results
```

This will save 10 times of inference results in `./outputs/` folder. To run the stability evaluation, open `scripts/stability_evaluation.ipynb`, and **modify the path for the segmentation results**. Then, click `Run All` and enjoy.



### Important Files to Focus on

- SDSeg model: `./ldm/models/diffusion/ddpm.py` in the `LatentDiffusion` class.
- Inference scripts: `./scripts/slice2seg.py`, but the main implementation of inference process is in `./ldm/models/diffusion/ddpm.py`, under the `log_dice` method of `LatentDiffusion`.
- Dataset storation: should be in `./data/`
- Dataloader files: `./ldm/data/`



## TODO List

- [ ] Organizing the inference code. (Toooo redundant right now.)
- [ ] Reimplement SDSeg in OOP. (Elegance is the key!)
- [ ] Add README for multi-class segmentation.



