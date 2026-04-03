from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .preprocessing import PreprocessedData, ERA_ORDER
from .tmdb_service import Movie


@dataclass
class ClusterInfo:
    """Information about a single cluster."""
    cluster_id: int
    size: int
    dominant_language: str
    language_distribution: Dict[str, int]
    top_genres: List[str]
    genre_scores: Dict[str, float]
    era: str
    era_distribution: Dict[str, int]
    movie_ids: List[int] = field(default_factory=list)

    def to_dict(self, include_movies: bool = False) -> Dict:
        result = {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "dominant_language": self.dominant_language,
            "language_distribution": self.language_distribution,
            "top_genres": self.top_genres,
            "era": self.era,
            "era_distribution": self.era_distribution
        }
        if include_movies:
            result["movie_ids"] = self.movie_ids
        return result


@dataclass
class ClusteringResult:
    """Complete clustering result with all clusters and metadata."""
    algorithm: str
    n_clusters: int
    clusters: List[ClusterInfo]
    labels: np.ndarray
    metrics: Dict = field(default_factory=dict)
    movies_by_cluster: Dict[int, List[Movie]] = field(default_factory=dict)

    def get_cluster(self, cluster_id: int) -> Optional[ClusterInfo]:
        """Get cluster info by ID."""
        for c in self.clusters:
            if c.cluster_id == cluster_id:
                return c
        return None

    def get_movies_in_cluster(self, cluster_id: int) -> List[Movie]:
        """Get all movies in a specific cluster."""
        return self.movies_by_cluster.get(cluster_id, [])

    def to_dict(self, include_movies: bool = False) -> Dict:
        return {
            "algorithm": self.algorithm,
            "n_clusters": self.n_clusters,
            "clusters": [c.to_dict(include_movies) for c in self.clusters],
            "metrics": self.metrics
        }


