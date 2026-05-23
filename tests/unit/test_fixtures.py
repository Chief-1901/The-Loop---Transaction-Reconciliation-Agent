import hashlib
import tempfile
from pathlib import Path
from recon_agent.data.generate_fixtures import generate_fixtures, DEFECT_VARIANTS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_produces_byte_identical_csv():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        gt1 = generate_fixtures(seed=42, n_txns=100, variant="default",
                                out_dir=Path(t1), ground_truth_dir=Path(t1))
        gt2 = generate_fixtures(seed=42, n_txns=100, variant="default",
                                out_dir=Path(t2), ground_truth_dir=Path(t2))
        assert _sha(Path(t1) / "tracking_db.csv") == _sha(Path(t2) / "tracking_db.csv")
        assert _sha(Path(t1) / "payu_settlements.json") == _sha(Path(t2) / "payu_settlements.json")


def test_different_seed_produces_different_csv():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        generate_fixtures(seed=42, n_txns=100, variant="default",
                          out_dir=Path(t1), ground_truth_dir=Path(t1))
        generate_fixtures(seed=43, n_txns=100, variant="default",
                          out_dir=Path(t2), ground_truth_dir=Path(t2))
        assert _sha(Path(t1) / "tracking_db.csv") != _sha(Path(t2) / "tracking_db.csv")


def test_all_variants_run_without_error():
    for variant in DEFECT_VARIANTS:
        with tempfile.TemporaryDirectory() as t:
            gt = generate_fixtures(seed=42, n_txns=50, variant=variant,
                                   out_dir=Path(t), ground_truth_dir=Path(t))
            assert gt.variant == variant
            assert gt.total_txns == 50
