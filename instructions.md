## Folder structure
In the directory `code`, you can find 3 files and one folder:
- The file `networks.py` contains the fully-connected and convolutional neural network architectures used in this project.
- The file `verifier.py` contains a template of the verifier. Loading of the stored networks and test cases is already implemented in the `main` function. If you decide to modify the `main` function, please ensure that the parsing of the test cases works correctly. Your task is to modify the `analyze` function by building upon DeepPoly convex relaxation. Note that the provided verifier template is guaranteed to achieve **0** points (by always outputting `not verified`).
- The file `evaluate` will run all networks and specs currently in the repository. It follows the calling convention we will use for grading.
- The folder `utils` contains helper methods for loading and initialization (There is most likely no need to change anything here).


In the directory `models`, you can find 14 neural networks (9 fully connected and 5 convolutional) weights. These networks are loaded using PyTorch in `verifier.py`. Note that we included two `_base` networks which do not contain activation functions.

In the directory `test_cases`, you can find 13 subfolders (the folder for `fc_6` contains both examples for `cifar10` and `mnist`). Each subfolder is associated with one of the networks using the same name. In a subfolder corresponding to a network, you can find 2 test cases for each network. Note that for the base networks, we provide you with 5 test cases each. Also, as we use 2 different versions (mnist, cifar10) of `fc_6`, the corresponding folder contains 2 test cases per dataset. As explained in the lecture, these test cases **are not** part of the set of test cases that we will use for the final evaluation.

Note that all inputs are images with pixel values between 0 and 1. The same range also applies to all abstract bounds that we want to verify.

