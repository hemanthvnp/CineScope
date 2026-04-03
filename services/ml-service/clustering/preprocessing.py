"""
Movie Preprocessing Module

Handles data preprocessing and feature engineering for movie clustering:
- Release date parsing and era bucketing
- Language one-hot encoding
- Genre multi-hot encoding
- Feature vector construction

Era Buckets:
  - Classic: < 1980
  - Old: 1980-1999
  - Modern: 2000-2015
  - Recent: 2016+
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .tmdb_service import Movie


# Era bucket definitions
ERA_BUCKETS = {
    "Classic": (0, 1979),
    "Old": (1980, 1999),
    "Modern": (2000, 2015),
    "Recent": (2016, 9999)
}

ERA_ORDER = ["Classic", "Old", "Modern", "Recent"]


@dataclass
class PreprocessedData:
    """Container for preprocessed movie data and feature matrix."""

    # Original movie data
    movies: List[Movie]

    # DataFrame with processed features
    df: pd.DataFrame

    # Feature matrix for clustering (numpy array)
    features: np.ndarray

    # Feature metadata
    language_columns: List[str] = field(default_factory=list)
    genre_columns: List[str] = field(default_factory=list)
    era_columns: List[str] = field(default_factory=list)

    # Mapping structures
    genre_map: Dict[int, str] = field(default_factory=dict)

    @property
    def feature_names(self) -> List[str]:
        """Return all feature column names."""
        return self.language_columns + self.genre_columns + self.era_columns

    @property
    def n_features(self) -> int:
        """Return total number of features."""
        return len(self.feature_names)


class MoviePreprocessor:
    """
    Preprocesses movie data for clustering.

    Pipeline:
    1. Parse release dates and extract years
    2. Assign era buckets
    3. One-hot encode languages
    4. Multi-hot encode genres
    5. Combine into feature matrix
    """

    def __init__(
        self,
        genre_map: Dict[int, str] = None,
        min_language_count: int = 5,
        fill_missing_year: int = 2000
    ):
        """
        Initialize preprocessor.

        Args:
            genre_map: Mapping of genre_id -> genre_name
            min_language_count: Minimum movies per language (others grouped as 'other')
            fill_missing_year: Default year for missing release_date
        """
        self.genre_map = genre_map or {}
        self.min_language_count = min_language_count
        self.fill_missing_year = fill_missing_year

        # Will be populated during fit
        self.all_languages: List[str] = []
        self.all_genres: List[str] = []
        self._fitted = False

    def _extract_year(self, release_date: str) -> Optional[int]:
        """Extract year from TMDB release_date string (YYYY-MM-DD)."""
        if not release_date or len(release_date) < 4:
            return None
        try:
            return int(release_date[:4])
        except ValueError:
            return None

    def _get_era(self, year: int) -> str:
        """Assign era bucket based on year."""
        for era, (start, end) in ERA_BUCKETS.items():
            if start <= year <= end:
                return era
        return "Recent"  # Default for future years

    def _create_dataframe(self, movies: List[Movie]) -> pd.DataFrame:
        """Convert movie list to pandas DataFrame with basic columns."""
        records = []
        for m in movies:
            year = self._extract_year(m.release_date)
            if year is None:
                year = self.fill_missing_year

            records.append({
                "movie_id": m.id,
                "title": m.title,
                "overview": m.overview,
                "release_date": m.release_date,
                "year": year,
                "era": self._get_era(year),
                "language": m.original_language,
                "genre_ids": m.genre_ids,
                "vote_average": m.vote_average,
                "popularity": m.popularity,
                "poster_path": m.poster_path
            })

        return pd.DataFrame(records)

    def _encode_languages(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        One-hot encode original_language column.

        Languages with count < min_language_count are grouped as 'other'.
        """
        # Count language frequencies
        lang_counts = df["language"].value_counts()

        # Identify frequent languages
        frequent_langs = lang_counts[lang_counts >= self.min_language_count].index.tolist()

        # Map infrequent to 'other'
        df["language_group"] = df["language"].apply(
            lambda x: x if x in frequent_langs else "other"
        )

        # One-hot encode
        lang_dummies = pd.get_dummies(df["language_group"], prefix="lang")
        language_columns = lang_dummies.columns.tolist()

        # Store for later use
        self.all_languages = sorted(df["language_group"].unique())

        return pd.concat([df, lang_dummies], axis=1), language_columns

    def _encode_genres(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Multi-hot encode genre_ids.

        Each genre becomes a binary column (1 if movie has genre, 0 otherwise).
        """
        # Collect all unique genres
        all_genre_ids = set()
        for genres in df["genre_ids"]:
            all_genre_ids.update(genres)

        # Create genre columns
        genre_columns = []
        for genre_id in sorted(all_genre_ids):
            genre_name = self.genre_map.get(genre_id, f"genre_{genre_id}")
            col_name = f"genre_{genre_name}".replace(" ", "_").lower()
            df[col_name] = df["genre_ids"].apply(lambda x: 1 if genre_id in x else 0)
            genre_columns.append(col_name)

        # Store for later use
        self.all_genres = [self.genre_map.get(gid, str(gid)) for gid in sorted(all_genre_ids)]

        return df, genre_columns

    def _encode_eras(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """One-hot encode era buckets."""
        era_dummies = pd.get_dummies(df["era"], prefix="era")

        # Ensure all era columns exist (even if no movies in that era)
        era_columns = []
        for era in ERA_ORDER:
            col = f"era_{era}"
            if col not in era_dummies.columns:
                era_dummies[col] = 0
            era_columns.append(col)

        return pd.concat([df, era_dummies[era_columns]], axis=1), era_columns

    def fit_transform(
        self,
        movies: List[Movie],
        drop_missing_date: bool = False
    ) -> PreprocessedData:
        """
        Fit preprocessor and transform movie data.

        Args:
            movies: List of Movie objects
            drop_missing_date: If True, drop movies without release_date

        Returns:
            PreprocessedData with feature matrix
        """
        if not movies:
            raise ValueError("No movies provided for preprocessing")

        print(f"[preprocessing] Processing {len(movies)} movies...")

        # Create base DataFrame
        df = self._create_dataframe(movies)

        # Handle missing release dates
        if drop_missing_date:
            initial_count = len(df)
            df = df[df["release_date"].str.len() >= 4]
            dropped = initial_count - len(df)
            if dropped > 0:
                print(f"[preprocessing] Dropped {dropped} movies with missing release_date")

        # Filter movies with empty fields
        df = df[df["title"].str.len() > 0]
        df = df.reset_index(drop=True)

        # Encode features
        df, language_columns = self._encode_languages(df)
        df, genre_columns = self._encode_genres(df)
        df, era_columns = self._encode_eras(df)

        # Build feature matrix
        feature_columns = language_columns + genre_columns + era_columns
        features = df[feature_columns].values.astype(np.float32)

        self._fitted = True

        print(f"[preprocessing] Created feature matrix: {features.shape}")
        print(f"  - Languages: {len(language_columns)}")
        print(f"  - Genres: {len(genre_columns)}")
        print(f"  - Eras: {len(era_columns)}")

        # Filter movies list to match DataFrame after drops
        movie_ids = set(df["movie_id"].tolist())
        filtered_movies = [m for m in movies if m.id in movie_ids]

        return PreprocessedData(
            movies=filtered_movies,
            df=df,
            features=features,
            language_columns=language_columns,
            genre_columns=genre_columns,
            era_columns=era_columns,
            genre_map=self.genre_map
        )

    def get_era_distribution(self, df: pd.DataFrame) -> Dict[str, int]:
        """Get count of movies per era."""
        return df["era"].value_counts().to_dict()

    def get_language_distribution(self, df: pd.DataFrame) -> Dict[str, int]:
        """Get count of movies per language."""
        return df["language_group"].value_counts().to_dict()

    def get_genre_distribution(self, df: pd.DataFrame) -> Dict[str, int]:
        """Get count of movies per genre."""
        genre_counts = {}
        for genre_ids in df["genre_ids"]:
            for gid in genre_ids:
                name = self.genre_map.get(gid, str(gid))
                genre_counts[name] = genre_counts.get(name, 0) + 1
        return dict(sorted(genre_counts.items(), key=lambda x: -x[1]))


def summarize_preprocessed_data(data: PreprocessedData) -> Dict:
    """Generate summary statistics for preprocessed data."""
    df = data.df

    return {
        "total_movies": len(df),
        "features": {
            "total": data.n_features,
            "languages": len(data.language_columns),
            "genres": len(data.genre_columns),
            "eras": len(data.era_columns)
        },
        "era_distribution": df["era"].value_counts().to_dict(),
        "language_distribution": df["language_group"].value_counts().head(10).to_dict(),
        "year_range": {
            "min": int(df["year"].min()),
            "max": int(df["year"].max())
        }
    }
