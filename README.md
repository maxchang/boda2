# Computational Optimization of DNA Activity (CODA)
[Preprint on bioRxiv](https://www.biorxiv.org/content/10.1101/2023.08.08.552077v1). For legacy reasons, this repo is currently listed as boda2.

# Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Installation Guide](#installation-guide)
- [Interactive Docker Environments](#interactive-docker-environments)
- [Interactive modeling and deployment](#interactive-modeling-and-deployment)
- [Applications](#applications)
- [Extending CODA](#extending-coda)
- [Cloud Integrations](#cloud-integrations)

# Overview
Here, we present a platform to engineer and validate synthetic CREs capable of driving gene expression
with programmed cell type specificity. This library contains the resources needed to train DNNs on MPRA data and generate synthetic sequences from these models. Additionally, we include resources to apply these model to to inference tasks on common input data types (e.g., VCF, FASTA, etc.). Finally, we provide examples which deploy the Malinois model.

# System requirements
## Hardware requirements
CODA was extensively tested in Google Colab environments and GCP VMs with the following specs:

- Type: `a2-highgpu-1g`
- CPU: 12 vCPU
- RAM: 85 GB
- GPU: 1x Tesla A100
- GPU-RAM: 40 GB HBM2

## Software Requirements
CODA was designed using the GCP deployment: NVIDIA GPU-Optimized Image for Deep Learning, ML & HPC

- OS: Ubuntu 20.04.2 LTS
- CUDA: 11.3

# Installation Guide
CODA can be installed from the latest version of the GITHUB repo.
```
git clone https://github.com/sjgosai/boda2.git
cd boda2/
pip install -e .
```

# Interactive Docker Environments
CODA has been installed in docker containers which can be downloaded in attached for interactive use. This can be quickly deployed using helper scripts in the repo:
```
cd /home/ubuntu
git clone https://github.com/sjgosai/boda2.git
bash boda2/src/run_docker_for_dev.sh gcr.io/sabeti-encode/boda devenv 0.2.0 8888 6006
```
Which connects `jupyter lab` to ports `8888` and `6006`.

More containers can be found at `gcr.io/sabeti-encode/boda`.

# Interactive usage
## Modeling
CODA is an extension of pytorch and pytorch-lightning. Classes in CODA used to construct models generally inherit from `nn.Module` and `lightning.LightningModule` but need to be combined as described in [`tutorials/construct_new_model.ipynb`](tutorials/construct_new_model.ipynb). The documentation for this is in progress.

## Inference
Example interactive deployment of Malinois for inference can be found here: [`tutorials/load_malinois_model.ipynb`](tutorials/load_malinois_model.ipynb)

## Sequence generation
The tutorials also include a notebook that describes how to mix models with the sequence generation algorithms implemented in CODA: [`tutorials/run_generators.ipynb`](tutorials/run_generators.ipynb)

# Applications
We have developed python applications to train models and generate sequences using this library.

## Model training
Deep learning models can be trained from the command line by invoking the DATA, MODEL, and GRAPH modules. For example:
```
python /home/ubuntu/boda2/src/train.py \
  --data_module=MPRA_DataModule \
    --datafile_path=gs://tewhey-public-data/CODA_resources/MPRA_ALL_HD_v2.txt \
    --activity_columns K562_mean HepG2_mean SKNSH_mean \
    --synth_val_pct=0.0 --synth_test_pct=99.98 \
    --batch_size=1076 --duplication_cutoff=0.5 --std_multiple_cut=6.0 \
    --val_chrs 7 13 --test_chrs 9 21 X \
    --padded_seq_len=600 --use_reverse_complements=True --num_workers=8 \
  --model_module=BassetBranched \
    --input_len 600 \
    --conv1_channels=300 --conv1_kernel_size=19 \
    --conv2_channels=200 --conv2_kernel_size=11 \
    --conv3_channels=200 --conv3_kernel_size=7 \
    --linear_activation=ReLU --linear_channels=1000 \
    --linear_dropout_p=0.11625456877954289 \
    --branched_activation=ReLU --branched_channels=140 \
    --branched_dropout_p=0.5757068086404574 \
    --n_outputs=3 --n_linear_layers=1 \
    --n_branched_layers=3 --n_branched_layers=3 \
    --use_batch_norm=True --use_weight_norm=False \
    --loss_criterion=L1KLmixed --beta=5.0 \
    --reduction=mean \
  --graph_module=CNNTransferLearning \
    --parent_weights=gs://tewhey-public-data/my-model.epoch_5-step_19885.pkl \
    --frozen_epochs=0 \
    --optimizer=Adam --amsgrad=True \
    --lr=0.0032658700881052086 --eps=1e-08 --weight_decay=0.0003438210249762151 \
    --beta1=0.8661062881299633 --beta2=0.879223105336538 \
    --scheduler=CosineAnnealingWarmRestarts --scheduler_interval=step \
    --T_0=4096 --T_mult=1 --eta_min=0.0 --last_epoch=-1 \
    --checkpoint_monitor=entropy_spearman --stopping_mode=max \
    --stopping_patience=30 --accelerator=gpu --devices=1 --min_epochs=60 --max_epochs=200 \
    --precision=16 --default_root_dir=/tmp/output/artifacts \
    --artifact_path=gs://your/bucket/mpra_model/
```

## Sequence design
Trained models can be deployed to generate sequences using implemented algorithms. This command will run Fast SeqProp using the Malinois model to optimize K562 specific expression:
```
python /home/ubuntu/boda2/src/generate.py \
    --params_module StraightThroughParameters \
        --batch_size 256 --n_channels 4 \
        --length 200 --n_samples 10 \
        --use_norm True --use_affine False \
    --energy_module MinGapEnergy \
        --target_feature 0 --bending_factor 1.0 --a_min -2.0 --a_max 6.0 \
        --model_artifact gs://tewhey-public-data/CODA_resources/malinois_artifacts__20211113_021200__287348.tar.gz \
    --generator_module FastSeqProp \
         --n_steps 200 --learning_rate 0.5 \
    --energy_threshold -0.5 --max_attempts 40 \
    --n_proposals 1000 \
    --proposal_path ./test__k562__fsp
```

This command will run Simulated Annealing with the same objective:
```
python /home/ubuntu/boda2/src/generate.py \
    --params_module BasicParameters \
        --batch_size 256 --n_channels 4 \
        --length 200 \
    --energy_module MinGapEnergy \
        --target_feature 0 --bending_factor 0.0 --a_min -2.0 --a_max 6.0 \
        --model_artifact gs://tewhey-public-data/CODA_resources/malinois_artifacts__20211113_021200__287348.tar.gz \
    --generator_module SimulatedAnnealing \
         --n_steps 2000 --n_positions 5 \
         --a 1.0 --b 1.0 --gamma 0.501 \
    --energy_threshold -0.5 --max_attempts 40 \
    --n_proposals 1000 \
    --proposal_path ./test__k562__sa
```

## Variant effect prediction
Trained models can be deployed to infer the effect of non-coding variants in CREs
```
python vcf_predict.py \
  --artifact_path gs://tewhey-public-data/CODA_resources/malinois_artifacts__20211113_021200__287348.tar.gz \
  --vcf_file hepg2.ase.calls.fdr.05.vcf \
  --fasta_file GRCh38_no_alt_analysis_set_GCA_000001405.15.fasta \
  --output test.vcf \
  --relative_start 25 --relative_end 180 --step_size 25 \
  --strand_reduction mean --window_reduction gather \
  --window_gathering abs_max --gather_source skew --activity_threshold 0.5 \
  --batch_size 16
```

## Saturation mutagenesis
UNDER CONSTRUCTION

# Extending CODA
CODA is modular. If new modules fit the API requirements, they will work with the entire system, including deployment applications. Further documentation on API requirements are forthcoming.

# Cloud Integrations
Containerized CODA applications can be used in combination with various GCP platforms.

## Training models on VertexAI
We provide containers that can be used in combination with Vertex AI's custom model APIs, including hyperparameter optimization. An example deployment using Vertex AI's Python SDK can be found here: [`tutorials/vertex_sdk_launch.ipynb`](tutorials/vertex_sdk_launch.ipynb)

## Deploying inference with Batch
UNDER CONSTRUCTION. Note: GCP is deprecating Life Sciences API which was what we used to scale inference. The goal is to move to Batch which we have to figure out, so expect this to take some time.