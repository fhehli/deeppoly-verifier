from dataclasses import dataclass
from time import time
from typing import Dict, List, Optional, Union

import torch
from torch.autograd.functional import jacobian
from torch.nn.functional import relu, sigmoid
import torch.nn as nn

from Box import Box
from utils.utils import has_relu, preprocess_net


@dataclass(frozen=True)
class LinearBound:
    lower_weight: torch.Tensor
    upper_weight: torch.Tensor
    lower_bias: Optional[torch.Tensor] = None
    upper_bias: Optional[torch.Tensor] = None
    is_diag: bool = False

    def get_params(self):
        return self.lower_weight.clone(), self.upper_weight.clone(), self.lower_bias.clone(), self.upper_bias.clone()


class DeepPoly:
    def __init__(self, model: nn.Module, x: torch.Tensor, eps: float):
        self.model = model
        self.initial_box = Box.construct_initial_box(x, eps)
        # stores the concrete bounds
        self.prev_box: Box
        # stores the linear bounds
        self.linear_bounds: Dict[int, LinearBound] = {}  # {layer_number: linear_bound}
        # stores the slope parameters for the ReLU layers
        self.alphas: Dict[int, torch.Tensor] = self._initial_alphas()  # {layer_number: alpha}

    def _initial_alphas(self) -> dict:
        """
        Initializes the alphas for the ReLU layers.
        """
        alphas = {}  # {layer_number: alpha}
        for i, layer in enumerate(self.model):
            if isinstance(layer, (nn.ReLU, nn.LeakyReLU)):
                initial_alpha = torch.rand(layer.in_features) * 2 - 1  # uniform in [-1, 1]
                alphas[i] = nn.Parameter(initial_alpha)

        return alphas

    def backsubstitute(self, layer_number: int) -> Box:
        """
        Performs backsubstitution to compute bounds for a given layer.

        Args:
            layer_number: index of the layer for which to compute bounds
        """
        linb = self.linear_bounds[layer_number]
        lower_weight, upper_weight, lower_bias, upper_bias = linb.get_params()

        prev_linear_bounds = [
            self.linear_bounds[i] for i in range(layer_number) if not isinstance(self.model[i], nn.Flatten)
        ]

        for prev_linb in reversed(prev_linear_bounds):
            lower_bias += relu(lower_weight) @ prev_linb.lower_bias - relu(-lower_weight) @ prev_linb.upper_bias
            upper_bias += relu(upper_weight) @ prev_linb.upper_bias - relu(-upper_weight) @ prev_linb.lower_bias
            if prev_linb.is_diag:
                lower_weight = (
                    relu(lower_weight) * prev_linb.lower_weight - relu(-lower_weight) * prev_linb.upper_weight
                )
                upper_weight = (
                    relu(upper_weight) * prev_linb.upper_weight - relu(-upper_weight) * prev_linb.lower_weight
                )
            else:
                lower_weight = (
                    relu(lower_weight) @ prev_linb.lower_weight - relu(-lower_weight) @ prev_linb.upper_weight
                )
                upper_weight = (
                    relu(upper_weight) @ prev_linb.upper_weight - relu(-upper_weight) @ prev_linb.lower_weight
                )

        # Insert the initial boxes into the linear bounds
        ilb, iub = self.initial_box.lb, self.initial_box.ub
        lb = relu(lower_weight) @ ilb - relu(-lower_weight) @ iub + lower_bias
        ub = relu(upper_weight) @ iub - relu(-upper_weight) @ ilb + upper_bias

        self.prev_box = Box(lb, ub)

    def propagate_linear(self, linear: nn.Linear, layer_number: int):
        if layer_number not in self.linear_bounds.keys():  # only set bounds in first propagation
            W = linear.weight
            b = linear.bias
            linear_bound = LinearBound(W, W, b, b)
            self.linear_bounds[layer_number] = linear_bound

        self.backsubstitute(layer_number)

    def propagate_conv(self, conv: nn.Conv2d, layer_number: int):
        if layer_number not in self.linear_bounds.keys():  # only set bounds in first propagation
            x = torch.rand(conv.input_shape)
            J = jacobian(conv, x)  # convenient to avoid building W manually, but loses exactness due to autodiff
            W = J.reshape(conv.out_features, conv.in_features)
            # Conv2d saves bias as a tensor of shape (out_channels,)
            b = conv.bias.repeat_interleave(conv.out_features // conv.out_channels) if conv.bias is not None else None
            linear_bound = LinearBound(W, W, b, b)
            self.linear_bounds[layer_number] = linear_bound

        self.backsubstitute(layer_number)

    def propagate_relu(self, relu: Union[nn.LeakyReLU, nn.ReLU], layer_number: int):
        slope = relu.negative_slope
        box = self.prev_box
        prev_lb, prev_ub = box.lb, box.ub

        ## set bounds for prev_lb >= 0 and prev_ub <= 0
        L_diag = 1.0 * (prev_lb >= 0) + slope * (prev_ub <= 0)
        U_diag = 1.0 * (prev_lb >= 0) + slope * (prev_ub <= 0)

        ## set bounds for crossing, i.e. prev_lb < 0 < prev_ub
        lmbda = (prev_ub - slope * prev_lb) / (prev_ub - prev_lb)
        b = (slope - 1) * prev_lb * prev_ub / (prev_ub - prev_lb)
        alpha = self.alphas[layer_number]
        crossing_selector = (prev_lb < 0) & (prev_ub > 0)
        if slope <= 1:
            bound_slope = sigmoid(alpha) * (1 - slope) + slope  # slope needs to be in [slope, 1]
            assert torch.all((slope <= bound_slope) & (bound_slope <= 1))
            L_diag += bound_slope * crossing_selector
            U_diag += lmbda * crossing_selector  # tightest possible linear upper bound
            l = torch.zeros_like(b)
            u = b * crossing_selector
        else:
            bound_slope = sigmoid(alpha) * (slope - 1) + 1  # slope needs to be in [1, slope]
            L_diag += lmbda * crossing_selector  # tightest possible linear lower bound
            U_diag += bound_slope * crossing_selector
            l = b * crossing_selector
            u = torch.zeros_like(b)

        linear_bound = LinearBound(L_diag, U_diag, l, u, is_diag=True)
        self.linear_bounds[layer_number] = linear_bound

        # no need to backsubstitute as concrete bounds are only used in relu propagation; relu is never followed by relu

    def propagate(self) -> Box:
        for i, layer in enumerate(self.model):
            if isinstance(layer, nn.Linear):
                self.propagate_linear(layer, layer_number=i)
            elif isinstance(layer, nn.Conv2d):
                self.propagate_conv(layer, layer_number=i)
            elif isinstance(layer, nn.Flatten):
                continue
            elif isinstance(layer, (nn.ReLU, nn.LeakyReLU)):
                self.propagate_relu(layer, layer_number=i)
            else:
                raise NotImplementedError(f"Unsupported layer type: {type(layer)}")
        return self.prev_box

    def optimize(self, timeout: int = 5) -> bool:
        """
        Optimizes the slopes of the relu approximation

        Args:
            timeout: the time in minutes until the optimization it aborted and not verified is returned
        """
        params = self.alphas.values()
        optimizer = torch.optim.Adam(params, lr=1)
        start_time = time()
        while time() - start_time < timeout * 60:
            optimizer.zero_grad()
            box = self.propagate()
            if box.check_postcondition():
                return True
            lb = box.lb
            loss = relu(-lb).sum()
            loss.backward()
            optimizer.step()

        return False

    def verify(self) -> bool:
        if has_relu(self.model):
            return self.optimize()
        else:
            box = self.propagate()
            return box.check_postcondition()


def certify_sample(model, x, y, eps) -> bool:
    preprocess_net(model, x.unsqueeze(0).shape, y)
    dp = DeepPoly(model, x, eps)
    return dp.verify()
