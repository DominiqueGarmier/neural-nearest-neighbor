from __future__ import annotations

from typing import Annotated

import torch
import torch.nn as nn
import torch.nn.functional as F
from einops import einsum

__all__ = [
    'NKNN',
]


def _compute_omega(
    s: Annotated[torch.Tensor, '*B', 'N'], k: int, t: float
) -> Annotated[torch.Tensor, '*B', 'N', 'K']:
    alpha = F.softmax(s, dim=-1)
    omega = torch.empty(*s.shape, k)

    omega[..., 0] = F.softmax(alpha / t, dim=-1)
    for i in range(1, k):
        alpha = alpha + torch.log(1 - omega[..., i - 1])
        omega[..., i] = F.softmax(alpha / t, dim=-1)

    return omega


class NKNN(nn.Module):
    _k: int
    _temp: float
    _dim: int
    _feature: int

    _no_values: bool = False

    def __init__(
        self, k: int, dim: int, temp: float, feature: int | None = None
    ) -> None:
        super().__init__()
        self._k = k
        self._temp = temp

        self._dim = dim
        self._feature = feature or dim
        if feature is None:
            self._no_values = True

    def _similarity(
        self,
        query: Annotated[torch.Tensor, '*B', 'D'],
        key: Annotated[torch.Tensor, '*B', 'D', 'N'],
    ) -> Annotated[torch.Tensor, '*B', 'N']:
        return -einsum(query, key, '... D, ... D N -> ... N') / (self._dim**0.5)

    def forward(
        self,
        query: Annotated[torch.Tensor, '*B', 'D'],
        keys: Annotated[torch.Tensor, '*B', 'D', 'N'],
        values: Annotated[torch.Tensor, '*B', 'F', 'N'] | None = None,
    ) -> Annotated[torch.Tensor, '*B', 'K', 'F']:
        if values is None:
            assert self._no_values
            values = keys
        assert query.shape[-1] == keys.shape[-2] == self._dim
        assert values.shape[-2] == self._feature
        assert keys.shape[-1] == values.shape[-1]

        sims = self._similarity(query, keys)
        omega = _compute_omega(s=sims, k=self._k, t=self._temp)
        k_nearest = einsum(omega, values, '... N K, ... F N -> ... K F')
        return k_nearest
