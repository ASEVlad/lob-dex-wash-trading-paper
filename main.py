import os
import subprocess
from pathlib import Path
from loguru import logger

from src.data_handler import CoinDataStore
from src.DataReformator import prepare_postmerge_csv


# ========= CONFIG =========
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / ".." / "data"
R_SCRIPT_PATH = Path("pipeline_wash_trading_paper_enhanced.R").expanduser()
OUTPUT_BASE = BASE_DIR / ".." / "output_r_pipeline"
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

TOKEN_USD_CONST = 1.0
ETH_USD_CONST = 3500.0
PRICE_IS_TOKEN_IN_ETH = False

# Default R arguments
SCC_THRESHOLD_RANK = 100
WASH_TRADE_DETECTION_ETHER = "FALSE"     # or "TRUE" if you want Ether detection
WASH_TRADE_DETECTION_MARGIN = 0.01
WASH_WINDOW_SIZE_1 = 3600
WASH_WINDOW_SIZE_2 = 86400
WASH_WINDOW_SIZE_3 = 604800
# ===========================


def run_r_pipeline(prepared_csv: Path, token: str):
    """Run R script for a single token using subprocess."""
    output_folder = (OUTPUT_BASE / f"{token}_output").resolve()
    output_folder.mkdir(parents=True, exist_ok=True)

    cmd = [
        "Rscript",
        str(R_SCRIPT_PATH),
        "--dex", "HyperLiquid",
        "--trades", str(prepared_csv),
        "--output", str(output_folder),
        "--sccthresholdrank", str(SCC_THRESHOLD_RANK),
        "--washdetectionether", WASH_TRADE_DETECTION_ETHER,
        "--margin", str(WASH_TRADE_DETECTION_MARGIN),
        "--washwindowsizesecondspass1", str(WASH_WINDOW_SIZE_1),
        "--washwindowsizesecondspass2", str(WASH_WINDOW_SIZE_2),
        "--washwindowsizesecondspass3", str(WASH_WINDOW_SIZE_3)
    ]

    logger.info(f"Running R pipeline for {token}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    (output_folder / "R_stdout.log").write_text(result.stdout)
    (output_folder / "R_stderr.log").write_text(result.stderr)

    if result.returncode == 0:
        logger.info(f"[{token}] ✅ Finished successfully")
    else:
        logger.error(f"[{token}] ❌ Failed (code {result.returncode}) — check logs in {output_folder}")


def main():
    logger.add("run_r_pipeline.log", rotation="2 MB", level="INFO")
    tokens = os.listdir(DATA_DIR)

    logger.info(f"Found {len(tokens)} tokens: {tokens}")

    for token in tokens:
        try:
            if token != "AVAX":
                continue

            logger.info(f"=== Processing token: {token} ===")

            store = CoinDataStore(token, engine="fastparquet")
            df_trades = store.load_all()

            prepared_csv = (OUTPUT_BASE / f"{token}_compatible_trades.csv").resolve()

            prepare_postmerge_csv(
                df_trades,
                out_csv=str(prepared_csv),
                token_id=token,
                token_usd_const=TOKEN_USD_CONST,
                eth_usd_const=ETH_USD_CONST,
                price_is_token_in_eth=PRICE_IS_TOKEN_IN_ETH,
            )

            logger.info(f"[{token}] Prepared compatible CSV at {prepared_csv}")
            run_r_pipeline(prepared_csv, token)

        except Exception as e:
            logger.exception(f"[{token}] Error during processing: {e}")

    logger.info("All tokens processed.")


if __name__ == "__main__":
    main()
