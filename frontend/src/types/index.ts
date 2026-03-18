// Shared TypeScript interfaces for SD City Nature Challenge

export interface Observation {
  id: number;
  species_name: string;
  common_name: string;
  taxon_group: string; // "Plants" | "Birds" | "Insects" | "Reptiles" | ...
  latitude: number;
  longitude: number;
  observed_on: string; // ISO date
  time_of_day: string; // "morning" | "afternoon" | "evening" | "night"
  user_id: string;
  quality_grade: string; // "research" | "needs_id" | "casual"
  city: string; // "San Diego" | "San Antonio" | "Los Angeles"
  contributor_tier?: string | null; // "1" | "2-5" | "6-20" | "21+" for map color-by
}

export interface HexBin {
  hex_id: string;
  center_lat: number;
  center_lng: number;
  observation_count: number;
  unique_species: number;
  biodiversity_yield: number; // unique_species / observation_count
  habitat_type: string;
  priority_score: number; // 0–100
  geometry: GeoJSON.Polygon;
}

export interface SpeciesBreakdownItem {
  species: string;
  count: number;
}

export interface SpeciesSummary {
  taxon_group: string;
  total_species: number;
  total_observations: number;
  top_species: string[];
  species_breakdown?: SpeciesBreakdownItem[]; // Top 9 + Other for drill-down bar
}

export interface CityStats {
  city: string;
  year: number;
  total_observations: number;
  unique_species: number;
  total_participants: number;
  species_per_observer: number;
}

/** Per-city spatial data for comparison maps (center + markers). */
export interface CitySpatial {
  city: string;
  center_lat: number;
  center_lng: number;
  markers: MarkerData[];
}

/** Research-grade and quality breakdown by city. */
export interface CityQuality {
  city: string;
  total: number;
  research_count: number;
  needs_id_count: number;
  casual_count: number;
  research_pct: number;
}

/** Who contributes the most: mean observations per user by city. */
export interface CityContributor {
  city: string;
  user_count: number;
  total_observations: number;
  mean_obs_per_user: number;
}

/** Captive vs wild by city (only wild counts toward CNC). */
export interface CityCaptiveWild {
  city: string;
  wild_count: number;
  captive_count: number;
  wild_pct: number;
  captive_pct: number;
}

/** Competition vs non-competition window comparison. */
export interface CompetitionSplit {
  window: string; // "competition" | "non_competition"
  observations: number;
  unique_species: number;
  participants: number;
  research_pct: number;
  species_per_observation: number;
}

/** Community ranked by observation volume with biodiversity yield. */
export interface CommunityRank {
  community: string;
  observations: number;
  unique_species: number;
  participants: number;
  species_per_observation: number;
}

/** Taxon group split by competition window. */
export interface TaxonComparison {
  taxon_group: string;
  competition_count: number;
  non_competition_count: number;
  total: number;
}

/** Top observed species with count and metadata. */
export interface TopSpeciesComparison {
  scientific_name: string;
  common_name: string;
  count: number;
  taxon_group: string;
}

/** Observation count per taxon group across comparison cities (CNC 2025).
 *  City columns are dynamic (keyed by snake_case city name). */
export interface CityTaxonItem {
  taxon_group: string;
  [cityKey: string]: string | number;
}

/** A top species for a specific city. */
export interface CityTopSpeciesItem {
  city: string;
  rank: number;
  scientific_name: string;
  common_name: string;
  count: number;
  taxon_group: string;
}

// From combined-website: richer PriorityZone with gap analysis
export type TargetTaxaByGroup = Record<string, string[]>;

export interface PriorityZone {
  // Core identifiers
  zone_id: string;  // Maps to hex_id
  hex_id?: string;  // Optional alias

  // Location
  center_lat: number;
  center_lng: number;

  // Performance metrics
  priority_score: number;
  priority_category: 'HIGH_PRIORITY' | 'MEDIUM_PRIORITY' | 'LOW_PRIORITY' | 'NO_DATA' | 'INSUFFICIENT_DATA';

