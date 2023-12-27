# RTAI 2023 Course Project
This is an implementation of a robustness verifier for neural networks using the DeepPoly relaxation ([from this paper](https://files.sri.inf.ethz.ch/website/papers/DeepPoly.pdf)) done in the context of the [Reliable and Trustworthy AI course]() at ETH. It provides a sound (i.e. certified) verifier to check for $L_\infty$-robustness to adversarial attacks that improves completeness (i.e. coverage) using gradient based optimization.

## Setup

You can create a virtual environment and install the dependencies using the following commands:

```bash
$ virtualenv venv --python=python3.10
$ source venv/bin/activate
$ pip install -r requirements.txt
```

If you prefer conda environments we also provide a conda `environment.yaml` file which you can install (After installing [conda](https://docs.conda.io/projects/conda/en/latest/commands/install.html) or [mamba](https://mamba.readthedocs.io/en/latest/installation.html)) via

```bash
$ conda env create -f ./environment.yaml
$ conda activate rtai-project
```

for `mamba` simply replace `conda` with `mamba`.

## Running the verifier

The verifier can be run using the command:

```bash
$ python code/verifier.py --net {net} --spec test_cases/{net}/img{id}_{dataset}_{eps}.txt
```

In this command,
- `net` is equal to one of the following values (each representing one of the networks we want to verify): `fc_base, fc_1, fc_2, fc_3, fc_4, fc_5, fc_6, fc_7, conv_base, conv_1, conv_2, conv_3, conv_4`.
- `id` is simply a numerical identifier of the case. They are not always ordered as they have been directly sampled from a larger set of cases.
- `dataset` is the dataset name, i.e.,  either `mnist` or `cifar10`.
- `eps` is the perturbation that the verifier should certify in this test case.

For example, you can run:

```bash
$ python code/verifier.py --net fc_1 --spec test_cases/fc_1/img0_mnist_0.1394.txt
```

To evaluate the verifier on all networks and sample test cases, we provide an evaluation script.
You can run this script from the root directory using the following commands:

```bash
chmod +x code/evaluate
code/evaluate
```