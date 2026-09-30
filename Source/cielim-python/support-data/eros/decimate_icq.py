"""
Decimate an implicitly connected quadrilateral (ICQ) shape model OBJ and weld it into a closed mesh.

An N-ICQ model is six cube faces of (N + 1) x (N + 1) vertices, stored face by face, row major. Keeping
every ``step``-th grid line gives an (N / step)-ICQ. The six faces share their edge vertices, stored
once per face and, in the Eros model, up to 3.2 m apart, so vertices within ``weld_distance`` are
merged to close the seams (the 128ICQ's closest distinct vertices are 30 m apart). The quads are split along the
(i, j)-(i + 1, j + 1) diagonal with the source's winding.

eros_normalized is the 512ICQ Eros model (Gaskell, in the corto S01_Eros inputs), which registers to
it at IoU > 0.996 with no axis change. ErosICQ128.obj was made with

    python decimate_icq.py 433_Eros_512ICQ.obj ErosICQ128.obj --step 4
"""

import argparse

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def decimate_icq(vertices, resolution, step, weld_distance=0.005):
    """
    Vertices (6 (N+1)^2, 3) of an N-ICQ model to the welded vertices and triangles of the (N/step)-ICQ.

    weld_distance is in the model's units (km for the Eros model).
    """
    if resolution % step:
        raise ValueError(f"step {step} does not divide the ICQ resolution {resolution}")
    grid = vertices.reshape(6, resolution + 1, resolution + 1, 3)[:, ::step, ::step]
    size = grid.shape[1]
    flat = grid.reshape(-1, 3)

    index = np.arange(6 * size * size).reshape(6, size, size)
    corner, below, diagonal, right = index[:, :-1, :-1], index[:, 1:, :-1], index[:, 1:, 1:], index[:, :-1, 1:]
    faces = np.concatenate(
        [np.stack([corner, below, diagonal], -1).reshape(-1, 3), np.stack([corner, diagonal, right], -1).reshape(-1, 3)]
    )

    pairs = cKDTree(flat).query_pairs(weld_distance, output_type="ndarray")
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(flat), len(flat)))
    _, inverse = connected_components(graph, directed=False)
    _, first = np.unique(inverse, return_index=True)
    faces = inverse[faces]
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    return flat[first], faces[keep]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--step", type=int, default=4)
    args = parser.parse_args()

    with open(args.source) as handle:
        vertices = np.array([line.split()[1:4] for line in handle if line.startswith("v ")], float)
    resolution = int(round(np.sqrt(len(vertices) / 6))) - 1
    if 6 * (resolution + 1) ** 2 != len(vertices):
        raise ValueError(f"{len(vertices)} vertices is not an ICQ model")
    welded, faces = decimate_icq(vertices, resolution, args.step)
    with open(args.target, "w") as handle:
        handle.write(f"# {resolution // args.step}ICQ decimated from {resolution}ICQ {args.source}, km\n")
        handle.writelines(f"v {x:.6f} {y:.6f} {z:.6f}\n" for x, y, z in welded)
        handle.writelines(f"f {a + 1} {b + 1} {c + 1}\n" for a, b, c in faces)
    print(f"{len(welded)} vertices, {len(faces)} faces -> {args.target}")


if __name__ == "__main__":
    main()