  // Non-CNC baseline
  non_cnc_observation_count: number;
  non_cnc_unique_species: number;
  non_cnc_biodiversity_yield: number;

  // CNC performance
  cnc_observation_count: number;
  cnc_unique_species: number;
  cnc_biodiversity_yield: number;

  // Gap analysis
  mobilization_gap: number;

  // Recommendations
  rationale: string;
  recommended_time?: string;
  recommended_actions?: string[];
  target_taxa?: TargetTaxaByGroup;

  // Geography
  geometry: GeoJSON.Geometry;

  // Legacy fields (optional for backwards compatibility)
  name?: string;
  radius_km?: number;
}

export interface MarkerData {
  lat: number;
  lng: number;
  popup?: string;
}

export interface HeatmapPoint {
  lat: number;
  lng: number;
  intensity: number;
}

export interface TemporalTrend {
  date: string;
  count: number;
  research_count?: number;
  taxon_group?: string;
}

/** One point on the species accumulation curve. */
export interface SpeciesAccumulationPoint {
  observation_count: number;
  unique_species: number;
}

export interface HourlyByDowItem {
  day_of_week: number;
  day_name: string;
  hour: number;
  count: number;
}

/** Histogram bucket for user contribution. */
export interface UserContributionBucket {
  bucket_label: string;
  user_count: number;
}

export interface TimingWindow {
  day_of_week: string;
  hour: number;
  observation_count: number;
  unique_species: number;
  efficiency_score: number;
}

// Exploratory dashboard (Page 1)
export interface ExploratoryKPIs {
  total_observations: number;
  unique_species: number;
  unique_observers: number;
  date_range_start: string | null;
  date_range_end: string | null;
  research_grade_pct: number | null;
}

export interface QualityGradeItem {
  grade: string;
  count: number;
  pct: number;
}

export interface CaptiveWild {
  captive_count: number;
  wild_count: number;
  captive_pct: number;
  wild_pct: number;
}

export interface ByCommunityItem {
  community: string;
  count: number;
}

export interface ByHourItem {
  hour: number;
  count: number;
}

export interface UserContributionDashboard {
  buckets: { bucket_label: string; user_count: number; total_obs?: number; segment_name?: string }[];
  pareto_pct: number | null;
  pareto_label: string | null;
  mean_obs_per_user?: number | null;
  median_obs_per_user?: number | null;
  mode_obs_per_user?: number | null;
  mode_bucket?: string | null;
  pareto_curve?: { user_pct: number; obs_pct: number }[];
  research_rate_by_segment?: { bucket_label: string; research_pct: number }[];
}

export interface UserRetention {
  users_2024: number;
  users_2025: number;
  users_both: number;
  users_2024_only: number;
  retention_pct: number | null;
}

export interface TopSpeciesItem {
  species: string;
  count: number;
}

export interface UploadDelayResponse {
  same_day_pct: number;
  median_hours: number;
  histogram: { bucket: string; count: number }[];
}

export interface ResearchRateByTaxonItem {
  taxon_group: string;
  total: number;
  research_pct: number;
}

export interface ExploratoryDashboard {
  kpis: ExploratoryKPIs;
  quality_grade: QualityGradeItem[];
  captive_wild: CaptiveWild | null;
  by_community: ByCommunityItem[];
  by_sd_neighborhood?: ByCommunityItem[];
  by_hour: ByHourItem[];
  user_contribution: UserContributionDashboard;
  top_species: TopSpeciesItem[];
  upload_delay: UploadDelayResponse | null;
  research_rate_by_taxon: ResearchRateByTaxonItem[];
  taxonomy_summary?: SpeciesSummary[];
  temporal_trends?: TemporalTrend[];
  hourly_by_dow?: HourlyByDowItem[];
  user_retention?: UserRetention | null;
}

// From combined-website: strategy map types
export type MapHex = {
  zone_id: string;
  center_lat: number;
  center_lng: number;
  priority_score: number;
  geometry: GeoJSON.Geometry;
  priority_category?: PriorityZone['priority_category'];
};

export type PriorityZonesBundle = { hexes: MapHex[]; top: PriorityZone[] };