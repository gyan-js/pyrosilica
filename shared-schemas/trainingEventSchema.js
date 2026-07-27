
import Ajv from 'ajv';

export const SCHEMA_VERSION = '1.0.0';


const EVENT_TYPES = [
  'layer_forward_start',
  'layer_forward_end',
  'layer_backward_start',
  'layer_backward_end',
  'optimizer_step',
  'step_start',
  'step_end',
  'epoch_start',
  'epoch_end',
  'run_start',
  'run_end',
];

export const trainingEventSchema = {
  $id: 'training-event.schema.json',
  type: 'object',
  required: ['type', 'node_id', 'step', 'epoch', 'timestamp', 'meta', 'schema_version', 'stream'],
  additionalProperties: false,
  properties: {
    type: { type: 'string', enum: EVENT_TYPES },
   
    node_id: { type: ['string', 'null'] },
    step: { type: 'integer', minimum: 0 },
    epoch: { type: 'integer', minimum: 0 },
    timestamp: { type: 'number' },
    meta: { type: 'object' },
    schema_version: { type: 'string' },
    stream: { const: 'training' },
  },
};

const ajv = new Ajv({ allErrors: true, strict: true });
const _validateEvent = ajv.compile(trainingEventSchema);

export function validateTrainingEvent(payload) {
  const valid = _validateEvent(payload);
  return { valid, errors: valid ? null : _validateEvent.errors };
}