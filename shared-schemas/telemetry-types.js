
export const SCHEMA_VERSION = '1.0.0';


const smStateSchema = {
  type: 'object',
  required: [
    'timestamp_ms', 'gpu_index', 'sm_utilization_pct',
    'memory_used_mb', 'memory_total_mb',
    'power_draw_w', 'power_limit_w', 'temperature_c',
    'clock_sm_mhz', 'clock_mem_mhz',
  ],
  additionalProperties: false,
  properties: {
    timestamp_ms: { type: 'number' },
    gpu_index: { type: 'integer', minimum: 0 },
    sm_utilization_pct: { type: 'number', minimum: 0, maximum: 100 },
    memory_used_mb: { type: 'number', minimum: 0 },
    memory_total_mb: { type: 'number', minimum: 0 },
    
    power_draw_w: { type: ['number', 'null'] },
    power_limit_w: { type: ['number', 'null'] },
    temperature_c: { type: ['number', 'null'] },
    clock_sm_mhz: { type: ['number', 'null'] },
    clock_mem_mhz: { type: ['number', 'null'] },
  },
};


const kernelEventSchema = {
  type: 'object',
  required: ['name', 'start_ts_ms', 'duration_ms', 'grid_dim', 'block_dim', 'source', 'stream_id'],
  additionalProperties: false,
  properties: {
    name: { type: 'string' },
    start_ts_ms: { type: 'number' },
    duration_ms: { type: 'number', minimum: 0 },
    grid_dim: {
      type: 'array', items: { type: 'integer', minimum: 1 }, minItems: 3, maxItems: 3,
    },
    block_dim: {
      type: 'array', items: { type: 'integer', minimum: 1 }, minItems: 3, maxItems: 3,
    },
    source: { type: 'string', enum: ['cupti', 'sampled'] },
    
    stream_id: { type: ['integer', 'null'] },
  },
};


const layerMemoryDeltaSchema = {
  type: 'object',
  required: ['layer_name', 'delta_mb', 'timestamp_ms'],
  additionalProperties: false,
  properties: {
    layer_name: { type: 'string' },
    delta_mb: { type: 'number' },
    timestamp_ms: { type: 'number' },
  },
};


const memorySnapshotSchema = {
  type: 'object',
  required: ['timestamp_ms', 'pid', 'process_memory_mb', 'per_layer_deltas'],
  additionalProperties: false,
  properties: {
    timestamp_ms: { type: 'number' },
    pid: { type: 'integer', minimum: 0 },
    process_memory_mb: { type: 'number', minimum: 0 },
    per_layer_deltas: { type: 'array', items: layerMemoryDeltaSchema },
  },
};


const trainingMetricsSchema = {
  type: 'object',
  required: ['step', 'loss', 'throughput_samples_per_sec', 'extra'],
  additionalProperties: false,
  properties: {
    step: { type: ['integer', 'null'] },
    loss: { type: ['number', 'null'] },
    throughput_samples_per_sec: { type: ['number', 'null'] },
    extra: { type: 'object' },
  },
};


export const telemetryFrameSchema = {
  $id: 'telemetry-frame.schema.json',
  type: 'object',
  required: ['frame_id', 'schema_version', 'tick_rate_hz', 'sm_state', 'kernel_events', 'memory_snapshot', 'training_metrics'],
  additionalProperties: false,
  properties: {
    frame_id: { type: 'integer', minimum: 0 },
    schema_version: { type: 'string' },
    tick_rate_hz: { type: 'number', exclusiveMinimum: 0 },
    sm_state: { oneOf: [smStateSchema, { type: 'null' }] },
    kernel_events: { type: 'array', items: kernelEventSchema },
    memory_snapshot: { oneOf: [memorySnapshotSchema, { type: 'null' }] },
    training_metrics: { oneOf: [trainingMetricsSchema, { type: 'null' }] },
  },
};


import Ajv from 'ajv';

const ajv = new Ajv({ allErrors: true, strict: true });
const _validateFrame = ajv.compile(telemetryFrameSchema);

export function validateTelemetryFrame(payload) {
  const valid = _validateFrame(payload);
  return { valid, errors: valid ? null : _validateFrame.errors };
}


