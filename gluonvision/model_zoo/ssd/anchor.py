# pylint: disable=unused-import
"""Anchor box generator for SSD detector."""
from __future__ import absolute_import

from mxnet import gluon
import numpy as np
from . import slice_like


class SSDAnchorGenerator(gluon.HybridBlock):
    """Bounding box anchor generator for Single-shot Object Detection.

    Parameters
    ----------
    index : int
        Index of this generator in SSD models, this is required for naming.
    sizes : iterable of floats
        Sizes of anchor boxes.
    ratios : iterable of floats
        Aspect ratios of anchor boxes.
    step : int or float
        Step size of anchor boxes.
    alloc_size : tuple of int
        Allocate size for the anchor boxes as (H, W).
        Usually we generate large enough anchors, e.g. 100x100.
        Later in inference we can have variable input sizes,
        at which time we can crop corresponding anchors from this large
        anchor map so we can skip re-generating anchors for each input.
    offsets : tuple of float
        Center offsets of anchor boxes as (h, w) in range(0, 1).

    """
    def __init__(self, index, im_size, sizes, ratios, step, alloc_size=(128, 128),
                 offsets=(0.5, 0.5), clip=True, **kwargs):
        super(SSDAnchorGenerator, self).__init__(**kwargs)
        assert len(im_size) == 2
        self._im_size = im_size
        self._clip = clip
        self._sizes = (sizes[0], np.sqrt(sizes[0] * sizes[1]))
        self._ratios = ratios
        # self._steps = (step, step)
        anchors = self._generate_anchors(self._sizes, self._ratios, step, alloc_size, offsets)
        self.anchors = self.params.get_constant('anchor_%d'%(index), anchors)

    def _generate_anchors(self, sizes, ratios, step, alloc_size, offsets):
        """Generate anchors for once."""
        assert len(sizes) == 2, "SSD requires sizes to be (size_min, size_max)"
        anchors = []
        for i in range(alloc_size[0]):
            for j in range(alloc_size[1]):
                cy = (i + offsets[0]) * step
                cx = (j + offsets[1]) * step
                # ratio = ratios[0], size = size_min or sqrt(size_min * size_max)
                r = ratios[0]
                anchors.append([cx, cy, sizes[0], sizes[0]])
                anchors.append([cx, cy, sizes[1], sizes[1]])
                # size = sizes[0], ratio = ...
                for r in ratios[1:]:
                    sr = np.sqrt(r)
                    w = sizes[0] * sr
                    h = sizes[0] / sr
                    anchors.append([cx, cy, w, h])
        # self._anchor = np.array(anchors).reshape(1, 1, alloc_size[0], alloc_size[1], -1, 4)
        return np.array(anchors).reshape(1, 1, alloc_size[0], alloc_size[1], -1, 4)

    @property
    def num_depth(self):
        """Number of anchors at each pixel."""
        return len(self._sizes) + len(self._ratios) - 1

    # pylint: disable=arguments-differ
    def hybrid_forward(self, F, x, anchors):
        # anchors = F.array(self._anchor)
        # return anchors[0][0].slice_axis(0, begin=0, end=x.shape[2]).slice_axis(1, begin=0, end=x.shape[2]).reshape((1, -1, 4)).clip(0, 300)
        a = F.Custom(anchors, x, op_type='slice_like', axis=2)
        a = F.Custom(a, x, op_type='slice_like', axis=3)
        a = a.reshape((1, -1, 4))
        if self._clip:
            cx, cy, cw, ch = a.split(axis=-1, num_outputs=4)
            H, W = self._im_size
            a = F.concat(*[cx.clip(0, W), cy.clip(0, H), cw.clip(0, W), ch.clip(0, H)])
        return a.reshape((1, -1, 4))