class MovieClusterer:
    def __init__(
        self,
        k_range: Tuple[int, int] = (3, 15),
        random_state: int = 42,
        scale_features: bool = True
    ):
        
        self.k_range = k_range
        self.random_state = random_state
        self.scale_features = scale_features
        self.scaler = StandardScaler() if scale_features else None

        # State
        self._preprocessed_data: Optional[PreprocessedData] = None
        self._scaled_features: Optional[np.ndarray] = None
        self._current_result: Optional[ClusteringResult] = None

    def _prepare_features(self, data: PreprocessedData) -> np.ndarray:
        """Scale features if enabled."""
        self._preprocessed_data = data

        if self.scale_features:
            self._scaled_features = self.scaler.fit_transform(data.features)
            return self._scaled_features
        return data.features

    def find_optimal_k(
        self,
        data: PreprocessedData,
        method: str = "silhouette"
    ) -> Tuple[int, Dict]:
        features = self._prepare_features(data)
        k_min, k_max = self.k_range

        inertias = []
        silhouettes = []
        k_values = list(range(k_min, min(k_max + 1, len(data.movies) // 5)))

        print(f"[clustering] Evaluating K from {k_min} to {max(k_values)}...")

        for k in k_values:
            kmeans = KMeans(
                n_clusters=k,
                random_state=self.random_state,
                n_init=10,
                max_iter=300
            )
            labels = kmeans.fit_predict(features)
            inertias.append(kmeans.inertia_)

            if k > 1:
                sil = silhouette_score(features, labels)
                silhouettes.append(sil)
            else:
                silhouettes.append(0)

        # Determine optimal K based on method
        if method == "silhouette":
            # Find K with highest silhouette score
            best_idx = np.argmax(silhouettes)
            optimal_k = k_values[best_idx]
        else:
            # Elbow method: find the "knee" point
            optimal_k = self._find_elbow(k_values, inertias)

        analysis = {
            "method": method,
            "k_values": k_values,
            "inertias": inertias,
            "silhouettes": silhouettes,
            "optimal_k": optimal_k,
            "best_silhouette": float(silhouettes[k_values.index(optimal_k)])
        }

        print(f"[clustering] Optimal K={optimal_k} (silhouette={analysis['best_silhouette']:.3f})")
        return optimal_k, analysis

    def _find_elbow(self, k_values: List[int], inertias: List[float]) -> int:
        """Find elbow point using the perpendicular distance method."""
        if len(k_values) < 3:
            return k_values[0]

        # Normalize coordinates
        x = np.array(k_values, dtype=float)
        y = np.array(inertias, dtype=float)

        x_norm = (x - x.min()) / (x.max() - x.min() + 1e-8)
        y_norm = (y - y.min()) / (y.max() - y.min() + 1e-8)

        # Line from first to last point
        p1 = np.array([x_norm[0], y_norm[0]])
        p2 = np.array([x_norm[-1], y_norm[-1]])

        # Find point with maximum perpendicular distance
        max_dist = 0
        elbow_idx = 0

        for i in range(len(k_values)):
            p = np.array([x_norm[i], y_norm[i]])
            dist = np.abs(np.cross(p2 - p1, p1 - p)) / np.linalg.norm(p2 - p1)
            if dist > max_dist:
                max_dist = dist
                elbow_idx = i

        return k_values[elbow_idx]

    def cluster_kmeans(
        self,
        data: PreprocessedData,
        n_clusters: int = None,
        auto_k: bool = True
    ) -> ClusteringResult:
        features = self._prepare_features(data)

        # Determine K
        if n_clusters is None and auto_k:
            n_clusters, k_analysis = self.find_optimal_k(data, method="silhouette")
        elif n_clusters is None:
            n_clusters = 8  # Default

        print(f"[clustering] Running KMeans with K={n_clusters}...")

        # Fit KMeans
        kmeans = KMeans(
            n_clusters=n_clusters,
            random_state=self.random_state,
            n_init=10,
            max_iter=300
        )
        labels = kmeans.fit_predict(features)

        # Calculate metrics
        silhouette = silhouette_score(features, labels) if n_clusters > 1 else 0

        # Build result
        result = self._build_result(
            data=data,
            labels=labels,
            algorithm="kmeans",
            metrics={
                "silhouette_score": float(silhouette),
                "inertia": float(kmeans.inertia_),
                "n_iterations": kmeans.n_iter_
            }
        )

        self._current_result = result
        return result

    def cluster_dbscan(
        self,
        data: PreprocessedData,
        eps: float = 0.5,
        min_samples: int = 5
    ) -> ClusteringResult:
        features = self._prepare_features(data)

        print(f"[clustering] Running DBSCAN (eps={eps}, min_samples={min_samples})...")

        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        labels = dbscan.fit_predict(features)

        # Count clusters (excluding noise label -1)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = np.sum(labels == -1)

        # Calculate silhouette (only if we have valid clusters)
        silhouette = 0
        if n_clusters > 1:
            # Exclude noise points for silhouette calculation
            mask = labels != -1
            if np.sum(mask) > n_clusters:
                silhouette = silhouette_score(features[mask], labels[mask])

        print(f"[clustering] DBSCAN found {n_clusters} clusters, {n_noise} noise points")

        result = self._build_result(
            data=data,
            labels=labels,
            algorithm="dbscan",
            metrics={
                "silhouette_score": float(silhouette),
                "n_noise_points": int(n_noise),
                "eps": eps,
                "min_samples": min_samples
            }
        )

        self._current_result = result
        return result

    def _build_result(
        self,
        data: PreprocessedData,
        labels: np.ndarray,
        algorithm: str,
        metrics: Dict
    ) -> ClusteringResult:
        """Build clustering result with cluster interpretation."""
        df = data.df.copy()
        df["cluster"] = labels

        # Group movies by cluster
        unique_labels = sorted(set(labels))
        if -1 in unique_labels:
            unique_labels.remove(-1)  # Exclude DBSCAN noise

        clusters: List[ClusterInfo] = []
        movies_by_cluster: Dict[int, List[Movie]] = {}

        for cluster_id in unique_labels:
            cluster_df = df[df["cluster"] == cluster_id]
            cluster_movies = [m for m in data.movies if m.id in cluster_df["movie_id"].tolist()]

            movies_by_cluster[cluster_id] = cluster_movies

            # Interpret cluster
            cluster_info = self._interpret_cluster(
                cluster_id=cluster_id,
                cluster_df=cluster_df,
                genre_map=data.genre_map
            )
            clusters.append(cluster_info)

        return ClusteringResult(
            algorithm=algorithm,
            n_clusters=len(clusters),
            clusters=clusters,
            labels=labels,
            metrics=metrics,
            movies_by_cluster=movies_by_cluster
        )

    def _interpret_cluster(
        self,
        cluster_id: int,
        cluster_df,
        genre_map: Dict[int, str]
    ) -> ClusterInfo:
        """Analyze and interpret cluster characteristics."""
        # Language analysis
        lang_counts = Counter(cluster_df["language_group"])
        dominant_language = lang_counts.most_common(1)[0][0] if lang_counts else "unknown"

        # Genre analysis
        genre_counts: Dict[str, int] = {}
        for genre_ids in cluster_df["genre_ids"]:
            for gid in genre_ids:
                name = genre_map.get(gid, str(gid))
                genre_counts[name] = genre_counts.get(name, 0) + 1

        # Normalize genre scores
        total_movies = len(cluster_df)
        genre_scores = {k: v / total_movies for k, v in genre_counts.items()}
        top_genres = sorted(genre_scores.keys(), key=lambda x: -genre_scores[x])[:5]

        # Era analysis
        era_counts = Counter(cluster_df["era"])
        dominant_era = era_counts.most_common(1)[0][0] if era_counts else "Unknown"

        return ClusterInfo(
            cluster_id=cluster_id,
            size=len(cluster_df),
            dominant_language=dominant_language,
            language_distribution=dict(lang_counts),
            top_genres=top_genres,
            genre_scores=genre_scores,
            era=dominant_era,
            era_distribution=dict(era_counts),
            movie_ids=cluster_df["movie_id"].tolist()
        )

    def get_similar_movies(
        self,
        movie_id: int,
        limit: int = 10
    ) -> List[Movie]:
        if self._current_result is None:
            raise ValueError("No clustering result available. Run clustering first.")

        # Find movie's cluster
        result = self._current_result
        for cluster_id, movies in result.movies_by_cluster.items():
            movie_ids = [m.id for m in movies]
            if movie_id in movie_ids:
                # Return other movies from same cluster
                similar = [m for m in movies if m.id != movie_id]
                # Sort by popularity
                similar.sort(key=lambda m: -m.popularity)
                return similar[:limit]

        return []

    def get_cluster_for_movie(self, movie_id: int) -> Optional[int]:
        """Get cluster ID for a specific movie."""
        if self._current_result is None:
            return None

        for cluster_id, movies in self._current_result.movies_by_cluster.items():
            if movie_id in [m.id for m in movies]:
                return cluster_id
        return None


def auto_cluster(
    data: PreprocessedData,
    algorithm: str = "kmeans",
    **kwargs
) -> ClusteringResult:
    clusterer = MovieClusterer()

    if algorithm == "kmeans":
        return clusterer.cluster_kmeans(data, **kwargs)
    elif algorithm == "dbscan":
        return clusterer.cluster_dbscan(data, **kwargs)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
