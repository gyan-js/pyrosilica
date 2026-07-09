import Ajv from 'ajv';

export const SUPPORTED_SCHEMA_VERSION = 1;

const frameSchema = {
  type: 'object',
  required: ['schema_version', 'timestamp', 'gpu'],
  additionalProperties: true,
  properties: {
    schema_version: { type: 'integer' },
    timestamp: { type: 'number' },
    gpu: {
      type: 'object',
      required: ['sm_utilization', 'memory', 'temperature_c', 'power_draw_w', 'clock_mhz'],
      properties: {
        sm_utilization: { type: 'number', minimum: 0, maximum: 100 },
        memory: {
          type: 'object',
          required: ['used_mb', 'total_mb', 'bandwidth_gbps'],
          properties: {
            used_mb: { type: 'number', minimum: 0 },
            total_mb: { type: 'number', minimum: 0 },
            bandwidth_gbps: { type: 'number', minimum: 0 },
          },
        },
        temperature_c: { type: 'number' },
        power_draw_w: { type: 'number', minimum: 0 },
        clock_mhz: { type: 'number', minimum: 0 },
      },
    },
    kernels: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'duration_us'],
        properties: {
          name: { type: 'string' },
          duration_us: { type: 'number', minimum: 0 },
          grid_dim: { type: 'array', items: { type: 'integer' } },
          block_dim: { type: 'array', items: { type: 'integer' } },
        },
      },
    },
    process_memory: {
      type: 'array',
      items: {
        type: 'object',
        required: ['pid', 'used_mb'],
        properties: {
          pid: { type: 'integer' },
          used_mb: { type: 'number', minimum: 0 },
        },
      },
    },
  },
};

const ajv = new Ajv({ allErrors: true });
const validateShape = ajv.compile(frameSchema);

// here im validating both structural shape (Ajv) and schema_version explicit,

export function validateFrame(frame) {
  if (!validateShape(frame)) {
    return { valid: false, errors: validateShape.errors };
  }
  if (frame.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    return {
      valid: false,
      errors: [`unsupported schema_version: ${frame.schema_version} (expected ${SUPPORTED_SCHEMA_VERSION})`],
    };
  }
  return { valid: true, errors: null };
}