from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .tmdb_service import Movie


ERA_BUCKETS = {
    "Classic": (0, 1979),
    "Old": (1980, 1999),
    "Modern": (2000, 2015),
    "Recent": (2016, 9999)
}

ERA_ORDER = ["Classic", "Old", "Modern", "Recent"]


@dataclass
class PreprocessedData:

    movies: List[Movie]
    df: pd.DataFrame
    features: np.ndarray
    language_columns: List[str] = field(default_factory=list)
    genre_columns: List[str] = field(default_factory=list)
    era_columns: List[str] = field(default_factory=list)
    genre_map: Dict[int, str] = field(default_factory=dict)

    @property
    def feature_names(self) -> List[str]:
        return self.language_columns + self.genre_columns + self.era_columns

    @property
    def n_features(self) -> int:
        return len(self.feature_names)


class MoviePreprocessor:

    def __init__(
        self,
        genre_map: Dict[int, str] = None,
        min_language_count: int = 5,
        fill_missing_year: int = 2000
    ):
        self.genre_map = genre_map or {}
        self.min_language_count = min_language_count
        self.fill_missing_year = fill_missing_year
        self.all_languages: List[str] = []
        self.all_genres: List[str] = []
        self._fitted = False

    def _extract_year(self, release_date: str) -> Optional[int]:
        if not release_date or len(release_date) < 4:
            return None
        try:
            return int(release_date[:4])
        except ValueError:
            return None

    def _get_era(self, year: int) -> str:
        for era, (start, end) in ERA_BUCKETS.items():
            if start <= year <= end:
                return era
        return "Recent"

    def _create_dataframe(self, movies: List[Movie]) -> pd.DataFrame:
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
        lang_counts = df["language"].value_counts()
        frequent_langs = lang_counts[lang_counts >= self.min_language_count].index.tolist()
        df["language_group"] = df["language"].apply(
            lambda x: x if x in frequent_langs else "other"
        )
        lang_dummies = pd.get_dummies(df["language_group"], prefix="lang")
        language_columns = lang_dummies.columns.tolist()
        self.all_languages = sorted(df["language_group"].unique())

        return pd.concat([df, lang_dummies], axis=1), language_columns

    def _encode_genres(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        all_genre_ids = set()
        for genres in df["genre_ids"]:
            all_genre_ids.update(genres)

        genre_columns = []
        for genre_id in sorted(all_genre_ids):
            genre_name = self.genre_map.get(genre_id, f"genre_{genre_id}")
            col_name = f"genre_{genre_name}".replace(" ", "_").lower()
            df[col_name] = df["genre_ids"].apply(lambda x: 1 if genre_id in x else 0)
            genre_columns.append(col_name)

        self.all_genres = [self.genre_map.get(gid, str(gid)) for gid in sorted(all_genre_ids)]

        return df, genre_columns

    def _encode_eras(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
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
        if not movies:
            raise ValueError("No movies provided for preprocessing")

        print(f"[preprocessing] Processing {len(movies)} movies...")
        df = self._create_dataframe(movies)
        if drop_missing_date:
            initial_count = len(df)
            df = df[df["release_date"].str.len() >= 4]
            dropped = initial_count - len(df)
            if dropped > 0:
                print(f"[preprocessing] Dropped {dropped} movies with missing release_date")

        df = df[df["title"].str.len() > 0]
        df = df.reset_index(drop=True)

        df, language_columns = self._encode_languages(df)
        df, genre_columns = self._encode_genres(df)
        df, era_columns = self._encode_eras(df)

        feature_columns = language_columns + genre_columns + era_columns
        features = df[feature_columns].values.astype(np.float32)

        self._fitted = True

        print(f"[preprocessing] Created feature matrix: {features.shape}")
        print(f"  - Languages: {len(language_columns)}")
        print(f"  - Genres: {len(genre_columns)}")
        print(f"  - Eras: {len(era_columns)}")

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


def summarize_preprocessed_data(data: PreprocessedData) -> Dict:
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
