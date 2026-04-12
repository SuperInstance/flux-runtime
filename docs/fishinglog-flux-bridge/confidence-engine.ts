/**
 * confidence-engine.ts — Confidence Computing Layer for FishingLog AI
 *
 * Implements the confidence computation pipeline that wraps fish species
 * classification results through FLUX confidence registers. This module is
 * the bridge between ML model outputs (YOLOv8 predictions, Whisper intents)
 * and FLUX bytecode confidence propagation.
 *
 * Features:
 *   - Bayesian fusion: combines confidences from multiple models / sensors
 *   - Species classification confidence aggregation
 *   - Confidence decay over time (staleness tracking)
 *   - Threshold-based alert triggers (low confidence → captain notification)
 *
 * Author: Super Z (FLUX Fleet, Task 2-b)
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single model prediction from YOLOv8, Whisper, or any sensor source. */
export interface Prediction {
  /** Predicted class label (e.g. "halibut", "cod", "pacific_halibut"). */
  label: string;
  /** Raw confidence score in [0, 1]. */
  confidence: number;
  /** Source of the prediction — used for weighting. */
  source: 'vision' | 'audio' | 'human' | 'sonar' | 'historical';
  /** ISO-8601 timestamp when this prediction was made. */
  timestamp: string;
  /** Optional bounding box or measurement data. */
  metadata?: Record<string, number>;
}

/** Aggregated result after confidence fusion. */
export interface ConfidenceResult {
  /** Final predicted label. */
  label: string;
  /** Fused confidence score in [0, 1]. */
  confidence: number;
  /** Individual source contributions. */
  sources: Array<{ source: Prediction['source']; weight: number; confidence: number }>;
  /** Whether an alert should be triggered (confidence below threshold). */
  alertTriggered: boolean;
  /** Human-readable alert reason, if applicable. */
  alertReason?: string;
  /** Number of milliseconds since the oldest prediction. */
  stalenessMs: number;
}

/** Configuration for the confidence engine. */
export interface ConfidenceEngineConfig {
  /** Source credibility weights (default: vision=0.4, human=0.35, audio=0.15, sonar=0.07, historical=0.03). */
  sourceWeights?: Partial<Record<Prediction['source'], number>>;
  /** Alert threshold — trigger if fused confidence below this value (default 0.65). */
  alertThreshold?: number;
  /** Regulatory threshold — below this, classification cannot be used for compliance (default 0.80). */
  regulatoryThreshold?: number;
  /** Confidence half-life in milliseconds (default 300_000 = 5 minutes). */
  confidenceHalfLifeMs?: number;
}

// ---------------------------------------------------------------------------
// Default configuration
// ---------------------------------------------------------------------------
const DEFAULT_WEIGHTS: Record<Prediction['source'], number> = {
  vision:     0.40,
  human:      0.35,  // Captain's voice correction is high-trust
  audio:      0.15,  // Whisper intent recognition
  sonar:      0.07,  // Sonar-based species detection
  historical: 0.03,  // Historical catch patterns
};

// ---------------------------------------------------------------------------
// ConfidenceEngine
// ---------------------------------------------------------------------------

export class ConfidenceEngine {
  private readonly weights: Record<Prediction['source'], number>;
  private readonly alertThreshold: number;
  private readonly regulatoryThreshold: number;
  private readonly halfLifeMs: number;

  /** In-memory cache of recent predictions for temporal decay. */
  private recentPredictions: Prediction[] = [];

  constructor(config: ConfidenceEngineConfig = {}) {
    this.weights = { ...DEFAULT_WEIGHTS, ...config.sourceWeights };
    this.alertThreshold = config.alertThreshold ?? 0.65;
    this.regulatoryThreshold = config.regulatoryThreshold ?? 0.80;
    this.halfLifeMs = config.confidenceHalfLifeMs ?? 300_000;
  }

  // ---- Public API --------------------------------------------------------

