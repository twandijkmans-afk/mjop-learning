"""Drempels en modelparameters van de Photo Walk-meetkern.

ALLE waarden hier zijn PROVISIONAL_UNVALIDATED: het zijn technische startwaarden voor poorten (gates) en een
ruismodel, geen bewezen meettoleranties. Ze zijn niet gekalibreerd op echte gevels of op een fysiek toestel.
Een gate die slaagt bewijst dus GEEN nauwkeurigheid; hij sluit alleen bekende foutsituaties uit.
Wijzigen van een waarde = nieuwe `processing_version` (zie PROCESSING_VERSION).
"""
from dataclasses import asdict, dataclass

MEASUREMENT_METHOD_VERSION = "photo_walk_levels_ABC_v1"
PROCESSING_VERSION = "photo_walk_core_0.1.0"


@dataclass(frozen=True)
class Config:
    threshold_status: str = "PROVISIONAL_UNVALIDATED"
    # buitenmaat-bereik (gelijk aan bruto_quantity_concepts_v2)
    min_dim_m: float = 0.10
    max_dim_m: float = 10.0
    # ruismodel voor onzekerheid (modelgebaseerd, niet gevalideerd)
    corner_pixel_sigma_px: float = 1.5
    depth_noise_floor_m: float = 0.01
    plane_effective_samples_cap: int = 50
    mc_samples: int = 200
    # niveau A: diepte
    depth_min_range_m: float = 0.3
    depth_max_range_m: float = 5.0
    annulus_inner_scale: float = 1.08
    annulus_outer_scale: float = 1.8
    annulus_min_points: int = 60
    annulus_min_valid_fraction: float = 0.35
    plane_ransac_threshold_m: float = 0.02
    plane_ransac_iterations: int = 200
    plane_min_inlier_ratio: float = 0.6
    plane_max_rms_m: float = 0.02
    min_incidence_cos: float = 0.35          # |cos| tussen straal en vlaknormaal; kleiner = te schuin
    rect_angle_tol_deg: float = 6.0
    rect_edge_ratio_tol: float = 0.05
    corner_depth_tol_m: float = 0.08
    corner_depth_block_m: float = 0.25       # >= 3 hoeken zo ver van het vlak: waarschijnlijk verkeerd vlak gekozen
    glass_inner_scale: float = 0.85
    glass_min_valid_fraction: float = 0.5
    glass_beyond_plane_m: float = 0.30
    glass_max_beyond_fraction: float = 0.25
    # meerdere standpunten
    consistency_k: float = 3.0
    # niveau B: triangulatie
    min_triangulation_angle_deg: float = 4.0
    max_reproj_px: float = 3.0
    max_corner_planarity_m: float = 0.05
    # niveau C: referentie
    ref_plane_tol_m: float = 0.05
    ref_orthogonality_tol: float = 0.08
    scale_verify_tol: float = 0.03
    # associatie / dekking
    assoc_center_gate_factor: float = 0.5   # x min(breedte, hoogte)
    assoc_normal_angle_deg: float = 15.0
    assoc_plane_offset_m: float = 0.15
    coverage_cell_m: float = 0.5
    coverage_min_incidence_cos: float = 0.5
    min_overlap_fraction: float = 0.2

    def as_dict(self):
        return asdict(self)


DEFAULT = Config()
