"""
DatasetLoader — fetches the Zomato dataset from Hugging Face.

Responsibilities
----------------
* Download the raw dataset via the ``datasets`` library.
* Return the raw data as a ``pandas.DataFrame`` for the ``Preprocessor``.
* All caching logic lives in ``Preprocessor``; this module is stateless.

Raw Dataset Schema (ManikaSaini/zomato-restaurant-recommendation)
-----------------------------------------------------------------
Columns observed in the dataset (subject to upstream changes):

    name          str   Restaurant name
    online_order  str   'Yes' / 'No' — whether online ordering is available
    book_table    str   'Yes' / 'No' — whether table booking is available
    rate          str   Rating string, e.g. '4.1/5', 'NEW', '-'
    votes         int   Number of user votes
    location      str   Locality / neighbourhood name
    rest_type     str   Restaurant type (e.g. 'Casual Dining', 'Cafe')
    dish_liked    str   Popular dishes (comma-separated, often null)
    cuisines      str   Cuisine types (comma-separated, e.g. 'North Indian, Chinese')
    approx_cost(for two people)
                  str   Approx cost for two people, e.g. '800', '1,500'
    listed_in(type)
                  str   Meal type (e.g. 'Buffet', 'Delivery')
    listed_in(city)
                  str   City / area listed under

Field Mapping to Restaurant Model
----------------------------------
    name                           → Restaurant.name
    rate                           → Restaurant.rating  (parsed to float)
    votes                          → Restaurant.votes
    location                       → Restaurant.location
    cuisines                       → Restaurant.cuisines (parsed list)
    approx_cost(for two people)    → Restaurant.cost_for_two (parsed float)
    listed_in(city)                → Restaurant.city
    address (if present)           → Restaurant.address
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Canonical Hugging Face dataset identifier
_HF_DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"

# Map from raw column names → normalised internal names used by Preprocessor.
# Columns not listed here are ignored during loading.
COLUMN_RENAMES: dict[str, str] = {
    "name": "name",
    "rate": "rate",
    "votes": "votes",
    "location": "location",
    "cuisines": "cuisines",
    "approx_cost(for two people)": "cost_raw",
    "listed_in(city)": "city",
    # Optional columns — may or may not be present in the dataset
    "address": "address",
    "rest_type": "rest_type",
}


class DatasetLoader:
    """Load the Zomato restaurant dataset from Hugging Face.

    Parameters
    ----------
    dataset_id:
        Hugging Face dataset repository identifier.  Defaults to the
        canonical Zomato dataset used in this project.
    """

    def __init__(self, dataset_id: str = _HF_DATASET_ID) -> None:
        self.dataset_id = dataset_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """Download and return the raw dataset as a DataFrame.

        The returned DataFrame uses normalised column names (see
        ``COLUMN_RENAMES``).  Unknown columns are dropped so the downstream
        ``Preprocessor`` operates on a predictable schema.

        Returns
        -------
        pd.DataFrame
            Raw, un-preprocessed data with normalised column names.

        Raises
        ------
        RuntimeError
            If the ``datasets`` library cannot be imported or the download
            fails after retries.
        """
        try:
            from datasets import load_dataset  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "The 'datasets' package is required.  "
                "Install it with: pip install datasets"
            ) from exc

        logger.info("Downloading dataset '%s' from Hugging Face…", self.dataset_id)
        try:
            hf_dataset = load_dataset(self.dataset_id)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download dataset '{self.dataset_id}': {exc}"
            ) from exc

        # The dataset may have 'train', 'test', 'validation' splits.
        # We concatenate all available splits into a single DataFrame.
        frames: list[pd.DataFrame] = []
        for split_name, split_data in hf_dataset.items():
            df = split_data.to_pandas()
            df["_split"] = split_name
            frames.append(df)
            logger.debug("Loaded split '%s' with %d rows.", split_name, len(df))

        raw_df = pd.concat(frames, ignore_index=True)
        logger.info("Total raw rows loaded: %d", len(raw_df))

        # Rename and select only the columns we care about
        raw_df = self._normalise_columns(raw_df)
        return raw_df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalise_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename raw columns to internal names and drop unknowns."""
        available = {col: norm for col, norm in COLUMN_RENAMES.items() if col in df.columns}
        missing = set(COLUMN_RENAMES.keys()) - set(available.keys())
        if missing:
            logger.warning(
                "The following expected columns were NOT found in the dataset "
                "and will be treated as absent: %s",
                sorted(missing),
            )

        df = df.rename(columns=available)
        # Keep only normalised columns (+ internal _split marker)
        keep = list(available.values()) + ["_split"]
        keep = [c for c in keep if c in df.columns]
        return df[keep].copy()
