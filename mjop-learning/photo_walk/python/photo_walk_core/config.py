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
    # niveau A v2: LiDAR-ruismodel en meervlaks-analyse (PROVISIONAL; te kalibreren met de meetdiagnose-exports van een echt toestel)
    lidar_sigma0_m: float = 0.004
    lidar_sigma1_per_m: float = 0.004         # sigma(z) = sigma0 + sigma1 * z   (diepteruis grows with distance)
    relief_tol_m: float = 0.012               # baksteenreliëf/voegen
    thr_k: float = 2.5                        # inlierdrempel = thr_k * sigma(z) + relief_tol
    ring_inner_scale: float = 1.06
    ring_outer_scale: float = 1.6
    band_lo_scale: float = 0.88               # binnenband (kozijnprofiel) tussen 0,88 en 0,985 x kader
    band_hi_scale: float = 0.985
    band_cluster_min_share: float = 0.35      # een dieptecluster telt mee als het >= dit aandeel van het grootste cluster heeft; het dichtstbijzijnde wint (profiel vóór glas)
    glass_scale: float = 0.70
    max_planes: int = 3
    # gerichte reparatie FACADE_NOT_PLANAR: lokale vlakruis, ondersteuning per zijde, ruimtelijke omvang (PROVISIONAL)
    facade_local_band_k: float = 3.0          # lokale ruis: punten binnen +-k*drempel van het vlak die niet bij een ander herkend vlak horen
    side_min_share: float = 0.05              # een zijde telt als gedekt bij >= dit aandeel van de vlakpunten (en side_min_points)
    facade_min_extent_ratio: float = 0.04     # kleinste in-vlak spreiding >= ratio * diagonaal van het kader (smal profiel/vensterbank is geen gevel)
    unexplained_max: float = 0.6              # max. aandeel ringpunten dat bij geen enkel herkend vlak hoort
    min_plane_points: int = 40
    plane_min_fraction: float = 0.06
    ransac_iterations_v2: int = 150
    max_ransac_points: int = 2500
    facade_min_facing: float = 0.35
    facade_max_vertical: float = 0.35         # |n_y|: verticale wand
    facade_support_min: float = 0.5           # aandeel van de niet door andere structuur verklaarde ringpunten
    facade_rms_k: float = 1.5                 # rms <= facade_rms_k * sigma(z) + 0.008
    ambiguity_ratio: float = 0.6
    min_sides_covered: int = 3
    side_min_points: int = 15
    frame_search_m: float = 0.35
    frame_side_min_points: int = 12
    frame_group_tol_k: float = 1.5
    flush_tol_k: float = 1.2
    corner_tol_k: float = 2.0
    corners_contradict_block: int = 3
    max_support_frames: int = 5
    min_baseline_m: float = 0.02
    min_rotation_deg: float = 1.5
    frame_tol_rel: float = 0.03
    frame_tol_abs_m: float = 0.01
    frame_normal_deg: float = 4.0
    frame_offset_k: float = 2.5
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
