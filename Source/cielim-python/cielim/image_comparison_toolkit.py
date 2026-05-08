import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

THRESHOLD = 10


def load_grayscale(path):
    return np.array(Image.open(path).convert("L"))


def compute_disk_stats(img, threshold=THRESHOLD):
    pixels = img[img > threshold]
    return {
        "pixels": pixels,
        "mean": np.mean(pixels),
        "std": np.std(pixels),
    }


def plot_histogram(img1, img2, title1="img1", title2="img2", bins=256):
    s1 = compute_disk_stats(img1)
    s2 = compute_disk_stats(img2)

    bin_edges = np.linspace(0, 255, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    counts1, _ = np.histogram(img1.flatten(), bins=bins, range=(0, 255))
    counts2, _ = np.histogram(img2.flatten(), bins=bins, range=(0, 255))

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle("Pixel Intensity Distribution & Disk Statistics", fontsize=14, fontweight="bold")

    ax.fill_between(bin_centers, counts1, alpha=0.4, color="red", label=title1)
    ax.fill_between(bin_centers, counts2, alpha=0.4, color="blue", label=title2)
    ax.step(bin_centers, counts1, color="darkred", alpha=0.9, linewidth=1.0)
    ax.step(bin_centers, counts2, color="darkblue", alpha=0.9, linewidth=1.0)

    ax.axvline(s1["mean"], color="darkred", linewidth=2, linestyle="--", label=f"{title1} mean: {s1['mean']:.1f}")
    ax.axvline(s2["mean"], color="darkblue", linewidth=2, linestyle="--", label=f"{title2} mean: {s2['mean']:.1f}")
    ax.axvspan(
        s1["mean"] - s1["std"], s1["mean"] + s1["std"], alpha=0.1, color="red", label=f"{title1} ±1σ: {s1['std']:.1f}"
    )
    ax.axvspan(
        s2["mean"] - s2["std"], s2["mean"] + s2["std"], alpha=0.1, color="blue", label=f"{title2} ±1σ: {s2['std']:.1f}"
    )

    ax.set_yscale("log")
    ax.set_xlabel("Pixel Intensity (0–255)", fontsize=12)
    ax.set_ylabel("Number of Pixels (log scale)", fontsize=12)
    ax.set_xlim(0, 255)
    ax.legend(fontsize=10)

    plt.tight_layout()
    return fig


def plot_difference(img1, img2, title1="img1", title2="img2", bins=256):
    s1 = compute_disk_stats(img1)
    s2 = compute_disk_stats(img2)

    bin_edges = np.linspace(0, 255, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    counts1, _ = np.histogram(s1["pixels"], bins=bins, range=(0, 255))
    counts2, _ = np.histogram(s2["pixels"], bins=bins, range=(0, 255))
    diff = counts1.astype(int) - counts2.astype(int)
    pos_mask = diff >= 0
    neg_mask = diff < 0

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle(f"Histogram Difference — {title1} vs {title2}", fontsize=14, fontweight="bold")

    ax.bar(bin_centers[pos_mask], diff[pos_mask], width=1.0, color="red", alpha=0.8, label=f"{title1} > {title2}")
    ax.bar(bin_centers[neg_mask], diff[neg_mask], width=1.0, color="blue", alpha=0.8, label=f"{title2} > {title1}")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Pixel Intensity (0–255)", fontsize=12)
    ax.set_ylabel(f"Count Difference ({title1} − {title2})", fontsize=12)
    ax.set_xlim(0, 255)
    ax.legend(fontsize=10)

    plt.tight_layout()
    return fig


def match_shapes(img1, img2):
    if img1.shape != img2.shape:
        img2 = np.array(Image.fromarray(img2).resize((img1.shape[1], img1.shape[0]), Image.BILINEAR))
    return img1, img2


def plot_diff_heatmap(img1, img2, title1="img1", title2="img2"):
    img1, img2 = match_shapes(img1, img2)
    mask = (img1 > THRESHOLD) | (img2 > THRESHOLD)
    diff = np.zeros_like(img1, dtype=float)
    diff[mask] = img1[mask].astype(float) - img2[mask].astype(float)

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.suptitle(f"Pixel Difference Heatmap — {title1} minus {title2}", fontsize=13, fontweight="bold")

    im = ax.imshow(diff, cmap="RdBu", vmin=-128, vmax=128)
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(f"Intensity Difference ({title1} − {title2})", fontsize=10)

    ax.set_title(f"Red = {title1} brighter  |  Blue = {title2} brighter  |  White = no difference", fontsize=9)
    ax.axis("off")

    plt.tight_layout()
    return fig


def generate_plots(img1, img2, output_dir, title1="img1", title2="img2", align=False, reference=1):
    """
    reference=1 means img1 is the reference for alignment (default).
    reference=2 means img2 is the reference.
    """
    from pathlib import Path
    import numpy as np

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not isinstance(img1, np.ndarray):
        img1 = load_grayscale(img1)
    if not isinstance(img2, np.ndarray):
        img2 = load_grayscale(img2)

    fig1 = plot_histogram(img1, img2, title1=title1, title2=title2)
    fig1.savefig(output_dir / "histogram.png", dpi=150, bbox_inches="tight")
    plt.close(fig1)

    fig2 = plot_difference(img1, img2, title1=title1, title2=title2)
    fig2.savefig(output_dir / "histogram_difference.png", dpi=150, bbox_inches="tight")
    plt.close(fig2)

    fig3 = plot_diff_heatmap(img1, img2, title1=title1, title2=title2)
    fig3.savefig(output_dir / "heatmap_diff.png", dpi=150, bbox_inches="tight")
    plt.close(fig3)

    if align:
        if reference == 1:
            fig4, shift_y, shift_x = plot_alignment(img1, img2, title1=title1, title2=title2)
        else:
            fig4, shift_y, shift_x = plot_alignment(img2, img1, title1=title2, title2=title1)
        fig4.savefig(output_dir / "alignment.png", dpi=150, bbox_inches="tight")
        plt.close(fig4)


def cross_correlate_fft(img1, img2):
    i1 = img1.astype(float) - img1.mean()
    i2 = img2.astype(float) - img2.mean()
    corr = np.fft.ifftshift(np.real(np.fft.ifft2(np.fft.fft2(i1) * np.conj(np.fft.fft2(i2)))))
    peak = np.unravel_index(np.argmax(corr), corr.shape)
    shift_y = peak[0] - corr.shape[0] // 2
    shift_x = peak[1] - corr.shape[1] // 2
    return shift_y, shift_x, corr


def apply_shift(img, shift_y, shift_x):
    return np.roll(np.roll(img, shift_y, axis=0), shift_x, axis=1)


def plot_alignment(img1, img2, title1="img1", title2="img2"):
    img1, img2 = match_shapes(img1, img2)

    shift_y, shift_x, corr = cross_correlate_fft(img1, img2)
    img2_aligned = apply_shift(img2, shift_y, shift_x)

    mask_b = (img1 > THRESHOLD) | (img2 > THRESHOLD)
    diff_before = np.zeros_like(img1, dtype=float)
    diff_before[mask_b] = img1[mask_b].astype(float) - img2[mask_b].astype(float)

    mask_a = (img1 > THRESHOLD) | (img2_aligned > THRESHOLD)
    diff_after = np.zeros_like(img1, dtype=float)
    diff_after[mask_a] = img1[mask_a].astype(float) - img2_aligned[mask_a].astype(float)

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle(
        f"Cross-Correlation Alignment\n"
        f"Reference: {title1}  |  Aligned: {title2}  |  "
        f"Offset — i (x): {shift_x}px,  j (y): {shift_y}px",
        fontsize=13,
        fontweight="bold",
    )

    axes[0, 0].imshow(img1, cmap="gray", vmin=0, vmax=255)
    axes[0, 0].set_title(f"{title1}\n(reference)", fontsize=11)
    axes[0, 0].axis("off")

    axes[0, 1].imshow(img2, cmap="gray", vmin=0, vmax=255)
    axes[0, 1].set_title(f"{title2} — before alignment", fontsize=11)
    axes[0, 1].axis("off")

    axes[0, 2].imshow(img2_aligned, cmap="gray", vmin=0, vmax=255)
    axes[0, 2].set_title(f"{title2} — after alignment\n(i={shift_x}px, j={shift_y}px)", fontsize=11)
    axes[0, 2].axis("off")

    ax_vec = axes[1, 0]
    lim = max(abs(shift_x), abs(shift_y), 10) * 1.5
    ax_vec.set_xlim(-lim, lim)
    ax_vec.set_ylim(-lim, lim)
    ax_vec.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax_vec.axvline(0, color="gray", linewidth=0.8, linestyle="--")
    ax_vec.annotate("", xy=(shift_x, 0), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="blue", lw=2))
    ax_vec.annotate("", xy=(0, -shift_y), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="red", lw=2))
    ax_vec.annotate("", xy=(shift_x, -shift_y), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="green", lw=2.5))
    ax_vec.plot(shift_x, -shift_y, "go", markersize=8)
    ax_vec.text(shift_x + lim * 0.05, lim * 0.05, f"i={shift_x}px", color="blue", fontsize=10)
    ax_vec.text(lim * 0.05, -shift_y + lim * 0.05, f"j={shift_y}px", color="red", fontsize=10)
    ax_vec.text(shift_x + lim * 0.05, -shift_y + lim * 0.05, f"({shift_x}, {shift_y})", color="green", fontsize=9)
    ax_vec.set_title(f"Offset vector\n{title2} → {title1}", fontsize=11)
    ax_vec.set_xlabel("i (x shift) px")
    ax_vec.set_ylabel("j (y shift) px")
    ax_vec.set_aspect("equal")
    ax_vec.grid(True, alpha=0.3)

    im1 = axes[1, 1].imshow(diff_before, cmap="RdBu", vmin=-128, vmax=128)
    plt.colorbar(im1, ax=axes[1, 1], fraction=0.046, pad=0.04)
    axes[1, 1].set_title(f"Heatmap — BEFORE alignment\n({title1} − {title2})", fontsize=11)
    axes[1, 1].axis("off")

    im2 = axes[1, 2].imshow(diff_after, cmap="RdBu", vmin=-128, vmax=128)
    plt.colorbar(im2, ax=axes[1, 2], fraction=0.046, pad=0.04)
    axes[1, 2].set_title(f"Heatmap — AFTER alignment\n({title1} − {title2} aligned)", fontsize=11)
    axes[1, 2].axis("off")

    plt.tight_layout()
    return fig, shift_y, shift_x
