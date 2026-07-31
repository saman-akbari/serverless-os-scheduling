import time
from pathlib import Path

import matplotlib.pyplot as plt


def store_figure(root: Path, suffix: str, with_timestamp: bool = True):
    """Stores the current figure in the 'figures' directory."""
    if with_timestamp:
        target_name = time.strftime("%Y-%m-%dT%H:%M:%S") + f"-{suffix}.pdf"
    else:
        target_name = f"{suffix}.pdf"
    target_path = root / "figures" / target_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(target_path)
    plt.close()