  /**
   * Compute the fused confidence for a set of predictions about the same
   * fish specimen / classification event.
   *
   * Uses Bayesian-inspired harmonic mean for combining multiple predictions
   * of the same label, weighted by source credibility and temporal decay.
   */
  computeConfidence(predictions: Prediction[]): ConfidenceResult {
    if (predictions.length === 0) {
      return {
        label: 'unknown',
        confidence: 0,
        sources: [],
        alertTriggered: true,
        alertReason: 'No predictions provided',
        stalenessMs: 0,
      };
    }

    const now = Date.now();

    // 1. Group predictions by label
    const grouped = this.groupByLabel(predictions);

    // 2. Compute per-label fused confidence
    const labelScores = Array.from(grouped.entries()).map(([label, preds]) => {
      const sources = preds.map((p) => {
        const rawWeight = this.weights[p.source];
        const decay = this.computeDecay(p.timestamp, now);
        const effectiveConf = p.confidence * decay;
        return { source: p.source, weight: rawWeight * decay, confidence: effectiveConf, raw: p.confidence };
      });

      // Weighted average confidence
      const totalWeight = sources.reduce((s, x) => s + x.weight, 0);
      const fusedConf = totalWeight > 0
        ? sources.reduce((s, x) => s + x.confidence * x.weight, 0) / totalWeight
        : 0;

      // Bayesian harmonic mean across sources (punishes disagreement)
      const harmonicMean = this.bayesianHarmonicMean(preds, now);

      // Blend weighted average (60%) with harmonic mean (40%)
      const finalConf = fusedConf * 0.6 + harmonicMean * 0.4;

      return { label, confidence: finalConf, sources: preds.map((p) => ({
        source: p.source,
        weight: this.weights[p.source],
        confidence: p.confidence,
      })) };
    });

    // 3. Select the label with highest fused confidence
    labelScores.sort((a, b) => b.confidence - a.confidence);
    const best = labelScores[0];

    // 4. Compute staleness
    const oldestTs = Math.min(...predictions.map((p) => new Date(p.timestamp).getTime()));
    const stalenessMs = now - oldestTs;

    // 5. Determine alert
    const alertTriggered = best.confidence < this.alertThreshold;
    const regulatoryFail = best.confidence < this.regulatoryThreshold;

    let alertReason: string | undefined;
    if (alertTriggered) {
      if (best.confidence < 0.30) {
        alertReason = `Very low confidence (${(best.confidence * 100).toFixed(1)}%) — manual identification required`;
      } else if (regulatoryFail) {
        alertReason = `Below regulatory threshold (${(best.confidence * 100).toFixed(1)}% < ${(this.regulatoryThreshold * 100).toFixed(0)}%) — cannot use for ADFG/NOAA reporting`;
      } else {
        alertReason = `Low confidence (${(best.confidence * 100).toFixed(1)}%) — captain review recommended`;
      }
    }

    // 6. Cache for future decay computation
    this.recentPredictions.push(...predictions);
    this.pruneCache(now);

    return {
      label: best.label,
      confidence: best.confidence,
      sources: best.sources,
      alertTriggered,
      alertReason,
      stalenessMs,
    };
  }

  /**
   * Apply time-based decay to a stored confidence value.
   * Uses exponential decay: confidence *= 2^(-elapsed / halfLife).
   */
  decayConfidence(confidence: number, timestamp: string, now?: number): number {
    return confidence * this.computeDecay(timestamp, now ?? Date.now());
  }

  /** Get the current alert threshold. */
  getAlertThreshold(): number {
    return this.alertThreshold;
  }

  /** Get the regulatory threshold. */
  getRegulatoryThreshold(): number {
    return this.regulatoryThreshold;
  }

  /** Clear the prediction cache. */
  reset(): void {
    this.recentPredictions = [];
  }

  // ---- Internal helpers --------------------------------------------------

  /** Group predictions by label. */
  private groupByLabel(predictions: Prediction[]): Map<string, Prediction[]> {
    const map = new Map<string, Prediction[]>();
    for (const p of predictions) {
      const key = p.label.toLowerCase();
      const group = map.get(key) ?? [];
      group.push(p);
      map.set(key, group);
    }
    return map;
  }

  /**
   * Bayesian harmonic mean for combining multiple confidence estimates.
   * Formula:  n / Σ(1/c_i)  — naturally downweights low-confidence sources.
   * Each source is further weighted by its credibility and temporal decay.
   */
  private bayesianHarmonicMean(predictions: Prediction[], now: number): number {
    if (predictions.length === 1) {
      return predictions[0].confidence * this.computeDecay(predictions[0].timestamp, now);
    }

    let sumInverse = 0;
    for (const p of predictions) {
      const decay = this.computeDecay(p.timestamp, now);
      const effective = Math.max(p.confidence * decay, 0.001); // floor to avoid div/0
      sumInverse += 1 / effective;
    }

    return predictions.length / sumInverse;
  }

  /**
   * Exponential time decay: factor = 2^(-elapsed / halfLife).
   * After one half-life, confidence is halved.
   */
  private computeDecay(timestamp: string, now: number): number {
    const ts = new Date(timestamp).getTime();
    const elapsed = now - ts;
    if (elapsed <= 0) return 1.0;
    return Math.pow(2, -elapsed / this.halfLifeMs);
  }

  /** Remove predictions older than 4 half-lives (>93.75% decayed). */
  private pruneCache(now: number): void {
    const cutoff = this.halfLifeMs * 4;
    this.recentPredictions = this.recentPredictions.filter(
      (p) => now - new Date(p.timestamp).getTime() < cutoff,
    );
  }
}
